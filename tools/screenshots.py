"""Render the README screenshots with the headless emulator.

usage: python screenshots.py   -> docs/screenshots/*.png
Needs sdcard_dump (an image of an SD card) and out/TOS.PCE + out/RGPOA.DAT.
RGPOA.DAT is injected into the emulated card in memory; the image file is never written.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from machine import Machine, SDCard
from fatinject import inject
from build import THEMES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
DOCS = os.path.join(ROOT, 'docs', 'screenshots')


def main():
    os.makedirs(DOCS, exist_ok=True)
    rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    inject(sd, b'RGPOA   DAT', open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())
    m = Machine(rom, sd)
    shot = lambda mm, name: mm.render(os.path.join(DOCS, name + '.png'))

    first = last = None
    for f in range(600):
        m.run_frames(1)
        on = m.cram[0x51] != 0 and any(m.vram[r * 64 + 5] >> 12 == 5 for r in range(32))
        if on and first is None: first = f
        if on: last = f
        if first is not None and f == first + 60: shot(m, 'splash')
        if first is not None and not on and f > first + 10: break
    print('splash visible for %d frames (%.1f s)' % (last - first + 1, (last - first + 1) / 60))
    m.run_frames(200)
    shot(m, 'menu')
    root = m.snapshot()

    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(120)
    for k in ['DOWN'] * 5: m.press(k, 2, 4)   # Bloody Wolf
    m.run_frames(40)
    shot(m, 'capa')
    folder = m.snapshot()

    act = Machine.restore(folder)
    act.press('RUN', 3, 60)
    act.press('DOWN', 2, 10)
    shot(act, 'acoes')

    tiles = []
    t = Machine.restore(folder)
    for i in range(len(THEMES)):
        t.render(os.path.join(OUT, '_theme.png'))
        tiles.append(Image.open(os.path.join(OUT, '_theme.png')).resize((256, 224)).copy())
        t.press('SEL', 3, 20)
    grid = Image.new('RGB', (4 * 256 + 3 * 8, 2 * 224 + 8), (24, 24, 24))
    for i, im in enumerate(tiles):
        grid.paste(im, ((i % 4) * 264, (i // 4) * 232))
    grid.save(os.path.join(DOCS, 'temas.png'))
    os.remove(os.path.join(OUT, '_theme.png'))

    a = Machine.restore(root)
    a.press('I', 3, 60)
    shot(a, 'menu_principal')
    a.press('DOWN', 2, 10); a.press('DOWN', 2, 10); a.pad = 8; a.run_frames(40); a.pad = 0
    shot(a, 'sobre')

    f = Machine.restore(folder)        # two favourites, then menu > Favoritos
    for downs in (0, 4):
        for k in ['DOWN'] * downs: f.press(k, 2, 4)
        f.press('RUN', 3, 60); f.press('DOWN', 2, 10); f.press('RUN', 3, 60); f.press('I', 3, 90)
    f.press('I', 3, 120)
    f.press('I', 3, 60); f.press('RUN', 3, 90)
    shot(f, 'favoritos')

    g = Machine.restore(folder)
    g.press('RUN', 3, 60)          # action screen, "Carregar" selected
    g.pad = 8; g.run_frames(4); g.pad = 0
    for f in range(60):
        g.run_frames(2)
        if 'Carreg' in g.text(rows=28): shot(g, 'carregando'); break
    print('screenshots in', DOCS)


if __name__ == '__main__':
    main()
