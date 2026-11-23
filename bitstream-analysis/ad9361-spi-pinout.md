# PZSDR P201Pro AD9361 SPI pinout (traced from stock bitstream)

The P201Pro AD9361 digital interface is NOT pin-compatible with ADALM-Pluto+
or Pluto Rev.C. Traced by decoding stock.bit to FASM (prjxray bit2fasm,
xc7z020clg400-2) and following the active PS7 SPI0 EMIO routing
(route_trace.py) from the PSS2 EMIO wires to the IO tiles.

PS7 SPI0 EMIO source wires (ppips_pss2.db):
  SCLK = PSS2_LOGIC_OUTS0_94 (liESCLKO)
  MOSI = PSS2_LOGIC_OUTS0_93 (liESO)
  SS0  = PSS2_LOGIC_OUTS0_92 (liESSON0)
  MISO = PSS2_IMUX_B0_93     (liESI)

SCLK and SS0 route to IO tile RIOI3_X73Y97. Combined with the IOB
input/output direction decode (stock_ad9361_iob_direction.csv):

  spi_clk  = T10  (RIOB33_X73Y97.IOB_Y0, OUT)
  spi_csn  = T11  (RIOB33_X73Y97.IOB_Y1, OUT, PULLUP)
  spi_mosi = T12  (RIOB33_X73Y95.IOB_Y0, OUT)
  spi_miso = U12  (RIOB33_X73Y95.IOB_Y1, IN)

Reference pinouts for comparison:
  Pluto+ (maia plutoplus constr): csn=A20 clk=B19 mosi=B20 miso=C20
  Pluto Rev.C (adi pluto constr): csn=E12 clk=E11 mosi=E13 miso=F12

On the P201Pro, A20/B19 are used for other AD9361 signals and B20/C20 are
unused (PULLDOWN), so a Pluto+/Rev.C constraint file drives SPI onto the
wrong pins and MISO floats (ad9361 PRODUCT_ID reads 0xFF).

Two further bring-up fixes needed in the Maia device tree:
  - keep the clock_extern_en gpio-hog (MIO48 high) so the AD9361 refclk is
    present (the stock u-boot adi_loadvals sets this; Maia's does not).
  - add spi-cpol to the ad9361 node (CPOL=1, mode 3 with spi-cpha); with
    CPOL=0 MISO floats.

## AD9361 resetb (traced)

PS7 EMIO GPIO13 output (PS7_EMIOGPIOO13 = PSS2_LOGIC_OUTS1_76) routes to IO
tile RIOI3_X73Y55. The inout pin is W19 (RIOB33_X73Y55.IOB_Y1: .IN + DRIVE +
OLOGIC_Y1.OMUX.D1); W18 (IOB_Y0) is PULLDOWN/unused. So:

  gpio_resetb = W19   (NOT W18 as in the Pluto+ Maia constr)

enable (EMIO GPIO15 = PSS2_LOGIC_OUTS3_76) and txnrx (EMIO GPIO16 =
PSS2_LOGIC_OUTS0_77) route into the axi_ad9361 IP (up_enable/up_txnrx), not
directly to an IOB, so their pins need tracing from the IP side.

## Data-interface pinout: status and tooling gap

stock_ad9361_iob_direction.csv gives the direction of every used IOB. The
rx-side inputs cluster at Y53-Y73 and the tx-side outputs at Y77-Y91, but
these are a permutation of the Pluto+ pins (e.g. the pins Maia uses for
rx_data are mostly tx outputs or SPI on the P201Pro), so the whole data
interface must be remapped, not just SPI.

Tracing the PS7 EMIO signals (SPI, resetb) works because the PSS2 EMIO
wires link cleanly to the fabric backbone (ppips_pss2.db). The data
interface is harder for two reasons:

  1. The rx/tx pins use ILOGIC ISERDES / OLOGIC ODDR DDR cells, not the
     simple OMUX/IMUX that route_trace.py --iomux handles. The default
     cell muxes are not in the FASM. ppips_rioi3.db defines
     ILOGIC/ODELAY Q -> IOI_LOGIC_OUTS links, but the db stops at the IOI
     routing wires (IOI_ILOGIC*_Q): it does not model the link from those
     wires through the ILOGIC/OLOGIC cell to the IOB pin, so querying
     IOI_LOGIC_OUTS* yields a tiny component (size 0-3) that never reaches
     the fabric backbone or the IP. The rx data tiles are also special
     clock-capable types (RIOI3_TBYTESRC_X73Y57/Y69,
     RIOI3_TBYTETERM_X73Y63), needing their own ppips.

  2. Even with the IOB linked to the fabric, the FASM carries no design
     hierarchy: the axi_ad9361 rx_data_in[0..11]/tx_data_out[0..11] port
     wires are anonymous CLB wires, so the BIT ORDER (which data bit lands
     on which pin) cannot be recovered from routing alone.

Next step options: extend route_trace to model the RIOI3 OLOGIC/ILOGIC DDR
cell connections via ppips_rioi3.db and recover the bit order from the
axi_ad9361 IP netlist, or obtain the vendor P201Pro HDL/constraint files.
The SPI + resetb pinout above is verified; the data-interface bit map is
not yet recovered.

## Progress: ILOGIC cell path modeled, rx data pins traced

route_trace.py now has site_logic_edges() (commit 8fb999f): config-aware
ILOGIC D->O/Q1 (and Q2 for IDDR, Q3..Q8 for ISERDES) plus OLOGIC D2->OQ.
This completes the IOB->ILOGIC->fabric chain the db ppips left open. With
it, the rx data IOI_LOGIC_OUTS components reach the axi_ad9361 IP CLB
fabric (were size 0, now 41-54 with CLB wires).

Tracing the rx-side input pins (stock.bit) gives the rx interface:

  rx_clk_in   = N18  (RIOB33_X73Y73 Y1; component ~21883, global clock net)
  rx_frame_in = R16  (RIOB33_X73Y61 Y0; component ~194)
  rx_data (12 pins, bit order TBD):
    V17 V18 (Y57)  R18 T17 (Y59)  V16 W16 (Y63)
    Y18 Y19 (Y65)  V20 W20 (Y67)  T20 U20 (Y69)

Each rx_data pin's component reaches a distinct set of axi_ad9361 IP CLB
sites, but the sites are placement-scattered (X51-55, Y57-70), so the
rx_data_in[0..11] BIT ORDER is not readable from the routing alone. It
needs the axi_ad9361 IP netlist (port->SLICE mapping, matched across the
Maia and stock placements) or a hardware BIST PN-sequence capture to
deduce the permutation. The tx data pins need the analogous OLOGIC-side
trace. SPI + resetb + rx_clk + rx_frame + the rx_data pin SET are verified;
the rx/tx bit order and tx pin set remain.

## OLOGIC output classification + enable/txnrx candidates

Classifying the stock OLOGIC cells by config: ODDR outputs (tx_data,
tx_clk, tx_frame, gpio_ctl) vs OBUFT/OMUX.D1 outputs (SPI, resetb, enable,
txnrx, gpio_en_agc, clk_out). The OBUFT outputs are T10/T11/T12 (SPI),
W19 (resetb), and A20/B19/P18/M18/Y149-Y1. Of these, only A20 and B19 have
an IP CLB connection (CLBLM_L_X58Y130 / X60Y130); P18/M18/Y149 have none.
So **enable/txnrx are A20 and B19** (order TBD by BIST). The IP hierarchy
(confirmed from the Maia axi_ad9361 OOC netlist) is
inst/i_dev_if/g_rx_data[0..11].i_rx_data, g_tx_data[0..11].i_tx_data,
i_enable, i_txnrx, i_rx_frame, i_tx_clk, i_tx_frame, plus i_rx/i_rx_channel_*/
i_rx_pnmon/i_pnmon (the BIST PN monitor).

Deeper prjxray gap: tracing THROUGH the IP (enable/txnrx output side, and
the rx/tx bit order) is blocked because the IP's SLICE LUT input->output
internal paths are not modeled (the input LUT and output FF are in different
SLICEs). site_logic_edges covers the IOB ILOGIC/OLOGIC cells but not fabric
SLICE LUTs. The per-bit g_rx_data cells are identical logic, so the bit order
is placement-dependent and not recoverable from LUT init patterns. BIST
(PN-sequence capture) is the reliable way to fix the bit order and confirm
enable/txnrx; the axi_ad9361 PN monitor + ad9361_bist_prbs driver support it.

## BIST bitstream built + flashed; AD9361 SPI still 0xFF

PZSDR constr applied, bitstream built (timing met) after fixing two Vivado
2025.2 environment blockers: (1) /etc/os-release fields leaking into the
generated system.v header as uncommented Verilog (simplified os-release);
(2) libncurses.so.5 missing in the Ubuntu 24.04 container (symlinked .so.6).
FIT repackaged (Maia kernel/rootfs + new bitstream + DTB refclk hog +
spi-cpol), flashed via DFU, boots (ssh/RNDIS up, axi_ad9361 0x000A0300).

But ad9361_spi_check still reads PRODUCT_ID 0xFF. FIT bitstream verified:
SPI clk/csn (T10/T11, Y97 OLOGIC OMUX.D1+OQUSED) and resetb (W19, Y55.Y1)
match stock exactly; SPI SCLK/SS0 traces reach RIOI3_X73Y97. SPI MISO
(U12, Y95.Y1, ISERDES.MASTER like stock) input path does NOT complete to
PS7 SPI0_MISO_I in the trace (component stops at INT, no IOB) — the Maia
design's SPI MISO input fabric routing differs from stock. refclk hog
(gpio-954 clock_extern_en out hi) is applied. Next: investigate the Maia
axi_ad9361 SPI MISO input routing (ILOGIC->IOI_LOGIC_OUTS->INT->PS7 path).

## SPI MISO divergence: FIT vs stock bitstream (empirical, not yet localized)

Decisive test on the same board: stock bitstream (fpga_manager) mode 3 ->
PRODUCT_ID 0x00 (MISO driven); FIT PZSDR bitstream mode 3 -> 0xFF (MISO
floats). resetb toggle (0->1) + refclk hog did not change the FIT result.

FASM comparison FIT vs stock is IDENTICAL at every level checked: SPI MISO
IOB_Y1 + ILOGIC_Y1 (ISERDES.MASTER, IDELMUXE3.P1, ZINV_D), SPI clk/csn
OLOGIC (OMUX.D1+OQUSED), resetb W19 OLOGIC, INT_R_X73Y95 (NW6BEG0.LOGIC_OUTS18),
INT_L_X18Y143 (GFAN), PSS2 (0 FASM PIPs - all ppips). The tracer shows the
MISO input path (IOI_LOGIC_OUTS18_1 -> PSS2_IMUX_B0_93) disconnected in BOTH
(the PS7 EMIO input mux is not fully modeled), so it cannot localize the
divergence. The difference is in the INT-fabric routing of the SPI MISO
input between the Maia and stock designs, not yet pinpointed. Next: full
FASM diff of the INT tiles along the MISO NW6BEG0->PSS2 path, or extend the
tracer's PS7 EMIO input-mux modeling.

## PS7 EMIO input-mux db gap localized (tracer extension target)

The SPI MISO input chain traces: PSS2_IMUX_B0_93 (PS7_EMIOSPI0SI) <-
PSS1_IMUX_B0_33 <- PSS_IMUX_B0_13. The last link PSS_IMUX -> INT fabric is
ABSENT from the prjxray zynq7 db: no PSS tile type in tilegrid, no PSS<->INT
tileconn, no PSS_IMUX in node_pattern_wires, and the 960 PSS_IMUX ppips
(ppips_pss1.db) only map PSS1_IMUX_B0_xx <- PSS_IMUX_B0_y, never
PSS_IMUX <- INT. So the tracer dead-ends at PSS_IMUX and cannot reach the
IOB MISO via the INT fabric. This is why the MISO input path shows
disconnected in both FIT and stock despite the empirical difference
(stock mode3 0x00, FIT 0xFF).

To finish: derive the PSS_IMUX_B0_y <- INT_L/INT_R wire mapping (Zynq TRM
EMIO input mux table, or prjxray fuzzing) and add it to the db/tracer, then
the FIT-vs-stock MISO INT-fabric routing divergence becomes traceable.

## DIVERGENCE FOUND: FIT bitstream missing SPI MISO INT-fabric routing PIPs

The MISO input INT_L tile is INT_L_X18Y83 (grid 51,69; via PSS_IMUX_B0_13 <-
INT_INTERFACE_PSS_IMUX_B0 <- INT_L.IMUX_L0). FASM diff FIT vs stock:
both have IMUX_L0.GFAN0 + GFAN0.GND_WIRE, but STOCK has extra routing PIPs
the FIT LACKS:
  INT_L_X18Y83.EE2BEG0.SS6END0
  INT_L_X18Y83.NN2BEG2.WR1END2
  INT_L_X18Y83.SE6BEG2.SS6END2
  INT_L_X18Y83.SS6BEG1.SS6END1
  INT_L_X18Y83.SS6BEG2.LVB_L0   (MISO via long-vertical-bus)
  INT_L_X18Y83.SS6BEG3.SS6END3
  INT_L_X18Y83.SW6BEG1.SE6END1
These route the AD9361 MISO (U12) through the INT fabric to the PS7 SPI0
MISO input. The FIT (Maia-design) bitstream did not route them, so the FIT
SPI MISO floats (0xFF) while stock reads the AD9361 (0x00). Root cause is
the Maia design SPI MISO connection/routing (spi_miso->spi0_sdi_i->PS7
SPI0_MISO_I), not the pin constr. Fix: investigate the Maia BD SPI MISO
path so Vivado routes U12->PS7 SPI0_MISO_I; the stock PIPs above are the
reference for the required routing.

## SPI MISO net UNROUTED; route_design does not route it

Vivado implemented-design check: spi_miso_IBUF and spi0_sdi_i ->
sys_ps7/SPI0_MISO_I nets are ROUTE_STATUS=UNROUTED (port correctly at
IOB_X1Y95=U12). The BD connection is correct (ad_connect spi0_sdi_i
sys_ps7/SPI0_MISO_I, matches ADI reference). Re-running route_design on
the routed checkpoint completes with 0 errors but does NOT route the MISO
net: the regenerated bitstream still lacks INT_L_X18Y83.SS6BEG2.LVB_L0 and
the other stock MISO PIPs (29 PIPs vs stock 36). So Vivado is leaving the
PS7 SPI0_MISO_I input net unrouted (defaulting to GND/floating). Next:
find why route_design skips this net (PS7 SPI0_MISO_I input handling /
whether the SPI0 peripheral input is marked used), or force-route it.

## Force-route also fails; PS7 SPI0_MISO_I input left unrouted

route_design -nets [get_nets -hier *spi_miso*] completes 0 errors but the
regenerated bitstream STILL lacks INT_L_X18Y83.SS6BEG2.LVB_L0 (29 PIPs vs
stock 36). Vivado consistently leaves the PS7 SPI0_MISO_I EMIO input net
unrouted. The BD connection and pin constr are correct; the stock design
routes the same net. Suspect the Maia PS7 SPI0 EMIO configuration
(PCW_SPI0_SPI0_IO / PCW_SPI0_PERIPHERAL_ENABLE) differs from stock in a way
that makes Vivado treat the MISO input as not needing PL routing. Next:
compare Maia vs stock PS7 SPI0 PCW parameters, or route the MISO input
manually (the stock INT_L_X18Y83 PIPs are the reference).
