#!/usr/bin/env python3
"""Measure V_trip(Vdd) for BOTH campaign receivers, at the DELIVERED rail.

Receiver S = 1.12u pMOS / 0.74u nMOS  (every cell in every chain deck)
Receiver A = 0.15u pMOS / 1.48u nMOS  (the skewed boundary receiver)

For each rail Vdd we DC-sweep Vin 0..Vdd and record:
  * trip   = Vin where Vout = Vdd/2   (the decision threshold)
  * VIH/VIL-style transition window = Vin(Vout=0.1*Vdd) - Vin(Vout=0.9*Vdd)
    (for an inverter Vout falls with Vin, so this is positive)
Nothing is assumed: the rails swept cover every delivered rail that appears
in the datasets (0.20 .. 1.50 V).
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
HDL = '.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"'
LIB = '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"'
CMP = '.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"'

RAILS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
         0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25,
         1.30, 1.35, 1.40, 1.45, 1.50]
CELLS = {"S": ("1.12u", "0.74u"), "A": ("0.15u", "1.48u")}
VSTEP = 0.001          # 1 mV DC step -- the whole point is sub-10 mV resolution


def deck(tag, rails, wp, wn):
    L = ["* fcrit trip-vs-rail, receiver %s (p=%s n=%s)" % (tag, wp, wn),
         HDL, LIB, CMP,
         ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17",
         "VIN in 0 0"]
    pr = ["V(in)"]
    for j, v in enumerate(rails):
        L += ["VD%d d%d 0 %.4f" % (j, j, v),
              "XP%d o%d in d%d d%d sg13_lv_pmos w=%s l=0.13u" % (j, j, j, j, wp),
              "XN%d o%d in 0   0   sg13_lv_nmos w=%s l=0.13u" % (j, j, wn)]
        pr.append("V(o%d)" % j)
    L += [".DC VIN 0 1.5 %g" % VSTEP,
          ".print dc " + " ".join(pr), ".end"]
    return "\n".join(L) + "\n"


def run(name, text):
    p = os.path.join(HERE, name + ".cir")
    open(p, "w").write(text)
    env = dict(os.environ)
    env["PYMS_DIR"] = "/usr/local/share/xyce/PyMS"
    env["PYMS_VAE_CACHE"] = ("/tmp/claude-1001/-usr-local-src/"
                             "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/"
                             "vae_cache_fcrit")
    os.makedirs(env["PYMS_VAE_CACHE"], exist_ok=True)
    t0 = time.time()
    rc = subprocess.call([XYCE, p], stdout=open(p + ".log", "w"),
                         stderr=subprocess.STDOUT, env=env, cwd=HERE)
    print("  %s rc=%d %.1fs" % (name, rc, time.time() - t0), flush=True)
    return p + ".prn" if rc == 0 else None


def read_prn(path):
    f = open(path)
    hdr = f.readline().split()
    rows = []
    for ln in f:
        p = ln.split()
        if not p or p[0].lower().startswith("end"):
            continue
        try:
            rows.append([float(x) for x in p[1:]])
        except ValueError:
            continue
    return [h.upper() for h in hdr[1:]], rows


def xing(vin, vout, target, falling=True):
    """linear-interpolated Vin at which vout crosses target."""
    for i in range(1, len(vin)):
        a, b = vout[i - 1], vout[i]
        if (a >= target >= b) if falling else (a <= target <= b):
            if a == b:
                return vin[i]
            return vin[i - 1] + (a - target) * (vin[i] - vin[i - 1]) / (a - b)
    return None


def main():
    out = {}
    for tag, (wp, wn) in CELLS.items():
        prn = run("trip_%s" % tag, deck(tag, RAILS, wp, wn))
        if prn is None:
            print("FAILED", tag)
            continue
        hdr, rows = read_prn(prn)
        ic = hdr.index("V(IN)")
        vin = [r[ic] for r in rows]
        res = {}
        for j, vdd in enumerate(RAILS):
            io = hdr.index("V(O%d)" % j)
            vo = [r[io] for r in rows]
            # restrict the sweep to Vin <= Vdd (a gate never sees more than its rail)
            n = max(i for i in range(len(vin)) if vin[i] <= vdd + 1e-9) + 1
            vi, vv = vin[:n], vo[:n]
            t50 = xing(vi, vv, 0.5 * vdd)
            t90 = xing(vi, vv, 0.9 * vdd)
            t10 = xing(vi, vv, 0.1 * vdd)
            res["%.4f" % vdd] = dict(
                vdd=vdd, trip_V=t50,
                trip_frac_of_rail=(t50 / vdd if t50 else None),
                vin_at_vout90_V=t90, vin_at_vout10_V=t10,
                window_10_90_mV=(1000.0 * (t10 - t90)
                                 if (t10 is not None and t90 is not None) else None),
                vout_at_vin0=vv[0], vout_at_vin_vdd=vv[-1])
        out[tag] = dict(wp=wp, wn=wn, rows=res)
    json.dump(out, open(os.path.join(HERE, "TRIP.json"), "w"), indent=1)
    for tag in out:
        print("\n== receiver %s (p=%s n=%s)" % (tag, out[tag]["wp"], out[tag]["wn"]))
        print("   Vdd    trip_V   frac   window(10-90) mV")
        for k in sorted(out[tag]["rows"], key=float):
            r = out[tag]["rows"][k]
            print("  %5.2f  %8.5f  %.4f  %8.2f" %
                  (r["vdd"], r["trip_V"] or -1, r["trip_frac_of_rail"] or -1,
                   r["window_10_90_mV"] or -1))


if __name__ == "__main__":
    main()
