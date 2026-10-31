"""v19: a theme panel (RGPOA.DAT) replaces the cover when the selection has none (Retrochimp: QR)."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from machine import Machine, SDCard
from fatinject import inject
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
TMP = os.environ.get('TEMP', '/tmp')
rom = open(os.path.join(OUT, 'TOS.PCE'), 'rb').read()
DAT = open(os.path.join(OUT, 'RGPOA.DAT'), 'rb').read()
tt = struct.unpack_from('<I', DAT, 20)[0] * 512
PAN = struct.unpack_from('<H', DAT, tt + 32 + 30)[0]              # theme 1 (Retrochimp)
fails = []
def check(what, ok):
    print(('ok   ' if ok else 'FAIL ') + what)
    if not ok: fails.append(what)

def boot(theme, lang=0):
    dat = bytearray(DAT); dat[16] = theme; dat[24] = lang
    sd = SDCard(os.path.join(ROOT, 'sdcard_dump'))
    inject(sd, b'RGPOA   DAT', bytes(dat))
    m = Machine(rom, sd); m.run_frames(650)
    return m

def panel(m):
    """-> (shown, first art-block sector read last, sprite palette colour 1)"""
    m.run_frames(40)
    return m.ram[0x2b], m.cram[0x101]

shown_pal = {}
for lang in (0, 1):
    m = boot(1, lang)
    check('lang %d: theme 1 panel sector %d in RAM' % (lang, PAN), (m.ram[0x5d] | m.ram[0x5e] << 8) == PAN)
    s, c = panel(m)                                  # root: folders, no cover
    check('lang %d: panel shown at the root (on a folder)' % lang, s == 1)
    m.render(os.path.join(TMP, 'rg_v19_root_%d.png' % lang))
    shown_pal[lang] = list(m.cram[0x100:0x110])
    vram_root = m.vram[0x4000:0x4000 + 3072]
    for k in ['DOWN', 'DOWN', 'II']: m.press(k, 3, 30)
    m.run_frames(100)
    for k in ['DOWN'] * 5: m.press(k, 2, 4)   # Battle Royale: has a cover
    s, c = panel(m)
    check('lang %d: cover shown on a game with cover' % lang, s == 1 and m.vram[0x4000:0x4000 + 3072] != vram_root)
    if lang == 0: m.render(os.path.join(TMP, 'rg_v19_cover.png'))

# English panel differs from the Portuguese one (text), same QR palette
check('PT and EN panels loaded', shown_pal[0] == shown_pal[1])

# a theme without panel: nothing at the root
m = boot(2)
s, _ = panel(m)
check('theme 2 (no panel): nothing at the root', s == 0)

# switching theme with SELECT from Retrochimp to the next hides the panel
m = boot(1)
s, _ = panel(m)
m.press('SEL', 3, 60)
s2, _ = panel(m)
check('SELECT to theme 2 hides the panel (%d -> %d)' % (s, s2), s == 1 and s2 == 0)

print('\n%d falhas' % len(fails))
sys.exit(1 if fails else 0)
