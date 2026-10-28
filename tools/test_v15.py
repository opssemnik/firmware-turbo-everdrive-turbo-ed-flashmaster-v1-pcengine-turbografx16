"""v15: LEFT/RIGHT on the game screen move to the previous/next game."""
import sys, os, hashlib, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
txt = lambda m: [l for l in m.text(rows=28).splitlines() if l.split('|', 1)[1].strip('|').strip()]
name = lambda m: m.text(rows=28).splitlines()[3][4:].strip('|')
bar = lambda m: m.text(rows=28).splitlines()[26][4:].strip('|')

def boot():
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    lba0 = inject(sd, b'RGPOA   DAT', open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())
    m = Machine(rom, sd); m.run_frames(650)
    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(100)
    return m, sd, lba0

def flash_hash(m):
    h = hashlib.md5()
    ow = m.write
    def w(a, v):
        if 0x40 <= m.mpr[a >> 13] < 0xf8: h.update(bytes([m.mpr[a >> 13], (a >> 8) & 0xff, a & 0xff, v]))
        ow(a, v)
    m.write = w
    return h

def load_now(m):
    h = flash_hash(m)
    m.pad = 8; m.run_frames(4); m.pad = 0; m.run_frames(400)
    return h.hexdigest()

m, sd, lba0 = boot()
for k in ['DOWN'] * 3: m.press(k, 2, 4)
m.press('RUN', 3, 60)
print('start:', name(m), '| cover', m.ram[0x42])
m.press('RIGHT', 2, 40); print('RIGHT ->', name(m), '| cover', m.ram[0x42], '| index', m.ram[0x1ff6])
for i in range(17): m.press('RIGHT', 2, 30)
print('17 more ->', name(m), '| index', m.ram[0x1ff6], 'page start', m.ram[0x1ff3])
m.press('LEFT', 2, 40); print('LEFT ->', name(m), '| index', m.ram[0x1ff6])
target = name(m); idx = m.ram[0x1ff6]
m.press('DOWN', 2, 10); m.press('RUN', 3, 60)
d = sd.block(lba0 + 1)
fav = [d[16 + e * 64 + 10:16 + e * 64 + 64].split(b'\0')[0].decode('latin-1') for e in range(7) if struct.unpack_from('<I', d, 16 + e * 64)[0]]
print('favourited:', fav)
m.press('I', 3, 90)
print('Voltar -> bar:', bar(m), '| page:', txt(m)[2:3])
m.press('DOWN', 2, 20); print('DOWN in browser ->', bar(m))

m1, _, _ = boot()                      # load via the game screen after navigating
for k in ['DOWN'] * 3: m1.press(k, 2, 4)
m1.press('RUN', 3, 60)
for i in range(idx - 3):
    m1.press('RIGHT', 2, 30)
print('navigated to', name(m1))
a = load_now(m1)
m2, _, _ = boot()                      # the same game straight from the list
for i in range(idx // 20): m2.press('RIGHT', 2, 40)
for i in range(idx % 20): m2.press('DOWN', 2, 4)
print('list cursor on', bar(m2))
m2.press('RUN', 3, 60)
b = load_now(m2)
print('same flash writes:', a == b)

r, _, _ = boot()                       # root: LEFT from the first file must not reach a folder
r.press('I', 3, 120)
rows = r.text(rows=28).splitlines()
i240 = [i for i, l in enumerate(rows) if '240pSuite' in l][0] - 5
for k in ['DOWN'] * i240: r.press(k, 2, 4)
r.press('RUN', 3, 60); before = name(r)
r.press('LEFT', 2, 40); print('root: LEFT from', before, '->', name(r))
