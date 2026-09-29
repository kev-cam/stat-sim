#!/usr/bin/env python3
"""SKEPTIC extraction: independent of qal/skip4/extract.py and of the .mt0
.measure lines.  Everything below is read out of the raw .prn by linear
interpolation in time.  Only the SCHEDULE (beat closes, hop zeros, boundaries)
is taken from skip.py, because that is the deck's own definition of time and it
is verified separately by reading the emitted PWL sources.
"""
import json, math, os, sys
from skip import MGATE, SCHED, EDGE, T1, is_hi, schedule

VTN = 0.5239      # MEASURED (inherited)
VTP = 0.4403      # MEASURED (inherited)
CLIFF = 0.60
BUDGET = 120.0
VB_REF = {1.0: 0.6758936, 1.2: 0.7138163, 1.5: None}


def load(path):
    hdr, T, cols = None, [], None
    for ln in open(path):
        p = ln.split()
        if hdr is None:
            if p and p[0].lower() == "index":
                hdr = [h.upper() for h in p]
                cols = [[] for _ in hdr]
            continue
        if not p or p[0].lower().startswith("end"):
            continue
        try:
            v = [float(x) for x in p]
        except ValueError:
            continue
        if len(v) != len(hdr):
            continue
        for i, x in enumerate(v):
            cols[i].append(x)
    t = [x * 1e12 for x in cols[hdr.index("TIME")]]
    return {"t": t, "c": {h: cols[i] for i, h in enumerate(hdr)}}


def iv(d, col, tt):
    """linear interpolation of column col at time tt (ps)."""
    t, y = d["t"], d["c"][col]
    if tt <= t[0]:
        return y[0]
    if tt >= t[-1]:
        return y[-1]
    lo, hi = 0, len(t) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if t[mid] <= tt:
            lo = mid
        else:
            hi = mid
    if t[hi] == t[lo]:
        return y[lo]
    f = (tt - t[lo]) / (t[hi] - t[lo])
    return y[lo] + f * (y[hi] - y[lo])


def win(d, col, ta, tb):
    t, y = d["t"], d["c"][col]
    return [(t[i], y[i]) for i in range(len(t)) if ta <= t[i] <= tb]


def zero_after_peak(d, col, t_close):
    t, y = d["t"], d["c"][col]
    pk, ipk = 0.0, None
    for i in range(len(t)):
        if t[i] < t_close:
            continue
        if abs(y[i]) > abs(pk):
            pk, ipk = y[i], i
    if ipk is None:
        return None, None, None
    for i in range(ipk + 1, len(t)):
        if y[i] == 0.0 or (y[i - 1] > 0) != (y[i] > 0):
            t0, v0, t1, v1 = t[i - 1], y[i - 1], t[i], y[i]
            tz = t0 if v1 == v0 else t0 + (-v0) * (t1 - t0) / (v1 - v0)
            return tz, pk, t[ipk]
    return None, pk, t[ipk]


def rail_life(d, k, S):
    """MEASURED rail life of bank k: from the first time V(rail k) crosses 0.05 V
    upward to the last time it is above 0.05 V (a 5%-of-1.2 V threshold, stated).
    Also the schedule's own answer (c_k .. d_k) for comparison."""
    col = "V(RAIL%d)" % k
    t, y = d["t"], d["c"][col]
    up = next((t[i] for i in range(len(t)) if y[i] >= 0.05), None)
    dn = next((t[i] for i in range(len(t) - 1, -1, -1) if y[i] >= 0.05), None)
    sched = None
    if k in S["c"] and k in S["d"]:
        sched = S["d"][k] - S["c"][k]
    return dict(thresh_up_ps=up, thresh_down_ps=dn,
                measured_life_ps=(dn - up) if (up is not None and dn is not None) else None,
                measured_life_beats=((dn - up) / S["T"]) if (up is not None and dn is not None) else None,
                schedule_life_ps=sched,
                schedule_life_beats=(sched / S["T"]) if sched else None)


def per_gate(d, k, tt):
    """per-gate settling at instant tt, with rail_k taken at the SAME instant."""
    rail = iv(d, "V(RAIL%d)" % k, tt)
    out = {}
    for i in range(MGATE):
        v = iv(d, "V(O%d_%d)" % (k, i), tt)
        pct = 100.0 * ((1.0 - v / rail) if is_hi(k, i) else (v / rail))
        ok = (v <= 0.10 * rail) if is_hi(k, i) else (v >= 0.50 * rail)
        out["o%d_%d" % (k, i)] = dict(V=v, pct=pct, kind="pull-down" if is_hi(k, i) else "pull-up",
                                      guard=ok)
    up = [o["pct"] for o in out.values() if o["kind"] == "pull-up"]
    dn = [o["pct"] for o in out.values() if o["kind"] == "pull-down"]
    return dict(t_ps=tt, rail_V=rail, gates=out,
                pullup_min=min(up), pullup_max=max(up),
                pulldown_min=min(dn), pulldown_max=max(dn),
                worst=min(min(up), min(dn)),
                limiting="pull-down" if min(dn) < min(up) else "pull-up",
                guard_all=all(o["guard"] for o in out.values()))


def extract(scheme, T, dv, tz, path):
    d = load(path + ".prn")
    S = schedule(scheme, T, dv, tz)
    nb, hops = S["nbank"], S["hops"]
    nh = len(hops)
    r = dict(scheme=scheme, T_ps=T, dv=dv, tz_ps=tz, nbank=nb, hops=hops,
             close_ps=S["close"], open_ps=S["open"], bound_ps=S["bound"],
             tend_ps=S["tend"], prn=os.path.basename(path) + ".prn",
             n_prn_rows=len(d["t"]), t_last_ps=d["t"][-1])

    # ---- C6 instrument, from the raw waveform
    inst = {}
    for h in range(1, nh + 1):
        tzm, pk, tpk = zero_after_peak(d, "I(L%d)" % h, S["close"][h - 1])
        inst[h] = dict(deck_open_ps=S["open"][h - 1],
                       deck_tz_rel_ps=S["open"][h - 1] - S["close"][h - 1],
                       measured_zero_ps=tzm,
                       measured_tz_rel_ps=(tzm - S["close"][h - 1]) if tzm else None,
                       I_at_deck_open_uA=iv(d, "I(L%d)" % h, S["open"][h - 1]) * 1e6,
                       I_peak_uA=pk * 1e6, t_peak_ps=tpk,
                       conduction_window_ps=[S["close"][h - 1], S["open"][h - 1]],
                       conduction_len_ps=S["open"][h - 1] - S["close"][h - 1])
    r["instrument_per_hop"] = inst
    r["C6_IZ_max_uA"] = max(abs(v["I_at_deck_open_uA"]) for v in inst.values())
    r["C6_IZ_PASS"] = r["C6_IZ_max_uA"] <= 1.0

    # ---- C1/C4 per-gate settling at every bank's own boundary
    sett = {k: per_gate(d, k, S["bound"][k]) for k in range(1, nb + 1)}
    r["settling_at_own_boundary"] = sett
    r["worst_gate_all_stages_pct"] = min(sett[k]["worst"] for k in range(1, nb + 1))
    hopc = sorted(S["c"].keys())
    r["hop_charged_banks"] = hopc
    r["worst_gate_hop_charged_pct"] = min(sett[k]["worst"] for k in hopc)
    r["A1_90_all"] = all(sett[k]["worst"] >= 90.0 for k in range(1, nb + 1))
    r["A1_75_all"] = all(sett[k]["worst"] >= 75.0 for k in range(1, nb + 1))
    r["A1_50_all"] = all(sett[k]["worst"] >= 50.0 for k in range(1, nb + 1))
    r["A2_guard_all"] = all(sett[k]["guard_all"] for k in range(1, nb + 1))
    r["PASS_90"] = bool(r["A1_90_all"] and r["A2_guard_all"])

    # ---- E4 bias check: re-score with the COMMON boundary c_k + T (heads: d_k)
    alt = {}
    for k in range(1, nb + 1):
        b = (S["c"][k] + T) if k in S["c"] else S["d"][k]
        alt[k] = per_gate(d, k, b)
    r["settling_at_common_boundary_ckplusT"] = {
        k: dict(t_ps=alt[k]["t_ps"], rail_V=alt[k]["rail_V"], worst=alt[k]["worst"],
                pullup_min=alt[k]["pullup_min"], pulldown_min=alt[k]["pulldown_min"])
        for k in alt}
    r["worst_gate_common_boundary_pct"] = min(alt[k]["worst"] for k in range(1, nb + 1))

    # ---- C2 overlap: rail life and interval geometry
    r["rail_life"] = {k: rail_life(d, k, S) for k in range(1, nb + 1)}
    ov = {}
    for h in range(1, nh + 1):
        s, t = hops[h - 1]
        hop_iv = [S["close"][h - 1], S["open"][h - 1]]
        # every OTHER bank's evaluation interval [its charge close, its boundary]
        others = {}
        for k in range(1, nb + 1):
            if k == t:
                continue
            ev = [S["c"][k] if k in S["c"] else 0.0, S["bound"][k]]
            lo, hi = max(hop_iv[0], ev[0]), min(hop_iv[1], ev[1])
            others[k] = dict(eval_window_ps=ev, overlap_ps=max(0.0, hi - lo),
                             overlap_frac_of_hop=max(0.0, hi - lo) /
                             (hop_iv[1] - hop_iv[0]))
        data_src = t - 1
        ov[h] = dict(src=s, dst=t, hop_conduction_ps=hop_iv,
                     data_source_bank=data_src,
                     data_source_is_draining_bank=(data_src == s),
                     other_bank_eval_overlap=others)
    r["overlap_intervals"] = ov

    # ---- C3 hold: full window trace of a bank that is charged then drained
    hold = {}
    for k in range(1, nb + 1):
        if k not in S["d"]:
            continue
        ta = S["open"][[h for h, (s, t) in enumerate(hops, 1) if t == k][0] - 1] \
            if k in S["c"] else 0.0
        tb = S["d"][k] - EDGE
        tr = win(d, "V(RAIL%d)" % k, ta, tb)
        if not tr:
            continue
        v0, v1 = iv(d, "V(RAIL%d)" % k, ta), iv(d, "V(RAIL%d)" % k, tb)
        vmin = min(v for _, v in tr); vmax = max(v for _, v in tr)
        # this bank's HIGH outputs (pull-UP cells) over the same window
        ho = {}
        for i in range(MGATE):
            if is_hi(k, i):
                continue
            a0, a1 = iv(d, "V(O%d_%d)" % (k, i), ta), iv(d, "V(O%d_%d)" % (k, i), tb)
            ho["o%d_%d" % (k, i)] = dict(at_start_V=a0, at_end_V=a1,
                                         change_mV=1000.0 * (a1 - a0))
        lo = {}
        for i in range(MGATE):
            if not is_hi(k, i):
                continue
            a0, a1 = iv(d, "V(O%d_%d)" % (k, i), ta), iv(d, "V(O%d_%d)" % (k, i), tb)
            lo["o%d_%d" % (k, i)] = dict(at_start_V=a0, at_end_V=a1,
                                         creep_mV=1000.0 * (a1 - a0))
        # THE SKEPTIC'S ADDITION: does the bank this one FEEDS still settle at the
        # END of the hold window, not only at its own boundary?
        fed = k + 1
        fed_end = per_gate(d, fed, tb) if fed <= nb else None
        hold[k] = dict(window_ps=[ta, tb], window_len_ps=tb - ta,
                       beats_held=(tb - ta) / T,
                       rail_start_V=v0, rail_end_V=v1, rail_min_V=vmin, rail_max_V=vmax,
                       droop_mV=1000.0 * (v1 - v0),
                       droop_pct=100.0 * (v1 / v0 - 1.0) if v0 else None,
                       max_excursion_below_start_mV=1000.0 * (vmin - v0),
                       above_cliff_whole_window=vmin >= CLIFF,
                       high_outputs=ho, low_outputs=lo,
                       fed_bank=fed if fed <= nb else None,
                       fed_bank_settling_at_hold_END=(
                           dict(t_ps=fed_end["t_ps"], rail_V=fed_end["rail_V"],
                                worst=fed_end["worst"], pullup_min=fed_end["pullup_min"],
                                pulldown_min=fed_end["pulldown_min"],
                                limiting=fed_end["limiting"],
                                guard_all=fed_end["guard_all"]) if fed_end else None),
                       fed_bank_settling_at_own_boundary=(
                           dict(t_ps=sett[fed]["t_ps"], worst=sett[fed]["worst"],
                                pullup_min=sett[fed]["pullup_min"],
                                pulldown_min=sett[fed]["pulldown_min"])
                           if fed <= nb else None))
    r["hold_test"] = hold

    # ---- C5 drain-vs-hold, both schemes: the successor's INPUT drive over its
    # own evaluation window
    dvh = {}
    for h in range(1, nh + 1):
        s, t = hops[h - 1]
        src_data = t - 1
        ta, tb = S["close"][h - 1], S["bound"][t]
        pdg, pug = {}, {}
        for i in range(MGATE):
            net = "V(O%d_%d)" % (src_data, i)
            if net not in d["c"]:
                continue
            v0, v1 = iv(d, net, ta), iv(d, net, tb)
            tr = win(d, net, ta, tb)
            rec = dict(at_beat_close_V=v0, at_boundary_V=v1,
                       min_V=min(v for _, v in tr), max_V=max(v for _, v in tr),
                       change_mV=1000.0 * (v1 - v0))
            if is_hi(t, i):
                rec["collapse_pct"] = 100.0 * (v1 / v0 - 1.0) if v0 else None
                pdg["o%d_%d" % (src_data, i)] = rec
            else:
                pug["o%d_%d" % (src_data, i)] = rec
        railt = iv(d, "V(RAIL%d)" % t, tb)
        pd_min = min(v["at_boundary_V"] for v in pdg.values()) if pdg else None
        pu_max = max(v["at_boundary_V"] for v in pug.values()) if pug else None
        dvh[h] = dict(src=s, dst=t, data_source_bank=src_data,
                      data_source_is_draining_bank=(src_data == s),
                      window_ps=[ta, tb],
                      data_source_rail_at_beat_close_V=iv(d, "V(RAIL%d)" % src_data, ta)
                      if src_data >= 1 else None,
                      data_source_rail_at_boundary_V=iv(d, "V(RAIL%d)" % src_data, tb)
                      if src_data >= 1 else None,
                      draining_bank_rail_at_boundary_V=iv(d, "V(RAIL%d)" % s, tb),
                      pulldown_gate_HIGH_inputs=pdg, pullup_gate_LOW_inputs=pug,
                      dst_rail_at_boundary_V=railt,
                      pulldown_gate_min_V=pd_min,
                      pulldown_overdrive_V=(pd_min - VTN) if pd_min is not None else None,
                      pullup_gate_max_V=pu_max,
                      pullup_overdrive_V=(railt - pu_max - VTP) if pu_max is not None else None,
                      dst_pulldown_min_pct=sett[t]["pulldown_min"],
                      dst_pullup_min_pct=sett[t]["pullup_min"],
                      dst_limiting=sett[t]["limiting"])
    r["drain_vs_hold"] = dvh

    # ---- A5 margin budget
    hr = [sett[k]["rail_V"] for k in hopc]
    ref = VB_REF.get(dv) or VB_REF[1.2]
    r["margin"] = dict(ref_delivered_rail_V=ref,
                       cumulative_mV=1000.0 * (ref - min(hr)),
                       compounding_mV=1000.0 * (max(hr) - min(hr)),
                       pct_of_120mV=100.0 * (1000.0 * (ref - min(hr))) / BUDGET,
                       min_hop_charged_rail_V=min(hr),
                       cliff_PASS=min(hr) >= CLIFF,
                       banks_below_cliff=[k for k in hopc if sett[k]["rail_V"] < CLIFF])

    # ---- eventual settle: the deepest bank 500 ps after its beat
    kdeep = nb
    tD = S["tend"] - 5.0
    r["deepest_bank_at_end_of_tail"] = dict(
        t_ps=tD, **{kk: vv for kk, vv in per_gate(d, kdeep, tD).items()
                    if kk in ("rail_V", "worst", "pullup_min", "pulldown_min",
                              "limiting", "guard_all")})
    return r


if __name__ == "__main__":
    tzall = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "tz.json")))
    out = {}
    for tag, tz in sorted(tzall.items()):
        scheme = tag.split("_")[0]
        T = float(tag.split("_T")[1].split("_")[0])
        dv = float(tag.split("_dv")[1]) / 1000.0
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "c_%s_free_T%g_dv%g.cir" % (scheme, T, dv * 1000))
        if not os.path.exists(path + ".prn"):
            out[tag] = {"ERROR": "no prn"}; continue
        try:
            out[tag] = extract(scheme, T, dv, tz, path)
            print("ok", tag, "worst=%.2f%%" % out[tag]["worst_gate_all_stages_pct"],
                  flush=True)
        except Exception as e:
            out[tag] = {"ERROR": repr(e)}
            print("ERR", tag, repr(e), flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "VERIFY.json"), "w"), indent=1)
