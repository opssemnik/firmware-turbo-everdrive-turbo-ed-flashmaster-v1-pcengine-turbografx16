"""v9: II on a game opens the game screen, SELECT+direction jumps letters, SELECT tap = theme."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
inject(sd, b'RGPOA   DAT', open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())

def txt(m): return [l for l in m.text(rows=28).splitlines() if l.split('|', 1)[1].strip('|').strip()]
def bar(m): return m.text(rows=28).splitlines()[26][4:].rstrip('|')
def theme(m): return m.cram[0x1ff] & 0xf

def combo(m, a, b, frames=4):
    m.pad = a; m.run_frames(3); m.pad = a | b; m.run_frames(frames); m.pad = a; m.run_frames(3); m.pad = 0; m.run_frames(40)

SEL, II, RUN, UP, RIGHT, DOWN, LEFT = 4, 2, 8, 16, 32, 64, 128
m = Machine(rom, sd)
first = None
for f in range(300):
    m.run_frames(1)
    on = m.cram[0x51] != 0 and any(m.vram[r * 64 + 5] >> 12 == 5 for r in range(32))
    if on and first is None: first = f
    if first is not None and not on: print('splash frames:', f - first); break
m.run_frames(400)
print('II on folder (USA):'); m.press('DOWN', 2, 4); m.press('DOWN', 2, 4); m.press('II', 3, 120); print(' ', txt(m)[2:4])
for k in ['DOWN'] * 3: m.press(k, 2, 4)
m.press('II', 3, 60); print('II on game:', [l for l in txt(m) if 'Carregar' in l or '.pce' in l][:2])
m.press('I', 3, 90)
t0 = theme(m); m.press('SEL', 3, 20); print('SELECT tap theme', t0, '->', theme(m))
t1 = theme(m)
print('at', bar(m))
for i in range(4):
    combo(m, SEL, RIGHT); print('SEL+RIGHT ->', bar(m))
combo(m, SEL, LEFT); print('SEL+LEFT  ->', bar(m))
combo(m, SEL, LEFT); print('SEL+LEFT  ->', bar(m))
print('theme unchanged by letter jumps:', theme(m) == t1)
for i in range(12): combo(m, SEL, DOWN)
print('after 12 next-letter jumps ->', bar(m), txt(m)[2])
