#!/usr/bin/env python3
"""Run ONE data pattern on the SHARED calibrated schedule (zeros from the P3
calibration probe).  One transient per pattern; the sampling instant is swept
later by READING the waveform, never by re-simulating.

usage: skrow.py <PATTERN>
"""
import json, os, sys, time
import skharness as SK

T, H, DV, M = 200.0, 4, 1.65, 10.0


def main():
    pat = sys.argv[1]
    bits = SK.PATTERNS[pat]
    d = SK.redirect(pat)
    SK.set_steps(0.05, 0.10)
    SK.set_pattern(bits)
    z = json.load(open(os.path.join(SK.HERE, "zeros_skeptic_T200_H4.json")))
    print("=== %s bits=%s on the SHARED calibrated schedule (P3) ===" % (pat, bits),
          flush=True)
    print("tzr=%s" % ["%.4f" % x for x in z["tzr"]], flush=True)
    print("tzq=%s" % ["%.4f" % x for x in z["tzq"]], flush=True)
    t0 = time.time()
    r = SK.bt.do_row(M, T, H, DV, "free", z)
    if r is None:
        print("ROW FAILED"); sys.exit(1)
    prn = os.path.join(d, "c_%s.cir.prn" % SK.bt.tag_of(M, T, H, DV, "free"))
    mt0 = prn[:-4] + ".mt0"
    if not os.path.exists(prn) or not os.path.exists(mt0):
        print("MISSING OUTPUT prn=%s mt0=%s" % (os.path.exists(prn),
                                                os.path.exists(mt0)))
        sys.exit(1)
    # A6 gate, bt.py's own, UNCHANGED: |I(L)| <= 1 uA at every commanded open
    mm = SK.bt.parse_mt0(mt0)
    a6 = {}
    worst = 0.0
    for k in range(1, SK.bt.NBANK + 1):
        for nm in ("IZ%d" % k, "IZQ%d" % k):
            if nm in mm:
                v = mm[nm] * 1e6
                a6[nm.lower() + "_uA"] = v
                worst = max(worst, abs(v))
    a6["worst_abs_uA"] = worst
    a6["A6_pass_1uA"] = bool(worst <= 1.0)
    S = SK.bt.schedule(T, H, DV, tzr=z["tzr"], tzq=z["tzq"])
    out = dict(pattern=pat, bits=bits, T=T, H=H, dv=DV, m=M,
               prn=prn, mt0=mt0, A6=a6,
               c={k: S["c"][k] for k in S["c"]},
               o={k: S["o"][k] for k in S["o"]},
               r={k: S["r"][k] for k in S["r"]},
               ro={k: S["ro"][k] for k in S["ro"]},
               tend=S["tend"], pstep=S["pstep"], mstep=S["mstep"],
               zeros_from="zeros_skeptic_T200_H4.json (P3 calibration, full 8-run)")
    json.dump(out, open(os.path.join(d, "sched.json"), "w"), indent=1, default=str)
    print("A6: %s" % json.dumps(a6), flush=True)
    if not a6["A6_pass_1uA"]:
        print("!!! A6 FAIL -- row QUARANTINED, not used in any eye", flush=True)
    print("done in %.1fs -> %s" % (time.time() - t0, prn), flush=True)


if __name__ == "__main__":
    main()
