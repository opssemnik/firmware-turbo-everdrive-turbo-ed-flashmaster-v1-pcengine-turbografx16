"""Model of how the OS numbers directory entries (verified against the OS in the emulator)."""
import struct

def fs_params(sd):
    mbr = sd.block(0)
    part = struct.unpack_from('<I', mbr, 0x1c6)[0]
    bpb = sd.block(part)
    spc = bpb[13]; res = struct.unpack_from('<H', bpb, 14)[0]; nf = bpb[16]
    fsz = struct.unpack_from('<I', bpb, 0x24)[0]
    fat = part + res; data = fat + nf * fsz
    return spc, fat, data

def chain(sd, c, fat):
    out = []
    while 2 <= c < 0x0ffffff8 and len(out) < 4096:
        out.append(c)
        s, o = divmod(c * 4, 512)
        c = struct.unpack_from('<I', sd.block(fat + s), o)[0] & 0x0fffffff
    return out

def raw_entries(sd, dircl):
    spc, fat, data = fs_params(sd)
    for c in chain(sd, dircl, fat):
        for s in range(spc):
            sec = sd.block(data + (c - 2) * spc + s)
            for e in range(16):
                ent = sec[e * 32:e * 32 + 32]
                if ent[0] == 0: return
                yield ent

def os_list(sd, dircl, skip):
    """[(first cluster, attr, sfn)] in the order the OS numbers them, given a skip rule."""
    out = []
    for ent in raw_entries(sd, dircl):
        attr = ent[11]
        if skip(ent, attr): continue
        cl = struct.unpack_from('<H', ent, 26)[0] | struct.unpack_from('<H', ent, 20)[0] << 16
        out.append((cl, attr, ent[:11]))
    return out
