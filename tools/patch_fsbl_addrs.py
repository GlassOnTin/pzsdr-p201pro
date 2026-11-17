import struct
import sys

# Usage: patch_fsbl_addrs.py ORIG NEW OUT ADDR[,ADDR...]
# Revert write/mask_write values for the listed addresses in NEW to the original
# (last occurrence per address). Handles op2 (write) and op3 (mask_write).
orig = open(sys.argv[1], "rb").read()
new = bytearray(open(sys.argv[2], "rb").read())
targets = set(int(x, 0) for x in sys.argv[4].split(","))


def words(b):
    return struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])


ow = words(orig)
nw = words(new)

omap = {}
for i in range(len(ow) - 3):
    H = ow[i]
    op, n = H >> 4, H & 0xF
    if op == 3 and n == 3 and ow[i + 1] in targets:
        omap[ow[i + 1]] = (3, ow[i + 3])
    elif op == 2 and n == 2 and ow[i + 1] in targets:
        omap[ow[i + 1]] = (2, ow[i + 2])

patched = 0
for i in range(len(nw) - 3):
    H = nw[i]
    op, n = H >> 4, H & 0xF
    if op == 3 and n == 3 and nw[i + 1] in omap:
        if nw[i + 3] != omap[nw[i + 1]][1]:
            struct.pack_into("<I", new, (i + 3) * 4, omap[nw[i + 1]][1])
            patched += 1
    elif op == 2 and n == 2 and nw[i + 1] in omap:
        if nw[i + 2] != omap[nw[i + 1]][1]:
            struct.pack_into("<I", new, (i + 2) * 4, omap[nw[i + 1]][1])
            patched += 1

open(sys.argv[3], "wb").write(new)
print("reverted %d write values for %s" % (patched, sys.argv[4]))
