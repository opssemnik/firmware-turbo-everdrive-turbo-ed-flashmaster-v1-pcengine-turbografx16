"""v18: language selector (Menu > Idioma / Language), saved in RGPOA.DAT byte 24."""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
import build
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
screen = lambda m: m.text(rows=28)
fails = []
def check(what, ok):
    print(('ok   ' if ok else 'FAIL ') + what)
    if not ok: fails.append(what)

def boot(lang=0, theme=None):
    dat = bytearray(open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())
    dat[24] = lang
    if theme is not None: dat[16] = theme
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    lba0 = inject(sd, b'RGPOA   DAT', bytes(dat))
    m = Machine(rom, sd)
    splash = 0
    for f in range(650):
        m.run_frames(1)
        if sum(1 for r in range(32) for c in range(32) if m.vram[r * 64 + c] >> 12 == 5) > 500: splash += 1
    return m, sd, lba0, splash

def flash_hash(m):
    h = hashlib.md5()
    ow = m.write
    def w(a, v):
        if 0x40 <= m.mpr[a >> 13] < 0xf8: h.update(bytes([m.mpr[a >> 13], (a >> 8) & 0xff, a & 0xff, v]))
        ow(a, v)
    m.write = w
    return h

def load_game(m):
    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(100)
    for k in ['DOWN'] * 5: m.press(k, 2, 4)
    m.press('RUN', 3, 60)
    game = screen(m)
    h = flash_hash(m)
    m.pad = 8; m.run_frames(4); m.pad = 0
    loading = ''
    for _ in range(40):
        m.run_frames(10)
        t = screen(m)
        if 'Load' in t or 'Carreg' in t: loading = t
    m.run_frames(200)
    return game, loading, h.hexdigest()

# Portuguese (default): menu has the new option
m, sd, lba0, spl = boot()
check('PT: MPR2 = bank 3', m.mpr[2] == 3)
check('PT: help line', 'Abrir' in screen(m) and 'Tema' in screen(m))
m.press('I', 3, 60)
check('PT: menu has "Idioma"', 'Idioma: Portugu' in screen(m))
for _ in range(4): m.press('DOWN', 2, 10)
m.press('RUN', 3, 90)
t = screen(m)
check('switch: menu now English', 'Language: English' in t and 'Favorites' in t and 'Search' in t)
check('switch: MPR2 = bank 14', m.mpr[2] == 14)
s0 = sd.block(lba0)
check('switch: DAT byte 24 = 1, header intact', s0[24] == 1 and s0[:12] == b'RGPOA-DAT-v3')
m.press('UP', 2, 10)                     # Sobre / About
m.press('RUN', 3, 90)
t = screen(m)
check('EN about: version + labels', 'OS Version   : EN v%d' % build.MOD_VERSION in t and 'Assembly Date' in t and 'by Antonio' in t)
print('\n'.join(l for l in t.splitlines() if l.strip('| 0123456789')))
m.press('I', 3, 60)                      # about -> menu
m.press('I', 3, 90)                      # menu -> browser
t = screen(m)
check('EN browser: help line + page', 'Open' in t and 'Theme' in t and 'Page:' in t)
m.press('I', 3, 60)                      # menu, cursor on Favorites
for _ in range(2): m.press('DOWN', 2, 10)
m.press('RUN', 3, 60)
check('EN search screen', 'Search game' in screen(m) and 'Space' in screen(m))
m.press('I', 3, 60)                      # search -> menu
for _ in range(2): m.press('DOWN', 2, 10)   # the cursor stays on Search: down to Language
m.press('RUN', 3, 90)
check('switch back: Portuguese, byte 24 = 0', 'Idioma: Portugu' in screen(m) and sd.block(lba0)[24] == 0 and m.mpr[2] == 3)

# English saved: boots in English; loading writes the same flash data as Portuguese
e, _, _, spl_e = boot(lang=1)
check('EN boot: MPR2 = bank 14, help line', e.mpr[2] == 14 and 'Open' in screen(e))
check('EN boot: splash shown (%d frames)' % spl_e, spl_e > 100)
import struct
dat = open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read()
tt = struct.unpack_from('<I', dat, 20)[0] * 512 + 32       # theme 1 (Retrochimp Games)
for lang, off in ((0, 22), (1, 26)):
    t1, _, _, spl1 = boot(lang=lang, theme=1)
    sec = struct.unpack_from('<I', bytes(t1.ram[0x58:0x5c]))[0]
    check('theme 1 lang %d: splash sector %d (table %d), shown %d frames'
          % (lang, sec, struct.unpack_from('<I', dat, tt + off)[0], spl1),
          sec == struct.unpack_from('<I', dat, tt + off)[0] and spl1 > 100)
game_e, loading_e, he = load_game(e)
check('EN game screen', 'Load' in game_e and 'Add to favorites' in game_e)
check('EN loading screen', 'Loading...' in loading_e)
p, _, _, _ = boot(lang=0)
game_p, loading_p, hp = load_game(p)
check('PT game screen', 'Carregar' in game_p)
check('same flash writes PT/EN', he == hp)

print('\n%d falhas' % len(fails))
sys.exit(1 if fails else 0)
