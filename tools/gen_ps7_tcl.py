import struct
import sys

blob = open(sys.argv[1], "rb").read()
w = struct.unpack("<%dI" % (len(blob) // 4), blob[:len(blob) // 4 * 4])
out = sys.argv[2]


def parse(s):
    i = s // 4
    ops = []
    while i < len(w):
        H = w[i]
        op, n = H >> 4, H & 0xF
        if op > 5 or n > 4:
            break
        data = w[i + 1:i + 1 + n]
        ops.append((op, data))
        i += 1 + n
        if op == 0:
            break
    return ops


# Board-exact arrays recovered from the vendor FSBL (silicon version 3 path).
PHASES = [
    ("ps7_mio_init", 0x10bd0),
    ("ps7_pll_init", 0x11054),
    ("ps7_clock_init", 0x123b8),
    ("ps7_ddr_init", 0x12494),
    ("ps7_peripherals_init", 0x129b0),
]

HEADER = '''# ps7_init.tcl — board-exact Zynq-7000 PS7 initialization for PUZHI PZSDR P201Pro
# (Zynq XC7Z020 + AD9361/AD9363, 1 GiB DDR3).
#
# Recovered by reverse-engineering the vendor FSBL dumped from QSPI mtd0.
# The FSBL stores ps7_init data as entries {header=(opcode<<4)|n, n data words}:
#   opcode 2 = write(addr,val); 3 = mask_write(addr,mask,val);
#   opcode 4 = mask_poll(addr,mask); 5 = delay; 1 = write0; 0 = end.
# Silicon version register 0xF8007080 = 0x30800100 (version 3) selects these arrays.
#
# Usage (xsdb):  source ps7_init.tcl ; ps7_init
# Generated tool: tools/gen_ps7_tcl.py

proc mask_write {addr mask val} {
    scan [lindex [mrd -force $addr 1] 1] %x cur
    set new [expr {($cur & ~$mask) | ($val & $mask)}]
    mwr -force $addr $new
}

proc mask_poll {addr mask} {
    set timeout 2000000
    while {1} {
        scan [lindex [mrd -force $addr 1] 1] %x cur
        if {($cur & $mask) != 0} { break }
        incr timeout -1
        if {$timeout <= 0} { error "mask_poll timeout at $addr mask $mask" }
    }
}

proc ps7_delay {count} { after 1 }

'''

body = []
for name, start in PHASES:
    ops = parse(start)
    body.append("proc %s {} {" % name)
    for op, data in ops:
        if op == 2:
            body.append("    mwr -force 0x%08x 0x%08x" % (data[0], data[1]))
        elif op == 3:
            body.append("    mask_write 0x%08x 0x%08x 0x%08x" % (data[0], data[1], data[2]))
        elif op == 4:
            body.append("    mask_poll 0x%08x 0x%08x" % (data[0], data[1]))
        elif op == 5:
            body.append("    ps7_delay 0x%08x" % data[1])
        elif op == 1:
            body.append("    mwr -force 0x%08x 0x0" % data[0])
    body.append("}")
    body.append("")

body.append("proc ps7_init {} {")
for name, _ in PHASES:
    body.append("    %s" % name)
body.append("    puts \"ps7_init: PZSDR P201Pro PS7 initialized (DDR up)\"")
body.append("}")
body.append("")

with open(out, "w") as f:
    f.write(HEADER + "\n".join(body))
print("wrote %s" % out)
for name, start in PHASES:
    print("  %-22s <- array 0x%05x (%d ops)" % (name, start, len(parse(start)) - 1))
