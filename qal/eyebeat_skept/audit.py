#!/usr/bin/env python3
"""SK_D: independent recomputation of the SWEEP.json cross-T aggregation and
audit of the budget composition (sum vs RSS per term; sigma_trip counting)."""
import json, math, os

EB = "/usr/local/src/stat-sim/qal/eyebeat"
TS = [60, 90, 120, 150, 200, 250, 300]
SIG = 6.441

sweep = json.load(open(os.path.join(EB, "SWEEP.json")))
D = {T: json.load(open(os.path.join(EB, "T%g" % T, "EYEBEAT.json"))) for T in TS}

print("=== A. recompute per-T worst aggregation from T*/EYEBEAT.json ===")
dev = 0
for T in TS:
    d = D[T]
    for tn in ("0mV", "3sigma"):
        ops, wds, wot, slk, hts, clip = [], [], [], [], [], False
        for k in "123":
            z = d["banks"][k]["EYES"]["EYE2"].get(tn, {})
            if "EYE" in z or not z:
                ops = None
                break
            ops.append(z["opening_minus_c_ps"]); wds.append(z["WIDTH_ps"])
            wot.append(z["WIDTH_over_T"]); slk.append(z["setup_slack_ps"])
            h = [x for x in (z["HEIGHT_at_sampling_HIGH_mV"],
                             z["HEIGHT_at_sampling_LOW_mV"]) if x is not None]
            hts.append(min(h)); clip = clip or z["WIDTH_IS_LOWER_BOUND"]
        w = [r for r in sweep["per_T"] if r["T"] == T][0]["worst"].get(tn, {})
        if ops is None:
            ok = "EMPTY" in w or not w
            print("T%-4g %-7s EMPTY  sweep agrees: %s" % (T, tn, ok))
            continue
        mine = dict(opening_minus_c_worst_ps=max(ops), WIDTH_min_ps=min(wds),
                    WIDTH_min_over_T=min(wot), setup_slack_min_ps=min(slk),
                    HEIGHT_at_sampling_min_mV=min(hts),
                    width_is_lower_bound=clip)
        bad = {kk: (mine[kk], w.get(kk)) for kk in mine
               if not (isinstance(mine[kk], bool) and mine[kk] == w.get(kk)) and
               (isinstance(mine[kk], bool) or abs(mine[kk] - w.get(kk, 1e18)) > 1e-3)}
        if bad:
            dev += 1
            print("T%-4g %-7s MISMATCH %s" % (T, tn, bad))
        else:
            print("T%-4g %-7s OK" % (T, tn))
    # stranded + floor
    sh = min(d["banks"][k]["STRANDED_HIGH"]["min_HIGH_during_drain_V"] for k in "123")
    fl = min(d["banks"][k]["POST_RETURN_FLOOR_EYE2"]["floor_mV"] for k in "123")
    r = [r for r in sweep["per_T"] if r["T"] == T][0]
    assert abs(sh - r["stranded_high_min_V"]) < 1e-5, (T, sh, r["stranded_high_min_V"])
    assert abs(fl - r["post_return_floor_min_mV"]) < 1e-3
    # value_correct flag
    vc = all(v["all_32_gates_value_correct"] for v in d["value_check"].values())
    assert vc == r["value_correct"], (T, vc)
print("aggregation deviations:", dev)

print()
print("=== B. budget composition audit ===")
JIT_WC, JIT_R, DRIFT = 61.6, 61.6 / 2.0, 0.46 * 10
print("terms: JIT worst-case %.1f ps (GIVEN, N-invariant, a WORST-CASE bound)" % JIT_WC)
print("       JIT random     %.1f ps (= 61.6/sqrt(4): a p-p WC bound scaled by 1/sqrt(N) -- convention mix, see below)" % JIT_R)
print("       drift          %.1f ps (0.46 ps/K x +/-10 K ASSUMED; systematic)" % DRIFT)
print("       sigma_trip     %.3f mV charged as 3*sigma = %.3f mV IN THE THRESHOLD (margin domain)" % (SIG, 3 * SIG))
print("composition: SLACK_3sigma > JIT + DRIFT  (straight SUM, no RSS)")
print()
for T in (120, 150, 200, 250, 300):
    r = [x for x in sweep["per_T"] if x["T"] == T][0]
    s = r["worst"]["3sigma"]["setup_slack_min_ps"]
    print("T=%-4g slack3s %8.4f | vs WC %.1f: %s (margin %+7.4f) | vs RAND %.1f: %s (margin %+7.4f)"
          % (T, s, JIT_WC + DRIFT, "PASS" if s > JIT_WC + DRIFT else "fail",
             s - (JIT_WC + DRIFT), JIT_R + DRIFT,
             "PASS" if s > JIT_R + DRIFT else "fail", s - (JIT_R + DRIFT)))
print()
print("double-count check: does the 3sigma slack already contain a trip-noise ps charge?")
for T in (150, 200):
    r = [x for x in sweep["per_T"] if x["T"] == T][0]
    d0 = r["worst"]["0mV"]["opening_minus_c_worst_ps"]
    d3 = r["worst"]["3sigma"]["opening_minus_c_worst_ps"]
    print("T=%-4g opening shift 0mV -> 3sigma: %.4f ps (= 19.323 mV / ~%.1f mV/ps edge slope)"
          % (T, d3 - d0, 3 * SIG / max(d3 - d0, 1e-9)))
print("sigma_trip appears ONCE (threshold). The ps budget contains no second trip term. OK")
print()
print("erasure temperature: (slack - JIT_WC)/0.46 at T=200:",
      round(( [x for x in sweep['per_T'] if x['T']==200][0]['worst']['3sigma']['setup_slack_min_ps'] - JIT_WC)/0.46, 1), "K")
print("local-spread variant: charge 9.2 + 4.6 = 13.8 ps ->",
      "T=150 slack %.4f %s" % ([x for x in sweep['per_T'] if x['T']==150][0]['worst']['3sigma']['setup_slack_min_ps'],
      "PASS" if [x for x in sweep['per_T'] if x['T']==150][0]['worst']['3sigma']['setup_slack_min_ps'] > 13.8 else "fail"))
print()
print("=== C. sustainable beat + crossover arithmetic ===")
CM = 57.143
for nm in ("worst_case_data", "random_data_N4"):
    c = sweep["SUSTAINABLE_BEAT"][nm]
    tq = c["sustainable_T_ps"]
    print(nm, "T=", tq, "budget", c["budget_charged_ps"],
          "vs_cmos claim", c["vs_cmos_level_2fF"], "recompute", round(tq / CM, 3))
    for treg, want in c["crossover_D_per_t_reg"].items():
        print("   D*(%s) claim %s recompute %.2f" % (treg, want, float(treg) / (tq - CM)))
print()
print("RSS alternative (if all three terms were treated as independent 3sigma randoms):")
for T in (150, 200):
    s = [x for x in sweep["per_T"] if x["T"] == T][0]["worst"]["3sigma"]["setup_slack_min_ps"]
    rss_wc = math.sqrt(JIT_WC**2 + DRIFT**2)
    rss_r = math.sqrt(JIT_R**2 + DRIFT**2)
    print("T=%-4g RSS(WC,drift)=%.1f -> %s | RSS(RAND,drift)=%.1f -> %s"
          % (T, rss_wc, "PASS" if s > rss_wc else "fail",
             rss_r, "PASS" if s > rss_r else "fail"))
