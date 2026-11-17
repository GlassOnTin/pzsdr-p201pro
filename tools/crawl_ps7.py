import struct
import sys

blob = open(sys.argv[1], "rb").read()
w = struct.unpack("<%dI" % (len(blob) // 4), blob[:len(blob) // 4 * 4])
OPS = {0: "END", 1: "WRITE0", 2: "WRITE", 3: "MASK_WRITE", 4: "MASK_POLL", 5: "DELAY"}


def valid_header(H):
    return (H >> 4) <= 5 and (H & 0xF) <= 4


starts = set()
for i in range(len(w)):
    v = w[i]
    if 0x10000 <= v < 0x13000 and v % 4 == 0:
        j = v // 4
        if j < len(w) and valid_header(w[j]) and (w[j] >> 4) > 0:
            starts.add(v)


def parse(s):
    i = s // 4
    out = []
    while i < len(w):
        H = w[i]
        if not valid_header(H):
            break
        n = H & 0xF
        op = H >> 4
        data = w[i + 1:i + 1 + n]
        out.append((i * 4, op, data))
        i += 1 + n
        if op == 0:
            break
    return out


allarrays = {}
for s in sorted(starts):
    ops = parse(s)
    if not ops:
        continue
    # keep only arrays that end cleanly with END and have >1 real op
    real = [o for o in ops if o[1] != 0]
    if not real or ops[-1][1] != 0:
        continue
    allarrays[s] = ops

with open("/tmp/ps7_arrays.txt", "w") as f:
    for s, ops in sorted(allarrays.items()):
        addrs = [o[2][0] for o in ops if o[1] in (1, 2, 3, 4) and o[2]]
        polls = sum(1 for o in ops if o[1] == 4)
        f.write("=== array 0x%05x : %d ops, %d polls, addrs 0x%08x-0x%08x ===\n"
                % (s, len(ops) - 1, polls, min(addrs), max(addrs)))
        for off, op, data in ops:
            if op == 0:
                f.write("  END\n")
            elif op == 2:
                f.write("  WRITE      0x%08x = 0x%08x\n" % (data[0], data[1]))
            elif op == 3:
                f.write("  MASK_WRITE 0x%08x mask=0x%08x val=0x%08x\n" % (data[0], data[1], data[2]))
            elif op == 4:
                f.write("  MASK_POLL  0x%08x mask=0x%08x\n" % (data[0], data[1]))
            elif op == 5:
                f.write("  DELAY      timer=0x%08x count=0x%08x\n" % (data[0], data[1]))
            elif op == 1:
                f.write("  WRITE0     0x%08x\n" % data[0])

for s, ops in sorted(allarrays.items()):
    addrs = [o[2][0] for o in ops if o[1] in (1, 2, 3, 4) and o[2]]
    polls = sum(1 for o in ops if o[1] == 4)
    print("array 0x%05x : %3d ops, %d polls, addrs 0x%08x-0x%08x"
          % (s, len(ops) - 1, polls, min(addrs), max(addrs)))
print("total arrays:", len(allarrays))
