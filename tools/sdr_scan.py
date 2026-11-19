#!/usr/bin/env python3
"""Spectrum survey with the PZSDR P201Pro (AD9361) via libiio.
Usage: sdr_scan.py <center_MHz> [samp_MHz] [navg]
Prints the strongest spectral peaks around the tuned center.
"""
import sys, time
import numpy as np
from scipy.signal import find_peaks, windows
import iio

URI = 'ip:192.168.0.168'
NFFT = 1 << 14

def get_ctx():
    ctx = iio.Context(URI)
    phy = ctx.find_device('ad9361-phy')
    rx = ctx.find_device('cf-ad9361-lpc')
    return ctx, phy, rx

def scan(center_mhz, samp_mhz=30.72, navg=8, gain_mode='slow_attack', gain_db=None):
    ctx, phy, rx = get_ctx()
    lo = phy.find_channel('altvoltage0', True)
    r0 = phy.find_channel('voltage0', False)
    samp = int(samp_mhz * 1e6)
    bw = int(min(samp_mhz, 20.0) * 1e6)
    lo.attrs['frequency'].value = str(int(center_mhz * 1e6))
    r0.attrs['sampling_frequency'].value = str(samp)
    r0.attrs['rf_bandwidth'].value = str(bw)
    r0.attrs['gain_control_mode'].value = gain_mode
    if gain_mode == 'manual' and gain_db is not None:
        r0.attrs['hardwaregain'].value = str(gain_db)
    # enable I/Q on RX1
    for ch in rx.channels:
        ch.enabled = ch.id in ('voltage0', 'voltage1')
    time.sleep(0.05)
    buf = iio.Buffer(rx, NFFT)
    win = windows.hann(NFFT, sym=False)
    acc = np.zeros(NFFT)
    for _ in range(navg):
        buf.refill()
        raw = buf.read()
        s = np.frombuffer(raw, dtype=np.int16)
        iq = s[0::2].astype(np.float64) + 1j * s[1::2].astype(np.float64)
        n = min(len(iq), NFFT)
        spec = np.fft.fftshift(np.abs(np.fft.fft(iq[:n] * win[:n])) ** 2)
        if len(spec) < NFFT:
            spec = np.pad(spec, (0, NFFT - len(spec)))
        acc += spec
    acc /= navg
    p_db = 10 * np.log10(acc + 1e-12)
    freqs = (center_mhz * 1e6 + np.fft.fftshift(np.fft.fftfreq(NFFT, 1 / samp))) / 1e6
    # noise floor = median; peaks well above it
    floor = np.median(p_db)
    pk, props = find_peaks(p_db, prominence=8, distance=int(NFFT * 0.002))
    order = np.argsort(props['prominences'])[::-1]
    print(f"--- center {center_mhz:.3f} MHz  span {samp_mhz:.2f} MHz  floor {floor:.1f} dB ---")
    out = []
    for i in order:
        f = freqs[pk[i]]
        if abs(f - center_mhz) < 0.25:   # skip LO/DC spur at center
            continue
        rel = p_db[pk[i]] - floor
        out.append((f, rel, props['prominences'][i]))
        if len(out) >= 10:
            break
    for f, rel, prom in out:
        print(f"  {f:9.4f} MHz   +{rel:5.1f} dB above floor   (prom {prom:.1f})")
    if not out:
        print("  (no significant peaks)")
    return out

if __name__ == '__main__':
    c = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
    sr = float(sys.argv[2]) if len(sys.argv) > 2 else 30.72
    na = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    scan(c, sr, na)