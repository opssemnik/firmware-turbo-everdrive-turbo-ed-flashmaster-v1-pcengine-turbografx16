"""Headless PC Engine + Turbo EverDrive v1 model, enough to run the stock OS menu.

Cart model (reverse engineered from tos.pce):
  bank 0 offset $0000-$000F (CPU $E000-$E00F with MPR7=0) = cart registers
    reg0  SPI data: write = transfer byte; read = last byte (auto-read mode: also clocks next)
    reg8  control; bit2 = auto-read
    reg4  status;  reg7 = firmware info (low nibble)
  banks $00-$0F = OS flash, $40+ = game flash (AMD command set, writes ignored here)
SD writes never reach the image file; they go to an in-memory overlay.
"""
import os
from cpu import CPU

CYC_LINE = 455
LINES = 263
VBL_LINE = 240


class SDCard:
    def __init__(self, path=None, image=None):
        self.path = path
        self.f = open(path, 'rb') if path else None
        self.image = image  # bytes-like alternative
        self.overlay = {}
        self.q = []
        self.cmd = []
        self.acmd = False
        self.stream = None  # next block for CMD18
        self.wr_state = None
        self.idle = True
        self.a41 = 0
        self.log = []

    def __getstate__(self):
        d = self.__dict__.copy(); d['f'] = None; d['path'] = self.path; return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        if self.path: self.f = open(self.path, 'rb')

    def block(self, n):
        if n in self.overlay: return self.overlay[n]
        if self.image is not None:
            return bytes(self.image[n * 512:(n + 1) * 512]).ljust(512, b'\0')
        self.f.seek(n * 512)
        return self.f.read(512).ljust(512, b'\0')

    def xfer(self, b):
        # write-block receive
        if self.wr_state is not None:
            st = self.wr_state
            if st['phase'] == 'token' and self.q:
                return self.q.pop(0)
            if st['phase'] == 'token':
                if b == 0xfe: st['phase'] = 'data'; st['buf'] = bytearray()
                return 0xff
            if st['phase'] == 'data':
                st['buf'].append(b)
                if len(st['buf']) == 514:
                    self.overlay[st['blk']] = bytes(st['buf'][:512])
                    self.log.append(('write', st['blk']))
                    self.wr_state = None
                    self.q = [0x05, 0x00, 0xff]
                return 0xff
        if self.cmd or (b & 0xc0) == 0x40:
            if not self.cmd: self.q = []
            self.cmd.append(b)
            if len(self.cmd) == 6:
                self._command(self.cmd)
                self.cmd = []
            return 0xff
        if self.q:
            return self.q.pop(0)
        if self.stream is not None:
            n = self.stream; self.stream += 1
            self.q = [0xfe] + list(self.block(n)) + [0, 0, 0xff]
            return 0xff
        return 0xff

    def _command(self, c):
        idx = c[0] & 0x3f
        arg = (c[1] << 24) | (c[2] << 16) | (c[3] << 8) | c[4]
        a = self.acmd; self.acmd = False
        self.log.append(('acmd' if a else 'cmd', idx, arg))
        if idx == 12:
            self.stream = None
            self.q = [0xff, 0x00, 0xff]
            return
        self.stream = None
        r1 = 1 if self.idle else 0
        if idx == 0: self.idle = True; self.q = [0xff, 0x01]
        elif idx == 8: self.q = [0xff, r1, 0x00, 0x00, 0x01, c[4]]
        elif idx == 55: self.acmd = True; self.q = [0xff, r1]
        elif idx == 41 and a:
            self.a41 += 1
            if self.a41 > 2: self.idle = False
            self.q = [0xff, 1 if self.idle else 0]
        elif idx == 58: self.q = [0xff, 0x00, 0xc0, 0xff, 0x80, 0x00]
        elif idx == 17:
            self.q = [0xff, 0x00, 0xff, 0xfe] + list(self.block(arg)) + [0, 0]
        elif idx == 18:
            self.q = [0xff, 0x00]; self.stream = arg
        elif idx == 24:
            self.q = [0xff, 0x00]; self.wr_state = {'phase': 'token', 'blk': arg}
        elif idx in (9, 10):
            self.q = [0xff, 0x00, 0xff, 0xfe] + [0] * 16 + [0, 0]
        else:
            self.q = [0xff, 0x00]


class Machine:
    def __init__(self, rom, sd=None):
        self.rom = bytearray(rom)
        self.ram = bytearray(0x2000)
        self.mpr = [0xff, 0xf8, 0, 0, 0, 0, 0, 0]
        self.vram = [0] * 0x8000
        self.vreg = [0] * 32
        self.var = 0
        self.vdc_status = 0
        self.vdc_lo_latch = 0
        self.vrr = 0
        self.cram = [0] * 512
        self.vce_addr = 0
        self.irq_disable = 0
        self.irq_status = 0  # bit1 IRQ1 (vdc)  bit2 timer
        self.timer_reload = 0
        self.timer_on = 0
        self.timer_cnt = 0
        self.timer_acc = 0
        self.pad = 0  # bitmask of pressed: 0 I,1 II,2 SEL,3 RUN,4 UP,5 RIGHT,6 DOWN,7 LEFT
        self.pad_sel = 0
        self.pad_idx = 0
        self.cart = [0] * 16
        self.cart[7] = 0x01
        self.cart[4] = 0x0b
        self.spi_latch = 0xff
        self.erase_armed = False
        self.erase_busy = 0                    # status reads left with "flash busy"
        self.erase_reads = 0                   # per erased bank; 0 = erase finishes at once
        self.sd = sd
        self.flash_writes = []
        self.unk = {}
        self.frame = 0
        self.line = 0
        self.line_acc = 0
        self.cpu = CPU(self)
        self.cpu.irq_pending = self._irq
        self.cpu.reset()

    def __getstate__(self):
        d = self.__dict__.copy(); return d

    def snapshot(self):
        import pickle
        cpu = self.cpu
        saved = (cpu.trace, cpu.hooks, cpu.irq_pending)
        cpu.trace = None; cpu.hooks = {}; cpu.irq_pending = None
        try:
            return pickle.dumps(self)
        finally:
            cpu.trace, cpu.hooks, cpu.irq_pending = saved

    @staticmethod
    def restore(blob):
        import pickle
        m = pickle.loads(blob)
        for k, v in (('erase_armed', False), ('erase_busy', 0), ('erase_reads', 0)):
            m.__dict__.setdefault(k, v)          # snapshots from older emulator versions
        m.cpu.irq_pending = m._irq
        return m

    def reset_mpr(self):
        self.mpr = [0xff, 0xf8, 0, 0, 0, 0, 0, 0]

    # ---------------- bus
    def read(self, a):
        bank = self.mpr[a >> 13]; off = a & 0x1fff
        if bank < 0x40:
            if bank == 0 and off < 0x10:
                return self.cart_read(off)
            o = (bank & 0x0f) * 0x2000 + off
            return self.rom[o] if o < len(self.rom) else 0xff
        if 0xf8 <= bank <= 0xfb: return self.ram[off]
        if bank == 0xff: return self.io_read(off)
        return self.flash_read(bank, off)

    def write(self, a, v):
        bank = self.mpr[a >> 13]; off = a & 0x1fff
        if 0xf8 <= bank <= 0xfb: self.ram[off] = v; return
        if bank == 0xff: self.io_write(off, v); return
        if bank == 0 and off < 0x10: self.cart_write(off, v); return
        self.flash_writes.append((bank, off, v))
        if bank >= 0x40:                       # AMD erase: $80 at $xaaa, later $30 = sector erase
            if v == 0x80 and off & 0xfff == 0xaaa: self.erase_armed = True
            elif v == 0x30 and self.erase_armed: self.erase_busy += self.erase_reads
        if len(self.flash_writes) > 100000: self.flash_writes = self.flash_writes[-1000:]

    def flash_read(self, bank, off):
        return 0xff              # the cart's other flash areas (firmware, games) are not modelled

    def cart_read(self, r):
        if r in (0, 1):  # reg1 mirrors reg0 (OS reads with TAI $e000)
            v = self.spi_latch
            if self.cart[8] & 4 and self.sd:
                self.spi_latch = self.sd.xfer(0xff)
            return v
        if r == 4 and self.erase_busy:
            self.erase_busy -= 1
            if not self.erase_busy: self.erase_armed = False
            return self.cart[4] & ~2
        return self.cart[r]

    def cart_write(self, r, v):
        if r == 0:
            self.spi_latch = self.sd.xfer(v) if self.sd else 0xff
            return
        self.cart[r] = v
        if r in (5, 6, 7, 10):
            self.unk.setdefault(('cartw', r), []).append(v)

    # ---------------- I/O
    def io_read(self, off):
        if off < 0x400:
            r = off & 3
            if r == 0:
                v = self.vdc_status; self.vdc_status = 0; self.irq_status &= ~2
                return v
            if r == 2: return self.vrr & 0xff
            if r == 3:
                v = self.vrr >> 8
                if self.var == 2:
                    self.vreg[1] = (self.vreg[1] + self._inc()) & 0xffff
                    self.vrr = self.vram[self.vreg[1] & 0x7fff]
                return v
            return 0
        if off < 0x800:
            r = off & 7
            if r == 4: return self.cram[self.vce_addr] & 0xff
            if r == 5:
                v = (self.cram[self.vce_addr] >> 8) | 0xfe
                self.vce_addr = (self.vce_addr + 1) & 0x1ff
                return v
            return 0xff
        if off < 0xc00: return 0
        if off < 0x1000: return self.timer_cnt & 0x7f
        if off < 0x1400:
            if self.pad_idx == 0:
                p = self.pad
                nib = (p >> 4) & 0xf if self.pad_sel else p & 0xf
                nib = (~nib) & 0xf
            else:
                nib = 0xf
            return 0xb0 | nib  # bit6 set: region bit as JP console; bit7 no CD
        if off < 0x1800:
            r = off & 3
            if r == 2: return self.irq_disable
            if r == 3: return self.irq_status
            return 0
        self.unk[('ior', off)] = self.unk.get(('ior', off), 0) + 1
        return 0xff

    def io_write(self, off, v):
        if off < 0x400:
            r = off & 3
            if r == 0: self.var = v & 0x1f
            elif r == 2: self.vdc_write(self.var, v, False)
            elif r == 3: self.vdc_write(self.var, v, True)
            return
        if off < 0x800:
            r = off & 7
            if r == 2: self.vce_addr = (self.vce_addr & 0x100) | v
            elif r == 3: self.vce_addr = (self.vce_addr & 0xff) | ((v & 1) << 8)
            elif r == 4: self.cram[self.vce_addr] = (self.cram[self.vce_addr] & 0x100) | v
            elif r == 5:
                self.cram[self.vce_addr] = (self.cram[self.vce_addr] & 0xff) | ((v & 1) << 8)
                self.vce_addr = (self.vce_addr + 1) & 0x1ff
            return
        if off < 0xc00: return
        if off < 0x1000:
            if off & 1:
                if (v & 1) and not self.timer_on: self.timer_cnt = self.timer_reload
                self.timer_on = v & 1
            else: self.timer_reload = v & 0x7f
            return
        if off < 0x1400:
            sel = v & 1
            if v & 2: self.pad_idx = 0
            elif sel and not self.pad_sel: self.pad_idx = min(self.pad_idx + 1, 5)
            self.pad_sel = sel
            return
        if off < 0x1800:
            r = off & 3
            if r == 2: self.irq_disable = v & 7
            elif r == 3: self.irq_status &= ~4
            return

    def vdc_st(self, which, v):
        if which == 0: self.var = v & 0x1f
        else: self.vdc_write(self.var, v, which == 2)

    def _inc(self):
        return (1, 32, 64, 128)[(self.vreg[5] >> 11) & 3]

    def vdc_write(self, reg, v, hi):
        if not hi:
            if reg == 2: self.vdc_lo_latch = v
            else: self.vreg[reg] = (self.vreg[reg] & 0xff00) | v
            return
        if reg == 2:
            w = self.vdc_lo_latch | (v << 8)
            self.vram[self.vreg[0] & 0x7fff] = w
            self.vreg[0] = (self.vreg[0] + self._inc()) & 0xffff
            return
        self.vreg[reg] = (self.vreg[reg] & 0xff) | (v << 8)
        if reg == 1:
            self.vrr = self.vram[self.vreg[1] & 0x7fff]
        elif reg == 0x12:
            self._vram_dma()

    def _vram_dma(self):
        src, dst, ln = self.vreg[0x10], self.vreg[0x11], self.vreg[0x12]
        dcr = self.vreg[0x0f]
        ds = -1 if dcr & 4 else 1
        dd = -1 if dcr & 8 else 1
        for _ in range(ln + 1):
            self.vram[dst & 0x7fff] = self.vram[src & 0x7fff]
            src = (src + ds) & 0xffff; dst = (dst + dd) & 0xffff

    # ---------------- interrupts / timing
    def _irq(self):
        pend = self.irq_status & ~self.irq_disable
        if pend & 2: return 0xfff8
        if pend & 4: return 0xfffa
        return None

    def run_cycles(self, n):
        cpu = self.cpu
        end = cpu.cycles + n
        while cpu.cycles < end:
            c0 = cpu.cycles
            cpu.step()
            dc = cpu.cycles - c0
            if self.timer_on:
                self.timer_acc += dc
                while self.timer_acc >= 1024:
                    self.timer_acc -= 1024
                    self.timer_cnt -= 1
                    if self.timer_cnt < 0:
                        self.timer_cnt = self.timer_reload
                        self.irq_status |= 4
            self.line_acc += dc
            while self.line_acc >= CYC_LINE:
                self.line_acc -= CYC_LINE
                self._next_line()

    def _next_line(self):
        self.line += 1
        cr = self.vreg[5]
        if self.line == VBL_LINE:
            self.vdc_status |= 0x20
            if cr & 8: self.irq_status |= 2
            self.frame += 1
        if self.line >= LINES:
            self.line = 0
        rcr = self.vreg[6] & 0x3ff
        if cr & 4 and rcr >= 64 and rcr - 64 == self.line:
            self.vdc_status |= 0x04
            self.irq_status |= 2

    def run_frames(self, n):
        for _ in range(n):
            self.run_cycles(CYC_LINE * LINES)

    # ---------------- rendering
    def color(self, idx):
        c = self.cram[idx]
        g = (c >> 6) & 7; r = (c >> 3) & 7; b = c & 7
        return (r * 255 // 7, g * 255 // 7, b * 255 // 7)

    def tile_pixel_rows(self, t):
        base = (t * 16) & 0x7fff
        rows = []
        for y in range(8):
            w0 = self.vram[base + y]; w1 = self.vram[base + 8 + y]
            row = []
            for x in range(8):
                bit = 7 - x
                p = ((w0 >> bit) & 1) | (((w0 >> (8 + bit)) & 1) << 1) | (((w1 >> bit) & 1) << 2) | (((w1 >> (8 + bit)) & 1) << 3)
                row.append(p)
            rows.append(row)
        return rows

    def screen_dims(self):
        mwr = self.vreg[9]
        bw = (32, 64, 128, 128)[(mwr >> 4) & 3]
        bh = 64 if mwr & 0x40 else 32
        w = ((self.vreg[0x0b] & 0x7f) + 1) * 8
        h = (self.vreg[0x0d] & 0x1ff) + 1
        if w < 64: w = 256
        if h < 64 or h > 242: h = 224
        return bw, bh, w, h

    def render(self, path):
        from PIL import Image
        bw, bh, w, h = self.screen_dims()
        bx = self.vreg[7] & 0x3ff; by = self.vreg[8] & 0x1ff
        img = Image.new('RGB', (w, h))
        px = img.load()
        cache = {}
        for sy in range(h):
            ty = ((sy + by) // 8) % bh; yy = (sy + by) % 8
            for sx in range(w):
                tx = ((sx + bx) // 8) % bw; xx = (sx + bx) % 8
                e = self.vram[ty * bw + tx]
                t = e & 0x7ff; pal = e >> 12
                if t not in cache: cache[t] = self.tile_pixel_rows(t)
                p = cache[t][yy][xx]
                px[sx, sy] = self.color(pal * 16 + p if p else 0)
        self._render_sprites(px, w, h)
        img = img.resize((w * 2, h * 2), Image.NEAREST)
        img.save(path)

    def _render_sprites(self, px, w, h):
        """SATB at VRAM reg $13 (auto DMA assumed); drawn in reverse so entry 0 is on top."""
        if not self.vreg[5] & 0x40: return
        sat = self.vreg[0x13] & 0x7fff
        for i in range(63, -1, -1):
            y0, x0, pat, attr = (self.vram[(sat + i * 4 + k) & 0x7fff] for k in range(4))
            sy = (y0 & 0x3ff) - 64; sx = (x0 & 0x3ff) - 32
            cw = 2 if attr & 0x100 else 1
            ch = (1, 2, 4, 4)[(attr >> 12) & 3]
            base = (pat & 0x7fe) << 5
            pal = 0x100 + (attr & 0xf) * 16
            if sy + ch * 16 <= 0 or sy >= h or sx + cw * 16 <= 0 or sx >= w: continue
            for cy in range(ch):
                for cx in range(cw):
                    cell = (base + (cy * 2 + cx) * 64) & 0x7fff
                    for yy in range(16):
                        p0, p1, p2, p3 = (self.vram[(cell + pl * 16 + yy) & 0x7fff] for pl in range(4))
                        for xx in range(16):
                            b = 15 - xx
                            c = ((p0 >> b) & 1) | (((p1 >> b) & 1) << 1) | (((p2 >> b) & 1) << 2) | (((p3 >> b) & 1) << 3)
                            X = sx + cx * 16 + xx; Y = sy + cy * 16 + yy
                            if c and 0 <= X < w and 0 <= Y < h:
                                px[X, Y] = self.color(pal + c)

    def text(self, font_base=None, rows=None):
        """BAT as text. Tile -> char = tile - font_base + 32."""
        bw, bh, w, h = self.screen_dims()
        if font_base is None: font_base = 0x60
        by = (self.vreg[8] & 0x1ff) // 8
        out = []
        for ry in range(rows or (h // 8)):
            ty = (ry + by) % bh
            s = ''
            for tx in range(min(bw, w // 8)):
                e = self.vram[ty * bw + tx]; t = e & 0x7ff
                c = t - font_base
                s += chr(c) if 32 <= c < 127 else ('.' if t else ' ')
            out.append('%2d|%s|' % (ry, s.rstrip()))
        return '\n'.join(out)

    def pal_at(self, tx, ty):
        bw = self.screen_dims()[0]
        return self.vram[ty * bw + tx] >> 12

    def guess_font_base(self):
        # find the tile whose pixels match font glyph 'A' from rom bank 1 ($2000 + 0x21*8)
        rom = self.rom
        for fo in (0x2000,):
            glyph = rom[fo + 0x21 * 8: fo + 0x22 * 8]
            for t in range(0x7ff):
                rows = self.tile_pixel_rows(t)
                ok = True
                for y in range(8):
                    bits = sum(1 << (7 - x) for x in range(8) if rows[y][x])
                    if bits != glyph[y]: ok = False; break
                if ok and any(glyph): return t - 0x21
        return 0x100

    def press(self, buttons, frames=4, release=6):
        names = {'I': 1, 'II': 2, 'SEL': 4, 'RUN': 8, 'UP': 16, 'RIGHT': 32, 'DOWN': 64, 'LEFT': 128}
        m = 0
        for b in buttons.split('+'): m |= names[b]
        self.pad = m
        self.run_frames(frames)
        self.pad = 0
        self.run_frames(release)
