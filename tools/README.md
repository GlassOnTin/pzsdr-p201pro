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

## Bitstream routing trace

- `route_trace.py` — active-configuration routing tracer. Builds the wire-node
  graph from a prjxray db (`tilegrid` + `tileconn`), adds the PIPs actually set
  in a FASM file, and reports connected components / BFS traces between wires.
  Unlike prjxray `simpleroute` (possible routes from the full PIP db), this uses
  only the active PIPs, so it reflects the configured design.

  ```
  route_trace.py --db-root <prjxray-db>/zynq7 --part xc7z020 \
      --fasm design.fasm --components
  route_trace.py ... --trace INT_L_X0Y16/SW2END1 INT_L_X0Y16/NL1BEG1
  route_trace.py ... --site RIOI3_X73Y103/IOI_OCLKM_1
  ```

  Upstreamed as [f4pga/prjxray#2579](https://github.com/f4pga/prjxray/pull/2579).
  Known gaps (toward full GEM0-MDIO-to-PHY tracing, issues #1/#3): IOI
  OLOGIC/ILOGIC mux wire-name mapping (`--iomux` is experimental), and functional
  EMIO naming in the zynq7 db (PSS wires are generic `PSS1_LOGIC_OUTS#_#`, so a
  Zynq TRM EMIO-index cross-reference is needed to locate GEM0 MDIO).