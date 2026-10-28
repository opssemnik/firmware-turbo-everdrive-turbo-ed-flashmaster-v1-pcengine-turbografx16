"""Global search (menu > Buscar). Runs from bank 15 mapped at $6000 (MPR3); entry at $7800.

Keyboard on screen -> breadth-first walk of every folder on the card (queue in VRAM $6000),
long names rebuilt from the LFN entries (low byte of each UTF-16 unit, like the OS),
case-insensitive substring match on .PCE/.SGX files, up to 64 results in VRAM $6800.
Read-only: nothing is written to the card. Picking a result reuses the "go to game" path.
"""

ORG = 0x7800

SRC = r'''
QUERY = $2040           ; 16 chars + 0 (upper case)
QLEN = $2051
KCUR = $2052            ; keyboard cursor 0..42
RCOUNT = $2053
RCUR = $2054
SMORE = $2055           ; more than RMAX matches
LFNOK = $2056
SSTART = $2057
NAMEB = $2060           ; 64-byte name buffer (shared with LIST, unused here)
ENT = $20a0             ; current directory entry (32 bytes)
SDIR = $20c0            ; folder being scanned (first cluster)
QH = $20c4              ; folder queue head/tail (u16 indices into VRAM $6000)
QT = $20c6
SSEC = $20ea
SENT = $20eb
CH1 = $2060             ; 1-char string for the keyboard (only while drawing)
QV = $60                ; VRAM queue page (hi byte)
RV = $68                ; VRAM results page
RMAX = 64
QMAX_HI = $04           ; 1024 folders
KEYS = 43

search_main:            ; -> A = 0 back to the menu, 1 go to GDIR/GFILE
    stz QLEN
    stz QUERY
    stz KCUR
sk_redraw:
    jsr $eda9
    sei
    jsr kb_draw
    lda <$f7
    sta $0000
    cli
sk_loop:
    jsr wait_key
    bit #$10
    bne sk_up
    bit #$40
    bne sk_down
    bit #$80
    bne sk_left
    bit #$20
    bne sk_right
    bit #$08
    jne sk_search
    bit #$02
    bne sk_press
    bit #$01
    bne sk_back
    bra sk_loop
sk_up:
    lda KCUR
    cmp #40
    bcs sk_up4
    cmp #10
    bcc sk_loop
    sbc #10
    bra sk_set
sk_up4:                 ; action row -> last key row
    sbc #40
    asl a
    asl a
    adc #30
    bra sk_set
sk_down:
    lda KCUR
    cmp #30
    bcs sk_dn4
    adc #10
    bra sk_set
sk_dn4:
    cmp #40
    bcs sk_loop
    sbc #29             ; carry clear: -30
    lsr a
    lsr a
    cmp #$03
    bcc sk_dn5
    lda #$02
sk_dn5:
    clc
    adc #40
    bra sk_set
sk_left:
    lda KCUR
    beq sk_loop
    dec a
    bra sk_set
sk_right:
    lda KCUR
    inc a
    cmp #KEYS
    bcs sk_loop
sk_set:
    sta KCUR
sk_upd:
    sei
    jsr kb_draw
    lda <$f7
    sta $0000
    cli
    jmp sk_loop
sk_back:                ; I: delete a character, or leave when empty
    lda QLEN
    beq sk_exit
sk_del:
    dec QLEN
    ldx QLEN
    stz QUERY,x
    bra sk_upd
sk_exit:
    jsr $eda9
    cla
    rts
sk_press:
    lda KCUR
    cmp #42
    beq sk_search
    cmp #41
    beq sk_back2
    ldx QLEN
    cpx #16
    bcs sk_upd
    cmp #40
    bne sk_char
    lda #$20
    bra sk_add
sk_char:
    tay
    lda keychars,y
sk_add:
    sta QUERY,x
    inx
    stz QUERY,x
    stx QLEN
    bra sk_upd
sk_back2:
    lda QLEN
    beq sk_upd
    bra sk_del
sk_search:
    lda QLEN
    jeq sk_loop
    jsr $eda9
    sei
    lda #lo(s_busy)
    sta T
    lda #hi(s_busy)
    sta T+1
    lda #30
    sta CNT
    ldx #$02
    ldy #$05
    lda #$02
    jsr prt
    jsr scan_all
    lda <$f7
    sta $0000
    cli
    jsr results
    cmp #$00
    jeq sk_redraw
    rts

; ---------------------------------------------------------------- keyboard screen
kb_draw:
    lda #30
    sta CNT
    lda #lo(s_title)
    sta T
    lda #hi(s_title)
    sta T+1
    ldx #$01
    ldy #$01
    lda #$02
    jsr prt
    ldx #$00            ; query line: "> QUERY_" padded
    lda #$3e
    sta LINE
    lda #$20
    sta LINE+1
kd_q:
    lda QUERY,x
    beq kd_qe
    sta LINE+2,x
    inx
    bra kd_q
kd_qe:
    lda #$5f
    sta LINE+2,x
    inx
kd_qp:
    cpx #20
    bcs kd_qd
    lda #$20
    sta LINE+2,x
    inx
    bra kd_qp
kd_qd:
    stz LINE+22
    lda #lo(LINE)
    sta T
    lda #hi(LINE)
    sta T+1
    ldx #$02
    ldy #$03
    cla
    jsr prt
    stz SSTART          ; key index
kd_key:
    lda SSTART
    cmp #40
    bcs kd_act
    tay
    lda keychars,y
    sta CH1
    stz CH1+1
    lda SSTART          ; row = 6 + (i / 10) * 2, col = 6 + (i % 10) * 2
    ldy #$00
kd_div:
    cmp #10
    bcc kd_dv
    sbc #10
    iny
    bra kd_div
kd_dv:
    asl a
    adc #$06
    tax
    tya
    asl a
    adc #$06
    tay
    lda #lo(CH1)
    sta T
    lda #hi(CH1)
    sta T+1
    lda SSTART
    cmp KCUR
    beq kd_sel
    lda #$01
    bra kd_put
kd_sel:
    lda #$02
kd_put:
    jsr prt
    inc SSTART
    bra kd_key
kd_act:                 ; Espaço / Apagar / Buscar
    lda SSTART
    sec
    sbc #40
    asl a
    tax
    lda act_tab,x
    sta T
    lda act_tab+1,x
    sta T+1
    lda SSTART
    sec
    sbc #40
    tax
    lda act_col,x
    tax
    lda SSTART
    cmp KCUR
    beq kd_asel
    lda #$01
    bra kd_aput
kd_asel:
    lda #$02
kd_aput:
    ldy #15
    jsr prt
    inc SSTART
    lda SSTART
    cmp #KEYS
    bne kd_act
    lda #lo(s_khint)
    sta T
    lda #hi(s_khint)
    sta T+1
    ldx #$01
    ldy #23
    lda #$01
    jmp prt

; ---------------------------------------------------------------- walk the card
scan_all:
    stz RCOUNT
    stz SMORE
    stz QH
    stz QH+1
    stz QT
    stz QT+1
    lda FS_ROOT         ; q_push takes the cluster from ENT
    sta ENT+26
    lda FS_ROOT+1
    sta ENT+27
    lda FS_ROOT+2
    sta ENT+20
    lda FS_ROOT+3
    sta ENT+21
    jsr q_push
sa_next:
    lda QH
    cmp QT
    bne sa_pop
    lda QH+1
    cmp QT+1
    bne sa_pop
    rts
sa_pop:
    jsr q_pop
    stz LFNOK
    lda #64
    sta CNT2
sa_clus:
    ldx #$03
sa_c1:
    lda DCL,x
    sta T,x
    dex
    bpl sa_c1
    jsr clus2lba
    lda FS_BPC+1        ; sectors per cluster
    sta SSEC
    lda FS_BPC+2
    lsr a
    ror SSEC
sa_sec:
    jsr read_scr
    bcs sa_next
    ldx #lo(SCR)
    lda #hi(SCR)
    jsr vram_r
    lda #$10
    sta SENT
sa_ent:
    ldx #$00
sa_rd:
    lda $0002
    sta ENT,x
    inx
    lda $0003
    sta ENT,x
    inx
    cpx #$20
    bne sa_rd
    jsr sa_entry
    bcs sa_next         ; end of this folder
    dec SENT
    bne sa_ent
    jsr lba_inc
    dec SSEC
    bne sa_sec
    jsr fat_next
    bcs sa_next
    dec CNT2
    bne sa_clus
    jmp sa_next

sa_entry:               ; ENT -> C=1 at the end of the folder
    lda ENT
    bne se_1
    sec
    rts
se_1:
    cmp #$e5
    beq se_skip
    lda ENT+11
    cmp #$0f
    bne se_sfn
    lda ENT             ; long-name part: chars at 1,3,5,7,9,14,...,30
    and #$40
    beq se_l1
    ldx #63
se_clr:
    stz NAMEB,x
    dex
    bpl se_clr
se_l1:
    lda ENT
    and #$1f
    beq se_skip
    dec a
    sta TMP             ; offset = (seq - 1) * 13
    asl a
    asl a
    asl a
    clc
    adc TMP
    adc TMP
    adc TMP
    adc TMP
    adc TMP
    tay
    clx
se_lc:
    cpy #60
    bcs se_lfn
    phx
    lda lfnpos,x
    tax
    lda ENT,x
    plx
    cmp #$ff
    bne se_lc2
    cla
se_lc2:
    sta NAMEB,y
    iny
    inx
    cpx #13
    bne se_lc
se_lfn:
    lda #$01
    sta LFNOK
    clc
    rts
se_skip:
    stz LFNOK
    clc
    rts
se_sfn:
    and #$08            ; volume label
    bne se_skip
    lda ENT
    cmp #$2e            ; . and ..
    beq se_skip
    lda ENT+11
    and #$10
    beq se_file
    jsr q_push          ; a folder: scan it later
    bra se_skip
se_file:
    ldx #$02            ; .PCE or .SGX
se_ext:
    lda ENT+8,x
    cmp ext_pce,x
    bne se_sgx
    dex
    bpl se_ext
    bra se_ok
se_sgx:
    ldx #$02
se_ext2:
    lda ENT+8,x
    cmp ext_sgx,x
    bne se_skip
    dex
    bpl se_ext2
se_ok:
    lda LFNOK
    bne se_name
    jsr sfn_name
se_name:
    stz LFNOK
    jsr name_match
    bcs se_done
    jsr add_result
se_done:
    clc
    rts

sfn_name:               ; NAMEB = "NAME.EXT" from the 8.3 entry
    clx
    cly
sn_1:
    lda ENT,x
    cmp #$20
    beq sn_2
    sta NAMEB,y
    iny
    inx
    cpx #$08
    bne sn_1
sn_2:
    lda #$2e
    sta NAMEB,y
    iny
    ldx #$08
sn_3:
    lda ENT,x
    sta NAMEB,y
    iny
    inx
    cpx #11
    bne sn_3
    cla
    sta NAMEB,y
    rts

name_match:             ; QUERY inside NAMEB, ignoring case. C=0 if found
    stz SSTART
nm_s:
    ldx SSTART
    cly
nm_c:
    cpy QLEN
    beq nm_yes
    lda NAMEB,x
    beq nm_no
    cmp #$61
    bcc nm_f
    cmp #$7b
    bcs nm_f
    sbc #$1f
nm_f:
    cmp QUERY,y
    bne nm_next
    inx
    iny
    bra nm_c
nm_next:
    inc SSTART
    ldx SSTART
    cpx #60
    bcs nm_no
    lda NAMEB,x
    bne nm_s
nm_no:
    sec
    rts
nm_yes:
    clc
    rts

q_push:                 ; queue the cluster in ENT+26/27/20/21
    lda QT+1
    cmp #QMAX_HI
    bcs qp_ret
    lda QT              ; VRAM = $6000 + QT * 2
    asl a
    tax
    lda QT+1
    rol a
    clc
    adc #QV
    jsr vram_w
    lda ENT+26
    sta $0002
    lda ENT+27
    sta $0003
    lda ENT+20
    sta $0002
    lda ENT+21
    sta $0003
    inc QT
    bne qp_ret
    inc QT+1
qp_ret:
    rts

q_pop:                  ; SDIR = DCL = next queued folder
    lda QH
    asl a
    tax
    lda QH+1
    rol a
    clc
    adc #QV
    jsr vram_r
    lda $0002
    sta SDIR
    sta DCL
    lda $0003
    sta SDIR+1
    sta DCL+1
    lda $0002
    sta SDIR+2
    sta DCL+2
    lda $0003
    sta SDIR+3
    sta DCL+3
    inc QH
    bne qo_ret
    inc QH+1
qo_ret:
    rts

res_addr:               ; A = index (0-63) -> X = lo, A = hi of VRAM $6800 + 20 * index
    stz TMP
    asl a
    asl a
    sta R
    asl a
    rol TMP
    asl a
    rol TMP
    clc
    adc R
    tax
    lda TMP
    adc #RV
    rts

add_result:             ; folder, file cluster, first 32 chars of the name
    lda RCOUNT
    cmp #RMAX
    bcc ar_go
    lda #$01
    sta SMORE
    rts
ar_go:
    jsr res_addr
    jsr vram_w
    lda SDIR
    sta $0002
    lda SDIR+1
    sta $0003
    lda SDIR+2
    sta $0002
    lda SDIR+3
    sta $0003
    lda ENT+26
    sta $0002
    lda ENT+27
    sta $0003
    lda ENT+20
    sta $0002
    lda ENT+21
    sta $0003
    clx
ar_nm:
    lda NAMEB,x
    sta $0002
    inx
    lda NAMEB,x
    sta $0003
    inx
    cpx #32
    bne ar_nm
    inc RCOUNT
    rts

; ---------------------------------------------------------------- results
results:                ; -> A = 0 back to the keyboard, 1 go (GDIR/GFILE set)
    stz RCUR
rs_redraw:
    jsr $eda9
    sei
    jsr res_draw
    lda <$f7
    sta $0000
    cli
rs_loop:
    jsr wait_key
    bit #$10
    bne rs_up
    bit #$40
    bne rs_down
    bit #$80
    bne rs_pgup
    bit #$20
    bne rs_pgdn
    bit #$0a
    bne rs_pick
    bit #$01
    bne rs_back
    bra rs_loop
rs_up:
    lda RCUR
    beq rs_loop
    dec RCUR
    bra rs_upd
rs_down:
    lda RCUR
    inc a
    cmp RCOUNT
    bcs rs_loop
    sta RCUR
    bra rs_upd
rs_pgup:
    lda RCUR
    sec
    sbc #16
    bcs rs_p1
    cla
rs_p1:
    sta RCUR
    bra rs_upd
rs_pgdn:
    lda RCOUNT
    beq rs_loop
    lda RCUR
    clc
    adc #16
    cmp RCOUNT
    bcc rs_p2
    lda RCOUNT
    dec a
rs_p2:
    sta RCUR
rs_upd:
    sei
    jsr res_draw
    lda <$f7
    sta $0000
    cli
    jmp rs_loop
rs_back:
    cla
    rts
rs_pick:
    lda RCOUNT
    beq rs_loop
    sei
    lda RCUR
    jsr res_addr
    jsr vram_r
    lda $0002
    sta GDIR
    lda $0003
    sta GDIR+1
    lda $0002
    sta GDIR+2
    lda $0003
    sta GDIR+3
    lda $0002
    sta GFILE
    lda $0003
    sta GFILE+1
    lda $0002
    sta GFILE+2
    lda $0003
    sta GFILE+3
    lda <$f7
    sta $0000
    cli
    lda #$01
    rts

res_draw:
    lda #30
    sta CNT
    ldx #$00            ; title: "Resultados: NN" (+ "+" when cut at 64)
rd_t:
    lda s_rtitle,x
    beq rd_tn
    sta LINE,x
    inx
    bra rd_t
rd_tn:
    lda RCOUNT
    ldy #$00
rd_div:
    cmp #10
    bcc rd_dv
    sbc #10
    iny
    bra rd_div
rd_dv:
    pha
    tya
    beq rd_u
    clc
    adc #$30
    sta LINE,x
    inx
rd_u:
    pla
    clc
    adc #$30
    sta LINE,x
    inx
    lda SMORE
    beq rd_z
    lda #$2b
    sta LINE,x
    inx
rd_z:
    stz LINE,x
    lda #lo(LINE)
    sta T
    lda #hi(LINE)
    sta T+1
    ldx #$01
    ldy #$01
    lda #$02
    jsr prt
    lda #lo(s_rhint)
    sta T
    lda #hi(s_rhint)
    sta T+1
    ldx #$01
    ldy #23
    lda #$01
    jsr prt
    lda RCOUNT
    bne rd_items
    lda #lo(s_none)
    sta T
    lda #hi(s_none)
    sta T+1
    ldx #$02
    ldy #$05
    lda #$01
    jmp prt
rd_items:
    lda RCUR
    and #$f0
    sta SSTART          ; first index on the page
    lda #$00
    sta SENT            ; row
rd_row:
    ldx #$1d            ; LINE = blanks
    lda #$20
rd_cl:
    sta LINE,x
    dex
    bpl rd_cl
    stz LINE+30
    lda SSTART
    clc
    adc SENT
    sta SSEC            ; index
    cmp RCOUNT
    bcs rd_put
    cmp RCUR
    bne rd_nm
    lda #$3e
    sta LINE
rd_nm:
    lda SSEC
    jsr res_addr
    pha
    txa
    clc
    adc #$04            ; name starts after 4 words
    tax
    pla
    adc #$00
    jsr vram_r
    ldx #$01
rd_cp:
    lda $0002
    beq rd_put
    sta LINE,x
    inx
    cpx #$1e
    beq rd_put
    lda $0003
    beq rd_put
    sta LINE,x
    inx
    cpx #$1e
    bne rd_cp
rd_put:
    lda #lo(LINE)
    sta T
    lda #hi(LINE)
    sta T+1
    lda SENT
    clc
    adc #$03
    tay
    lda SSEC
    cmp RCUR
    beq rd_sel
    lda #$01
    bra rd_p2
rd_sel:
    cla
rd_p2:
    ldx #$01
    jsr prt
    inc SENT
    lda SENT
    cmp #16
    jne rd_row
    rts
'''


def tables(enc):
    db = lambda b: ','.join(str(x) for x in b)
    keys = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-\'&.'
    t = '\nkeychars: .db ' + db(keys.encode())
    t += '\nlfnpos: .db 1,3,5,7,9,14,16,18,20,22,24,28,30'
    t += '\next_pce: .db "PCE"'
    t += '\next_sgx: .db "SGX"'
    t += '\nact_col: .db 3,13,23'
    t += '\nact_tab: .dw s_space,s_bksp,s_find'
    for name, text in {
        's_title': 'Buscar jogo',
        's_space': 'Espaço',
        's_bksp': 'Apagar',
        's_find': 'Buscar',
        's_khint': 'II: tecla  I: apaga  RUN: busca',
        's_busy': 'Buscando no cartão...',
        's_rtitle': 'Resultados: ',
        's_none': 'Nenhum jogo encontrado.',
        's_rhint': 'RUN/II: ir ao jogo  I: voltar',
    }.items():
        t += '\n%s: .db %s' % (name, db(enc(text)))
    return t
