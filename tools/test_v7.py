"""v7: action screen (RUN on a file), favourites and recents in RGPOA.DAT v2."""
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

def lines(m, a=0, b=28):
    return [l for l in m.text(rows=28).splitlines()[a:b] if l.split('|', 1)[1].strip('|').strip()]

def entries(sector):
    d = sd.block(lba0 + sector)
    out = []
    for e in range(7):
        o = 16 + e * 64
        cl, seq = struct.unpack_from('<IH', d, o)
        if cl: out.append((cl, seq, d[o + 10:o + 64].split(b'\0')[0].decode('latin-1')))
    return d[:12], out

m = Machine(rom, fresh()); m.run_frames(600)
assert m.ram[0x24] == 3, 'RGPOA.DAT v2 not found'
for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
m.run_frames(100)
for k in ['DOWN'] * 3: m.press(k, 2, 4)
m.run_frames(40)
print('browser art shown:', m.ram[0x2b], '| sp', hex(m.ram[0] | m.ram[1] << 8))
sp0 = m.ram[0] | m.ram[1] << 8
nw = len([e for e in sd.log if e[0] == 'write'])

m.press('RUN', 3, 60)
print('\n'.join(lines(m)))
print('cover SAT x/y:', m.vram[0x7f01] - 32, m.vram[0x7f00] - 64, '| AFAV', m.ram[0x41])
m.render(os.path.join(OUT, 'v7_action.png'))

m.press('DOWN', 2, 10); m.press('RUN', 3, 60)
print('after Favoritar:', lines(m, 6, 23))
print('fav sector 1:', entries(1))
m.render(os.path.join(OUT, 'v7_fav.png'))
m.press('RUN', 3, 60); print('after Remover:', [l for l in lines(m) if 'favorit' in l.lower()])
print('fav sector 1:', entries(1))
m.press('RUN', 3, 60)   # add again
m.press('I', 3, 90)
print('back in browser:', lines(m, 3, 8), '| sp', hex(m.ram[0] | m.ram[1] << 8), 'expected', hex(sp0))
m.run_frames(40); print('art shown again:', m.ram[0x2b])
m.press('DOWN', 2, 30); print('cursor still moves:', lines(m, 26, 28))
m.press('UP', 2, 30)

m.press('RUN', 3, 60)
print('reopen (should offer Remover):', [l for l in lines(m) if 'favorit' in l.lower()])
m.press('RUN', 3, 4)      # Carregar
n = len(sd.log)
for f in range(60):
    m.run_frames(2)
    if 'Carreg' in m.text(rows=28): break
print('loading screen:', 'Carreg' in m.text(rows=28), '| rec sector 9:', entries(9))
writes = [e[1] - lba0 for e in sd.log if e[0] == 'write'][nw:]
print('writes (relative sectors):', writes)
assert all(0 <= w <= 10 for w in writes)

m2 = Machine(rom, fresh()); m2.run_frames(600)
for k in ['DOWN', 'DOWN', 'II']: m2.press(k, 3, 30)
m2.run_frames(100)
for k in ['DOWN'] * 3: m2.press(k, 2, 4)
m2.press('RUN', 3, 60)
print('after reboot:', [l for l in lines(m2) if 'favorit' in l.lower()])
