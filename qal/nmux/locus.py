#!/usr/bin/env python3
"""The pass ceiling is a RATE LIMIT, not a DC wall -- measure the rate directly.

A DC probe of a pass transistor alone is useless: with no load current the node
settles at the drain voltage, because an ideal switch in DC steady state drops
nothing.  What actually stops an nMOS pass node is that the charging current
COLLAPSES as the source rises, so the last stretch takes longer than the window.

So measure the current along the ACTUAL operating locus:
    gate  at VGH (1.5 V, or the rail for an operand-driven gate)
    drain at the rail (fixed -- the driving QAL cell holds it)
    source swept 0 -> 1.3 V   == the output node as it charges
    bulk  at 0                == body effect included, self-consistently

Then the time to charge a load C from 0 to V is exactly

    t(V) = C * integral_0^V dV' / I(V')

which is a parameter-free prediction of the transient, from MEASURED current,
with the real Vds at every point (not the Vds = 0.1 V of the threshold extraction).
The transient runs are the arbiter; this says what they should find and why.
"""
import json, math, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import nm

HERE = nm.HERE
CY_FF = nm.CY          # 2 fF load, the campaign's gate-input proxy

CASES = [
    ("mux_tank",  1.5,   1.326, 0.60, "MUX2 select on the 1.5 V control rail, tank-fed data"),
    ("mux_peer",  1.5,   0.755, 0.60, "MUX2 select on the 1.5 V control rail, peer-fed data"),
    ("xor_tank",  1.326, 1.326, 0.60, "XOR2: an OPERAND drives the gate, tank-fed"),
    ("xor_peer",  0.755, 0.755, 0.60, "XOR2: an OPERAND drives the gate, peer-fed"),
    ("mux_tank_w015", 1.5, 1.326, 0.15, "as mux_tank, minimum-width pass device"),
    ("mux_tank_w120", 1.5, 1.326, 1.20, "as mux_tank, 1.2 um pass device"),
]


def deck(vg, vd, w):
    vmax = min(1.32, vd - 0.002)
    return "\n".join(nm.head() + [
        "VG g 0 %.4f" % vg,
        "VD d 0 %.4f" % vd,
        "VS s 0 0",
        "XN d g s 0 sg13_lv_nmos w=%gu l=0.13u" % w,
        ".dc VS 0 %.4f 0.002" % vmax,
        ".print dc V(s) V(d) I(VD) I(VS)",
        ".end", ""])


def run(c):
    tag, vg, vd, w, _ = c
    p = os.path.join(HERE, "loc_%s.cir" % tag)
    open(p, "w").write(deck(vg, vd, w))
    t0 = time.monotonic()
    r = subprocess.run([nm.XYCE, p], cwd=HERE, env=nm.ENV,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return tag, r.returncode, time.monotonic() - t0


def read(tag):
    rows = []
    for ln in open(os.path.join(HERE, "loc_%s.cir.prn" % tag)):
        f = ln.split()
        if not f or not f[0].isdigit():
            continue
        try:
            vs, vd, idd = float(f[1]), float(f[2]), float(f[3])
        except (IndexError, ValueError):
            continue
        rows.append((vs, abs(idd)))          # |I| delivered into the node
    return rows


def charge_time(rows, cfF, vstop):
    """t = C * int dV / I  (trapezoid on 1/I), ps"""
    C = cfF * 1e-15
    t = 0.0
    out = []
    for i in range(1, len(rows)):
        v0, i0 = rows[i - 1]
        v1, i1 = rows[i]
        if v1 > vstop:
            break
        if i0 <= 0 or i1 <= 0:
            return None, out
        t += C * (v1 - v0) * 0.5 * (1.0 / i0 + 1.0 / i1)
        out.append((v1, t * 1e12))
    return t * 1e12, out


def level_at(curve, tps):
    """invert: what level is reached by time tps"""
    prev = 0.0
    for v, t in curve:
        if t >= tps:
            return v
        prev = v
    return prev


def main():
    with ThreadPoolExecutor(max_workers=3) as ex:
        done = list(ex.map(run, CASES))
    out = {"_doc": __doc__.strip().splitlines()[0],
           "load_fF": CY_FF, "rows": []}
    for (tag, vg, vd, w, lab), (_, rc, sec) in zip(CASES, done):
        if rc != 0:
            out["rows"].append({"tag": tag, "FAIL": "rc=%d" % rc}); continue
        rows = read(tag)
        _, curve = charge_time(rows, CY_FF, vd)
        r = {"tag": tag, "label": lab, "VGH_V": vg, "rail_V": vd, "w_um": w,
             "sec": round(sec, 1),
             "I_uA_at_Vout": {("%.2f" % v): 1e6 * i for v, i in rows
                              if abs(v * 100 - round(v * 100)) < 1e-9
                              and round(v * 100) % 20 == 0},
             "level_reached_V": {}}
        for win in (50, 100, 150, 200, 300, 500, 1000, 5000):
            r["level_reached_V"]["%dps" % win] = level_at(curve, win)
        # where the current has fallen to the campaign threshold criteria
        for lab2, ic in (("100nA*W/L", 100e-9 * w / 0.13),
                         ("10nA*W/L", 10e-9 * w / 0.13),
                         ("1nA*W/L", 1e-9 * w / 0.13)):
            v = None
            for k in range(1, len(rows)):
                if rows[k - 1][1] > ic >= rows[k][1]:
                    v = rows[k][0]; break
            r["level_where_I_falls_to_" + lab2] = v
        out["rows"].append(r)
    json.dump(out, open(os.path.join(HERE, "locus.json"), "w"), indent=1)
    for r in out["rows"]:
        if "FAIL" in r:
            print(r); continue
        L = r["level_reached_V"]
        print("%-16s VGH=%.3f rail=%.3f w=%.2f | 100ps %.4f  300ps %.4f  "
              "1ns %.4f  5ns %.4f | I->100nA*W/L at %s"
              % (r["tag"], r["VGH_V"], r["rail_V"], r["w_um"],
                 L["100ps"], L["300ps"], L["1000ps"], L["5000ps"],
                 ("%.4f" % r["level_where_I_falls_to_100nA*W/L"])
                 if r["level_where_I_falls_to_100nA*W/L"] else "n/a"))


if __name__ == "__main__":
    main()
