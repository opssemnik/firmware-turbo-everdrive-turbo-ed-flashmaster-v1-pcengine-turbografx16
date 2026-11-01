"""Menu music: an original chiptune loop for the PSG, the player's data tables, and a preview.

Song: 8 bars in A minor (Am F C G | Am F G E), 150 BPM, a sixteenth = 6 frames at 60 Hz.
Channels: 0 lead, 1 bass, 2 arpeggio (PSG channels 0-2, wavetable), 3 drums (PSG channel 4, noise).

Event stream per channel: note, frames ... and $ff = back to the start of that channel.
note 0 = rest; tone channels: note = MIDI - 26 (index into `periods`); drums: 1 kick, 2 snare, 3 hat.

usage: python music.py            -> out/musica.wav (rendered from the real player in the emulator)
"""
import os, struct, math

STEP = 6                         # frames per sixteenth
PSG_CLOCK = 3579545
NOTE_BASE = 26                   # table index 1 = MIDI 27 (D#1); 64 notes


def midi(name):
    """'A4' / 'G#5' -> MIDI number."""
    n = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[name[0]]
    rest = name[1:]
    if rest[0] == '#': n += 1; rest = rest[1:]
    return n + 12 * (int(rest) + 1)


def period(m):
    return round(PSG_CLOCK / (32 * 440 * 2 ** ((m - 69) / 12)))


CHORDS = [  # root (bass octave), chord tones for the arpeggio
    ('A1', ['A4', 'C5', 'E5', 'A5']), ('F1', ['F4', 'A4', 'C5', 'F5']),
    ('C2', ['C5', 'E5', 'G5', 'C6']), ('G1', ['G4', 'B4', 'D5', 'G5']),
    ('A1', ['A4', 'C5', 'E5', 'A5']), ('F1', ['F4', 'A4', 'C5', 'F5']),
    ('G1', ['G4', 'B4', 'D5', 'G5']), ('E1', ['E4', 'G#4', 'B4', 'E5']),
]
LEAD = [  # (note or None, sixteenths); 16 per bar
    [('E5', 2), ('A5', 2), ('B5', 2), ('C6', 4), ('B5', 2), ('A5', 2), ('G5', 2)],
    [('A5', 6), ('F5', 2), ('C5', 2), ('F5', 2), ('A5', 4)],
    [('G5', 2), ('E5', 2), ('G5', 2), ('C6', 6), ('B5', 2), ('C6', 2)],
    [('D6', 4), ('B5', 4), ('G5', 4), (None, 4)],
    [('E5', 2), ('A5', 2), ('B5', 2), ('C6', 4), ('D6', 2), ('E6', 4)],
    [('F6', 4), ('E6', 2), ('D6', 2), ('C6', 4), ('A5', 4)],
    [('B5', 2), ('C6', 2), ('D6', 4), ('G5', 4), ('B5', 4)],
    [('G#5', 6), ('B5', 2), ('E6', 4), (None, 4)],
]
DRUMS = [1, 0, 3, 0, 2, 0, 3, 0, 1, 0, 1, 3, 2, 0, 3, 3]   # one bar of sixteenths


def tone(m):
    i = m - NOTE_BASE
    assert 1 <= i <= 64, m
    return i


def channels():
    """-> four event lists [(note, frames)]"""
    lead, bass, arp, drums = [], [], [], []
    for bar, ((root, tones), mel) in enumerate(zip(CHORDS, LEAD)):
        assert sum(n for _, n in mel) == 16, bar
        for name, n in mel:
            if name is None: lead.append((0, n * STEP))
            else:                    # a short gap between notes keeps them articulated
                lead += [(tone(midi(name)), n * STEP - 1), (0, 1)]
        r = midi(root)
        for i in range(8):           # octave bass in eighths
            bass += [(tone(r + (12 if i % 2 else 0)), 2 * STEP - 2), (0, 2)]
        for i in range(16):          # arpeggio up and down
            arp.append((tone(midi(tones[(0, 1, 2, 3, 2, 1, 2, 3)[i % 8]])), STEP))
        for d in DRUMS:
            drums.append((d, STEP))
    return [lead, bass, arp, drums]


def merge(ev):
    """Join consecutive rests."""
    out = []
    for note, n in ev:
        if out and note == 0 and out[-1][0] == 0 and out[-1][1] + n < 256: out[-1] = (0, out[-1][1] + n)
        else: out.append((note, n))
    return out


# lead: square-ish pulse, bass: triangle, arpeggio: thin pulse (5-bit samples)
WAVES = [
    [26] * 10 + [5] * 22,
    [round(abs(15.5 - ((i * 2) % 32 if i < 16 else 62 - i * 2)) * 2) for i in range(32)],
    [22] * 6 + [9] * 26,
]
# per channel: start volume (0-31), decay step, frames per step, floor
ENV = [(29, 1, 4, 20), (27, 1, 6, 22), (19, 1, 2, 9), (0, 3, 1, 0)]
DRUM = {1: (4, 29), 2: (26, 26), 3: (31, 16)}   # drum -> (noise frequency 0-31, start volume)


def tables():
    """Assembler source for the player's data (bank 12)."""
    db = lambda xs: ','.join(str(x) for x in xs)
    t = '\nperiods: .dw ' + db(period(NOTE_BASE + i) for i in range(1, 65))
    t += '\nwaves: .db ' + db(v for w in WAVES for v in w)
    t += '\nwave_off: .db 0,32,64'
    t += '\npsg_ch: .db 0,1,2,4'
    t += '\nvol_start: .db ' + db(e[0] for e in ENV)
    t += '\nenv_step: .db ' + db(e[1] for e in ENV)
    t += '\nenv_rate: .db ' + db(e[2] for e in ENV)
    t += '\nenv_floor: .db ' + db(e[3] for e in ENV)
    t += '\ndrum_nz: .db ' + db(0x80 | DRUM[d][0] for d in (1, 2, 3))
    t += '\ndrum_vol: .db ' + db(DRUM[d][1] for d in (1, 2, 3))
    t += '\nsong_lo: .db lo(song0),lo(song1),lo(song2),lo(song3)'
    t += '\nsong_hi: .db hi(song0),hi(song1),hi(song2),hi(song3)'
    for c, ev in enumerate(channels()):
        ev = merge(ev)
        assert all(0 < n < 256 for _, n in ev)
        t += '\nsong%d: .db %s,255' % (c, db(x for e in ev for x in e))
    return t


# ---------------------------------------------------------------- preview: PSG register log -> WAV
def render(log, path, seconds, cpu_hz=455 * 263 * 60, rate=32000):
    """log: [(cpu cycle, register 0-9, value)] as recorded by machine.Machine.psg_log."""
    import random
    rnd = random.Random(1)
    sel, main = 0, 0xff
    ch = [dict(per=0, ctl=0, bal=0xff, wave=[0] * 32, wi=0, pos=0.0, nz=0, nzv=0.0, nzpos=0.0) for _ in range(6)]
    t0 = log[0][0] if log else 0
    n = int(seconds * rate)
    out = bytearray()
    li = 0
    att = lambda steps15: 10 ** (-steps15 * 3 / 20)          # 3 dB per step of a 4-bit level
    for s in range(n):
        cyc = t0 + s * cpu_hz / rate
        while li < len(log) and log[li][0] <= cyc:
            _, r, v = log[li]; li += 1
            c = ch[sel]
            if r == 0: sel = v & 7 if v & 7 < 6 else sel
            elif r == 1: main = v
            elif r == 2: c['per'] = (c['per'] & 0xf00) | v
            elif r == 3: c['per'] = (c['per'] & 0xff) | (v & 15) << 8
            elif r == 4:
                if v & 0x40: c['wi'] = 0                       # DDA bit resets the wave write index
                c['ctl'] = v
            elif r == 5: c['bal'] = v
            elif r == 6:
                if not c['ctl'] & 0x80: c['wave'][c['wi']] = v & 31; c['wi'] = (c['wi'] + 1) & 31
            elif r == 7: c['nz'] = v
        acc = 0.0
        for i, c in enumerate(ch):
            vol = c['ctl'] & 31
            if not c['ctl'] & 0x80 or vol == 0: continue
            g = 10 ** (-(31 - vol) * 1.5 / 20) * att(15 - (main >> 4)) * att(15 - (c['bal'] >> 4))
            if i >= 4 and c['nz'] & 0x80:
                f = PSG_CLOCK / 64 / max(1, 32 - (c['nz'] & 31))
                c['nzpos'] += f / rate
                if c['nzpos'] >= 1: c['nzpos'] %= 1; c['nzv'] = rnd.choice((-1.0, 1.0))
                acc += c['nzv'] * g
            elif c['per']:
                c['pos'] = (c['pos'] + 32 * PSG_CLOCK / (32 * c['per']) / rate) % 32
                acc += (c['wave'][int(c['pos'])] - 15.5) / 15.5 * g
        out.append(max(0, min(255, int(128 + acc * 60))))
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 36 + len(out)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate, 1, 8)
                + b'data' + struct.pack('<I', len(out)) + bytes(out))


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from machine import Machine, SDCard
    from fatinject import inject
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sd = SDCard(os.path.join(root, 'sdcard_dump'))
    inject(sd, b'RGPOA   DAT', open(os.path.join(root, 'out', 'RGPOA.DAT'), 'rb').read())
    m = Machine(open(os.path.join(root, 'out', 'TOS.PCE'), 'rb').read(), sd)
    m.psg_log = []
    secs = 2 * 8 * 16 * STEP / 60 + 1
    m.run_frames(int(secs * 60) + 30)
    out = os.path.join(root, 'out', 'musica.wav')
    render(m.psg_log, out, secs)
    print('%d PSG writes -> %s (%.1f s)' % (len(m.psg_log), out, secs))
