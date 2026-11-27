#!/usr/bin/env python3
"""Recover the PZSDR P201Pro AD9361 pinout and RX bit order from stock.fasm.

Resolves package pins via prjxray-db tilegrid.json + package_pins.csv
(IOB33M = IOB_Y0, IOB33S = IOB_Y1, avoiding alphabetical-sort swaps on tiles
such as RIOB33_X73Y97 T11/T10 and RIOB33_X73Y59 T17/R18), traces PS7 SPI0 and
EMIO GPIO signals, identifies enable/txnrx (ODDR with D1==D2 in fabric) and
tx_clk_out/tx_frame_out, and traces all 12 rx_data_in pins through CLB SLICEs
to axi_ad9361 DSP48E1 port A[23:12] to determine the exact bit order [0..11].
"""
import argparse
import csv
import os
import re
from collections import defaultdict

import route_trace as rt


def build_true_pin_map(db_root, part_pkg, tilegrid):
    site_to_pin = {}
    pp_path = os.path.join(db_root, part_pkg, "package_pins.csv")
    with open(pp_path) as f:
        for row in csv.DictReader(f):
            site_to_pin[row["site"]] = row["pin"]

    tile_y_to_pin = {}
    for tile, td in tilegrid.items():
        if "RIOB33" not in tile and "LIOB33" not in tile:
            continue
        for sname, stype in td.get("sites", {}).items():
            pin = site_to_pin.get(sname, "?")
            if stype == "IOB33M":
                y_idx = 0
            elif stype == "IOB33S":
                y_idx = 1
            else:
                yc = int(sname.split("Y")[1])
                y_idx = 0 if (yc % 50 == 0) else 1
            tile_y_to_pin[(tile, y_idx)] = pin
    return tile_y_to_pin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-root", required=True)
    ap.add_argument("--part", default="xc7z020")
    ap.add_argument("--part-pkg", default="xc7z020clg400-2")
    ap.add_argument("--fasm", required=True)
    args = ap.parse_args()

    tilegrid, tileconn, node_wires = rt.load_db(args.db_root, args.part)
    wiresets = rt.wire_sets(node_wires)
    tile_y_to_pin = build_true_pin_map(args.db_root, args.part_pkg, tilegrid)

    # Full graph for SPI0 and EMIO GPIO end-to-end traces
    uf_full, type_to_tiles, _ = rt.build_nodes(tilegrid, tileconn)
    edges_full = rt.active_pip_edges(args.fasm, uf_full, tilegrid, wiresets)
    edges_full += rt.ppips_edges(args.db_root, args.part, uf_full, type_to_tiles)
    edges_full += rt.site_logic_edges(args.fasm, uf_full, tilegrid)
    cuf_full, adj_full, comp_full = rt.components(edges_full)

    print("=== 1. PS7 SPI0 EMIO ===")
    spi_checks = [
        ("spi_clk", "PSS2_X32Y105/PS7_EMIOSPI0SCLKO", "RIOI3_X73Y97/RIOI_OLOGIC0_OQ", ("RIOB33_X73Y97", 0)),
        ("spi_csn", "PSS2_X32Y105/PS7_EMIOSPI0SSON0", "RIOI3_X73Y97/RIOI_OLOGIC1_OQ", ("RIOB33_X73Y97", 1)),
        ("spi_mosi", "PSS2_X32Y105/PS7_EMIOSPI0MO", "RIOI3_X73Y95/RIOI_OLOGIC0_OQ", ("RIOB33_X73Y95", 0)),
        ("spi_miso", "RIOI3_X73Y95/RIOI_I1", "PSS2_X32Y105/PS7_EMIOSPI0MI", ("RIOB33_X73Y95", 1)),
    ]
    for name, src, dst, (bt, by) in spi_checks:
        s = uf_full.find(tuple(src.split("/")))
        d = uf_full.find(tuple(dst.split("/")))
        path = rt.bfs_path(adj_full, s, d)
        pin = tile_y_to_pin[(bt, by)]
        print(f"  {name:10s} = {pin:4s} ({bt}.IOB_Y{by}): {'CONNECTED (%d hops)' % (len(path)-1) if path else 'DISCONNECTED'}")

    print("\n=== 2. PS7 EMIO GPIO [0..13] (ad_iobuf) ===")
    for g in range(14):
        n = cuf_full.find(uf_full.find(("PSS2_X32Y105", f"PS7_EMIOGPIOI{g}")))
        pins = []
        for t, w in comp_full.get(n, []):
            if ("RIOI" in t or "LIOI" in t) and w.endswith(("_I0", "_I1")):
                xy = t.split("_")[-1]
                side = "RIOB33" if t.startswith("R") else "LIOB33"
                bt = [k for k in tilegrid if k.endswith("_" + xy) and side in k][0]
                pins.append(tile_y_to_pin[(bt, int(w[-1]))])
        role = (
            f"gpio_status[{g}]" if g < 8 else
            f"gpio_ctl[{g - 8}]" if g < 12 else
            "gpio_en_agc" if g == 12 else "gpio_resetb"
        )
        print(f"  EMIO {g:2d} ({role:14s}) = {sorted(set(pins))}")

    # Graph without OLOGIC *_OQ merge so D1 and D2 remain distinct unless driven by same fabric net
    uf, type_to_tiles2, _ = rt.build_nodes(tilegrid, tileconn)
    edges = rt.active_pip_edges(args.fasm, uf, tilegrid, wiresets)
    for e in rt.ppips_edges(args.db_root, args.part, uf, type_to_tiles2):
        if "_OQ" not in e[2]:
            edges.append(e)
    cuf, _, comp = rt.components(edges)

    in_re = re.compile(r"^CLBL[LM]_(L|LL|M)_([ABCD])([1-6X]|[I])$")
    out_re = re.compile(r"^CLBL[LM]_(L|LL|M)_([ABCD])(|Q|MUX)$")

    bel_fwd = defaultdict(set)
    for _, nodes in comp.items():
        srcs, dsts, dsps, ios = [], [], [], []
        for t, w in nodes:
            if t.startswith("CLB"):
                mo = out_re.match(w)
                if mo:
                    srcs.append((t, mo.group(1), mo.group(2)))
                    continue
                mi = in_re.match(w)
                if mi:
                    dsts.append((t, mi.group(1), mi.group(2)))
            elif t.startswith("DSP"):
                dsps.append(f"{t}/{w}")
            elif "IOI" in t and "OLOGIC" in w:
                ios.append(f"{t}/{w}")
        for s in srcs:
            for d in dsts:
                if s != d:
                    bel_fwd[s].add(d)
            for dp in dsps:
                bel_fwd[s].add(("DSP", dp))
            for io in ios:
                bel_fwd[s].add(("IO", io))

    print("\n=== 3. enable (EMIO 15) and txnrx (EMIO 16) ===")
    for g, role in [(15, "enable"), (16, "txnrx")]:
        r = cuf.find(uf.find(("PSS2_X32Y105", f"PS7_EMIOGPIOO{g}")))
        frontier = set()
        for t, w in comp.get(r, []):
            if t.startswith("CLB"):
                mi = in_re.match(w)
                if mi:
                    frontier.add((t, mi.group(1), mi.group(2)))
        seen = set(frontier)
        io_hits = set()
        for _ in range(6):
            nxt = set()
            for b in frontier:
                for nb in bel_fwd.get(b, ()):
                    if nb[0] == "IO":
                        ioi, ow = nb[1].split("/")
                        xy = ioi.split("_")[-1]
                        bt = [k for k in tilegrid if k.endswith("_" + xy) and "RIOB33" in k][0]
                        y_idx = 0 if "OLOGIC0" in ow else 1
                        io_hits.add(tile_y_to_pin[(bt, y_idx)])
                    elif nb[0] != "DSP" and nb not in seen:
                        seen.add(nb)
                        nxt.add(nb)
            frontier = nxt
        print(f"  EMIO {g} ({role:6s}) -> {sorted(io_hits)}")

    print("\n=== 4. rx_data_in[0..11] via DSP_R_X25Y45/DSP_1_A[23:12] ===")
    rx_tiles = [
        ("RIOB33_X73Y57", 0), ("RIOB33_X73Y57", 1),
        ("RIOB33_X73Y59", 0), ("RIOB33_X73Y59", 1),
        ("RIOB33_X73Y63", 0), ("RIOB33_X73Y63", 1),
        ("RIOB33_X73Y65", 0), ("RIOB33_X73Y65", 1),
        ("RIOB33_X73Y67", 0), ("RIOB33_X73Y67", 1),
        ("RIOB33_X73Y69", 0), ("RIOB33_X73Y69", 1),
    ]
    pin_first_a = {}
    for bt, y in rx_tiles:
        xy = bt.split("_")[-1]
        ioi = [t for t in tilegrid if t.endswith("_" + xy) and "RIOI" in t][0]
        pin = tile_y_to_pin[(bt, y)]
        frontier = set()
        for q in (f"IOI_ILOGIC{y}_Q1", f"IOI_ILOGIC{y}_Q2"):
            r = cuf.find(uf.find((ioi, q)))
            for t, w in comp.get(r, []):
                if t.startswith("CLB"):
                    mi = in_re.match(w)
                    if mi:
                        frontier.add((t, mi.group(1), mi.group(2)))
        seen = set(frontier)
        a_hits = {}
        for hop in range(1, 5):
            nxt = set()
            for b in frontier:
                for nb in bel_fwd.get(b, ()):
                    if nb[0] == "DSP" and "DSP_R_X25Y45/DSP_1_A" in nb[1]:
                        abit = int(nb[1].split("_A")[1])
                        if 12 <= abit <= 23:
                            a_hits.setdefault(hop, set()).add(abit - 12)
                    elif nb[0] not in ("DSP", "IO") and nb not in seen:
                        seen.add(nb)
                        nxt.add(nb)
            frontier = nxt
        pin_first_a[pin] = a_hits
        print(f"  pin {pin:4s} ({bt}.IOB_Y{y}) -> bit hits by hop: {a_hits}")


if __name__ == "__main__":
    main()
