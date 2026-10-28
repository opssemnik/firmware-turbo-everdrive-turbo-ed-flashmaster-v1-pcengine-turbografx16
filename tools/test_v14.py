"""v14: per-theme splash (from RGPOA.DAT) and progress bar in theme colours."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
dat = bytearray(open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())

def boot(theme):
    d = bytearray(dat); d[16] = theme
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump')); inject(sd, b'RGPOA   DAT', bytes(d))
    m = Machine(rom, sd)
    for f in range(120):
        m.run_frames(1)
        if sum(1 for r in range(32) for c in range(32) if m.vram[r * 64 + c] >> 12 == 5) > 500: break
    m.run_frames(30)
    return m, f

tiles = []
for t in range(10):
    m, f = boot(t)
    m.render(os.path.join(OUT, '_s.png'))
    tiles.append(Image.open(os.path.join(OUT, '_s.png')).resize((256, 224)).copy())
    print('theme %d: splash shown at frame %d, SPLSEC %d, banner %d' % (t, f, int.from_bytes(m.ram[0x58:0x5c], 'little'), m.ram[0xe9]))
g = Image.new('RGB', (5 * 264, 2 * 232), (24, 24, 24))
for i, im in enumerate(tiles): g.paste(im, ((i % 5) * 264, (i // 5) * 232))
g.save(os.path.join(OUT, 'v14_splashes.png'))

m, f = boot(1)                      # Retrochimp: load a game, check the bar colours
m.run_frames(300)
for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
m.run_frames(100)
for k in ['DOWN'] * 3: m.press(k, 2, 4)
m.press('RUN', 3, 40); m.pad = 8; m.run_frames(4); m.pad = 0
for i in range(60):
    m.run_frames(5)
    row = [m.vram[18 * 64 + c] for c in range(32)]
    if sum(1 for w in row if w & 0x7ff == 0x1c1) >= 6:
        m.render(os.path.join(OUT, 'v14_bar.png')); break
print('bar palette 7:', [hex(m.cram[0x70 + i]) for i in range(1, 5)], 'theme cols bar/bg/folder/cursor:',
      [hex(m.cram[a]) for a in (0x32, 0x02, 0x21, 0x01)])
