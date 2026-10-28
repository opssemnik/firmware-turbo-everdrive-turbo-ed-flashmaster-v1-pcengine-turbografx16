import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import boot, ROOT
from machine import Machine, SDCard
from huc6280 import decode
m = Machine(open(ROOT+'stock/tos.pce','rb').read(), SDCard(ROOT+'sdcard_dump'))
hist=[]
def tr(cpu, pc):
    hist.append((pc, m.mpr[pc>>13], cpu.a, cpu.x, cpu.y, cpu.p))
    if len(hist)>200000: del hist[:100000]
m.cpu.trace = tr
m.run_frames(int(sys.argv[1]) if len(sys.argv)>1 else 3)
from collections import Counter
c=Counter((h[0],h[1]) for h in hist[-20000:])
print(c.most_common(15))
for h in hist[-int(sys.argv[2]) if len(sys.argv)>2 else -40:]:
    n,s,_=decode(m.read,h[0]); print('%04x b%02x a=%02x x=%02x y=%02x p=%02x  %s'%(h[0],h[1],h[2],h[3],h[4],h[5],s))
