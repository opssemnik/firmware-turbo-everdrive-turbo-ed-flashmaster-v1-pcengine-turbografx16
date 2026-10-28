"""Match the ROMs on the SD card to libretro-thumbnails artwork and download it.

usage: python scrape.py [rom_dir ...] [--no-download]
Default dirs: sdcard/ and GAMES_PCENGINE/. Handles .pce (PC Engine / TurboGrafx-16)
and .sgx (SuperGrafx). Matching: CRC32 -> No-Intro name (libretro-database dat), then
the thumbnail of that name; otherwise a fuzzy title match (hacks, translations, sound
tests). Results: art_cache/matches.json (keyed by file name), images in art_cache/img/.
Downloaded art is copyrighted: it stays in art_cache/ (git-ignored).
"""
import difflib, json, os, re, sys, urllib.parse, urllib.request, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'art_cache')
KINDS = ('Named_Boxarts', 'Named_Titles', 'Named_Snaps')  # preference order
SYSTEMS = {  # extension -> (dat, tree json, thumbnail repo)
    '.pce': ('nointro.dat', 'tree.json', 'NEC_-_PC_Engine_-_TurboGrafx_16'),
    '.sgx': ('nointro_sgx.dat', 'tree_sgx.json', 'NEC_-_PC_Engine_SuperGrafx'),
}
RAW = 'https://raw.githubusercontent.com/libretro-thumbnails/%s/master/%s/%s'


def load_dat(path):
    crc = {}
    name = None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\tname "(.*)"', line)
        if m: name = m.group(1)
        m = re.search(r'crc ([0-9A-F]{8})', line)
        if m and name: crc[int(m.group(1), 16)] = name
    return crc


def load_thumbs(path):
    t = json.load(open(path, encoding='utf-8'))
    have = {k: set() for k in KINDS}
    for e in t['tree']:
        parts = e['path'].split('/')
        if e['type'] == 'blob' and parts[0] in have and parts[1].endswith('.png'):
            have[parts[0]].add(parts[1][:-4])
    return have


def rom_crc(path):
    d = open(path, 'rb').read()
    if len(d) % 8192 == 512: d = d[512:]  # copier header
    return zlib.crc32(d) & 0xffffffff


def norm(s):
    s = re.sub(r'(?i)\.(pce|sgx)$', '', s)
    s = re.sub(r'^\d{2,4}[\s\-._]+(?=\D)', '', s)          # "026 Zipang"
    s = re.sub(r'[\(\[][^\)\]]*[\)\]]', ' ', s)          # tags
    s = re.sub(r'(?i)\b(hack|by|translated|eng|ver|v\d.*)\b.*$', ' ', s)
    s = s.replace('&', 'and')
    s = re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
    s = re.sub(r'^the ', '', s)
    return s


def variants(f):
    """Title keys to try for a file name, most specific first."""
    base = re.sub(r'(?i)\s*sounds?(?=\.(pce|sgx)$)', '', f)
    k = norm(base); out = [k]
    t = re.sub(r'^\d{2,4}[\s\-._]+(?=\D)', '', base)
    t = re.sub(r'[\(\[].*$', '', t)
    if ' - ' in t:
        out += [norm(t.split(' - ')[0]), norm(t.split(' - ', 1)[1])]
    words = k.split()
    if len(words) > 2: out.append(' '.join(words[:2]))
    return [v for v in dict.fromkeys(out) if len(v) >= 4]


def thumb_name(n):  # libretro replaces these characters in file names
    return re.sub(r'[&*/:`<>?\\|"]', '_', n)


class System:
    def __init__(self, ext):
        dat, tree, self.repo = SYSTEMS[ext]
        self.crc = load_dat(os.path.join(CACHE, dat))
        self.have = load_thumbs(os.path.join(CACHE, tree))
        names = sorted(set().union(*self.have.values()))
        self.by_norm = {}
        for n in names: self.by_norm.setdefault(norm(n), []).append(n)
        self.keys = list(self.by_norm)

    def pick(self, name):
        for k in KINDS:
            if thumb_name(name) in self.have[k]: return k, thumb_name(name)
        return None

    def first_with_art(self, cands):
        for c in cands:
            r = self.pick(c)
            if r: return r
        return None


def region_rank(n, fname):
    jp = re.search(r'\(J|Japan', fname) is not None
    if jp: return 0 if 'Japan' in n else 1
    return 0 if 'USA' in n else 1


def match_file(systems, path, f):
    ext = os.path.splitext(f)[1].lower()
    order = [systems[ext]] + [s for e, s in systems.items() if e != ext]
    nm = systems[ext].crc.get(rom_crc(path))
    if nm:
        for sysm in order:
            res = sysm.pick(nm) or sysm.first_with_art(
                sorted(sysm.by_norm.get(norm(nm), []), key=lambda n: region_rank(n, nm)))
            if res: return sysm, res, 'crc'
    for key in variants(f):
        for sysm in order:
            best = difflib.get_close_matches(key, sysm.keys, n=1, cutoff=0.82)
            if best:
                res = sysm.first_with_art(sorted(sysm.by_norm[best[0]], key=lambda n: region_rank(n, f)))
                if res: return sysm, res, 'fuzzy'
    return None, None, None


def img_path(repo, kind, thumb):
    short = 'sgx' if 'SuperGrafx' in repo else 'pce'
    return 'img/%s__%s__%s.png' % (short, kind, thumb)   # relative to art_cache/


def main(dirs):
    systems = {e: System(e) for e in SYSTEMS}
    matches = {}
    stats = {'crc': 0, 'fuzzy': 0, 'none': 0, 'dup': 0}
    for sd in dirs:
        for dp, dn, fn in os.walk(sd):
            for f in sorted(fn):
                if os.path.splitext(f)[1].lower() not in SYSTEMS or f.upper() == 'TOS.PCE': continue
                if f in matches: stats['dup'] += 1; continue   # the cart identifies games by name
                sysm, res, how = match_file(systems, os.path.join(dp, f), f)
                if res:
                    stats[how] += 1
                    matches[f] = {'file': f, 'repo': sysm.repo, 'kind': res[0], 'thumb': res[1], 'how': how,
                                  'img': img_path(sysm.repo, res[0], res[1])}
                else:
                    stats['none'] += 1
    json.dump(matches, open(os.path.join(CACHE, 'matches.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('names: crc %(crc)d, fuzzy %(fuzzy)d, no art %(none)d (duplicate names skipped: %(dup)d)' % stats)
    return matches


def download(matches):
    os.makedirs(os.path.join(CACHE, 'img'), exist_ok=True)
    todo = {(m['repo'], m['kind'], m['thumb'], m['img']) for m in matches.values()}
    n = 0
    for repo, kind, thumb, rel in sorted(todo):
        dst = os.path.join(CACHE, rel)
        if os.path.exists(dst): continue
        old = os.path.join(CACHE, 'img', kind + '__' + thumb + '.png')  # earlier cache layout
        if 'SuperGrafx' not in repo and os.path.exists(old):
            os.replace(old, dst); continue
        try:
            data = urllib.request.urlopen(RAW % (repo, kind, urllib.parse.quote(thumb + '.png')), timeout=30).read()
            open(dst, 'wb').write(data); n += 1
        except Exception as e:
            print('fail', thumb, e)
    print('downloaded %d new images (%d unique)' % (n, len(todo)))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dirs = args or [os.path.join(ROOT, 'sdcard'), os.path.join(ROOT, 'GAMES_PCENGINE')]
    m = main(dirs)
    if '--no-download' not in sys.argv: download(m)
