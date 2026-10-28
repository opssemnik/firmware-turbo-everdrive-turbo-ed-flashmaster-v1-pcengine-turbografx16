"""Test helper: put a file into the ROOT of an emulated FAT32 card (SDCard overlay only).

The card image itself is never written; sectors go to SDCard.overlay.
"""
import struct


def inject(sd, name83, data):
    """name83: 11-byte 8.3 name, e.g. b'RGPOA   DAT'. Returns first data LBA."""
    mbr = sd.block(0)
    part = struct.unpack_from('<I', mbr, 0x1c6)[0] if mbr[0x1fe:] == b'\x55\xaa' and mbr[0x1c2] in (0x0b, 0x0c) else 0
    bpb = sd.block(part)
    spc = bpb[13]; res = struct.unpack_from('<H', bpb, 14)[0]; nf = bpb[16]
    fsz = struct.unpack_from('<I', bpb, 0x24)[0]; rootc = struct.unpack_from('<I', bpb, 0x2c)[0]
    fat = part + res; datab = fat + nf * fsz
    c2l = lambda c: datab + (c - 2) * spc
    need = max(1, -(-len(data) // (spc * 512)))
    # contiguous free run in the FAT
    run, start, c = 0, None, 2
    cache = {}
    def fat_get(c):
        s, o = divmod(c * 4, 512)
        if s not in cache: cache[s] = bytearray(sd.block(fat + s))
        return struct.unpack_from('<I', cache[s], o)[0] & 0x0fffffff
    def fat_set(c, v):
        s, o = divmod(c * 4, 512)
        fat_get(c); struct.pack_into('<I', cache[s], o, v)
    while run < need:
        if fat_get(c) == 0:
            if run == 0: start = c
            run += 1
        else:
            run = 0
        c += 1
    for i in range(need):
        fat_set(start + i, start + i + 1 if i < need - 1 else 0x0fffffff)
    for s, buf in cache.items():
        for k in range(nf):
            sd.overlay[fat + k * fsz + s] = bytes(buf)
    padded = data + b'\0' * (-len(data) % 512)
    for i in range(len(padded) // 512):
        sd.overlay[c2l(start) + i] = padded[i * 512:(i + 1) * 512]
    # directory entry in the root's first cluster
    for s in range(spc):
        lba = c2l(rootc) + s
        sec = bytearray(sd.block(lba))
        for e in range(16):
            if sec[e * 32] in (0, 0xe5):
                ent = bytearray(32)
                ent[0:11] = name83; ent[11] = 0x20
                struct.pack_into('<H', ent, 20, start >> 16)
                struct.pack_into('<H', ent, 26, start & 0xffff)
                struct.pack_into('<I', ent, 28, len(data))
                sec[e * 32:e * 32 + 32] = ent
                sd.overlay[lba] = bytes(sec)
                return c2l(start)
    raise RuntimeError('root directory full')


def inject_dir(sd, name83, files):
    """Test helper: create a root subdirectory with SFN-only files [(name83, data)]. Returns
    (dir cluster, [file clusters])."""
    mbr = sd.block(0)
    part = struct.unpack_from('<I', mbr, 0x1c6)[0]
    bpb = sd.block(part)
    spc = bpb[13]; res = struct.unpack_from('<H', bpb, 14)[0]; nf = bpb[16]
    fsz = struct.unpack_from('<I', bpb, 0x24)[0]; rootc = struct.unpack_from('<I', bpb, 0x2c)[0]
    fat = part + res; datab = fat + nf * fsz
    c2l = lambda c: datab + (c - 2) * spc
    cache = {}
    def fat_get(c):
        s, o = divmod(c * 4, 512)
        if s not in cache: cache[s] = bytearray(sd.overlay.get(fat + s, sd.block(fat + s)))
        return struct.unpack_from('<I', cache[s], o)[0] & 0x0fffffff
    def fat_set(c, v):
        s, o = divmod(c * 4, 512); fat_get(c); struct.pack_into('<I', cache[s], o, v)
    def alloc(n):
        out, c = [], 2
        while len(out) < n:
            if fat_get(c) == 0: out.append(c); fat_set(c, 0x0fffffff)
            c += 1
        for a, b in zip(out, out[1:]): fat_set(a, b)
        return out
    ents = (len(files) + 2) * 32
    dcl = alloc(-(-ents // (spc * 512)))
    fcl = []
    raw = bytearray()
    def ent(n, attr, cl, size):
        e = bytearray(32); e[0:11] = n; e[11] = attr
        struct.pack_into('<H', e, 20, cl >> 16); struct.pack_into('<H', e, 26, cl & 0xffff)
        struct.pack_into('<I', e, 28, size); return e
    raw += ent(b'.          ', 0x10, dcl[0], 0) + ent(b'..         ', 0x10, 0, 0)
    for n, data in files:
        c = alloc(1)[0]; fcl.append(c)
        sd.overlay[c2l(c)] = data.ljust(512, b'\0')[:512]
        raw += ent(n, 0x20, c, len(data))
    raw += b'\0' * (-len(raw) % (spc * 512))
    for i, c in enumerate(dcl):
        for s in range(spc):
            o = (i * spc + s) * 512
            sd.overlay[c2l(c) + s] = bytes(raw[o:o + 512])
    for s, buf in cache.items():
        for k in range(nf): sd.overlay[fat + k * fsz + s] = bytes(buf)
    for s in range(spc):
        lba = c2l(rootc) + s
        sec = bytearray(sd.overlay.get(lba, sd.block(lba)))
        for e in range(16):
            if sec[e * 32] in (0, 0xe5):
                sec[e * 32:e * 32 + 32] = ent(name83, 0x10, dcl[0], 0)
                sd.overlay[lba] = bytes(sec)
                return dcl[0], fcl
    raise RuntimeError('root directory full')
