#!/usr/bin/env python3
"""SKEPTIC charge ledger.

Two INDEPENDENT instruments for every term:
  (1) the deck's 1F integrators, read at phase boundaries via .measure (t0-referenced)
  (2) my own trapezoidal integration of the PRINTED currents

If (1) and (2) disagree, one of the instruments is wrong and the ledger is void.

Sign conventions, DERIVED from the ammeter placements in mkprobe.py:
  VMHSS3 tsup->shs3 : I(VMHSS3)  = current INTO the HS source+bulk
  VMHS3  nhs3->na3  : I(VMHS3)   = current OUT of the HS drain INTO na3
  VMFWS3 sfw3->0    : I(VMFWS3)  = current OUT of the FW source INTO ground
  VMFW3  nfw3->na3  : I(VMFW3)   = current OUT of the FW drain INTO na3
  VMCNA3 ncx3->0    : I(VMCNA3)  = current OUT of na3 through the switch-node cap
  I(LTU3)           = current OUT of na3 into the inductor
  I(VMTU3)          = current through the OUT switch toward rail3
  I(VGxx)           = current out of the gate node into its drive source

Identities (each term independently metered; NOTHING is a residual):
  (i)   na3 KCL   : I(VMHS3) + I(VMFW3) - I(LTU3) - I(VMCNA3)  = 0
  (ii)  HS device : I(VMHSS3) - I(VGTU3) - I(VMHS3)            = 0
  (iii) FW device : I(VMFW3)  + I(VMFWS3) + I(VGFW3)           = 0
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anal import Trace, read_mt0, P

FC = 1e-15

def ledger(prn, mt0, phases, label):
    tr = Trace(prn)
    m = read_mt0(mt0) if os.path.exists(mt0) else {}
    names = ["sup3","hsd","fws","fwd","cna","ind","gtu","gfw","supt",
             "esup","ebnk","ehsd","egdrv","er"]
    # ---- instrument (1): the deck's 1F integrators, t0-referenced to phase 0
    I1 = {}
    for n in names:
        vals = []
        ok = True
        for i in range(len(phases)):
            k = "S%s_P%d" % (n.upper(), i)
            if k not in m: ok = False; break
            vals.append(m[k])
        I1[n] = [v - vals[0] for v in vals] if ok else None

    # ---- instrument (2): my own trapezoid on the printed currents
    expr = {"sup3":"I(VMHSS3)", "hsd":"I(VMHS3)", "fws":"I(VMFWS3)",
            "fwd":"I(VMFW3)", "cna":"I(VMCNA3)", "ind":"I(LTU3)",
            "gtu":"I(VGTU3)", "gfw":"I(VGFW3)", "supt":"I(VTSUP)",
            "out":"I(VMTU3)"}
    t0 = phases[0] * P
    I2 = {}
    for n, e in expr.items():
        if not tr.has(e): continue
        sgn = -1.0 if n == "supt" else 1.0
        I2[n] = [sgn * tr.integ(e, t0, ph * P) for ph in phases]

    # ---- identity residuals, integrated over the whole window ----
    tE = phases[-1] * P
    q = {n: I2[n][-1] for n in I2}
    res_kcl = q["hsd"] + q["fwd"] - q["ind"] - q["cna"]
    res_hs  = q["sup3"] - q["gtu"] - q["hsd"]
    res_fw  = q["fwd"] + q["fws"] + q["gfw"]
    qsup = q["supt"]

    # ---- per-phase table ----
    rows = []
    for i in range(1, len(phases)):
        r = {"phase": "%.3f-%.3f ps" % (phases[i-1], phases[i])}
        for n in ["supt","sup3","hsd","fwd","fws","cna","ind","out","gtu","gfw"]:
            if n in I2:
                r[n] = (I2[n][i] - I2[n][i-1]) / FC
        rows.append(r)

    # ---- cross-check instrument (1) vs (2) ----
    cross = {}
    for n in names:
        if I1.get(n) is None or n not in I2: continue
        a, b = I1[n][-1], I2[n][-1]
        cross[n] = {"integrator_fC": a / FC, "my_trapezoid_fC": b / FC,
                    "abs_diff_fC": (a - b) / FC,
                    "rel": ((a - b) / b) if abs(b) > 1e-18 else None}

    # ---- simultaneous conduction test ----
    # HS conducting: current out of its drain into na3 > thresh
    # FW conducting to ground: current out of its source into ground > thresh
    thr = 100e-6
    both = []
    t = tr.t
    ihs = tr.col("I(VMHS3)"); ifw = tr.col("I(VMFWS3)")
    for i in range(len(t)):
        if ihs[i] > thr and ifw[i] > thr:
            both.append((t[i] / P, ihs[i] * 1e6, ifw[i] * 1e6))
    wins = []
    if both:
        a = both[0][0]; prev = both[0][0]
        for (tt, _, _) in both[1:]:
            if tt - prev > 0.5:
                wins.append((a, prev)); a = tt
            prev = tt
        wins.append((a, prev))
    # charge that went straight to ground while BOTH were on
    q_shoot = 0.0
    for (a, b) in wins:
        q_shoot += tr.integ("I(VMFWS3)", a * P, b * P)

    return dict(
        label=label, prn=os.path.basename(prn), phases_ps=phases,
        totals_fC={n: q[n] / FC for n in q},
        identity_residual_fC={"na3_KCL": res_kcl / FC, "HS_device": res_hs / FC,
                              "FW_device": res_fw / FC},
        identity_residual_pct_of_Qsup={
            "na3_KCL": 100 * res_kcl / qsup if qsup else None,
            "HS_device": 100 * res_hs / qsup if qsup else None,
            "FW_device": 100 * res_fw / qsup if qsup else None},
        Qsup_fC=qsup / FC,
        Qbank_fC=q.get("out", float("nan")) / FC,
        Qdel_over_Qsup=(q.get("out", float("nan")) / qsup) if qsup else None,
        per_phase_fC=rows,
        cross_check=cross,
        both_on_windows_ps=wins,
        both_on_total_ps=sum(b - a for a, b in wins),
        peak_simultaneous_uA=max([max(x[1], x[2]) for x in both]) if both else 0.0,
        shootthrough_charge_to_ground_fC=q_shoot / FC,
    )

if __name__ == "__main__":
    out = {}
    for spec in sys.argv[1:]:
        lbl, prn, ph = spec.split("=", 2)
        phases = [float(x) for x in ph.split(",")]
        out[lbl] = ledger(prn, prn.replace(".prn", ".mt0"), phases, lbl)
    print(json.dumps(out, indent=1, default=str))
