import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
dat = open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read()
lba0 = inject(sd, b'RGPOA   DAT', dat)
base_overlay = dict(sd.overlay)
print('injected at', lba0)

def fresh_sd():
    sd.q = []; sd.cmd = []; sd.stream = None; sd.wr_state = None; sd.idle = True; sd.a41 = 0; sd.acmd = False
    return sd

m = Machine(rom, fresh_sd()); m.run_frames(700)
zp = lambda m, a: m.ram[a]
print('FLAGS', zp(m, 0x24), 'DAT', int.from_bytes(m.ram[0x20:0x24], 'little'), 'NBMASK', zp(m, 0x25))
m.render(os.path.join(OUT, 'v3_menu.png'))
open(os.path.join(OUT, 'v3_menu.snap'), 'wb').write(m.snapshot())

# go into PCE USA(A-Z) (index 2) and rest on a few games
for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
m.run_frames(150)
print(m.text(rows=8))
print('SHOWN', zp(m, 0x2b), 'STABLE', zp(m, 0x2a))
m.render(os.path.join(OUT, 'v3_art1.png'))
for k in ['DOWN', 'DOWN', 'DOWN']: m.press(k, 2, 4)
m.run_frames(40); print('SHOWN', zp(m, 0x2b)); m.render(os.path.join(OUT, 'v3_art2.png'))

# theme save: SELECT x3, then reboot on the same card
writes_before = [e for e in sd.log if e[0] == 'write']
for i in range(3): m.press('SEL', 3, 10)
writes = [e for e in sd.log if e[0] == 'write']
print('writes:', writes[len(writes_before):], 'header theme byte', sd.block(lba0)[16])
assert all(e[1] == lba0 for e in writes), 'unexpected write target!'
m2 = Machine(rom, fresh_sd()); m2.run_frames(700)
print('after reboot theme state', hex(m2.cram[0x1ff]), 'bd', hex(m2.cram[0x02]))
m2.render(os.path.join(OUT, 'v3_reboot.png'))
# about screen hides the panel
m.press('I', 3, 30); print('about: SHOWN', zp(m, 0x2b)); m.render(os.path.join(OUT, 'v3_about.png'))
