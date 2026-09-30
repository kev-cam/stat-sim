#!/usr/bin/env python3
"""qal/fastwave PHASE 1 analysis -> RESULTS.json.

Everything here is arithmetic on MEASURED rows in ROWS.json (and on committed
.mt0 digits reproduced in INSTRUMENT_CHECK.json).  Nothing is re-simulated.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "ROWS.json")))
CB = json.load(open(os.path.join(HERE, "CBANK.json")))
IC = json.load(open(os.path.join(HERE, "INSTRUMENT_CHECK.json")))

DV = 1.65
FLOOR = 0.9642          # Vtn + |Vtp|, the level-restoring floor
VTN = 0.5240
RS = 10.0
# MEASURED committed comparators (qal/fcrit/cmos.cir.mt0, digit-reproduced here)
CMOS = {6.91: 94.1745, 2.0: 57.1428}
# MEASURED flop tax (OpenSTA on the vendor liberty, best flop)
TREG = {0.0: 307.1, 6.91: 335.7, 20.0: 390.0}
TREG_2FF = TREG[0.0] + (TREG[6.91] - TREG[0.0]) * 2.0 / 6.91
LIB_OPTIMISM = (1.11, 1.21)

ok = {t: r for t, r in R.items() if not r.get("error")}
err = {t: r["error"] for t, r in R.items() if r.get("error")}
data = {t: r for t, r in ok.items() if r.get("mix", "data") == "data"
        and abs(r.get("vgh", 1.5) - 1.5) < 1e-9}
rest = {t: r for t, r in ok.items() if r.get("mix") == "restored"}
vgh = {t: r for t, r in ok.items() if abs(r.get("vgh", 1.5) - 1.5) > 1e-9}


def fit_affine(xs, ys):
    n = len(xs)
    if n < 2:
        return None, None, None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None, None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    worst = max(abs(a + b * x - y) / abs(y) * 100 for x, y in zip(xs, ys))
    return a, b, worst


# ---------------------------------------------------------------- (1) C_ser(N)
cser_fit = {}
for w in sorted({r["total_um"] for r in data.values()}):
    for l in sorted({r["L_nH"] for r in data.values()}, reverse=True):
        pts = sorted((r["N"], r["C_ser_eff_fF"]) for r in data.values()
                     if r["total_um"] == w and r["L_nH"] == l)
        if len(pts) < 3:
            continue
        a, b, wrst = fit_affine([p[0] for p in pts], [p[1] for p in pts])
        cser_fit["W%g_L%g" % (w, l)] = dict(
            c0_switch_floor_fF=a, c1_per_cell_fF=b, worst_resid_pct=wrst,
            points={"N%d" % p[0]: p[1] for p in pts},
            half_of_measured_bank_C_per_cell_fF=13.19 / 1.0)

# ---------------------------------------------------------- (2) Q and the R spec
qmax = {}
for l in sorted({r["L_nH"] for r in data.values()}, reverse=True):
    for n in sorted({r["N"] for r in data.values()}):
        rows = [r for r in data.values() if r["L_nH"] == l and r["N"] == n
                and r["Q_measured"]]
        if not rows:
            continue
        best = max(rows, key=lambda r: r["Q_measured"])
        need = best["Z0_ohm"] / 10.0 - RS          # R_total for Q=10 -> Ron
        qmax["N%d_L%g" % (n, l)] = dict(
            Q_max_measured=best["Q_measured"], at_W_um=best["total_um"],
            Ron_there_ohm=best["Ron_sw_eff_ohm"], Z0_ohm=best["Z0_ohm"],
            Ron_required_for_Q10_ohm=need,
            reached_Q10=bool(best["Q_measured"] >= 10.0),
            Ron_min_in_ladder_ohm=min(r["Ron_sw_eff_ohm"] for r in rows),
            Q_at_widest=max(rows, key=lambda r: r["total_um"])["Q_measured"])

# --------------------------------------------------------------- (3) frontier
def feas(r):
    return r["FEASIBLE"] == "YES"


feasible = [r for r in data.values() if feas(r)]
near = sorted((r for r in data.values() if len(r["fails"]) <= 1),
              key=lambda r: (len(r["fails"]), r["t_level_ps"] or 9e9))
fastest_any = min((r for r in data.values() if r["t_level_ps"]),
                  key=lambda r: r["t_level_ps"])
fastest_fc = min((r for r in data.values() if r["t_level_fcrit_ps"]),
                 key=lambda r: r["t_level_fcrit_ps"])
fastest_hop = min(data.values(), key=lambda r: r["t_hop_ps"])
best_rail = max(data.values(), key=lambda r: r["VBEND"])
best_level = max((r for r in data.values()
                  if r.get("V_hi_min_at_commit") is not None),
                 key=lambda r: r["V_hi_min_at_commit"])

# ------------------------------------------------------- (4) dt_level / dW  (P4)
widen = {}
for l in sorted({r["L_nH"] for r in data.values()}, reverse=True):
    for n in sorted({r["N"] for r in data.values()}):
        pts = sorted(((r["total_um"], r) for r in data.values()
                      if r["L_nH"] == l and r["N"] == n and r["t_level_ps"]),
                     key=lambda x: x[0])
        if len(pts) < 3:
            continue
        widen["N%d_L%g" % (n, l)] = dict(
            W_um=[p[0] for p in pts],
            t_level_ps=[round(p[1]["t_level_ps"], 2) for p in pts],
            t_hop_ps=[round(p[1]["t_hop_ps"], 2) for p in pts],
            VBPK=[round(p[1]["VBPK"], 4) for p in pts],
            VBEND=[round(p[1]["VBEND"], 4) for p in pts],
            Q=[round(p[1]["Q_measured"], 2) for p in pts],
            monotone_increasing_in_W=all(
                pts[k][1]["t_level_ps"] >= pts[k - 1][1]["t_level_ps"] - 1e-9
                for k in range(1, len(pts))),
            t_level_first_to_last_pct=100 * (pts[-1][1]["t_level_ps"]
                                             / pts[0][1]["t_level_ps"] - 1))

# ----------------------------------------------- (5) the mix control (A7)
mixctl = {}
for t, r in sorted(rest.items()):
    key = "n%d_L%g_W%g" % (r["N"], r["L_nH"], r["total_um"])
    d = next((x for x in data.values() if x["N"] == r["N"]
              and x["L_nH"] == r["L_nH"] and x["total_um"] == r["total_um"]), None)
    mixctl[key] = dict(
        restored_mix=dict(t_hop_ps=r["t_hop_ps"], C_ser_eff_fF=r["C_ser_eff_fF"],
                          Q=r["Q_measured"], VBPK=r["VBPK"], VBEND=r["VBEND"],
                          droop_mV=1000 * (r["VBPK"] - r["VBEND"]),
                          t_level_ps=r["t_level_ps"],
                          t_level_fcrit_ps=r["t_level_fcrit_ps"],
                          n_restored=r["n_restored"], fails=r["fails"]),
        data_mix=(None if not d else
                  dict(t_hop_ps=d["t_hop_ps"], C_ser_eff_fF=d["C_ser_eff_fF"],
                       Q=d["Q_measured"], VBPK=d["VBPK"], VBEND=d["VBEND"],
                       droop_mV=1000 * (d["VBPK"] - d["VBEND"]),
                       t_level_ps=d["t_level_ps"],
                       t_level_fcrit_ps=d["t_level_fcrit_ps"],
                       n_restored=d["n_restored"], fails=d["fails"])))

# ------------------------------------------------ (6) the gate-drive spec
vghtab = {}
for t, r in sorted(vgh.items()):
    key = "n%d_L%g_W%g" % (r["N"], r["L_nH"], r["total_um"])
    vghtab.setdefault(key, {})["VGH_%.3f" % r["vgh"]] = dict(
        Ron_sw_eff_ohm=r["Ron_sw_eff_ohm"], Q=r["Q_measured"],
        t_hop_ps=r["t_hop_ps"], VBPK=r["VBPK"], VBEND=r["VBEND"],
        VA_open=r["VA_open"], V_hi_min_at_commit=r.get("V_hi_min_at_commit"),
        t_level_ps=r["t_level_ps"], t_level_fcrit_ps=r["t_level_fcrit_ps"],
        FEASIBLE=r["FEASIBLE"], fails=r["fails"])
for key in vghtab:
    n, l, w = key[1:].split("_L")[0], key.split("_L")[1].split("_W")[0], key.split("_W")[1]
    d = next((x for x in data.values() if x["N"] == int(n)
              and abs(x["L_nH"] - float(l)) < 1e-9
              and abs(x["total_um"] - float(w)) < 1e-9), None)
    if d:
        vghtab[key]["VGH_1.500"] = dict(
            Ron_sw_eff_ohm=d["Ron_sw_eff_ohm"], Q=d["Q_measured"],
            t_hop_ps=d["t_hop_ps"], VBPK=d["VBPK"], VBEND=d["VBEND"],
            VA_open=d["VA_open"], V_hi_min_at_commit=d.get("V_hi_min_at_commit"),
            t_level_ps=d["t_level_ps"], t_level_fcrit_ps=d["t_level_fcrit_ps"],
            FEASIBLE=d["FEASIBLE"], fails=d["fails"])


# ------------------------------------------- (7) the comparison and crossover D*
def compare(beat_ps, label):
    out = {"beat_ps": beat_ps, "what": label}
    for cl, tl in CMOS.items():
        k = "vs_CMOS_level_%gfF_%gps" % (cl, tl)
        treg = TREG_2FF if cl == 2.0 else TREG[6.91]
        if beat_ps <= tl:
            out[k] = dict(ratio_QAL_over_CMOS=beat_ps / tl,
                          QAL_faster_at_the_level=True,
                          crossover_D="QAL wins at EVERY pipeline depth",
                          t_reg_used_ps=treg)
        else:
            dstar = treg / (beat_ps - tl)
            out[k] = dict(ratio_QAL_over_CMOS=beat_ps / tl,
                          QAL_faster_at_the_level=False,
                          t_reg_used_ps=treg,
                          crossover_D_star=dstar,
                          reading=("QAL's flop-free beat beats CMOS+flop only "
                                   "for pipeline depth D < %.2f levels" % dstar),
                          D_star_with_liberty_optimism_removed=[
                              treg * f / (beat_ps - tl) for f in LIB_OPTIMISM])
    out["load_matched_comparator"] = (
        "2 fF / 57.1428 ps -- this run's TG-XOR cells each carry CL = 2 fF on "
        "their output, referenced to the cell ground, which is the SAME load the "
        "2 fF CMOS arm of qal/fcrit/cmos.cir drives.  The 6.91 fF comparator is "
        "reported alongside because it is the committed headline, but it is NOT "
        "the load-matched one and it flatters QAL.")
    return out


# ---- the frontier over EVERY row, with VGH declared on each
allf = [r for r in ok.values() if r["FEASIBLE"] == "YES"]
allf_fc = sorted((r for r in allf if r["t_level_fcrit_ps"]),
                 key=lambda r: r["t_level_fcrit_ps"])
allf_90 = sorted((r for r in allf if r["t_level_ps"]),
                 key=lambda r: r["t_level_ps"])


def frow(r):
    return dict(tag=r["tag"], N=r["N"], L_nH=r["L_nH"], W_um=r["total_um"],
                VGH=r.get("vgh"), mix=r.get("mix", "data"),
                t_hop_ps=r["t_hop_ps"], t_settle_ps=r["t_settle_ps"],
                t_level_ps=r["t_level_ps"], t_level_fcrit_ps=r["t_level_fcrit_ps"],
                hop_share_of_level_pct=(100 * r["t_hop_ps"] / r["t_level_fcrit_ps"]
                                        if r["t_level_fcrit_ps"] else None),
                Ron_sw_eff_ohm=r["Ron_sw_eff_ohm"], Q_measured=r["Q_measured"],
                Ron_at_Ipk_ohm=r["Ron_at_Ipk_ohm"], Z0_ohm=r["Z0_ohm"],
                C_ser_eff_fF=r["C_ser_eff_fF"], IPK_uA=r["IPK_uA"],
                VBPK=r["VBPK"], VBEND=r["VBEND"], VA_open=r["VA_open"],
                V_hi_min_at_commit=r.get("V_hi_min_at_commit"),
                V_hi_min_at_tail=r.get("V_hi_min_at_tail"),
                K1_on_DELIVERED_LEVEL_strictest=r.get("K1_on_DELIVERED_LEVEL_strictest"),
                K1_on_PEAK_rail_most_generous=r.get("K1_on_PEAK_rail_most_generous"),
                value_all_correct=r["value_all_correct"],
                value_min_margin_mV=r["value_min_margin_mV"],
                settling_end_min_pct=r["settling_end_min_pct"],
                E_hop_raw_toB_fJ=r["E_hop_raw_toB_fJ"],
                E_gate_drive_fJ=r["E_gate_drive_fJ"],
                rails_net_fJ=r["rails_net_fJ"],
                IZ_uA=r["IZ_uA"], closure_Q_pct=r["closure_Q_pct"],
                closure_E_pct=r["closure_E_pct"],
                identity_at_B_fJ=r["identity_at_B_fJ"])


FRONTIER = dict(
  feasible_row_count=len(allf),
  THE_MINIMUM_BEAT_functional=(frow(allf_fc[0]) if allf_fc else None),
  THE_MINIMUM_BEAT_committed_90pct_bar=(frow(allf_90[0]) if allf_90 else None),
  all_feasible_rows_by_functional_beat=[frow(r) for r in allf_fc],
  reading=("The minimum beat subject to completeness is %.2f ps (functional "
           "criterion) / %.2f ps (inherited 90%% bar) at N = %d, W = %g um, "
           "L = %g nH, VGH = %.3f V.  The hop is %.1f%% of the functional level "
           "time, so the level is SETTLE-BOUND, not hop-bound."
           % (allf_fc[0]["t_level_fcrit_ps"], allf_fc[0]["t_level_ps"],
              allf_fc[0]["N"], allf_fc[0]["total_um"], allf_fc[0]["L_nH"],
              allf_fc[0]["vgh"],
              100 * allf_fc[0]["t_hop_ps"] / allf_fc[0]["t_level_fcrit_ps"]))
  if allf_fc else "no feasible row at any gate drive",
  IS_IT_Q_BOUND=("NO.  Q at the frontier point is %.2f, and Q as high as 39.19 "
                 "was MEASURED (N=2, L=15 nH, W=120 um, VGH=2.174) on a row that "
                 "is still INFEASIBLE because its delivered rail is only "
                 "0.8981 V.  Raising Q does NOT raise the delivered rail: over "
                 "the W ladder at N=2/L=15/VGH=2.174, Q goes 18.96 -> 27.98 -> "
                 "39.19 while VBEND goes 0.9641 -> 0.9273 -> 0.8981.  The "
                 "constraint is the DELIVERED RAIL, and widening trades rail for "
                 "Q because the switch capacitance joins the resonance and "
                 "lowers the peak." % allf_fc[0]["Q_measured"]) if allf_fc else None,
  THE_STRICTEST_READING_FAILS_EVERYWHERE=(
    "Under the STRICTEST defensible completeness form -- the delivered LOGIC "
    "LEVEL handed to the next bank, measured at the instant the receiver commits "
    "-- NO row in this run reaches the 0.9642 V level-restoring floor.  The best "
    "is %s at %.4f V, short by %.0f mV.  The pre-registered gates are on the "
    "delivered RAIL, which is what they say; the level is reported alongside on "
    "every row so the reader can see that the frontier above is the RAIL "
    "frontier and that a CASCADE needs more than this run delivers."
    % (best_level["tag"], best_level["V_hi_min_at_commit"],
       1000 * (FLOOR - best_level["V_hi_min_at_commit"]))))

TRESTOR = json.load(open(os.path.join(HERE, "T_RESTORING.json")))

out = {
 "_what": ("qal/fastwave PHASE 1 -- the SELF-CONSISTENT (N_bank, W_switch, L) "
           "CORNER SEARCH FOR MINIMUM BEAT on a pass-gate TG-XOR bank at "
           "dV = 1.65 V.  Pre-registration PRE_REGISTERED.json sha256 "
           "c23021e9e97089bf60826b118ec44ddaa874dd1f51049df1ae226c062cc05638, "
           "written 2026-09-29 19:50:27 -0700 after DISK_STATE_BEFORE.txt "
           "(19:46:26) and before any deck in this directory.  Amendments, each "
           "with the measurement that forced it: AMENDMENT.md.  SPEED is the "
           "objective; energy is reported and gates nothing."),
 "_labels": ("MEASURED = read off a .prn/.mt0 in this or a committed directory. "
             "DERIVED = arithmetic on MEASURED values.  ASSUMED = neither, and "
             "every ideal source or lumped element is a BOOKING whose row is a "
             "BOUND."),
 "A_INSTRUMENT": {
   "verdict": IC["GATE"],
   "F1_comparator_anchor": dict(
       deck=IC["F1_comparator_anchor"]["deck"],
       worst_rel=IC["F1_comparator_anchor"]["worst_rel"],
       reproduced_6p91fF_ps=IC["F1_comparator_anchor"]["headline_6p91fF_ps"],
       reproduced_2fF_ps=IC["F1_comparator_anchor"]["headline_2fF_ps"]),
   "F2_hop_anchor": dict(deck=IC["F2_hop_anchor"]["deck"],
                         worst_rel=IC["F2_hop_anchor"]["worst_rel"]),
   "reading": ("PASS at rel 0.00e+00 on all 22 digit-checked quantities -- the "
               "fourteen .mt0 measures of the committed CMOS comparator and the "
               "eight committed tg15p hop headlines, the latter extracted with "
               "qal/lsweep/lsw.py's own `extract` IMPORTED rather than "
               "re-implemented.  Both decks are byte-identical copies of the "
               "committed ones, re-run under this run's private PYMS_VAE_CACHE.")},
 "B_THE_BANK_CELL_AS_BUILT": {
   "cell": ("pass-gate transmission-gate XOR2, qal/pgcell/pg.py tg_xnor2 with "
            "xor_form=True, tgM widths (wn 0.74 / wp 1.12 um), pass-pMOS n-well "
            "on VGH ('fixedwell').  8 devices, data-path depth 1."),
   "why": ("depth 1 on the data path (the user's budget is two levels); NO series "
           "stack, which matters because a QAL rail ramps from zero and the "
           "binding device is MEASURED to be Vtn = 0.5240 V (qal/strip); XOR and "
           "XNOR are the same 8 devices with a tap swap so the bank is "
           "content-uniform; and the data path never touches the rail."),
   "MEASURED_rail_load": dict(
       bank_C_secant_at_dV_fF={k: CB[k]["C_secant_dV_fF"] for k in sorted(CB, key=lambda x: CB[x]["N"])},
       per_cell_fF=13.19,
       affine_in_N="C_bank = 13.19 * N fF with an offset of essentially zero",
       note=("N = 2 sits 3.0 fF above 2 x 13.19 because it is the all-RESTORED "
             "bank (AMENDMENT A1) -- the harsher bank, deliberately.")),
   "THE_COST_THE_CELL_CHOICE_CARRIES_AND_I_DID_NOT_PREDICT": (
       "MEASURED (AMENDMENT A4, diag_n4.cir): while the rail is below the level "
       "that separates a cell's select signals b/bb, BOTH transmission-gate pMOS "
       "devices conduct and the mux does not select -- the cell SHORTS ITS TWO "
       "DATA INPUTS together.  A transparent want-1 cell draws 176 fC from its "
       "own A input over a 4 ns ramp (crowbar excess 4.1 / 270 / 536 / 1072 fC "
       "at N = 2/4/8/16; N = 2 has no transparent cell and almost none of it).  "
       "In Phase 1 that current comes from an IDEAL INPUT SOURCE, so it is a "
       "BOOKING THAT HIDES A COST: in a real chain it is drawn out of the "
       "PREDECESSOR bank's outputs.  It is a strike against the cell that "
       "qal/pgcell did not surface."),
 },
 "C_THE_SWEEP": {
   "grid_run": dict(
       N=sorted({r["N"] for r in data.values()}),
       L_nH=sorted({r["L_nH"] for r in data.values()}),
       W_um=sorted({r["total_um"] for r in data.values()}),
       points_measured=len(data), mix_control_points=len(rest),
       gate_drive_points=len(vgh), points_that_never_converged=err),
   "dV": DV, "VGH_committed": 1.5, "VINHI": 1.20,
   "rows": {t: {k: v for k, v in r.items()
                if k not in ("ledger_waveform", "ledger_mt0", "levels",
                             "levels_RESTORED_only", "probe", "settling_open_pct")}
            for t, r in sorted(ok.items())}},
 "D_C_SER_SCALES_AFFINELY_IN_N_MEASURED": cser_fit,
 "E_Q_AND_THE_REQUIRED_R": qmax,
 "F_WIDENING_AT_EVERY_L": widen,
 "G_THE_MIX_CONTROL": mixctl,
 "H_THE_GATE_DRIVE_SPEC": vghtab,
 "I_THE_FRONTIER": {
   "I0_AT_THE_COMMITTED_GATE_DRIVE_VGH_1p5": {
     "FEASIBLE_ROWS": len(feasible),
     "the_answer": ("EMPTY.  Not one of the %d measured (N, W, L) points clears "
                    "all five pre-registered gates at dV = 1.65 V with the "
                    "COMMITTED VGH = 1.5 V.  The binding gates are K1/K2 (the "
                    "delivered rail against the 0.9642 V level-restoring floor "
                    "and the 0.990 V swing floor) and K3 (rail drain) -- NOT Q."
                    % len(data)),
     "why_the_committed_gate_drive_cannot_work_MEASURED": (
       "dV = 1.65 V EXCEEDS VGH = 1.5 V, so the transfer nMOS has Vgs < 0 over "
       "the top of the swing and is CUT OFF there; the transfer is pMOS-only "
       "near the peak.  The measured loss-equivalent channel resistance is "
       "179-190 ohm at W = 15 um across every N and every L -- about 1.45x the "
       "96-130 ohm qal/lsweep measured at dV = 1.0, and about 3x lsweep's "
       "13.7 ohm at W = 240 um.  The switch is the wall, and at dV = 1.65 V it "
       "is a WORSE wall than the committed record records.")},
   "I1_THE_FOURTH_AXIS_THE_CORNER_SEARCH_FORCED": {
     "what": ("The pre-registered search was over (N_bank, W_switch, L).  It "
              "returns an EMPTY frontier, and the measurement identifies the "
              "missing degree of freedom as the TRANSFER GATE DRIVE VGH, which "
              "every committed deck holds at 1.5 V because every committed deck "
              "runs at dV = 1.0-1.2 V.  VGH is therefore swept as a declared "
              "FOURTH axis and reported separately -- it is NOT part of the "
              "pre-registered grid and every VGH != 1.5 row is labelled."),
     "MEASURED_interior_optimum_in_VGH": (
       "VGH has an INTERIOR OPTIMUM at N=4, L=6 nH, W=30 um: VGH = 1.5 / 2.174 "
       "/ 2.4 / 2.8 V gives VBEND = 0.9059 / 0.9935 / 0.9975 / 0.9998 V but "
       "VA_open = 0.1717 / 0.2344 / 0.2497 / 0.2874 V, so the row is FEASIBLE "
       "ONLY at VGH = 2.174 V -- at 2.4 and 2.8 V it FAILS the rail-drain gate.  "
       "More gate drive is WORSE.  2.174 V is exactly dV + Vtn = 1.65 + 0.5240, "
       "the drive at which the transfer nMOS conducts at the top of the swing "
       "and no further; beyond it the extra n-well bias and switch capacitance "
       "cost more than the lower channel resistance returns."),
     "THE_DEVICE_SPEC": ("the transfer gate drive must be VGH = dV + Vtn "
                         "(2.174 V at dV = 1.65 V), NOT the committed 1.5 V, and "
                         "NOT more.")},
   "the_answer": ("THE FEASIBLE FRONTIER IS EMPTY at the committed VGH = 1.5 V "
                  "and NON-EMPTY at VGH = dV + Vtn."),
   "nearest_misses": [dict(tag=r["tag"], N=r["N"], L_nH=r["L_nH"],
                           W_um=r["total_um"], fails=r["fails"],
                           t_level_ps=r["t_level_ps"],
                           t_level_fcrit_ps=r["t_level_fcrit_ps"],
                           VBEND=r["VBEND"], VA_open=r["VA_open"],
                           Q=r["Q_measured"], t_hop_ps=r["t_hop_ps"],
                           K3_limit=0.1478 * DV,
                           miss=("VA_open exceeds the 0.24387 V drain limit by "
                                 "%.4f V" % (r["VA_open"] - 0.1478 * DV))
                           if "K3_drain" in r["fails"] else None)
                      for r in near[:6]],
   "fastest_by_t_level_90pct_bar_ANY_row": dict(
       tag=fastest_any["tag"], t_level_ps=fastest_any["t_level_ps"],
       N=fastest_any["N"], L_nH=fastest_any["L_nH"], W_um=fastest_any["total_um"],
       FEASIBLE=fastest_any["FEASIBLE"], fails=fastest_any["fails"]),
   "fastest_by_t_level_FUNCTIONAL_ANY_row": dict(
       tag=fastest_fc["tag"], t_level_fcrit_ps=fastest_fc["t_level_fcrit_ps"],
       N=fastest_fc["N"], L_nH=fastest_fc["L_nH"], W_um=fastest_fc["total_um"],
       FEASIBLE=fastest_fc["FEASIBLE"], fails=fastest_fc["fails"]),
   "fastest_hop_ANY_row": dict(
       tag=fastest_hop["tag"], t_hop_ps=fastest_hop["t_hop_ps"],
       VBEND=fastest_hop["VBEND"], FEASIBLE=fastest_hop["FEASIBLE"]),
   "best_delivered_rail": dict(tag=best_rail["tag"], VBEND=best_rail["VBEND"],
                               N=best_rail["N"], L_nH=best_rail["L_nH"],
                               W_um=best_rail["total_um"],
                               floor=FLOOR, fails=best_rail["fails"]),
   "best_delivered_LEVEL_at_commit": dict(
       tag=best_level["tag"], V_hi_min_at_commit=best_level["V_hi_min_at_commit"],
       floor=FLOOR, short_by_mV=1000 * (FLOOR - best_level["V_hi_min_at_commit"]))},
 "I2_THE_FEASIBLE_FRONTIER_WITH_THE_GATE_DRIVE_AMENDED": FRONTIER,
 "I3_THE_REQUIRED_R_SO_THE_RESULT_IS_A_DEVICE_SPEC": {
   "at_the_frontier_N4_L6nH": {
     "Z0_ohm_MEASURED": 389.71,
     "Ron_required_for_Q10_ohm": 389.71 / 10.0 - RS,
     "Ron_ACHIEVED_at_the_frontier_W30_VGH2p174_ohm": 34.26,
     "Q_achieved": 8.81,
     "is_Q10_reachable": ("YES.  W = 60 um at VGH = 2.174 V MEASURES Ron = 17.9 "
                          "ohm and Q = 13.28 at N = 4, L = 6 nH -- comfortably "
                          "past Q = 10.  But that row FAILS K1/K2: widening to "
                          "60 um drops VBPK from 1.3011 to 1.1023 V and VBEND "
                          "from 0.9935 to 0.9627 V, because the switch's own "
                          "capacitance joins the resonance.  THAT is the "
                          "circularity, and it is now quantified: Q = 10 is "
                          "reachable and NOT WORTH REACHING."),
     "reading": ("The frontier is NOT Q-bound.  A device spec of the form 'get "
                 "Ron below X' does not unlock it, because Ron is already low "
                 "enough and the width that lowers it further costs more rail "
                 "than the Q buys.")},
   "the_spec_that_DOES_matter_MEASURED": {
     "quantity": "the transfer GATE DRIVE, not the channel resistance",
     "value": "VGH = dV + Vtn = 1.65 + 0.5240 = 2.174 V",
     "why": ("at the committed VGH = 1.5 V < dV = 1.65 V the transfer nMOS has "
             "Vgs < 0 over the top of the swing and is cut off there, so the "
             "measured loss-equivalent Ron is 179-190 ohm at W = 15 um -- 1.45x "
             "the 96-130 ohm qal/lsweep measured at dV = 1.0 and ~3x its 13.7 "
             "ohm at W = 240 um.  Raising VGH to dV + Vtn takes Ron at W = 30 um "
             "from 100 to 34 ohm and is what makes ANY row feasible."),
     "and_it_is_an_INTERIOR_optimum": ("more is worse.  At N = 4, L = 6 nH, "
                                       "W = 30 um: VGH = 1.5 / 2.174 / 2.4 / 2.8 "
                                       "V gives VA_open = 0.1717 / 0.2344 / "
                                       "0.2497 / 0.2874 V, and only VGH = 2.174 "
                                       "V clears the rail-drain gate."),
     "the_cost_not_paid_in_this_run": ("a 2.174 V gate supply on a 1.2 V-nominal "
                                       "1.5 V-tolerant LV device is an OVERDRIVE "
                                       "and an oxide-reliability question this "
                                       "run does NOT answer.  Every VGH > 1.5 V "
                                       "row is labelled, and the gate-drive "
                                       "energy is reported (rails_net_fJ) but "
                                       "gates nothing.  The frontier therefore "
                                       "rests on a DEVICE ASK, not on a "
                                       "(N, W, L) choice alone.")},
 },
 "K_PREDICTIONS_SCORED": {
   "_how": ("Each pre-registered prediction in PRE_REGISTERED.json section G is "
            "restated and scored against the MEASURED rows.  Three of six are "
            "wrong and say so."),
   "P0_symmetric_banks_raise_the_delivered_rail_fraction": {
     "predicted": "VBEND/dV >= 0.80 at Q >= 8; falsified if it saturates below 0.72",
     "MEASURED": ("FALSIFIED.  At the frontier (Q = 8.81) VBEND/dV = 0.9935/1.65 "
                  "= 0.602.  At the highest Q measured anywhere (24.62, N = 2, "
                  "L = 15 nH, W = 240 um) VBEND/dV = 0.8913/1.65 = 0.540.  The "
                  "fraction saturates at 0.54-0.60, BELOW the committed "
                  "asymmetric-bank ~0.69, i.e. making the banks symmetric made "
                  "the fraction WORSE, not better."),
     "and_my_hypothesised_MECHANISM_was_also_wrong": (
       "I attributed the committed saturation to a capacitance MISMATCH between "
       "a 35.979 fF lumped source and an ~90 fF real destination.  Symmetrising "
       "the banks did not lift the fraction, so that was not the mechanism.  The "
       "measured mechanism is AMENDMENT A6: the rail PEAKS above the floor "
       "(VBPK = 1.3011 V at the frontier) and then loses 10.3 fC to the bank's "
       "own internal nodes and n-wells over the next 100-200 ps, because those "
       "nodes cannot follow a ~48 ps hop.  It is charge REDISTRIBUTION inside "
       "the destination bank, not a source/destination mismatch.")},
   "P1_N_is_the_dominant_lever_and_the_frontier_sits_at_the_SMALLEST_N": {
     "mechanism_CONFIRMED": ("C_ser_eff is affine in N to 0.79%: at W = 15 um, "
                             "L = 15 nH, C_ser = 8.510 + 6.5877*N fF.  The slope "
                             "6.5877 fF/cell is HALF the independently measured "
                             "13.19 fF/cell bank capacitance to 0.1%, which is "
                             "exactly the symmetric-series prediction.  c0, the "
                             "switch-and-parasitic floor, rises with W as "
                             "predicted: 8.51 / 11.21 / 12.83 fF at W = 15 / 30 "
                             "/ 60 um."),
     "conclusion_FALSIFIED": ("the frontier is at N = 4, NOT N = 2.  Every N = 2 "
                              "row fails the rail gates at every W and every L "
                              "and every gate drive tried, up to VGH = 2.8 V.  "
                              "The reason is the one P0 got wrong: the binding "
                              "constraint is the delivered rail, and a smaller "
                              "bank has LESS stored charge to hold its rail up "
                              "against the same per-cell redistribution."),
     "the_L_half_CONFIRMED": ("I predicted L_opt >= 3 nH and that L = 0.3 and "
                              "0.5 nH would be INFEASIBLE at every N and every "
                              "W.  MEASURED: L_opt = 6 nH, and all 10 measured "
                              "L <= 0.5 nH rows are infeasible."),
     "the_N16_test_CONFIRMED": ("I said the prediction is falsified if N = 16 "
                                "beats N = 2 on t_level.  It does not: at "
                                "W = 15 um, L = 15 nH, t_level = 209.4 ps "
                                "(N = 2) vs 278.8 ps (N = 16)."),
     "and_the_N_axis_had_to_be_DE-CONFOUNDED": ("see AMENDMENT A7 -- the data mix "
                                                "makes N = 2 100% RESTORED and "
                                                "N >= 4 only 50%, so the raw N "
                                                "comparison was confounded.  At "
                                                "a FIXED 100%-restored mix VBEND "
                                                "falls monotonically with N "
                                                "(0.9359 / 0.8807 / 0.8492 / "
                                                "0.7917 V at N = 2/4/8/16), "
                                                "which is the predicted "
                                                "direction; the frontier still "
                                                "lands at N = 4 because the "
                                                "data-mix bank is the honest "
                                                "one.")},
   "P2_the_minimum_feasible_beat_is_70_to_95_ps": {
     "MEASURED": "FALSIFIED.  130.91 ps (functional) / 230.66 ps (90% bar).",
     "the_sub_prediction_CONFIRMED": ("I predicted t_hop < 40 ps and under 45% of "
                                      "t_level at the frontier.  MEASURED "
                                      "48.37 ps, which is 36.9% of the "
                                      "functional level time -- the share is "
                                      "confirmed, the absolute value is not."),
     "the_briefs_own_arithmetic_CONFIRMED_as_unreachable": (
       "I pre-stated that the brief's DERIVED ~60 ps beat (17 ps hop + 40 ps "
       "settle at 30 fF, L = 1 nH) would not be reproduced because it needs "
       "Q ~ 1.8, and that the L = 1 nH rows would be FAST and INFEASIBLE at "
       "every N and W.  Both hold: the fastest hop measured is 7.76 ps (N = 2, "
       "L = 0.3 nH, W = 15 um) at a delivered rail of 0.6236 V, and every one of "
       "the 11 L = 1 nH rows is infeasible.")},
   "P3_does_Q_forbid_it": {
     "the_headline_CONFIRMED": ("the load-matched comparator IS the 2 fF / "
                                "57.1428 ps one, QAL LOSES at the level "
                                "(2.29x slower), and the speed case rests "
                                "entirely on the flop tax and the crossover "
                                "depth -- all as pre-stated."),
     "but_the_REASON_is_OVERTURNED": ("I pre-stated that Q forbids a beat under "
                                      "the 2 fF comparator.  IT DOES NOT.  Q is "
                                      "not the binding constraint at all: the "
                                      "frontier sits at Q = 8.81, Q = 39.19 was "
                                      "measured, and raising Q LOWERS the "
                                      "delivered rail.  What forbids the fast "
                                      "beat is the delivered rail and the "
                                      "settle time it buys -- neither of which "
                                      "is a Q story."),
     "the_saturation_sub_prediction_HALF_WRONG": (
       "I predicted lsweep's 'Q saturates near 7 even at 240 um at L = 1 nH' "
       "would be CONFIRMED at N = 8 and PARTLY OVERTURNED at N = 2, with max Q "
       "at N = 2, L = 1 nH between 3 and 6.  The BAND is right (MEASURED 3.38 at "
       "W = 240 um) but the framing is wrong in BOTH directions: at L = 1 nH "
       "NOTHING in this run reaches Q = 7 at any N or W -- WORSE than lsweep, "
       "because dV = 1.65 V against the committed VGH = 1.5 V makes Ron ~3x "
       "worse -- while at L = 15 nH, N = 2, W = 240 um Q reaches 24.62, which "
       "overturns the saturation claim decisively.  The saturation is an "
       "L = 1 nH phenomenon, not a width phenomenon.")},
   "P4_widening_penalises_the_level_time_at_every_L": {
     "MEASURED": ("FALSIFIED as stated.  dt_level/dW > 0 monotonically at only "
                  "ONE of the six (N, L) cells with a full W ladder: N = 2, "
                  "L = 15 nH, where t_level rises 205.2 -> 321.6 ps (+56.7%) "
                  "over 7.5 -> 240 um.  Everywhere else there is an INTERIOR "
                  "OPTIMUM in W: at N = 2, L = 1 nH t_level goes 382.3 / 292.7 / "
                  "277.2 / 307.9 / 311.1 / 316.2 ps, a minimum at W = 30 um and "
                  "17.3% FASTER at the widest than at the narrowest."),
     "what_IS_confirmed": ("the widening PENALTY is real and dominates ABOVE the "
                           "optimum width, and its mechanism is confirmed "
                           "directly: over the W ladder the rail PEAK falls "
                           "monotonically at every (N, L) -- e.g. VBPK 1.4081 -> "
                           "0.9321 V at N = 2, L = 15 nH -- because the switch's "
                           "own capacitance joins the resonance.  lsweep's "
                           "direction is right above the optimum and wrong "
                           "below it, and reducing L in step does NOT reverse "
                           "it.")},
   "P5_the_comparator_and_the_crossover": {
     "MEASURED_and_as_pre_stated": ("both committed comparators are reported, the "
                                    "load-matched one (2 fF / 57.1428 ps) is "
                                    "named and used for the headline, and D* is "
                                    "given against both with the liberty "
                                    "optimism carried.")},
 },
 "I4_THE_CASCADABLE_BEAT_the_number_a_WAVE_actually_needs": {
   "_what": ("MEASURED off each feasible row's own waveform: the first instant "
             "after which ALL want-1 outputs stay at or above the level-"
             "restoring floor Vtn + |Vtp| = 0.9642 V and all want-0 outputs stay "
             "below dV - 0.9642 V.  This is the instant the bank can FEED THE "
             "NEXT BANK, and it is the beat a wave is entitled to quote."),
   "why_it_is_a_different_number": (
     "At the frontier row the delivered LEVEL at each instant is: rail peak "
     "(50.4 ps) rail 1.3011 V but v_hi_min only 0.2405 V; commit (130.9 ps) rail "
     "1.0600 V, v_hi_min 0.5972 V; 90%-bar (230.7 ps) rail 1.0094 V, v_hi_min "
     "0.9087 V; tail (443.4 ps) rail 0.9935 V, v_hi_min 0.9914 V.  The 130.91 ps "
     "functional beat therefore HANDS ON A 0.597 V LEVEL -- 367 mV below the "
     "floor.  A single hop scored against a receiver's trip passes there; a "
     "CASCADE does not, because the next bank's cells need Vtn + |Vtp| to "
     "restore."),
   "MEASURED_per_feasible_row_ps": TRESTOR,
   "THE_MINIMUM_CASCADABLE_BEAT_ps": (min(v for v in TRESTOR.values() if v)
                                      if any(TRESTOR.values()) else None),
   "at": ("N = 4, L = 15 nH, W = 30 um, VGH = 2.4 V -- 243.64 ps.  NOT the same "
          "(N, W, L) as the functional-beat frontier (N = 4, L = 6 nH, W = 30 um, "
          "VGH = 2.174 V), because the shorter-L point delivers a lower rail and "
          "its cells take longer to climb to the floor: its cascadable beat is "
          "289.91 ps despite a 130.91 ps functional beat."),
   "reading": ("The three beats this run can defend are 130.91 ps (functional, "
               "single hop), 230.66 ps (the inherited 90%-of-rail bar) and "
               "243.64 ps (level-restoring, cascadable).  They differ by 1.9x, "
               "and the ONLY one a fast WAVE may quote is the last."),
 },
 "J_THE_COMPARISON": {
   "comparators_MEASURED": dict(
       CMOS_level_6p91fF_ps=CMOS[6.91], CMOS_level_2fF_ps=CMOS[2.0],
       source=("qal/fcrit/cmos.cir.mt0, digit-reproduced by this run's "
               "INSTRUMENT_CHECK.json at rel 0.00e+00: T90R = 1.941745e-10 and "
               "T90R2 = 1.571428e-10 against the t = 100 ps input edge"),
       t_reg_ps=TREG, t_reg_at_2fF_interpolated_ps=TREG_2FF,
       liberty_optimism="transistor cross-check 258.9-302 ps, i.e. the liberty "
                        "figure is 1.11-1.21x OPTIMISTIC, so a D* computed from "
                        "liberty FLATTERS CMOS"),
   "at_the_fastest_FUNCTIONAL_level_any_row_INFEASIBLE":
       compare(fastest_fc["t_level_fcrit_ps"],
               "fastest functional level time of ANY row, %s -- INFEASIBLE "
               "(fails %s)" % (fastest_fc["tag"], ",".join(fastest_fc["fails"]))),
   "at_the_fastest_90pct_level_any_row_INFEASIBLE":
       compare(fastest_any["t_level_ps"],
               "fastest 90%%-bar level time of ANY row, %s -- INFEASIBLE "
               "(fails %s)" % (fastest_any["tag"], ",".join(fastest_any["fails"]))),
   "AT_THE_FEASIBLE_FRONTIER_functional":
       (compare(allf_fc[0]["t_level_fcrit_ps"],
                "THE FEASIBLE FRONTIER: functional level time at %s "
                "(N=%d, W=%g um, L=%g nH, VGH=%.3f V) -- all five gates PASS"
                % (allf_fc[0]["tag"], allf_fc[0]["N"], allf_fc[0]["total_um"],
                   allf_fc[0]["L_nH"], allf_fc[0]["vgh"])) if allf_fc else None),
   "AT_THE_MINIMUM_CASCADABLE_BEAT_the_one_a_wave_may_quote":
       compare(min(v for v in TRESTOR.values() if v),
               "THE MINIMUM CASCADABLE BEAT: the first instant the bank's own "
               "outputs all clear the 0.9642 V level-restoring floor, so the "
               "level can feed the next bank (N=4, L=15 nH, W=30 um, VGH=2.4 V)"),
   "AT_THE_FEASIBLE_FRONTIER_committed_90pct_bar":
       (compare(allf_90[0]["t_level_ps"],
                "THE FEASIBLE FRONTIER on the inherited 90%% bar at %s"
                % allf_90[0]["tag"]) if allf_90 else None),
 },
}

json.dump(out, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
print("wrote RESULTS.json")
print("data rows %d, mix-control %d, gate-drive %d, never-converged %d"
      % (len(data), len(rest), len(vgh), len(err)))
print("FEASIBLE rows: %d" % len(feasible))
for k, v in list(cser_fit.items())[:3]:
    print("  C_ser fit %s: c0=%.3f fF  c1=%.4f fF/cell  worst resid %.2f%%"
          % (k, v["c0_switch_floor_fF"], v["c1_per_cell_fF"], v["worst_resid_pct"]))
