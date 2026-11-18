# Ethernet RX fix: GEM0_RCLK_CTRL SRCSEL

The 2026-11-16 FSBL breaks ethernet receive on the stock (EMIO converter)
firmware by selecting the wrong GEM0 RX signal source. The fix is to set
`GEM0_RCLK_CTRL` (SLCR `0xF8000138`) bit 4 (`SRCSEL`) to 1 (EMIO): write `0x11`
instead of `0x01`.

## The register (UG585)

`GEM0_RCLK_CTRL` — "GigE 0 Rx Clock and Rx Signals Select", offset `0x138`,
reset value `0x00000001`:

| bit | field | meaning |
|---|---|---|
| 4 | `SRCSEL` | RX clock/control/data source: **0 = MIO, 1 = EMIO** |
| 0 | `CLKACT` | GEM0 RX clock enable: 0 = disable, 1 = enable |

- Original FSBL writes `0x11` = `CLKACT=1`, `SRCSEL=1` (EMIO).
- New FSBL writes `0x01` = `CLKACT=1`, `SRCSEL=0` (MIO).

## Why it breaks RX

The stock P201Pro PL design routes GEM0 through EMIO to a GMII-to-RGMII
converter (`phy-mode = "rgmii-rxid"`, PHY behind the converter at MDIO addr 1).
GEM0's RX clock/data must therefore come from EMIO (`SRCSEL=1`). The new FSBL
sets `SRCSEL=0` (MIO), so the GEM0 RX signals are taken from the MIO pins instead
of the EMIO converter path — RX receives nothing.

TX uses a separate register (`GEM0_TCLK_CTRL`) and MDIO is independent, so link,
TX, and MDIO all stay up while RX is dead (`rx_packets` stays 0). This matches the
observed symptom exactly.

The new FSBL's `SRCSEL=0` is correct for the *new* direct-RGMII PL design (which
routes GEM0 RX via MIO), but wrong for the stock EMIO-converter design. The FSBL
and bitstream must agree on the GEM0 RX source.

## Fix

Any one of these restores RX on the stock firmware:

1. Runtime (no reflash, re-apply each boot):
   ```
   devmem 0xF8000008 32 0xDF0D     # SLCR unlock
   devmem 0xF8000138 32 0x11       # GEM0_RCLK_CTRL: CLKACT=1, SRCSEL=EMIO
   ```
   U-Boot: `mw f8000008 df0d; mw f8000138 11`

2. Patch the FSBL: change its `GEM0_RCLK_CTRL` writes from `0x01` to `0x11`
   (`tools/patch_fsbl_addrs.py ORIG NEW OUT 0xF8000138`), splice into `BOOT.bin`
   at `0x1700`. Artifact: `sd-firmware/BOOT_fix138.bin`.

3. Use the original FSBL (writes `0x11`). Artifact:
   `sd-firmware/BOOT_origfsbl_patched.bin`.

Verified: with `0x138=0x11`, bidirectional ping passes (0% loss), `rx_packets`
increments.

## Live toggle test (scope-free, on the bench)

Run on the stock QSPI board (Linux 5.10, eth0 192.168.0.168, gateway
192.168.0.1), console over the USB-gadget ACM port. Toggling bit 4 of
`0xF8000138` while pinging the gateway, reading `rx_packets` before/after each
3-packet ping:

| stage | `0x138` | SRCSEL | ping | `rx_packets` delta |
|---|---|---|---|---|
| baseline | `0x11` | EMIO | 3/3, 0% loss, 0.6 ms | +12 |
| clear bit 4 | `0x01` | MIO | 0/3, **100% loss** | **0 (frozen)** |
| restore | `0x11` | EMIO | 3/3, 0% loss, 0.6 ms | +22 |

Clearing SRCSEL freezes RX immediately (`rx_packets` stops, ping 100% loss);
setting it resumes RX. TX and the 1 Gbps link stay up throughout. The board was
left at `0x11` (working). This demonstrates the root cause live, reversibly,
without a scope. SLCR must be unlocked first (`devmem 0xF8000008 32 0xDF0D`).

## Note on the 5.15 firmware

This fixes the stock-kernel RX fault. The newer Linux 5.15 firmware has a
separate, bitstream-level MDIO fault (GEM0 MDIO stranded, no IOB) — see
`../docs/bitstream-analysis.md`. The `SRCSEL` fix alone does not make the 5.15
firmware work.