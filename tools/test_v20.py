"""v20: menu music (PSG, vsync hook), Menu > Música on/off saved in RGPOA.DAT byte 26."""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
screen = lambda m: m.text(rows=28)
fails = []
def check(what, ok):
    print(('ok   ' if ok else 'FAIL ') + what)
    if not ok: fails.append(what)

def boot(music_off=0):
    dat = bytearray(open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())
    dat[26] = music_off
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    lba0 = inject(sd, b'RGPOA   DAT', bytes(dat))
    m = Machine(rom, sd); m.psg_log = []
    m.run_frames(650)
    return m, sd, lba0

def sounding(m, frames=60):
    """-> number of PSG control writes with a volume (> 0) during `frames` frames"""
    m.psg_log.clear(); m.run_frames(frames)
    return sum(1 for _, r, v in m.psg_log if r == 4 and v & 0x80 and v & 31)

def music_on(m): return bool(m.ram[0xf5] & 0x10)

m, sd, lba0 = boot()
check('boot: music on, hook installed', music_on(m) and (m.ram[0x208] | m.ram[0x209] << 8) == 0xff63)
check('browser root: playing', sounding(m) > 100)
for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
m.run_frames(100)
for k in ['DOWN'] * 5: m.press(k, 2, 4)
check('folder: playing', sounding(m) > 100)
m.press('RUN', 3, 60)
check('game screen: playing', sounding(m) > 100)
m.press('I', 3, 90); m.press('I', 3, 120)
m.press('I', 3, 60)
t = screen(m)
check('menu shows "Música: Ligada"', 'sica: Ligada' in t)
check('menu: playing', sounding(m) > 100)
for _ in range(5): m.press('DOWN', 2, 10)
m.press('RUN', 3, 60)
t = screen(m)
check('switch off: label, hook bit, DAT byte 26 = 1', 'sica: Desligada' in t and not music_on(m) and sd.block(lba0)[26] == 1)
check('switch off: silent', sounding(m) == 0)
m.press('RUN', 3, 60)
check('switch on again: playing, DAT byte 26 = 0', music_on(m) and sounding(m) > 100 and sd.block(lba0)[26] == 0)
m.press('UP', 2, 10); m.press('UP', 2, 10); m.press('UP', 2, 10)   # Buscar
m.press('RUN', 3, 60)
check('search keyboard: playing', 'Buscar jogo' in screen(m) and sounding(m) > 100)

q, _, _ = boot(music_off=1)
check('boot with music off: silent', not music_on(q) and sounding(q) == 0)

def load(m):
    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(100)
    for k in ['DOWN'] * 5: m.press(k, 2, 4)
    m.press('RUN', 3, 60)
    h = hashlib.md5()
    ow = m.write
    first = []
    def w(a, v):
        b = m.mpr[a >> 13]
        if 0x40 <= b < 0xf8:
            if not first: first.append((music_on(m), len(m.psg_log)))
            h.update(bytes([b, (a >> 8) & 0xff, a & 0xff, v]))
        ow(a, v)
    m.write = w
    m.psg_log.clear()
    m.pad = 8; m.run_frames(4); m.pad = 0; m.run_frames(400)
    return h.hexdigest(), first[0] if first else None, m

a, (mus_at_flash, _), _ = load(boot()[0])
check('loading: music stopped before the first flash write', not mus_at_flash)
b, _, _ = load(boot(music_off=1)[0])
check('same flash writes with and without music', a == b)

print('\n%d falhas' % len(fails))
sys.exit(1 if fails else 0)
