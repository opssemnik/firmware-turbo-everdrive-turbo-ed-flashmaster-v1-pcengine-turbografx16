import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine import Machine, SDCard
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
m = Machine(open(os.path.join(OUT, 'TOS.PCE'), 'rb').read(), SDCard(os.path.join(ROOT, 'sdcard_dump')))
for f in range(0, 400, 20):
    m.run_frames(20)
    t = m.text(rows=28)
    if 'Aperte' in t or m.vram[0x780] >> 12 == 5 or any(m.vram[i] >> 12 == 5 for i in range(0, 0x800, 7)):
        m.render(os.path.join(OUT, 'v2_splash.png')); print('splash seen at frame', m.frame); break
m.run_frames(320)
print(m.text(rows=28)); m.render(os.path.join(OUT, 'v2_menu.png'))
open(os.path.join(OUT, 'v2_menu.snap'), 'wb').write(m.snapshot())
a = Machine.restore(m.snapshot()); a.press('I', 3, 40); a.render(os.path.join(OUT, 'v2_about.png')); print(a.text(rows=28))
t = Machine.restore(m.snapshot())
for i in range(5): t.press('SEL', 3, 10)
t.press('II', 3, 60); t.render(os.path.join(OUT, 'v2_folder_t5.png')); print(t.text(rows=6))
g = Machine.restore(m.snapshot())
for k in ['DOWN'] * 8: g.press(k, 2, 4)
g.pad = 8; g.run_frames(6); g.pad = 0
for f in range(40):
    g.run_frames(2)
    if 'Carreg' in g.text(rows=28): g.render(os.path.join(OUT, 'v2_loading.png')); print('loading ok'); break
