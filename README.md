# PZSDR P201Pro open notes

Reverse-engineering notes, recovery tools, and a getting-started guide for the
PUZHI PZSDR P201Pro SDR. The vendor publishes no design files or documentation
for this board, so this repo collects what we learned by reading the firmware.

License: AGPL-3.0 (see `LICENSE`). The tools and recovered init data are free to
use, modify, and redistribute under that license.

## The board

- PUZHI PZSDR P201Pro (also sold as P203Pro, AD9363 variant, pin-compatible).
- Zynq XC7Z020 (dual Cortex-A9) + AD9361, 1 GiB DDR3, 256 Mb QSPI flash.
- RTL8211F gigabit ethernet through a PL GMII-to-RGMII converter.
- Pluto+ derivative. Firmware is ADI PlutoSDR-based (kernel 5.10), boots from
  SD card or QSPI. A boot-mode switch selects SD/QSPI or JTAG.
- USB-C is a "3-in-1" port: JTAG + UART + USB OTG, via an onboard FT2232
  (Digilent JTAG-SMT1) and a USB hub.

## Maia SDR firmware (`pzsdr_p201pro`)

Maia SDR runs on the PZSDR P201Pro via the maintained fork at
[GlassOnTin/plutosdr-fw](https://github.com/GlassOnTin/plutosdr-fw) (HDL in
[GlassOnTin/maia-sdr](https://github.com/GlassOnTin/maia-sdr)):

- Prebuilt DFU images (`pzsdr_p201pro.dfu` + `uboot-env.dfu`) and flashing guide:
  [GlassOnTin/plutosdr-fw releases](https://github.com/GlassOnTin/plutosdr-fw/releases/latest)
- Traced AD9361 CMOS/SPI pinout and Vivado constraints:
  `bitstream-analysis/ad9361-spi-pinout.md` and
  `bitstream-analysis/pzsdr-p201pro-system_constr.xdc`
- Flash from U-Boot DFU (`run dfu_sf` on `/dev/ttyUSB1`, then `dfu-util -d 0456:b674`)
  and cold power-cycle afterward. Do not write QSPI from Linux (`pluto.frm`,
  `flashcp`, or `fw_setenv`), as the Linux `spi-nor` driver mis-addresses the
  board's Winbond `W25Q256` flash.

## Getting started

### Serial console (no soldering)

The console is already available over the USB-C port. The onboard FT2232
exposes JTAG on port A and the PS UART1 console on port B. On Linux the console
is `/dev/ttyUSB1` (the second FTDI serial port), **115200 8N1, 3.3V**.

```
picocom -b 115200 /dev/ttyUSB1
```

The console UART is PS UART1 on MIO12 (TX) / MIO13 (RX). If you prefer to wire a
separate 3.3V USB-UART adapter, those are the pins; do not use 5V logic.

### JTAG

The same FT2232 port A is a standard Xilinx/Digilent JTAG cable. It works with
`hw_server` and `xsdb` (Vivado/Vitis). On Linux the Digilent Adept runtime must
be installed; `djtgcfg enum` should list "Digilent JTAG-SMT1".

### Boot modes

- SD card inserted, switch in SD/QSPI position: boots SD (`BOOT.bin` + `uEnv.txt`
  + `image.ub`).
- No SD card, switch in SD/QSPI position: boots QSPI.
- Switch in JTAG position: BootROM waits for JTAG; nothing boots until you load
  firmware over JTAG.

### Ethernet fix (the important one)

A 2026-11-16 vendor firmware update breaks ethernet receive: link comes up at
1 Gbps and transmit works, but the board receives nothing. The cause is one bit
in the FSBL that selects the wrong source for GEM0's RX signals (MIO instead of
EMIO). See `fix/ethernet-gem0-rclk.md` for the one-line fix and
`docs/ethernet-regression.md` for the full diagnosis.

Quick runtime fix (until you reflash):

```
devmem 0xF8000008 32 0xDF0D     # unlock SLCR
devmem 0xF8000138 32 0x11       # GEM0_RCLK_CTRL: SRCSEL=EMIO (bit 4), CLKACT=1
```

## Repo layout

- `docs/hardware.md` — board interfaces, console/JTAG, boot, UART pins.
- `docs/ethernet-regression.md` — the ethernet failure: diagnosis and root cause.
- `docs/ps7-init-format.md` — the vendor FSBL init-data format, decoded.
- `fix/ethernet-gem0-rclk.md` — the one-bit ethernet fix, three ways to apply it.
- `fix/qspi-env.md` — repair the incomplete QSPI U-Boot environment so QSPI
  autoboots.
- `ps7_init/ps7_init.tcl` — board-exact Zynq PS7 init recovered from the FSBL,
  validated over JTAG (DDR bring-up). Usable with `xsdb` for JTAG boot.
- `tools/` — extraction and analysis tools (see `tools/README.md`):
  FIT/uImage parsing, FSBL init-data extraction, `ps7_init.tcl` generation,
  register-init diffing, FSBL patching, and a small MDIO ioctl tool.
- `docs/bitstream-analysis.md` + `bitstream-analysis/` — prjxray IOB pin-usage
  diff of the stock vs new bitstream (characterizes the 5.15 MDIO fault, #1).

## Extracting firmware from your own board

This repo does not redistribute the vendor's firmware binaries (FSBL, U-Boot,
kernel FIT, QSPI dumps). To work on them, dump them from a board you own:

```
# over the USB gadget network (device is 192.168.2.1, root/analog)
ssh root@192.168.2.1 'cat /dev/mtd0' > mtd0_fsbl_uboot.bin   # FSBL + U-Boot
ssh root@192.168.2.1 'cat /dev/mtd3' > mtd3_linux.bin       # kernel FIT
ssh root@192.168.2.1 'cat /sd0/BOOT.bin' > BOOT.bin         # SD boot image
```

Then use `tools/fit_extract.py`, `tools/crawl_ps7.py`, and
`tools/gen_ps7_tcl.py` to extract the init data and regenerate `ps7_init.tcl`.
See `docs/ps7-init-format.md`.

## Status and limitations

- The ethernet root cause and fix are verified (FSBL bisection plus direct
  register writes). See the regression doc for what was ruled out.
- The newer Linux 5.15 vendor firmware has a separate MDIO fault (no PHY at any
  address), traced to the new direct-RGMII bitstream stranding GEM0 MDIO (no
  path to any IOB) and dropping the MDIO IOB pin. The `SRCSEL` fix, MIO
  re-routing, and a full MDIO scan do not resolve it. Use the stock firmware
  with the `SRCSEL` fix. See `docs/ethernet-regression.md`,
  `docs/bitstream-analysis.md`, and issue #1.
- The QSPI U-Boot environment on the tested board was incomplete (`read_sf`
  undefined), so QSPI autoboot fell into DFU. Repaired and verified; see
  `fix/qspi-env.md`.
- The recovered `ps7_init.tcl` was validated for DDR bring-up over JTAG. A full
  JTAG Linux boot reached the kernel but hung before USB gadget init; that hang
  is separate from the ethernet issue and is not resolved here.

## Contributing

Issues and merge requests welcome, especially: the 5.15 firmware MDIO topology,
a clean QSPI environment repair, and schematic confirmation of the PHY control
GPIO net.

## Upstream contributions

- prjxray build fixes (GCC 15 / CMake 4): [f4pga/prjxray#2578](https://github.com/f4pga/prjxray/pull/2578).
- prjxray active-configuration routing tracer: [f4pga/prjxray#2579](https://github.com/f4pga/prjxray/pull/2579).
- P201Pro ethernet diagnosis + fix: [plutoplus/plutoplus#70](https://github.com/plutoplus/plutoplus/issues/70).
- FSBL GEM0_RCLK_CTRL note for derivatives: [analogdevicesinc/plutosdr-fw#114](https://github.com/analogdevicesinc/plutosdr-fw/issues/114).