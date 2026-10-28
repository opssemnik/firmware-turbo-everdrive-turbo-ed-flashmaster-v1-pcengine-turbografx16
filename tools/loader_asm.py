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
SETUP = r'''
; ---------------------------------------------------------------- loading progress bar
BAR_ROW = 18
BAR_TILE = $1c0         ; empty, $1c1 full (VRAM $1c00)

prog_setup:             ; X = number of 8 KB banks to copy
    tii ld_routine,$2b8e,$0100
    txa                 ; banks per block = ceil(banks / 26)
    clc
    adc #25
    ldy #$00
ps_div:
    cmp #26
    bcc ps_d
    sbc #26
    iny
    bra ps_div
ps_d:
    tya
    bne ps_s1
    iny
ps_s1:
    sty LD_STEP_RAM     ; patch the routine's "lda #step"
    sty PCNT
    stx R               ; blocks = ceil(banks / step)
    stz R2
    txa
ps_blk:
    inc R2
    sec
    sbc LD_STEP_RAM
    beq ps_b2
    bcs ps_blk
ps_b2:
    st0 #$00            ; tiles: VRAM $1c00
    st1 #$00
    st2 #$1c
    st0 #$02
    tia bar_tiles,$0002,64
    lda #32             ; first column = (32 - blocks) / 2
    sec
    sbc R2
    lsr a
    sta R
    clc                 ; MAWR = BAR_ROW * 64 + column
    adc #lo(BAR_ROW * 64)
    sta TMP
    lda #hi(BAR_ROW * 64)
    adc #$00
    sta CNT
    st0 #$00
    lda TMP
    sta $0002
    lda CNT
    sta $0003
    st0 #$02
    ldx R2              ; empty frame
ps_e:
    st1 #lo($4000 + BAR_TILE)
    st2 #hi($4000 + BAR_TILE)
    dex
    bne ps_e
    st0 #$00            ; back to the start of the bar; the routine fills it
    lda TMP
    sta $0002
    lda CNT
    sta $0003
    lda #$02
    sta <$f7
    st0 #$02
    rts
'''


def tiles():
    """Two 8x8 tiles in palette 4 colours: 13 grey frame, 14 dark inside / 10 green fill."""
    from art import tile_bytes
    empty = [[13] * 8] + [[13] + [14] * 6 + [13] for _ in range(6)] + [[13] * 8]
    full = [[13] * 8] + [[13, 12] + [10] * 5 + [13]] + [[13] + [10] * 6 + [13] for _ in range(5)] + [[13] * 8]
    return tile_bytes(empty) + tile_bytes(full)
