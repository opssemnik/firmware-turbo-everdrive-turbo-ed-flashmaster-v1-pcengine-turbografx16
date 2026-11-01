"""Extra code in bank 12 (mapped at $8000 by the OS; free from $8200 to $8fff).

Entry points (fixed, a jump table at ORG): see ENTRY.

game_nav: on the game screen, LEFT/RIGHT move to the previous/next game in the folder.
The browser's own variables (index, row, page start) are updated so "Carregar" loads the
new game and "Voltar" leaves the cursor on it.

music: a PSG player run from the HuC user vsync hook ($2208, enabled by bit 4 of zp $f5 --
that bit is also the "music on" state). The hook enters through mus_irq in bank 0, which
checks that bank 12 is mapped (the OS remaps MPR4 for a moment in some bank 1 routines).
The player's RAM ($2c60+) is inside the flash routines' RAM area: those stop the music first.
"""

ORG = 0x8200
END = 0x9000            # the default splash's last tiles start here
ENTRY = {'GAME_NAV': ORG, 'MUSIC_TICK': ORG + 3, 'MUSIC_START': ORG + 6, 'MUSIC_STOP': ORG + 9}

SRC = r'''
NIDX = $2057            ; target index (free while the game screen is up)
NKEY = $2046

    jmp game_nav
    jmp music_tick
    jmp music_start
    jmp music_stop

game_nav:               ; A = $80 LEFT / $20 RIGHT -> C=0 if another game was opened
    sta NKEY
    ldy #$0e            ; browser local: index of the selected entry
    lda [$00],y
    tax
    lda $3a63           ; entries in the folder (the OS shows at most 224)
    bne gn_max
    lda $3a62
    cmp #224
    bcc gn_cnt
gn_max:
    lda #224
gn_cnt:
    sta TMP
    lda NKEY
    and #$20
    beq gn_left
    inx
    cpx TMP
    bcs gn_no
    bra gn_try
gn_left:
    txa
    beq gn_no
    dex
gn_try:
    stx NIDX
    cla
    jsr os_open
    lda $3b68           ; folders have size 0: games never sit between folders, so stop there
    ora $3b69
    ora $3b6a
    ora $3b6b
    bne gn_file
    ldy #$0e            ; put the OS's "current file" back
    lda [$00],y
    tax
    cla
    jsr os_open
gn_no:
    sec
    rts
gn_file:
    lda NIDX            ; browser locals: index, row, page start
    ldy #$0e
    sta [$00],y
    iny
    cla
    sta [$00],y
    lda NIDX
    jsr div20
    ldy #$09
    sta [$00],y
    sta TMP
    lda NIDX
    sec
    sbc TMP
    ldy #$0b
    sta [$00],y
    ldx #$03
gn_fc:
    lda $3b64,x
    sta FILECL,x
    dex
    bpl gn_fc
    stz AART
    stz AFAV
    stz MSG+1
    lda FLAGS
    and #$02
    beq gn_ok
    sei
    jsr name_hash       ; cover and favourite state for the new game
    ldx #$03
gn_h:
    lda H,x
    sta SEL,x
    dex
    bpl gn_h
    jsr art_load
    bcs gn_noart
    inc AART
gn_noart:
    jsr fav_scan
    bcs gn_nofav
    lda FND_S
    cmp #$ff
    beq gn_nofav
    inc AFAV
gn_nofav:
    lda <$f7
    sta $0000
    cli
gn_ok:
    clc
    rts

name_hash:              ; H = hash of NAMEBUF, same rules as the bottom-bar hash and artpack.py
    stz H
    stz H+1
    stz H+2
    stz H+3
    clx
nh_l:
    lda NAMEBUF,x
    beq nh_done
    cpx #60
    bcs nh_done
    cmp #$21
    bcc nh_n
    cmp #$7f
    bcs nh_n
    cmp #$2e
    beq nh_n
    cmp #$61
    bcc nh_a
    cmp #$7b
    bcs nh_a
    sbc #$1f            ; carry clear: -$20
nh_a:
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
nh_n:
    inx
    bra nh_l
nh_done:
    rts

; ---------------------------------------------------------------- music
MUS = $2c60
M_PTR = MUS             ; 4 channels x 2: next event
M_TIM = MUS + 8         ; frames left of the current event
M_VOL = MUS + 12        ; current volume (0-31)
M_EC = MUS + 16         ; envelope frame counter
M_TMP = MUS + 20
PSG_SEL = $0800
PSG_MAIN = $0801
PSG_FLO = $0802
PSG_FHI = $0803
PSG_CTL = $0804
PSG_BAL = $0805
PSG_WAVE = $0806
PSG_NOISE = $0807

music_start:            ; waves, song from the start, vsync hook on
    php
    sei
    jsr music_stop
    lda #$ff
    sta PSG_MAIN
    clx
ms_wave:
    stx PSG_SEL
    lda #$ff
    sta PSG_BAL
    lda #$40            ; DDA on then off: wave write index back to 0
    sta PSG_CTL
    stz PSG_CTL
    lda wave_off,x
    tay
    lda #32
    sta M_TMP
ms_wl:
    lda waves,y
    sta PSG_WAVE
    iny
    dec M_TMP
    bne ms_wl
    inx
    cpx #$03
    bne ms_wave
    lda #$04            ; drums: noise channel
    sta PSG_SEL
    lda #$ff
    sta PSG_BAL
    ldx #$03
ms_ch:
    txa
    asl a
    tay
    lda song_lo,x
    sta M_PTR,y
    lda song_hi,x
    sta M_PTR+1,y
    lda #$01
    sta M_TIM,x
    stz M_VOL,x
    stz M_EC,x
    dex
    bpl ms_ch
    lda #lo(MUS_IRQ)
    sta $2208
    lda #hi(MUS_IRQ)
    sta $2209
    smb4 <$f5
    plp
    rts

music_stop:             ; hook off, all channels silent
    rmb4 <$f5
    ldx #$05
mst_ch:
    stx PSG_SEL
    stz PSG_CTL
    dex
    bpl mst_ch
    stz PSG_NOISE
    rts

music_tick:             ; once per frame, from the vsync interrupt
    lda <$3e            ; borrow a zero-page pointer
    pha
    lda <$3f
    pha
    clx
mt_ch:
    lda psg_ch,x
    sta PSG_SEL
    dec M_TIM,x
    jne mt_env
    txa
    asl a
    tay
    lda M_PTR,y
    sta <$3e
    lda M_PTR+1,y
    sta <$3f
mt_get:
    lda [$3e]
    cmp #$ff
    bne mt_ev
    lda song_lo,x       ; end: back to the start of this channel
    sta <$3e
    lda song_hi,x
    sta <$3f
    bra mt_get
mt_ev:
    pha                 ; note
    phy
    ldy #$01
    lda [$3e],y         ; frames
    ply
    sta M_TIM,x
    lda <$3e
    clc
    adc #$02
    sta M_PTR,y
    lda <$3f
    adc #$00
    sta M_PTR+1,y
    pla
    beq mt_rest
    cpx #$03
    beq mt_drum
    asl a
    tay
    lda periods-2,y
    sta PSG_FLO
    lda periods-1,y
    sta PSG_FHI
    lda vol_start,x
    bra mt_set
mt_drum:
    tay
    lda drum_nz-1,y
    sta PSG_NOISE
    lda drum_vol-1,y
    bra mt_set
mt_rest:
    cla
mt_set:
    sta M_VOL,x
    stz M_EC,x
    bra mt_out
mt_env:                 ; every env_rate frames the volume drops by env_step, down to env_floor
    lda M_VOL,x
    beq mt_out
    inc M_EC,x
    lda M_EC,x
    cmp env_rate,x
    bcc mt_out
    stz M_EC,x
    lda M_VOL,x
    sec
    sbc env_step,x
    bcs mt_fl
    cla
mt_fl:
    cmp env_floor,x
    bcs mt_v
    lda env_floor,x
mt_v:
    sta M_VOL,x
mt_out:
    lda M_VOL,x
    ora #$80
    sta PSG_CTL
    inx
    cpx #$04
    jne mt_ch
    pla
    sta <$3f
    pla
    sta <$3e
    rts
'''
