"""Progress bar for "Carregando...".

The OS copies the game from the SD card to flash with a routine it first copies to RAM
($2b8e, 256 bytes: an id byte then code), because flash can't be read while it is
being programmed. This is that routine (stock $fd66-$fe60, rebuilt with labels) with
a few redundant instructions removed and, after each 8 KB bank, a bar block written
straight to the VDC (st1/st2: the VDC address and register were set up beforehand).
"""

RAM_ORG = 0x2b8e
PCNT = 0x20ea           # banks left until the next block

ROUTINE = r'''
    .db $01             ; routine id (the OS checks $2b8e before re-copying)
ld_start:               ; fd54(count = X:A, bank = stack): copy count banks from SD to flash
    pha
    sec
    lda <$00
    sbc #$02
    sta <$00
    lda <$01
    sbc #$00
    sta <$01
    pla
    sax
    sta [$00]
    sax
    ldy #$01
    sta [$00],y
    lda $2020
    sta $2c8e
    lda $2021
    sta $2c8f
    tma #$08
    sta $2c90
    ldy #$02
    lda [$00],y
    tam #$08
    lda #$aa
    sta $6aaa
    lda #$55
    sta $6555
    lda #$20
    sta $6aaa
    ldy #$00
    lda [$00],y
    tax
    lda $e008
    ora #$04
    sta $e008
    lda $e000
ld_bank:
    ldy #$00
    lda #$00
    sta $2020
    lda #$60
    sta $2021
ld_tok:
    lda $e000
    cmp #$fe
    bne ld_tok
ld_4:
    lda #$56
    sta $6aaa
    lda $e000
    sta [$20]
    inc <$20
    lda $e000
    sta [$20]
    inc <$20
    lda $e000
    sta [$20]
    inc <$20
    lda $e000
    sta [$20]
    inc <$20
    iny
    iny
    iny
    iny
ld_wait:
    lda $e004
    and #$02
    beq ld_wait
    cpy #$00
    bne ld_4
    inc $2021
    lda $2021
    and #$1f
    beq ld_done
    and #$01
    bne ld_4
    lda $e000
    lda $e000
    bra ld_tok
ld_done:                ; one 8 KB bank written
    dec PCNT
    bne ld_nobar
    st1 #lo(BAR_FULL)
    st2 #hi(BAR_FULL)
ld_step:
    lda #$01            ; patched: banks per block
    sta PCNT
ld_nobar:
    tma #$08
    inc a
    tam #$08
    dex
    beq ld_end
    lda $e000
    lda $e000
    bra ld_bank
ld_end:
    lda #$01
    tam #$08
    lda #$90
    sta $6000
    lda #$00
    sta $6000
    lda $e000
    lda $e008
    and #$03
    sta $e008
    lda $2c8e
    sta $2020
    lda $2c8f
    sta $2021
    lda $2c90
    tam #$08
    pha
    clc
    lda <$00
    adc #$04
    sta <$00
    lda <$01
    adc #$00
    sta <$01
    pla
    rts
'''

# bank 13: set up the bar, then run the routine above from RAM
ERASE = r'''
    .db $04             ; routine id
er_start:               ; fb0d(count = X:A, bank = stack): erase count banks of flash
    pha
    sec
    lda <$00
    sbc #$02
    sta <$00
    lda <$01
    sbc #$00
    sta <$01
    pla
    sax
    sta [$00]
    sax
    ldy #$01
    sta [$00],y
    ldy #$02
    lda [$00],y
    tax
    cla
    tma #$08
    pha
    txa
    tam #$08
    lda #$aa
    sta $6aaa
    lda #$55
    sta $6555
    lda #$80
    sta $6aaa
    lda #$aa
    sta $6aaa
    lda #$55
    sta $6555
    ldy #$00
    lda [$00],y
    tax
    cla
er_cmd:
    lda #$30
    sta $6000
    tma #$08
    clc
    adc #$01
    tam #$08
    dex
    bne er_cmd
er_wait:                ; the chip erases everything queued; one block moves every 65536 polls
    lda $e004
    and #$02
    bne er_done
    inc ECNT
    bne er_wait
    inc ECNT+1
    bne er_wait
    lda EBASE           ; clear the block at EPOS
    clc
    adc EPOS
    st0 #$00
    sta $0002
    lda EBASE+1
    adc #$00
    sta $0003
    st0 #$02
    st1 #lo(BAR_EMPTY)
    st2 #hi(BAR_EMPTY)
    lda EPOS            ; next position, wrapping
    inc a
    cmp EBLK
    bcc er_p
    cla
er_p:
    sta EPOS
    clc
    adc EBASE
    st0 #$00
    sta $0002
    lda EBASE+1
    adc #$00
    sta $0003
    st0 #$02
    st1 #lo(BAR_FULL)
    st2 #hi(BAR_FULL)
    bra er_wait
er_done:
    pla
    tam #$08
    pha
    clc
    lda <$00
    adc #$04
    sta <$00
    lda <$01
    adc #$00
    sta <$01
    pla
    rts
'''

ERASE_VARS = {'ECNT': 0x2040, 'EPOS': 0x2042, 'EBASE': 0x2043, 'EBLK': 0x2045}

# bank 13: set up the bar, then run the routines above from RAM
SETUP = r'''
; ---------------------------------------------------------------- loading progress bar
BAR_ROW = 18
BAR_TILE = $1c0         ; empty, $1c1 full (VRAM $1c00)
ECNT = $2040            ; erase animation (the game screen variables are free by now)
EPOS = $2042
EBASE = $2043
EBLK = $2045
ESTEP = $2046

prog_setup:             ; copy phase. X = number of 8 KB banks to copy
    tii ld_routine,$2b8e,$0100
    jsr bar_frame
    sty LD_STEP_RAM     ; patch the routine's "lda #step"
    sty PCNT
    rts

prog_erase:             ; erase phase: a block walks along the empty bar while the chip works
    tii er_routine,$2b8e,$0100
    jsr bar_frame
    lda TMP
    sta EBASE
    lda CNT
    sta EBASE+1
    lda R2
    sta EBLK
    stz EPOS
    stz ECNT
    stz ECNT+1
    st1 #lo($7000 + BAR_TILE + 1)
    st2 #hi($7000 + BAR_TILE + 1)
    rts

bar_frame:              ; X = banks -> Y = banks per block, R2 = blocks, TMP/CNT = first block's
    txa                 ; VRAM address; draws the empty bar; VDC left on it with register 2
    clc                 ; banks per block = ceil(banks / 26)
    adc #25
    ldy #$00
bf_div:
    cmp #26
    bcc bf_d
    sbc #26
    iny
    bra bf_div
bf_d:
    tya
    bne bf_s1
    iny
bf_s1:
    sty ESTEP
    stz R2              ; blocks = ceil(banks / step)
    txa
bf_blk:
    inc R2
    sec
    sbc ESTEP
    beq bf_b2
    bcs bf_blk
bf_b2:
    st0 #$00            ; tiles: VRAM $1c00
    st1 #$00
    st2 #$1c
    st0 #$02
    tia bar_tiles,$0002,64
    lda #32             ; first column = (32 - blocks) / 2
    sec
    sbc R2
    lsr a
    clc                 ; address = BAR_ROW * 64 + column
    adc #lo(BAR_ROW * 64)
    sta TMP
    lda #hi(BAR_ROW * 64)
    adc #$00
    sta CNT
    jsr bf_addr
    ldx R2              ; empty frame
bf_e:
    st1 #lo($7000 + BAR_TILE)
    st2 #hi($7000 + BAR_TILE)
    dex
    bne bf_e
    ldy #$03            ; palette 7 = the theme's bar bg, screen bg, folder and cursor colours
bf_pc:
    lda bar_src,y
    sta VCE_A
    stz VCE_AH
    ldx VCE_D
    lda VCE_DH
    pha
    tya
    clc
    adc #$71
    sta VCE_A
    stz VCE_AH
    stx VCE_D
    pla
    sta VCE_DH
    dey
    bpl bf_pc
    lda #$02
    sta <$f7
    jsr bf_addr         ; back to the start of the bar
    ldy ESTEP
    rts
bf_addr:
    st0 #$00
    lda TMP
    sta $0002
    lda CNT
    sta $0003
    st0 #$02
    rts
'''


def tiles():
    """Two 8x8 tiles in palette 7 (theme colours): 1 frame, 2 inside, 3 fill, 4 highlight."""
    from art import tile_bytes
    empty = [[1] * 8] + [[1] + [2] * 6 + [1] for _ in range(6)] + [[1] * 8]
    full = [[1] * 8] + [[1, 4] + [3] * 5 + [1]] + [[1] + [3] * 6 + [1] for _ in range(5)] + [[1] * 8]
    return tile_bytes(empty) + tile_bytes(full)
