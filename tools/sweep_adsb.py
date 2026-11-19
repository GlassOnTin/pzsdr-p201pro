#!/usr/bin/env python3
"""Offline gain x coherent-integration sweep on archived 1090 MHz IQ.
For each gain capture, smooth the magnitude with a moving-average window
(non-coherent integration length, samples) and run a matched-filter preamble
detector + PPM bit decode + Mode S CRC. Reports decodes and best preamble SNR.
Usage: sweep_adsb.py <dataset_dir>
"""
import sys, os, json, gzip
import numpy as np

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

PULSE = np.array([0, 1, 4, 5, 14, 15, 18, 19])
GAP = np.array([2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 20, 21])
DATA_OFF = 32
NBITS = 112

def movavg(x, w):
    if w <= 1:
        return x
    k = np.ones(w) / w
    return np.convolve(x, k, mode='same')

def run(mag, integ):
    sm = movavg(mag, integ)
    noise = np.median(sm) + 1e-9
    decodes = 0
    df17 = 0
    icaos = set()
    best_snr = 0.0
    last = -1000
    CH = 250000
    OV = 600
    for start in range(0, max(len(sm) - 600, 1), CH - OV):
        block = sm[start:start + CH]
        n = len(block)
        if n < 600:
            break
        idx = np.arange(n - 30)
        pe = np.mean(block[PULSE[None, :] + idx[:, None]], axis=1)
        ge = np.mean(block[GAP[None, :] + idx[:, None]], axis=1)
        cand = np.where((pe > ge * 1.3) & (pe > noise * 1.6))[0]
        for i in cand:
            gpos = start + i
            if gpos - last < 200:
                continue
            base = i + DATA_OFF
            if base + NBITS * 4 > n:
                break
            seg = block[base:base + NBITS * 4].reshape(NBITS, 4)
            bits = (seg[:, 0:2].sum(1) > seg[:, 2:4].sum(1)).astype(np.uint8)
            msg = np.packbits(bits).tobytes()
            df = (msg[0] >> 3) & 31
            syn = csum(msg)
            icao = int.from_bytes(msg[1:4], 'big')
            valid = (syn == icao) if df in (11, 17, 18) else (syn == 0)
            snr = 20 * np.log10(pe[i] / noise)
            if snr > best_snr:
                best_snr = snr
            if valid:
                decodes += 1
                if df == 17:
                    df17 += 1
                    icaos.add(icao)
                last = gpos
    return decodes, df17, icaos, best_snr

def main():
    d = sys.argv[1]
    meta = json.load(open(os.path.join(d, 'meta.json')))
    integs = [1, 2, 4, 8, 16]
    print(f"{'gain_dB':>7} {'integ':>5} {'noise_dBFS':>10} {'decodes':>7} {'df17':>5} {'aircraft':>8} {'best_preamble_SNR_dB':>20}")
    results = {}
    for g in meta['gains']:
        fn = os.path.join(d, meta['gains'][g]['iq_file'])
        with gzip.open(fn, 'rb') as f:
            iq16 = np.frombuffer(f.read(), dtype=np.int16)
        iq = iq16[0::2].astype(np.float64) + 1j * iq16[1::2].astype(np.float64)
        mag = np.abs(iq)
        noise_dbfs = 20 * np.log10(np.median(mag) / 32768 + 1e-12)
        results[g] = {}
        for integ in integs:
            dec, d17, icaos, bsnr = run(mag, integ)
            results[g][integ] = {'decodes': dec, 'df17': d17, 'aircraft': len(icaos),
                                 'best_snr_db': round(bsnr, 2)}
            print(f"{g:>7} {integ:>5} {noise_dbfs:>10.1f} {dec:>7} {d17:>5} {len(icaos):>8} {bsnr:>20.2f}")
    json.dump(results, open(os.path.join(d, 'sweep_results.json'), 'w'), indent=2)
    print("saved sweep_results.json")

if __name__ == '__main__':
    main()