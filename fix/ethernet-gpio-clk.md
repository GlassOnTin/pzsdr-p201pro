# Ethernet fix: GPIO_CLK_CTRL CLKACT0

The 2026-11-16 FSBL gates the GPIO peripheral clock, which disables the PHY's
reset/control GPIO and kills ethernet receive. The fix is to set bit 4
(`CLKACT0`) of `GPIO_CLK_CTRL` (SLCR `0xF8000138`): write `0x11` instead of
`0x01`. Full diagnosis in `../docs/ethernet-regression.md`.

Three ways to apply it, in order of permanence.

## 1. Runtime (no reflash, needs re-applying each boot)

On the device (SSH `root@192.168.2.1`, password `analog`):

```
devmem 0xF8000008 32 0xDF0D     # SLCR unlock
devmem 0xF8000138 32 0x11       # GPIO_CLK_CTRL: divisor 1 + CLKACT0
```

Or in U-Boot:

```
mw f8000008 df0d
mw f8000138 11
```

To make it persistent without reflashing the FSBL, add those two writes to the
U-Boot boot script (e.g. a `uenvcmd` in `uEnv.txt` that runs them before booting
the kernel).

## 2. Patch the FSBL (minimal, one register)

Keep the new FSBL and change only its `GPIO_CLK_CTRL` writes from `0x01` to
`0x11`. With the original FSBL dumped as `fsbl_orig.bin` and the new FSBL as
`new_fsbl.bin` (see `../docs/ps7-init-format.md` for extraction):

```
python3 tools/patch_fsbl_addrs.py fsbl_orig.bin new_fsbl.bin new_fsbl_fix138.bin 0xF8000138
```

Then splice the patched FSBL into `BOOT.bin` at offset `0x1700` (length
`0x18008`, unchanged):

```
python3 - <<'PY'
nb = open("BOOT.bin","rb").read()
fm = open("new_fsbl_fix138.bin","rb").read()
assert len(fm) == 0x18008
open("BOOT_fixed.bin","wb").write(nb[:0x1700] + fm + nb[0x1700+0x18008:])
PY
```

Write `BOOT_fixed.bin` to the SD as `BOOT.bin`. The boot/partition checksums
cover headers, not the FSBL payload, so no checksum recomputation is needed.

## 3. Use the original FSBL

Splice the original FSBL (from QSPI `mtd0`) into the new `BOOT.bin` the same way.
This reverts all FSBL changes, not just the GPIO clock. Use it if you want the
known-good original PS init entirely.

## Verify

After booting, on the device:

```
devmem 0xF8000138                       # expect 0x00000011
cat /sys/class/net/eth0/statistics/rx_packets   # should increment
ifconfig eth0:1 192.168.0.222 netmask 255.255.255.0 up
ping -c 3 192.168.0.1                    # your LAN gateway; expect replies
```

`rx_packets` increasing and bidirectional ping passing confirms the fix.

## Note on the 5.15 firmware

This fix addresses the stock-kernel RX failure. The newer Linux 5.15 vendor
firmware has a separate MDIO fault (no PHY at any address) from a different
ethernet topology in its devicetree; this fix alone does not make that firmware
work. See `../docs/ethernet-regression.md`.