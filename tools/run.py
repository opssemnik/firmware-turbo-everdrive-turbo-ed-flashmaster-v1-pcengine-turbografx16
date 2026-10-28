import sys, time, os
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine import Machine, SDCard
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
def boot(rom=ROOT+'stock/tos.pce', frames=60):
    m = Machine(open(rom,'rb').read(), SDCard(ROOT+'sdcard_dump'))
    m.run_frames(frames)
    return m
if __name__ == '__main__':
    t=time.time()
    m = boot(sys.argv[1] if len(sys.argv)>1 and sys.argv[1] else ROOT+'stock/tos.pce', int(sys.argv[2]) if len(sys.argv)>2 else 60)
    print('time %.1fs frames %d pc %04x mpr %s'%(time.time()-t, m.frame, m.cpu.pc, [hex(x) for x in m.mpr]))
    print(m.text())
    print(m.sd.log[:20], len(m.sd.log))
    print(m.unk)
