"""HuC6280 CPU core (instruction-level, approximate cycles)."""
from huc6280 import T, SIZE

C, Z, I, D, B, TF, V, N = 1, 2, 4, 8, 16, 32, 64, 128


class CPU:
    def __init__(self, bus):
        self.bus = bus  # bus.read(addr16) / bus.write(addr16,v) operate on logical addresses
        self.a = self.x = self.y = 0
        self.s = 0xff
        self.p = I
        self.pc = 0
        self.cycles = 0
        self.irq_pending = None  # callable -> vector or None
        self.waiting = False
        self.hooks = {}  # pc -> fn(cpu) ; return True to skip executing instruction
        self.trace = None
        self._build()

    # ---- helpers
    def rd(self, a): return self.bus.read(a & 0xffff)
    def wr(self, a, v): self.bus.write(a & 0xffff, v & 0xff)
    def zp(self, a): return self.bus.read(0x2000 | (a & 0xff))
    def zpw(self, a, v): self.bus.write(0x2000 | (a & 0xff), v & 0xff)
    def zpword(self, a): return self.zp(a) | (self.zp(a + 1) << 8)
    def push(self, v):
        self.bus.write(0x2100 | self.s, v & 0xff); self.s = (self.s - 1) & 0xff
    def pull(self):
        self.s = (self.s + 1) & 0xff; return self.bus.read(0x2100 | self.s)
    def nz(self, v):
        self.p = (self.p & ~(N | Z)) | (v & 0x80) | (0 if v else Z)
        return v

    def reset(self):
        self.bus.reset_mpr()
        self.pc = self.rd(0xfffe) | (self.rd(0xffff) << 8)
        self.p = I

    def interrupt(self, vec, brk=False):
        self.push(self.pc >> 8); self.push(self.pc)
        self.push((self.p | B) if brk else (self.p & ~B))
        self.p = (self.p | I) & ~D & ~TF
        self.pc = self.rd(vec) | (self.rd(vec + 1) << 8)
        self.cycles += 8

    # ---- address modes -> effective address
    def ea(self, md, pc):
        rd = self.rd
        if md == 'zp': return 0x2000 | rd(pc + 1)
        if md == 'zpx': return 0x2000 | ((rd(pc + 1) + self.x) & 0xff)
        if md == 'zpy': return 0x2000 | ((rd(pc + 1) + self.y) & 0xff)
        if md == 'abs': return rd(pc + 1) | (rd(pc + 2) << 8)
        if md == 'abx': return ((rd(pc + 1) | (rd(pc + 2) << 8)) + self.x) & 0xffff
        if md == 'aby': return ((rd(pc + 1) | (rd(pc + 2) << 8)) + self.y) & 0xffff
        if md == 'izx': return self.zpword((rd(pc + 1) + self.x) & 0xff)
        if md == 'izy': return (self.zpword(rd(pc + 1)) + self.y) & 0xffff
        if md == 'izp': return self.zpword(rd(pc + 1))
        raise ValueError(md)

    def _build(self):
        self.ops = [None] * 256
        for op, (m, md) in T.items():
            self.ops[op] = (m, md, SIZE[md])

    def adc(self, v):
        a = self.a
        if self.p & D:
            lo = (a & 0xf) + (v & 0xf) + (self.p & C)
            hi = (a >> 4) + (v >> 4)
            if lo > 9: lo -= 10; hi += 1
            c = 0
            if hi > 9: hi -= 10; c = 1
            r = ((hi << 4) | lo) & 0xff
            self.p = (self.p & ~C) | c
            self.cycles += 1
        else:
            s = a + v + (self.p & C)
            r = s & 0xff
            self.p = (self.p & ~(C | V)) | (1 if s > 0xff else 0) | (V if (~(a ^ v) & (a ^ r) & 0x80) else 0)
        return self.nz(r)

    def sbc(self, v):
        a = self.a
        if self.p & D:
            borrow = 1 - (self.p & C)
            lo = (a & 0xf) - (v & 0xf) - borrow
            hi = (a >> 4) - (v >> 4)
            if lo < 0: lo += 10; hi -= 1
            c = 1
            if hi < 0: hi += 10; c = 0
            r = ((hi << 4) | lo) & 0xff
            self.p = (self.p & ~C) | c
            self.cycles += 1
        else:
            s = a - v - (1 - (self.p & C))
            r = s & 0xff
            self.p = (self.p & ~(C | V)) | (1 if s >= 0 else 0) | (V if ((a ^ v) & (a ^ r) & 0x80) else 0)
        return self.nz(r)

    def cmp(self, r, v):
        t = r - v
        self.p = (self.p & ~C) | (1 if t >= 0 else 0)
        self.nz(t & 0xff)

    def step(self):
        if self.irq_pending is not None:
            vec = self.irq_pending()
            if vec is not None and not (self.p & I):
                self.waiting = False
                self.interrupt(vec)
        pc = self.pc
        h = self.hooks.get(pc)
        if h is not None and h(self):
            return
        op = self.rd(pc)
        ent = self.ops[op]
        if ent is None:
            # undefined opcodes act as NOP on HuC6280
            self.pc = (pc + 1) & 0xffff; self.cycles += 2; return
        m, md, n = ent
        if self.trace: self.trace(self, pc)
        tflag = self.p & TF
        self.p &= ~TF
        self.pc = (pc + n) & 0xffff
        self.cycles += 2 + n
        rd, wr = self.rd, self.wr
        # operand value fetch helpers
        def val():
            if md == 'imm': return rd(pc + 1)
            if md == 'acc': return self.a
            return rd(self.ea(md, pc))

        if m in ('lda', 'ldx', 'ldy'):
            v = self.nz(val())
            setattr(self, m[2], v)
        elif m in ('sta', 'stx', 'sty', 'stz'):
            v = 0 if m == 'stz' else getattr(self, m[2])
            wr(self.ea(md, pc), v)
        elif m in ('ora', 'and', 'eor', 'adc', 'sbc'):
            if tflag:
                # T flag: operate on (zp,X) instead of A
                addr = 0x2000 | self.x
                acc = rd(addr)
                save = self.a; self.a = acc
            v = val()
            if m == 'ora': r = self.nz(self.a | v)
            elif m == 'and': r = self.nz(self.a & v)
            elif m == 'eor': r = self.nz(self.a ^ v)
            elif m == 'adc': r = self.adc(v)
            else: r = self.sbc(v)
            if tflag:
                wr(addr, r); self.a = save
            else:
                self.a = r
        elif m == 'cmp': self.cmp(self.a, val())
        elif m == 'cpx': self.cmp(self.x, val())
        elif m == 'cpy': self.cmp(self.y, val())
        elif m == 'bit':
            v = val()
            if md == 'imm':
                self.p = (self.p & ~(N | V | Z)) | (v & 0xc0) | (0 if (self.a & v) else Z)
            else:
                self.p = (self.p & ~(N | V | Z)) | (v & 0xc0) | (0 if (self.a & v) else Z)
        elif m in ('asl', 'lsr', 'rol', 'ror', 'inc', 'dec'):
            if md == 'acc':
                v = self.a
            else:
                addr = self.ea(md, pc); v = rd(addr)
            if m == 'asl':
                self.p = (self.p & ~C) | (v >> 7); r = (v << 1) & 0xff
            elif m == 'lsr':
                self.p = (self.p & ~C) | (v & 1); r = v >> 1
            elif m == 'rol':
                c = self.p & C; self.p = (self.p & ~C) | (v >> 7); r = ((v << 1) | c) & 0xff
            elif m == 'ror':
                c = self.p & C; self.p = (self.p & ~C) | (v & 1); r = (v >> 1) | (c << 7)
            elif m == 'inc': r = (v + 1) & 0xff
            else: r = (v - 1) & 0xff
            self.nz(r)
            if md == 'acc': self.a = r
            else: wr(addr, r)
        elif m in ('tsb', 'trb'):
            addr = self.ea(md, pc); v = rd(addr)
            self.p = (self.p & ~(N | V | Z)) | (v & 0xc0) | (0 if (self.a & v) else Z)
            wr(addr, (v | self.a) if m == 'tsb' else (v & ~self.a))
        elif m == 'tst':
            imm = rd(pc + 1)
            if md == 'immzp': addr = 0x2000 | rd(pc + 2)
            elif md == 'immzpx': addr = 0x2000 | ((rd(pc + 2) + self.x) & 0xff)
            elif md == 'immabs': addr = rd(pc + 2) | (rd(pc + 3) << 8)
            else: addr = ((rd(pc + 2) | (rd(pc + 3) << 8)) + self.x) & 0xffff
            v = rd(addr)
            self.p = (self.p & ~(N | V | Z)) | (v & 0xc0) | (0 if (imm & v) else Z)
        elif md == 'rel':
            off = rd(pc + 1); off = off - 256 if off > 127 else off
            tgt = (pc + 2 + off) & 0xffff
            p = self.p
            take = {'bpl': not p & N, 'bmi': p & N, 'bvc': not p & V, 'bvs': p & V, 'bcc': not p & C,
                    'bcs': p & C, 'bne': not p & Z, 'beq': p & Z, 'bra': True, 'bsr': True}[m]
            if m == 'bsr':
                r = (pc + 1) & 0xffff
                self.push(r >> 8); self.push(r)
            if take:
                self.pc = tgt; self.cycles += 2
        elif md == 'zrel':
            v = self.zp(rd(pc + 1)); bit = int(m[3])
            off = rd(pc + 2); off = off - 256 if off > 127 else off
            s = (v >> bit) & 1
            if (m[:3] == 'bbs') == bool(s):
                self.pc = (pc + 3 + off) & 0xffff; self.cycles += 2
        elif m[:3] in ('rmb', 'smb'):
            addr = self.ea('zp', pc); bit = int(m[3]); v = rd(addr)
            wr(addr, (v | (1 << bit)) if m[0] == 's' else (v & ~(1 << bit)))
        elif m == 'jmp':
            if md == 'abs': self.pc = rd(pc + 1) | (rd(pc + 2) << 8)
            elif md == 'ind':
                a = rd(pc + 1) | (rd(pc + 2) << 8); self.pc = rd(a) | (rd(a + 1) << 8)
            else:
                a = ((rd(pc + 1) | (rd(pc + 2) << 8)) + self.x) & 0xffff; self.pc = rd(a) | (rd(a + 1) << 8)
        elif m == 'jsr':
            r = (pc + 2) & 0xffff
            self.push(r >> 8); self.push(r)
            self.pc = rd(pc + 1) | (rd(pc + 2) << 8)
        elif m == 'rts':
            lo = self.pull(); hi = self.pull(); self.pc = ((hi << 8) | lo) + 1 & 0xffff
        elif m == 'rti':
            self.p = self.pull() & ~B
            lo = self.pull(); hi = self.pull(); self.pc = (hi << 8) | lo
        elif m == 'brk':
            self.pc = (pc + 2) & 0xffff
            self.interrupt(0xfff6, brk=True)
        elif m == 'pha': self.push(self.a)
        elif m == 'phx': self.push(self.x)
        elif m == 'phy': self.push(self.y)
        elif m == 'php': self.push(self.p | B)
        elif m == 'pla': self.a = self.nz(self.pull())
        elif m == 'plx': self.x = self.nz(self.pull())
        elif m == 'ply': self.y = self.nz(self.pull())
        elif m == 'plp': self.p = self.pull() & ~B
        elif m == 'tax': self.x = self.nz(self.a)
        elif m == 'tay': self.y = self.nz(self.a)
        elif m == 'txa': self.a = self.nz(self.x)
        elif m == 'tya': self.a = self.nz(self.y)
        elif m == 'tsx': self.x = self.nz(self.s)
        elif m == 'txs': self.s = self.x
        elif m == 'inx': self.x = self.nz((self.x + 1) & 0xff)
        elif m == 'iny': self.y = self.nz((self.y + 1) & 0xff)
        elif m == 'dex': self.x = self.nz((self.x - 1) & 0xff)
        elif m == 'dey': self.y = self.nz((self.y - 1) & 0xff)
        elif m == 'sax': self.a, self.x = self.x, self.a
        elif m == 'say': self.a, self.y = self.y, self.a
        elif m == 'sxy': self.x, self.y = self.y, self.x
        elif m == 'cla': self.a = 0
        elif m == 'clx': self.x = 0
        elif m == 'cly': self.y = 0
        elif m == 'clc': self.p &= ~C
        elif m == 'sec': self.p |= C
        elif m == 'cli': self.p &= ~I
        elif m == 'sei': self.p |= I
        elif m == 'cld': self.p &= ~D
        elif m == 'sed': self.p |= D
        elif m == 'clv': self.p &= ~V
        elif m == 'set': self.p |= TF
        elif m in ('csl', 'csh', 'nop'): pass
        elif m in ('st0', 'st1', 'st2'):
            self.bus.vdc_st(int(m[2]), rd(pc + 1))
        elif m == 'tam':
            msk = rd(pc + 1)
            for i in range(8):
                if msk & (1 << i): self.bus.mpr[i] = self.a
        elif m == 'tma':
            msk = rd(pc + 1)
            for i in range(8):
                if msk & (1 << i): self.a = self.bus.mpr[i]; break
        elif md == 'blk':
            src = rd(pc + 1) | (rd(pc + 2) << 8)
            dst = rd(pc + 3) | (rd(pc + 4) << 8)
            ln = rd(pc + 5) | (rd(pc + 6) << 8)
            if ln == 0: ln = 0x10000
            alt = 0
            for i in range(ln):
                if m == 'tii': wr(dst + i, rd(src + i))
                elif m == 'tdd': wr(dst - i, rd(src - i))
                elif m == 'tin': wr(dst, rd(src + i))
                elif m == 'tia': wr(dst + alt, rd(src + i)); alt ^= 1
                elif m == 'tai': wr(dst + i, rd(src + alt)); alt ^= 1
            self.cycles += 17 + 6 * ln
        else:
            raise NotImplementedError(m)
