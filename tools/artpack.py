"""Build RGPOA.DAT (theme save + game artwork) for the SD card root.

usage: python artpack.py [--keep OLD.DAT] [out_file]
  --keep copies the saved theme, favourites and recents from an existing RGPOA.DAT.

Layout v3 (512-byte sectors, offsets relative to the file start):
  sector 0      header: magic[16] "RGPOA-DAT-v3", theme(1), nbuckets(1), version(1)
  1..8          favourites, 9..10 recents: "RGPOA-SLOT" kind('F'/'R') rel_sector 0 0 0 0,
                then 7 entries x 64 bytes: dir cluster u32 (0 = empty), seq u16, file cluster u32, name[54]
  header byte 19 = number of themes, bytes 20-23 = sector of the theme table (0 = built-in themes)
  theme table   32 bytes per theme: 9 colours (u16, VCE format, slot order of build.SLOTS),
                banner sector u32 (0 = default banner), name[10]
  banner        5 sectors: palette (16 x u16), then 64 tiles (2 rows x 32, 4bpp, VRAM order)
  11..10+nb     index buckets: 64 entries x 8 bytes (hashA u16, hashB u16, art sector u32); sector 0 = end
  art blocks    13 sectors each: [magic "RGA1", hashA, hashB, palette 16 x u16] + 6144 bytes of sprites
The cart identifies the selected game by hashing the name shown in the browser's bottom bar.
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artconv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAGIC = b'RGPOA-DAT-v3'.ljust(16, b'\0')
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


THEMES_JSON = os.path.join(ROOT, 'themes', 'themes.json')
BANNERS = os.path.join(ROOT, 'themes', 'banners')


def banner_block(path):
    """256x16 PNG -> 5 sectors: palette sector + 64 tiles (sequential, palette indices 1-15)."""
    from PIL import Image
    import art
    im = Image.open(path).convert('RGB')
    if im.size != (256, 16): raise SystemExit('%s: banner must be 256x16' % path)
    q = lambda v: min(7, (v * 7 + 127) // 255)
    px = im.load()
    cols, idx = [], [[0] * 256 for _ in range(16)]
    for y in range(16):
        for x in range(256):
            c = tuple(q(v) for v in px[x, y])
            if c not in cols:
                cols.append(c)
                if len(cols) > 15: raise SystemExit('%s: more than 15 colours' % path)
            idx[y][x] = cols.index(c) + 1
    pal = bytearray(512)
    for i, c in enumerate([cols[0]] + cols):
        struct.pack_into('<H', pal, i * 2, vce(c))
    tiles = b''
    for ty in range(2):
        for tx in range(32):
            tiles += art.tile_bytes([idx[ty * 8 + y][tx * 8:tx * 8 + 8] for y in range(8)])
    return bytes(pal) + tiles


def theme_section(first_sector):
    """-> (bytes, count) for themes/themes.json, placed at first_sector."""
    if not os.path.exists(THEMES_JSON): return b'', 0
    themes = json.load(open(THEMES_JSON, encoding='utf-8'))['themes'][:32]
    ntab = -(-len(themes) * 32 // 512)
    table = bytearray(ntab * 512)
    blocks = b''
    for i, t in enumerate(themes):
        c = [t['backdrop'], t['cursor'], t['fundo'], t['arquivo'], t['fundo'], t['pasta'], t['fundo'],
             t['barra_texto'], t['barra_fundo']]
        for k, rgb in enumerate(c): struct.pack_into('<H', table, i * 32 + k * 2, vce(rgb))
        if t.get('banner'):
            struct.pack_into('<I', table, i * 32 + 18, first_sector + ntab + len(blocks) // 512)
            blocks += banner_block(os.path.join(BANNERS, t['banner']))
        table[i * 32 + 22:i * 32 + 32] = t['name'].encode('latin-1', 'replace')[:10].ljust(10, b'\0')
    return bytes(table) + blocks, len(themes)


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
        if old[:11] == b'RGPOA-DAT-v': theme = old[16]
        same = old[:12] == MAGIC[:12]  # slot entries changed format in v3
        if same:
            slots = [bytearray(old[(1 + i) * 512:(2 + i) * 512]) for i in range(len(slots))]
        print('kept from %s: theme %d%s' % (keep, theme, ', favourites + recents' if same else ''))
    data = bytearray()
    hdr = bytearray(512); hdr[:16] = MAGIC; hdr[16] = theme; hdr[17] = nb; hdr[18] = 3
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
    tsec = len(data) // 512
    tdata, tcount = theme_section(tsec)
    if tcount:
        data += tdata
        data[19] = tcount
        struct.pack_into('<I', data, 20, tsec)
        if theme >= tcount: data[16] = 0
        print('themes: %d (%d banners)' % (tcount, (len(tdata) // 512 - (-(-tcount * 32 // 512))) // 5))
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
