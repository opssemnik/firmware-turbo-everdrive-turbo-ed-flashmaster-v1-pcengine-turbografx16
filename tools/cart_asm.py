"""Bank 13 code (mapped at $c000 through MPR6): themes, banner/help/splash, SD + artwork.

Conventions
- Everything that touches the VDC or the SD card runs with interrupts off (php/sei ... plp)
  and puts the OS's VDC register selection (zp $f7) back before returning.
- Zero page $20-$3f is ours: the OS only uses it inside the flash-programming routines,
  which end in a reset. RAM clear at boot zeroes it.
- SD access mirrors the OS: CMD12 (stop the stream the OS left open), CMD18 + blocks,
  and the stream is left open again so the OS's next CMD12 is valid.
"""

THEME = """
; Theme state lives in VCE CRAM $1FF (sprite pal 15 col 15): bits 0-3 = index, bit 8 = initialised.
; CRAM $1FE keeps the stock bar colour picked by the OS at boot.
VCE_A = $0402
VCE_AH = $0403
VCE_D = $0404
VCE_DH = $0405

theme_cur:              ; -> X = current theme (first call also saves the stock bar colour)
    lda #$ff
    sta VCE_A
    lda #$01
    sta VCE_AH
    lda VCE_D
    and #$0f
    tax
    lda VCE_DH
    and #$01
    bne tc_done
    lda #$32
    sta VCE_A
    stz VCE_AH
    ldy VCE_D
    lda VCE_DH
    and #$01
    pha
    lda #$fe
    sta VCE_A
    lda #$01
    sta VCE_AH
    sty VCE_D
    pla
    sta VCE_DH
    clx
tc_done:
    rts

theme_set:              ; X = theme index: remember it and load its colours
    lda #$ff
    sta VCE_A
    lda #$01
    sta VCE_AH
    stx VCE_D
    lda #$01
    sta VCE_DH
    lda TCOUNT
    jne theme_dat
    phx
    lda offs,x
    tax
    cly
ts_loop:
    lda slots,y
    sta VCE_A
    stz VCE_AH
    lda colors,x
    sta VCE_D
    lda colors+1,x
    sta VCE_DH
    inx
    inx
    iny
    cpy #NSLOTS
    bne ts_loop
    plx
    bne ts_done
    lda #$fe            ; theme 0: put back the stock bar colour
    sta VCE_A
    lda #$01
    sta VCE_AH
    ldy VCE_D
    lda VCE_DH
    and #$01
    pha
    lda #$32
    sta VCE_A
    stz VCE_AH
    sty VCE_D
    pla
    sta VCE_DH
ts_done:
    rts

theme_next:             ; SELECT pressed in the browser
    php
    sei
    jsr theme_cur
    inx
    jsr theme_count
    sta TMP
    cpx TMP
    bcc tn_ok
    clx
tn_ok:
    phx
    jsr theme_set
    plx
    jsr dat_save_theme
    lda <$f7
    sta $0000
    plp
    rts
"""

GFX = """
banner_draw:            ; cls() hook: palette 4 + tiles at VRAM $1000 + BAT rows 30-31; hide art
    php
    sei
    tma #$08            ; graphics data lives in bank 15
    pha
    lda #$0f
    tam #$08
    lda #$40
    sta VCE_A
    stz VCE_AH
    tia B15_BANPAL,VCE_D,32
    st0 #$00
    st1 #$00
    st2 #$10
    st0 #$02
    tia B15_BANTILES,$0002,BAN_TILES_LEN
    pla
    tam #$08
    jsr banner_rows
    jsr panel_hide
    lda #$ff            ; forget the selection so the art reloads after the redraw
    sta SEL
    stz STABLE
    lda <$f7
    sta $0000
    plp
    rts

help_check:             ; draw the help line in BAT row 0 unless it is already there
    st0 #$01
    st1 #HELP_PROBE_COL
    st2 #$00
    st0 #$02
    lda $0002
    cmp #lo(HELP_PROBE)
    bne hc_draw
    lda $0003
    cmp #hi(HELP_PROBE)
    beq hc_done
hc_draw:
    tma #$08
    pha
    lda #$0f
    tam #$08
    st0 #$00
    st1 #$00
    st2 #$00
    st0 #$02
    tia B15_HELPMAP,$0002,64
    pla
    tam #$08
hc_done:
    rts

idle:                   ; every frame of the browser's wait-for-key loop
    php
    sei
    jsr help_check
    lda FLAGS
    and #$01
    bne id_init_done
    jsr dat_init
id_init_done:
    stz INJ
    jsr goto_tick
    lda INJ
    bne id_noinput
    jsr input_tick
id_noinput:
    lda FLAGS
    and #$02
    beq id_out
    jsr art_tick
id_out:
    lda <$f7
    sta $0000
    plp
    lda INJ
    rts

splash:                 ; boot splash: palette 5, tiles (bank 14) at VRAM $2000, BAT (bank 15)
    php
    sei
    tma #$08
    pha
    lda #SPL_MAP_BANK
    tam #$08
    lda #$50
    sta VCE_A
    stz VCE_AH
    tia B15_SPLPAL,VCE_D,32
    st0 #$00
    st1 #$00
    st2 #$20
    st0 #$02
    lda #SPL_TILE_BANK
    tam #$08
    tia $6000,$0002,SPL_TILES_LEN
    lda #SPL_MAP_BANK
    tam #$08
    st0 #$00
    st1 #$00
    st2 #$00
    st0 #$02
    tia $6000,$0002,4096
    pla
    tam #$08
    lda <$f7
    sta $0000
    plp
    lda #SPLASH_FRAMES
sp_wait:
    pha
    ldx #$01            ; vsync(1)
    cla
    ldy #$01
    jsr $f01a
    pla
    ldx $222d           ; any button newly pressed?
    bne sp_go
    dec a
    bne sp_wait
sp_go:
    jmp $eda9           ; cls (draws the banner) and return to main
"""

SDART = """
; ---------------------------------------------------------------- state: RAM $2020-$203f (zero page area, absolute addressing)
DAT = $2020               ; LBA of RGPOA.DAT sector 0 (4 bytes)
FLAGS = $2024             ; bit0 lookup done, bit1 file valid
NBMASK = $2025
SEL = $2026               ; hash of the selection being tracked (4 bytes)
STABLE = $202a            ; frames the selection has been stable
SHOWN = $202b
LBA = $202c               ; 4 bytes
ARG = $2030               ; 4 bytes, SD command argument
H = $2034                 ; 4 bytes, computed hash
T = $2038                 ; 4 bytes temp
CNT = $203c
CNT2 = $20de
TMP = $203d
R = $203e
R2 = $203f
SD_DATA = $e000
SD_STAT = $e004
SD_CTRL = $e008
CARDTYPE = $2985        ; OS: bit0 = block addressing (SDHC)
FS_DATA = $30b5         ; OS FAT: LBA of cluster 2
FS_BPC = $30b9          ; OS FAT: bytes per cluster
FS_ROOT = $30bd         ; OS FAT: root directory cluster
SCR = $7c00             ; VRAM scratch for one sector
ART_VRAM = $4000        ; sprite patterns

; ---------------------------------------------------------------- VRAM address helpers
vram_w:                 ; X = lo, A = hi: MAWR, select VWR
    st0 #$00
    stx $0002
    sta $0003
    st0 #$02
    rts
vram_r:                 ; X = lo, A = hi: MARR, select VRR
    st0 #$01
    stx $0002
    sta $0003
    st0 #$02
    rts

; ---------------------------------------------------------------- SPI / SD (same register use as the OS)
spi:                    ; A out -> A in
    sta SD_DATA
spi_w:
    lda SD_STAT
    and #$01
    beq spi_w
    lda SD_DATA
    rts
cs_high:
    lda SD_CTRL
    ora #$01
    sta SD_CTRL
    lda SD_STAT
    rts
cs_low:
    lda SD_CTRL
    and #$fe
    sta SD_CTRL
    rts

sd_cmd:                 ; A = command byte, ARG = argument -> A = R1
    pha
    jsr cs_high
    jsr cs_low
    lda #$ff
    jsr spi
    lda #$ff
    jsr spi
    pla
    jsr spi
    lda ARG+3
    jsr spi
    lda ARG+2
    jsr spi
    lda ARG+1
    jsr spi
    lda ARG
    jsr spi
    lda #$95
    jsr spi
    ldx #$10
sc_r1:
    lda #$ff
    jsr spi
    cmp #$ff
    bne sc_done
    dex
    bne sc_r1
sc_done:
    pha
    jsr cs_high
    pla
    rts

set_arg_lba:            ; ARG = LBA (SDHC) or LBA * 512
    lda CARDTYPE
    and #$01
    beq sa_byte
    lda LBA
    sta ARG
    lda LBA+1
    sta ARG+1
    lda LBA+2
    sta ARG+2
    lda LBA+3
    sta ARG+3
    rts
sa_byte:
    stz ARG
    lda LBA
    asl a
    sta ARG+1
    lda LBA+1
    rol a
    sta ARG+2
    lda LBA+2
    rol a
    sta ARG+3
    rts

stop_stream:            ; CMD12, like the OS does before every read
    stz ARG
    stz ARG+1
    stz ARG+2
    stz ARG+3
    lda #$4c
    jmp sd_cmd

read_blocks:            ; LBA, X = count -> VRAM at the current MAWR. C=1 on error. Stream left open.
    phx
    jsr stop_stream
    jsr set_arg_lba
    lda #$52
    jsr sd_cmd
    plx
    cmp #$00
    bne rb_err
    stx CNT
    jsr cs_low
rb_block:
    ldy #$00
    ldx #$00
rb_tok:
    lda #$ff
    sta SD_DATA
    lda SD_DATA
    cmp #$fe
    beq rb_go
    dey
    bne rb_tok
    dex
    bne rb_tok
    bra rb_err
rb_go:
    lda SD_CTRL
    ora #$04
    sta SD_CTRL
    lda SD_DATA
    ldx #$00
rb_loop:
    lda SD_DATA
    sta $0002
    lda SD_DATA
    sta $0003
    dex
    bne rb_loop
    lda SD_DATA
    lda SD_CTRL
    and #$03
    sta SD_CTRL
    dec CNT
    bne rb_block
    clc
    rts
rb_err:
    sec
    rts

read_scr:               ; one sector at LBA -> VRAM scratch
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_w
    ldx #$01
    jmp read_blocks

lba_inc:
    inc LBA
    bne li_done
    inc LBA+1
    bne li_done
    inc LBA+2
    bne li_done
    inc LBA+3
li_done:
    rts

lba_from_dat:           ; LBA = DAT + T
    clc
    lda DAT
    adc T
    sta LBA
    lda DAT+1
    adc T+1
    sta LBA+1
    lda DAT+2
    adc T+2
    sta LBA+2
    lda DAT+3
    adc T+3
    sta LBA+3
    rts

clus2lba:               ; T = cluster -> LBA = FS_DATA + (T - 2) * sectors_per_cluster
    sec
    lda T
    sbc #$02
    sta T
    lda T+1
    sbc #$00
    sta T+1
    lda T+2
    sbc #$00
    sta T+2
    lda T+3
    sbc #$00
    sta T+3
    lda FS_BPC+1        ; sectors per cluster = bytes per cluster >> 9
    sta TMP
    lda FS_BPC+2
    lsr a
    ror TMP
    lda TMP
    bne cl_shift
    inc TMP
cl_shift:
    lda TMP
    cmp #$01
    beq cl_add
    lsr TMP
    asl T
    rol T+1
    rol T+2
    rol T+3
    bra cl_shift
cl_add:
    clc
    lda T
    adc FS_DATA
    sta LBA
    lda T+1
    adc FS_DATA+1
    sta LBA+1
    lda T+2
    adc FS_DATA+2
    sta LBA+2
    lda T+3
    adc FS_DATA+3
    sta LBA+3
    rts

; ---------------------------------------------------------------- RGPOA.DAT lookup (root directory)
dat_init:
    lda FLAGS
    ora #$01
    sta FLAGS
    lda FS_ROOT
    sta T
    lda FS_ROOT+1
    sta T+1
    lda FS_ROOT+2
    sta T+2
    lda FS_ROOT+3
    sta T+3
    jsr clus2lba
    lda #ROOT_SECTORS
    sta R
di_sector:
    jsr read_scr
    bcs di_fail
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    ldy #$10
di_entry:
    stz TMP             ; mismatch flag
    stz R2              ; end-of-directory flag
    clx
di_bytes:
    lda $0002
    jsr di_byte
    inx
    lda $0003
    jsr di_byte
    inx
    cpx #$20
    bne di_bytes
    lda R2
    bne di_fail
    lda TMP
    beq di_found
    dey
    bne di_entry
    jsr lba_inc
    dec R
    bne di_sector
di_fail:
    rts

di_byte:                ; A = byte X of a directory entry
    cpx #$00
    bne db_name
    cmp #$00
    bne db_name
    inc R2
db_name:
    cpx #$0b
    bcs db_attr
    cmp name83,x
    beq db_ret
    inc TMP
    rts
db_attr:
    bne db_c20
    and #$18            ; directory or volume label
    beq db_ret
    inc TMP
    rts
db_c20:
    cpx #$14
    bne db_c21
    sta T+2
db_c21:
    cpx #$15
    bne db_c26
    sta T+3
db_c26:
    cpx #$1a
    bne db_c27
    sta T
db_c27:
    cpx #$1b
    bne db_ret
    sta T+1
db_ret:
    rts

di_found:
    jsr clus2lba
    lda LBA
    sta DAT
    lda LBA+1
    sta DAT+1
    lda LBA+2
    sta DAT+2
    lda LBA+3
    sta DAT+3
    jsr check_header
    bcs di_fail
    lda FLAGS
    ora #$02
    sta FLAGS
    lda #hi(SCR)        ; word 8: lo = theme, hi = bucket count
    ldx #lo(SCR+8)
    jsr vram_r
    lda $0002
    sta R2
    lda $0003
    dec a
    sta NBMASK
    lda $0002           ; word 9: version, theme count
    lda $0003
    sta TCOUNT
    lda $0002           ; words 10-11: theme table sector
    sta TTAB
    lda $0003
    sta TTAB+1
    lda $0002
    sta TTAB+2
    lda $0003
    sta TTAB+3
    jsr theme_cur       ; saves the stock bar colour on first use
    jsr theme_count
    sta TMP
    ldx R2
    cpx TMP
    bcs di_done
    jsr theme_set
di_done:
    rts

check_header:           ; LBA = DAT: read sector 0, C=0 if the magic matches
    lda DAT
    sta LBA
    lda DAT+1
    sta LBA+1
    lda DAT+2
    sta LBA+2
    lda DAT+3
    sta LBA+3
    jsr read_scr
    bcs ch_bad
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    clx
ch_loop:
    lda $0002
    cmp dat_magic,x
    bne ch_bad
    inx
    lda $0003
    cmp dat_magic,x
    bne ch_bad
    inx
    cpx #$10
    bne ch_loop
    clc
    rts
ch_bad:
    sec
    rts

; ---------------------------------------------------------------- writes (RGPOA.DAT sectors 0..WRITABLE-1 only)
ws_badj:
    sec
    rts
write_scr:              ; VRAM scratch -> sector LBA. Caller has just read + verified that sector. C=1 on error
    sec                 ; the file must sit in the FAT data area
    lda DAT
    sbc FS_DATA
    lda DAT+1
    sbc FS_DATA+1
    lda DAT+2
    sbc FS_DATA+2
    lda DAT+3
    sbc FS_DATA+3
    bcc ws_badj
    sec                 ; and LBA must be one of the file's writable sectors
    lda LBA
    sbc DAT
    sta T
    lda LBA+1
    sbc DAT+1
    sta T+1
    lda LBA+2
    sbc DAT+2
    sta T+2
    lda LBA+3
    sbc DAT+3
    sta T+3
    bcc ws_badj
    lda T+1
    ora T+2
    ora T+3
    bne ws_badj
    lda T
    cmp #WRITABLE
    bcs ws_badj
    jsr stop_stream
    jsr set_arg_lba
    lda #$58            ; CMD24 write block
    jsr sd_cmd
    cmp #$00
    beq ws_cmdok
    jmp ws_fail
ws_cmdok:
    jsr cs_low
    lda #$ff
    jsr spi
    lda #$fe
    jsr spi
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    cly
ws_loop:
    lda $0002
    jsr spi
    lda $0003
    jsr spi
    iny
    bne ws_loop
    lda #$ff            ; CRC (ignored in SPI mode)
    jsr spi
    lda #$ff
    jsr spi
    lda #$ff            ; data response: xxx00101 = accepted
    jsr spi
    and #$1f
    sta TMP
    ldy #$00
    ldx #$00
ws_busy:
    lda #$ff
    jsr spi
    cmp #$00
    bne ws_done
    dey
    bne ws_busy
    dex
    bne ws_busy
ws_done:
    jsr cs_high
    jsr read_scr        ; leaves a read stream open, like the OS expects
    lda TMP
    cmp #$05
    bne ws_bad
    clc
    rts
ws_fail:
    jsr read_scr
ws_bad:
    sec
    rts

dat_save_theme:         ; X = theme -> byte 16 of sector 0
    lda FLAGS
    and #$02
    bne ds_ok1
    rts
ds_ok1:
    stx R2
    jsr check_header    ; re-read and verify right before writing (LBA = DAT)
    bcc ds_ok2
    rts
ds_ok2:
    ldx #lo(SCR+8)
    lda #hi(SCR)
    jsr vram_r
    lda $0002
    lda $0003
    sta TMP             ; keep the bucket count byte
    ldx #lo(SCR+8)
    lda #hi(SCR)
    jsr vram_w
    lda R2
    sta $0002
    lda TMP
    sta $0003
    jmp write_scr

; ---------------------------------------------------------------- artwork
sel_hash:               ; H = hash of the name in the bottom bar (BAT rows 24-25)
    stz H
    stz H+1
    stz H+2
    stz H+3
    ldx #$00
    lda #$06
    jsr vram_r
    ldy #$80
sh_loop:
    lda $0002           ; lo first: reading hi advances MARR
    sta TMP
    lda $0003
    and #$07            ; tiles $100+ are not font characters
    bne sh_next
    lda TMP
    sec
    sbc #$60
    cmp #$21
    bcc sh_next
    cmp #$7f
    bcs sh_next
    cmp #$2e
    beq sh_next
    cmp #$61
    bcc sh_add
    cmp #$7b
    bcs sh_add
    sbc #$1f            ; carry clear here: subtracts $20
sh_add:
    clc
    adc H
    sta H
    lda H+1
    adc #$00
    sta H+1
    clc
    lda H+2
    adc H
    sta H+2
    lda H+3
    adc H+1
    sta H+3
sh_next:
    dey
    bne sh_loop
    rts

art_tick:
    jsr sel_hash
    ldx #$03
at_cmp:
    lda H,x
    cmp SEL,x
    bne at_changed
    dex
    bpl at_cmp
    lda STABLE
    cmp #ART_DELAY
    beq at_ret
    inc STABLE
    lda STABLE
    cmp #ART_DELAY
    bne at_ret
    jsr art_load
    bcs at_ret
    jmp panel_show
at_changed:
    ldx #$03
at_copy:
    lda H,x
    sta SEL,x
    dex
    bpl at_copy
    stz STABLE
    lda SHOWN
    beq at_ret
    jmp panel_hide
at_ret:
    rts

art_load:               ; look up SEL in the index, load palette + sprites. C=1 if none
    lda SEL
    ora SEL+1
    ora SEL+2
    ora SEL+3
    beq al_fail
    lda SEL
    eor SEL+2
    and NBMASK
    clc
    adc #INDEX_BASE
    sta T
    stz T+1
    stz T+2
    stz T+3
    jsr lba_from_dat
    jsr read_scr
    bcs al_fail
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    ldy #$40
al_scan:
    lda $0002
    sta H
    lda $0003
    sta H+1
    lda $0002
    sta H+2
    lda $0003
    sta H+3
    lda $0002
    sta T
    lda $0003
    sta T+1
    lda $0002
    sta T+2
    lda $0003
    sta T+3
    lda T
    ora T+1
    ora T+2
    ora T+3
    beq al_fail
    ldx #$03
al_cmp:
    lda H,x
    cmp SEL,x
    bne al_next
    dex
    bpl al_cmp
    bra al_found
al_next:
    dey
    bne al_scan
al_fail:
    sec
    rts
al_found:
    jsr lba_from_dat
    jsr read_scr
    bcs al_fail
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    lda $0002
    cmp #$52            ; "RGA1"
    bne al_fail
    lda $0003
    cmp #$47
    bne al_fail
    lda $0002
    cmp #$41
    bne al_fail
    lda $0003
    cmp #$31
    bne al_fail
    lda $0002           ; skip bytes 4-7
    lda $0003
    lda $0002
    lda $0003
    lda #$00            ; sprite palette 0 = CRAM $100
    sta VCE_A
    lda #$01
    sta VCE_AH
    ldx #$10
al_pal:
    lda $0002
    sta VCE_D
    lda $0003
    sta VCE_DH
    dex
    bne al_pal
    jsr lba_inc
    ldx #lo(ART_VRAM)
    lda #hi(ART_VRAM)
    jsr vram_w
    ldx #ART_SPR_SECTORS
    jsr read_blocks
    rts

panel_show:
    ldx #$00
    lda #$7f
    jsr vram_w
    tia sat_on,$0002,48
    lda #$01
    sta SHOWN
    rts

panel_hide:
    ldx #$00
    lda #$7f
    jsr vram_w
    tia sat_off,$0002,48
    stz SHOWN
    rts
"""


def sat(x, y):
    words = []
    for s in range(6):
        sr, sc = divmod(s, 3)
        words += [y + sr * 64 + 64, x + sc * 32 + 32, (0x4000 + s * 0x200) >> 5, 0x3180]
    return ','.join(str(w) for w in words)


def tables(enc):
    """Data after the code: SAT entries for the cover panel, names, magics, menu strings."""
    db = lambda b: ','.join(str(x) for x in b)
    t = '\nsat_on: .dw ' + sat(152, 40)
    t += '\nsat_act: .dw ' + sat(8, 40)
    t += '\nsat_off: .dw ' + ','.join('0' for _ in range(24))
    t += '\nname83: .db "RGPOA   DAT"'
    t += '\ndat_magic: .db "RGPOA-DAT-v3",0,0,0,0'
    t += '\nslot_magic: .db "RGPOA-SLOT"'
    t += '\nopt_row: .db 5,8,11'
    t += '\nopt_tab: .dw s_load,s_fav,s_back,s_unfav'
    t += '\nhub_row: .db 6,9,12'
    t += '\nhub_tab: .dw s_mfav,s_mrec,s_mabout'
    t += '\ntitle_tab: .dw s_tfav,s_trec'
    for name, text in MENU_STRINGS.items():
        t += '\n%s: .db %s' % (name, db(enc(text)))
    return t


MENU_STRINGS = {  # padded so a shorter text erases a longer one
    's_load':    '  Carregar        ',
    's_fav':     '  Favoritar       ',
    's_unfav':   '  Remover favorito',
    's_back':    '  Voltar          ',
    's_cur':     '>',
    's_hint':    'RUN/II: confirmar   I: voltar',
    's_added':   'Adicionado aos favoritos!     ',
    's_removed': 'Removido dos favoritos.       ',
    's_full':    'Favoritos cheios (56).        ',
    's_err':     'Erro ao gravar no SD.         ',
    's_nodat':   'Precisa do RGPOA.DAT no SD.   ',
    's_menu':    'Menu',
    's_mfav':    '  Favoritos',
    's_mrec':    '  Recentes ',
    's_mabout':  '  Sobre    ',
    's_hint_menu': 'RUN/II: abrir    I: voltar   ',
    's_tfav':    'Favoritos',
    's_trec':    'Recentes ',
    's_empty':   'Nenhum jogo nesta lista.',
    's_hint_list': 'RUN/II: ir ao jogo  I: menu  ',
}


ACTION = """
; ---------------------------------------------------------------- action screen (RUN on a file)
NAMEBUF = $3a64         ; OS: name of the selected entry
CURDIR = $30c1          ; OS: cluster of the current directory
ACUR = $2040            ; menu cursor 0..2
AFAV = $2041            ; selected file is a favourite
AART = $2042            ; cover loaded
SBASE = $2043           ; slot scan: first sector (relative), sector count, kind
SCNT = $2044
SKIND = $2045
SS = $2046
SE = $2047
FND_S = $2048
FND_E = $2049
FREE_S = $204a
FREE_E = $204b
MIN_S = $204c
MIN_E = $204d
MINSEQ = $204e
MAXSEQ = $2050
CURSEQ = $2052
MSG = $2054             ; status message pointer (0 = none)
ADI = $2056             ; act_draw loop index (prt uses R/R2/TMP)

action:                 ; -> A = 0 load, 1 back
    ldy #$0e            ; browser local: index of the selected entry
    lda [$00],y
    tax
    iny
    lda [$00],y
    jsr os_open
    ldx #$03
ac_fc:
    lda $3b64,x
    sta FILECL,x
    dex
    bpl ac_fc
    stz ACUR
    stz AFAV
    stz AART
    stz MSG+1
    lda FLAGS
    and #$02
    beq ac_cls
    sei
    jsr sel_hash        ; the bottom bar still shows the file name
    ldx #$03
ac_h:
    lda H,x
    sta SEL,x
    dex
    bpl ac_h
    jsr art_load
    bcs ac_noart
    inc AART
ac_noart:
    jsr fav_scan
    bcs ac_nofav
    lda FND_S
    cmp #$ff
    beq ac_nofav
    inc AFAV
ac_nofav:
    lda <$f7
    sta $0000
    cli
ac_cls:
    jsr $eda9           ; cls (+ banner)
    sei
    jsr act_draw_static
    jsr act_draw
    lda AART
    beq ac_nopanel
    ldx #$00
    lda #$7f
    jsr vram_w
    tia sat_act,$0002,48
ac_nopanel:
    lda <$f7
    sta $0000
    cli
ac_loop:
    ldx #$01            ; vsync(1)
    cla
    ldy #$01
    jsr $f01a
    lda $222d
    beq ac_loop
    bit #$10            ; up
    bne ac_up
    bit #$40            ; down
    bne ac_down
    bit #$0a            ; II or RUN
    bne ac_ok
    bit #$01            ; I
    bne ac_back
    bra ac_loop
ac_up:
    lda ACUR
    bne ac_up1
    lda #$03
ac_up1:
    dec a
    sta ACUR
    bra ac_redraw
ac_down:
    lda ACUR
    inc a
    cmp #$03
    bcc ac_dn1
    cla
ac_dn1:
    sta ACUR
ac_redraw:
    sei
    jsr act_draw
    lda <$f7
    sta $0000
    cli
    bra ac_loop
ac_ok:
    lda ACUR
    beq ac_load
    cmp #$02
    beq ac_back
    sei
    jsr fav_toggle
    jsr act_draw
    lda <$f7
    sta $0000
    cli
    bra ac_loop
ac_load:
    sei
    jsr recent_add
    lda <$f7
    sta $0000
    cli
    jsr $eda9
    cla
    rts
ac_back:
    jsr $eda9
    lda #$01
    rts

prt:                    ; T/T+1 -> string, X = col, Y = BAT row, A = palette, CNT = max chars
    asl a
    asl a
    asl a
    asl a
    sta TMP
    stx R2
    tya
    lsr a
    lsr a
    sta R
    tya
    and #$03
    asl a
    asl a
    asl a
    asl a
    asl a
    asl a
    ora R2
    tax
    lda R
    jsr vram_w
    cly
pr_loop:
    lda [$38],y
    beq pr_end
    cmp #$20
    bcs pr_ch
    lda #$20
pr_ch:
    clc
    adc #$60
    sta $0002
    cla
    adc #$00
    ora TMP
    sta $0003
    iny
    cpy CNT
    bne pr_loop
pr_end:
    rts

act_draw_static:        ; name (2 lines), hint
    lda #lo(NAMEBUF)
    sta T
    lda #hi(NAMEBUF)
    sta T+1
    lda #30
    sta CNT
    ldx #$01
    ldy #$01
    lda #$02
    jsr prt
    ldx #$00            ; second line only if the name is longer than 30
ads_len:
    lda NAMEBUF,x
    beq ads_hint
    inx
    cpx #30
    bne ads_len
    lda #lo(NAMEBUF+30)
    sta T
    lda #hi(NAMEBUF+30)
    sta T+1
    ldx #$01
    ldy #$02
    lda #$02
    jsr prt
ads_hint:
    lda #lo(s_hint)
    sta T
    lda #hi(s_hint)
    sta T+1
    ldx #$01
    ldy #23
    lda #$01
    jmp prt

act_draw:               ; the three options, cursor, status line
    lda #30
    sta CNT
    stz ADI               ; option index
ad_opt:
    lda ADI
    asl a
    tax
    cpx #$02
    bne ad_lbl
    lda AFAV            ; option 1 reads "Remover favorito" when it is one
    beq ad_lbl
    ldx #$06
ad_lbl:
    lda opt_tab,x
    sta T
    lda opt_tab+1,x
    sta T+1
    ldx ADI
    lda opt_row,x
    tay
    lda ADI
    cmp ACUR
    beq ad_sel
    lda #$01
    bra ad_put
ad_sel:
    cla
ad_put:
    ldx #13
    phy
    jsr prt
    ply
    lda ADI
    cmp ACUR
    bne ad_next
    lda #lo(s_cur)      ; cursor mark on the selected option
    sta T
    lda #hi(s_cur)
    sta T+1
    ldx #13
    cla
    jsr prt
ad_next:
    inc ADI
    lda ADI
    cmp #$03
    bne ad_opt
    lda MSG+1
    beq ad_done
    lda MSG
    sta T
    lda MSG+1
    sta T+1
    ldx #$01
    ldy #20
    lda #$02
    jmp prt
ad_done:
    rts

; ---------------------------------------------------------------- slots in RGPOA.DAT
; sector: "RGPOA-SLOT" kind(1) rel_sector(1) 0 0 0 0, then 7 entries of 64 bytes:
;   cluster u32 (0 = empty), seq u16, name[58] (56 chars + NUL padding)
ent_addr:               ; X/A = VRAM address of entry SE
    lda SE
    asl a
    asl a
    asl a
    asl a
    asl a
    clc
    adc #lo(SCR+8)
    tax
    lda #hi(SCR)
    rts

slot_read:              ; sector SBASE+SS -> SCR, verified. C=1 on error
    clc
    lda SBASE
    adc SS
    sta R2
    sta T
    stz T+1
    stz T+2
    stz T+3
    jsr lba_from_dat
    jsr read_scr
    bcs sr_bad
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    clx
sr_mag:
    lda $0002
    cmp slot_magic,x
    bne sr_bad
    inx
    lda $0003
    cmp slot_magic,x
    bne sr_bad
    inx
    cpx #$0a
    bne sr_mag
    lda $0002
    cmp SKIND
    bne sr_bad
    lda $0003
    cmp R2
    bne sr_bad
    clc
    rts
sr_bad:
    sec
    rts

slot_scan:              ; SBASE/SCNT/SKIND -> FND, FREE, MIN, MAXSEQ. C=1 on error
    lda #$ff
    sta FND_S
    sta FREE_S
    sta MIN_S
    sta MINSEQ
    sta MINSEQ+1
    stz MAXSEQ
    stz MAXSEQ+1
    stz SS
ss_sec:
    jsr slot_read
    bcc ss_ok
    rts
ss_ok:
    stz SE
ss_ent:
    jsr ent_addr
    jsr vram_r
    lda $0002
    sta T
    lda $0003
    sta T+1
    lda $0002
    sta T+2
    lda $0003
    sta T+3
    lda $0002
    sta CURSEQ
    lda $0003
    sta CURSEQ+1
    lda T
    ora T+1
    ora T+2
    ora T+3
    bne ss_used
    lda FREE_S
    cmp #$ff
    bne ss_next
    lda SS
    sta FREE_S
    lda SE
    sta FREE_E
    bra ss_next
ss_used:
    lda MAXSEQ          ; MAXSEQ = max(MAXSEQ, CURSEQ)
    cmp CURSEQ
    lda MAXSEQ+1
    sbc CURSEQ+1
    bcs ss_nomax
    lda CURSEQ
    sta MAXSEQ
    lda CURSEQ+1
    sta MAXSEQ+1
ss_nomax:
    lda CURSEQ          ; MIN = oldest used entry
    cmp MINSEQ
    lda CURSEQ+1
    sbc MINSEQ+1
    bcs ss_nomin
    lda CURSEQ
    sta MINSEQ
    lda CURSEQ+1
    sta MINSEQ+1
    lda SS
    sta MIN_S
    lda SE
    sta MIN_E
ss_nomin:
    jsr ent_match
    bcs ss_next
    lda SS
    sta FND_S
    lda SE
    sta FND_E
ss_next:
    inc SE
    lda SE
    cmp #$07
    jne ss_ent
    inc SS
    lda SS
    cmp SCNT
    jne ss_sec
    clc
    rts

ent_match:              ; T = dir cluster, VRAM read pointer at the file cluster. C=0 if same file
    ldx #$03
em_cl:
    lda T,x
    cmp CURDIR,x
    bne em_no
    dex
    bpl em_cl
    lda $0002
    cmp FILECL
    bne em_no
    lda $0003
    cmp FILECL+1
    bne em_no
    lda $0002
    cmp FILECL+2
    bne em_no
    lda $0003
    cmp FILECL+3
    bne em_no
em_yes:
    clc
    rts
em_no:
    sec
    rts

slot_put:               ; A = sector index, X = entry, Y = 1 write this file / 0 clear. C=1 on error
    sta SS
    stx SE
    phy
    jsr slot_read       ; re-read + verify right before writing
    ply
    jcs sp_ret
    phy
    jsr ent_addr
    jsr vram_w
    ply
    beq sp_clear
    ldx #$00
sp_cl:
    lda CURDIR,x
    sta $0002
    lda CURDIR+1,x
    sta $0003
    inx
    inx
    cpx #$04
    bne sp_cl
    clc                 ; seq = MAXSEQ + 1
    lda MAXSEQ
    adc #$01
    sta $0002
    lda MAXSEQ+1
    adc #$00
    sta $0003
    lda FILECL
    sta $0002
    lda FILECL+1
    sta $0003
    lda FILECL+2
    sta $0002
    lda FILECL+3
    sta $0003
    ldx #$00            ; name: 54 bytes, NUL padded
    stz TMP
sp_nm:
    jsr sp_byte
    sta $0002
    inx
    jsr sp_byte
    sta $0003
    inx
    cpx #54
    bne sp_nm
    jmp write_scr
sp_byte:                ; X = index -> A = name byte, 0 after the end
    lda TMP
    bne sb_zero
    cpx #NAMELEN
    bcs sb_end
    lda NAMEBUF,x
    bne sb_ret
sb_end:
    inc TMP
sb_zero:
    cla
sb_ret:
    rts
sp_clear:
    ldx #$20
sp_zl:
    stz $0002
    stz $0003
    dex
    bne sp_zl
    jmp write_scr
sp_ret:
    rts

fav_scan:
    lda #FAV_BASE
    sta SBASE
    lda #FAV_SECTORS
    sta SCNT
    lda #$46            ; "F"
    sta SKIND
    jmp slot_scan

fav_toggle:             ; option "Favoritar" / "Remover favorito"
    lda FLAGS
    and #$02
    bne ft_dat
    lda #lo(s_nodat)
    ldx #hi(s_nodat)
    bra ft_msg
ft_dat:
    jsr fav_scan
    bcs ft_err
    lda FND_S
    cmp #$ff
    beq ft_add
    ldx FND_E
    ldy #$00
    jsr slot_put
    bcs ft_err
    stz AFAV
    lda #lo(s_removed)
    ldx #hi(s_removed)
    bra ft_msg
ft_add:
    lda FREE_S
    cmp #$ff
    beq ft_full
    ldx FREE_E
    ldy #$01
    jsr slot_put
    bcs ft_err
    lda #$01
    sta AFAV
    lda #lo(s_added)
    ldx #hi(s_added)
    bra ft_msg
ft_full:
    lda #lo(s_full)
    ldx #hi(s_full)
    bra ft_msg
ft_err:
    lda #lo(s_err)
    ldx #hi(s_err)
ft_msg:
    sta MSG
    stx MSG+1
    rts

recent_add:             ; remember the game being loaded (skips TOS.PCE)
    lda FLAGS
    and #$02
    beq ra_ret
    lda NAMEBUF
    cmp #$54            ; "TOS"
    bne ra_go
    lda NAMEBUF+1
    cmp #$4f
    bne ra_go
    lda NAMEBUF+2
    cmp #$53
    bne ra_go
    lda NAMEBUF+3
    cmp #$20
    beq ra_ret
    cmp #$2e
    beq ra_ret
ra_go:
    lda #REC_BASE
    sta SBASE
    lda #REC_SECTORS
    sta SCNT
    lda #$52            ; "R"
    sta SKIND
    jsr slot_scan
    bcs ra_ret
    lda FND_S           ; same game again: refresh its entry
    ldx FND_E
    cmp #$ff
    bne ra_put
    lda FREE_S
    ldx FREE_E
    cmp #$ff
    bne ra_put
    lda MIN_S           ; full: replace the oldest
    ldx MIN_E
ra_put:
    ldy #$01
    jsr slot_put
ra_ret:
    rts
"""

HUB = """
; ---------------------------------------------------------------- menu (I at the root), lists, go to a game
LCOUNT = $2058
LCUR = $2059
LTOP = $205a
LKIND = $205b           ; 0 favourites, 1 recents
GSTATE = $205c          ; 0 nothing, 1 find the game in the folder just entered, 2 inject keys
GTGT = $20df           ; seek: target display index
GRUN = $20e0           ; seek: press RUN when there
GCOUNT = $20e1         ; seek: step limit
SELHELD = $20e2
SELUSED = $20e3
LDIR = $20b8           ; letter jump temporaries (inside LINE, unused while jumping)
LN = $20b9
LC = $20ba
LCH = $20bb
LISDIR = $20bc
DCNT = $20bd
RS = $20be
RE = $20bf
BSLO = $20c0
BSHI = $20c1
BSKEY = $20c2
BSMODE = $20c3
BSMID = $20c4
ISDIR = $20c5
LT = $20c6
INJ = $205f
LIST = $2060            ; entry ids (sector * 7 + entry), up to 56
SEQS = $2098            ; recents sort keys (u16 each); shares space with LINE
LINE = $2098            ; 48-byte buffer
GDIR = $20c8
GFILE = $20cc
FILECL = $20d0
DCL = $20d4             ; directory scan: current cluster
ORD = $20d8             ; directory scan: ordinal (u16)
HCUR = $20da
LSEC = $20db
LROW = $20dc
LIDX = $20dd
TBL = $397d             ; OS: display order -> entry ordinal (u8, max 224 entries per folder)
FS_FAT = $30b1          ; OS FAT: LBA of the FAT
PAGE = 16

cpush:                  ; HuC C stack push: X = lo, A = hi
    pha
    lda <$00
    sec
    sbc #$02
    sta <$00
    bcs cpu1
    dec <$01
cpu1:
    pla
    ldy #$01
    sta [$00],y
    txa
    sta [$00]
    rts

os_open:                ; OS open(index): X = lo, A = hi -> name at $3a64, cluster at $3b64
    jsr cpush
    ldx #lo(NAMEBUF)
    lda #hi(NAMEBUF)
    jsr cpush
    ldx #$64
    lda #$3b
    jsr cpush
    ldx #$68
    lda #$3b
    jmp $810e

wait_key:               ; -> A = buttons newly pressed
    ldx #$01
    cla
    ldy #$01
    jsr $f01a
    lda $222d
    beq wait_key
    rts

hub:                    ; -> A = 0 back to the browser, 1 go to GDIR/GFILE
    stz HCUR
hub_redraw:
    jsr $eda9
    sei
    jsr hub_draw
    lda <$f7
    sta $0000
    cli
hub_loop:
    jsr wait_key
    bit #$10
    bne hub_up
    bit #$40
    bne hub_dn
    bit #$0a
    bne hub_ok
    bit #$01
    bne hub_back
    bra hub_loop
hub_up:
    lda HCUR
    bne hub_up1
    lda #$03
hub_up1:
    dec a
    sta HCUR
    bra hub_upd
hub_dn:
    lda HCUR
    inc a
    cmp #$03
    bcc hub_dn1
    cla
hub_dn1:
    sta HCUR
hub_upd:
    sei
    jsr hub_draw
    lda <$f7
    sta $0000
    cli
    bra hub_loop
hub_ok:
    lda HCUR
    cmp #$02
    beq hub_about
    sta LKIND
    jsr list_screen
    cmp #$00
    beq hub_redraw
    ldx #$03            ; go: the OS's "enter folder" code reads the cluster at $3b96
hub_go:
    lda GDIR,x
    sta $3b96,x
    dex
    bpl hub_go
    lda #$02            ; start from the root with an empty path, so I leads back to it
    sta CURDIR
    stz CURDIR+1
    stz CURDIR+2
    stz CURDIR+3
    stz $3d12
    stz $3d13
    lda #$01
    sta GSTATE
    rts
hub_about:
    jsr $8144           ; the OS about screen
    jmp hub_redraw
hub_back:
    jsr $eda9
    cla
    rts

hub_draw:
    lda #30
    sta CNT
    lda #lo(s_menu)
    sta T
    lda #hi(s_menu)
    sta T+1
    ldx #$01
    ldy #$02
    lda #$02
    jsr prt
    stz ADI
hd_opt:
    lda ADI
    asl a
    tax
    lda hub_tab,x
    sta T
    lda hub_tab+1,x
    sta T+1
    ldx ADI
    lda hub_row,x
    tay
    sty LROW
    lda ADI
    cmp HCUR
    beq hd_sel
    lda #$01
    bra hd_put
hd_sel:
    cla
hd_put:
    ldx #$08
    jsr prt
    lda ADI
    cmp HCUR
    bne hd_next
    lda #lo(s_cur)
    sta T
    lda #hi(s_cur)
    sta T+1
    ldx #$08
    ldy LROW
    cla
    jsr prt
hd_next:
    inc ADI
    lda ADI
    cmp #$03
    bne hd_opt
    lda #lo(s_hint_menu)
    sta T
    lda #hi(s_hint_menu)
    sta T+1
    ldx #$01
    ldy #23
    lda #$01
    jmp prt

; ---------------------------------------------------------------- favourites / recents list
list_screen:            ; LKIND -> A = 0 back to the menu, 1 go (GDIR/GFILE set)
    jsr $eda9
    sei
    jsr list_build
    stz LCUR
    jsr list_draw
    lda <$f7
    sta $0000
    cli
ls_loop:
    jsr wait_key
    bit #$10
    bne ls_up
    bit #$40
    bne ls_dn
    bit #$80
    bne ls_pgup
    bit #$20
    bne ls_pgdn
    bit #$0a
    bne ls_ok
    bit #$01
    bne ls_back
    bra ls_loop
ls_up:
    lda LCUR
    beq ls_loop
    dec LCUR
    bra ls_upd
ls_dn:
    lda LCUR
    inc a
    cmp LCOUNT
    bcs ls_loop
    sta LCUR
    bra ls_upd
ls_pgup:
    lda LCUR
    sec
    sbc #PAGE
    bcs ls_pg1
    cla
ls_pg1:
    sta LCUR
    bra ls_upd
ls_pgdn:
    lda LCOUNT
    beq ls_loop
    lda LCUR
    clc
    adc #PAGE
    cmp LCOUNT
    bcc ls_pg2
    lda LCOUNT
    dec a
ls_pg2:
    sta LCUR
ls_upd:
    sei
    jsr list_draw
    lda <$f7
    sta $0000
    cli
    jmp ls_loop
ls_ok:
    lda LCOUNT
    jeq ls_loop
    sei
    jsr list_pick
    lda <$f7
    sta $0000
    cli
    jcs ls_loop
    lda #$01
    rts
ls_back:
    cla
    rts

list_kind:              ; SBASE/SCNT/SKIND for LKIND
    lda LKIND
    bne lk_rec
    lda #FAV_BASE
    sta SBASE
    lda #FAV_SECTORS
    sta SCNT
    lda #$46
    sta SKIND
    rts
lk_rec:
    lda #REC_BASE
    sta SBASE
    lda #REC_SECTORS
    sta SCNT
    lda #$52
    sta SKIND
    rts

list_build:             ; -> LIST/LCOUNT (recents newest first)
    stz LCOUNT
    lda #$ff
    sta LSEC
    lda FLAGS
    and #$02
    bne lb_go
    rts
lb_go:
    jsr list_kind
    stz SS
lb_sec:
    jsr slot_read
    bcc lb_ok
    rts
lb_ok:
    stz SE
lb_ent:
    jsr ent_addr
    jsr vram_r
    lda $0002
    sta T
    lda $0003
    sta T+1
    lda $0002
    sta T+2
    lda $0003
    ora T
    ora T+1
    ora T+2
    beq lb_next
    lda $0002           ; seq
    sta CURSEQ
    lda $0003
    sta CURSEQ+1
    lda SS              ; id = sector * 7 + entry
    asl a
    asl a
    asl a
    sec
    sbc SS
    clc
    adc SE
    ldx LCOUNT
    sta LIST,x
    txa
    asl a
    tax
    lda CURSEQ
    sta SEQS,x
    lda CURSEQ+1
    sta SEQS+1,x
    inc LCOUNT
lb_next:
    inc SE
    lda SE
    cmp #$07
    bne lb_ent
    inc SS
    lda SS
    cmp SCNT
    bne lb_sec
    lda LKIND
    beq lb_done
    jsr sort_recent
lb_done:
    rts

sort_recent:            ; selection sort, newest (highest seq) first
    stz R
sr_i:
    lda R
    inc a
    cmp LCOUNT
    bcs sr_done
    lda R
    sta R2              ; index of the max
    inc a
    sta TMP
sr_j:
    lda TMP
    cmp LCOUNT
    bcs sr_swap
    asl a
    tax
    lda R2
    asl a
    tay
    lda SEQS,y          ; if seq[j] > seq[max]: max = j
    cmp SEQS,x
    lda SEQS+1,y
    sbc SEQS+1,x
    bcs sr_jn
    lda TMP
    sta R2
sr_jn:
    inc TMP
    bra sr_j
sr_swap:
    ldx R
    ldy R2
    lda LIST,x
    pha
    lda LIST,y
    sta LIST,x
    pla
    sta LIST,y
    txa
    asl a
    tax
    tya
    asl a
    tay
    lda SEQS,x
    pha
    lda SEQS,y
    sta SEQS,x
    pla
    sta SEQS,y
    lda SEQS+1,x
    pha
    lda SEQS+1,y
    sta SEQS+1,x
    pla
    sta SEQS+1,y
    inc R
    bra sr_i
sr_done:
    rts

id_load:                ; A = entry id -> SCR holds its sector (cached), SE = entry. C=1 on error
    ldx #$00
il_div:
    cmp #$07
    bcc il_d
    sbc #$07
    inx
    bra il_div
il_d:
    sta SE
    stx SS
    cpx LSEC
    beq il_ok
    jsr list_kind
    jsr slot_read
    bcs il_bad
    lda SS
    sta LSEC
il_ok:
    clc
    rts
il_bad:
    lda #$ff
    sta LSEC
    sec
    rts

list_draw:
    lda #30
    sta CNT
    lda LKIND           ; title
    asl a
    tax
    lda title_tab,x
    sta T
    lda title_tab+1,x
    sta T+1
    ldx #$01
    ldy #$01
    lda #$02
    jsr prt
    lda #lo(s_hint_list)
    sta T
    lda #hi(s_hint_list)
    sta T+1
    ldx #$01
    ldy #23
    lda #$01
    jsr prt
    lda LCOUNT
    bne ld_items
    lda FLAGS
    and #$02
    bne ld_empty
    lda #lo(s_nodat)
    ldx #hi(s_nodat)
    bra ld_msg
ld_empty:
    lda #lo(s_empty)
    ldx #hi(s_empty)
ld_msg:
    sta T
    stx T+1
    ldx #$02
    ldy #$05
    lda #$01
    jmp prt
ld_items:
    lda LCUR            ; first row of the page = LCUR rounded down to PAGE
    and #$f0
    sta LTOP
    stz LROW
ld_row:
    lda LTOP
    clc
    adc LROW
    sta LIDX
    jsr ld_fill         ; LINE = name or blanks
    lda #lo(LINE)
    sta T
    lda #hi(LINE)
    sta T+1
    lda #30
    sta CNT
    lda LROW
    clc
    adc #$03
    tay
    lda LIDX
    cmp LCUR
    beq ld_sel
    lda #$01
    bra ld_put
ld_sel:
    cla
ld_put:
    ldx #$01
    jsr prt
    inc LROW
    lda LROW
    cmp #PAGE
    bne ld_row
    rts

ld_fill:                ; LINE[0] = cursor mark, LINE[1..29] = name of LIST[LIDX], LINE[30] = 0
    ldx #$1d
    lda #$20
lf_clr:
    sta LINE,x
    dex
    bpl lf_clr
    stz LINE+30
    lda LIDX
    cmp LCOUNT
    bcs lf_ret
    cmp LCUR
    bne lf_nomark
    lda #$3e            ; ">"
    sta LINE
lf_nomark:
    ldx LIDX
    lda LIST,x
    jsr id_load
    bcs lf_ret
    jsr ent_addr        ; name starts at entry byte 10 = word 5
    txa
    clc
    adc #$05
    tax
    lda #hi(SCR)
    jsr vram_r
    ldx #$01
lf_cp:
    lda $0002
    beq lf_ret
    sta LINE,x
    inx
    cpx #$1e
    beq lf_ret
    lda $0003
    beq lf_ret
    sta LINE,x
    inx
    cpx #$1e
    bne lf_cp
lf_ret:
    rts

list_pick:              ; LIST[LCUR] -> GDIR, GFILE. C=1 on error
    ldx LCUR
    lda LIST,x
    jsr id_load
    bcs lp_bad
    jsr ent_addr
    jsr vram_r
    lda $0002
    sta GDIR
    lda $0003
    sta GDIR+1
    lda $0002
    sta GDIR+2
    lda $0003
    sta GDIR+3
    lda $0002           ; seq
    lda $0003
    lda $0002
    sta GFILE
    lda $0003
    sta GFILE+1
    lda $0002
    sta GFILE+2
    lda $0003
    sta GFILE+3
    lda GDIR
    ora GDIR+1
    ora GDIR+2
    ora GDIR+3
    beq lp_bad
    clc
    rts
lp_bad:
    sec
    rts

; ---------------------------------------------------------------- go to a game: find it in the folder, then press keys
goto_tick:              ; called every idle frame; sets INJ
    lda GSTATE
    bne gt_on
    rts
gt_on:
    cmp #$01
    jne gt_seek
    stz GSTATE
    ldx #$03            ; did the OS enter the folder?
gt_dir:
    lda CURDIR,x
    cmp GDIR,x
    jne gt_ret
    dex
    bpl gt_dir
    jsr dir_ordinal     ; ORD = ordinal of GFILE among the folder's entries
    jcs gt_ret
    lda ORD+1
    jne gt_ret          ; the OS lists at most 224 entries
    clx
gt_find:
    lda TBL,x
    cmp ORD
    bne gt_nx
    phx                 ; confirm with the OS: open(i) must give the same file
    cla
    jsr os_open
    plx
    lda $3b64
    cmp GFILE
    bne gt_nx
    lda $3b65
    cmp GFILE+1
    bne gt_nx
    lda $3b66
    cmp GFILE+2
    bne gt_nx
    lda $3b67
    cmp GFILE+3
    beq gt_found
gt_nx:
    inx
    cpx #224
    bne gt_find
    rts
gt_found:
    stx GTGT
    lda #$01
    sta GRUN
    jmp seek_start
gt_seek:                ; move the cursor one step towards GTGT (pages first)
    dec GCOUNT
    beq gt_stop
    jsr cur_index
    txa
    jsr div20
    sty TMP             ; current page
    lda GTGT
    jsr div20
    cpy TMP
    beq gt_samepage
    bcs gt_right
    lda #$80            ; LEFT
    sta INJ
    rts
gt_right:
    lda #$20
    sta INJ
    rts
gt_samepage:
    jsr cur_index
    cpx GTGT
    beq gt_there
    bcc gt_down
    lda #$10            ; UP
    sta INJ
    rts
gt_down:
    lda #$40
    sta INJ
    rts
gt_there:
    lda GRUN
    beq gt_stop
    lda #$08            ; RUN: open the game screen
    sta INJ
gt_stop:
    stz GSTATE
gt_ret:
    rts

seek_start:             ; GTGT set: start moving the cursor
    lda #$02
    sta GSTATE
    lda #200
    sta GCOUNT
    rts

div20:                  ; A -> Y = A / 20, A = A % 20
    ldy #$00
dv_l:
    cmp #20
    bcc dv_r
    sbc #20
    iny
    bra dv_l
dv_r:
    rts

cur_index:              ; browser cursor (index local; the joy() call pushed 2 bytes) -> X
    ldy #$10
    lda [$00],y
    tax
    rts

; ---------------------------------------------------------------- SELECT (themes on release, letters with a direction), II on a game
input_tick:
    lda $2228           ; held buttons
    and #$04
    beq it_nosel
    lda #$ff            ; the OS never sees SELECT
    sta INJ
    lda #$01
    sta SELHELD
    lda $222d
    bit #$90            ; LEFT or UP: previous letter
    bne it_prev
    bit #$60            ; RIGHT or DOWN: next letter
    bne it_next
    rts
it_prev:
    sta SELUSED
    cla
    jmp letter_jump
it_next:
    sta SELUSED
    lda #$01
    jmp letter_jump
it_nosel:
    lda SELHELD
    beq it_ii
    stz SELHELD
    lda SELUSED
    stz SELUSED
    bne it_ii
    jsr theme_next      ; SELECT released without a direction
it_ii:
    lda $222d           ; II alone on a game: open the game screen like RUN
    cmp #$02
    bne it_ret
    lda $2228
    cmp #$02
    bne it_ret
    jsr cur_index
    txa
    jsr entry_info
    lda ISDIR
    bne it_ret
    lda #$08
    sta INJ
it_ret:
    rts

entry_info:             ; A = display index -> A = first letter (upper case), ISDIR
    tax
    cla
    jsr os_open
    stz ISDIR
    lda $3b68           ; folders have size 0
    ora $3b69
    ora $3b6a
    ora $3b6b
    bne ei_file
    inc ISDIR
ei_file:
    lda NAMEBUF
    cmp #$61
    bcc ei_ret
    cmp #$7b
    bcs ei_ret
    sbc #$1f            ; carry clear: -$20
ei_ret:
    rts

bsearch:                ; first index in [BSLO, BSHI) where the predicate holds -> A
bs_loop:
    lda BSLO
    cmp BSHI
    bcs bs_done
    clc
    adc BSHI
    ror a
    sta BSMID
    jsr entry_info
    ldx BSMODE
    beq bs_gt
    dex
    beq bs_ge
    lda ISDIR           ; mode 2: is a file
    beq bs_true
    bra bs_false
bs_gt:
    cmp BSKEY
    beq bs_false
    bcs bs_true
    bra bs_false
bs_ge:
    cmp BSKEY
    bcs bs_true
bs_false:
    lda BSMID
    inc a
    sta BSLO
    bra bs_loop
bs_true:
    lda BSMID
    sta BSHI
    bra bs_loop
bs_done:
    lda BSLO
    rts

letter_jump:            ; A = 1 next letter, 0 previous letter (the list is sorted, case-insensitive)
    sta LDIR
    lda $3a62           ; number of entries (the OS shows at most 224)
    ldx $3a63
    beq lj_n
    lda #224
lj_n:
    sta LN
    cmp #$00
    bne lj_go
    rts
lj_go:
    jsr cur_index
    stx LC
    txa
    jsr entry_info
    sta LCH
    lda ISDIR
    sta LISDIR
    stz BSLO            ; folders come first: D = first file
    lda LN
    sta BSHI
    lda #$02
    sta BSMODE
    jsr bsearch
    sta DCNT
    lda LISDIR          ; search inside the current group (folders or files)
    beq lj_files
    stz RS
    lda DCNT
    sta RE
    bra lj_dir
lj_files:
    lda DCNT
    sta RS
    lda LN
    sta RE
lj_dir:
    lda LDIR
    beq lj_prev
    lda LC              ; next: first entry after LC whose letter is greater
    inc a
    sta BSLO
    lda RE
    sta BSHI
    lda LCH
    sta BSKEY
    stz BSMODE
    jsr bsearch
    cmp RE
    bcc lj_set
    lda RS              ; past the end: wrap to the first entry
    bra lj_set
lj_prev:
    lda RS              ; g = first entry of the current letter
    sta BSLO
    lda LC
    sta BSHI
    lda LCH
    sta BSKEY
    lda #$01
    sta BSMODE
    jsr bsearch
    cmp LC
    bcc lj_set          ; not at the start of the letter yet: go there
    cmp RS
    bne lj_before
    lda RE              ; already at the first letter: wrap to the last letter
    dec a
    bra lj_key
lj_before:
    dec a               ; letter of the entry just before this group
lj_key:
    sta LT
    jsr entry_info
    sta BSKEY
    lda RS
    sta BSLO
    lda LT
    inc a
    sta BSHI
    lda #$01
    sta BSMODE
    jsr bsearch
lj_set:
    sta GTGT
    stz GRUN
    jmp seek_start

dir_ordinal:            ; scan CURDIR for GFILE, counting entries the way the OS numbers them
    stz ORD
    stz ORD+1
    ldx #$03
do_c0:
    lda CURDIR,x
    sta DCL,x
    dex
    bpl do_c0
    lda #64             ; at most 64 clusters
    sta CNT2
do_clus:
    ldx #$03
do_c1:
    lda DCL,x
    sta T,x
    dex
    bpl do_c1
    jsr clus2lba        ; LBA = first sector, TMP = sectors per cluster
    lda FS_BPC+1
    sta R
    lda FS_BPC+2
    lsr a
    ror R
do_sec:
    jsr read_scr
    jcs do_fail
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    lda #$10
    sta R2
do_ent:
    ldx #$00            ; entry -> LINE[0..31]
do_rd:
    lda $0002
    sta LINE,x
    inx
    lda $0003
    sta LINE,x
    inx
    cpx #$20
    bne do_rd
    lda LINE
    jeq do_fail         ; end of directory
    cmp #$e5            ; deleted
    beq do_next
    cmp #$2e            ; . and ..
    beq do_next
    lda LINE+11
    cmp #$0f            ; long-name part
    beq do_next
    and #$08            ; volume label
    bne do_next
    lda LINE+26
    cmp GFILE
    bne do_cnt
    lda LINE+27
    cmp GFILE+1
    bne do_cnt
    lda LINE+20
    cmp GFILE+2
    bne do_cnt
    lda LINE+21
    cmp GFILE+3
    bne do_cnt
    clc
    rts
do_cnt:
    inc ORD
    bne do_next
    inc ORD+1
do_next:
    dec R2
    bne do_ent
    jsr lba_inc
    dec R
    bne do_sec
    jsr fat_next        ; next cluster of the directory
    jcs do_fail
    dec CNT2
    jne do_clus
do_fail:
    sec
    rts

fat_next:               ; DCL = FAT[DCL]. C=1 at the end of the chain
    lda DCL             ; LBA = FS_FAT + DCL / 128
    asl a
    lda DCL+1
    rol a
    sta T
    lda DCL+2
    rol a
    sta T+1
    lda DCL+3
    rol a
    sta T+2
    clc
    lda T
    adc FS_FAT
    sta LBA
    lda T+1
    adc FS_FAT+1
    sta LBA+1
    lda T+2
    adc FS_FAT+2
    sta LBA+2
    lda #$00
    adc FS_FAT+3
    sta LBA+3
    jsr read_scr
    bcs fn_end
    lda DCL             ; word offset = (DCL & 127) * 2
    and #$7f
    asl a
    tax
    lda #hi(SCR)
    jsr vram_r
    lda $0002
    sta DCL
    lda $0003
    sta DCL+1
    lda $0002
    sta DCL+2
    lda $0003
    and #$0f
    sta DCL+3
    cmp #$0f            ; end-of-chain markers (and anything absurd)
    beq fn_end
    lda DCL+3
    ora DCL+2
    ora DCL+1
    bne fn_ok
    lda DCL
    cmp #$02
    bcc fn_end
fn_ok:
    clc
    rts
fn_end:
    sec
    rts
"""

THEMES_DAT = """
; ---------------------------------------------------------------- themes and banners from RGPOA.DAT
TCOUNT = $20e4          ; themes in RGPOA.DAT (0 = built-in)
TTAB = $20e5            ; theme table sector (relative, 4 bytes)
BANCUST = $20e9         ; 1 = the active theme has its own banner (tiles $140+, palette 6)

theme_count:            ; -> A = number of themes
    lda TCOUNT
    bne tcn_r
    lda #NTHEMES
tcn_r:
    rts

theme_dat:              ; X = theme: 9 colours from the table, then the optional banner
    txa                 ; sector = TTAB + X / 16
    lsr a
    lsr a
    lsr a
    lsr a
    clc
    adc TTAB
    sta T
    lda TTAB+1
    adc #$00
    sta T+1
    lda TTAB+2
    adc #$00
    sta T+2
    lda TTAB+3
    adc #$00
    sta T+3
    phx
    jsr lba_from_dat
    jsr read_scr
    plx
    jcs td_ret
    txa                 ; entry = (X % 16) * 16 words
    and #$0f
    asl a
    asl a
    asl a
    asl a
    tax
    lda #hi(SCR)
    jsr vram_r
    cly
td_col:
    lda slots,y
    sta VCE_A
    stz VCE_AH
    lda $0002
    sta VCE_D
    lda $0003
    sta VCE_DH
    iny
    cpy #NSLOTS
    bne td_col
    lda $0002           ; banner sector
    sta T
    lda $0003
    sta T+1
    lda $0002
    sta T+2
    lda $0003
    sta T+3
    stz BANCUST
    ora T
    ora T+1
    ora T+2
    beq td_rows
    jsr lba_from_dat    ; palette sector -> CRAM $60 (palette 6)
    jsr read_scr
    bcs td_rows
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    lda #$60
    sta VCE_A
    stz VCE_AH
    ldx #$10
td_pal:
    lda $0002
    sta VCE_D
    lda $0003
    sta VCE_DH
    dex
    bne td_pal
    jsr lba_inc         ; 64 tiles -> VRAM $1400
    ldx #$00
    lda #$14
    jsr vram_w
    ldx #$04
    jsr read_blocks
    bcs td_rows
    inc BANCUST
td_rows:
    jmp banner_rows
td_ret:
    rts

banner_rows:            ; BAT rows 30-31 (the top of the screen): custom or default banner
    st0 #$00
    st1 #$80
    st2 #$07
    st0 #$02
    lda BANCUST
    beq br_def
    clx
br_r1:
    txa
    clc
    adc #$40
    sta $0002
    lda #$61            ; palette 6, tile $140 + i
    sta $0003
    inx
    cpx #32
    bne br_r1
    st0 #$00
    st1 #$c0
    st2 #$07
    st0 #$02
br_r2:
    txa
    clc
    adc #$40
    sta $0002
    lda #$61
    sta $0003
    inx
    cpx #64
    bne br_r2
    rts
br_def:
    tma #$08
    pha
    lda #$0f
    tam #$08
    tia B15_BANMAP,$0002,64
    st0 #$00
    st1 #$c0
    st2 #$07
    st0 #$02
    tia B15_BANMAP+64,$0002,64
    pla
    tam #$08
    rts
"""

BANK13 = THEME + GFX + SDART + ACTION + HUB + THEMES_DAT
# RGPOA.DAT v2 layout (sectors relative to the file start)
FAV_BASE, FAV_SECTORS = 1, 8
REC_BASE, REC_SECTORS = 9, 2
INDEX_BASE = 11
CONSTS = {'ROOT_SECTORS': 16, 'ART_DELAY': 12, 'ART_SPR_SECTORS': 12,
          'FAV_BASE': FAV_BASE, 'FAV_SECTORS': FAV_SECTORS, 'REC_BASE': REC_BASE,
          'REC_SECTORS': REC_SECTORS, 'INDEX_BASE': INDEX_BASE, 'WRITABLE': INDEX_BASE, 'NAMELEN': 52}
