"""Convert artwork to a 96x128 PC Engine sprite panel (15 colours + transparent)."""
from PIL import Image

W, H = 96, 128


def to9(c):  # 8-bit channel -> 0..7
    return min(7, (c * 7 + 127) // 255)


def convert(path, dither=True):
    """-> (indices[H][W], palette list of 16 (r,g,b) 0-7 tuples; index 0 = transparent)"""
    im = Image.open(path).convert('RGB')
    im.thumbnail((W - 2, H - 2), Image.LANCZOS)
    # snap to the 512-colour space before choosing the palette
    im = im.point(lambda c: to9(c) * 255 // 7)
    q = im.quantize(colors=14, method=Image.Quantize.MEDIANCUT,
                    dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)
    pal = q.getpalette()[:14 * 3]
    colors = [(0, 0, 0)] + [(to9(pal[i]), to9(pal[i + 1]), to9(pal[i + 2])) for i in range(0, 42, 3)]
    colors += [(0, 0, 0)] * (15 - len(colors))
    frame = (5, 5, 5)
    colors.append(frame)  # 15 = frame
    idx = [[0] * W for _ in range(H)]
    ox = (W - q.width) // 2; oy = (H - q.height) // 2
    qp = q.load()
    for y in range(q.height):
        for x in range(q.width):
            idx[oy + y][ox + x] = qp[x, y] + 1
    for x in range(ox - 1, ox + q.width + 1):
        idx[oy - 1][x] = 15; idx[oy + q.height][x] = 15
    for y in range(oy - 1, oy + q.height + 1):
        idx[y][ox - 1] = 15; idx[y][ox + q.width] = 15
    return idx, colors


def sprite_cells(idx):
    """Sprite pattern data for 3x2 sprites of 32x64 (each = 2x4 cells of 16x16).
    Returns bytes in VRAM order: sprite s (col-major: s = row*3 + col), cells laid out as the
    VDC expects for a 32x64 sprite: cell n at +n*64 words, n = cy*2 + cx."""
    out = bytearray()
    for sr in range(2):
        for sc in range(3):
            for cy in range(4):
                for cx in range(2):
                    x0 = sc * 32 + cx * 16; y0 = sr * 64 + cy * 16
                    for plane in range(4):
                        for y in range(16):
                            w = 0
                            for x in range(16):
                                if (idx[y0 + y][x0 + x] >> plane) & 1: w |= 0x8000 >> x
                            out += bytes([w & 0xff, w >> 8])
    return bytes(out)


def preview(idx, colors, path, scale=3):
    im = Image.new('RGB', (W, H), (40, 40, 40))
    px = im.load()
    for y in range(H):
        for x in range(W):
            c = idx[y][x]
            if c: r, g, b = colors[c]; px[x, y] = (r * 255 // 7, g * 255 // 7, b * 255 // 7)
    im.resize((W * scale, H * scale), Image.NEAREST).save(path)
