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
    cpx #NTHEMES
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
    lda #$40
    sta VCE_A
    stz VCE_AH
    tia ban_pal,VCE_D,32
    st0 #$00
    st1 #$00
    st2 #$10
    st0 #$02
    tia ban_tiles,$0002,BAN_TILES_LEN
    st0 #$00
    st1 #$80
    st2 #$07
    st0 #$02
    tia ban_map,$0002,64
    st0 #$00
    st1 #$c0
    st2 #$07
    st0 #$02
    tia ban_map+64,$0002,64
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
    st0 #$00
    st1 #$00
    st2 #$00
    st0 #$02
    tia help_map,$0002,64
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
    lda FLAGS
    and #$02
    beq id_out
    jsr art_tick
id_out:
    lda <$f7
    sta $0000
    plp
    rts

splash:                 ; boot splash: palette 5, tiles (bank 14) at VRAM $2000, BAT (bank 15)
    php
    sei
    lda #$50
    sta VCE_A
    stz VCE_AH
    tia spl_pal,VCE_D,32
    st0 #$00
    st1 #$00
    st2 #$20
    st0 #$02
    tma #$08
    pha
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
    jsr theme_cur       ; saves the stock bar colour on first use
    ldx R2
    cpx #NTHEMES
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

; ---------------------------------------------------------------- theme save (sector 0 only)
dat_save_theme:         ; X = theme
    lda FLAGS
    and #$02
    bne ds_ok1
    rts
ds_ok1:
    stx R2
    sec                 ; never below the FAT data area
    lda DAT
    sbc FS_DATA
    lda DAT+1
    sbc FS_DATA+1
    lda DAT+2
    sbc FS_DATA+2
    lda DAT+3
    sbc FS_DATA+3
    bcs ds_ok2
    rts
ds_ok2:
    jsr check_header    ; re-read and verify right before writing
    bcc ds_ok3
    rts
ds_ok3:
    jsr stop_stream
    jsr set_arg_lba     ; LBA = DAT (set by check_header)
    lda #$58            ; CMD24 write block
    jsr sd_cmd
    cmp #$00
    bne ds_reopen
    jsr cs_low
    lda #$ff
    jsr spi
    lda #$fe
    jsr spi
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    cly
ds_loop:
    lda $0002
    cpy #$08
    bne ds_lo
    lda R2              ; byte 16 = theme
ds_lo:
    jsr spi
    lda $0003
    jsr spi
    iny
    bne ds_loop
    lda #$ff            ; CRC (ignored in SPI mode)
    jsr spi
    lda #$ff
    jsr spi
    lda #$ff            ; data response
    jsr spi
    ldy #$00
    ldx #$00
ds_busy:
    lda #$ff
    jsr spi
    cmp #$00
    bne ds_done
    dey
    bne ds_busy
    dex
    bne ds_busy
ds_done:
    jsr cs_high
ds_reopen:
    jsr check_header    ; leaves a read stream open, like the OS expects
ds_ret:
    rts

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
    inc a
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


def tables(art_x=152, art_y=40):
    """Data that goes after the code: SAT entries for the 96x128 panel, names, magic."""
    words = []
    for s in range(6):
        sr, sc = divmod(s, 3)
        words += [art_y + sr * 64 + 64, art_x + sc * 32 + 32, (0x4000 + s * 0x200) >> 5, 0x3180]
    t = '\nsat_on: .dw ' + ','.join(str(w) for w in words)
    t += '\nsat_off: .dw ' + ','.join('0' for _ in words)
    t += '\nname83: .db "RGPOA   DAT"'
    t += '\ndat_magic: .db "RGPOA-DAT-v1",0,0,0,0'
    return t


BANK13 = THEME + GFX + SDART
CONSTS = {'ROOT_SECTORS': 16, 'ART_DELAY': 12, 'ART_SPR_SECTORS': 12}
