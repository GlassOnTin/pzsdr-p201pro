# Vendor FSBL init-data format

The P201Pro FSBL stores its PS7 initialization as register-write arrays in the
binary. This is the format decoded from the consumer loop at FSBL offset
`0x2b1c`, and how to extract it.

## Entry format

Each entry is a header word followed by `n` data words:

```
H = (opcode << 4) | n
```

- `n` = low nibble of H = number of data words that follow.
- `opcode` = H >> 4.

Opcodes (from the jump table at `0x2b7c`):

| opcode | header example | operation | data words |
|---|---|---|---|
| 0 | `0x00` | end of array | none |
| 1 | `0x11` | write 0 | `{addr}` |
| 2 | `0x22` | write | `{addr, value}` |
| 3 | `0x33` | mask_write (read-modify-write) | `{addr, mask, value}` |
| 4 | `0x42` | mask_poll (poll until `reg & mask != 0`) | `{addr, mask}` |
| 5 | `0x52` | delay | `{timer_addr, count}` |

The `0x22` and `0x33` bytes that look like noise in a hex dump are these
headers. mask_write computes `(reg & ~mask) | (value & mask)`.

## Arrays and silicon versions

The data region holds several arrays (MIO + DDRIOB, PLL, clock, DDR, peripherals),
each in three silicon-version variants. The FSBL reads the version from the top
nibble of `0xF8007080` and selects the variant: version 0 -> first, version 1 ->
second, version >= 2 -> third. The tested board reads `0x30800100` (version 3),
so it uses the third variant.

The DDR controller registers are at `0xF8006000` (not `0xF8000B00`); DDRIOB is at
`0xF8000B40`. The DDR array ends with two mask_polls (calibration complete at
`0xF8000B74` bit13, and DDRC init complete at `0xF8006054` bits0-2).

Some arrays write a magic `0xC5ACCE55` to scratch addresses (`0xF88xxxxx`); these
are data-integrity checks and can be skipped when generating a `ps7_init.tcl`.

## Extracting it

1. Dump the FSBL from QSPI `mtd0` (or extract it from `BOOT.bin` at offset
   `0x1700`, length `0x18008`). It is a raw binary (starts with ARM vectors), not
   an ELF.

2. `tools/crawl_ps7.py FSBL` finds the arrays (it scans for pointer words into
   the data region whose target is a valid header) and dumps every operation.

3. `tools/gen_ps7_tcl.py FSBL out.tcl` emits a `ps7_init.tcl` with `mask_write`,
   `mask_poll`, and per-phase procs (`ps7_mio_init`, `ps7_pll_init`,
   `ps7_clock_init`, `ps7_ddr_init`, `ps7_peripherals_init`, `ps7_init`). The
   array offsets for the version-3 path are hardcoded in that script; adjust if
   your FSBL differs.

4. `tools/parse_ps7.py FSBL START COUNT` parses sequentially from an offset (use
   for inspection; it stops at the first invalid header).

## Using the recovered tcl

```
xsdb
connect
targets -set -filter {name =~ "ARM*#0"}
rst -system
source ps7_init/ps7_init.tcl
ps7_init
```

This was validated to bring up DDR (DDRC init-complete bit set, DDR reads return
data). For a full JTAG Linux boot you would then remap OCM high, load the
bitstream (`fpga -f`), load kernel/DTB/ramdisk, set `r0=0 r1=~0 r2=dtb_addr
pc=kernel_entry`, and `con`. On the tested board that reached the kernel but hung
before USB gadget init (unresolved).

## Diffing and patching FSBLs

- `tools/diff_all.py ORIG NEW` lists every register-init difference (write and
  mask_write) between two FSBLs.
- `tools/diff_mio.py ORIG NEW` focuses on MIO/DDRIOB/GPIOB pins.
- `tools/patch_fsbl_addrs.py ORIG NEW OUT ADDR[,ADDR...]` reverts the write
  values for chosen addresses in NEW to ORIG's values (last occurrence per
  address). Used for the bisection in `ethernet-regression.md`.
- `tools/patch_fsbl_mio.py ORIG NEW OUT` reverts all MIO-range writes.

To boot a patched FSBL, splice it into `BOOT.bin` at `0x1700` (same `0x18008`
length). The boot-header and partition checksums cover headers, not the FSBL
payload, so the splice is valid without recomputing checksums.