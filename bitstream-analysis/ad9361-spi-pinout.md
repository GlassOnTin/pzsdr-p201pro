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
     cell muxes are not in the FASM. ppips_rioi3.db does define the
     ILOGIC/ODELAY Q -> IOI_LOGIC_OUTS fabric links, so the IOB<->fabric
     path is partially modelable, but the tracer's iomux_edges uses wire
     names (OLOGIC_Y0_OMUX_*) that do not match the db IOI_* wires.

  2. Even with the IOB linked to the fabric, the FASM carries no design
     hierarchy: the axi_ad9361 rx_data_in[0..11]/tx_data_out[0..11] port
     wires are anonymous CLB wires, so the BIT ORDER (which data bit lands
     on which pin) cannot be recovered from routing alone.

Next step options: extend route_trace to model the RIOI3 OLOGIC/ILOGIC DDR
cell connections via ppips_rioi3.db and recover the bit order from the
axi_ad9361 IP netlist, or obtain the vendor P201Pro HDL/constraint files.
The SPI + resetb pinout above is verified; the data-interface bit map is
not yet recovered.
