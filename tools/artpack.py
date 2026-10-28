"""Build RGPOA.DAT (theme save + game artwork) for the SD card root.

usage: python artpack.py [sdcard_dir] [out_file]

Layout (512-byte sectors, offsets relative to the file start):
  sector 0      header: magic[16] "RGPOA-DAT-v1", theme(1), nbuckets(1), reserved
  1..nb         index buckets: 64 entries x 8 bytes (hashA u16, hashB u16, art sector u32); sector 0 = end
  art blocks    13 sectors each: [magic "RGA1", hashA, hashB, palette 16 x u16] + 6144 bytes of sprites
The cart identifies the selected game by hashing the name shown in the browser's bottom bar.
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artconv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAGIC = b'RGPOA-DAT-v1'.ljust(16, b'\0')
ART_MAGIC = b'RGA1'
ART_SECTORS = 13
BAR_CHARS = 60  # the bottom bar shows 2 x 30 characters


def name_hash(fname):
    """Same as the cart: low byte of each UTF-16 unit, first 60, printable ASCII except
    '.', case-folded; A += c, B += A (16-bit)."""
    units = fname.encode('utf-16-le')
    a = b = 0
    for i in range(0, min(len(units), BAR_CHARS * 2), 2):
        c = units[i]
        if 0x21 <= c <= 0x7e and c != 0x2e:
            if 0x61 <= c <= 0x7a: c -= 0x20
            a = (a + c) & 0xffff
            b = (b + a) & 0xffff
    return a, b


def vce(rgb):
    r, g, b = rgb
    return (g << 6) | (r << 3) | b


def build(sd, out, theme=0):
    matches = json.load(open(os.path.join(ROOT, 'art_cache', 'matches.json'), encoding='utf-8'))
    arts = {}      # image -> block index
    entries = {}   # hash -> image
    for rel, m in sorted(matches.items()):
        img = os.path.join(ROOT, 'art_cache', m['img'])
        if not os.path.exists(img): continue
        h = name_hash(m['file'])
        if h == (0, 0): continue
        if h in entries and entries[h] != img:
            print('hash collision, skipped:', m['file'])
            continue
        entries[h] = img
        arts.setdefault(img, len(arts))
    nb = 1
    while True:
        buckets = [[] for _ in range(nb)]
        for h in entries: buckets[(h[0] ^ h[1]) & 0xff & (nb - 1)].append(h)
        if max(len(b) for b in buckets) <= 63 or nb == 128: break
        nb *= 2
    if max(len(b) for b in buckets) > 63: raise SystemExit('too many games for the index')
    first_art = 1 + nb
    blocks = []
    order = sorted(arts, key=arts.get)
    for img in order:
        idx, colors = artconv.convert(img)
        blocks.append((idx, colors))
    sector_of = {img: first_art + i * ART_SECTORS for i, img in enumerate(order)}

    data = bytearray()
    hdr = bytearray(512); hdr[:16] = MAGIC; hdr[16] = theme; hdr[17] = nb; hdr[18] = 1
    data += hdr
    for b in buckets:
        sec = bytearray(512)
        for i, h in enumerate(b):
            struct.pack_into('<HHI', sec, i * 8, h[0], h[1], sector_of[entries[h]])
        data += sec
    for img, (idx, colors) in zip(order, blocks):
        # one header per image; every hash that points here is accepted by the cart
        hdr = bytearray(512)
        hdr[:4] = ART_MAGIC
        for i, c in enumerate(colors): struct.pack_into('<H', hdr, 8 + i * 2, vce(c))
        data += hdr + artconv.sprite_cells(idx)
    open(out, 'wb').write(data)
    print('%s: %d games, %d images, %d index sectors, %.1f MB'
          % (out, len(entries), len(order), nb, len(data) / 1e6))
    return entries, sector_of


if __name__ == '__main__':
    sd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'sdcard')
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'out', 'RGPOA.DAT')
    build(sd, out)
