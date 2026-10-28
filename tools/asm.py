"""Tiny two-pass HuC6280 assembler for patch routines.

Syntax (same as the disassembler output):
  label:            lda #$04        lda <$02        sta $3f24,y
  jsr label         bne label       tam #$40        lda [$ee],y
  .db 1,2,"text"    .dw label       name = expr
Expressions are Python expressions over labels; lo(x)/hi(x) helpers; $hex allowed.
"""
import re
from huc6280 import T, SIZE

REV = {}
for op, (m, md) in T.items():
    REV[(m, md)] = op
LONG = {'jeq': 'bne', 'jne': 'beq', 'jcc': 'bcs', 'jcs': 'bcc', 'jpl': 'bmi', 'jmi': 'bpl',
        'jvc': 'bvs', 'jvs': 'bvc'}
BRANCH = {'bpl', 'bmi', 'bvc', 'bvs', 'bcc', 'bcs', 'bne', 'beq', 'bra', 'bsr'}


def _expr(s, sym):
    s = re.sub(r'\$([0-9a-fA-F]+)', lambda m: str(int(m.group(1), 16)), s.strip())
    s = re.sub(r'(?<![\w])\.(\w+)', lambda m: '_dot_' + m.group(1), s)
    env = dict(sym); env['lo'] = lambda v: v & 0xff; env['hi'] = lambda v: (v >> 8) & 0xff
    return int(eval(s, {'__builtins__': {}}, env))


def _mode(m, opnd):
    o = opnd.strip()
    if m in ('bbr0',) or re.match(r'bb[rs]\d', m): return 'zrel', o
    if m in BRANCH: return 'rel', o
    if m in ('tii', 'tdd', 'tin', 'tia', 'tai'): return 'blk', o
    if m == 'tst':
        imm, rest = o[1:].split(',', 1)
        rest = rest.strip()
        if rest.startswith('<'):
            return ('immzpx' if rest.endswith(',x') else 'immzp'), o
        return ('immabx' if rest.endswith(',x') else 'immabs'), o
    if o == '': return 'imp', o
    if o == 'a': return 'acc', o
    if o.startswith('#'): return 'imm', o
    if o.startswith('<'):
        if o.endswith(',x'): return 'zpx', o
        if o.endswith(',y'): return 'zpy', o
        return 'zp', o
    if o.startswith('['):
        if o.endswith(',x]'): return ('iax' if m == 'jmp' else 'izx'), o
        if o.endswith('],y'): return 'izy', o
        return ('ind' if m == 'jmp' else 'izp'), o
    if o.endswith(',x'): return 'abx', o
    if o.endswith(',y'): return 'aby', o
    return 'abs', o


def assemble(src, org, sym=None):
    """Returns (bytes, symbols). sym: external symbols (dict)."""
    sym = dict(sym or {})
    lines = []
    for raw in src.splitlines():
        line = raw.split(';')[0].rstrip()
        if not line.strip(): continue
        lines.append(line)
    out = b''
    for pas in (1, 2):
        pc = org; out = bytearray()
        for line in lines:
            s = line.strip()
            mlab = re.match(r'^([A-Za-z_.][\w.]*):\s*(.*)$', s)
            if mlab:
                sym[re.sub(r'^\.', '_dot_', mlab.group(1))] = pc; s = mlab.group(2).strip()
                if not s: continue
            meq = re.match(r'^([A-Za-z_][\w]*)\s*=\s*(.+)$', s)
            if meq:
                try: sym[meq.group(1)] = _expr(meq.group(2), sym)
                except Exception:
                    if pas == 2: raise
                continue
            parts = s.split(None, 1)
            m = parts[0].lower(); opnd = parts[1] if len(parts) > 1 else ''
            if m in LONG:  # long branch: inverted short branch over a jmp
                t = _ev(opnd, sym, pas)
                out += bytes([REV[(LONG[m], 'rel')], 3, 0x4c, t & 0xff, (t >> 8) & 0xff])
                pc += 5; continue
            if m in ('.db', '.byte'):
                for item in _split_args(opnd):
                    if item.startswith('"'):
                        out += item[1:-1].encode('latin-1')
                    else:
                        out.append(_ev(item, sym, pas) & 0xff)
                pc = org + len(out); continue
            if m in ('.dw', '.word'):
                for item in _split_args(opnd):
                    v = _ev(item, sym, pas); out += bytes([v & 0xff, (v >> 8) & 0xff])
                pc = org + len(out); continue
            md, o = _mode(m, opnd)
            if (m, md) not in REV and md == 'abs' and (m, 'zp') in REV and False: md = 'zp'
            if (m, md) not in REV:
                raise ValueError('bad instruction: %s (%s)' % (s, md))
            op = REV[(m, md)]; n = SIZE[md]
            b = [op]
            if md in ('imp', 'acc'): pass
            elif md == 'imm': b.append(_ev(o[1:], sym, pas) & 0xff)
            elif md in ('zp', 'zpx', 'zpy'):
                b.append(_ev(o[1:].split(',')[0], sym, pas) & 0xff)
            elif md in ('izx', 'izy', 'izp'):
                inner = o[1:o.index(']')].split(',')[0]
                b.append(_ev(inner, sym, pas) & 0xff)
            elif md in ('abs', 'abx', 'aby'):
                v = _ev(o.split(',')[0], sym, pas); b += [v & 0xff, (v >> 8) & 0xff]
            elif md in ('ind', 'iax'):
                inner = o[1:o.index(']')].split(',')[0]
                v = _ev(inner, sym, pas); b += [v & 0xff, (v >> 8) & 0xff]
            elif md == 'rel':
                t = _ev(o, sym, pas); off = t - (pc + 2)
                if pas == 2 and not -128 <= off <= 127: raise ValueError('branch out of range: ' + s)
                b.append(off & 0xff)
            elif md == 'zrel':
                zpx, lab = o.split(',', 1)
                b.append(_ev(zpx.lstrip('<'), sym, pas) & 0xff)
                t = _ev(lab, sym, pas); off = t - (pc + 3)
                if pas == 2 and not -128 <= off <= 127: raise ValueError('branch out of range: ' + s)
                b.append(off & 0xff)
            elif md == 'blk':
                for item in o.split(','):
                    v = _ev(item, sym, pas); b += [v & 0xff, (v >> 8) & 0xff]
            else:
                raise ValueError(md)
            assert len(b) == n, (s, b, n)
            out += bytes(b); pc += n
    return bytes(out), sym


def _split_args(s):
    items, cur, q = [], '', False
    for ch in s:
        if ch == '"': q = not q
        if ch == ',' and not q: items.append(cur.strip()); cur = ''
        else: cur += ch
    if cur.strip(): items.append(cur.strip())
    return items


def _ev(s, sym, pas):
    try:
        return _expr(s, sym)
    except Exception:
        if pas == 1: return 0
        raise
