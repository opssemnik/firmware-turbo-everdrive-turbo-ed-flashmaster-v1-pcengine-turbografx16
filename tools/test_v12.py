"""v12: loading progress bar. Flash writes must be identical to the previous version's."""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')

def load(rom_path, downs, shots=None):
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    inject(sd, b'RGPOA   DAT', open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read())
    m = Machine(open(rom_path, 'rb').read(), sd); m.run_frames(650)
    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(100)
    for k in ['DOWN'] * downs: m.press(k, 2, 4)
    m.run_frames(30)
    h = hashlib.md5(); n = [0]
    ow = m.write
    def w(a, v):
        if m.mpr[a >> 13] >= 0x40 and m.mpr[a >> 13] < 0xf8:
            h.update(bytes([m.mpr[a >> 13], (a >> 8) & 0xff, a & 0xff, v])); n[0] += 1
        ow(a, v)
    m.write = w
    m.press('RUN', 3, 40)
    m.pad = 8; m.run_frames(4); m.pad = 0
    bars = []
    for f in range(80):
        m.run_frames(5)
        row = [m.vram[18 * 64 + c] & 0x7ff for c in range(32)]
        full, empty = row.count(0x1c1), row.count(0x1c0)
        if full + empty: bars.append((full, full + empty))
        if shots is not None and full and len(shots) < 1 and full * 2 >= full + empty:
            m.render(os.path.join(OUT, 'v12_loading.png')); shots.append(1)
    return h.hexdigest(), n[0], bars

if __name__ == '__main__':
    from concurrent.futures import ProcessPoolExecutor
    old = os.path.join(OUT, 'release', 'TOS.PCE')       # the previous release
    new = os.path.join(OUT, 'TOS.PCE')
    with ProcessPoolExecutor() as ex:                     # the four loads run in parallel
        jobs = {(d, v): ex.submit(load, rom, d, [] if v == 'new' else None)
                for d in (3, 9) for v, rom in (('old', old), ('new', new))}
        for downs in (3, 9):
            a, b = jobs[(downs, 'old')].result(), jobs[(downs, 'new')].result()
            print('game #%d: flash writes previous %d / new %d, identical: %s' % (downs, a[1], b[1], a[0] == b[0]))
            print('   bar progress samples:', sorted(set(b[2]))[:3], '...', sorted(set(b[2]))[-2:])
