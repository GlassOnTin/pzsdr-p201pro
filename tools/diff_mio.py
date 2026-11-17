import struct
import sys


def load(path):
    b = open(path, "rb").read()
    return struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])


def mio_writes(w):
    # mask_write entries: header 0x33 (op3,n3) -> addr,mask,val
    out = {}
    for i in range(len(w) - 3):
        if w[i] == 0x33:
            a, m, v = w[i + 1], w[i + 2], w[i + 3]
            if 0xF8000700 <= a <= 0xF80007D4 or 0xF8000B40 <= a <= 0xF8000B74 or a == 0xF8000830:
                out.setdefault(a, []).append((m, v))
    return out


a = mio_writes(load(sys.argv[1]))
b = mio_writes(load(sys.argv[2]))
print("addr        ORIGINAL (mask,val)                 NEW (mask,val)")
for addr in sorted(set(a) | set(b)):
    oa = a.get(addr, [])
    ob = b.get(addr, [])
    # compare the distinct value sets
    sa = sorted(set(oa))
    sb = sorted(set(ob))
    mark = "  " if sa == sb else "* "
    fa = " ".join("(%08x,%08x)" % t for t in sa)
    fb = " ".join("(%08x,%08x)" % t for t in sb)
    print("%s0x%08x  %-38s  %s" % (mark, addr, fa, fb))
print("\n* = differs between original and new FSBL")
