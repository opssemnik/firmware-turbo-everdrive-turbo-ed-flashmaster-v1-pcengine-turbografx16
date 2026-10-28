"""Generate per-theme boot splashes (original pixel art) into themes/splashes/*.png.

usage: python splash_art.py
256x224, at most 15 colours on the PC Engine 512-colour grid. Edit or replace freely.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import build, art
from theme_art import CHIMP, JOY, FONT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'themes', 'splashes')
W, H = 256, 224


def c8(rgb): return tuple(v * 255 // 7 for v in rgb)


class S:
    def __init__(self, bg):
        self.im = Image.new('RGB', (W, H), c8(bg)); self.px = self.im.load()

    def set(self, x, y, col):
        if 0 <= x < W and 0 <= y < H: self.px[x, y] = c8(col)

    def rect(self, x, y, w, h, col):
        for yy in range(y, y + h):
            for xx in range(x, x + w): self.set(xx, yy, col)

    def text(self, s, y, scale, colfn, shadows=(), x=None):
        codes = build.enc(s)[:-1]
        if x is None: x = (W - len(codes) * 8 * scale) // 2
        for dx, dy, col in shadows: self._t(codes, x + dx, y + dy, scale, lambda r: col)
        self._t(codes, x, y, scale, colfn if callable(colfn) else (lambda r: colfn))
        return x

    def _t(self, codes, x, y, scale, colfn):
        for i, ch in enumerate(codes):
            g = FONT[(ch - 32) * 8:(ch - 31) * 8]
            for gy, bits in enumerate(g):
                for gx in range(8):
                    if bits & (0x80 >> gx):
                        for sy in range(scale):
                            for sx in range(scale):
                                self.set(x + i * 8 * scale + gx * scale + sx, y + gy * scale + sy, colfn(gy * scale + sy))

    def sprite(self, rows, x, y, pal, scale=1):
        for yy, r in enumerate(rows):
            for xx, ch in enumerate(r):
                if ch != '.':
                    self.rect(x + xx * scale, y + yy * scale, scale, scale, pal[ch])

    def save(self, name):
        os.makedirs(OUT, exist_ok=True)
        self.im.save(os.path.join(OUT, name + '.png'))


def grad(cols, height):
    return lambda r: cols[min(r * len(cols) // max(1, height), len(cols) - 1)]


# ---------------------------------------------------------------- Retrogamer POA variants (the default layout, recoloured)
def poa_variant(name, pal):
    """Reuse the default splash drawing (art.build_splash) with a different palette."""
    stock = open(os.path.join(ROOT, 'stock', 'tos.pce'), 'rb').read()
    font = stock[0x2000:0x2300] + build.make_glyphs(stock[0x2000:0x2300])
    lines = [('Turbo EverDrive OS', 2), ('PT-BR', 11), ('', 0), ('por Antonio & The Nobre', 5), ('', 0), ('Aperte um botão', 3)]
    _, _, can = art.build_splash(font, build.enc, lines)
    im = Image.new('RGB', (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            px[x, y] = c8(pal[can.p[y][x]])
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, name + '.png'))


#            0 (unused) 1 bg      2 white   3 grey    4 title1  5 title2  6 title3  7 title4  8 shadow  9 band g  10 POA1  11 PT-BR  12 star   13 POA2  14 band r 15 band bg
VARIANTS = {
    'fosforo_verde': [(0,0,0), (0,1,0), (5,7,5), (2,4,2), (5,7,5), (4,7,4), (3,6,3), (2,5,2), (0,0,0), (2,6,2), (4,7,4), (3,7,3), (1,3,1), (2,5,2), (1,4,1), (0,2,0)],
    'ambar':         [(0,0,0), (1,0,0), (7,6,3), (4,3,1), (7,7,3), (7,6,1), (7,4,0), (6,3,0), (0,0,0), (5,3,0), (7,6,2), (7,5,1), (3,2,0), (6,4,0), (7,3,0), (2,1,0)],
    'azul':          [(0,0,0), (0,0,2), (7,7,7), (4,5,6), (7,7,7), (5,6,7), (3,5,7), (2,3,7), (0,0,0), (3,5,7), (7,7,7), (5,6,7), (2,3,5), (4,6,7), (1,2,6), (0,0,3)],
    'brasil':        [(0,0,0), (0,2,0), (7,7,7), (4,6,4), (7,7,3), (7,7,0), (7,6,0), (6,5,0), (0,0,2), (0,5,0), (2,3,7), (7,7,0), (2,4,2), (1,2,6), (7,7,0), (0,3,0)],
    'synthwave':     [(0,0,0), (1,0,2), (7,7,7), (4,3,6), (7,6,1), (7,4,2), (7,2,4), (6,0,5), (0,0,0), (2,7,7), (2,7,7), (6,3,7), (3,2,4), (7,2,6), (7,1,3), (2,0,3)],
    'turbo':         [(0,0,0), (0,0,0), (7,7,7), (4,4,4), (7,7,7), (7,6,4), (7,4,1), (6,2,0), (2,1,0), (7,4,0), (7,7,7), (7,4,0), (3,3,3), (6,2,0), (7,2,0), (1,0,0)],
    'papel':         [(0,0,0), (6,6,6), (1,1,4), (3,3,3), (1,1,5), (1,2,6), (2,2,6), (3,3,6), (5,5,5), (1,1,4), (5,1,0), (1,1,5), (5,5,5), (6,2,0), (1,1,4), (7,7,7)],
}


# ---------------------------------------------------------------- Retrochimp Games (inspired by the group's badge)
INVADER = ['..X.....X..', '...X...X...', '..XXXXXXX..', '.XX.XXX.XX.', 'XXXXXXXXXXX',
           'X.XXXXXXX.X', 'X.X.....X.X', '...XX.XX...']


def retrochimp():
    navy, cream, yel, ora, red, teal = (0, 0, 1), (7, 7, 6), (7, 6, 1), (7, 4, 1), (6, 1, 1), (0, 4, 4)
    s = S(navy)
    cx, cy, R = 128, 66, 58
    bands = [yel, ora, red, teal, ora, yel]
    for y in range(cy - R, cy + R):
        for x in range(cx - R, cx + R):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= (R - 4) ** 2 and y < cy + 10:            # retro sun stripes
                band = (y - (cy - R)) // 9
                if (y - (cy - R)) % 9 < 6: s.set(x, y, bands[band % len(bands)])
            elif (R - 4) ** 2 < d2 <= R ** 2:                  # cream ring
                s.set(x, y, cream)
    pal = {'B': (2, 1, 0), 'F': (5, 4, 2), 'K': (0, 0, 0), 'W': cream, 'T': (4, 2, 1)}
    s.sprite(CHIMP, cx - 24, 30, pal, 3)
    s.text('RETROCHIMP', 128, 3, cream, [(1, 1, teal), (2, 2, red), (3, 3, ora), (4, 4, yel)])
    s.rect(cx - 34, 160, 68, 15, cream)
    s.set(cx - 30, 167, red); s.set(cx + 29, 167, red)
    s.text('GAMES', 164, 1, navy)
    s.sprite(INVADER, 18, 162, {'X': cream}); s.sprite(INVADER, 227, 162, {'X': cream})
    s.text('Games * Consoles', 182, 1, teal)
    s.text('Acessórios * Colecionáveis', 192, 1, teal)
    s.text('Aperte um botão', 210, 1, (4, 4, 4))
    s.save('retrochimp')


# ---------------------------------------------------------------- Maddrugamers
def maddrugamers():
    black, dkg = (0, 0, 0), (0, 2, 0)
    s = S(black)
    import random
    r = random.Random(3)
    for _ in range(40):
        s.set(r.randrange(W), r.randrange(0, 90), dkg)
    jp = {'K': (2, 2, 2), 'G': (4, 4, 4), 'D': (1, 1, 1), 'R': (7, 0, 0)}
    s.sprite(JOY, 128 - 28, 14, jp, 4)
    green = grad([(4, 7, 1), (3, 7, 1), (2, 6, 1), (1, 5, 0)], 16)
    s.text('MADDRUGAMERS', 92, 2, green, [(1, 1, (0, 3, 0)), (2, 2, dkg)])
    s.rect(24, 118, 208, 2, (1, 5, 0))
    s.text('Canal de games retrô', 128, 1, (5, 7, 5))
    s.text('PC Engine * Super Nintendo', 146, 1, (2, 6, 2))
    s.text('Mega Drive * Neo Geo * Atari', 156, 1, (2, 6, 2))
    s.text('youtube.com/@maddrugamers', 176, 1, (7, 7, 7))
    s.text('Aperte um botão', 206, 1, (3, 3, 3))
    s.save('maddrugamers')


if __name__ == '__main__':
    for name, pal in VARIANTS.items(): poa_variant(name, pal)
    retrochimp(); maddrugamers()
    for f in sorted(os.listdir(OUT)):
        im = Image.open(os.path.join(OUT, f)).convert('RGB')
        print(f, len(set(im.getdata())), 'colours')
