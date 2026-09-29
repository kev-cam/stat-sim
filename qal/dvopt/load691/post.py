#!/usr/bin/env python3
"""load691 post-processing.  Two jobs, both off the RAW .prn:

 1. the C2 rail-drain quantity under BOTH checkpoint conventions (amendment L2) --
    the sk path's ZCS instant and the lsw grid's t_open + 7 ps -- read as V(bka)
    from this row's own waveform, plus the end value and the post-open ring extremes.
 2. the two objective surfaces built ONLY from measured intervals of this deck's own
    timeline: t_hop, the post-arrival settle (t_out90_final_max - t_rail90), and the
    end-to-end level time t_valid90 (switch close -> all outputs within 10% of the
    instantaneous rail).  No surrogate, no floor curve.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
T0 = 50.0
CMOS = 92.8
GATE = 0.1478


def trace(prn, node="V(BKA)"):
    with open(prn) as fh:
        hdr = [h.upper() for h in fh.readline().split()]
        it, ib = hdr.index("TIME"), hdr.index(node)
        out = []
        for line in fh:
            p = line.split()
            if len(p) < len(hdr):
                continue
            try:
                out.append((float(p[it]) * 1e12, float(p[ib])))
            except ValueError:
                continue
    return out


def at(tr, tps):
    prev = tr[0]
    for r in tr:
        if r[0] >= tps:
            if r[0] == prev[0]:
                return r[1]
            f = (tps - prev[0]) / (r[0] - prev[0])
            return prev[1] + f * (r[1] - prev[1])
        prev = r
    return tr[-1][1]


def main():
    rows = json.load(open(os.path.join(HERE, "rows.json")))
    out = {}
    for tag, r in sorted(rows.items(), key=lambda kv: -kv[1]["L_nH"]):
        prn = os.path.join(HERE, "h_%s.cir.prn" % tag)
        t_open = T0 + r["t_hop_ps"]
        tr = trace(prn)
        post = [p for p in tr if p[0] >= t_open]
        va_zcs = at(tr, t_open)
        va_c7 = at(tr, t_open + 7.0)
        s = dict(
            dv=r["dv"], L_nH=r["L_nH"], W_um=r["total_um"], cl_fF=r["cl_fF"],
            t_hop_ps=r["t_hop_ps"], VBEND=r["VBEND"], VBPK=r["VBPK"],
            VBPK_over_VBEND=r["VBPK"] / r["VBEND"],
            t_rail90_ps=r["t_rail90_lastentry_ps"],
            t_out90_max_ps=r["t_out90_final_max_ps"],
            post_arrival_settle_ps=r["t_settle_after_rail_ps"],
            t_valid90_ps=r["t_valid90_ps"], t_settle90_ps=r["t_settle90_ps"],
            s_end_min_pct=r["s_end_min"],
            VA_open_ZCS=va_zcs, VA_open_C7=va_c7,
            VA_open_harness=r["VA_open"],
            VA_end=post[-1][1], VA_ring_max=max(p[1] for p in post),
            VA_ring_min=min(p[1] for p in post),
            C2_ZCS="PASS" if va_zcs <= GATE else "FAIL",
            C2_C7="PASS" if va_c7 <= GATE else "FAIL",
            C3_abs="PASS" if r["VBEND"] >= 0.60 else "FAIL",
            C1_all8_end="PASS" if r["s_end_min"] >= 90.0 else "FAIL",
        )
        s["SUM_measured_ps"] = s["t_hop_ps"] + s["post_arrival_settle_ps"]
        s["MAX_measured_ps"] = max(s["t_hop_ps"], s["post_arrival_settle_ps"])
        s["level_vs_CMOS"] = s["t_valid90_ps"] / CMOS
        out[tag] = s
    json.dump(out, open(os.path.join(HERE, "surfaces_load.json"), "w"), indent=1)
    hdr = ("tag                 L    W  | t_hop  VBEND VBPK/VB rail90 out90  post | "
           "SUM_m  MAX_m  val90  x CMOS | VA_zcs VA_+7 VA_end  ring | C2z C2_7 C1 C3")
    print(hdr)
    print("-" * len(hdr))
    for tag, s in sorted(out.items(), key=lambda kv: -kv[1]["L_nH"]):
        print("%-18s %5.1f %4.0f | %6.2f %.4f %6.3f %6.2f %6.2f %6.2f | "
              "%6.2f %6.2f %6.2f %6.3f | %+.4f %+.4f %+.4f %+.2f/%+.2f | %-4s %-4s %-4s %-4s"
              % (tag, s["L_nH"], s["W_um"], s["t_hop_ps"], s["VBEND"],
                 s["VBPK_over_VBEND"], s["t_rail90_ps"], s["t_out90_max_ps"],
                 s["post_arrival_settle_ps"], s["SUM_measured_ps"],
                 s["MAX_measured_ps"], s["t_valid90_ps"], s["level_vs_CMOS"],
                 s["VA_open_ZCS"], s["VA_open_C7"], s["VA_end"],
                 s["VA_ring_max"], s["VA_ring_min"],
                 s["C2_ZCS"], s["C2_C7"], s["C1_all8_end"], s["C3_abs"]))


if __name__ == "__main__":
    main()
