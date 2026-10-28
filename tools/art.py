"""Original graphics for the mod: top banner, button icons + help line, boot splash.

Everything is drawn here from the OS font plus hand-made pixels, then converted to
PC Engine 4bpp tiles / BAT words / 9-bit palettes.
"""

def vce(rgb):
    r, g, b = rgb
    return (g << 6) | (r << 3) | b


def tile_bytes(px):
    """px: 8 rows of 8 colour indices -> 32 bytes in VRAM write order (word lo, word hi)."""
    out = bytearray()
    for plane_pair in (0, 2):
        for y in range(8):
            lo = hi = 0
            for x in range(8):
                c = px[y][x]
                lo |= ((c >> plane_pair) & 1) << (7 - x)
                hi |= ((c >> (plane_pair + 1)) & 1) << (7 - x)
            out += bytes([lo, hi])
    return bytes(out)


class Canvas:
    def __init__(self, w, h, fill=0):
        self.w, self.h = w, h
        self.p = [[fill] * w for _ in range(h)]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h: self.p[y][x] = c

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w): self.set(xx, yy, c)

    def glyph(self, rows, x, y, scale, color, shadow=None):
        """rows: 8 bytes. color: index or fn(row_pixel_y)->index."""
        if shadow is not None:
            self.glyph(rows, x + 1, y + 1, scale, lambda _: shadow)
        for gy, bits in enumerate(rows):
            for gx in range(8):
                if bits & (0x80 >> gx):
                    for sy in range(scale):
                        py = gy * scale + sy
                        c = color(py) if callable(color) else color
                        for sx in range(scale):
                            self.set(x + gx * scale + sx, y + py, c)

    def text(self, font, codes, x, y, scale, color, shadow=None, adv=8):
        for i, ch in enumerate(codes):
            self.glyph(font[(ch - 32) * 8:(ch - 31) * 8], x + i * adv * scale, y, scale, color, shadow)

    def tiles(self):
        """-> list of 8x8 index grids, row-major over the canvas."""
        out = []
        for ty in range(self.h // 8):
            for tx in range(self.w // 8):
                out.append([self.p[ty * 8 + y][tx * 8:tx * 8 + 8] for y in range(8)])
        return out

    def png(self, path, pal, scale=2):
        from PIL import Image
        img = Image.new('RGB', (self.w, self.h))
        px = img.load()
        for y in range(self.h):
            for x in range(self.w):
                r, g, b = pal[self.p[y][x]]
                px[x, y] = (r * 255 // 7, g * 255 // 7, b * 255 // 7)
        img.resize((self.w * scale, self.h * scale), Image.NEAREST).save(path)


class TileSet:
    """Deduplicating tile store starting at VRAM tile number `base`."""
    def __init__(self, base, blank=True):
        self.base = base; self.data = []; self.index = {}
        if blank: self.add([[0] * 8 for _ in range(8)])

    def add(self, px):
        key = tile_bytes(px)
        if key not in self.index:
            self.index[key] = self.base + len(self.data); self.data.append(key)
        return self.index[key]

    def blob(self):
        return b''.join(self.data)


def centred_text_x(n, scale=1, width=256):
    return (width - n * 8 * scale) // 2


# ------------------------------------------------------------------ palette 4: banner + icons
BANNER_PAL_NO = 4
BANNER_PAL = [
    (0, 0, 0),   # 0 transparent
    (1, 0, 2),   # 1 banner background (deep purple)
    (7, 7, 3),   # 2 text top (pale yellow)
    (7, 6, 0),   # 3 yellow
    (7, 4, 0),   # 4 orange
    (7, 1, 0),   # 5 red
    (0, 0, 0),   # 6 shadow
    (7, 0, 0),   # 7 stripe red
    (7, 3, 0),   # 8 stripe orange
    (7, 7, 0),   # 9 stripe yellow
    (0, 6, 1),   # 10 stripe green
    (0, 3, 7),   # 11 stripe blue
    (7, 7, 7),   # 12 icon face (white)
    (5, 5, 5),   # 13 pill face (grey)
    (0, 0, 1),   # 14 icon ink
    (3, 0, 4),   # 15 banner edge line
]
STRIPES = [7, 8, 9, 10, 11]


def gradient16(py):  # text gradient for 2x glyph rows (0..13)
    return (2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5)[min(py, 15)]


def banner_canvas(font, title):
    c = Canvas(256, 16, 1)
    # first/last pixel rows stay plain so a 1-line scroll offset never shows garbage
    c.rect(0, 1, 256, 1, 15); c.rect(0, 14, 256, 1, 15)
    n = len(title)
    tx = centred_text_x(n, 2)
    # rainbow racing stripes left and right of the title
    for i, col in enumerate(STRIPES):
        y = 3 + i * 2
        c.rect(0, y, tx - 6, 2, col)
        c.rect(tx + n * 16 + 4, y, 256 - (tx + n * 16 + 4), 2, col)
    c.text(font, title, tx, 1, 2, gradient16, shadow=6)
    c.rect(0, 0, 256, 1, 1); c.rect(0, 15, 256, 1, 1)
    return c


MINI = {  # 3x5 letters for the pill buttons
    'R': ['###', '#.#', '##.', '#.#', '#.#'], 'U': ['#.#', '#.#', '#.#', '#.#', '###'],
    'N': ['##.', '#.#', '#.#', '#.#', '#.#'], 'S': ['###', '#..', '###', '..#', '###'],
    'E': ['###', '#..', '##.', '#..', '###'], 'L': ['#..', '#..', '#..', '#..', '###'],
}


def icon_round(label):
    c = Canvas(8, 8, 0)
    rows = ['..###...', '.#####..', '#######.', '#######.', '#######.', '.#####..', '..###...', '........']
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == '#': c.set(x, y, 12)
    cols = [3] if label == 'I' else [2, 4]
    for x in cols:
        for y in (2, 3, 4): c.set(x, y, 14)
    return c


def icon_pill(word):
    c = Canvas(16, 8, 0)
    c.rect(1, 0, 13, 7, 13); c.rect(0, 1, 15, 5, 13)
    for i, ch in enumerate(word):
        for y, r in enumerate(MINI[ch]):
            for x, b in enumerate(r):
                if b == '#': c.set(2 + i * 4 + x, 1 + y, 14)
    return c


def build_banner(font, enc, title='RETROGAMER POA'):
    """-> dict(tiles, ban_map(64 words: BAT rows 30,31), help_map(32 words), pal, canvas)"""
    ts = TileSet(0x100)
    can = banner_canvas(font, enc(title)[:-1])
    tl = can.tiles()
    ban = [(BANNER_PAL_NO << 12) | ts.add(t) for t in tl]   # 2 rows x 32
    icons = {}
    for lab in ('I', 'II'):
        icons[lab] = [(BANNER_PAL_NO << 12) | ts.add(t) for t in icon_round(lab).tiles()]
    for w in ('RUN', 'SEL'):
        icons[w] = [(BANNER_PAL_NO << 12) | ts.add(t) for t in icon_pill(w).tiles()]
    return ts, ban, icons, can


def help_line(icons, enc, items, text_pal=1, cols=32):
    """items: [(icon, word)] -> 32 BAT words for row 0 (font tiles = $80 + code - $20)."""
    cells = []
    for i, (ic, word) in enumerate(items):
        if i: cells.append(None)
        cells += icons[ic]
        cells += [(text_pal << 12) | (0x80 + ch - 0x20) for ch in enc(word)[:-1]]
    space = 0x80
    pad = (cols - len(cells)) // 2
    row = [space] * pad + [space if c is None else c for c in cells]
    assert len(row) <= cols, 'help line too long: %d' % len(row)
    return row + [space] * (cols - len(row))


# ------------------------------------------------------------------ palette 5: splash
SPLASH_PAL_NO = 5
SPLASH_PAL = [
    (0, 0, 0),   # 0 unused
    (0, 0, 1),   # 1 background
    (7, 7, 7),   # 2 white
    (4, 4, 5),   # 3 grey
    (7, 7, 3),   # 4 pale yellow
    (7, 6, 0),   # 5 yellow
    (7, 4, 0),   # 6 orange
    (7, 1, 0),   # 7 red
    (0, 0, 0),   # 8 shadow
    (0, 6, 1),   # 9 green
    (0, 3, 7),   # 10 blue
    (2, 7, 7),   # 11 cyan
    (2, 2, 4),   # 12 dim star
    (6, 1, 6),   # 13 magenta
    (7, 0, 0),   # 14 stripe red
    (1, 0, 2),   # 15 band background
]


def build_splash(font, enc, lines, title='RETROGAMER', sub='POA'):
    """lines: [(text, colour_index)] drawn small under the logo. -> (TileSet, bat 32x64 words, canvas)"""
    c = Canvas(256, 224, 1)
    import random
    rnd = random.Random(7)
    for _ in range(26):  # a few stars on fixed tile-aligned spots keep the tile count low
        x = rnd.randrange(0, 32) * 8 + rnd.choice((2, 5)); y = rnd.randrange(0, 4) * 8 + rnd.choice((2, 5))
        c.set(x, y, rnd.choice((2, 12, 12)))
    t = enc(title)[:-1]
    grad3 = lambda py: (4, 4, 4, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7)[min(py, 23)]
    c.text(font, t, centred_text_x(len(t), 3) + 4, 40, 3, grad3, shadow=8)
    s = enc(sub)[:-1]
    grad4 = lambda py: (11, 11, 11, 11, 11, 11, 10, 10, 10, 10, 10, 10, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
                        13, 13, 13, 13, 13, 13, 13, 13)[min(py, 31)]
    c.text(font, s, centred_text_x(len(s), 4) + 4, 72, 4, grad4, shadow=8)
    # rainbow band
    c.rect(0, 112, 256, 20, 15)
    for i, col in enumerate((14, 6, 5, 9, 10)):
        c.rect(0, 114 + i * 3, 256, 2, col)
    y = 144
    for text, colr in lines:
        if text:
            e = enc(text)[:-1]
            c.text(font, e, centred_text_x(len(e)), y, 1, colr)
        y += 12
    ts = TileSet(0x200)
    tl = c.tiles()
    # screen row r shows BAT row (r + 30) % 32 because the mod scrolls the BG 16px
    blank = (SPLASH_PAL_NO << 12) | 0x200
    bat = [[blank] * 64 for _ in range(32)]
    for r in range(28):
        for col in range(32):
            bat[(r + 30) % 32][col] = (SPLASH_PAL_NO << 12) | ts.add(tl[r * 32 + col])
    return ts, bat, c
