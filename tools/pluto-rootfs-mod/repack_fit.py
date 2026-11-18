#!/usr/bin/env python3
"""Rebuild the FIT DTS: replace each image's inline data byte-array with
/incbin/ of the extracted sub-image (ramdisk -> modified new_ramdisk.gz),
and update the ramdisk data-size + MD5 hash. Compile with dtc afterwards."""
import re

dts = open('fit.dts').read()
files = [
    'extracted/fit_images_fdt@1.bin',
    'extracted/fit_images_fdt@2.bin',
    'extracted/fit_images_fdt@3.bin',
    'extracted/fit_images_fpga@1.bin',
    'extracted/fit_images_linux_kernel@1.bin',
    'new_ramdisk.gz',
]
it = iter(files)
count = [0]

def repl(m):
    f = next(it)
    count[0] += 1
    return 'data = /incbin/("%s");' % f

dts2 = re.sub(r'data\s*=\s*(?:\[[^\]]*\]|<[^>]*>)\s*;', repl, dts)
assert count[0] == 6, count[0]

NEW_SIZE = 5564880
NEW_HASH = '0x68c20584 0xd89a9ef0 0x734c20ca 0xe73b3b8f'
idx = dts2.index('ramdisk@1 {')
cfg = dts2.index('configurations', idx)
region = dts2[idx:cfg]
region, n1 = re.subn(r'data-size\s*=\s*<[^>]*>;',
                     'data-size = <0x%x>;' % NEW_SIZE, region)
region, n2 = re.subn(r'value\s*=\s*<[^>]*>;',
                     'value = <%s>;' % NEW_HASH, region)
# original ramdisk node has no data-size (size is implicit from data length,
# which /incbin/ sets); only the hash must be updated.
assert n2 == 1, n2
dts2 = dts2[:idx] + region + dts2[cfg:]
open('fit_new.dts', 'w').write(dts2)
print('replaced %d data arrays; ramdisk data-size=%d hash updated' % (count[0], NEW_SIZE))