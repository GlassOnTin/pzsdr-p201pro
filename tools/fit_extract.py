#!/usr/bin/env python3
"""Extract images from a U-Boot FIT (DTB) and parse a legacy uImage header.

Usage: python3 -I fit_extract.py <image.ub> <uImage> <outdir>
Writes embedded FIT images (kernel/fdt/ramdisk) and the uImage payload to outdir.
"""
import struct
import sys
import os

FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9


def parse_dtb(blob):
    """Yield (path, propname, data) for every property, walking the struct block."""
    (magic, totalsize, off_struct, off_strings, off_rsv, version,
     last_comp, boot_cpu, size_strings, size_struct) = struct.unpack(">10I", blob[:40])
    if magic != 0xD00DFEED:
        raise ValueError("bad DTB magic 0x%08x" % magic)
    strings = blob[off_strings:off_strings + size_strings]
    pos = off_struct
    end = off_struct + size_struct
    stack = []
    while pos < end:
        tok = struct.unpack(">I", blob[pos:pos + 4])[0]
        pos += 4
        if tok == FDT_BEGIN_NODE:
            nul = blob.index(b"\x00", pos)
            name = blob[pos:nul].decode("utf-8", "replace")
            pos = (nul + 1 + 3) & ~3
            stack.append(name)
        elif tok == FDT_END_NODE:
            if stack:
                stack.pop()
        elif tok == FDT_PROP:
            plen, nameoff = struct.unpack(">II", blob[pos:pos + 8])
            pos += 8
            nul = strings.index(b"\x00", nameoff)
            pname = strings[nameoff:nul].decode("utf-8", "replace")
            data = blob[pos:pos + plen]
            pos = (pos + plen + 3) & ~3
            yield ("/" + "/".join(n for n in stack if n), pname, data)
        elif tok == FDT_NOP:
            pass
        elif tok == FDT_END:
            break
        else:
            raise ValueError("unknown token %d at %d" % (tok, pos))


def extract_fit(path, outdir):
    blob = open(path, "rb").read()
    # group properties by node
    nodes = {}
    for node, pname, data in parse_dtb(blob):
        nodes.setdefault(node, {})[pname] = data
    print("=== FIT images in %s ===" % os.path.basename(path))
    for node, props in nodes.items():
        if not node.startswith("/images/"):
            continue
        typ = props.get("type", b"?").decode("utf-8", "replace").rstrip("\x00")
        desc = props.get("description", b"").decode("utf-8", "replace").rstrip("\x00")
        comp = props.get("compression", b"none").decode("utf-8", "replace").rstrip("\x00")
        data = props.get("data", b"")
        safe = node.replace("/", "_").strip("_")
        out = os.path.join(outdir, "fit_" + safe + ".bin")
        if data:
            open(out, "wb").write(data)
        print("  %-28s type=%-10s comp=%-8s size=%-9d %s" %
              (node, typ, comp, len(data), desc))
        print("      -> %s" % out)


def parse_uimage(path, outdir):
    blob = open(path, "rb").read()
    (magic, hcrc, timestamp, size, load, ep, dcrc, os_, arch, typ, comp) = \
        struct.unpack(">7I4B", blob[:32])
    name = blob[32:64].split(b"\x00")[0].decode("utf-8", "replace")
    if magic != 0x27051956:
        print("=== %s: not a legacy uImage (magic 0x%08x) ===" %
              (os.path.basename(path), magic))
        return
    import datetime
    print("=== uImage header: %s ===" % os.path.basename(path))
    print("  name      : %s" % name)
    print("  created   : %s UTC" % datetime.datetime.utcfromtimestamp(timestamp))
    print("  data size : %d bytes" % size)
    print("  load addr : 0x%08x  entry: 0x%08x" % (load, ep))
    print("  os/arch   : %d/%d  type=%d  compression=%d" % (os_, arch, typ, comp))
    payload = blob[64:64 + size]
    out = os.path.join(outdir, "uImage_payload.bin")
    open(out, "wb").write(payload)
    print("  payload   -> %s" % out)


if __name__ == "__main__":
    fit, uimg, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    extract_fit(fit, outdir)
    print()
    parse_uimage(uimg, outdir)
