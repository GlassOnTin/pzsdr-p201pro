# ADS-B 1090 MHz window-antenna gain / integration sweep

Date: 2026-11-19. Receive-only (no TX). Candidate anchor dataset for the
fieldsmith T16 antenna workbench.

## Question

The prior comparison decoded 0 ADS-B messages on the PZSDR window wideband
antenna (best preamble candidate 6.5 dB SNR). Is any decode recoverable by
sweeping manual gain and coherent integration length, or is the antenna the
hard limit?

## Result: 0 decodes across the entire sweep — antenna is the hard limit

Best preamble SNR (dB) by gain × integration window (samples); **decodes = 0,
DF17 = 0, aircraft = 0 in every cell**:

| gain (dB) | noise (dBFS) | integ=1 | integ=2 | integ=4 | integ=8 | integ=16 |
|---|---|---|---|---|---|---|
| 40 | −80.3 | 18.33 | 17.85 | 16.85 | 7.47 | 0.00 |
| 55 | −76.3 | 7.77 | 7.17 | 6.24 | 5.24 | 0.00 |
| 71 | −66.9 | 7.60 | 6.69 | 4.93 | 0.00 | 0.00 |

- No gain (40/55/71 dB) and no integration window (1–16 samples) produced a
  single valid-CRC Mode S message.
- Longer integration **reduces** preamble SNR: ADS-B PPM pulses are 0.5 µs
  (2 samples at 4 MS/s); a moving-average window longer than the pulse blurs
  it away. There is no coherent-integration gain to be had beyond the pulse.
- The gain-40 "18.33 dB" cell is a metric artifact, not a recoverable signal:
  at low gain the noise floor is quantization-limited (median |IQ| ≈ 3 LSB),
  which inflates the pulse/noise ratio for noise spikes. That candidate fails
  CRC (random data), as do all others.
- The decode threshold (~10 dB per-bit SNR for reliable CRC) is **not
  reachable**. The window wideband antenna does not deliver decodable 1090 MHz
  signal; receiver gain/integration cannot recover what the antenna does not
  receive. Compare the loft 1090 colinear (6 m above roof): 11.9 dB median
  DF17 SNR, 90.9 msg/s, 175.6 nm 24 h range.

## Dataset manifest

| File | Contents |
|---|---|
| `iq_g40.bin.gz` / `iq_g55.bin.gz` / `iq_g71.bin.gz` | raw int16 I/Q interleaved, 1090 MHz, 4 MS/s, ~3 s each, manual gain 40/55/71 dB |
| `spectrum_g40.npz` / `g55` / `g71` | averaged FFT survey spectrum (freq_mhz, power_db), 16384-pt Hann |
| `meta.json` | receiver, antenna, LO/fs/bw, gain, duration, noise dBFS, mag percentiles, RSSI, rx_only=true |
| `sweep_results.json` | per gain × integration: decodes, df17, aircraft, best preamble SNR |
| `REPORT.md` | this report |

## Capture conditions

- PZSDR P201Pro (AD9361), RX1 A_BALANCED, wideband antenna indoors at window.
- LO 1090.000 MHz, 4 MS/s, rf_bandwidth 4 MHz, gain_control_mode manual,
  hardwaregain {40,55,71} dB. **RX-only; no TX channel enabled.**
- libiio network backend `ip:192.168.0.168`. 3 s per gain.
- Demod: matched-filter preamble (pulse vs gap energy), 112-bit PPM, dump1090
  Mode S CRC (DF11/17/18 syndrome==ICAO, else 0). Validated on synthetic DF17
  (syndrome==ICAO 0x4bb147 at 15.9 dB) — 0-decode is antenna/SNR, not decoder.
- Integration sweep = magnitude moving-average window {1,2,4,8,16} samples
  before preamble detection (non-coherent integration length).

## PZSDR known limits (operator-noted)

- Dead Ethernet MDI.
- LAN via router route plus workstation NAT.
- Wideband antenna indoors at window — confirmed here as the hard limit for
  1090 MHz ADS-B decode.

## Reproduce

- Capture: `tools/capture_adsb.py <outdir> [duration]`
- Sweep: `tools/sweep_adsb.py <dataset_dir>`