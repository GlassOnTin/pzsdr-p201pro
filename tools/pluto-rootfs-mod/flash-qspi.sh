#!/bin/sh
# Apply a patched Linux FIT to the PZSDR P201Pro QSPI "qspi-linux" partition
# (mtd3), so the DHCP boot fix (or any rootfs mod) also applies when booting
# QSPI with no SD card. Run from the workstation; talks to the board over the
# USB-gadget network (default 192.168.2.1, root/analog).
#
# Usage: flash-qspi.sh <padded-fit-14MB> [board-ip]
#
# The FIT must be padded with 0xFF to 0xE00000 (14680064 bytes) — the size
# qspiboot reads from QSPI offset 0x200000 (mtd3 start). Build it from the
# repacked FIT (repack_fit.py output) with:
#   python3 -c "d=open('new_image.ub','rb').read(); open('out.bin','wb').write(d+b'\xff'*(0xE00000-len(d)))"
#
# Safety: backs up mtd3 first, verifies the transferred image by MD5 before
# erasing, and verifies the readback after writing. The board must be booted
# from SD (rootfs in RAM) so mtd3 is not in use. QSPI is the fallback boot;
# SD and JTAG still recover it if anything goes wrong.
set -e
IMG="$1"
IP="${2:-192.168.2.1}"
[ -f "$IMG" ] || { echo "usage: $0 <padded-fit-14MB> [board-ip]"; exit 1; }
SZ=$(wc -c < "$IMG")
[ "$SZ" -eq 14680064 ] || { echo "image must be padded to 14680064 bytes (got $SZ)"; exit 1; }
SSH="sshpass -p analog ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$IP"
LMD5=$(md5sum "$IMG" | cut -d' ' -f1)

echo "backup mtd3 -> mtd3_backup.bin"
$SSH 'dd if=/dev/mtd3 bs=65536 count=480 2>/dev/null' > mtd3_backup.bin

echo "push image + verify"
cat "$IMG" | $SSH 'cat > /tmp/fit_qspi.bin'
RMD5=$($SSH 'md5sum /tmp/fit_qspi.bin' | cut -d' ' -f1)
[ "$LMD5" = "$RMD5" ] || { echo "transfer MD5 mismatch"; exit 1; }

echo "erase mtd3 boot region (224 x 64KiB = 14MiB) + write + sync"
$SSH 'flash_erase /dev/mtd3 0 224 >/dev/null 2>&1; dd if=/tmp/fit_qspi.bin of=/dev/mtd3 bs=65536 2>/dev/null; sync'

echo "readback verify"
$SSH 'dd if=/dev/mtd3 bs=65536 count=224 2>/dev/null' > mtd3_readback.bin
cmp "$IMG" mtd3_readback.bin && echo "QSPI write verified identical"
echo "done. Remove SD card and power cycle to boot QSPI."