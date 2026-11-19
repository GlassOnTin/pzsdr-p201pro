#!/usr/bin/env python3
"""Receive-only 1090 MHz ADS-B capture + pulse demod on the PZSDR P201Pro.
Streams IQ via libiio (no TX), demodulates Mode S PPM, checks CRC, counts
messages and unique ICAO aircraft, and measures noise floor / SNR.
Bounded by DURATION seconds. Sample rate 4 MS/s (4 samples/us).
"""
import sys, time
import numpy as np
import iio

URI = 'ip:192.168.0.168'
FS = 4_000_000           # 4 samples per us
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
GAIN = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
BUF_N = 1 << 18          # samples per buffer (~65 ms)
OVERLAP = 600            # samples carried across buffer boundary (~150 us)

# Mode S CRC (dump1090 algorithm)
POLY = 0x1FFF409
TAB = []
for i in range(256):
    c = i << 16
    for _ in range(8):
        c = ((c << 1) ^ POLY) & 0xFFFFFF if c & 0x800000 else (c << 1) & 0xFFFFFF
    TAB.append(c)

def csum(m):
    c = 0
    for j in range(len(m) - 3):
        c = TAB[(m[j] ^ (c >> 16)) & 0xFF] ^ ((c << 8) & 0xFFFFFF)
    c ^= (m[-3] << 16) | (m[-2] << 8) | m[-1]
    return c & 0xFFFFFF

# preamble pulse / gap sample offsets at 4 samples/us (pulses 0,1,3.5,4.5 us)
PULSE = np.array([0, 1, 4, 5, 14, 15, 18, 19])
GAP = np.array([2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 20, 21])
DATA_OFF = 32            # data begins 8 us after preamble start
NBITS = 112

def demod(mag, noise, counts, icaos, snrs):
    n = len(mag)
    # candidate preamble positions: pulse energy clearly above gap energy
    if n < DATA_OFF + NBITS * 4 + 8:
        return
    pe = np.mean(mag[PULSE[None, :] + np.arange(n - 30)[:, None]], axis=1)
    ge = np.mean(mag[GAP[None, :] + np.arange(n - 30)[:, None]], axis=1)
    cand = np.where((pe > ge * 1.4) & (pe > noise * 1.8))[0]
    last = -1000
    for i in cand:
        if i - last < 200:    # skip duplicates within one message
            continue
        base = i + DATA_OFF
        if base + NBITS * 4 > n:
            break
        seg = mag[base:base + NBITS * 4].reshape(NBITS, 4)
        bits = (seg[:, 0:2].sum(axis=1) > seg[:, 2:4].sum(axis=1)).astype(np.uint8)
        msg = np.packbits(bits).tobytes()
        df = (msg[0] >> 3) & 0x1F
        syn = csum(msg)
        icao = int.from_bytes(msg[1:4], 'big')
        valid = (syn == icao) if df in (11, 17, 18) else (syn == 0)
        if valid:
            counts[df] = counts.get(df, 0) + 1
            counts['total'] = counts.get('total', 0) + 1
            if df in (17, 18):
                icaos.add(icao)
            snrs.append(20 * np.log10(pe[i] / noise + 1e-9))
            last = i

def main():
    ctx = iio.Context(URI)
    phy = ctx.find_device('ad9361-phy')
    rx = ctx.find_device('cf-ad9361-lpc')
    lo = phy.find_channel('altvoltage0', True)
    r0 = phy.find_channel('voltage0', False)
    lo.attrs['frequency'].value = '1090000000'
    r0.attrs['sampling_frequency'].value = str(FS)
    r0.attrs['rf_bandwidth'].value = str(4_000_000)
    r0.attrs['gain_control_mode'].value = 'manual'
    r0.attrs['hardwaregain'].value = str(GAIN)
    r0.attrs['rf_port_select'].value = 'A_BALANCED'
    for ch in rx.channels:
        ch.enabled = ch.id in ('voltage0', 'voltage1')
    time.sleep(0.1)
    buf = iio.Buffer(rx, BUF_N)
    counts, icaos, snrs = {}, set(), []
    mags = []
    tail = np.zeros(0, dtype=np.float64)
    t0 = time.time()
    nbuf = 0
    while time.time() - t0 < DURATION:
        buf.refill()
        raw = buf.read()
        s = np.frombuffer(raw, dtype=np.int16)
        iq = s[0::2].astype(np.float64) + 1j * s[1::2].astype(np.float64)
        mag = np.abs(iq)
        mags.append(np.median(mag))
        work = np.concatenate([tail, mag])
        noise = np.median(work) + 1e-9
        demod(work, noise, counts, icaos, snrs)
        tail = mag[-OVERLAP:]
        nbuf += 1
    elapsed = time.time() - t0
    noise_med = float(np.median(mags))
    noise_dbfs = 20 * np.log10(noise_med / 32768 + 1e-12)
    snr_med = float(np.median(snrs)) if snrs else 0.0
    total = counts.get('total', 0)
    print("=== PZSDR window antenna, 1090 MHz RX-only ===")
    print(f"capture: {elapsed:.1f}s  fs={FS/1e6:.1f}MS/s  gain={GAIN:.0f}dB manual  buffers={nbuf}")
    print(f"noise_floor: {noise_dbfs:.1f} dBFS (median |IQ| {noise_med:.0f} of 32768)")
    print(f"messages_total: {total}  rate: {total/elapsed:.2f} msg/s")
    print(f"df17: {counts.get(17,0)} ({counts.get(17,0)/elapsed:.2f}/s)  df11: {counts.get(11,0)}  df18: {counts.get(18,0)}")
    print(f"by_df: { {k:v for k,v in sorted(counts.items()) if k!='total'} }")
    print(f"unique_aircraft_ICAO: {len(icaos)}")
    print(f"snr_median: {snr_med:.1f} dB (preamble pulse vs noise, n={len(snrs)})")
    print(f"icaos: {sorted('%06x'%x for x in icaos)}")

if __name__ == '__main__':
    main()