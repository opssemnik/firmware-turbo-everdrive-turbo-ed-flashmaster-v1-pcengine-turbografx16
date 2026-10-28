"""Build the Retrogamer POA PT-BR mod of the Turbo EverDrive v1 OS (tos.pce, OS v4).

usage: python build.py [stock_tos.pce] [out_tos.pce]
Every patch checks the stock bytes it replaces, so a wrong input ROM fails loudly.
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import assemble
import art
import cart_asm
import search_asm
import loader_asm

MOD_VERSION = 12
VERSION_STR = 'PT-BR v%d' % MOD_VERSION
STOCK_MD5 = '38241a96caa1573f9caf20a2b52dd3e8'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BANK = 0x2000
def foff(bank, cpu):  # file offset of a cpu address inside a bank
    return bank * BANK + (cpu & 0x1fff)

# ---------------------------------------------------------------- charset
# Codes $80-$9F are new glyphs appended to the font (tiles $E0-$FF).
ACCENTS = 'áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇüÜºª'
CHARMAP = {ch: 0x80 + i for i, ch in enumerate(ACCENTS)}

def enc(s):
    out = bytearray()
    for ch in s:
        if ch in CHARMAP: out.append(CHARMAP[ch])
        elif 32 <= ord(ch) < 127: out.append(ord(ch))
        else: raise ValueError('no glyph for %r' % ch)
    return bytes(out) + b'\0'

def b(s): return int(s.replace('.', '0').replace('#', '1'), 2)

ACC2 = {  # two-row accents for lowercase (rows 0,1)
    'acute': (b('....##..'), b('...##...')),
    'grave': (b('..##....'), b('...##...')),
    'circ':  (b('...##...'), b('..#..#..')),
    'tilde': (b('..##.#..'), b('.#.##...')),
    'uml':   (0, b('.##..##.')),
}
ACC1 = {  # one-row accents for capitals (row 0)
    'acute': b('...##...'), 'grave': b('..##....'), 'circ': b('..####..'),
    'tilde': b('.##.##..'), 'uml': b('.##..##.'),
}
DROP = {'A': 3, 'E': 2, 'I': 2, 'O': 2, 'U': 2, 'C': 3}

def make_glyphs(font):
    def g(ch): return list(font[(ord(ch) - 32) * 8:(ord(ch) - 31) * 8])
    def low(base, acc):
        rows = g(base)
        if base == 'i': rows[0] = rows[1] = 0
        a0, a1 = ACC2[acc]
        rows[0] |= a0; rows[1] |= a1
        return rows
    def cap(base, acc):
        rows = g(base)[:7]
        del rows[DROP[base]]
        return [ACC1[acc]] + rows + [0]
    def ced(base, upper):
        rows = g(base)
        if upper:
            rows = rows[:7]; del rows[DROP['C']]; rows = [0] + rows + [b('..##....')]
        else:
            rows[7] = b('..##....')
        return rows
    spec = [('a', 'acute'), ('a', 'grave'), ('a', 'circ'), ('a', 'tilde'), ('e', 'acute'), ('e', 'circ'),
            ('i', 'acute'), ('o', 'acute'), ('o', 'circ'), ('o', 'tilde'), ('u', 'acute'), 'ç',
            ('A', 'acute'), ('A', 'grave'), ('A', 'circ'), ('A', 'tilde'), ('E', 'acute'), ('E', 'circ'),
            ('I', 'acute'), ('O', 'acute'), ('O', 'circ'), ('O', 'tilde'), ('U', 'acute'), 'Ç',
            ('u', 'uml'), ('U', 'uml')]
    out = bytearray()
    for s in spec:
        if s == 'ç': out += bytes(ced('c', False))
        elif s == 'Ç': out += bytes(ced('C', True))
        elif s[0].islower(): out += bytes(low(*s))
        else: out += bytes(cap(*s))
    out += bytes([0, b('..###...'), b('.#...#..'), b('..###...'), 0, b('.#####..'), 0, 0])  # º
    out += bytes([0, b('..###...'), b('.....#..'), b('..####..'), b('.#...#..'), b('..####..'), 0, b('.#####..')])  # ª
    assert len(out) == len(ACCENTS) * 8
    return bytes(out).ljust(32 * 8, b'\0')

# ---------------------------------------------------------------- strings
# (stock address, new text, centre?) ; centre=True re-centres the fixed x coordinate
TRANSLATE = [
    (0x4000, 'Atualizando o SO...', True),
    (0x400d, 'NÃO DESLIGUE O CONSOLE', True),
    (0x4028, 'Atualizando o SO...', True),
    (0x4035, 'NÃO DESLIGUE O CONSOLE', True),
    (0x4050, 'Carregando...', True),
    (0x405b, 'NÃO DESLIGUE O CONSOLE', True),
    (0x4076, 'Carregando...', True),
    (0x4081, 'NÃO DESLIGUE O CONSOLE', True),
    (0x40a8, 'Pág.:  /', False),        # same length: page numbers are drawn into the gaps
    (0x40b4, 'Versão do SO :', False),
    (0x40c3, 'Versão Firm. :', False),
    (0x40d2, 'Data Compil. :', False),
    (0x40e1, 'Hora Compil. :', False),
    (0x4102, 'ERRO:  ', False),
]
EXTRA = {  # new strings used by the mod's own code
    'str_ver': VERSION_STR,
    'str_c1': 'Mod: Retrogamer POA',
    'str_c2': 'por Antonio & The Nobre',
    'str_c3': 'SELECT no menu: muda o tema',
}
HELP = [('II', 'Abrir'), ('RUN', 'Jogar'), ('I', 'Voltar'), ('SEL', 'Tema')]  # top help line
SPLASH_LINES = [('Turbo EverDrive OS', 2), (VERSION_STR, 11), ('', 0), ('por Antonio & The Nobre', 5),
                ('', 0), ('Aperte um botão', 3)]
SPLASH_FRAMES = 90       # 1.5 s, or until a button is pressed
BG_SCROLL = 240          # BAT row 30 is the top screen row: rows 30-31 hold the banner
SPLASH_BANKS = (14, 15)  # tiles, BAT map
STR_BASE = 0x4110  # free space in bank 3 (mapped at $4000 by the OS)
SCREEN_COLS = 32

# ---------------------------------------------------------------- themes
# Palette n colour 1 = glyph, colour 2 = cell background. Blank screen cells are palette-0
# spaces, so palette 0 colour 2 is the screen background; palettes 1/2 reuse it.
# pal0 fg = cursor line / about text, pal1 = files (+ hint), pal2 = folders (+ credits), pal3 = bars
SLOTS = [0x00, 0x01, 0x02, 0x11, 0x12, 0x21, 0x22, 0x31, 0x32]
THEMES = [  # name, backdrop, screen bg, cursor, file, folder, bar fg, bar bg   (r,g,b 0-7)
    ('Original',      (0,0,1), (0,0,0), (7,7,7), (4,4,4), (6,6,0), (7,7,7), (3,3,3)),
    ('Fosforo Verde', (0,1,0), (0,1,0), (5,7,5), (1,5,1), (3,7,2), (0,1,0), (2,6,2)),
    ('Ambar',         (1,0,0), (1,0,0), (7,7,3), (6,3,0), (7,5,1), (1,0,0), (6,4,0)),
    ('Azul',          (0,0,2), (0,0,2), (7,7,7), (4,5,7), (7,7,2), (7,7,7), (1,2,5)),
    ('Brasil',        (0,2,0), (0,2,0), (7,7,7), (7,6,0), (5,6,7), (7,7,7), (0,0,4)),
    ('Synthwave',     (1,0,2), (1,0,2), (7,7,7), (6,3,7), (2,7,7), (7,7,7), (5,0,5)),
    ('Turbo',         (0,0,0), (0,0,0), (7,7,7), (5,5,5), (7,4,0), (7,7,7), (6,2,0)),
    ('Papel',         (6,6,6), (6,6,6), (0,0,6), (2,2,2), (5,2,0), (7,7,7), (1,1,4)),
]
def theme_colors(t):
    _, bd, bg, cur, fil, fol, barfg, barbg = t
    return [bd, cur, bg, fil, bg, fol, bg, barfg, barbg]  # in SLOTS order
def vce(rgb):
    r, g, bl = rgb
    return (g << 6) | (r << 3) | bl

# ---------------------------------------------------------------- code
JOYHOOK = """
; bank 0 free space, always mapped at $e000.
joyhook:                ; replaces "jsr joy" in the file browser's wait-for-key loop
    jsr $f8e9           ; joy(0): X = buttons, A = extended
    phx
    pha
    tma #$40            ; far call idle in bank 13 via MPR6
    pha
    lda #$0d
    tam #$40
    jsr idle            ; help line, artwork, SELECT/II handling; A = key for the OS
    tay
    pla
    tam #$40
    pla
    plx
    cpy #$00            ; 0: the real buttons
    beq jh_real
    cpy #$ff            ; $ff: nothing (SELECT is handled by the mod)
    beq jh_none
    tya                 ; a key pressed by the mod (go to game, letter jump, II on a game)
    tax
jh_none:
    cla
    cpy #$ff
    bne jh_real
    clx
jh_real:
    rts

cls_new:                ; cls() entry ($eda9) jumps here
    jsr cls_orig
    tma #$40
    pha
    lda #$0d
    tam #$40
    jsr banner_draw
    pla
    tam #$40
    rts
cls_orig:
    lda $276f           ; first instruction of the stock cls, overwritten by the jump
    jmp $edac

hub_far:                ; menu in bank 13 -> A = 0 back, 1 go to a game
    tma #$40
    pha
    lda #$0d
    tam #$40
    jsr hub
    tay
    pla
    tam #$40
    tya
    rts

ld_hook:                ; replaces the OS's $fd54 (copy game to flash): bar setup, then the RAM routine
    sei
    phx
    pha
    tma #$40
    pha
    lda #$0d
    tam #$40
    jsr prog_setup      ; X = banks to copy
    pla
    tam #$40
    pla
    plx
    jmp $2b8f

act_far:                ; action screen in bank 13 -> A = 0 load, 1 back
    tma #$40
    pha
    lda #$0d
    tam #$40
    jsr action
    tay
    pla
    tam #$40
    tya
    rts
"""

HOOK10 = """
; bank 10 free space. RUN on a file jumps here instead of starting to load it.
hook10:
    jsr act_far
    cmp #$00
    bne h10_back
    lda <$00            ; the two instructions the jump replaced
    sec
    jmp $a96d
h10_back:               ; same as the OS does around the about screen: force a full redraw
    ldx #$ff
    lda #$ff
    stx $3b8e
    sta $3b8f
    stx $3b90
    sta $3b91
    jmp $b2bf

hub10b:                 ; replaces "jsr about" at $b0e9 (I at the root)
    jsr hub_far
    cmp #$00
    bne hb_go
    rts                 ; back to the OS, which continues with jmp $b2bf
hb_go:
    pla                 ; not returning: enter the game's folder with the OS's own code
    pla
    lda #$02            ; the key local becomes II, as if the user opened a folder
    ldy #$0d
    sta [$00],y
    lda #$04            ; the OS passes $3b92 + this local to enterdir: point it at $3b96
    ldy #$08
    sta [$00],y
    jmp $af69
"""

def puts(label, x, y):
    """HuC put_string(label, x, y) call sequence, as the OS compiles it."""
    return """
    lda <$02
    clc
    adc #$03
    sta <$02
    tay
    lda #hi(%s)
    sta $3f24,y
    lda #lo(%s)
    sta $3f25,y
    lda #%d
    sta $3f26,y
    ldx #%d
    cla
    jsr $efd8
""" % (label, label, x, y)

def about_src():
    return """
; bank 11 free space (about screen runs with bank 11 at $a000)
about_ver:              ; replaces put_number(4, 2, x, y) for the OS version
    ldy <$02
    lda $3f26,y         ; x argument
    pha
    lda <$02
    sec
    sbc #$04            ; drop put_number's 4 bytes of arguments
    clc
    adc #$03
    sta <$02
    tay
    lda #hi(str_ver)
    sta $3f24,y
    lda #lo(str_ver)
    sta $3f25,y
    pla
    sta $3f26,y
    cla                 ; X still holds y
    jmp $efd8

about_credits:          ; runs after the last about label is drawn
    jsr $efd8
    lda $2770           ; font palette lives in the high nibble
    pha
    and #$0f
    ora #$20            ; palette 2 (folder colour) for the credits
    sta $2770
""" + puts('str_c1', 4, 20) + puts('str_c2', 4, 22) + """
    pla
    pha
    and #$0f
    ora #$10            ; palette 1 (file colour) for the hint
    sta $2770
""" + puts('str_c3', 2, 24) + """
    pla
    sta $2770
    rts

splash_entry:           ; replaces set_font_pal(0) in main, after palette + font init
    jsr $edd5
    tma #$40
    pha
    lda #$0d
    tam #$40
    jsr splash
    pla
    tam #$40
    rts
"""

# ---------------------------------------------------------------- patching
class Rom:
    def __init__(self, data):
        self.d = bytearray(data)
    def expect(self, off, hexs):
        want = bytes.fromhex(hexs.replace(' ', ''))
        got = bytes(self.d[off:off + len(want)])
        if got != want:
            raise SystemExit('stock bytes differ at %05x: %s != %s' % (off, got.hex(), want.hex()))
    def put(self, off, data, free=True):
        if free:
            seg = self.d[off:off + len(data)]
            if any(x != 0xff for x in seg):
                raise SystemExit('target %05x not free' % off)
        self.d[off:off + len(data)] = data

STOCK_URL = 'https://krikzz.com/pub/support/turbo-everdrive/v1/os/v4/tos.pce'

def build(src, dst):
    if not os.path.exists(src):  # the stock OS is not redistributed here: fetch it from Krikzz
        import urllib.request
        os.makedirs(os.path.dirname(src), exist_ok=True)
        print('downloading stock OS from', STOCK_URL)
        open(src, 'wb').write(urllib.request.urlopen(STOCK_URL, timeout=60).read())
    data = open(src, 'rb').read()
    if hashlib.md5(data).hexdigest() != STOCK_MD5:
        raise SystemExit('input is not the stock OS v4 tos.pce')
    rom = Rom(data)

    # 1. font: 96 stock glyphs + 32 new ones in empty bank 13, loaded as 128 chars
    font = data[0x2000:0x2300]
    rom.put(foff(13, 0), font + make_glyphs(font))
    for site in (0x01ae, 0x0e5c):              # lda #1 / sta <$fa / lda #$60 / sta <$fc
        rom.expect(site, 'a9 01 85 fa a9 60 85 fc')
        rom.d[site + 1] = 13
        rom.d[site + 5] = 0x80

    # 2. strings
    sym = {}
    pool = bytearray(); addr = STR_BASE
    newaddr = {}
    for old, text, _ in TRANSLATE:
        if text not in newaddr:
            newaddr[text] = addr + len(pool); pool += enc(text)
    for name, text in EXTRA.items():
        sym[name] = addr + len(pool); pool += enc(text)
    rom.put(foff(3, STR_BASE), bytes(pool))
    for old, text, centre in TRANSLATE:
        sites = [i for i in range(len(data) - 5)
                 if data[i] == 0xa2 and data[i + 1] == old & 0xff and data[i + 2] == 0xa9
                 and data[i + 3] == old >> 8 and data[i + 4] == 0xa8]
        if len(sites) != 1: raise SystemExit('string %04x: %d refs' % (old, len(sites)))
        i = sites[0]; new = newaddr[text]
        rom.d[i + 1] = new & 0xff; rom.d[i + 3] = new >> 8
        if centre:
            rom.expect(i + 20, 'a2'); rom.expect(i + 22, 'a9 00')
            rom.d[i + 21] = (SCREEN_COLS - len(text)) // 2

    # 3. graphics: banner/icons (bank 13), splash (banks 14-15)
    font128 = bytes(rom.d[foff(13, 0):foff(13, 0) + 0x400])
    ts, ban, icons, ban_can = art.build_banner(font128, enc)
    help_row = art.help_line(icons, enc, HELP)
    probe_col = next(i for i, w in enumerate(help_row) if w >> 12 == art.BANNER_PAL_NO)
    sts, sbat, spl_can = art.build_splash(font128, enc, SPLASH_LINES)
    spl_tiles = sts.blob()
    if len(spl_tiles) > BANK: raise SystemExit('splash too big: %d tiles' % len(sts.data))
    rom.put(foff(SPLASH_BANKS[0], 0), spl_tiles)
    rom.put(foff(SPLASH_BANKS[1], 0), b''.join(bytes([w & 0xff, w >> 8]) for row in sbat for w in row))
    ban_can.png(os.path.join(os.path.dirname(dst), 'art_banner.png'), art.BANNER_PAL, 3)
    spl_can.png(os.path.join(os.path.dirname(dst), 'art_splash.png'), art.SPLASH_PAL, 2)

    # 4. themes + graphics code and tables in bank 13 at $c400
    tsym = dict(cart_asm.CONSTS)
    tsym.update({'NTHEMES': len(THEMES), 'NSLOTS': len(SLOTS), 'BAN_TILES_LEN': len(ts.blob()),
            'HELP_PROBE_COL': probe_col, 'HELP_PROBE': help_row[probe_col],
            'SPL_TILES_LEN': len(spl_tiles), 'SPL_TILE_BANK': SPLASH_BANKS[0],
            'SPL_MAP_BANK': SPLASH_BANKS[1], 'SPLASH_FRAMES': SPLASH_FRAMES})
    stride = len(SLOTS) * 2
    tables = '\nslots: .db ' + ','.join(str(s) for s in SLOTS)
    tables += '\noffs: .db ' + ','.join(str(i * stride) for i in range(len(THEMES)))
    words = [vce(c) for t in THEMES for c in theme_colors(t)]
    tables += '\ncolors: .dw ' + ','.join(str(w) for w in words)
    # banner/help/splash data in bank 15 after the splash map, read through MPR3 ($6000)
    w16 = lambda ws: b''.join(bytes([w & 0xff, w >> 8]) for w in ws)
    blob15 = (w16(art.vce(c) for c in art.BANNER_PAL) + w16(art.vce(c) for c in art.SPLASH_PAL)
              + w16(ban) + w16(help_row) + ts.blob())
    rom.put(foff(SPLASH_BANKS[1], 0x1000), blob15)
    tsym.update({'B15_BANPAL': 0x7000, 'B15_SPLPAL': 0x7020, 'B15_BANMAP': 0x7040,
                 'B15_HELPMAP': 0x70c0, 'B15_BANTILES': 0x7100})
    tables += cart_asm.tables(enc)
    tsym.update({'SEARCH_BANK': SPLASH_BANKS[1], 'SEARCH_ENTRY': search_asm.ORG})
    # loading progress: the OS's RAM copy routine, rebuilt with a bar block per 8 KB bank
    lsym = {'PCNT': loader_asm.PCNT, 'BAR_FULL': 0x41c1}
    lcode, lsym = assemble(loader_asm.ROUTINE, loader_asm.RAM_ORG, lsym)
    if len(lcode) > 0x100: raise SystemExit('loader routine too big: %d' % len(lcode))
    tables += '\nld_routine: .db ' + ','.join(str(x) for x in lcode.ljust(0x100, bytes(1)))
    tables += '\nbar_tiles: .db ' + ','.join(str(x) for x in loader_asm.tiles())
    tsym.update({'PCNT': loader_asm.PCNT, 'LD_STEP_RAM': lsym['ld_step'] + 1})
    tcode, tsym = assemble(cart_asm.BANK13 + loader_asm.SETUP + tables, 0xc400, tsym)
    if 0xc400 + len(tcode) > 0xe000: raise SystemExit('bank 13 overflow')
    rom.put(foff(13, 0xc400), tcode)
    scode, _ = assemble(search_asm.SRC + search_asm.tables(enc), search_asm.ORG, dict(tsym))
    if len(scode) > 0x800: raise SystemExit('search module too big: %d' % len(scode))
    rom.put(foff(SPLASH_BANKS[1], search_asm.ORG), scode)

    # 5. about screen: version text + credits; splash hook (bank 11, $a000)
    sym['splash'] = tsym['splash']
    code, sym = assemble(about_src(), 0xb600, sym)
    rom.put(foff(11, 0xb600), code)
    rom.expect(foff(11, 0xa30e), '20 64 ef')   # put_number(4,...) = OS version
    rom.d[foff(11, 0xa30f):foff(11, 0xa311)] = bytes([sym['about_ver'] & 0xff, sym['about_ver'] >> 8])
    rom.expect(foff(11, 0xa2a8), '20 d8 ef')   # put_string("Assembly Time:")
    rom.d[foff(11, 0xa2a9):foff(11, 0xa2ab)] = bytes([sym['about_credits'] & 0xff, sym['about_credits'] >> 8])

    rom.expect(foff(11, 0xad50), 'a2 00 a9 00 20 d5 ed')  # set_font_pal(0) after palette init
    rom.d[foff(11, 0xad55):foff(11, 0xad57)] = bytes([sym['splash_entry'] & 0xff, sym['splash_entry'] >> 8])

    # 6. bank 0: SELECT/help hook + cls hook; vsync IRQ scrolls the BG by BG_SCROLL
    jcode, jsym = assemble(JOYHOOK, 0xff63, {k: tsym[k] for k in ('idle', 'banner_draw', 'action', 'hub', 'prog_setup')})
    if 0xff63 + len(jcode) > 0xfff6: raise SystemExit('bank 0 hook overflow')
    rom.put(foff(0, 0xff63), jcode)
    rom.expect(foff(10, 0xa567), '20 e9 f8')
    rom.d[foff(10, 0xa568):foff(10, 0xa56a)] = bytes([jsym['joyhook'] & 0xff, jsym['joyhook'] >> 8])
    hcode, hsym = assemble(HOOK10, 0xbf63, {'act_far': jsym['act_far'], 'hub_far': jsym['hub_far']})
    if 0xbf63 + len(hcode) > 0xc000: raise SystemExit('bank 10 hook overflow')
    rom.put(foff(10, 0xbf63), hcode)
    rom.expect(foff(10, 0xa96a), 'a5 00 38 e9 02')   # RUN on a file: start of the load path
    rom.d[foff(10, 0xa96a):foff(10, 0xa96d)] = bytes([0x4c, 0x63, 0xbf])
    rom.expect(foff(10, 0xb0e9), '20 44 81')   # I at the root: jsr about
    rom.d[foff(10, 0xb0ea):foff(10, 0xb0ec)] = bytes([hsym['hub10b'] & 0xff, hsym['hub10b'] >> 8])
    rom.expect(0x1d54, '78 ad 8e 2b c9 01 f0 07 73 66 fd 8e 2b 00 01 4c 8f 2b')  # copy game to flash
    rom.d[0x1d54:0x1d57] = bytes([0x4c, jsym['ld_hook'] & 0xff, jsym['ld_hook'] >> 8])
    print('  loader routine %d bytes' % len(lcode))
    rom.expect(0x0da9, 'ad 6f 27')             # cls(): lda $276f
    rom.d[0x0da9:0x0dac] = bytes([0x4c, jsym['cls_new'] & 0xff, jsym['cls_new'] >> 8])
    rom.expect(0x027d, 'ad 10 22 8d 02 00 ad 11 22')  # vsync IRQ: BYR = bg_y
    rom.d[0x027d:0x0280] = bytes([0xa9, BG_SCROLL & 0xff, 0xea])
    rom.d[0x0283:0x0286] = bytes([0xa9, BG_SCROLL >> 8, 0xea])

    open(dst, 'wb').write(rom.d)
    print('built %s  (%s)  md5 %s' % (dst, VERSION_STR, hashlib.md5(rom.d).hexdigest()))
    print('  bank0 hook %d bytes, bank11 about %d bytes, bank13 themes %d bytes, strings %d bytes'
          % (len(jcode), len(code), len(tcode), len(pool)))
    return rom.d

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'stock', 'tos.pce')
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'out', 'TOS.PCE')
    build(src, dst)
