# P201Pro hardware notes

Identified from the board, the vendor datasheet, and the firmware. The vendor
publishes no schematic; pin-level details below are from the Pluto+ reference
schematic (the P201Pro is a Pluto+ derivative) and from the firmware's MIO init.

## SoC and memory

- Zynq XC7Z020-2CLG400 (dual Cortex-A9, 85K logic cells). Silicon version
  register `0xF8007080` reads `0x30800100` (version 3).
- 1 GiB DDR3.
- 256 Mb QSPI flash (Winbond W25Q256). Partition map (from the kernel):
  - `mtd0` `qspi-fsbl-uboot` 1 MiB (FSBL + U-Boot)
  - `mtd1` `qspi-uboot-env` 128 KiB
  - `mtd2` `qspi-nvmfs` 896 KiB
  - `mtd3` `qspi-linux` 30 MiB (kernel FIT image)
- AD9361 RF transceiver (P203Pro uses AD9363), 70 MHz to 6 GHz.

## USB-C "3-in-1" port

One USB-C port carries JTAG, UART, and USB OTG through an onboard USB hub
(Microchip USB2514) feeding:

- FT2232 (Digilent JTAG-SMT1, USB `0403:6010`):
  - port A: JTAG (Xilinx/Digilent cable, works with `hw_server`/`xsdb`).
  - port B: PS UART1 console, `/dev/ttyUSB1`, 115200 8N1, 3.3V.
- Zynq USB OTG: the Pluto USB gadget (USB `0456:b673`), which exposes a serial
  console, a mass-storage function, and a USB ethernet gadget (device IP
  `192.168.2.1`, host `192.168.2.10`).

The console UART is PS UART1 (`e0001000`), routed to MIO12 (TX) / MIO13 (RX).
This is confirmed by the FSBL MIO init (MIO12 = `0x16e0` output, MIO13 = `0x16e1`
input) and the Pluto+ schematic nets `UART_TX = PS_MIO12`, `UART_RX = PS_MIO13`.

No soldering is needed for console or JTAG; both are on the USB-C port.

## Ethernet

- RTL8211F gigabit PHY (PHY ID `0x001cc916`).
- In the stock design the Zynq GEM0 connects via EMIO (GMII) to a PL
  GMII-to-RGMII converter (`xlnx,gmii-to-rgmii-1.0`, MDIO address 8); the PHY is
  behind it at MDIO address 1. `phy-mode = "rgmii-rxid"`.
- PHY reset/control is a GPIO: EMIO13, `gpio-973`, kernel label "reset". In the
  stock bitstream it routes to package pins W18/W19 (`RIOB33_X73Y55`,
  IO_L22P/N_T3_34, PULLDOWN). The new bitstream routes EMIO13 to a different pin,
  R19 (`RIOB33_SING_X73Y99`), leaving W18/W19 undriven by EMIO — see
  `bitstream-analysis.md` (#3). The stock-kernel RX regression itself is the
  `GEM0_RCLK_CTRL.SRCSEL` bit, not this GPIO (see `ethernet-regression.md`).
- The newer 5.15 firmware's devicetree instead describes a direct-RGMII design
  (PHY at MDIO address 0, no converter), which does not match the stock
  bitstream.

## Expansion header

The datasheet describes a 24-pin expansion connector (5x 3.3V power, 16x 3.3V
IO, 4x 1.8V IO), not a 40-pin Raspberry Pi header. Do not assume RPi pin
numbering. Other interfaces: SD card, GPS antenna, PPS/10M input, IPEX clock
input, 8-36V power (XH2.54 and DC007).

## Boot modes

A boot-mode switch selects SD/QSPI or JTAG (sampled at power-on):

- SD inserted + SD/QSPI position: BootROM loads `BOOT.bin` from SD; U-Boot
  imports `uEnv.txt` and boots `image.ub` (FIT: kernel + DTB + ramdisk +
  bitstream).
- No SD + SD/QSPI position: boots QSPI (`mtd0` FSBL/U-Boot, `mtd3` FIT).
- JTAG position: BootROM waits; load firmware over JTAG (see `ps7_init/`).

## JTAG recovery

With the switch in JTAG position, `xsdb` can load the FSBL/`ps7_init`, bitstream,
and kernel directly. The recovered `ps7_init/ps7_init.tcl` brings up the PS and
DDR. A full JTAG Linux boot reached the kernel on the tested board but hung in a
spinlock before USB gadget init; that hang is unresolved and separate from the
ethernet issue. QSPI/SD boot is the reliable path.