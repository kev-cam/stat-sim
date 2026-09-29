#!/usr/bin/env python3
"""Per-row extraction for the PER-BANK TANK study.

Every number here is MEASURED off a .mt0 or a .prn.  Conventions inherited
VERBATIM from qal/skip4/extract.py (which inherits chain3/lsweep/swsweep/gateb):

  * per-gate settling at the bank's OWN stage boundary, NEVER aggregated:
      pull-DOWN cell (input HIGH):  pct = 100*(1 - V(o)/rail_k)
      pull-UP   cell (input LOW ):  pct = 100*(V(o)/rail_k)
    with rail_k = V(rail k) at that same boundary instant.
  * data-pattern guard: pull-DOWN output <= 0.10*rail_k, pull-UP >= 0.50*rail_k.
  * gate-drive-vs-Vt check (the guard that caught skip4's "the nMOS is off and
    the node is merely undisturbed").
  * separation by depth against the CORRECTED 6.44 mV 1-sigma floor.
"""
import json, math, os, sys
from bt import (MGATE, NBANK, EDGE, TAIL, T1, CBANK, in_hi, out_hi, schedule,
                parse_mt0, read_prn, vtank0, widths)

SIGMA_FLOOR_MV = 6.44       # qal/vtaudit/AUDIT.md corrected 1-sigma floor
VTN   = 0.5239              # MEASURED, qal/chain3/vt.json
VTP   = 0.4403              # MEASURED |Vtp|, qal/chain3/vt.json
CLIFF = 0.60                # V, absolute functional floor (device-Vt fact)


def settle_pct(k, i, v, rail):
    return 100.0 * ((1.0 - v / rail) if in_hi(k, i) else (v / rail))


def guard_ok(k, i, v, rail):
    return (v <= 0.10 * rail) if in_hi(k, i) else (v >= 0.50 * rail)


def col(hdr, name):
    return hdr.index(name.upper())


def at(hdr, rows, name, tt):
    ic = col(hdr, name)
    best, bt_ = None, None
    for r in rows:
        t = r[1] * 1e12
        if bt_ is None or abs(t - tt) < abs(bt_ - tt):
            bt_, best = t, r[ic]
    return best


def data_valid_instant(hdr, rows, k, t_from, t_to, thresh=90.0):
    """MEASURED: the first instant in [t_from, t_to] at which ALL 8 gates of bank
    k are >= thresh% settled AND pattern-correct, referenced to the rail at that
    same instant.  None if it never happens in the window."""
    ir = col(hdr, "V(RAIL%d)" % k)
    io = [col(hdr, "V(O%d_%d)" % (k, i)) for i in range(MGATE)]
    for r in rows:
        t = r[1] * 1e12
        if t < t_from or t > t_to:
            continue
        rail = r[ir]
        if rail <= 0.05:
            continue
        ok = True
        for i in range(MGATE):
            v = r[io[i]]
            if settle_pct(k, i, v, rail) < thresh or not guard_ok(k, i, v, rail):
                ok = False
                break
        if ok:
            return t
    return None


def overlap(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return max(0.0, hi - lo)


def row_extract(m, T, H, dv, mode, z, path):
    mt = parse_mt0(path + ".mt0")
    hdr, rows = read_prn(path + ".prn")
    S = schedule(T, H, dv, z["tzr"], z["tzq"])
    nb = S["nbank"]
    vt0 = vtank0(m, dv)
    ct_fF = m * CBANK
    r = dict(m=m, T_ps=T, H=H, dv=dv, mode=mode, C_tank_fF=ct_fF, V_tank0=vt0,
             tzr=z["tzr"], tzq=z["tzq"], c=S["c"], o=S["o"], rcl=S["r"],
             ro=S["ro"], bound=S["bound"], tend=S["tend"])

    # ---------------- rails / tanks (MEASURED)
    rail = {k: mt["VR%dB%d" % (k, k)] for k in range(1, nb + 1)}
    r["rail_at_own_boundary_V"] = rail
    r["rail_peak_V"] = {k: mt["VR%dPK" % k] for k in range(1, nb + 1)}
    r["rail_at_own_open_V"] = {k: mt["VR%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_t0_V"] = {k: mt["VT%dZ" % k] for k in range(1, nb + 1)}
    r["tank_after_rise_V"] = {k: mt["VT%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_after_return_V"] = {k: mt["VT%dQ%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_end_V"] = {k: mt["VT%dD" % k] for k in range(1, nb + 1)}

    # DEPTH TEST: does the delivered rail fade with depth?  (the thing local
    # tanks are supposed to remove entirely)
    r["rail_depth_spread_mV"] = 1000.0 * (max(rail.values()) - min(rail.values()))
    r["rail_bank4_minus_bank1_mV"] = 1000.0 * (rail[nb] - rail[1])

    # ---------------- per-gate settling + VALUE check at each bank's boundary
    st, pat, drv, sep = {}, {}, {}, {}
    for k in range(1, nb + 1):
        rk = rail[k]
        sk, pk_, dk = {}, {}, {}
        his, los = [], []
        for i in range(MGATE):
            v = mt["O%d_%dB" % (k, i)]
            sk["o%d" % i] = settle_pct(k, i, v, rk) if rk > 0 else None
            pk_["o%d" % i] = dict(v=v, expect_hi=bool(out_hi(k, i)),
                                  guard=bool(guard_ok(k, i, v, rk)) if rk > 0 else False)
            (los if in_hi(k, i) else his).append(v)     # in HIGH -> out LOW
            if k > 1:
                vin = mt["N%d_%dB" % (k, i)]
                if in_hi(k, i):      # nMOS must be ON: Vgs - Vtn
                    dk["o%d" % i] = dict(vin=vin, dev="nmos",
                                         overdrive_V=vin - VTN)
                else:                # pMOS must be ON: rail - Vin - |Vtp|
                    dk["o%d" % i] = dict(vin=vin, dev="pmos",
                                         overdrive_V=rk - vin - VTP)
        st[k] = sk
        pat[k] = pk_
        drv[k] = dk
        sep[k] = dict(min_HIGH_V=min(his), max_LOW_V=max(los),
                      separation_mV=1000.0 * (min(his) - max(los)))
    r["settling_pct_per_gate"] = st
    r["value_check_per_gate"] = pat
    r["gate_drive_per_gate"] = drv
    r["separation_by_depth"] = sep

    r["worst_gate_pct"] = min(v for k in st for v in st[k].values() if v is not None)
    r["worst_gate_where"] = min(((v, k, g) for k in st for g, v in st[k].items()
                                 if v is not None))[1:]
    r["per_bank_worst_pct"] = {k: min(v for v in st[k].values() if v is not None)
                               for k in st}
    r["value_check_all_pass"] = all(pat[k][g]["guard"] for k in pat for g in pat[k])
    r["value_fail_list"] = [(k, g) for k in pat for g in pat[k]
                            if not pat[k][g]["guard"]]
    r["A1_settling_pass_90"] = r["worst_gate_pct"] >= 90.0
    r["A2_value_pass"] = r["value_check_all_pass"]
    r["PASS"] = bool(r["A1_settling_pass_90"] and r["A2_value_pass"])
    r["separation_min_mV"] = min(sep[k]["separation_mV"] for k in sep)
    r["A5_fade_pass"] = (r["separation_min_mV"] >= SIGMA_FLOOR_MV and
                         all(sep[k]["separation_mV"] > 0 for k in sep))

    # ---------------- MEASURED data-valid instants and the REAL overlap
    dvt = {}
    for k in range(1, nb + 1):
        dvt[k] = data_valid_instant(hdr, rows, k, S["c"][k], S["tend"] - TAIL / 2)
    r["data_valid_instant_ps"] = dvt
    r["data_valid_delay_from_own_rail_start_ps"] = {
        k: (dvt[k] - S["c"][k]) if dvt[k] else None for k in dvt}
    r["rail_start_offset_vs_pred_dv_ps"] = {
        k: (S["c"][k] - dvt[k - 1]) if (k > 1 and dvt[k - 1]) else None
        for k in range(2, nb + 1)}
    # AMENDMENT A3: the rate at which VALID data actually advances one stage,
    # measured DIRECTLY off the running chain (never composed from parts).
    r["steady_state_stage_time_ps"] = {
        "%d_minus_%d" % (k, k - 1): ((dvt[k] - dvt[k - 1])
                                     if (dvt[k] and dvt[k - 1]) else None)
        for k in range(2, nb + 1)}
    dd = [v for v in r["steady_state_stage_time_ps"].values() if v is not None]
    r["stage_time_deepest_ps"] = (dvt[nb] - dvt[nb - 1]) if (dvt[nb] and dvt[nb - 1]) \
        else None
    r["all_banks_reach_valid"] = all(dvt[k] is not None for k in dvt)

    # ---------------- EXHAUSTIVE INTERVAL SCAN (the skip4 instrument)
    ramp = {k: (S["c"][k], S["o"][k]) for k in range(1, nb + 1)}
    ret = {k: (S["r"][k], S["ro"][k]) for k in range(1, nb + 1)}
    ev_post = {k: (S["o"][k], S["bound"][k]) for k in range(1, nb + 1)}
    ev_full = {k: (S["c"][k], S["bound"][k]) for k in range(1, nb + 1)}
    ev_meas = {k: (S["c"][k], dvt[k]) for k in range(1, nb + 1) if dvt[k]}
    scan = {}
    for nma, A in (("ramp", ramp), ("return", ret)):
        for nmb, B in (("eval_post_ramp", ev_post), ("eval_full", ev_full),
                       ("eval_measured_to_valid", ev_meas), ("ramp", ramp)):
            for ka in A:
                for kb in B:
                    if nma == nmb and ka == kb:
                        continue
                    ov = overlap(A[ka], B[kb])
                    if ov > 0.0:
                        scan["%s%d_x_%s%d" % (nma, ka, nmb, kb)] = round(ov, 4)
    r["interval_scan_intersections_ps"] = scan
    r["ramp_x_pred_eval_measured_ps"] = {
        k: round(overlap(ramp[k], ev_meas[k - 1]), 4)
        for k in range(2, nb + 1) if (k - 1) in ev_meas}
    r["ramp_x_pred_eval_full_ps"] = {
        k: round(overlap(ramp[k], ev_full[k - 1]), 4) for k in range(2, nb + 1)}

    # ---------------- CONCURRENT INDUCTOR COUNT
    #  schedule-exact: how many transfer switches conduct at once
    evts = sorted(set([t for k in ramp for t in ramp[k]] +
                      [t for k in ret for t in ret[k]]))
    best, bestt = 0, None
    for a, b in zip(evts, evts[1:]):
        mid = 0.5 * (a + b)
        n = sum(1 for k in ramp if ramp[k][0] <= mid <= ramp[k][1]) + \
            sum(1 for k in ret if ret[k][0] <= mid <= ret[k][1])
        if n > best:
            best, bestt = n, mid
    r["concurrent_inductors_schedule"] = best
    r["concurrent_inductors_at_ps"] = bestt
    r["concurrent_ramps_only_schedule"] = max(
        [sum(1 for k in ramp if ramp[k][0] <= 0.5 * (a + b) <= ramp[k][1])
         for a, b in zip(evts, evts[1:])] or [0])
    #  waveform cross-check: how many |I(L)| exceed 1 uA at the same instant
    ii = [col(hdr, "I(L%d)" % k) for k in range(1, nb + 1)]
    mx, mxt = 0, None
    for rr in rows:
        n = sum(1 for c in ii if abs(rr[c]) > 1e-6)
        if n > mx:
            mx, mxt = n, rr[1] * 1e12
    r["concurrent_inductors_waveform_gt1uA"] = mx
    r["concurrent_inductors_waveform_at_ps"] = mxt

    # ---------------- INSTRUMENT gates
    r["IZ_uA"] = {k: 1e6 * mt["IZ%d" % k] for k in range(1, nb + 1)}
    r["IZQ_uA"] = {k: 1e6 * mt["IZQ%d" % k] for k in range(1, nb + 1)}
    r["IPK_uA"] = {k: 1e6 * mt["IPK%d" % k] for k in range(1, nb + 1)}
    r["A6_zcs_pass"] = all(abs(v) <= 1.0 for v in r["IZ_uA"].values()) and \
                       all(abs(v) <= 1.0 for v in r["IZQ_uA"].values())

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
        en[k] = dict(
            E_out_of_tank_rise_fJ=ea_o,
            E_into_rail_rise_fJ=eb_o,
            E_seriesR_rise_fJ=er_o,
            E_switchblock_rise_fJ=esw_o - eb_o,
            path_identity_rise_fJ=ea_o - esw_o - er_o,
            E_back_into_tank_return_fJ=-(ea_q - ea_r),
            E_out_of_rail_return_fJ=-(eb_q - eb_r),
            E_seriesR_return_fJ=g("er%d" % k, q) - g("er%d" % k, rc),
            Q_through_L_rise_fC=g("qlt%d" % k, o) * 1e0,
            E_cells_ground_return_fJ=None)
        # the decisive, convention-free number: what the tank actually lost.
        # C_tank is a LINEAR cap, so 1/2 C (V0^2 - V1^2) needs no integrator
        # convention at all.  Reported at the return-open instant (one full
        # rise+hold+return cycle) AND at the end of the run.
        v0 = mt["VT%dZ" % k]
        v1 = mt["VT%dQ%d" % (k, k)]
        v2 = mt["VT%dD" % k]
        en[k]["tank_dV_over_cycle_mV"] = 1000.0 * (v0 - v1)
        en[k]["tank_energy_lost_fJ"] = 0.5 * ct_fF * (v0 * v0 - v1 * v1)
        en[k]["tank_dV_to_end_mV"] = 1000.0 * (v0 - v2)
        en[k]["tank_energy_lost_to_end_fJ"] = 0.5 * ct_fF * (v0 * v0 - v2 * v2)
        # closure: the whole-run integral of V(tnk)*I(L) must equal the cap's own
        # energy change, because nothing else draws from tnk except through L.
        ea_D = g("ea%d" % k, "D")
        en[k]["E_out_of_tank_whole_run_fJ"] = ea_D
        en[k]["tank_closure_residual_fJ"] = ea_D - en[k]["tank_energy_lost_to_end_fJ"]
        en[k]["recycle_fraction_pct"] = (
            100.0 * en[k]["E_back_into_tank_return_fJ"] / en[k]["E_into_rail_rise_fJ"]
            if en[k]["E_into_rail_rise_fJ"] else None)
    r["energy_per_bank"] = en
    r["E_gate_drive_total_fJ"] = g("egt", "D")
    r["E_vhi_total_fJ"] = g("ehi", "D")
    if mode == "topup":
        r["E_tank_recharge_measured_fJ"] = g("etu", "D")
        r["Q_tank_recharge_fC"] = g("qtu", "D") * 1e0
        # INTEGRATOR-FREE cross-check of the same quantity (amendment A8): the
        # source delivers Q at a known fixed rail voltage, and the tanks are
        # LINEAR caps whose stored-energy change needs no convention at all.
        qf = r["Q_tank_recharge_fC"]
        r["E_from_recharge_rail_QV_fJ"] = vt0 * qf
        stored = sum(0.5 * ct_fF * (mt["VT%dD" % k] ** 2 - mt["VT%dQ%d" % (k, k)] ** 2)
                     for k in range(1, nb + 1))
        r["E_stored_into_tanks_fJ"] = stored
        r["E_lost_in_recharge_switch_fJ"] = vt0 * qf - stored
        r["recharge_switch_efficiency_pct"] = (100.0 * stored / (vt0 * qf)
                                               if qf else None)
    r["A6_path_identity_pass"] = all(
        abs(en[k]["path_identity_rise_fJ"]) <= 0.01 * abs(en[k]["E_out_of_tank_rise_fJ"])
        for k in en if en[k]["E_out_of_tank_rise_fJ"])

    # ---------------- tank AREA (MIM/MOM density from the PDK)
    r["tank_area_um2_MIM"] = ct_fF / 1.5      # fF/um^2, sg13g2 MIM
    r["tank_area_um2_per_chain"] = nb * ct_fF / 1.5
    return r


if __name__ == "__main__":
    import bt
    m, T, H, dv, mode, zf = (float(sys.argv[1]), float(sys.argv[2]),
                             int(sys.argv[3]), float(sys.argv[4]),
                             sys.argv[5], sys.argv[6])
    z = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), zf)))
    tag = bt.tag_of(m, T, H, dv, mode)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "c_%s.cir" % tag)
    r = row_extract(m, T, H, dv, mode, z, path)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "row_%s.json" % tag)
    open(out, "w").write(json.dumps(r, indent=1, default=str))
    print("%s PASS=%s worst=%.2f%% sep_min=%.3f mV rail=%s Lconc=%d" %
          (tag, r["PASS"], r["worst_gate_pct"], r["separation_min_mV"],
           {k: round(v, 4) for k, v in r["rail_at_own_boundary_V"].items()},
           r["concurrent_inductors_schedule"]))
