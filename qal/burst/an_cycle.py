#!/usr/bin/env python3
"""Analyze one cycle deck: value checks per wave, three-way energy decomposition."""
import re, sys, json, math

PAT = [1, 1, 1, 0, 1, 0, 0, 1]
C = 359.79e-15


def mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d


def wave_pat(w):
    return PAT if w % 2 == 0 else [1 - b for b in PAT]


def analyze(tpre, pref="cy"):
    d = mt0("%s_tpre%d.cir.mt0" % (pref, tpre))
    S = json.load(open("%s_tpre%d.cir.sched.json" % (pref, tpre)))
    res = dict(tpre_ps=tpre, sched=S)
    # ---- value check: every bank, every wave, at that bank's boundary
    fails, worstmargin = [], None
    for w in range(5):
        pw = wave_pat(w)
        for k in range(1, 5):
            rail = d["VR%dW%d" % (k, w)]
            for i in range(8):
                v = d["O%d_%dW%d" % (k, i, w)]
                inhi = (pw[i] == 1) if k % 2 == 1 else (pw[i] == 0)
                want_hi = not inhi
                ok = (v >= 0.5 * rail) if want_hi else (v <= 0.10 * rail)
                if not ok:
                    fails.append(dict(w=w, k=k, i=i, v=v, rail=rail, want_hi=want_hi))
    res["value_fails"] = fails
    res["value_pass"] = "%d/160" % (160 - len(fails))
    res["first_postpark_wave_pass"] = not any(f["w"] == 0 for f in fails)
    # ---- ZCS residuals per wave (instrument note)
    iz = {}
    for w in range(5):
        iz["w%d" % w] = dict(
            IZ=[d["IZ%dW%d" % (k, w)] * 1e6 for k in range(1, 5)],
            IZQ=[d["IZQ%dW%d" % (k, w)] * 1e6 for k in range(1, 5)])
    res["zcs_residual_uA"] = iz
    # ---- energy decomposition: segments Z(0.5ps) -> PS(park end) -> BE -> D
    segs = {}
    for a, b in (("park_pre", ("Z", "PS")), ("burst", ("PS", "BE")),
                 ("park_post", ("BE", "D"))):
        e = {}
        for k in range(1, 5):
            v0, v1 = d["VT%d%s" % (k, a and b[0])], d["VT%d%s" % (k, b[1])]
            e["tank%d_dE_fJ" % k] = 0.5 * C * (v0 * v0 - v1 * v1) * 1e15
            e["tank%d_V" % k] = (v0, v1)
        for tg in ("EGT", "EHI", "EI1", "QI1", "ETU", "QTU"):
            if "%s_%s" % (tg, b[1]) in d:
                e[tg] = (d["%s_%s" % (tg, b[1])] - d["%s_%s" % (tg, b[0])]) * 1e15
        for k in range(1, 5):
            for tg in ("EA", "ER", "ESW"):
                key = "%s%d" % (tg, k)
                e[key] = (d["%s_%s" % (key, b[1])] - d["%s_%s" % (key, b[0])]) * 1e15
        e["tank_dE_total_fJ"] = sum(e["tank%d_dE_fJ" % k] for k in range(1, 5))
        segs[a] = e
    res["segments"] = segs
    # park rate cross-check vs dedicated deck (A2d):
    tpre_s = (S["T0"] - 10 - 0.5) * 1e-12
    dE = segs["park_pre"]["tank_dE_total_fJ"]
    res["park_pre_tank_dE_fJ"] = dE
    res["park_pre_implied_pW"] = dE * 1e-15 / tpre_s * 1e12 if tpre_s > 0 else None
    return res


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    pref = "cy"
    args = []
    for x in sys.argv[1:]:
        if x == "--tu":
            pref = "cytu"
        else:
            args.append(x)
    out = {}
    for tp in args:
        r = analyze(int(tp), pref)
        out["%s_tpre%s" % (pref, tp)] = r
        print("== tpre %s ps: value %s (first post-park wave pass: %s)"
              % (tp, r["value_pass"], r["first_postpark_wave_pass"]))
        for nm in ("park_pre", "burst", "park_post"):
            s = r["segments"][nm]
            etu = ("%9.3f" % s["ETU"]) if "ETU" in s else "        -"
            print("  %-9s tank_dE %9.3f fJ  EGT %8.3f  EHI %9.3f  EI1 %7.3f  ETU %s"
                  % (nm, s["tank_dE_total_fJ"], s["EGT"], s["EHI"], s["EI1"], etu))
        if r["value_fails"]:
            for f in r["value_fails"][:8]:
                print("   FAIL", f)
        print("  park_pre implied drain: %.1f pW (dedicated park deck: 871 pW tank-only)"
              % (r["park_pre_implied_pW"] or 0))
        wz = r["zcs_residual_uA"]
        print("  worst |IZ| rise %.2f uA, return %.2f uA" % (
            max(abs(x) for w in wz.values() for x in w["IZ"]),
            max(abs(x) for w in wz.values() for x in w["IZQ"])))
    json.dump(out, open("CYCLES_%s.json" % pref, "w"), indent=1)
