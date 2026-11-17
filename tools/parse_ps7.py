import struct
import sys

blob = open(sys.argv[1], "rb").read()
w = struct.unpack("<%dI" % (len(blob) // 4), blob[:len(blob) // 4 * 4])
start = int(sys.argv[2], 0)
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 400

OPS = {0: "END", 1: "WRITE0", 2: "WRITE", 3: "MASK_WRITE", 4: "MASK_POLL", 5: "DELAY"}

i = start // 4
count = 0
arrays = 0
while i < len(w) and count < limit:
    H = w[i]
    n = H & 0xF
    op = H >> 4
    if op > 5 or n > 4:
        print("[stop: invalid header 0x%08x at 0x%05x]" % (H, i * 4))
        break
    data = w[i + 1:i + 1 + n]
    name = OPS[op]
    if op == 0:
        print("--- array end (0x%05x) ---" % (i * 4))
        arrays += 1
    elif op == 2:
        print("0x%05x WRITE      addr=0x%08x val=0x%08x" % (i * 4, data[0], data[1]))
    elif op == 3:
        print("0x%05x MASK_WRITE addr=0x%08x mask=0x%08x val=0x%08x" % (i * 4, data[0], data[1], data[2]))
    elif op == 4:
        print("0x%05x MASK_POLL  addr=0x%08x mask=0x%08x" % (i * 4, data[0], data[1]))
    elif op == 5:
        print("0x%05x DELAY      timer=0x%08x count=0x%08x" % (i * 4, data[0], data[1]))
    elif op == 1:
        print("0x%05x WRITE0     addr=0x%08x" % (i * 4, data[0]))
    i += 1 + n
    count += 1
print("parsed %d entries, %d array-ends" % (count, arrays))
