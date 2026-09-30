#!/usr/bin/env python3
"""INDEPENDENT policing of my own AddRoundKey re-run.

Two things the parent's own extractor cannot check for me, because it is the
thing under audit:

 1. VALUE, against a FIPS-197 oracle I wrote from the standard.  The parent's
    G11 'reference' check uses veh.py's own reference; mine recomputes
    AddRoundKey and ShiftRows from the AES definition and compares against the
    level-3 output voltages in MY .prn.

 2. PER-GATE SETTLING, computed from MY .prn with my own arithmetic, reported
    as the worst gate on every level -- not taken from the row JSON.

Usage: police.py <row.cir.prn> <ROW_*.json>
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/local/src/stat-sim/qal/cipher/btk")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/fcrit")
import run as prun


# ---------------------------------------------------------------- the oracle
def fips197_addroundkey_shiftrows(state, rk):
    """AES-128, FIPS-197. State is column-major: index i = 4*c + r.
    AddRoundKey: XOR byte-wise.  ShiftRows: row r rotates LEFT by r, i.e.
    out[r][c] = in[r][(c+r) mod 4]."""
    ark = [s ^ k for s, k in zip(state, rk)]
    sr = [0] * 16
    for c in range(4):
        for r in range(4):
            sr[4 * c + r] = ark[4 * ((c + r) % 4) + r]
    return ark, sr


def bits_lsb_first(byts):
    """The netlist orders bit i of byte b at flat index 8*b + i, LSB first."""
    out = []
    for b in byts:
        for i in range(8):
            out.append((b >> i) & 1)
    return out


# ------------------------------------------------------------------- reading
def read_prn(path):
    hdr, rows = None, []
    for line in open(path):
        p = line.split()
        if hdr is None:
            if p and p[0].upper() == "INDEX":
                hdr = [x.upper() for x in p]
            continue
        if not p or not p[0].isdigit():
            continue
        rows.append([float(x) for x in p])
    return hdr, rows


def main(prn, rowjson):
    d = json.load(open(rowjson))
    hdr, rows = read_prn(prn)
    ti = hdr.index("TIME")
    ch = prun.make("aes", d["cw_per_bit_fF"])

    # ---- 1. the value oracle, on the netlist's own declared vector
    import veh
    vec = veh.AES_VECTOR if hasattr(veh, "AES_VECTOR") else None
    g = json.load(open(os.path.join(os.path.dirname(rowjson), "GEOMETRY.json")))
    av = g["vehicles"]["aes_addroundkey"]["vector"]
    state = [int(x, 16) for x in av["state"]]
    rk = [int(x, 16) for x in av["round_key"]]
    ark_mine, sr_mine = fips197_addroundkey_shiftrows(state, rk)
    ark_theirs = [int(x, 16) for x in av["addroundkey"]]
    sr_theirs = [int(x, 16) for x in av["shiftrows"]]
    oracle = {
        "addroundkey_matches_my_FIPS197": ark_mine == ark_theirs,
        "shiftrows_matches_my_FIPS197": sr_mine == sr_theirs,
        "my_addroundkey": [hex(v) for v in ark_mine],
        "my_shiftrows": [hex(v) for v in sr_mine],
    }

    # ---- 2. settling and value, per level, from MY waveform
    # commit instant per level: the row's own measured rise ZCS of the RECEIVER
    res = {"levels": {}}
    worst_overall = (1e9, None, None)
    for k in (1, 2, 3):
        n = ch.n_of(k)
        ir = hdr.index("V(RAIL%d)" % k)
        io, hi = [], []
        for i in range(n):
            io.append(hdr.index("V(%s)" % ch.out_net(k, i).upper()))
            hi.append(bool(ch.levels[k - 1][i].val))
        # evaluate at the level's own boundary instant, as the row does
        tb = d["bound"][str(k)]
        best = min(range(len(rows)), key=lambda j: abs(rows[j][ti] * 1e12 - tb))
        r = rows[best]
        rail = r[ir]
        pcts = []
        nbad = 0
        for i in range(n):
            v = r[io[i]]
            pct = (100.0 * v / rail) if hi[i] else (100.0 * (rail - v) / rail)
            pcts.append(pct)
            if pct < 90.0:
                nbad += 1
        wi = min(range(n), key=lambda i: pcts[i])
        if pcts[wi] < worst_overall[0]:
            worst_overall = (pcts[wi], k, wi)
        res["levels"][k] = {
            "t_boundary_ps": tb, "rail_V": rail, "n": n,
            "worst_settle_pct": pcts[wi], "worst_cell": wi,
            "cells_below_90pct": nbad,
            "mean_settle_pct": sum(pcts) / len(pcts),
        }
    res["worst_gate_pct_MINE"] = worst_overall[0]
    res["worst_gate_level"] = worst_overall[1]
    res["worst_gate_cell"] = worst_overall[2]

    # ---- 3. level-3 outputs against the oracle's ShiftRows bits
    k = 3
    n = ch.n_of(k)
    ir = hdr.index("V(RAIL3)")
    tb = d["bound"]["3"]
    best = min(range(len(rows)), key=lambda j: abs(rows[j][ti] * 1e12 - tb))
    r = rows[best]
    rail = r[ir]
    # what the netlist says level 3 holds
    net_bits = [int(bool(ch.levels[2][i].val)) for i in range(n)]
    # level 3 is a bank of inverters fed THROUGH ShiftRows, so it holds the
    # COMPLEMENT of the permuted AddRoundKey result
    sr_bits = bits_lsb_first(sr_mine)
    inv_sr = [1 - b for b in sr_bits]
    res["level3_netlist_equals_NOT_my_shiftrows"] = (net_bits == inv_sr)
    res["level3_netlist_equals_my_shiftrows"] = (net_bits == sr_bits)
    bad = []
    ref = net_bits
    for i in range(n):
        v = r[hdr.index("V(%s)" % ch.out_net(k, i).upper())]
        ok = (v >= 0.50 * rail) if ref[i] else (v <= 0.10 * rail)
        if not ok:
            bad.append((i, ref[i], v))
    res["level3_value_fails_vs_netlist"] = len(bad)
    res["level3_value_fail_list"] = bad[:10]
    res["oracle"] = oracle
    print(json.dumps(res, indent=1))
    out = os.path.join(HERE, "POLICE.json")
    open(out, "w").write(json.dumps(res, indent=1))
    print("-> %s" % out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
