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

The full rx/tx data + GPIO pinout still needs per-signal tracing of the
axi_ad9361 IP ports; stock_ad9361_iob_direction.csv gives the direction of
every used IOB as the starting map.
