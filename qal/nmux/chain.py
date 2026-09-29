#!/usr/bin/env python3
"""(c) THE DEGRADATION QUESTION -- does a restoring cell repair the degraded high?

Six tank-fed banks, alternating [restoring QAL cell bank] -> [pass structure] ->
[next restoring bank].  Structure is the committed qal/resv ch_res20 chain with
a pass structure inserted in every inter-bank hop; the `wire` variant IS the
committed chain and is the control.

TANK-FED only (pre-registration P5): the campaign record says peer-fed fails for
everything, so testing there would measure the rail, not the pass structure.

Variants
  pass : wire | nmos | tg          (what sits between bank k out and bank k+1 in)
  rest : std (1.12p/0.74n, committed) | skew (0.15p/1.48n, the boundary-study fix)

Separation at depth k = V(o_k HIGH) - V(o_k LOW) at bank k's own boundary,
against the 6.44 mV sigma floor, sign checked at every depth.
"""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import nm

HERE = nm.HERE
# REDUCED GEOMETRY (see AMENDMENT A7): 6 banks kept -- depth is the whole
# question -- but 4 bits per bank instead of the committed 8, and a 0.2 ps max
# step instead of 0.0884183 ps.  The committed ch_res20 deck is 1416 lines over
# 2500 ps and does not finish in usable time on this box.  4 bits still gives two
# HIGH and two LOW cells per bank, which is what a min(up) - max(down) separation
# needs.  The rail is NOT compensated for the missing cells: it therefore comes
# out slightly HIGHER than the committed 1.326 V, which makes the nMOS-only case
# HARDER, not easier.  The delivered rail is reported at every depth.
NB, NW_ = 6, 4                 # banks, bits per bank
CRES, VRES = 719.58, 1.2       # committed reservoir (ca_mult = 20)
LT, RS, VHI = 15.0, 10.0, 1.5
SWN, SWP = 10.0, 20.0
CLB, CY = 2.0, 2.0
VGH = 1.5
T0, TSTEP = 200.0, 300.0       # bank 1 closes at 200 ps, one bank per 300 ps
TEND = 2500.0
SIGMA_FLOOR_MV = 6.44
# committed res20 zeros (probe seed; re-probed per variant)
TZ0 = [145.834, 141.507, 134.503, 129.140, 124.667, 121.429]

REST = {"std": (1.12, 0.74), "skew": (0.15, 1.48)}


def build(pass_kind, rest_kind, w, tz, tag):
    wp, wn = REST[rest_kind]
    D = nm.head()
    D += ["VHI vhi 0 %g" % VHI, "VRES vres 0 %g" % VRES,
          "CRES1 res1 0 %gf" % CRES,
          "VSEL sel 0 %g" % VGH, "VSELB selb 0 0", "VNW nw 0 %g" % VGH]

    # ---- per bank: transfer path from the shared reservoir, own rail ----
    for k in range(1, NB + 1):
        tc = T0 + TSTEP * (k - 1)
        to = tc + tz[k - 1]
        D += ["L%d a%d mid%d %gn" % (k, k, k, LT),
              "R%d mid%d sw%d %g" % (k, k, k, RS),
              "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, k, SWN),
              "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, k, SWP),
              "XSWSN%d a%d gt%d res1 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, SWN),
              "XSWSP%d a%d gtp%d res1 vhi sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, SWP),
              "VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (k, k, tc - 2, tc, VHI, to, VHI, to + 2),
              "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (k, k, VHI, tc - 2, VHI, tc, to, to + 2, VHI),
              "VMG%d gn%d 0 0" % (k, k)]

    # ---- bank 1 inputs are static; banks 2..6 take the previous bank's output
    #      through the pass structure under test ----
    for k in range(1, NB + 1):
        for i in range(NW_):
            hi = (i % 2 == 0)
            if k == 1:
                src = "in1_%d" % i
                D += ["VI1_%d in1_%d 0 %g" % (i, i, VRES if hi else 0.0)]
            else:
                src = "g%d_%d" % (k, i)          # pass-structure output node
                a = "o%d_%d" % (k - 1, i)        # data leg A (the real datum)
                b = "o%d_%d" % (k - 1, (i + 1) % NW_)   # leg B (the other polarity)
                if pass_kind == "wire":
                    src = a
                elif pass_kind == "nmos":
                    D += ["XPN%d_%dA %s sel %s 0 sg13_lv_nmos w=%gu l=0.13u" % (k, i, a, src, w),
                          "XPN%d_%dB %s selb %s 0 sg13_lv_nmos w=%gu l=0.13u" % (k, i, b, src, w),
                          "CPY%d_%d %s 0 %gf" % (k, i, src, CY)]
                elif pass_kind == "tg":
                    D += ["XPN%d_%dA %s sel %s 0 sg13_lv_nmos w=%gu l=0.13u" % (k, i, a, src, w),
                          "XPP%d_%dA %s selb %s nw sg13_lv_pmos w=%gu l=0.13u" % (k, i, a, src, w),
                          "XPN%d_%dB %s selb %s 0 sg13_lv_nmos w=%gu l=0.13u" % (k, i, b, src, w),
                          "XPP%d_%dB %s sel %s nw sg13_lv_pmos w=%gu l=0.13u" % (k, i, b, src, w),
                          "CPY%d_%d %s 0 %gf" % (k, i, src, CY)]
                else:
                    raise ValueError(pass_kind)
            D += ["XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                  % (k, i, k, i, src, k, k, wp),
                  "XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                  % (k, i, k, i, src, k, k, wn),
                  "CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, CLB)]

    D += [".ic V(res1)=%g " % VRES +
          " ".join("V(rail%d)=0 V(a%d)=0" % (k, k) for k in range(1, NB + 1))]
    pr = ["V(res1)"] + ["V(rail%d)" % k for k in range(1, NB + 1)] + \
         ["I(L%d)" % k for k in range(1, NB + 1)]
    for k in range(1, NB + 1):
        pr += ["V(o%d_0)" % k, "V(o%d_1)" % k]
        if k > 1 and pass_kind != "wire":
            pr += ["V(g%d_0)" % k, "V(g%d_1)" % k]  # both parities printed
    D += [".print tran " + " ".join(pr[:12])]
    for i in range(12, len(pr), 12):
        D[-1] += ""
        D.append("+ " + " ".join(pr[i:i + 12]))
    D += [".tran 0.1p %gp 0 0.2p" % TEND, ".end", ""]
    p = os.path.join(HERE, tag + ".cir")
    open(p, "w").write("\n".join(D))
    return p


def sh(path):
    t0 = time.monotonic()
    r = subprocess.run([nm.XYCE, path], cwd=HERE, env=nm.ENV,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, time.monotonic() - t0, r.stdout.decode()[-800:]


def zeros(w):
    z = []
    for k in range(1, NB + 1):
        tc = T0 + TSTEP * (k - 1)
        t = w.zero_after("I(L%d)" % k, tc + 5)
        z.append((t - tc) if t else TZ0[k - 1])
    return z


def one(a):
    pass_kind, rest_kind, wid = a
    tag = "ch_%s_%s_w%03d" % (pass_kind, rest_kind, round(wid * 100))
    tz, shifts = list(TZ0), None
    # seed with the committed res20 zeros; re-probe once and re-run only if the
    # added pass load actually moved a zero by more than 3 ps (the boundary study
    # measured that load on CELL OUTPUTS barely joins the resonance, so it
    # usually will not).  Each of these decks is ~150 devices over 2500 ps.
    for it in range(2):
        p = build(pass_kind, rest_kind, wid, tz, tag)
        rc, dt, tail = sh(p)
        if rc != 0:
            return {"tag": tag, "FAIL": "rc=%d it=%d" % (rc, it), "tail": tail}
        w = nm.W(p + ".prn")
        nz = zeros(w)
        shifts = [b - a for a, b in zip(tz, nz)]
        if max(abs(x) for x in shifts) < 3.0:
            break
        tz = nz
    sep, rails, hi_v, lo_v, gate_v = [], [], [], [], []
    for k in range(1, NB + 1):
        tb = T0 + TSTEP * k - 1.0          # bank k's own boundary
        # polarity alternates by bank: HIGH output of bank k is index (k % 2)
        ih, il = k % 2, 1 - k % 2
        hi = w.at("V(o%d_%d)" % (k, ih), tb)
        lo = w.at("V(o%d_%d)" % (k, il), tb)
        sep.append((hi - lo) * 1e3); rails.append(w.at("V(rail%d)" % k, tb))
        hi_v.append(hi); lo_v.append(lo)
        if k > 1 and pass_kind != "wire":
            # the pass-structure output feeding bank k is the INPUT of bank k's
            # cell, so its HIGH index is the opposite parity again
            gate_v.append([w.at("V(g%d_%d)" % (k, il), tb),
                           w.at("V(g%d_%d)" % (k, ih), tb)])
    depth_ok = 0
    for s in sep:
        if s > SIGMA_FLOOR_MV:
            depth_ok += 1
        else:
            break
    return {"tag": tag, "pass": pass_kind, "rest": rest_kind, "w_um": wid,
            "sec": round(dt, 1), "tz_ps": tz, "zero_shift_ps": shifts,
            "separation_mV": sep, "rail_at_boundary_V": rails,
            "out_high_V": hi_v, "out_low_V": lo_v,
            "pass_out_high_low_V": gate_v,
            "margin_over_floor_x": [s / SIGMA_FLOOR_MV for s in sep],
            "depth_above_floor_correct_sign": depth_ok}


def main():
    wid = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
    # (wire, std) is the committed qal/resv ch_res20 chain itself and is run as
    # instrument gate G3 in run_cells.py, so it is not repeated here.
    jobs = [("wire", "std", wid), ("nmos", "std", wid), ("tg", "std", wid),
            ("wire", "skew", wid), ("nmos", "skew", wid)]
    if len(sys.argv) > 2:
        jobs = [j for j in jobs if j[0] in sys.argv[2].split(",")]
    with ThreadPoolExecutor(max_workers=3) as ex:
        rows = list(ex.map(one, jobs))
    json.dump(rows, open(os.path.join(HERE, "chain_rows_w%03d.json"
                                      % round(wid * 100)), "w"), indent=1)
    for r in rows:
        if "FAIL" in r:
            print(r["tag"], r["FAIL"]); continue
        print("%-22s depth=%d  sep_mV=%s" %
              (r["tag"], r["depth_above_floor_correct_sign"],
               ["%.1f" % s for s in r["separation_mV"]]))


if __name__ == "__main__":
    main()
