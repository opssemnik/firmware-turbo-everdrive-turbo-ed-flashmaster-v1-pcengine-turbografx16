"""Build RGPOA.DAT (theme save + game artwork) for the SD card root.

usage: python artpack.py [--keep OLD.DAT] [out_file]
  --keep copies the saved theme, favourites and recents from an existing RGPOA.DAT.

Layout v2 (512-byte sectors, offsets relative to the file start):
  sector 0      header: magic[16] "RGPOA-DAT-v2", theme(1), nbuckets(1), version(1)
  1..8          favourites, 9..10 recents: "RGPOA-SLOT" kind('F'/'R') rel_sector 0 0 0 0,
                then 7 entries x 64 bytes: dir cluster u32 (0 = empty), seq u16, name[58]
  11..10+nb     index buckets: 64 entries x 8 bytes (hashA u16, hashB u16, art sector u32); sector 0 = end
  art blocks    13 sectors each: [magic "RGA1", hashA, hashB, palette 16 x u16] + 6144 bytes of sprites
The cart identifies the selected game by hashing the name shown in the browser's bottom bar.
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artconv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAGIC = b'RGPOA-DAT-v2'.ljust(16, b'\0')
FAV_BASE, FAV_SECTORS, REC_BASE, REC_SECTORS, INDEX_BASE = 1, 8, 9, 2, 11
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


def slot_sector(kind, rel):
    sec = bytearray(512)
    sec[:10] = b'RGPOA-SLOT'; sec[10] = ord(kind); sec[11] = rel
    return sec


def build(sd, out, theme=0, keep=None):
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
    first_art = INDEX_BASE + nb
    blocks = []
    order = sorted(arts, key=arts.get)
    for img in order:
        idx, colors = artconv.convert(img)
        blocks.append((idx, colors))
    sector_of = {img: first_art + i * ART_SECTORS for i, img in enumerate(order)}

    slots = [slot_sector('F', FAV_BASE + i) for i in range(FAV_SECTORS)]
    slots += [slot_sector('R', REC_BASE + i) for i in range(REC_SECTORS)]
    if keep:
        old = open(keep, 'rb').read()
        if old[:12] in (b'RGPOA-DAT-v1', b'RGPOA-DAT-v2'): theme = old[16]
        if old[:12] == b'RGPOA-DAT-v2':
            slots = [bytearray(old[(1 + i) * 512:(2 + i) * 512]) for i in range(len(slots))]
        print('kept from %s: theme %d%s' % (keep, theme, ', favourites + recents' if old[:12] == b'RGPOA-DAT-v2' else ''))
    data = bytearray()
    hdr = bytearray(512); hdr[:16] = MAGIC; hdr[16] = theme; hdr[17] = nb; hdr[18] = 2
    data += hdr
    for sec in slots: data += sec
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
    args = sys.argv[1:]
    keep = None
    if '--keep' in args:
        i = args.index('--keep'); keep = args[i + 1]; del args[i:i + 2]
    out = args[0] if args else os.path.join(ROOT, 'out', 'RGPOA.DAT')
    build(None, out, keep=keep)
