"""Generate the example theme banners (original pixel art) into themes/banners/*.png.

usage: python theme_art.py
The PNGs are 256x16 and use at most 15 colours on the PC Engine's 512-colour grid, so
artpack.py converts them losslessly. Edit them in any image editor, or replace them.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'themes', 'banners')
W, H = 256, 16

stock = open(os.path.join(ROOT, 'stock', 'tos.pce'), 'rb').read()
FONT = stock[0x2000:0x2300] + build.make_glyphs(stock[0x2000:0x2300])


def c8(rgb):  # 0-7 -> 0-255
    return tuple(v * 255 // 7 for v in rgb)


class B:
    def __init__(self, bg):
        self.im = Image.new('RGB', (W, H), c8(bg))
        self.px = self.im.load()

    def set(self, x, y, col):
        if 0 <= x < W and 0 <= y < H: self.px[x, y] = c8(col)

    def rect(self, x, y, w, h, col):
        for yy in range(y, y + h):
            for xx in range(x, x + w): self.set(xx, yy, col)

    def text(self, s, x, y, scale, colfn, shadows=(), adv=8):
        """colfn(row) -> colour; shadows: [(dx, dy, colour)] drawn first."""
        codes = build.enc(s)[:-1]
        for dx, dy, col in shadows:
            self._text(codes, x + dx, y + dy, scale, lambda r: col, adv)
        self._text(codes, x, y, scale, colfn, adv)

    def _text(self, codes, x, y, scale, colfn, adv):
        for i, ch in enumerate(codes):
            g = FONT[(ch - 32) * 8:(ch - 31) * 8]
            for gy, bits in enumerate(g):
                for gx in range(8):
                    if bits & (0x80 >> gx):
                        for sy in range(scale):
                            for sx in range(scale):
                                self.set(x + i * adv * scale + gx * scale + sx, y + gy * scale + sy, colfn(gy * scale + sy))

    def sprite(self, rows, x, y, pal):
        for yy, r in enumerate(rows):
            for xx, ch in enumerate(r):
                if ch != '.': self.set(x + xx, y + yy, pal[ch])

    def save(self, name):
        os.makedirs(OUT, exist_ok=True)
        self.im.save(os.path.join(OUT, name + '.png'))


def width(s, scale=2): return len(build.enc(s)[:-1]) * 8 * scale


def grad(cols):
    return lambda r: cols[min(r * len(cols) // 14, len(cols) - 1)]


TITLE = 'RETROGAMER POA'


def fosforo():
    b = B((0, 1, 0))
    x = (W - width(TITLE)) // 2
    b.text(TITLE, x, 1, 2, lambda r: (2, 7, 2) if r % 2 == 0 else (1, 5, 1), [(1, 1, (0, 2, 0))])
    for y in range(1, 15, 2): b.rect(0, y, x - 6, 1, (0, 2, 0)); b.rect(x + width(TITLE) + 6, y, W, 1, (0, 2, 0))
    b.rect(0, 0, W, 1, (0, 1, 0)); b.rect(0, 15, W, 1, (0, 1, 0))
    b.save('fosforo_verde')


def ambar():
    b = B((1, 0, 0))
    x = (W - width(TITLE)) // 2
    b.text(TITLE, x, 1, 2, lambda r: (7, 6, 1) if r % 2 == 0 else (6, 4, 0), [(1, 1, (2, 1, 0))])
    for y in range(1, 15, 2): b.rect(0, y, x - 6, 1, (2, 1, 0)); b.rect(x + width(TITLE) + 6, y, W, 1, (2, 1, 0))
    b.save('ambar')


def azul():
    b = B((0, 0, 2))
    x = (W - width(TITLE)) // 2
    b.text(TITLE, x, 1, 2, grad([(7, 7, 7), (5, 6, 7), (3, 5, 7), (2, 3, 7)]), [(1, 1, (0, 0, 0))])
    for sx, sy, c in [(6, 3, (7, 7, 7)), (14, 9, (4, 5, 7)), (24, 5, (7, 7, 7)), (230, 4, (7, 7, 7)), (240, 10, (4, 5, 7)), (250, 6, (7, 7, 7))]:
        b.set(sx, sy, c); b.set(sx - 1, sy, c); b.set(sx + 1, sy, c); b.set(sx, sy - 1, c); b.set(sx, sy + 1, c)
    b.save('azul')


def brasil():
    b = B((0, 3, 0))
    x = (W - width(TITLE)) // 2
    b.text(TITLE, x, 1, 2, lambda r: (7, 7, 0), [(1, 1, (0, 0, 4)), (2, 1, (0, 0, 4))])
    diamond = ['.......Y.......', '.....YYYYY.....', '...YYYBBBYYY...', '.YYYBBBWBBBYYY.',
               '...YYYBBBYYY...', '.....YYYYY.....', '.......Y.......']
    pal = {'Y': (7, 7, 0), 'B': (0, 1, 5), 'W': (7, 7, 7)}
    b.sprite(diamond, 4, 4, pal); b.sprite(diamond, W - 19, 4, pal)
    b.save('brasil')


def synthwave():
    b = B((1, 0, 2))
    x = (W - width(TITLE)) // 2
    b.text(TITLE, x, 1, 2, grad([(7, 3, 7), (6, 2, 7), (3, 4, 7), (2, 7, 7)]), [(1, 1, (3, 0, 4))])
    for i, (y, col) in enumerate([(3, (7, 6, 0)), (6, (7, 4, 1)), (9, (7, 2, 3)), (12, (6, 0, 5))]):
        b.rect(2, y, x - 8, 2, col); b.rect(x + width(TITLE) + 6, y, W, 2, col)
    b.save('synthwave')


def turbo():
    b = B((0, 0, 0))
    x = (W - width(TITLE)) // 2
    b.text(TITLE, x, 1, 2, lambda r: (7, 7, 7), [(1, 1, (6, 2, 0)), (2, 2, (4, 1, 0))])
    for i in range(0, x - 8, 6):
        for y in range(2, 14): b.set(i + (y // 2), y, (6, 2, 0)); b.set(i + 1 + (y // 2), y, (6, 2, 0))
    for i in range(x + width(TITLE) + 6, W, 6):
        for y in range(2, 14): b.set(i + (y // 2), y, (6, 2, 0)); b.set(i + 1 + (y // 2), y, (6, 2, 0))
    b.save('turbo')


def papel():
    b = B((6, 6, 6))
    x = (W - width(TITLE)) // 2
    b.text(TITLE, x, 1, 2, lambda r: (1, 1, 4), [(1, 1, (4, 4, 4))])
    b.rect(0, 1, W, 1, (1, 1, 4)); b.rect(0, 14, W, 1, (1, 1, 4))
    b.save('papel')


CHIMP = [  # original 16x15 chimp head
    '....BBBBBBBB....',
    '..BBBBBBBBBBBB..',
    '.BBBBBBBBBBBBBB.',
    'BBBFFFFBBFFFFBBB',
    'TTBFKKFFFFKKFBTT',
    'TTBFKWFFFFKWFBTT',
    'TTBFFFFFFFFFFBTT',
    '.BBFFFFKKFFFFBB.',
    '..BFFFFFFFFFFB..',
    '..BFFKKKKKKFFB..',
    '...FFKWWWWKFF...',
    '...FFFKKKKFFF...',
    '....FFFFFFFF....',
    '.....FFFFFF.....',
    '................',
]


def retrochimp():
    b = B((0, 0, 1))
    pal = {'B': (2, 1, 0), 'F': (5, 4, 2), 'K': (0, 0, 0), 'W': (7, 7, 6), 'T': (4, 2, 1)}
    word = 'RETROCHIMP'
    tw = width(word)
    small = 'GAMES'
    total = 16 + 6 + tw + 6 + width(small, 1)
    x0 = (W - total) // 2
    b.sprite(CHIMP, x0, 1, pal)
    x = x0 + 22
    b.text(word, x, 1, 2, lambda r: (7, 7, 6), [(1, 1, (0, 4, 4)), (2, 2, (6, 1, 1)), (3, 3, (7, 4, 1))])
    b.rect(x + tw + 4, 4, width(small, 1) + 4, 9, (7, 7, 6))
    b.text(small, x + tw + 6, 5, 1, lambda r: (0, 0, 1))
    for i, col in enumerate([(7, 6, 1), (7, 4, 1), (6, 1, 1), (0, 4, 4)]):
        b.rect(0, 3 + i * 3, x0 - 4, 2, col); b.rect(x + tw + width(small, 1) + 14, 3 + i * 3, W, 2, col)
    b.rect(0, 0, W, 1, (0, 0, 1)); b.rect(0, 15, W, 1, (0, 0, 1))
    b.save('retrochimp')


JOY = [  # original Atari-style joystick, 14x15
    '......KK......',
    '.....KGGK.....',
    '.....KGGK.....',
    '.....KGGK.....',
    '.....KGGK.....',
    '.....KGGK.....',
    '..KKKKGGKKKK..',
    '.KDDDDDDDDDDK.',
    'KDRRDDDDDDDDDK',
    'KDRRDDDDDDDDDK',
    'KDDDDDDDDDDDDK',
    'KDDDDDDDDDDDDK',
    '.KDDDDDDDDDDK.',
    '..KKKKKKKKKK..',
    '..............',
]


def maddrugamers():
    b = B((0, 0, 0))
    pal = {'K': (2, 2, 2), 'G': (4, 4, 4), 'D': (1, 1, 1), 'R': (7, 0, 0)}
    word = 'MADDRUGAMERS'
    tw = width(word)
    total = 14 + 8 + tw + 8 + 14
    x0 = (W - total) // 2
    b.sprite(JOY, x0, 1, pal)
    b.sprite(JOY, x0 + 14 + 8 + tw + 8, 1, pal)
    b.text(word, x0 + 22, 1, 2, grad([(4, 7, 1), (2, 7, 1), (1, 6, 1), (1, 5, 0)]), [(1, 1, (0, 3, 0)), (2, 2, (0, 2, 0))])
    b.save('maddrugamers')


if __name__ == '__main__':
    for f in (fosforo, ambar, azul, brasil, synthwave, turbo, papel, retrochimp, maddrugamers):
        f()
    print('banners in', OUT)
