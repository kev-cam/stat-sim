#!/usr/bin/env python3
"""qal/rfast composition: RESULTS.json from the per-cell EYEBEAT.json records,
the SEQA6 records and the two instrument anchors.  Labels MEASURED / DERIVED /
ASSUMED.  Reads only; no simulation."""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TIMER = 7.272          # INHERITED (ASSUMED at this drive) qal/eye/p2 U2
CMOS_LVL = 52.510      # MEASURED qal/fcrit_skept (2 fF load-matched)
TREG_2FF = 315.4       # DERIVED from MEASURED 307.1 @0fF / 335.7 @6.91fF
COMMITTED_OPEN_L15 = 129.6      # MEASURED qal/eyebeat at VGH=1.5, W=30
SQRT_PRED = {15: 129.6, 10: 105.8, 6: 82.0, 3: 58.0}


def cell(L, W, T):
    f = os.path.join(HERE, "L%gW%g" % (L, W), "T%g" % T, "EYEBEAT.json")
    if not os.path.exists(f):
        return None
    d = json.load(open(f))
    pats = d["patterns"]
    r = dict(L_nH=L, W_um=W, T_ps=T, patterns=pats,
             patterns_A6_pass=d.get("patterns_A6_pass"),
             A6_worst_uA=max(d["a6"][p]["worst_uA"] for p in pats),
             A6_strict_all_patterns=bool(
                 all(d["a6"][p]["A6_pass"] for p in pats)),
             value_all_correct=bool(all(
                 d["value_check"][p]["all_32_gates_value_correct"]
                 for p in pats)))
    ops, o3s, slk, bud, loc, wc, flo, hts, close = [], [], [], [], [], [], [], [], []
    for k in ("1", "2", "3"):
        b = d["banks"][k]
        z = b["EYES"]["EYE2"].get("0mV", {})
        if "opening_minus_c_ps" not in z:
            return dict(r, EYE="EMPTY")
        ops.append(z["opening_minus_c_ps"])
        h = [x for x in (z["HEIGHT_at_sampling_HIGH_mV"],
                         z["HEIGHT_at_sampling_LOW_mV"]) if x is not None]
        hts.append(min(h))
        close.append(z.get("closing_minus_r_ps"))
        bd = b.get("BUDGET_G3", {})
        if "budget_ps" in bd:
            o3s.append(bd["opening_3sig_total_ps"])
            slk.append(bd["setup_slack_0mV_ps"])
            bud.append(bd["budget_ps"])
            loc.append(bd["PASS_local"])
            wc.append(bd["PASS_worstcase"])
        flo.append(b["POST_RETURN_FLOOR_EYE2"]["floor_mV"])
    r.update(opening_0mV_worst_ps=max(ops), opening_per_bank_ps=ops,
             opening_3sig_total_worst_ps=(max(o3s) if o3s else None),
             setup_slack_min_ps=(min(slk) if slk else None),
             budget_G3_max_ps=(max(bud) if bud else None),
             G3_local_PASS=bool(loc and all(loc)),
             G3_worstcase_PASS=bool(wc and all(wc)),
             post_return_floor_min_mV=min(flo),
             HEIGHT_at_sampling_min_mV=min(hts),
             closing_minus_r_per_bank_ps=close)
    r["ALL_STRICT_PASS"] = bool(r["A6_strict_all_patterns"]
                                and r["value_all_correct"] and r["G3_local_PASS"])
    r["PASS_A2_floor_documented"] = bool(r["value_all_correct"]
                                         and r["G3_local_PASS"])
    return r


def main():
    cells = []
    for d in sorted(glob.glob(os.path.join(HERE, "L*W*", "T*"))):
        m = re.match(r".*/L([\d.]+)W([\d.]+)/T([\d.]+)$", d)
        if not m:
            continue
        L, W, T = (float(m.group(i)) for i in (1, 2, 3))
        c = cell(L, W, T)
        if c:
            cells.append(c)
    seq = []
    for f in sorted(glob.glob(os.path.join(HERE, "seqA6", "*", "SEQA6.json"))):
        seq.append(json.load(open(f)))
    out = dict(
        _what="qal/rfast RESULTS -- the (L, T) sweep on restoring banktank "
              "banks at VGH = 2.174 V.  PRE_REGISTERED.json sha256 70fac658..., "
              "amendments A1-A6 in AMENDMENT.md.",
        _labels="openings/slacks/floors/heights MEASURED; budget = MEASURED "
                "mismatch + 7.272 ps timer INHERITED-ASSUMED; sqrt predictions "
                "DERIVED from the committed 129.6 ps; CMOS level 52.510 ps "
                "MEASURED (fcrit_skept); t_reg(2fF)=315.4 DERIVED from MEASURED "
                "307.1/335.7; VGH=2.174 V reliability ASSUMED (no HV card).",
        ANCHORS=dict(IC1=json.load(open(os.path.join(HERE, "IC1.json"))),
                     IC2=json.load(open(os.path.join(HERE, "IC2.json")))),
        CELLS=cells,
        SEQUENTIAL_A6_VS_BEAT=seq,
        SQRT_PREDICTION_DERIVED=SQRT_PRED)

    # frontier under both readings
    ok_strict = [c for c in cells if c.get("ALL_STRICT_PASS")]
    ok_doc = [c for c in cells if c.get("PASS_A2_floor_documented")]
    for nm, S in (("FRONTIER_STRICT", ok_strict), ("FRONTIER_A2_DOCUMENTED", ok_doc)):
        if not S:
            out[nm] = None
            continue
        tmin = min(c["T_ps"] for c in S)
        best = [c for c in S if c["T_ps"] == tmin]
        out[nm] = dict(T_ps=tmin, cells=[
            dict(L_nH=c["L_nH"], W_um=c["W_um"],
                 opening_ps=c["opening_0mV_worst_ps"],
                 slack_ps=c["setup_slack_min_ps"],
                 budget_ps=c["budget_G3_max_ps"],
                 A6_worst_uA=c["A6_worst_uA"],
                 floor_mV=c["post_return_floor_min_mV"],
                 height_mV=c["HEIGHT_at_sampling_min_mV"]) for c in best])
    json.dump(out, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    print("cells:", len(cells), " strict-pass:", len(ok_strict))
    print("FRONTIER_STRICT:", json.dumps(out["FRONTIER_STRICT"]))


if __name__ == "__main__":
    main()
