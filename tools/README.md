# Tools

Python 3 (standard library only) and one small C program. Run Python with `-I`
and pass file paths as arguments. These operate on firmware you dump from your
own board; no vendor binaries are included in this repo.

## FIT / uImage parsing

- `fit_extract.py IMAGE.UB UIMAGE OUTDIR` — extracts the embedded images
  (kernel, FDT, ramdisk, FPGA bitstream) from a U-Boot FIT (`image.ub`) and
  parses a legacy `uImage` header. The FIT is a DTB; this walks it directly.

## FSBL init-data extraction

See `../docs/ps7-init-format.md` for the data format.

- `crawl_ps7.py FSBL` — finds all init arrays and dumps every operation to
  `/tmp/ps7_arrays.txt`, with a per-array summary.
- `parse_ps7.py FSBL START COUNT` — parses sequentially from a byte offset
  (inspection; stops at the first invalid header).
- `gen_ps7_tcl.py FSBL OUT.tcl` — generates a `ps7_init.tcl` (mask_write /
  mask_poll procs per phase). Version-3 array offsets are hardcoded; adjust for
  a different FSBL.

## Diffing and patching FSBLs

- `diff_all.py ORIG NEW` — every register-init difference (write + mask_write).
- `diff_mio.py ORIG NEW` — MIO / DDRIOB / GPIOB pin differences.
- `patch_fsbl_addrs.py ORIG NEW OUT ADDR[,ADDR...]` — revert the write values for
  chosen addresses in NEW to ORIG's values. Used for the ethernet bisection.
- `patch_fsbl_mio.py ORIG NEW OUT` — revert all MIO-range writes.

## MDIO

- `mdiotool.c` — clause-22 MDIO read/write via the kernel `SIOCGMIIREG`/
  `SIOCSMIIREG` ioctl. Cross-compile for the board, e.g.:

  ```
  arm-linux-gnueabihf-gcc -static -O2 -o mdiotool mdiotool.c
  ```

  Usage on the board: `mdiotool eth0 PHY dump`, `mdiotool eth0 PHY REG [VALUE]`,
  `mdiotool eth0 PHY page PAGE REG [VALUE]`. Note: with the stock GMII2RGMII
  converter the PHY sits behind a child MDIO bus, so raw ioctl reads of the PHY
  may return 0; U-Boot `mii` commands are more reliable for that design.

## JTAG helpers

The `xsdb` scripts used during the investigation (ps7_init test, JTAG boot,
register probes) are described in `../docs/ps7-init-format.md` and
`../docs/hardware.md`. They are short enough to recreate from those docs.