#!/usr/bin/env python3
"""Receive-only 1090 MHz IQ capture at several manual gains + survey spectrum.
Archives raw int16 IQ (gzip), averaged FFT spectrum, and metadata. No TX.
Usage: capture_adsb.py <outdir> [duration_s]
"""
import sys, os, json, time, gzip
import numpy as np
import iio

URI = 'ip:192.168.0.168'
FS = 4_000_000
LO = 1_090_000_000
BW = 4_000_000
GAINS = [40, 55, 71]
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/adsb-dataset'
NFFT = 1 << 14
os.makedirs(OUT, exist_ok=True)

ctx = iio.Context(URI)
phy = ctx.find_device('ad9361-phy')
rx = ctx.find_device('cf-ad9361-lpc')
lo = phy.find_channel('altvoltage0', True)
r0 = phy.find_channel('voltage0', False)
lo.attrs['frequency'].value = str(LO)
r0.attrs['sampling_frequency'].value = str(FS)
r0.attrs['rf_bandwidth'].value = str(BW)
r0.attrs['gain_control_mode'].value = 'manual'
r0.attrs['rf_port_select'].value = 'A_BALANCED'
for ch in rx.channels:
    ch.enabled = ch.id in ('voltage0', 'voltage1')

meta = {'receiver': 'PZSDR P201Pro AD9361', 'antenna': 'wideband indoors at window (RX1 A_BALANCED)',
        'lo_hz': LO, 'fs_hz': FS, 'rf_bw_hz': BW, 'rx_only': True, 'tx_enabled': False,
        'date': '2026-11-19', 'uri': URI, 'gains': {}}

buf = iio.Buffer(rx, 1 << 18)
for g in GAINS:
    r0.attrs['hardwaregain'].value = str(g)
    time.sleep(0.15)
    chunks = []
    t0 = time.time()
    while time.time() - t0 < DUR:
        buf.refill()
        chunks.append(np.frombuffer(buf.read(), dtype=np.int16).copy())
    iq16 = np.concatenate(chunks)
    elapsed = time.time() - t0
    iq = iq16[0::2].astype(np.float64) + 1j * iq16[1::2].astype(np.float64)
    mag = np.abs(iq)
    # averaged spectrum
    win = np.hanning(NFFT)
    acc = np.zeros(NFFT)
    nb = 0
    for k in range(0, len(iq) - NFFT, NFFT):
        acc += np.abs(np.fft.fftshift(np.fft.fft(iq[k:k + NFFT] * win))) ** 2
        nb += 1
    acc /= max(nb, 1)
    pdb = 10 * np.log10(acc + 1e-12)
    freqs = (LO + np.fft.fftshift(np.fft.fftfreq(NFFT, 1 / FS))) / 1e6
    noise_dbfs = 20 * np.log10(np.median(mag) / 32768 + 1e-12)
    # save raw IQ gzip
    fn = os.path.join(OUT, f'iq_g{g}.bin.gz')
    with gzip.open(fn, 'wb', compresslevel=6) as f:
        f.write(iq16.tobytes())
    np.savez_compressed(os.path.join(OUT, f'spectrum_g{g}.npz'),
                        freq_mhz=freqs, power_db=pdb)
    sz = os.path.getsize(fn)
    meta['gains'][str(g)] = {
        'duration_s': round(elapsed, 2), 'n_samples': len(iq),
        'noise_dbfs': round(float(noise_dbfs), 2),
        'median_mag': round(float(np.median(mag)), 2),
        'p99_mag': round(float(np.percentile(mag, 99)), 2),
        'max_mag': round(float(mag.max()), 2),
        'rssi_db': r0.attrs['rssi'].value,
        'iq_file': f'iq_g{g}.bin.gz', 'iq_gz_bytes': sz,
        'spectrum_file': f'spectrum_g{g}.npz',
    }
    print(f"gain {g} dB: {elapsed:.1f}s {len(iq)} samples noise {noise_dbfs:.1f} dBFS "
          f"max_mag {mag.max():.0f} rssi {r0.attrs['rssi'].value} iq_gz {sz/1e6:.1f} MB")

json.dump(meta, open(os.path.join(OUT, 'meta.json'), 'w'), indent=2)
print("saved dataset to", OUT)