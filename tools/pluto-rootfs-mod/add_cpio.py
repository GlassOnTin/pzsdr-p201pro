#!/usr/bin/env python3
"""Insert etc/init.d/S99dhcp-wait into the rootfs cpio (newc) before the
TRAILER!!! entry, preserving every existing byte/ownership. Then gzip and
report the MD5 (the FIT ramdisk hash algo)."""
import struct, gzip, hashlib

cpio = open('rootfs.cpio', 'rb').read()
script = open('S99dhcp-wait.sh', 'rb').read()
name = b'etc/init.d/S99dhcp-wait\x00'

def pad4(n):
    return (n + 3) & ~3

# walk to the real TRAILER!!! entry
off = 0
while True:
    hdr = cpio[off:off + 110]
    assert hdr[:6] in (b'070701', b'070702'), off
    fields = [int(hdr[6 + i * 8:6 + (i + 1) * 8], 16) for i in range(13)]
    namesize, fsize = fields[11], fields[6]
    nm = cpio[off + 110:off + 110 + namesize - 1]
    if nm == b'TRAILER!!!':
        trailer = off
        break
    off = off + pad4(110 + namesize) + pad4(fsize)

def f8(x):
    return ('%08X' % x).encode('ascii')

mode = 0o100755
hdr = (b'070701' + f8(0x01234567) + f8(mode) + f8(0) + f8(0) + f8(1) +
       f8(0) + f8(len(script)) + f8(0) + f8(0) + f8(0) + f8(0) +
       f8(len(name)) + f8(0))
assert len(hdr) == 110, len(hdr)
entry = hdr + name
entry += b'\x00' * (pad4(len(entry)) - len(entry))
entry += script
entry += b'\x00' * (pad4(len(entry)) - len(entry))
assert len(entry) % 4 == 0

new = cpio[:trailer] + entry + cpio[trailer:]
open('rootfs_new.cpio', 'wb').write(new)
with gzip.GzipFile('new_ramdisk.gz', 'wb', compresslevel=9, mtime=0) as g:
    g.write(new)
gz = open('new_ramdisk.gz', 'rb').read()
words = struct.unpack('>4I', hashlib.md5(gz).digest())
print('trailer at', trailer, 'entry bytes', len(entry))
print('new cpio size', len(new), '(was %d)' % len(cpio))
print('new_ramdisk.gz size', len(gz), '(was 5564685)')
print('MD5 words:', ' '.join('0x%08x' % w for w in words))