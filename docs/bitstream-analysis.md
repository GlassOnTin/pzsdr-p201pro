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

## Limitations

- prjxray recovers IOB pin usage/IOSTANDARD/pull/drive, **not** the internal
  signal-to-pin routing or net names. So this confirms the topology change
  (converter removed, RGMII retained) and localizes the MDIO fault to internal
  routing, but cannot prove the exact misconnection.
- Confirming/fixing the MDIO routing needs the vendor's Vivado project / XDC
  constraints, or a scope probe on the PHY MDIO pins.
- The `?` pin entries in the CSV are IOB sites with no entry in
  `package_pins.csv` (dedicated/unbonded pins); they are stock-only GMII pins.