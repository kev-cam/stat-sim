#!/usr/bin/env python3
"""Cross-T composition: the beat-sweep verdict tables, the optimum, the
budget-composed sustainable beat, and both CMOS comparisons.  Reads only the
per-T EYEBEAT.json files.  Everything labeled MEASURED / DERIVED / ASSUMED."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
TS = [60, 90, 120, 150, 200, 250, 300]
JIT_WC = 61.6          # GIVEN: worst-case data zero spread, N-invariant
JIT_RAND = 61.6 / 2.0  # GIVEN scaling 1/sqrt(N), N = 4 hops -> 30.8
DRIFT = 0.46 * 10      # ASSUMED +/-10 K -> 4.6 ps
CMOS_LVL = 57.143      # GIVEN load-matched at 2 fF (this deck's CL)
CMOS_LVL_ALT = 94.174  # GIVEN at 6.91 fF (context only)
TREG = [307.1, 335.7, 390.0]


def main():
    D = {}
    for T in TS:
        f = os.path.join(HERE, "T%g" % T, "EYEBEAT.json")
        if os.path.exists(f):
            D[T] = json.load(open(f))
    rows = []
    for T in sorted(D):
        d = D[T]
        val_ok = all(v["all_32_gates_value_correct"] for v in d["value_check"].values())
        a6_ok = all(v["A6_pass"] for v in d["a6"].values())
        # worst over MEASURED banks 1-3
        w = {}
        for tn in ("0mV", "3sigma"):
            ops, wds, slk, wot, hts = [], [], [], [], []
            clip = False
            for k in ("1", "2", "3"):
                z = d["banks"][k]["EYES"]["EYE2"].get(tn, {})
                if "EYE" in z or not z:
                    ops.append(None)
                    continue
                ops.append(z["opening_minus_c_ps"])
                wds.append(z["WIDTH_ps"])
                wot.append(z["WIDTH_over_T"])
                slk.append(z["setup_slack_ps"])
                h = [x for x in (z["HEIGHT_at_sampling_HIGH_mV"],
                                 z["HEIGHT_at_sampling_LOW_mV"]) if x is not None]
                hts.append(min(h) if h else None)
                clip = clip or z["WIDTH_IS_LOWER_BOUND"]
            if any(o is None for o in ops):
                w[tn] = dict(EMPTY=True)
                continue
            w[tn] = dict(opening_minus_c_worst_ps=max(ops),
                         WIDTH_min_ps=min(wds), WIDTH_min_over_T=min(wot),
                         setup_slack_min_ps=min(slk),
                         HEIGHT_at_sampling_min_mV=min(x for x in hts if x is not None),
                         width_is_lower_bound=clip)
        fl = min(d["banks"][k]["POST_RETURN_FLOOR_EYE2"]["floor_mV"]
                 for k in ("1", "2", "3"))
        flt = {k: d["banks"][k]["POST_RETURN_FLOOR_EYE2"] for k in ("1", "2", "3")}
        lag = {k: d["banks"][k]["TRACKING_LAG"] for k in ("1", "2", "3")}
        sh = min(d["banks"][k]["STRANDED_HIGH"]["min_HIGH_during_drain_V"]
                 for k in ("1", "2", "3"))
        rows.append(dict(T=T, value_correct=val_ok, A6=a6_ok, worst=w,
                         post_return_floor_min_mV=fl, floors=flt,
                         stranded_high_min_V=sh, lag=lag))
    out = dict(_inputs=dict(JIT_worstcase_ps=JIT_WC, JIT_random_N4_ps=JIT_RAND,
                            drift_ps_ASSUMED_pm10K=DRIFT,
                            cmos_level_ps_load_matched_2fF=CMOS_LVL,
                            cmos_level_ps_6p91fF_context=CMOS_LVL_ALT,
                            t_reg_ps_MEASURED=TREG,
                            liberty_optimism="1.11-1.21x"),
               per_T=rows)

    # ---- P1 verdict material
    ok = [r for r in rows if r["value_correct"] and r["A6"]
          and "EMPTY" not in r["worst"]["3sigma"]]
    fr = [(r["T"], r["worst"]["3sigma"]["WIDTH_min_over_T"]) for r in ok]
    op = [(r["T"], r["worst"]["3sigma"]["opening_minus_c_worst_ps"]) for r in ok]
    op0 = [(r["T"], r["worst"]["0mV"]["opening_minus_c_worst_ps"]) for r in ok
           if "EMPTY" not in r["worst"]["0mV"]]
    out["P1_material"] = dict(
        fractional_eye_W3s_over_T_vs_T=fr,
        fractional_monotone_increasing_as_T_shrinks=all(
            fr[i][1] > fr[i + 1][1] for i in range(len(fr) - 1)),
        opening_minus_c_vs_T_3sigma=op, opening_minus_c_vs_T_0mV=op0,
        collision_Ts=[r["T"] for r in rows if not (
            r["value_correct"] and "EMPTY" not in r["worst"]["3sigma"]
            and r["worst"]["3sigma"]["opening_minus_c_worst_ps"] < r["T"])])
    # ---- P2 material
    out["P2_material"] = dict(
        stranded_high_min_V_vs_T=[(r["T"], r["stranded_high_min_V"]) for r in rows],
        committed_peer_fed_stranded_V=[0.336, 0.455])
    # ---- optimum + sustainable beat
    if ok:
        out["OPTIMUM"] = dict(
            T_max_absolute_W3s=max(ok, key=lambda r: r["worst"]["3sigma"]["WIDTH_min_ps"])["T"],
            T_max_fractional_W3s_over_T=max(ok, key=lambda r: r["worst"]["3sigma"]["WIDTH_min_over_T"])["T"])
        sust, sust_r = None, None
        for r in sorted(ok, key=lambda r: r["T"]):
            s = r["worst"]["3sigma"]["setup_slack_min_ps"]
            if sust is None and s > JIT_WC + DRIFT:
                sust = r["T"]
            if sust_r is None and s > JIT_RAND + DRIFT:
                sust_r = r["T"]
        comp = {}
        for nm, tq in (("worst_case_data", sust), ("random_data_N4", sust_r)):
            if tq is None:
                comp[nm] = dict(sustainable_T_ps=None,
                                note="no swept T passes; budget exceeds slack everywhere")
                continue
            comp[nm] = dict(
                sustainable_T_ps=tq,
                budget_charged_ps=(JIT_WC if nm == "worst_case_data" else JIT_RAND) + DRIFT,
                vs_cmos_level_2fF=round(tq / CMOS_LVL, 3),
                crossover_D_per_t_reg={str(t): (round(t / (tq - CMOS_LVL), 2)
                                                if tq > CMOS_LVL else "QAL_wins_all_D")
                                       for t in TREG},
                note="crossover D* = t_reg/(T-57.143): pipeline chop depth beyond which "
                     "the QAL wave out-THROUGHPUTS flopped CMOS (one datum per beat per "
                     "level, hold depth permitting). THROUGHPUT only, never latency.")
        out["SUSTAINABLE_BEAT"] = comp
    json.dump(out, open(os.path.join(HERE, "SWEEP.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("P1_material", "P2_material") if k in out}, indent=1))
    if "OPTIMUM" in out:
        print(json.dumps(out["OPTIMUM"], indent=1))
        print(json.dumps(out.get("SUSTAINABLE_BEAT"), indent=1))


if __name__ == "__main__":
    main()
