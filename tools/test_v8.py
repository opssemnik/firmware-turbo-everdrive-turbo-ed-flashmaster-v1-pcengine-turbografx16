"""v8: menu at the root (I), favourites/recents lists, go to a game."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
lba0 = inject(sd, b'RGPOA   DAT', open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())

def fresh():
    sd.q = []; sd.cmd = []; sd.stream = None; sd.wr_state = None; sd.idle = True; sd.a41 = 0; sd.acmd = False
    return sd

def txt(m, a=0, b=28):
    return [l for l in m.text(rows=28).splitlines()[a:b] if l.split('|', 1)[1].strip('|').strip()]

def bar(m):
    return m.text(rows=28).splitlines()[26]

def sp(m): return m.ram[0] | m.ram[1] << 8

def boot():
    m = Machine(rom, fresh()); m.run_frames(600); return m

def into_usa(m):
    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(100)

def favourite(m, downs):
    for k in ['DOWN'] * downs: m.press(k, 2, 4)
    m.press('RIGHT', 0, 0) if False else None
    m.run_frames(20)
    name = bar(m)
    m.press('RUN', 3, 60); m.press('DOWN', 2, 10); m.press('RUN', 3, 60)
    msg = [l for l in txt(m) if 'favorit' in l.lower()]
    m.press('I', 3, 90)
    return name, msg

m = boot()
into_usa(m)
print('fav 1:', favourite(m, 3))                       # Ballistix (U) [h1]
m.press('RIGHT', 2, 40)                                 # page 2
print('fav 2:', favourite(m, 2))
# load a game -> recents (the emulator reboots afterwards)
m.press('LEFT', 2, 40)
for k in ['DOWN'] * 5: m.press(k, 2, 4)
loaded = bar(m)
m.press('RUN', 3, 60); m.pad = 8; m.run_frames(4); m.pad = 0; m.run_frames(200)
print('loaded:', loaded)

m = boot()
m.press('I', 3, 60)
print('menu:', txt(m, 2, 26)); m.render(os.path.join(OUT, 'v8_menu.png'))
m.press('RUN', 3, 80)
print('favourites:', txt(m, 2, 26)); m.render(os.path.join(OUT, 'v8_favs.png'))
m.press('DOWN', 2, 20)
sp0 = sp(m)
m.press('RUN', 3, 10)
for f in range(300):
    m.run_frames(2)
    if any('Carregar' in l for l in txt(m)): break
print('after go, frames %d:' % (f * 2), txt(m, 2, 6), '| sp', hex(sp(m)))
m.render(os.path.join(OUT, 'v8_go.png'))
m.press('I', 3, 90)
print('back to the folder:', bar(m), txt(m, 3, 4))
m.press('I', 3, 120)
print('I again -> root?', txt(m, 3, 6))

m.press('I', 3, 60); m.press('DOWN', 2, 10); m.press('RUN', 3, 80)
print('recents:', txt(m, 2, 8)); m.render(os.path.join(OUT, 'v8_recents.png'))
m.press('I', 3, 40); m.press('DOWN', 2, 10); m.press('DOWN', 2, 10); m.press('RUN', 3, 60)
print('about:', [l for l in txt(m) if 'Vers' in l])
m.press('I', 3, 60); print('back to menu:', [l for l in txt(m) if 'Favoritos' in l or 'Sobre' in l])
m.press('I', 3, 90); print('browser:', txt(m, 3, 6))
print('writes (relative):', sorted({e[1] - lba0 for e in sd.log if e[0] == 'write'}))
