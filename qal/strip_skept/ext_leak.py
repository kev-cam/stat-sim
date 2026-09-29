#!/usr/bin/env python3
"""Extract steady-state leakage currents from the SKEPT lk_*.cir.prn files and
turn them into a per-beat charge budget.

The per-beat droop is DERIVED from a MEASURED current:
    dV_beat = I_leak * t_beat / CL
    fraction_of_node_charge = I_leak * t_beat / (CL * rail)
It is NOT read off a waveform: a 200 ps droop of tens of nV is orders below the
solver's own voltage resolution (RELTOL * rail) and cannot be measured directly.
"""
import os, sys, json

CL = 2.0e-15
BEATS = [150e-12, 200e-12, 300e-12]
RAILS = [0.5217, 0.5594, 0.6077, 0.7000, 1.0000]


def tagf(r):
    return ("r%0.4f" % r).replace(".", "p")


def read_prn(p):
    with open(p) as f:
        lines = [l for l in f if l.strip()]
    hdr = lines[0].split()
    # drop trailing "End of Xyce(TM) Simulation" style lines
    rows = []
    for l in lines[1:]:
        parts = l.split()
        if len(parts) != len(hdr):
            continue
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            continue
    cols = {h.lower(): i for i, h in enumerate(hdr)}
    return cols, rows


def steady(cols, rows, name, frac_tail=0.2):
    """Value averaged over the last frac_tail of the record, plus the spread
    across that tail (so a non-settled reading reveals itself)."""
    i = cols.get(name.lower())
    if i is None:
        return None, None
    n = len(rows)
    k = max(1, int(n * frac_tail))
    vals = [r[i] for r in rows[-k:]]
    return vals[-1], (max(vals) - min(vals))


ARMS = [("qn/nMOS only (HIGH node)", "VBN"),
        ("qp/pMOS only (HIGH node, DEGENERATE all-terminals-equal)", "VBP"),
        ("ql/LOW node (OFF pMOS |Vds|=rail + OFF nMOS)", "VBL"),
        ("qb/BOTH (bare dynamic HIGH node)", "VBB"),
        ("qz/NULL control (capacitor only)", "VBZ"),
        ("qr/RCAL 1e12 ohm", "VBR"),
        ("qh/hard-off nMOS Vgs=-0.3", "VBH"),
        ("qk/KEEPER fitted", "VBK")]


def main():
    d = os.path.dirname(os.path.abspath(__file__))
    out = {}
    for arm in ("def", "zero", "real"):
        p = os.path.join(d, "lk_%s.cir.prn" % arm)
        if not os.path.exists(p):
            print("MISSING", p)
            continue
        cols, rows = read_prn(p)
        tend = rows[-1][0]
        out[arm] = dict(tend_s=tend, nrows=len(rows), rails={})
        for r in RAILS:
            t = tagf(r)
            e = {}
            for label, pfx in ARMS:
                v, spread = steady(cols, rows, "I(%s%s)" % (pfx, t))
                if v is None:
                    continue
                e[label] = dict(I_pA=abs(v) * 1e12, tail_spread_pA=spread * 1e12)
            out[arm]["rails"][("%.4f" % r)] = e
        v, _ = steady(cols, rows, "I(VB56)")
        if v is not None:
            out[arm]["pmos_0p56u_off_pA"] = abs(v) * 1e12
    json.dump(out, open(os.path.join(d, "LEAK_SKEPT.json"), "w"), indent=1)

    # ---- report
    print("SETTLED-STATE LEAKAGE, pA  (|I| through the fixed-bias ammeter)")
    print("declared harness current floor = ABSTOL = 1e-17 A = 0.00001 pA\n")
    hdr = "%-56s %12s %12s %12s" % ("arm", "DEF(shim)", "ZERO", "REAL(PDK)")
    for r in RAILS:
        print("=== rail %.4f V" % r)
        print(hdr)
        for label, pfx in ARMS:
            vals = []
            for arm in ("def", "zero", "real"):
                e = out.get(arm, {}).get("rails", {}).get("%.4f" % r, {})
                vals.append(e.get(label, {}).get("I_pA"))
            if all(v is None for v in vals):
                continue
            print("%-56s %12s %12s %12s" % (
                label,
                "-" if vals[0] is None else "%.5f" % vals[0],
                "-" if vals[1] is None else "%.5f" % vals[1],
                "-" if vals[2] is None else "%.5f" % vals[2]))
        print()

    # ---- the budget, on the bare dynamic HIGH node
    print("PER-BEAT CHARGE BUDGET on the bare dynamic HIGH node (CL = 2 fF)")
    print("%-8s %-10s %12s %12s %14s %16s" % (
        "arm", "rail(V)", "I_leak(pA)", "Qnode(fC)", "dV/200ps(uV)", "frac/200ps(%)"))
    for arm in ("def", "zero", "real"):
        for r in RAILS:
            e = out.get(arm, {}).get("rails", {}).get("%.4f" % r, {})
            k = "qb/BOTH (bare dynamic HIGH node)"
            if k not in e:
                continue
            I = e[k]["I_pA"] * 1e-12
            Q = CL * r
            dv = I * 200e-12 / CL
            print("%-8s %-10.4f %12.5f %12.5f %14.4f %16.3e" % (
                arm, r, e[k]["I_pA"], Q * 1e15, dv * 1e6, 100.0 * I * 200e-12 / Q))
    print()
    print("SAME NODE, ALL THREE BEAT LENGTHS, rail 0.6077 V")
    for arm in ("def", "zero", "real"):
        e = out.get(arm, {}).get("rails", {}).get("0.6077", {})
        k = "qb/BOTH (bare dynamic HIGH node)"
        if k not in e:
            continue
        I = e[k]["I_pA"] * 1e-12
        Q = CL * 0.6077
        s = "  ".join("%d ps: dV=%.4f uV frac=%.3e %%" % (
            b * 1e12, I * b / CL * 1e6, 100.0 * I * b / Q) for b in BEATS)
        print("%-6s %s" % (arm, s))


if __name__ == "__main__":
    main()
