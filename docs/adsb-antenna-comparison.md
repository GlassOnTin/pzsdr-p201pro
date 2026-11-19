# ADS-B antenna comparison: PZSDR window vs loft colinear

Date: 2026-11-19. Receive-only on both receivers (no TX). 1090 MHz Mode S / ADS-B.

## Comparison table

| Metric | PZSDR P201Pro (window) | Loft feed (airspy.lan) |
|---|---|---|
| Receiver | AD9361 (P201Pro), RX1 A_BALANCED | Airspy R2 |
| Antenna | wideband, indoors at window | 1090 MHz colinear, 6 m above roof |
| Decoder | custom Python PPM + Mode S CRC | airspy_adsb |
| Sample rate | 4.0 MS/s | 12 MS/s |
| Gain | 71 dB manual | 21 (airspy index), auto |
| RF bandwidth | 4 MHz | (12 MS/s capture) |
| Capture window | 60 s (915 buffers) | 60 s stats interval |
| **Messages decoded** | **0** | **5454 / 60 s** |
| **Message rate** | **0.00 msg/s** | **90.9 msg/s** (peak 139.5 observed) |
| DF17 rate | 0.00 /s | 13.9 /s |
| **Unique aircraft (ICAO)** | **0** | **7 now / 14 peak** |
| Max aircraft in interval | 0 | 6 (peak 13) |
| **Max range, 24 h outline** | n/a (no decode) | **175.6 nm** (median 117.8 nm) |
| Max range, current | n/a | 132.5 nm |
| **Noise floor** | **−66.4 dBFS** (median \|IQ\| 16/32768) | **28.1 dB** (airspy rel., DF17) |
| **SNR** | **≤ 6.5 dB** best preamble candidate, no CRC pass | **11.9 dB median** (p95 16.4), decoded DF17 |
| Lost buffers | n/a | 0 |
| Receiver position | (window, indoors) | 50.898748, −1.058695, alt 55 m |

Noise-floor references differ (PZSDR dBFS vs ADC full scale; airspy_adsb relative dB, DF17-only) — not directly comparable. SNR is the meaningful cross-receiver figure: the loft decodes DF17 at 11.9 dB median; the PZSDR's strongest preamble-shaped candidate is 6.5 dB and fails CRC.

## PZSDR result detail

- 60 s capture at 1090.000 MHz: 0 valid-CRC messages, 0 aircraft.
- 5 s sensitive scan (preamble threshold pe>1.2×gap, pe>1.5×noise): 353090 candidates, 0 valid CRC; best candidate SNR 6.5 dB, DF types random (noise).
- Demod validated on a synthetic DF17 (CRC syndrome == ICAO 0x4bb147, decoded at 15.9 dB SNR) — the 0-decode is an antenna/SNR limit, not a decoder fault.
- Spectrum survey (AGC, 30.72 MS/s) showed only a +4–5 dB ADS-B bump at 1089–1091 MHz at the window.

## Capture conditions

- PZSDR: RX-only, LO 1090.000 MHz, 4 MS/s, rf_bandwidth 4 MHz, gain_control_mode manual, hardwaregain 71 dB, rf_port_select A_BALANCED. libiio network backend `ip:192.168.0.168`. Demod: 4 samples/µs PPM, 112-bit Mode S, dump1090 CRC (DF11/17/18 syndrome==ICAO, else 0).
- Loft: Airspy R2 + airspy_adsb (`-g auto -m 12`), 12 MS/s, gain 21; stats from `/run/airspy_adsb/stats.json` (60 s window, DF17-limited rssi/snr/noise); aircraft from `/run/dump1090-fa/aircraft.json`; 24 h range from `/run/adsbfi-feed/outline.json` (actualRange.last24h, 360 bearings). Message rate cross-checked against beast output (port 30005): 117.5 msg/s over 10 s.

## PZSDR known limits (operator-noted)

- Dead Ethernet MDI.
- LAN reached via router route plus workstation NAT.
- Wideband antenna indoors at a window (vs dedicated 1090 colinear with height and sky view) — the dominant factor in the 0-decode result.

## Evidence

- PZSDR demod source: `tools/pzsdr_adsb.py` (receive-only; no TX channel enabled). Spectrum survey: `tools/sdr_scan.py`.
- Loft stats: airspy_adsb 60 s window; beast frame count independent cross-check.
- Traffic varies with time of day: loft snapshot ranged 7–14 aircraft and 90.9–139.5 msg/s across the session; PZSDR remained 0 throughout.