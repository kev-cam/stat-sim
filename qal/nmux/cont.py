#!/usr/bin/env python3
"""(f) THE STATIC-POWER TRAP.

A degraded high on the input of a following STATIC CMOS gate leaves its pMOS
partly on -> DC contention.  The campaign measured exactly this at the QAL->sync
boundary: the standard 1.12/0.74 cell drew 8.780 uA at a 0.6759 V input on a
1.2 V rail = 3.0896 fJ over a 293 ps hold = 36.75 % of the 8.408 fJ hop.

Here: sweep the receiver input as a DC level and read I(VDD) directly, for
  - the STANDARD receiver 1.12u p / 0.74u n
  - the boundary study's SKEWED receiver 0.15u p / 1.48u n
at receiver rails 0.9 / 1.2 / 1.26 / 1.33 V (a QAL receiving cell sits on the
rail that fed it, so the rail is a variable, not a constant).

Reports, for any input level: I_dc, the trip point (Vin = Vout), and the energy
over the campaign's 293 ps hold.
"""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import nm

HERE = nm.HERE
HOLD_PS = 293.0
HOP_FJ  = 8.408270111148767     # committed tg15p hop

RX = {"std":  (1.12, 0.74),
      "skew": (0.15, 1.48)}
VDDS = [0.9, 1.2, 1.26, 1.33]


def deck(wp, wn, vdd):
    return "\n".join(nm.head() + [
        "VDD vdd 0 %.4f" % vdd,
        "VIN vin 0 0",
        "XP out vin vdd vdd sg13_lv_pmos w=%gu l=0.13u" % wp,
        "XN out vin 0 0 sg13_lv_nmos w=%gu l=0.13u" % wn,
        ".dc VIN 0 1.5 0.001",
        ".print dc V(vin) V(out) I(VDD)",
        ".end", ""])


def run(a):
    name, vdd = a
    wp, wn = RX[name]
    tag = "rx_%s_%03d" % (name, round(vdd * 100))
    p = os.path.join(HERE, tag + ".cir")
    open(p, "w").write(deck(wp, wn, vdd))
    t0 = time.monotonic()
    r = subprocess.run([nm.XYCE, p], cwd=HERE, env=nm.ENV,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return name, vdd, wp, wn, tag, r.returncode, time.monotonic() - t0


def read(tag):
    rows = []
    for ln in open(os.path.join(HERE, tag + ".cir.prn")):
        f = ln.split()
        if not f or not f[0].isdigit():
            continue
        try:
            rows.append((float(f[1]), float(f[2]), -float(f[3])))  # vin, vout, Idd
        except (IndexError, ValueError):
            pass
    return rows


def trip(rows):
    """Vin = Vout crossing"""
    for i in range(1, len(rows)):
        a = rows[i - 1][0] - rows[i - 1][1]
        b = rows[i][0] - rows[i][1]
        if a < 0 <= b:
            return rows[i - 1][0] + (-a) * (rows[i][0] - rows[i - 1][0]) / (b - a)
    return None


def idc_at(rows, v):
    for i in range(1, len(rows)):
        if rows[i - 1][0] <= v <= rows[i][0]:
            f = ((v - rows[i - 1][0]) /
                 (rows[i][0] - rows[i - 1][0] or 1e-12))
            return rows[i - 1][2] + f * (rows[i][2] - rows[i - 1][2])
    return None


def main():
    levels = json.loads(sys.argv[1]) if len(sys.argv) > 1 else \
        {"committed_QAL_high": 0.6759}
    jobs = [(n, v) for n in RX for v in VDDS]
    with ThreadPoolExecutor(max_workers=3) as ex:
        done = list(ex.map(run, jobs))
    out = {"_doc": "(f) static contention into a following static CMOS cell",
           "hold_ps": HOLD_PS, "hop_fJ": HOP_FJ,
           "committed_anchor": {"receiver": "1.12p/0.74n @1.2V", "vin": 0.6759,
                                "I_uA": 8.780026706089604, "E_fJ": 3.089638717712695,
                                "pct_of_hop": 36.745236259906235},
           "levels_probed_V": levels, "rows": []}
    for name, vdd, wp, wn, tag, rc, sec in done:
        if rc != 0:
            out["rows"].append({"rx": name, "vdd": vdd, "FAIL": rc}); continue
        rows = read(tag)
        r = {"rx": name, "wp_um": wp, "wn_um": wn, "vdd_V": vdd,
             "trip_V": trip(rows), "sec": round(sec, 1), "at_level": {}}
        for lab, v in levels.items():
            i = idc_at(rows, v)
            if i is None:
                continue
            e = abs(i) * vdd * HOLD_PS * 1e-12 * 1e15      # fJ
            r["at_level"][lab] = {
                "Vin": v, "I_uA": i * 1e6, "E_hold_fJ": e,
                "pct_of_hop": 100.0 * e / HOP_FJ,
                "reads_as": "1" if v > (r["trip_V"] or 9) else "0"}
        out["rows"].append(r)
    out["rows"].sort(key=lambda z: (z.get("rx", ""), z.get("vdd_V", 0)))
    json.dump(out, open(os.path.join(HERE, "cont.json"), "w"), indent=1)
    for r in out["rows"]:
        if "FAIL" in r:
            print(r); continue
        print("%-5s vdd=%.2f trip=%.4f  " % (r["rx"], r["vdd_V"], r["trip_V"] or -1)
              + "  ".join("%s:%.3fuA/%.3ffJ(%s)" %
                          (k, d["I_uA"], d["E_hold_fJ"], d["reads_as"])
                          for k, d in r["at_level"].items()))


if __name__ == "__main__":
    main()
