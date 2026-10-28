"""Extra code in bank 12 (always mapped at $8000 by the OS; free from $8200).

game_nav: on the game screen, LEFT/RIGHT move to the previous/next game in the folder.
The browser's own variables (index, row, page start) are updated so "Carregar" loads the
new game and "Voltar" leaves the cursor on it.
"""

ORG = 0x8200

SRC = r'''
NIDX = $2057            ; target index (free while the game screen is up)
NKEY = $2046

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
'''
