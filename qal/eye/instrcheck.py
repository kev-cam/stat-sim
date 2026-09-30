#!/usr/bin/env python3
"""STEP (b): reproduce the committed banktank headline row DIGIT-CHECKED.

IC1  the deck regenerates BYTE-IDENTICALLY from bt.py at the committed step.
IC2  every numeric .mt0 key agrees to <= 1e-9 relative (<= 1e-12 absolute for
     keys whose committed value is < 1e-9).
IC3  the derived scalars pre-stated in PRE_REGISTERED.json reproduce to every
     printed digit.
IC4  >= 99.0 % of .mt0 keys pass IC2, else the study STOPS.

Run: python3 instrcheck.py deck        (IC1 only, no simulation)
     python3 instrcheck.py run         (re-run at the COMMITTED 0.25 ps step)
     python3 instrcheck.py run_fine    (re-run at MY 0.10 ps step, convergence)
     python3 instrcheck.py score
"""
import json, os, re, subprocess, sys
import eyeharness as EH

HERE = EH.HERE
BTDIR = EH.BTDIR
TAG = "m10_T200_H4_dv1200_free"
COMMITTED_CIR = os.path.join(BTDIR, "c_%s.cir" % TAG)
COMMITTED_MT0 = os.path.join(BTDIR, "c_%s.cir.mt0" % TAG)
COMMITTED_ROW = os.path.join(BTDIR, "row_%s.json" % TAG)
ZEROS = os.path.join(BTDIR, "zeros_m10_dv1200_T200_H4.json")
ARGS = dict(m=10.0, T=200.0, H=4, dv=1.2, mode="free")


def gen(pstep, mstep):
    EH.redirect()
    EH.set_pattern(EH.PATTERNS["P0"])
    EH.set_steps(pstep, mstep)
    z = json.load(open(ZEROS))
    lines, S = EH.bt.deck(ARGS["m"], ARGS["T"], ARGS["H"], ARGS["dv"],
                          mode=ARGS["mode"], tzr=z["tzr"], tzq=z["tzq"])
    return lines, S


def cmd_deck():
    lines, S = gen(0.1, 0.25)                    # the COMMITTED steps
    mine = "\n".join(lines) + "\n"
    ref = open(COMMITTED_CIR).read()
    out = {"IC1_byte_identical_regeneration": mine == ref,
           "mine_bytes": len(mine), "committed_bytes": len(ref)}
    if mine != ref:
        ml, rl = mine.splitlines(), ref.splitlines()
        diffs = [{"line": i + 1, "mine": ml[i] if i < len(ml) else None,
                  "committed": rl[i] if i < len(rl) else None}
                 for i in range(max(len(ml), len(rl)))
                 if (ml[i] if i < len(ml) else None) != (rl[i] if i < len(rl) else None)]
        out["n_differing_lines"] = len(diffs)
        out["first_differing_lines"] = diffs[:10]
    open(os.path.join(HERE, "IC1.json"), "w").write(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:2000])
    return out["IC1_byte_identical_regeneration"]


def cmd_run(fine):
    pstep, mstep = (0.05, 0.10) if fine else (0.1, 0.25)
    lines, S = gen(pstep, mstep)
    fn = "ic_%s%s.cir" % (TAG, "_fine" if fine else "")
    p, msg = EH.bt.run(fn, lines, timeout=5400)
    print(msg, flush=True)
    if p is None:
        return False
    open(os.path.join(HERE, "ic_sched%s.json" % ("_fine" if fine else "")),
         "w").write(json.dumps({k: v for k, v in S.items()}, indent=1, default=str))
    return True


def cmp_mt0():
    a = EH.bt.parse_mt0(COMMITTED_MT0)
    b = EH.bt.parse_mt0(os.path.join(HERE, "ic_%s.cir.mt0" % TAG))
    bad, worst = [], 0.0
    common = sorted(set(a) & set(b))
    for k in common:
        va, vb = a[k], b[k]
        if abs(va) < 1e-9:
            ok = abs(vb - va) <= 1e-12
            rel = abs(vb - va)
        else:
            rel = abs(vb - va) / abs(va)
            ok = rel <= 1e-9
        worst = max(worst, rel)
        if not ok:
            bad.append({"key": k, "committed": va, "mine": vb, "rel": rel})
    return dict(n_committed=len(a), n_mine=len(b), n_common=len(common),
                only_in_committed=sorted(set(a) - set(b)),
                only_in_mine=sorted(set(b) - set(a)),
                n_fail=len(bad), pct_pass=100.0 * (len(common) - len(bad)) / max(1, len(common)),
                worst_rel_or_abs=worst,
                fails=sorted(bad, key=lambda x: -x["rel"])[:25])


# ---------- IC3: rebuild the committed row's derived scalars from MY .mt0 ----
def derive_row():
    """The committed row's settling / value / data-valid scalars, recomputed from
    MY .mt0 and MY .prn with the committed conventions (bt.py's own .measure
    keys: O{k}_{i}B at the boundary, VR{k}B the rail there, VR{k}PK the peak)."""
    d = EH.bt.parse_mt0(os.path.join(HERE, "ic_%s.cir.mt0" % TAG))
    S = json.load(open(os.path.join(HERE, "ic_sched.json")))
    nb, mg = EH.bt.NBANK, EH.bt.MGATE
    EH.set_pattern(EH.PATTERNS["P0"])
    out = {}
    out["rail_at_own_boundary_V"] = {str(k): d["VR%dB%d" % (k, k)] for k in range(1, nb + 1)}
    out["rail_peak_V"] = {str(k): d["VR%dPK" % k] for k in range(1, nb + 1)}
    out["IZ_uA"] = {str(k): d["IZ%d" % k] * 1e6 for k in range(1, nb + 1)}
    out["IZQ_uA"] = {str(k): d["IZQ%d" % k] * 1e6 for k in range(1, nb + 1)}
    # the committed settling convention: |v - target| vs the rail AT the boundary
    pct, worst, where = {}, 1e9, None
    for k in range(1, nb + 1):
        R = d["VR%dB%d" % (k, k)]
        pct[str(k)] = {}
        for i in range(mg):
            v = d["O%d_%dB" % (k, i)]
            hi = EH.bt.out_hi(k, i)
            tgt = R if hi else 0.0
            s = 100.0 * (1.0 - abs(v - tgt) / R)
            pct[str(k)]["o%d" % i] = s
            if s < worst:
                worst, where = s, [k, "o%d" % i]
    out["settling_pct_per_gate"] = pct
    out["worst_gate_pct"] = worst
    out["worst_gate_where"] = where
    out["per_bank_worst_pct"] = {k: min(v.values()) for k, v in pct.items()}
    sep = {}
    for k in range(1, nb + 1):
        his = [d["O%d_%dB" % (k, i)] for i in range(mg) if EH.bt.out_hi(k, i)]
        los = [d["O%d_%dB" % (k, i)] for i in range(mg) if not EH.bt.out_hi(k, i)]
        sep[str(k)] = {"min_HIGH_V": min(his), "max_LOW_V": max(los),
                       "separation_mV": 1000.0 * (min(his) - max(los))}
    out["separation_by_depth"] = sep
    out["separation_min_mV"] = min(v["separation_mV"] for v in sep.values())
    return out


def cmd_score():
    ref = json.load(open(COMMITTED_ROW))
    pre = json.load(open(os.path.join(HERE, "PRE_REGISTERED.json")))
    want = pre["STEP_b_INSTRUMENT_CHECK"]["digit_checked_quantities_stated_NOW"]
    mt0 = cmp_mt0()
    mine = derive_row()
    checks = []

    def chk(name, got, exp, tol=0.0):
        ok = (got == exp) if tol == 0 else (abs(got - exp) <= tol)
        checks.append(dict(quantity=name, committed=exp, mine=got, exact=ok,
                           delta=(None if not isinstance(got, float) else got - exp)))
        return ok

    for k in ("1", "2", "3", "4"):
        chk("rail_at_own_boundary_V[%s]" % k,
            mine["rail_at_own_boundary_V"][k], ref["rail_at_own_boundary_V"][k])
    chk("worst_gate_pct", mine["worst_gate_pct"], ref["worst_gate_pct"])
    chk("worst_gate_where", mine["worst_gate_where"], ref["worst_gate_where"])
    for k in ("1", "2", "3", "4"):
        chk("per_bank_worst_pct[%s]" % k,
            mine["per_bank_worst_pct"][k], ref["per_bank_worst_pct"][k])
    chk("separation_min_mV", mine["separation_min_mV"], ref["separation_min_mV"])
    for k in ("1", "2", "3", "4"):
        chk("IZ_uA[%s]" % k, mine["IZ_uA"][k], ref["IZ_uA"][k])
    nexact = sum(1 for c in checks if c["exact"])

    # the brief's transcription of the same row, pre-declared in PRE_REGISTERED
    brief = {"2": 0.6767239, "3": 0.7312456, "4": 0.7200877}
    transcription = {k: dict(brief=brief[k], committed_file=ref["rail_at_own_boundary_V"][k],
                             mine=mine["rail_at_own_boundary_V"][k],
                             brief_minus_committed_V=brief[k] - ref["rail_at_own_boundary_V"][k])
                     for k in brief}

    out = dict(IC1=json.load(open(os.path.join(HERE, "IC1.json")))
               ["IC1_byte_identical_regeneration"],
               IC2_mt0=mt0,
               IC3_derived_scalar_checks=checks,
               IC3_n_exact=nexact, IC3_n_total=len(checks),
               IC3_all_exact=(nexact == len(checks)),
               IC4_pct_pass=mt0["pct_pass"],
               IC4_pass=(mt0["pct_pass"] >= 99.0),
               BRIEF_TRANSCRIPTION_of_the_same_row=transcription,
               VERDICT=("INSTRUMENT OK" if (mt0["pct_pass"] >= 99.0
                                            and nexact == len(checks))
                        else "INSTRUMENT FAILURE"))
    open(os.path.join(HERE, "INSTRUMENT_CHECK.json"), "w").write(
        json.dumps(out, indent=1))
    print("IC1 byte-identical deck :", out["IC1"])
    print("IC2 mt0 keys            : %d common, %d fail, %.4f%% pass, worst rel %.3e"
          % (mt0["n_common"], mt0["n_fail"], mt0["pct_pass"], mt0["worst_rel_or_abs"]))
    print("IC3 derived scalars     : %d/%d EXACT" % (nexact, len(checks)))
    for c in checks:
        if not c["exact"]:
            print("    MISMATCH", c)
    print("VERDICT:", out["VERDICT"])
    return out["VERDICT"] == "INSTRUMENT OK"


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "deck"
    if a == "deck":
        sys.exit(0 if cmd_deck() else 1)
    if a == "run":
        sys.exit(0 if cmd_run(False) else 1)
    if a == "run_fine":
        sys.exit(0 if cmd_run(True) else 1)
    if a == "score":
        sys.exit(0 if cmd_score() else 1)
    sys.exit(2)
