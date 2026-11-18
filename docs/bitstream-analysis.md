# Bitstream IOB analysis (stock vs 2026-11-16)

Partial reverse engineering of the two PL bitstreams with [Project
X-Ray](https://github.com/f4pga/prjxray), to characterize the 5.15 firmware
ethernet MDIO fault (issue #1). This recovers **pin usage and IO configuration**,
not internal signal routing.

## Tooling and setup

- `prjxray` (`bitread` C++ tool + `utils/bit2fasm.py`) with the
  [`prjxray-db`](https://github.com/f4pga/prjxray-db) `zynq7/xc7z020clg400-2`
  database (the board is XC7Z020-2CLG400). The db has IOB segbits
  (`segbits_liob33.db`, `segbits_riob33.db`) and `package_pins.csv`.
- Build fixes needed on a modern toolchain (GCC 15 / CMake 4):
  - add `#include <cstdint>` to `lib/include/prjxray/memory_mapped_file.h`
    (`uint8_t` no longer pulled in transitively);
  - configure with `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` (gflags uses an old
    `cmake_minimum_required`);
  - change `add_compile_options(-Wall -Werror)` to `-Wno-error` in the top
    `CMakeLists.txt` (GCC 15 `-Wfree-nonheap-object` false positive).
- Python: `fasm` (from `third_party/fasm`) + `prjxray` (`pip install -e .`).

## Bitstream preparation

- Stock: the FPGA image from the QSPI/SD FIT (`image.ub` `fpga@1`), a `.bit`
  file (big-endian words, `COMPRESS=TRUE` header). `bitread` reads it directly.
- New: the `system_top.bit` partition from the new `BOOT.bin` (offset
  `0x19740`). It is a **raw little-endian** bitstream with a QSPI bus-width
  detect prefix. To feed `bitread`: strip everything before the sync word
  (`0xAA995566`, at offset `0x30`), byte-swap each 32-bit word LE→BE, and wrap
  in a `.bit` header (reuse the stock header up to the `e` field, then
  `0x65` + 4-byte BE length + data).

Decode:

```
bit2fasm.py --db-root <db>/zynq7 --part xc7z020clg400-2 \
    --bitread <build>/tools/bitread --bits-file out.bits design.bit > out.fasm
```

## Findings

| | IOB sites | IOB FASM features |
|---|---|---|
| stock | 72 | 706 |
| new (2026-11-16) | 31 | 280 |

The new design's 31 IOB sites are a **strict subset** of the stock's 72 — no new
sites are added. The 41 dropped sites:

- 24 `LIOB33_X0Y*` (left-side PL pins, e.g. T5/U5, W11/Y11, V8/W8): the GMII
  data/control bus between GEM0 (EMIO) and the GMII-to-RGMII converter.
- 17 `RIOB33_X73Y*` (right-side, bank 35): further converter-related PL pins.

The 31 **common** sites are all `RIOB33_X73Y*` (bank 35, right side, e.g.
M14/M15, L14/L15, J14/K14): the RGMII interface to the RTL8211F that both
designs share, plus MDIO/clock/other PL IO.

See `../bitstream-analysis/iob_pinmap.csv` (site → package pins, in_stock,
in_new) and `stock_iob.fasm` / `new_iob.fasm` (the IOB FASM features).

## Interpretation for issue #1

The new bitstream removes the GMII-to-RGMII converter's EMIO pin interface and
moves GEM0 to a direct-RGMII design. This matches the new FSBL's MIO init
(MIO16-27 set for GEM0 RGMII `L0_SEL=1`; MIO52/53 left as GPIO with pullup, not
MDIO) and the 5.15 devicetree (`phy@0`, `rgmii-id`, no converter).

The RGMII PHY pins (common bank-35 sites) are still configured in the new
bitstream, but MDIO finds no PHY at any address. Since the IOB is configured yet
MDIO is dead, the fault is in the new bitstream's **internal routing** — GEM0's
MDIO is not connected to the PHY's MDIO pin (the stock converter forwarded MDIO;
the direct design must route it explicitly, and does not, or routes it to MIO
pins that the PCB does not wire to the PHY).

## EMIO tracing investigation (toward closing #1/#3 from the bitstream)

The active-routing tracer (`tools/route_trace.py`, upstreamed as
[f4pga/prjxray#2579](https://github.com/f4pga/prjxray/pull/2579)) reconstructs
the configured routing graph from FASM PIPs + `tileconn`. On the stock bitstream
it captures ~173k active PIP edges including the interconnect backbone and the
PS-boundary (`PSS0`–`PSS4`) tiles. Two gaps remain for an end-to-end
GEM0-MDIO-to-PHY trace:

1. **EMIO-signal -> PSS-wire mapping is undocumented in the zynq7 db.**
   - `ps7_ports.json` and `site_type_PS7.json` name the EMIO signals
     (`EMIOENET0MDIOMDC/O/TN/I`, `EMIOENET0GMIIRXD[0:7]`, etc.) and their
     direction, but `site_pips` is empty and the PSS tiles' `pin_functions`
     only cover the DDR IOPADs, not EMIO.
   - The PSS wires are generic (`PSS1_LOGIC_OUTS<group>_<bit>`, groups 0-23);
     nothing maps them to EMIO signal names.
   - UG585 Table 16-13 gives MIO pins (MDIO = MIO52 MDC / MIO53 data) and EMIO
     signal *names*, but not the PSS-wire index. The Vivado PS7 IP RTL
     (`processing_system7.ttcl`) maps EMIO ports to PS7 internal port names
     (`ENET0_MDIO_MDC`), not PSS wires — the EMIO->PSS relation is the silicon
     PS-PL interface.
   - Filling this needs prjxray-style fuzzing of the PS-PL interface (drive known
     EMIO signals, diff bitstreams) to document the PSS-wire <-> EMIO-signal map.
     That is a reusable zynq7 db contribution.
   - Progress: querying Vivado (2025.2, `open_io_design` + `get_bel_pins` of the
     PS7 site, mirroring fuzzers/076-ps7) extracts the **functional** EMIO wire
     names: 441 EMIO ports -> `PSS2_X32Y105/PS7_EMIO*` wires
     (`bitstream-analysis/ps7_emio_wires.csv`, script
     `extract_ps7_emio_wires.tcl`). E.g. `EMIOENET0MDIOMDC ->
     PSS2_X32Y105/PS7_EMIOENET0MDIOMDC`. The PS7 site has **zero site_pips**
     (hard block), so the EMIO-wire -> fabric `PSS1_LOGIC_OUTS#` cross-tile
     correspondence is not queryable from Vivado pin-planning mode; it is the
     tileconn/fuzzer-documented relation still missing from the db.

2. **IO-interconnect mux mapping.** IOB outputs reach the fabric via
   `OLOGIC.OMUX` / `ILOGIC.IMUX` selections; the mux-input -> IOI-wire relation
   needs the db site-pin mapping. `route_trace.py --iomux` is a first attempt.

With those two mappings, the tracer can walk GEM0's EMIO MDIO port through the
active PIPs to the bank-35 PHY IOB and compare stock vs new — a bitstream-only
diagnosis of #1, and the reset-GPIO net for #3.

## Definitive result for #1 (bitstream-only, no vendor files)

The key was loading the fixed "always" pseudo-PIPs from `ppips_pss2.db` (family
level `zynq7/`, keyed by tile *type* `PSS2`, expanded to every instance). These
hardwired PIPs link the PS7 EMIO wires to the fabric `PSS2_LOGIC_OUTS*` wires and
are not in the bitstream FASM. `route_trace.py` now loads them (`ppips_edges`).
The EMIO->LOGIC_OUTS map for GEM0 MDIO is in the db, e.g.:

```
PSS2.PSS2_LOGIC_OUTS5_67.PS7_EMIOENET0MDIOMDC always   (MDC)
PSS2.PSS2_LOGIC_OUTS0_66.PS7_EMIOENET0MDIOO  always   (data out)
PSS2.PSS2_LOGIC_OUTS1_66.PS7_EMIOENET0MDIOTN always   (tristate)
PSS2.PS7_EMIOENET0MDIOI.PSS2_IMUX_B0_66      always   (data in)
```

Tracing `PSS2_X32Y105/PS7_EMIOENET0MDIOMDC` (and `...MDIOO`) through the active
routing graph:

| bitstream | MDIO component | reaches IOB? |
|---|---|---|
| stock | 29 nodes: INT_R/INT_L fabric + RIOI3 | **yes -> RIOI3_X73Y145** |
| new (2026-11-16) | 4 nodes: PSS3/INT_L/PSS2 only | **no IOB** |

`RIOI3_X73Y145` -> `RIOB33_X73Y145` -> package pins **A20/B19** (bank 35), the
RTL8211F MDIO pins. The IOB pinmap confirms `RIOB33_X73Y145` is `in_stock=1,
in_new=0`.

**Conclusion:** the stock bitstream routes GEM0 MDIO to the PHY MDIO IOB
(A20/B19); the new direct-RGMII bitstream strands GEM0 MDIO (no path to any IOB)
and does not configure the MDIO IOB at all. This is why the 5.15 firmware finds
no PHY on MDIO. Diagnosed purely from the two bitstreams + prjxray db, no vendor
schematic required. The fix is to restore the MDIO routing + IOB in the new
PL design (or use the stock converter bitstream).

## Definitive result for #3 (the "reset" GPIO net — AD9361, not the PHY)

The same tracer resolves the GPIO the kernel labels "reset" (`gpio-973`,
EMIO13). **This is the AD9361 reset, not the ethernet PHY reset.** The only
`reset-gpios` in either devicetree is in the `ad9361-phy@0` node
(`reset-gpios = <&gpio0 67 0>`; offset 67 = EMIO13). Neither DT has an
ethernet-PHY reset GPIO and there is no GPIO hog. Confirmed on the running stock
board: `gpiochip0` base 906, `gpio-973` ("reset") out hi, the `ad9361-phy` IIO
device probed; the RTL8211F is at MDIO address 1 behind the converter at address
8 (`phy_id 0x011cc916`) with no reset GPIO. The earlier "PHY reset GPIO" framing
misread the kernel label.

The traced PS7 output wire is `PS7_EMIOGPIOO13`, linked to the fabric by the
fixed PIP `PSS2.PSS2_LOGIC_OUTS1_76.PS7_EMIOGPIOO13 always` (`ppips_pss2.db`).
Tracing that wire through the active routing graph:

| bitstream | EMIO13 output reaches | package pin | bank 34 function |
|---|---|---|---|
| stock | `RIOI3_X73Y55` (OLOGIC1) -> `RIOB33_X73Y55` | **W18/W19** | `IO_L22P/N_T3_34` |
| new (2026-11-16) | `RIOI3_SING_X73Y99` (OLOGIC0) -> `RIOB33_SING_X73Y99` | **R19** | `IO_0_34` |

Stock path (29 hops, abbreviated):

```
PSS2_X32Y105/PS7_EMIOGPIOO13 -> PSS3_LOGIC_OUTS1_16 -> INT_L/INT_R fabric
  -> INT_R_X73Y55/SE2END1 -> R_TERM_INT_X184Y58/TERM_INT_IMUX34
  -> RIOI3_X73Y55/IOI_OLOGIC1_D1 -> RIOI_OLOGIC1_OQ  (-> W18/W19)
```

New path (23 hops) ends at `RIOI3_SING_X73Y99/IOI_OLOGIC0_D1 -> RIOI_OLOGIC0_OQ`
(-> R19). In the new bitstream the W18/W19 output logic (`RIOI3_X73Y55`
OLOGIC1) is a 4-node component with **no PS7 EMIO driver** — the reset GPIO no
longer reaches W18/W19.

**Conclusion:** the stock design drives the AD9361 RESETB net from EMIO13 on
W18/W19; the new direct-RGMII design routes EMIO13 to R19 instead. The IOB site
`RIOB33_X73Y55` is still *configured* in the new bitstream (`in_new=1` in the
pinmap), but configuring the site is not the same as routing the signal to it —
an earlier reading of the pinmap alone missed this. So the new PL design changes
the AD9361 reset pin as well as stranding MDIO (#1), consistent with it targeting
a different board revision/pinout.

The **ethernet PHY (RTL8211F) reset is a separate net and is not a PS7 GPIO** in
either design; it is likely PL-driven or a hardware power-on reset. It has not
been traced. Identifying it needs a scope probe on the PHY PHYRSTB pin (pin 12,
QFN-48) at boot, or the schematic.

Caveat: W18/W19 (stock) / R19 (new) carrying the AD9361 RESETB is inferred from
the DT `reset-gpios` and the stock routing; the AD9361 pin it reaches is not
confirmed against a schematic. The bitstream routing difference itself is
verified by BFS on both decoded bitstreams, and the GPIO attribution by the DT
plus the running board's GPIO/IIO state.

## Limitations

- With the `ppips_*.db` "always" PIPs loaded, `route_trace.py` traces internal
  signal routing (PS7 EMIO -> fabric -> IOB), not just pin usage. This proved the
  MDIO misconnection above without vendor files. Net *names* are still not in the
  bitstream; signals are identified by their PS7 EMIO port / IOB pin.
- The trace reflects connectivity, not timing/electrical correctness. Fixing the
  new PL design's MDIO routing still needs the vendor Vivado project (or a
  rebuild); the diagnosis itself no longer does.
- The `?` pin entries in the CSV are IOB sites with no entry in
  `package_pins.csv` (dedicated/unbonded pins); they are stock-only GMII pins.