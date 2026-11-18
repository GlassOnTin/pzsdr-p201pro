# Ethernet receive failure in the 2026-11-16 firmware

## Summary

A firmware update dated 2026-11-16 broke ethernet receive on the P201Pro. The
link comes up at 1 Gbps and transmit works, but the interface receives nothing
(`rx_packets` stays 0). The cause is a single bit in the new FSBL: it selects the
wrong source for GEM0's RX clock/data signals (MIO instead of EMIO). Setting that
bit back restores ethernet. The hardware is fine.

Fix: write `0x11` (not `0x01`) to `GEM0_RCLK_CTRL` at SLCR `0xF8000138`. Bit 4
(`SRCSEL`) selects the RX signal source: 0 = MIO, 1 = EMIO. See
`../fix/ethernet-gem0-rclk.md`.

## Symptom

- RJ45 link LEDs flash during boot, then the port appears dead.
- `eth0`: carrier 1, speed 1000, `tx_packets` increments, `rx_packets` stays 0.
- DHCP gets no lease. Ping fails both directions.
- The host receives the SDR's ARP requests (TX, cable, and switch are good), but
  the SDR receives nothing back. The fault is specifically the RX path.

The flashing link LED is easy to mistake for "working". Link and TX are up; only
RX is dead.

## What it is not

Ruled out by measurement:

- Power rail. The fault reproduces on USB-only power.
- Cable, switch, router port. Multiple cables and switches tried; the host sees
  the SDR's transmitted frames.
- U-Boot. Splicing the original FSBL into the new `BOOT.bin` (new U-Boot kept)
  restores RX.
- MIO pinmux, GEM0 TX clock divider, SDIO clock divider, GPIO init. Reverting
  each in the new FSBL did not restore RX. Reverting `GEM0_RCLK_CTRL` did.

## Root cause

The FSBL holds the PS7 initialization register data. The original and new FSBLs
differ in 28 register addresses. Bisecting those differences (patching the new
FSBL toward the original one group at a time, and booting) isolates the fault to
`GEM0_RCLK_CTRL` (`0xF8000138`, UG585 "GigE 0 Rx Clock and Rx Signals Select"):

| FSBL | `0xF8000138` | bit4 SRCSEL | eth0 RX |
|---|---|---|---|
| original (QSPI) | `0x11` | 1 (EMIO) | works |
| new (2026-11-16) | `0x01` | 0 (MIO) | dead |
| new, only `0x138` reverted to `0x11` | `0x11` | 1 (EMIO) | works |

Both values keep bit0 `CLKACT` set (RX clock enabled); the difference is bit4
`SRCSEL`, which selects the source of GEM0's RX clock/control/data signals:
0 = MIO pins, 1 = EMIO.

Confirmed directly on a running system: clearing bit4 of `0xF8000138` stops RX
immediately (`rx_packets` freezes, ping 100% loss); setting it resumes RX.

Mechanism: the stock P201Pro PL design routes GEM0 through EMIO to a
GMII-to-RGMII converter (`phy-mode = "rgmii-rxid"`, PHY behind the converter at
MDIO address 1), so GEM0's RX signals must come from EMIO (`SRCSEL=1`). The new
FSBL sets `SRCSEL=0` (MIO), taking the RX signals from the MIO pins instead of
the EMIO converter path, so RX receives nothing. TX uses a separate register
(`GEM0_TCLK_CTRL`) and MDIO is independent, so link, TX, and MDIO all stay up
while RX is dead — exactly the observed symptom.

The new FSBL's `SRCSEL=0` is correct for the *new* direct-RGMII PL design (which
routes GEM0 RX via MIO), but wrong for the stock EMIO-converter design. The FSBL
and bitstream must agree on the GEM0 RX source. The new FSBL appears to target a
different hardware revision: its MIO and clock init match a direct-RGMII design
with the PHY at MDIO address 0 and no converter.

## How the bisection was done

The FSBL init data is a list of register writes (see `ps7-init-format.md`).
`tools/patch_fsbl_addrs.py` reverts the write values for chosen addresses in the
new FSBL to the original FSBL's values. The patched FSBL is spliced into
`BOOT.bin` at offset `0x1700` (both FSBLs are `0x18008` bytes; the boot and
partition checksums cover headers, not the FSBL payload, so an in-place splice
is valid). Each variant was booted and RX tested with a bidirectional ping.

Sequence:

1. Original FSBL spliced into new `BOOT.bin` (new U-Boot kept): RX works.
   Confirms the FSBL, not U-Boot.
2. New FSBL, MIO reverted to original (GPIO/clock still new): RX dead. Rules out
   MIO.
3. New FSBL, MIO + clock (`0x138`,`0x140`,`0x150`) reverted (GPIO still new): RX
   works. Implicates the clock group.
4. New FSBL, MIO + only `0x140` (GEM0_TCLK_CTRL) reverted: RX dead. Rules out the
   TX clock register.
5. New FSBL, MIO + only `0x138` (GEM0_RCLK_CTRL) reverted: RX works. Implicates
   `0x138`.
6. New FSBL, only `0x138` reverted (everything else new): RX works. Confirms the
   single register.

Running-Linux `devmem` tests of clock/MIO registers were initially misleading
because the kernel clk/pinctrl drivers re-initialize those registers after boot.
`GEM0_RCLK_CTRL.SRCSEL` is not re-set by the kernel, which is why the FSBL state
persists and why direct writes to it take effect.

## Other findings

- The QSPI U-Boot environment on the tested board is incomplete: `read_sf` and
  `dfu_sf_info` are undefined, so QSPI autoboot falls through to DFU. Manual boot
  works:

  ```
  sf probe 0:0 50000000 0
  sf read 0x2080000 0x200000 0xE00000
  setenv bootargs console=ttyPS0,115200 maxcpus=2 rootfstype=ramfs root=/dev/ram0 rw earlyprintk clk_ignore_unused
  bootm 0x2080000#config@0
  ```

- The new Linux 5.15 firmware (also 2026-11-16) has a separate fault: no PHY
  responds on MDIO at any of the 32 addresses. Its devicetree assumes a
  direct-RGMII topology (PHY at address 0, no converter) and its FSBL MIO init
  matches that design (MIO24-27 `L0_SEL=1`, MIO52/53 as GPIO with pullup).
  Verified on hardware: the `SRCSEL` fix does not restore MDIO; routing GEM0
  MDIO back to MIO52/53 does not restore it; a full 32-address scan with the
  `SRCSEL` fix finds no PHY. Bitstream tracing (`bitstream-analysis.md`) confirms
  the new direct-RGMII bitstream strands GEM0 MDIO (no path to any IOB) and drops
  the MDIO IOB pin. This is a PL-design/bitstream-level fault, not fixable via
  `GEM0_RCLK_CTRL`, MIO pinmux, or DT PHY address. The stock converter firmware
  with the `SRCSEL` fix is the working path.

## Limitations

- The register-level cause (`GEM0_RCLK_CTRL.SRCSEL`) and fix are verified by
  bisection and direct write; this is the stock-kernel RX fault, independent of
  the PHY reset GPIO.
- The PHY reset GPIO (EMIO13, `gpio-973`, kernel label "reset") traces to W18/W19
  (`RIOB33_X73Y55`) in the stock bitstream but to R19 (`RIOB33_SING_X73Y99`) in
  the new bitstream, which leaves W18/W19 undriven by EMIO. Which RTL8211F pin
  W18/W19 drives (RESETB) is inferred; confirming the PCB net needs the
  schematic. See `bitstream-analysis.md` (#3).
- The 5.15 firmware MDIO failure is characterized, not fixed.
- The QSPI environment corruption is repaired and verified (see
  `../fix/qspi-env.md`); QSPI now autoboots cleanly.