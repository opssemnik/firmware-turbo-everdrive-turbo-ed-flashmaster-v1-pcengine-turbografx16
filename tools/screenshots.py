"""Render the README screenshots with the headless emulator.

usage: python screenshots.py   -> docs/screenshots/*.png
Needs sdcard_dump (an image of an SD card) and out/TOS.PCE + out/RGPOA.DAT.
RGPOA.DAT is injected into the emulated card in memory; the image file is never written.
One boot builds two snapshots (root, a game folder); every screenshot then runs in its
own process from those snapshots, in parallel.
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from PIL import Image
from machine import Machine, SDCard
from fatinject import inject

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
DOCS = os.path.join(ROOT, 'docs', 'screenshots')
TMP = tempfile.gettempdir()


def shot(m, name, size=None):
    path = os.path.join(DOCS, name + '.png') if size is None else os.path.join(TMP, 'rg_%s.png' % name)
    m.render(path)
    return path


def card(theme=None):
    dat = bytearray(open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())
    if theme is not None: dat[16] = theme
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    inject(sd, b'RGPOA   DAT', bytes(dat))
    return sd


def load(snap): return Machine.restore(open(snap, 'rb').read())


def job_acoes(folder):
    m = load(folder); m.press('RUN', 3, 60); m.press('DOWN', 2, 10); shot(m, 'acoes')


def job_theme(folder, i):
    m = load(folder)
    for _ in range(i): m.press('SEL', 3, 20)
    m.run_frames(10)
    return shot(m, 'theme%d' % i, 'tmp')


def job_menu_sobre(root):
    a = load(root); a.press('I', 3, 60); shot(a, 'menu_principal')
    for _ in range(3): a.press('DOWN', 2, 10)
    a.pad = 8; a.run_frames(40); a.pad = 0
    shot(a, 'sobre')


def job_busca(root):
    k = load(root)
    k.press('I', 3, 60); k.press('DOWN', 2, 10); k.press('DOWN', 2, 10); k.press('RUN', 3, 60)
    for seq in (['RIGHT'], ['DOWN', 'RIGHT', 'RIGHT', 'RIGHT'], ['LEFT', 'LEFT'], ['UP', 'LEFT']):
        for key in seq: k.press(key, 2, 6)
        k.press('II', 2, 10)
    shot(k, 'busca_teclado')
    k.press('RUN', 3, 400)
    shot(k, 'busca_resultados')


def job_favoritos(folder):
    f = load(folder)
    for downs in (0, 4):
        for k in ['DOWN'] * downs: f.press(k, 2, 4)
        f.press('RUN', 3, 60); f.press('DOWN', 2, 10); f.press('RUN', 3, 60); f.press('I', 3, 90)
    f.press('I', 3, 120)
    f.press('I', 3, 60); f.press('RUN', 3, 90)
    shot(f, 'favoritos')


def job_carregando(folder):
    g = load(folder)
    g.press('RUN', 3, 60)
    g.pad = 8; g.run_frames(4); g.pad = 0
    for _ in range(60):
        g.run_frames(2)
        row = [g.vram[18 * 64 + c] & 0x7ff for c in range(32)]
        if row.count(0x1c1) * 2 >= row.count(0x1c0) + row.count(0x1c1) > 0:
            shot(g, 'carregando'); return


def job_splash(theme):
    m = Machine(open(os.path.join(OUT, 'TOS.PCE'), 'rb').read(), card(theme))
    for _ in range(120):
        m.run_frames(1)
        if sum(1 for r in range(32) for c in range(32) if m.vram[r * 64 + c] >> 12 == 5) > 500: break
    m.run_frames(30)
    return shot(m, 'splash%d' % theme, 'tmp')


def grid(paths, name, cols=5):
    tiles = [Image.open(p).resize((256, 224)) for p in paths]
    rows = -(-len(tiles) // cols)
    g = Image.new('RGB', (cols * 264 - 8, rows * 232 - 8), (24, 24, 24))
    for i, im in enumerate(tiles): g.paste(im, ((i % cols) * 264, (i // cols) * 232))
    g.save(os.path.join(DOCS, name + '.png'))


def main():
    os.makedirs(DOCS, exist_ok=True)
    m = Machine(open(os.path.join(OUT, 'TOS.PCE'), 'rb').read(), card())
    first = last = None
    for f in range(600):
        m.run_frames(1)
        on = sum(1 for r in range(32) for c in range(32) if m.vram[r * 64 + c] >> 12 == 5) > 500
        if on and first is None: first = f
        if on: last = f
        if first is not None and f == first + 60: shot(m, 'splash')
        if first is not None and not on and f > first + 10: break
    print('splash visible for %d frames (%.1f s)' % (last - first + 1, (last - first + 1) / 60))
    m.run_frames(200)
    shot(m, 'menu')
    root = os.path.join(TMP, 'rg_root.snap'); open(root, 'wb').write(m.snapshot())
    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(120)
    for k in ['DOWN'] * 5: m.press(k, 2, 4)   # Bloody Wolf
    m.run_frames(40)
    shot(m, 'capa')
    folder = os.path.join(TMP, 'rg_folder.snap'); open(folder, 'wb').write(m.snapshot())
    n = m.ram[0xe4] or 8                      # themes in RGPOA.DAT

    with ProcessPoolExecutor() as ex:
        theme_jobs = [ex.submit(job_theme, folder, i) for i in range(n)]
        splash_jobs = [ex.submit(job_splash, i) for i in range(n)]
        others = [ex.submit(job_acoes, folder), ex.submit(job_menu_sobre, root), ex.submit(job_busca, root),
                  ex.submit(job_favoritos, folder), ex.submit(job_carregando, folder)]
        grid([j.result() for j in theme_jobs], 'temas')
        grid([j.result() for j in splash_jobs], 'splashes')
        for j in others: j.result()

    bdir = os.path.join(ROOT, 'themes', 'banners')
    names = sorted(f for f in os.listdir(bdir) if f.endswith('.png'))
    gal = Image.new('RGB', (768, len(names) * 54), (40, 40, 40))
    for i, f in enumerate(names):
        gal.paste(Image.open(os.path.join(bdir, f)).convert('RGB').resize((768, 48), Image.NEAREST), (0, i * 54))
    gal.save(os.path.join(DOCS, 'banners.png'))
    print('screenshots in', DOCS)


if __name__ == '__main__':
    main()
