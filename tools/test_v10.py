"""v10: themes and banners from RGPOA.DAT."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()

def card(with_dat=True):
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    if with_dat: inject(sd, b'RGPOA   DAT', open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())
    return sd

sd = card()
m = Machine(rom, sd); m.run_frames(650)
for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
m.run_frames(100)
for k in ['DOWN'] * 5: m.press(k, 2, 4)
m.run_frames(40)
print('TCOUNT', m.ram[0xe4], 'BANCUST', m.ram[0xe9])
tiles = []
for i in range(m.ram[0xe4]):
    m.render(os.path.join(OUT, '_t.png'))
    tiles.append(Image.open(os.path.join(OUT, '_t.png')).resize((256, 224)).copy())
    print('theme', m.cram[0x1ff] & 15, 'custom banner', m.ram[0xe9], 'row30 entry', hex(m.vram[0x780 + 5]))
    m.press('SEL', 3, 30)
print('wrapped to', m.cram[0x1ff] & 15)
grid = Image.new('RGB', (5 * 264, 2 * 232), (24, 24, 24))
for i, im in enumerate(tiles): grid.paste(im, ((i % 5) * 264, (i // 5) * 232))
grid.save(os.path.join(OUT, 'v10_themes.png'))
for k in range(8): m.press('SEL', 3, 30)          # theme 8 = Retrochimp
print('saved theme', m.cram[0x1ff] & 15, 'header byte', sd.block(sd.log and [e for e in sd.log if e[0] == 'write'][-1][1])[16])
m2 = Machine(rom, sd); m2.run_frames(650)
print('after reboot: theme', m2.cram[0x1ff] & 15, 'custom banner', m2.ram[0xe9])
m2.render(os.path.join(OUT, 'v10_reboot.png'))
m2.press('I', 3, 60); print('menu keeps banner:', m2.ram[0xe9], hex(m2.vram[0x780 + 5]))
m3 = Machine(rom, card(False)); m3.run_frames(650)
for i in range(9): m3.press('SEL', 3, 20)
print('no DAT: TCOUNT', m3.ram[0xe4], 'theme after 9 presses', m3.cram[0x1ff] & 15, '(8 built-in -> 1)')
