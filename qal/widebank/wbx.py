#!/usr/bin/env python3
"""Per-row extraction for the WIDEBANK sweep.

Conventions inherited VERBATIM from qal/banktank/extract.py (sha256 75336909...,
recorded in DISK_STATE_BEFORE.txt), which inherits skip4/chain3/lsweep/swsweep:

  * per-gate settling at the bank's OWN stage boundary, NEVER aggregated:
      pull-DOWN cell (input HIGH):  pct = 100*(1 - V(o)/rail_k)
      pull-UP   cell (input LOW ):  pct = 100*(V(o)/rail_k)
  * data-pattern VALUE guard: pull-DOWN output <= 0.10*rail_k, pull-UP >= 0.50*rail_k
  * gate-drive-vs-Vt check with the CORRECTED thresholds Vtn 0.5239 / |Vtp| 0.4403
  * 1F integrators, every one t0-referenced against its own Z checkpoint.

WHAT IS DIFFERENT HERE, and why:
  * ALL N gate outputs come from .measure (the .mt0), not from .prn columns --
    a disk decision declared in PRE_REGISTERED.json.  Trajectory-dependent
    quantities are computed on the two class representatives that ARE printed,
    and the intra-class identity that licenses that is MEASURED at the
    checkpoint on all N gates (reported as intra_class_spread_mV).
  * the FUNCTIONAL criterion is qal/fcrit's, imported UNMODIFIED (Trip class
    from fcrit/rescore.py) -- bank 2's gates are scored against bank 3's
    MEASURED trip at bank 3's DELIVERED rail at the instant bank 3 commits
    (its own rise ZCS = the end of its charge delivery), which is exactly
    rescore.commit_instants' rule for an inductor-charged bank.
  * the noise budget is DETERMINISTIC TERMS ONLY.  The primary margin is the
    BARE threshold (0 mV); the committed 3*sigma_trip = 19.323 mV column is
    reported alongside for continuity ONLY, with the standing correction that
    it double-counts mismatch when mismatch is not being drawn.
"""
import json, math, os, sys
import wb
from wb import (EDGE, TAIL, cbank, wtot, widths, pat, in_hi, out_hi, reps,
                schedule, parse_mt0, read_prn, vtank0, QGATE_PER_UM, VGH,
                RS_REF, L_REF)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/local/src/stat-sim/qal/fcrit")
import rescore as FC                      # committed, UNMODIFIED

TRIP = FC.Trip("/usr/local/src/stat-sim/qal/fcrit/TRIP.json", "S")
SIGMA_TRIP_MV = FC.SIGMA_TRIP_MV          # 6.441, MEASURED qal/vtaudit
NB_FREE_MV = 3.0 * SIGMA_TRIP_MV          # 19.323, the committed 'free' budget

VTN, VTP = 0.5239, 0.4403                 # MEASURED qal/chain3/vt.json
SIGMA_FLOOR_MV = 6.44

# CMOS references (committed; both carried, neither replaces the other)
CMOS_INV_CYCLE_FJ = 10.0831               # one hi+lo cycle of the measured inverter
CMOS_BLOCK_PER_CELL_FJ = 4.14             # 232 fJ/op / 56 cells
CMOS_BLOCK_LEVEL_PS = 92.8                # 928 ps / 10 levels
E_TIMER_FLOOR_FJ = 3.5227                 # campaign's measured ideal-PWL timer floor

# --- SWING FAIRNESS, and it cuts AGAINST QAL ------------------------------
# BOTH committed CMOS references are measured at 1.2 V (bound/PRE_REGISTERED.json
# CMOS_inverter_anchor_fJ_per_full_cycle 10.0831 on the SAME 1.12p/0.74n cell;
# the 232 fJ/928 ps/56-cell block on the SG13G2 typ 1.2 V synthesis).  QAL is
# run here at dV = 1.65 V because BELOW Vtn + |Vtp| = 0.9642 V the cascade is
# not level-restoring and the block fails 59/161 at dV = 1.2 -- i.e. the larger
# swing is a REQUIREMENT OF QAL, not a free parameter.  So the PRIMARY
# comparison is QAL at 1.65 V against CMOS at 1.2 V, which is the comparison
# that does NOT flatter QAL.  The iso-swing column (what CMOS would cost if it
# were also forced to 1.65 V, scaling as V^2) is reported as a clearly labelled
# DERIVED alternative, never as the headline.
CMOS_V = 1.2
ISO = (1.65 / CMOS_V) ** 2                                  # 1.890625
CMOS_INV_CYCLE_ISO_FJ = CMOS_INV_CYCLE_FJ * ISO             # 19.0634
CMOS_BLOCK_PER_CELL_ISO_FJ = CMOS_BLOCK_PER_CELL_FJ * ISO   # 7.8272


def settle_pct(k, i, v, rail, P):
    return 100.0 * ((1.0 - v / rail) if in_hi(k, i, P) else (v / rail))


def guard_ok(k, i, v, rail, P):
    return (v <= 0.10 * rail) if in_hi(k, i, P) else (v >= 0.50 * rail)


def col(hdr, name):
    return hdr.index(name.upper())


def first_valid_on_reps(hdr, rows, k, P, t_from, t_to, thresh=90.0):
    """MEASURED: first instant in [t_from, t_to] at which BOTH electrical class
    representatives of bank k are >= thresh% settled AND pattern-correct,
    referenced to the rail at that same instant.  The committed
    data_valid_instant rule, evaluated on the representatives."""
    ir = col(hdr, "V(RAIL%d)" % k)
    io = [(i, col(hdr, "V(O%d_%d)" % (k, i))) for i in reps(k, P)]
    for r in rows:
        t = r[1] * 1e12
        if t < t_from or t > t_to:
            continue
        rail = r[ir]
        if rail <= 0.05:
            continue
        if all(settle_pct(k, i, r[c], rail, P) >= thresh and
               guard_ok(k, i, r[c], rail, P) for i, c in io):
            return t
    return None


def first_functional_on_reps(hdr, rows, k, P, t_from, t_to, budget_mV=0.0):
    """MEASURED: first instant both class representatives of bank k are on the
    correct side of the trip evaluated at the rail DELIVERED AT THAT INSTANT, by
    at least budget_mV.  Self-referenced (bank k's own rail), so it is the
    settling time of the bank, not the receiver-referenced commit test."""
    ir = col(hdr, "V(RAIL%d)" % k)
    io = [(i, col(hdr, "V(O%d_%d)" % (k, i))) for i in reps(k, P)]
    for r in rows:
        t = r[1] * 1e12
        if t < t_from or t > t_to:
            continue
        rail = r[ir]
        if rail <= 0.05:
            continue
        vt, _ = TRIP(rail)
        ok = True
        for i, c in io:
            d = (r[c] - vt) if out_hi(k, i, P) else (vt - r[c])
            if d < budget_mV / 1000.0:
                ok = False
                break
        if ok:
            return t
    return None


def row_extract(n, m, T, H, dv, mode, z, path, wmul=1.0, nb=3, mstep=None,
                P=None, wall_s=None):
    P = P or pat(n)
    mt = parse_mt0(path + ".mt0")
    hdr, rows = read_prn(path + ".prn")
    S = schedule(T, H, dv, z["tzr"], z["tzq"], nb)
    vt0 = dv if mode == "vfull" else vtank0(m, dv)
    cb = cbank(n)
    ct = m * cb
    W = wtot(n, wmul)
    w3 = widths(W)
    Wdev = w3["wn"] + w3["wp"] + w3["park"]

    r = dict(_LABELS="MEASURED unless the key says DERIVED or ASSUMED",
             N=n, m=m, T_ps=T, H=H, dv=dv, mode=mode, nb=nb, wmul=wmul,
             L_nH=L_REF, RS_ohm=RS_REF, wall_s=wall_s,
             C_bank_fF_DERIVED=cb, C_tank_fF_DERIVED=ct, V_tank0_DERIVED=vt0,
             W_nominal_um=W, W_device_total_um=Wdev,
             mstep_ps=wb.mstep_of(n, mstep),
             tzr=z["tzr"], tzq=z["tzq"], c=S["c"], o=S["o"], rcl=S["r"],
             ro=S["ro"], bound=S["bound"], tend=S["tend"])

    # ---------------- rails / tanks
    rail = {k: mt["VR%dB%d" % (k, k)] for k in range(1, nb + 1)}
    r["rail_at_own_boundary_V"] = rail
    r["rail_peak_V"] = {k: mt["VR%dPK" % k] for k in range(1, nb + 1)}
    r["rail_at_own_open_V"] = {k: mt["VR%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_t0_V"] = {k: mt["VT%dZ" % k] for k in range(1, nb + 1)}
    r["tank_after_rise_V"] = {k: mt["VT%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_after_return_V"] = {k: mt["VT%dQ%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_end_V"] = {k: mt["VT%dD" % k] for k in range(1, nb + 1)}
    r["rail_depth_spread_mV"] = 1000.0 * (max(rail.values()) - min(rail.values()))

    # ---------------- per-gate settling + VALUE, ALL N gates from .mt0
    st, pat_, drv, sep, spread = {}, {}, {}, {}, {}
    for k in range(1, nb + 1):
        rk = rail[k]
        sk, pk_, dk = {}, {}, {}
        his, los = [], []
        cls = {True: [], False: []}
        for i in range(n):
            v = mt["O%d_%dB" % (k, i)]
            sk["o%d" % i] = settle_pct(k, i, v, rk, P) if rk > 0 else None
            pk_["o%d" % i] = dict(v=v, expect_hi=bool(out_hi(k, i, P)),
                                  guard=bool(guard_ok(k, i, v, rk, P))
                                  if rk > 0 else False)
            (los if in_hi(k, i, P) else his).append(v)
            cls[in_hi(k, i, P)].append(v)
            if k > 1:
                vin = mt["N%d_%dB" % (k, i)]
                if in_hi(k, i, P):
                    dk["o%d" % i] = dict(vin=vin, dev="nmos", overdrive_V=vin - VTN)
                else:
                    dk["o%d" % i] = dict(vin=vin, dev="pmos",
                                         overdrive_V=rk - vin - VTP)
        st[k] = sk; pat_[k] = pk_; drv[k] = dk
        sep[k] = dict(min_HIGH_V=min(his), max_LOW_V=max(los),
                      separation_mV=1000.0 * (min(his) - max(los)))
        spread[k] = {("in_HIGH" if kk else "in_LOW"):
                     round(1000.0 * (max(vv) - min(vv)), 9)
                     for kk, vv in cls.items() if vv}
    r["intra_class_spread_mV"] = spread
    r["settling_pct_per_class"] = {
        k: {("in_HIGH" if in_hi(k, i, P) else "in_LOW"): st[k]["o%d" % i]
            for i in reps(k, P)} for k in st}
    r["settling_worst_per_bank_pct"] = {
        k: min(v for v in st[k].values() if v is not None) for k in st}
    r["worst_gate_pct"] = min(v for k in st for v in st[k].values()
                              if v is not None)
    r["worst_gate_where"] = min(((v, k, gg) for k in st for gg, v in st[k].items()
                                 if v is not None))[1:]
    r["gate_drive_per_class"] = {
        k: {("in_HIGH" if in_hi(k, i, P) else "in_LOW"): drv[k].get("o%d" % i)
            for i in reps(k, P)} for k in drv if drv[k]}
    r["separation_by_depth"] = sep
    r["separation_min_mV"] = min(sep[k]["separation_mV"] for k in sep)

    r["A1_value_all_banks_pass"] = all(pat_[k][gg]["guard"]
                                       for k in pat_ for gg in pat_[k])
    r["A1_value_bank2_pass"] = (all(pat_[2][gg]["guard"] for gg in pat_[2])
                                if 2 in pat_ else None)
    r["A1_value_fail_count"] = sum(1 for k in pat_ for gg in pat_[k]
                                   if not pat_[k][gg]["guard"])
    r["A1_value_fail_list"] = [(k, gg) for k in pat_ for gg in pat_[k]
                               if not pat_[k][gg]["guard"]][:20]
    r["A3_settling_pass_90"] = r["worst_gate_pct"] >= 90.0
    r["A5_fade_pass"] = (r["separation_min_mV"] >= SIGMA_FLOOR_MV and
                         all(sep[k]["separation_mV"] > 0 for k in sep))

    # ---------------- A2 FUNCTIONAL: bank 2 scored at bank 3's commit
    if nb >= 3 and "VR3F" in mt:
        t_commit3 = S["o"][3]
        rail3 = mt["VR3F"]
        vt_rx, extrap = TRIP(rail3)
        links, mins = [], []
        for i in range(n):
            v = mt["O2_%dF" % i]
            d = (v - vt_rx) if out_hi(2, i, P) else (vt_rx - v)
            mins.append(1000.0 * d)
            links.append(dict(i=i, want_hi=bool(out_hi(2, i, P)),
                              v_at_commit_V=v, margin_mV=round(1000.0 * d, 4)))
        r["A2_functional"] = dict(
            _criterion="qal/fcrit S3, imported unmodified: sender vs the "
                       "RECEIVER's measured trip at the RECEIVER's delivered "
                       "rail at the instant the RECEIVER commits (its rise ZCS)",
            receiver_bank=3, t_commit_ps=t_commit3,
            rail_receiver_V=rail3, rail_sender_V=mt.get("VR2F"),
            vtrip_receiver_V=vt_rx,
            trip_frac_of_rail=(vt_rx / rail3 if rail3 else None),
            trip_extrapolated=bool(extrap),
            margin_min_mV=min(mins), margin_max_mV=max(mins),
            n_pass_bare=sum(1 for x in mins if x >= 0.0),
            n_pass_3sigma=sum(1 for x in mins if x >= NB_FREE_MV),
            n_gates=n,
            PASS_bare=all(x >= 0.0 for x in mins),
            PASS_3sigma_CONTINUITY_ONLY=all(x >= NB_FREE_MV for x in mins),
            worst_links=sorted(links, key=lambda L: L["margin_mV"])[:6])
        r["A2_value_pass"] = r["A2_functional"]["PASS_bare"]
    else:
        r["A2_functional"] = None
        r["A2_value_pass"] = None

    r["PASS"] = bool(r["A1_value_all_banks_pass"] and r["A2_value_pass"])

    # ---------------- t_hop / t_settle / LEVEL time, all MEASURED
    r["t_hop_rise_ps"] = z["tzr"][1] if nb >= 2 else z["tzr"][0]
    r["t_hop_return_ps"] = z["tzq"][1] if nb >= 2 else z["tzq"][0]
    fv, ff = {}, {}
    for k in range(1, nb + 1):
        fv[k] = first_valid_on_reps(hdr, rows, k, P, S["c"][k],
                                    S["tend"] - TAIL / 2)
        ff[k] = first_functional_on_reps(hdr, rows, k, P, S["c"][k],
                                         S["tend"] - TAIL / 2)
    r["first_valid90_instant_ps"] = fv
    r["first_functional_instant_ps"] = ff
    r["t_settle_from_own_rail_start_ps"] = {
        k: (fv[k] - S["c"][k]) if fv[k] else None for k in fv}
    r["t_settle_functional_from_own_rail_start_ps"] = {
        k: (ff[k] - S["c"][k]) if ff[k] else None for k in ff}
    r["t_settle_after_hop_ps"] = {
        k: (fv[k] - S["o"][k]) if fv[k] else None for k in fv}
    r["LEVEL_TIME_scheduled_beat_ps"] = T
    r["LEVEL_TIME_measured_bank2_ps"] = r["t_settle_from_own_rail_start_ps"].get(2)
    r["LEVEL_TIME_measured_functional_bank2_ps"] = \
        r["t_settle_functional_from_own_rail_start_ps"].get(2)
    r["stage_time_measured_ps"] = ((fv[3] - fv[2]) if (nb >= 3 and fv.get(3)
                                                       and fv.get(2)) else None)

    # ---------------- INSTRUMENT gates
    r["IZ_uA"] = {k: 1e6 * mt["IZ%d" % k] for k in range(1, nb + 1)}
    r["IZQ_uA"] = {k: 1e6 * mt["IZQ%d" % k] for k in range(1, nb + 1)}
    r["IPK_uA"] = {k: 1e6 * mt["IPK%d" % k] for k in range(1, nb + 1)}
    r["A4_zcs_pass"] = (all(abs(v) <= 1.0 for v in r["IZ_uA"].values()) and
                        all(abs(v) <= 1.0 for v in r["IZQ_uA"].values()))
    r["ICROSS_at_bank2_zcs_uA"] = {k: 1e6 * mt["ICROSS%d" % k]
                                   for k in range(1, nb + 1)}
    r["A7_source_side_cut_pass"] = all(
        abs(r["ICROSS_at_bank2_zcs_uA"][k]) <= 5.0
        for k in r["ICROSS_at_bank2_zcs_uA"] if k != 2)

    # ---------------- ENERGY (1F integrators, t0-referenced; fJ)
    def g(tag, ck):
        return (mt["%s_%s" % (tag.upper(), ck)] - mt["%s_Z" % tag.upper()]) * 1e15

    en = {}
    for k in range(1, nb + 1):
        o, q, rc = "O%d" % k, "Q%d" % k, "R%d" % k
        ea_o, eb_o = g("ea%d" % k, o), g("eb%d" % k, o)
        esw_o, er_o = g("esw%d" % k, o), g("er%d" % k, o)
        ea_q, eb_q = g("ea%d" % k, q), g("eb%d" % k, q)
        ea_r, eb_r = g("ea%d" % k, rc), g("eb%d" % k, rc)
        v0, v1, v2 = mt["VT%dZ" % k], mt["VT%dQ%d" % (k, k)], mt["VT%dD" % k]
        e = dict(E_out_of_tank_rise_fJ=ea_o,
                 E_into_rail_rise_fJ=eb_o,
                 E_seriesR_rise_fJ=er_o,
                 E_switchblock_rise_fJ=esw_o - eb_o,
                 path_identity_rise_fJ=ea_o - esw_o - er_o,
                 E_back_into_tank_return_fJ=-(ea_q - ea_r),
                 E_out_of_rail_return_fJ=-(eb_q - eb_r),
                 E_seriesR_return_fJ=g("er%d" % k, q) - g("er%d" % k, rc),
                 Q_through_L_rise_fC=g("qlt%d" % k, o),
                 tank_dV_over_cycle_mV=1000.0 * (v0 - v1),
                 tank_energy_lost_fJ=0.5 * ct * (v0 * v0 - v1 * v1),
                 tank_dV_to_end_mV=1000.0 * (v0 - v2),
                 tank_energy_lost_to_end_fJ=0.5 * ct * (v0 * v0 - v2 * v2))
        ea_D = g("ea%d" % k, "D")
        e["E_out_of_tank_whole_run_fJ"] = ea_D
        # PARK BRANCH, measured (widebank amendment A5): positive = INTO tank.
        epa_o, epa_q, epa_r = (g("epa%d" % k, o), g("epa%d" % k, q),
                               g("epa%d" % k, rc))
        epa_D = g("epa%d" % k, "D")
        e["E_park_into_tank_rise_fJ"] = epa_o
        e["E_park_into_tank_cycle_fJ"] = epa_q
        e["E_park_into_tank_whole_run_fJ"] = epa_D
        e["Q_park_into_tank_cycle_fC"] = g("qpa%d" % k, q)
        e["E_out_of_tank_via_park_cycle_fJ"] = -epa_q
        # CLOSURE, now complete: the tank's own energy change must equal what
        # left through L minus what came back through the park.
        e["tank_closure_residual_fJ"] = (ea_D - epa_D
                                         - e["tank_energy_lost_to_end_fJ"])
        e["tank_closure_residual_Lonly_fJ"] = (ea_D
                                               - e["tank_energy_lost_to_end_fJ"])
        e["recycle_fraction_pct"] = (100.0 * e["E_back_into_tank_return_fJ"]
                                     / e["E_into_rail_rise_fJ"]
                                     if e["E_into_rail_rise_fJ"] else None)
        qq = {}
        for src in ("qgt", "qgp", "qpk"):
            # PRE-CLOSE reference (widebank amendment A6): the close-edge charge
            # is taken against a checkpoint 3 ps BEFORE the close edge, not
            # against the t=0 integrator zero.  Referencing to t=0 would put
            # every earlier bank's whole hop inside bank k's "close" window.
            base = mt["%s%d_P" % (src.upper(), k)] * 1e15
            a_ = mt["%s%d_A" % (src.upper(), k)] * 1e15
            b_ = mt["%s%d_B" % (src.upper(), k)] * 1e15
            c_ = mt["%s%d_C" % (src.upper(), k)] * 1e15
            qq[src] = dict(Q_close_fC=a_ - base, Q_conduct_fC=b_ - a_,
                           Q_open_fC=c_ - b_,
                           Q_net_over_hop_fC=c_ - base,
                           Q_abs_per_hop_fC=abs(a_ - base) + abs(c_ - b_))
        e["gate_charge_MEASURED_fC"] = qq
        e["Q_gate_abs_total_per_hop_fC"] = sum(qq[s]["Q_abs_per_hop_fC"]
                                               for s in qq)
        en[k] = e
    r["energy_per_bank"] = en
    r["E_gate_drive_idealPWL_total_fJ"] = g("egt", "D")
    r["E_wellrail_total_fJ"] = g("ehi", "D")
    r["E_ideal_inputs_bank1_fJ"] = g("ei1", "D")
    r["A5_path_identity_pass"] = all(
        abs(en[k]["path_identity_rise_fJ"]) <= 0.01
        * abs(en[k]["E_out_of_tank_rise_fJ"]) for k in en
        if en[k]["E_out_of_tank_rise_fJ"])
    r["A6_tank_closure_pass"] = all(
        abs(en[k]["tank_closure_residual_fJ"]) <= 0.05
        * abs(en[k]["tank_energy_lost_fJ"]) for k in en
        if en[k]["tank_energy_lost_fJ"])

    # ---------------- A9: is the swept axis labelled correctly?
    k2 = 2 if nb >= 2 else 1
    swing = r["rail_at_own_open_V"][k2]
    q_meas = en[k2]["Q_through_L_rise_fC"]
    c_meas = q_meas / swing if swing else None
    r["A9_C_bank_measured_secant_fF"] = c_meas
    r["A9_C_bank_ratio_measured_over_derived"] = (c_meas / cb) if c_meas else None
    r["A9_pass"] = bool(c_meas and 0.5 <= c_meas / cb <= 2.0)

    # ---------------- THE LEDGER (PRE_REGISTERED : ENERGY LEDGER)
    e2 = en[k2]
    e_tank = e2["tank_energy_lost_fJ"]
    egd_floor = r["E_gate_drive_idealPWL_total_fJ"] / nb
    qg_derived = QGATE_PER_UM * W
    qg_measured = e2["Q_gate_abs_total_per_hop_fC"]
    egd_conv_derived = qg_derived * VGH
    egd_conv_measured = qg_measured * VGH
    L1 = {}
    for name, egd in (("idealPWL_floor_MEASURED", egd_floor),
                      ("conventional_from_lsweep_fit_DERIVED", egd_conv_derived),
                      ("conventional_from_own_measured_charge", egd_conv_measured)):
        for tn, et in (("timer0_BOUND", 0.0),
                       ("timer_floor_ASSUMED_3p5227", E_TIMER_FLOOR_FJ)):
            tot = e_tank + egd + et
            L1["%s__%s" % (name, tn)] = dict(
                E_bank_per_hop_fJ=tot, E_per_gate_fJ=tot / n,
                x_vs_CMOS_block_4p14=tot / n / CMOS_BLOCK_PER_CELL_FJ,
                x_vs_CMOS_inv_cycle=tot / n / CMOS_INV_CYCLE_FJ,
                beats_CMOS_block=bool(tot / n < CMOS_BLOCK_PER_CELL_FJ),
                beats_CMOS_inv_cycle=bool(tot / n < CMOS_INV_CYCLE_FJ),
                x_vs_CMOS_block_isoswing_DERIVED=tot / n
                / CMOS_BLOCK_PER_CELL_ISO_FJ,
                x_vs_CMOS_inv_isoswing_DERIVED=tot / n / CMOS_INV_CYCLE_ISO_FJ,
                beats_CMOS_block_isoswing_DERIVED=bool(
                    tot / n < CMOS_BLOCK_PER_CELL_ISO_FJ))
    r["LEDGER"] = dict(
        _terms="E_bank_per_hop = E_tank_loss (MEASURED, convention-free) "
               "+ E_switch_gate_drive (band) + E_timer (0 or 3.5227, ASSUMED). "
               "Switch conduction and series R are INSIDE E_tank_loss and are "
               "NOT added again.",
        bank_scored=k2,
        E_tank_loss_fJ=e_tank,
        E_switch_conduction_fJ=e2["E_switchblock_rise_fJ"],
        E_seriesR_rise_fJ=e2["E_seriesR_rise_fJ"],
        E_out_of_tank_via_park_cycle_fJ=e2["E_out_of_tank_via_park_cycle_fJ"],
        E_resonant_share_of_tank_loss_pct=(
            100.0 * (e_tank - e2["E_out_of_tank_via_park_cycle_fJ"]) / e_tank
            if e_tank else None),
        E_gate_drive_idealPWL_per_bank_fJ=egd_floor,
        Q_gate_DERIVED_lsweep_fC=qg_derived,
        Q_gate_MEASURED_fC=qg_measured,
        Q_gate_MEASURED_per_um=qg_measured / W,
        E_gate_drive_conventional_DERIVED_fJ=egd_conv_derived,
        E_gate_drive_conventional_from_measured_fJ=egd_conv_measured,
        rows=L1)
    r["E_per_gate_headline_fJ"] = \
        L1["idealPWL_floor_MEASURED__timer0_BOUND"]["E_per_gate_fJ"]

    # ---------------- AREA (the other half of the trade)
    r["area"] = dict(
        _basis="MIM 1.5 fF/um^2 (sg13g2) for the tank; switch area = nominal "
               "total width x 0.13 um channel length (device active only, no "
               "routing/contacts); cells = N x (1.12+0.74) um x 0.13 um. "
               "DERIVED, not laid out.",
        tank_um2=ct / 1.5, switch_um2=Wdev * 0.13,
        cells_um2=n * (1.12 + 0.74) * 0.13,
        tank_um2_per_gate=ct / 1.5 / n)
    return r


if __name__ == "__main__":
    n, T, H, dv, mode, zf = (int(sys.argv[1]), float(sys.argv[2]),
                             int(sys.argv[3]), float(sys.argv[4]),
                             sys.argv[5], sys.argv[6])
    nb = int(sys.argv[7]) if len(sys.argv) > 7 else 3
    wmul = float(sys.argv[8]) if len(sys.argv) > 8 else 1.0
    ms = float(sys.argv[9]) if len(sys.argv) > 9 and sys.argv[9] != "-" else None
    extra = sys.argv[10] if len(sys.argv) > 10 else ""
    z = json.load(open(os.path.join(HERE, zf)))
    tag = wb.tag_of(n, T, H, dv, mode, wmul, nb, extra)
    path = os.path.join(HERE, "c_%s.cir" % tag)
    r = row_extract(n, 10.0, T, H, dv, mode, z, path, wmul=wmul, nb=nb, mstep=ms)
    open(os.path.join(HERE, "row_%s.json" % tag), "w").write(
        json.dumps(r, indent=1, default=str))
    A2 = r["A2_functional"]
    print("%s  N=%d PASS=%s A1=%s A2=%s(min %.2f mV) worst90=%.2f%% "
          "t_hop=%.1f Lvl=%s E/gate=%.4f fJ (%.3fx CMOS4.14) Ipk=%.0fuA "
          "W=%.1fum Qg=%.2ffC"
          % (tag, n, r["PASS"], r["A1_value_all_banks_pass"],
             A2["PASS_bare"] if A2 else None,
             A2["margin_min_mV"] if A2 else float("nan"),
             r["worst_gate_pct"], r["t_hop_rise_ps"],
             r["LEVEL_TIME_measured_bank2_ps"], r["E_per_gate_headline_fJ"],
             r["E_per_gate_headline_fJ"] / CMOS_BLOCK_PER_CELL_FJ,
             r["IPK_uA"][2], r["W_nominal_um"],
             r["LEDGER"]["Q_gate_MEASURED_fC"]))
