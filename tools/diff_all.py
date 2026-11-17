import struct
import sys


def load(path):
    b = open(path, "rb").read()
    return struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])


def writes(w):
    out = {}
    for i in range(len(w) - 3):
        H = w[i]
        op, n = H >> 4, H & 0xF
        if op == 3 and n == 3:           # mask_write
            a, m, v = w[i + 1], w[i + 2], w[i + 3]
            out.setdefault(a, set()).add((m, v))
        elif op == 2 and n == 2:         # full write
            a, v = w[i + 1], w[i + 2]
            out.setdefault(a, set()).add((0xFFFFFFFF, v))
    return out


a = writes(load(sys.argv[1]))
b = writes(load(sys.argv[2]))
print("Differing register init (ORIGINAL vs NEW FSBL):")
print("addr        original (mask,val)                       new (mask,val)")
nd = 0
for addr in sorted(set(a) | set(b)):
    sa = sorted(a.get(addr, set()))
    sb = sorted(b.get(addr, set()))
    if sa != sb:
        nd += 1
        fa = " ".join("(%08x,%08x)" % t for t in sa)
        fb = " ".join("(%08x,%08x)" % t for t in sb)
        print("0x%08x  %-40s  %s" % (addr, fa, fb))
print("\n%d differing addresses" % nd)
