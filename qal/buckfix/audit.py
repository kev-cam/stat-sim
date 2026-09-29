#!/usr/bin/env python3
"""(c) THE CHARGE AUDIT, per phase, to closure -- and (d) the simultaneous
HS/FW conduction test.  Runs on the standalone fixture so the converter is the
only thing in the circuit.
"""
import json, os, sys
import buck as B

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "CHARGE_AUDIT.json")


def marks_for(s, tstop):
    """Phase boundaries, named, from the schedule itself."""
    (h0, h1) = s["hs_off_lo"]
    (f0, f1) = s["fw_off"] or s["hs_off_lo"]
    (o0, o1) = s["out_close"]
    (p0, p1) = s["pulse"]
    (hx0, hx1) = s["hs_on_hi"]
    (fn0, fn1) = s["fw_on"]
    oo = s["out_open"]
    o0 = o0 or h0
    pts = [("Z", 0.5), ("A", min(h0, f0, o0) - 1.0), ("B", h1 + 0.2),
           ("C", f0), ("D", f1), ("O", o1), ("E", p1), ("F", max(hx1, fn1)),
           ("G", (s.get("fw_cut") or oo or (tstop - 40.0))), ("H", (oo + B.E + 0.5) if oo else tstop - 20.0),
           ("I", tstop - 1.0)]
    # keep strictly increasing and unique
    out, last = [], -1e9
    for t, v in pts:
        if v > last + 1e-6:
            out.append((t, v)); last = v
    return out


def probe_zero(s, cb, tstop=460.0, ltu_nh=B.LTU_NH, cna=B.CNA_FF, vrail0=0.766,
               tag="probe", wsw=B.WSW):
    """A6: RE-PROBE the true inductor current zero for THIS schedule.
    OUT is held closed past the transient end, exactly the committed probe form."""
    sp = dict(s, out_open=None)
    lines = B.deck(sp, cb, tstop, marks_for(sp, tstop), ltu_nh, cna, vrail0, wsw)
    fn = "P_%s_%s.cir" % (s["name"], tag)
    p, msg = B.run(fn, lines)
    if p is None:
        return None, msg
    hdr, rows = B.prn(p)
    it, il = B.col(hdr, "TIME"), B.col(hdr, "I(LTU)")
    t0 = s["pulse"][0] * 1e-12
    pk, tpk = 0.0, None
    for r in rows:
        if r[it] >= t0 and r[il] > pk:
            pk, tpk = r[il], r[it]
    if tpk is None:
        return None, "no positive inductor current after pulse start"
    zt = None
    prev = None
    for r in rows:
        if r[it] <= tpk:
            prev = r; continue
        if r[il] <= 0.0 and prev is not None:
            # linear interpolation onto the zero
            t1, i1 = prev[it], prev[il]
            t2, i2 = r[it], r[il]
            zt = t1 + (t2 - t1) * (i1 / (i1 - i2)) if i1 != i2 else t2
            break
        prev = r
    if zt is None:
        return None, "no zero crossing found after peak"
    return dict(t_zero_ps=zt * 1e12, i_peak_uA=pk * 1e6, t_peak_ps=tpk * 1e12), msg


def ledger(s, cb, tstop=460.0, ltu_nh=B.LTU_NH, cna=B.CNA_FF, vrail0=0.766,
           tag="run", wsw=B.WSW):
    mk = marks_for(s, tstop)
    lines = B.deck(s, cb, tstop, mk, ltu_nh, cna, vrail0, wsw)
    fn = "R_%s_%s.cir" % (s["name"], tag)
    p, msg = B.run(fn, lines)
    if p is None:
        return None, msg
    m = B.mt0(p)
    names = [n for n, _ in B.INTEG]
    # t0-reference EVERY integrator on the Z mark (the 1F pedestal)
    series = {}
    for n in names:
        z = m["%s_Z" % n.upper()]
        series[n] = {t: (m["%s_%s" % (n.upper(), t)] - z) for t, _ in mk}
    res = dict(schedule=s["name"], tag=tag, deck=fn, msg=msg, wsw_um=wsw,
               marks_ps={t: v for t, v in mk},
               C_bank_fF=cb, Ltu_nH=ltu_nh, Cna_fF=cna, vrail0_V=vrail0,
               I_L_peak_uA=m.get("ILPK", 0.0) * 1e6)
    # cumulative, in fC / fJ
    fC = lambda x: x * 1e15
    res["cumulative_fC"] = {n: {t: round(fC(series[n][t]), 4) for t, _ in mk}
                            for n in names if not n.startswith("e")}
    res["cumulative_fJ"] = {n: {t: round(series[n][t] * 1e15, 5) for t, _ in mk}
                            for n in names if n.startswith("e")}
    res["rail_V"] = {t: round(m["VRAIL_%s" % t], 7) for t, _ in mk}
    res["na_V"] = {t: round(m["VNA_%s" % t], 7) for t, _ in mk}
    res["I_LTU_uA"] = {t: round(m["ILTU_%s" % t] * 1e6, 4) for t, _ in mk}
    # per-phase deltas
    ph = []
    for i in range(len(mk) - 1):
        (t1, v1), (t2, v2) = mk[i], mk[i + 1]
        d = {n: fC(series[n][t2] - series[n][t1]) for n in names if not n.startswith("e")}
        resid = d["qhs"] - (d["qfw"] + d["qind"] + d["qcna"] + d["qgtu"] + d["qgfw"])
        ph.append(dict(phase="%s->%s" % (t1, t2), t_ps=[v1, v2],
                       dt_ps=round(v2 - v1, 4),
                       q_supply_fC=round(d["qsup"], 4),
                       q_HSleg_fC=round(d["qhs"], 4),
                       q_to_ground_via_FW_fC=round(d["qfw"], 4),
                       q_into_inductor_fC=round(d["qind"], 4),
                       q_into_CNA_fC=round(d["qcna"], 4),
                       q_gate_HS_fC=round(d["qgtu"], 4),
                       q_gate_FW_fC=round(d["qgfw"], 4),
                       q_into_bank_fC=round(d["qbk"], 4),
                       KCL_residual_fC=round(resid, 5)))
    res["phases"] = ph
    tot = {n: fC(series[n][mk[-1][0]] - series[n][mk[0][0]]) for n in names
           if not n.startswith("e")}
    etot = {n: (series[n][mk[-1][0]] - series[n][mk[0][0]]) * 1e15 for n in names
            if n.startswith("e")}
    resid = tot["qhs"] - (tot["qfw"] + tot["qind"] + tot["qcna"] + tot["qgtu"] + tot["qgfw"])
    res["TOTAL_fC"] = {k: round(v, 4) for k, v in tot.items()}
    res["TOTAL_fJ"] = {k: round(v, 5) for k, v in etot.items()}
    res["LEDGER"] = dict(
        q_supply_fC=round(tot["qsup"], 4),
        q_HSleg_fC=round(tot["qhs"], 4),
        sinks=dict(to_ground_via_freewheel_fC=round(tot["qfw"], 4),
                   into_inductor_fC=round(tot["qind"], 4),
                   into_switch_node_CNA_fC=round(tot["qcna"], 4),
                   HS_gate_overlap_fC=round(tot["qgtu"], 4),
                   FW_gate_overlap_fC=round(tot["qgfw"], 4)),
        KCL_residual_fC=round(resid, 5),
        KCL_residual_pct_of_supply=(round(100 * resid / tot["qsup"], 5)
                                    if abs(tot["qsup"]) > 1e-6 else None),
        q_into_bank_fC=round(tot["qbk"], 4),
        Qdel_over_Qsup=(round(tot["qbk"] / tot["qsup"], 5)
                        if abs(tot["qsup"]) > 1e-6 else None),
        E_supply_fJ=round(etot["esup"], 5),
        E_into_bank_fJ=round(etot["ebk"], 5),
        eta_energy=(round(etot["ebk"] / etot["esup"], 5)
                    if abs(etot["esup"]) > 1e-9 else None),
        E_burned_in_FW_leg_fJ=round(etot["efw"], 5),
        E_I2R_inductor_fJ=round(etot["erl"], 5))
    res["rail_rise_mV"] = round(1e3 * (m["VRAIL_%s" % mk[-1][0]] - m["VRAIL_Z"]), 4)
    res["rail_rise_from_C_bank_fC"] = round(cb * (m["VRAIL_%s" % mk[-1][0]]
                                                  - m["VRAIL_Z"]), 4)
    return res, msg


def crossconduction(s, cb, tstop=460.0, tag="run"):
    """(d) THE SIMULTANEOUS HS/FW CONDUCTION TEST.  Reads the raw .prn and
    reports, sample by sample, where BOTH devices carry current at once."""
    p = os.path.join(HERE, "R_%s_%s.cir" % (s["name"], tag))
    hdr, rows = B.prn(p)
    it = B.col(hdr, "TIME")
    ih = B.col(hdr, "I(VMSUP)")     # + = out of the supply into the HS
    ifw = B.col(hdr, "I(VMFW)")     # + = out of the FW source into ground
    il = B.col(hdr, "I(LTU)")
    ign = B.col(hdr, "V(gtu)")
    igf = B.col(hdr, "V(gfw)")
    THR = 1e-6                      # 1 uA -- "conducting"
    win, qboth, prev = [], 0.0, None
    peak = dict(i=0.0, t=None)
    for r in rows:
        both = (r[ih] > THR and r[ifw] > THR)
        if both:
            win.append(r[it] * 1e12)
            i_st = min(r[ih], r[ifw])
            if i_st > peak["i"]:
                peak = dict(i=i_st, t=r[it] * 1e12)
            if prev is not None:
                qboth += 0.5 * (min(r[ih], r[ifw]) + min(prev[ih], prev[ifw])) \
                         * (r[it] - prev[it])
        prev = r
    # contiguous windows
    runs = []
    if win:
        st = win[0]; last = win[0]
        for t in win[1:]:
            if t - last > 0.5:
                runs.append((st, last)); st = t
            last = t
        runs.append((st, last))
    # the DIRECT shoot-through current = the part of I(HS) that goes straight to
    # ground, i.e. min(I_HS, I_FW) while both conduct, integrated.
    return dict(threshold_uA=THR * 1e6,
                windows_ps=[[round(a, 4), round(b, 4)] for a, b in runs],
                total_both_on_ps=round(sum(b - a for a, b in runs), 4),
                peak_shootthrough_uA=round(peak["i"] * 1e6, 4),
                peak_at_ps=(round(peak["t"], 4) if peak["t"] else None),
                Q_shootthrough_fC=round(qboth * 1e15, 4))


def trace(s, tag, t0, t1, step=0.4):
    """Sampled I(HS)/I(FW)/I(L) across a window -- the evidence table."""
    p = os.path.join(HERE, "R_%s_%s.cir" % (s["name"], tag))
    hdr, rows = B.prn(p)
    it, ih = B.col(hdr, "TIME"), B.col(hdr, "I(VMSUP)")
    ifw, il = B.col(hdr, "I(VMFW)"), B.col(hdr, "I(LTU)")
    ina, ig, igf = B.col(hdr, "V(na)"), B.col(hdr, "V(gtu)"), B.col(hdr, "V(gfw)")
    out, nxt = [], t0
    for r in rows:
        t = r[it] * 1e12
        if t + 1e-9 >= nxt and t <= t1:
            out.append(dict(t_ps=round(t, 4),
                            V_gtu=round(r[ig], 4), V_gfw=round(r[igf], 4),
                            I_HS_uA=round(r[ih] * 1e6, 3),
                            I_FW_uA=round(r[ifw] * 1e6, 3),
                            I_L_uA=round(r[il] * 1e6, 3),
                            V_na=round(r[ina], 5)))
            nxt += step
    return out
