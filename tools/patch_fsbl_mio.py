import struct
import sys

# Usage: patch_fsbl_mio.py ORIG_FSBL NEW_FSBL OUT
# Revert every MIO-range mask_write value in NEW_FSBL to the original (v3 = last
# occurrence per address), leaving GPIO/clock/DDR changes intact.
orig = open(sys.argv[1], "rb").read()
new = bytearray(open(sys.argv[2], "rb").read())


def words(b):
    return struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])


ow = words(orig)
nw = words(new)
MIO = lambda a: 0xF8000700 <= a <= 0xF80007D4

# original value per MIO addr (last occurrence = silicon v3 variant)
omap = {}
for i in range(len(ow) - 3):
    if ow[i] == 0x33 and MIO(ow[i + 1]):
        omap[ow[i + 1]] = ow[i + 3]

patched = 0
for i in range(len(nw) - 3):
    if nw[i] == 0x33 and MIO(nw[i + 1]) and nw[i + 1] in omap:
        if nw[i + 3] != omap[nw[i + 1]]:
            struct.pack_into("<I", new, (i + 3) * 4, omap[nw[i + 1]])
            patched += 1

open(sys.argv[3], "wb").write(new)
print("reverted %d MIO mask_write values to original" % patched)
