"""v11: global search (menu > Buscar)."""
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
txt = lambda m: [l for l in m.text(rows=28).splitlines() if l.split('|', 1)[1].strip('|').strip()]

m = Machine(rom, sd); m.run_frames(650)
m.press('I', 3, 60)
for k in ['DOWN', 'DOWN']: m.press(k, 2, 10)
m.press('RUN', 3, 60)
print('keyboard:', txt(m)[2:5]); m.render(os.path.join(OUT, 'v11_keyboard.png'))
for seq in (['RIGHT'], ['DOWN', 'RIGHT', 'RIGHT', 'RIGHT'], ['LEFT', 'LEFT'], ['UP', 'LEFT']):
    for k in seq: m.press(k, 2, 6)
    m.press('II', 2, 10)
print('typed:', [l for l in txt(m) if '>' in l][:1])
n = len(m.sd.log)
m.press('RUN', 3, 2)
for f in range(1200):
    m.run_frames(5)
    if any('Resultados' in l or 'Nenhum' in l for l in txt(m)): break
print('search took %d frames (%.1f s), sd commands %d' % (f * 5, f * 5 / 60, len(m.sd.log) - n))
print('\n'.join(txt(m)[:12])); m.render(os.path.join(OUT, 'v11_results.png'))
writes = [e for e in m.sd.log[n:] if e[0] == 'write']
print('writes during search:', writes)
for k in ['DOWN', 'DOWN']: m.press(k, 2, 10)
pick = [l for l in txt(m) if '>' in l][0]
m.press('II', 3, 10)
for f in range(400):
    m.run_frames(3)
    if any('Carregar' in l for l in txt(m)): break
print('picked', pick, '-> game screen after %d frames:' % (f * 3), txt(m)[2:3])
