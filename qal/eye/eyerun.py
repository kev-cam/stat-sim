#!/usr/bin/env python3
"""Aggregate the per-pattern transients into THE EYE -- per bank, both
polarities, as the INTERSECTION over data patterns.  Writes EYE.json and the
margin-vs-time curves Phase 2 needs (MARGIN_bank{k}.csv.gz).

Two decision references, both from the SAME single transient per pattern:

  EYE1  RX_INSTANTANEOUS  -- PRE_REGISTERED.json STEP_d verbatim: the receiver's
        MEASURED trip at the receiver's INSTANTANEOUS rail, in-table only.  What
        a receiver actually has to tolerate.  Its early edge is the RECEIVER'S
        POWER-UP (AMENDMENT E3).
  EYE2  DATA_FIXED       -- AMENDMENT E3: the same machinery against a FIXED
        level per link, Trip_S(VR{k+1}B).  Isolates the DRIVER.  This is the one
        that bounds the beat, and the one Phase 2 needs.

Two windows, because AMENDMENT E4 found the pre-registered window END was
masquerading as a closing edge:

  W_PREREG    [c_k, ro_k]     as pre-registered
  W_EXTENDED  [c_k, tend-1]   the whole live span of the transient
"""
import glob, gzip, json, math, os, sys
from array import array
import eyeharness as EH
import eyecalc as EC

HERE = EH.HERE
GRID = EC.GRID
SIG = EC.SIG_TRIP_MV
THRESH = [("0mV", 0.0), ("1sigma_6.441mV", SIG), ("3sigma_19.323mV", 3 * SIG)]


def a6_of(pname):
    sub = os.path.join(HERE, pname)
    mt0 = glob.glob(os.path.join(sub, "c_*.mt0"))
    if not mt0:
        return dict(A6_zcs_pass=None, worst_abs_uA=None, note="no .mt0")
    d = EH.bt.parse_mt0(mt0[0])
    iz = {str(k): d.get("IZ%d" % k, float("nan")) * 1e6 for k in range(1, 5)}
    izq = {str(k): d.get("IZQ%d" % k, float("nan")) * 1e6 for k in range(1, 5)}
    worst = max(max(abs(v) for v in iz.values()), max(abs(v) for v in izq.values()))
    return dict(IZ_uA={k: round(v, 6) for k, v in iz.items()},
                IZQ_uA={k: round(v, 6) for k, v in izq.items()},
                worst_abs_uA=round(worst, 6),
                A6_zcs_pass=bool(worst <= 1.0))


def rnd(e):
    if e is None:
        return None
    return {k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in e.items() if not k.startswith("i_")}


def main(patterns):
    Ps, a6 = {}, {}
    for p in patterns:
        if not os.path.exists(os.path.join(HERE, p, "sched.json")):
            print("  SKIP %s (no sched.json -- did not run)" % p)
            continue
        a6[p] = a6_of(p)
        Ps[p] = EC.per_pattern(p)
        print("  loaded %s bits=%s  %d solver pts, dt_max %.4f ps, A6 %s (worst %s uA)"
              % (p, Ps[p]["bits"], Ps[p]["meta"]["n_solver_points"],
                 Ps[p]["meta"]["solver_dt_max_ps"], a6[p]["A6_zcs_pass"],
                 a6[p]["worst_abs_uA"]), flush=True)
    patterns = [p for p in patterns if p in Ps]
    if not patterns:
        print("NO PATTERNS RAN")
        return 1

    good = [p for p in patterns if a6[p]["A6_zcs_pass"]]
    bad = [p for p in patterns if not a6[p]["A6_zcs_pass"]]
    nb, mg = EH.bt.NBANK, EH.bt.MGATE
    n = min(len(Ps[p]["grid"]) for p in patterns)
    g = Ps[patterns[0]]["grid"][:n]

    out = dict(
        _what="THE EYE of a per-bank-tank QAL wave: a WIDTH in ps and a HEIGHT in mV. "
              "A bank output is not a node approaching an asymptote; it becomes valid, "
              "stays valid for a window, and stops being valid. There is no completion event.",
        _grid_ps=GRID,
        _edge_location="sub-grid LINEAR INTERPOLATION of the root of margin(t)=threshold "
                       "(AMENDMENT E1); grid-quantised edges given alongside",
        _operating_point=dict(m=10.0, T_ps=200.0, H=4, dv_V=1.65, mode="free", L_nH=15.0,
                              nbank=nb, ngate_per_bank=mg,
                              arrangement="qal/banktank 0aae11e per-bank tanks, "
                                          "no flop/latch/buffer/keeper between banks"),
        _receiver_threshold="MEASURED qal/fcrit/TRIP.json cell S (wp 1.12u/wn 0.74u, identical "
                            "widths AND bulk connections to every banktank cell), 27 rails "
                            "0.20-1.50 V at 1 mV DC step, LINEARLY INTERPOLATED at the "
                            "receiver's rail. The trip FRACTION is not a constant: MEASURED "
                            "0.728124 at 0.20 V -> 0.517850 at 1.50 V. 0.59 is never used.",
        _references=dict(
            EYE1_RX_INSTANTANEOUS="PRE_REGISTERED STEP_d verbatim. Trip at the receiver's "
                                  "INSTANTANEOUS rail, in-table only. Early edge is the "
                                  "RECEIVER'S POWER-UP (AMENDMENT E3), not the data.",
            EYE2_DATA_FIXED="AMENDMENT E3. Fixed level Trip_S(VR{k+1}B), the receiver's trip "
                            "at the receiver's rail at ITS OWN pre-registered boundary instant "
                            "(a committed banktank .measure key, MEASURED per pattern). "
                            "Isolates the DRIVER. THIS is the one that bounds the beat."),
        _windows=dict(W_PREREG="[c_k, ro_k] as pre-registered",
                      W_EXTENDED="[c_k, tend-1] -- AMENDMENT E4, because the pre-registered "
                                 "window END was masquerading as a closing edge"),
        _patterns={p: dict(bits=Ps[p]["bits"], weight=sum(Ps[p]["bits"]),
                           probe_protocol=json.load(
                               open(os.path.join(HERE, p, "zeros.json")))
                           .get("probe_protocol", "?"), **a6[p]) for p in patterns},
        _patterns_in_intersection=good,
        _patterns_excluded_A6_instrument_failure=bad,
        _n_patterns_in_intersection=len(good),
        banks={})

    if not good:
        out["VERDICT"] = ("INSTRUMENT FAILURE: no pattern passed the A6 ZCS gate "
                          "(pre-declared failure handling F1)")
        open(os.path.join(HERE, "EYE.json"), "w").write(json.dumps(out, indent=1))
        print(out["VERDICT"])
        return 1

    for k in range(1, nb + 1):
        ck = max(Ps[p]["c"][k] for p in good)
        rk = max(Ps[p]["r"][k] for p in good)
        rok = min(Ps[p]["ro"][k] for p in good)
        tendw = g[n - 1] - 1.0
        rec = dict(
            receiver=("bank %d (MEASURED)" % (k + 1)) if k < nb else
                     ("DERIVED: receiver rail = V(rail%d)(t - T) and the fixed data level "
                      "uses VR%dB; there is no bank %d in a %d-bank deck"
                      % (nb - 1, nb, nb + 1, nb)),
            receiver_is_measured=(k < nb),
            own_rail_start_c_ps=ck,
            transfer_open_o_ps=max(Ps[p]["o"][k] for p in good),
            return_close_r_ps=rk, return_open_ro_ps=rok,
            windows_ps=dict(W_PREREG=[ck, rok], W_EXTENDED=[ck, tendw]),
            decision_levels={p: {kk: (round(vv, 7) if isinstance(vv, float) else vv)
                                 for kk, vv in Ps[p]["tripspan"][k].items()}
                             for p in good})

        allg = list(range(mg))
        rec["gates_expected_HIGH_by_pattern"] = {
            p: [i for i in allg if Ps[p]["hi"][k][i]] for p in good}
        # P1 (all-zero) and P2 (all-one) give a bank EIGHT gates of ONE polarity,
        # so they contribute to only one of the two polarity eyes.  Recorded
        # explicitly so a per-polarity intersection cannot be misread as being
        # over all patterns.
        rec["patterns_contributing_to_polarity_eye"] = dict(
            HIGH=[p for p in good if any(Ps[p]["hi"][k][i] for i in allg)],
            LOW=[p for p in good if any(not Ps[p]["hi"][k][i] for i in allg)])

        # ---------- per-pattern min-over-gates curves, per reference
        cur = {}
        for ref, key in (("EYE1_RX_INSTANTANEOUS", "mgn"),
                         ("EYE2_DATA_FIXED", "mgn_data")):
            cur[ref] = {}
            for p in good:
                P = Ps[p]
                hiP = [i for i in allg if P["hi"][k][i]]
                loP = [i for i in allg if not P["hi"][k][i]]
                M = P[key][k]
                cur[ref][p] = dict(
                    all=array("d", (min(M[i][a] for i in allg) for a in range(n))),
                    HIGH=(array("d", (min(M[i][a] for i in hiP) for a in range(n)))
                          if hiP else None),
                    LOW=(array("d", (min(M[i][a] for i in loP) for a in range(n)))
                         if loP else None))
            cur[ref]["_INTER"] = {}
            for nm in ("all", "HIGH", "LOW"):
                cs = [cur[ref][p][nm] for p in good if cur[ref][p][nm] is not None]
                cur[ref]["_INTER"][nm] = (
                    array("d", (min(c[a] for c in cs) for a in range(n))) if cs else None)
        intab_i = bytearray(1 if all(Ps[p]["intab"][k][a] for p in good) else 0
                            for a in range(n))

        # ---------- the eyes
        rec["EYES"] = {}
        for ref in ("EYE1_RX_INSTANTANEOUS", "EYE2_DATA_FIXED"):
            use_tab = (ref == "EYE1_RX_INSTANTANEOUS")
            R = {}
            for wname, wlo, whi in (("W_PREREG", ck, rok),
                                    ("W_EXTENDED", ck, tendw)):
                W = {}
                for tname, tv in THRESH:
                    c0 = cur[ref]["_INTER"]["all"]
                    m = [c0[a] > tv and (intab_i[a] if use_tab else 1) for a in range(n)]
                    e = EC.eye_from_mask(m, g, wlo, whi, c0, tv)
                    if e is None:
                        W[tname] = dict(EYE="EMPTY")
                        continue
                    ctr = 0.5 * (e["open_ps"] + e["close_ps"])
                    ia = max(0, min(n - 1, int(round(ctr / GRID))))
                    hh = cur[ref]["_INTER"]["HIGH"]
                    hl = cur[ref]["_INTER"]["LOW"]
                    hhv = hh[ia] if hh is not None else None
                    hlv = hl[ia] if hl is not None else None
                    both = [x for x in (hhv, hlv) if x is not None]
                    W[tname] = dict(
                        opening_ps=round(e["open_ps"], 4),
                        closing_ps=round(e["close_ps"], 4),
                        WIDTH_ps=round(e["width_ps"], 4),
                        opening_ps_gridquant=round(e["open_ps_gridquant"], 4),
                        closing_ps_gridquant=round(e["close_ps_gridquant"], 4),
                        centre_ps=round(ctr, 4),
                        HEIGHT_at_centre_HIGH_mV=(round(hhv, 4) if hhv is not None else None),
                        HEIGHT_at_centre_LOW_mV=(round(hlv, 4) if hlv is not None else None),
                        HEIGHT_at_centre_mV=(round(2.0 * min(both), 4) if both else None),
                        opening_minus_own_rail_start_ps=round(e["open_ps"] - ck, 4),
                        closing_minus_return_close_ps=round(e["close_ps"] - rk, 4),
                        clipped_at_window_start=e["clipped_at_window_start"],
                        clipped_at_window_end=e["clipped_at_window_end"],
                        WIDTH_IS_A_LOWER_BOUND=bool(e["clipped_at_window_end"]),
                        width_bound_reason=(
                            "the margin had NOT crossed the threshold by the window end -- "
                            "the eye does not close here; see AMENDMENT E4"
                            if e["clipped_at_window_end"] else None))
                # OPERATIONAL: the FIRST contiguous open interval, which is what
                # a receiver actually gets.  At a 3-sigma threshold the margin can
                # dip below the bar at the post-return trough and SPLIT the eye, in
                # which case the pre-registered "largest run" rule reports the
                # LATER fragment -- useless for sampling.  Both are reported.
                WF = {}
                for tname, tv in THRESH:
                    c0 = cur[ref]["_INTER"]["all"]
                    m = [c0[a] > tv and (intab_i[a] if use_tab else 1) for a in range(n)]
                    e = EC.eye_from_mask(m, g, wlo, whi, c0, tv, pick="first")
                    if e is None:
                        WF[tname] = dict(EYE="EMPTY")
                        continue
                    WF[tname] = dict(
                        opening_ps=round(e["open_ps"], 4),
                        closing_ps=round(e["close_ps"], 4),
                        WIDTH_ps=round(e["width_ps"], 4),
                        opening_minus_own_rail_start_ps=round(e["open_ps"] - ck, 4),
                        closing_minus_return_close_ps=round(e["close_ps"] - rk, 4),
                        clipped_at_window_start=e["clipped_at_window_start"],
                        clipped_at_window_end=e["clipped_at_window_end"],
                        WIDTH_IS_A_LOWER_BOUND=bool(e["clipped_at_window_end"]),
                        eye_was_SPLIT_by_the_threshold=bool(
                            not e["clipped_at_window_end"] and e["close_ps"] < whi - 0.5))
                R[wname] = W
                R[wname + "_FIRST_RUN"] = WF
            for nm in ("HIGH", "LOW"):
                cc = cur[ref]["_INTER"][nm]
                if cc is None:
                    R["%s_only_W_EXTENDED_0mV" % nm] = None
                    continue
                m = [cc[a] > 0.0 and (intab_i[a] if use_tab else 1) for a in range(n)]
                R["%s_only_W_EXTENDED_0mV" % nm] = rnd(
                    EC.eye_from_mask(m, g, ck, tendw, cc, 0.0))
            R["per_pattern_W_EXTENDED_0mV"] = {}
            for p in good:
                cc = cur[ref][p]["all"]
                m = [cc[a] > 0.0 and (intab_i[a] if use_tab else 1) for a in range(n)]
                pol = {}
                for nm in ("HIGH", "LOW"):
                    c2 = cur[ref][p][nm]
                    if c2 is None:
                        pol[nm] = None
                        continue
                    m2 = [c2[a] > 0.0 and (intab_i[a] if use_tab else 1) for a in range(n)]
                    pol[nm] = rnd(EC.eye_from_mask(m2, g, ck, tendw, c2, 0.0))
                R["per_pattern_W_EXTENDED_0mV"][p] = dict(
                    joint=rnd(EC.eye_from_mask(m, g, ck, tendw, cc, 0.0)),
                    HIGH=pol["HIGH"], LOW=pol["LOW"])
            # the DIRECTLY MEASURED data-dependent jitter of the eye EDGE:
            # the spread of the per-pattern opening across the pattern set.
            # This is the apples-to-apples comparable for the campaign's 61.6 ps
            # figure -- it is NOT claimed to be the same quantity.
            for pol in ("HIGH", "LOW"):
                po = [(p, R["per_pattern_W_EXTENDED_0mV"][p][pol]["open_ps"])
                      for p in good
                      if R["per_pattern_W_EXTENDED_0mV"][p].get(pol) is not None]
                if not po:
                    continue
                vs = [v for _, v in po]
                mu = sum(vs) / len(vs)
                R["DATA_JITTER_%s_polarity" % pol] = dict(
                    n_patterns_with_this_polarity=len(po),
                    patterns=[p for p, _ in po],
                    per_pattern_opening_ps={p: round(v, 4) for p, v in po},
                    per_pattern_opening_minus_c_k_ps={p: round(v - ck, 4) for p, v in po},
                    peak_to_peak_ps=round(max(vs) - min(vs), 4),
                    sigma_ps=round((sum((x - mu) ** 2 for x in vs) / len(vs)) ** 0.5, 4),
                    note="P1 (all-zero) and P2 (all-one) give a bank eight gates of ONE "
                         "polarity, so they appear in only one of these two lists.")
            ops = [R["per_pattern_W_EXTENDED_0mV"][p]["joint"]["open_ps"]
                   for p in good
                   if R["per_pattern_W_EXTENDED_0mV"][p]["joint"] is not None]
            cls = [R["per_pattern_W_EXTENDED_0mV"][p]["joint"]["close_ps"]
                   for p in good
                   if R["per_pattern_W_EXTENDED_0mV"][p]["joint"] is not None]
            if ops:
                mu = sum(ops) / len(ops)
                sd = (sum((x - mu) ** 2 for x in ops) / len(ops)) ** 0.5
                R["DATA_DEPENDENT_EDGE_JITTER"] = dict(
                    n_patterns=len(ops),
                    opening_min_ps=round(min(ops), 4),
                    opening_max_ps=round(max(ops), 4),
                    opening_peak_to_peak_ps=round(max(ops) - min(ops), 4),
                    opening_mean_ps=round(mu, 4),
                    opening_sigma_ps=round(sd, 4),
                    closing_peak_to_peak_ps=round(max(cls) - min(cls), 4),
                    per_pattern_opening_ps={p: round(
                        R["per_pattern_W_EXTENDED_0mV"][p]["joint"]["open_ps"], 4)
                        for p in good
                        if R["per_pattern_W_EXTENDED_0mV"][p]["joint"] is not None},
                    what="PEAK-TO-PEAK spread of this bank's eye OPENING instant across the "
                         "data patterns, measured. This is the data-dependent jitter that "
                         "closes the eye from the early side, and it is what the pattern "
                         "INTERSECTION charges. It is NOT the campaign's 61.6 ps number, "
                         "which is a zero-crossing spread, not an eye-edge spread.")
            rec["EYES"][ref] = R

        # ---------- HEIGHT at instants that MEAN something.
        # The pre-registered "height at the centre" is the centre of the eye,
        # but AMENDMENT E4 showed the eye's right edge is the deck's end, so that
        # centre lands ~1280 ps -- AFTER the return -- and the height there is a
        # deck artifact.  The heights that matter are (i) at the SAMPLING INSTANT
        # (the receiver's own rail start, c_k + T, which is when the receiver
        # begins to evaluate) and (ii) at the centre of the PIPELINED eye
        # [opening, c_k + H*T], the window a real machine would give it.
        Tb = Ps[good[0]]["T"]
        Hb = int(Ps[good[0]].get("H", 4) or 4)
        rec["HEIGHT_at_meaningful_instants"] = {}
        for ref in ("EYE1_RX_INSTANTANEOUS", "EYE2_DATA_FIXED"):
            zf = rec["EYES"][ref]["W_EXTENDED_FIRST_RUN"]["0mV"]
            op = zf.get("opening_ps", ck)
            pts = dict(sampling_instant_receiver_rail_start_ps=ck + Tb,
                       pipelined_eye_centre_ps=0.5 * (op + ck + Hb * Tb),
                       eye_opening_plus_1ps=op + 1.0,
                       return_close_minus_1ps=rk - 1.0)
            H = {}
            for nm, tt in pts.items():
                a = max(0, min(n - 1, int(round(tt / GRID))))
                hh = cur[ref]["_INTER"]["HIGH"]
                hl = cur[ref]["_INTER"]["LOW"]
                hhv = hh[a] if hh is not None else None
                hlv = hl[a] if hl is not None else None
                both = [x for x in (hhv, hlv) if x is not None]
                H[nm] = dict(t_ps=round(tt, 4),
                             HEIGHT_HIGH_mV=(round(hhv, 4) if hhv is not None else None),
                             HEIGHT_LOW_mV=(round(hlv, 4) if hlv is not None else None),
                             HEIGHT_mV=(round(2.0 * min(both), 4) if both else None),
                             min_over_both_polarities_mV=(round(min(both), 4) if both else None),
                             in_eye=bool(cur[ref]["_INTER"]["all"][a] > 0.0))
            rec["HEIGHT_at_meaningful_instants"][ref] = H

        # ---------- the worst post-return margin (E4: where a right edge WOULD be)
        ar = int(round(rk / GRID))
        pr = {}
        for ref in ("EYE1_RX_INSTANTANEOUS", "EYE2_DATA_FIXED"):
            c0 = cur[ref]["_INTER"]["all"]
            mm = min((c0[a], g[a]) for a in range(ar, n))
            pr[ref] = dict(worst_margin_after_return_close_mV=round(mm[0], 4),
                           at_t_ps=round(mm[1], 4),
                           at_t_minus_return_open_ro_ps=round(mm[1] - rok, 4),
                           right_edge_appears_only_for_thresholds_above_mV=round(mm[0], 4))
        # AMENDMENT E4: the margin does not cross zero, but it has a MINIMUM
        # after the return.  That instant is the LATE-EDGE CANDIDATE: the place
        # a right edge appears first as the Phase-2 budget grows.  Its mechanism
        # is the physically meaningful "why too late", so it is attributed here.
        for ref in ("EYE1_RX_INSTANTANEOUS", "EYE2_DATA_FIXED"):
            key = "mgn" if ref == "EYE1_RX_INSTANTANEOUS" else "mgn_data"
            ta = max(1, min(n - 2, int(round(pr[ref]["at_t_ps"] / GRID))))
            bp, bg, bv = None, None, 1e18
            for p2 in good:
                for i in allg:
                    v = Ps[p2][key][k][i][ta]
                    if v < bv:
                        bp, bg, bv = p2, i, v
            pr[ref]["LATE_EDGE_CANDIDATE"] = dict(
                binding_pattern=bp, binding_gate="o%d" % bg,
                binding_polarity=("HIGH" if Ps[bp]["hi"][k][bg] else "LOW"),
                binding_margin_mV=round(bv, 5),
                MECHANISM=EC.mechanism(Ps[bp], k, ta, bg, "late", ref, False))
        rec["POST_RETURN_MARGIN_FLOOR"] = pr

        # ---------- WHY it closes at each edge
        rec["CLOSING_MECHANISM"] = {}
        for ref in ("EYE1_RX_INSTANTANEOUS", "EYE2_DATA_FIXED"):
            z = rec["EYES"][ref]["W_EXTENDED"]["0mV"]
            if "EYE" in z:
                rec["CLOSING_MECHANISM"][ref] = "EYE EMPTY"
                continue
            key = "mgn" if ref == "EYE1_RX_INSTANTANEOUS" else "mgn_data"
            M = {}
            for side, tt, clipped in (("early_edge_OPENING", z["opening_ps"],
                                       z["clipped_at_window_start"]),
                                      ("late_edge_CLOSING", z["closing_ps"],
                                       z["clipped_at_window_end"])):
                a = max(1, min(n - 2, int(round(tt / GRID))))
                bp, bg, bv = None, None, 1e18
                for p in good:
                    for i in allg:
                        v = Ps[p][key][k][i][a]
                        if v < bv:
                            bp, bg, bv = p, i, v
                ent = dict(t_ps=round(tt, 4),
                           binding_pattern=bp, binding_pattern_bits=EH.PATTERNS[bp],
                           binding_gate="o%d" % bg,
                           binding_polarity=("HIGH" if Ps[bp]["hi"][k][bg] else "LOW"),
                           binding_margin_mV=round(bv, 5))
                if clipped:
                    ent["NO_EDGE"] = (
                        "the eye is CLIPPED at this window bound -- there is no crossing "
                        "here. %s" % ("The window starts at the bank's own rail start; the "
                                      "receiver's rail has not yet powered up."
                                      if side.startswith("early") else
                                      "The margin never crosses the threshold within the "
                                      "transient: the true right edge is set by the NEXT "
                                      "datum on this bank at the initiation interval H*T, "
                                      "which this single-shot deck does not contain "
                                      "(AMENDMENT E4)."))
                ent["MECHANISM"] = EC.mechanism(Ps[bp], k, a, bg, side, ref, clipped)
                M[side] = ent
            rec["CLOSING_MECHANISM"][ref] = M

        # ---------- the margin-vs-time curve Phase 2 needs
        fn = os.path.join(HERE, "MARGIN_bank%d.csv.gz" % k)
        with gzip.open(fn, "wt") as f:
            f.write("t_ps,rx_inst_all_mV,rx_inst_HIGH_mV,rx_inst_LOW_mV,in_table,"
                    "data_fixed_all_mV,data_fixed_HIGH_mV,data_fixed_LOW_mV,"
                    "V_rail_driver_min_over_pat,V_rail_rx_min_over_pat,V_trip_rx_min_over_pat\n")
            A = cur["EYE1_RX_INSTANTANEOUS"]["_INTER"]
            B = cur["EYE2_DATA_FIXED"]["_INTER"]
            for a in range(n):
                f.write("%.4f,%.6f,%s,%s,%d,%.6f,%s,%s,%.7f,%.7f,%.7f\n" % (
                    g[a], A["all"][a],
                    ("%.6f" % A["HIGH"][a]) if A["HIGH"] is not None else "",
                    ("%.6f" % A["LOW"][a]) if A["LOW"] is not None else "",
                    intab_i[a], B["all"][a],
                    ("%.6f" % B["HIGH"][a]) if B["HIGH"] is not None else "",
                    ("%.6f" % B["LOW"][a]) if B["LOW"] is not None else "",
                    min(Ps[p]["C"]["V(RAIL%d)" % k][a] for p in good),
                    min(Ps[p]["rx"][k][a] for p in good),
                    min(Ps[p]["trip"][k][a] for p in good)))
        rec["margin_curve_file"] = os.path.basename(fn)
        rec["margin_curve_n_points"] = n
        out["banks"][str(k)] = rec

    # ---------- THE PHASE-2 HANDOFF: slack around the sampling instant.
    # The eye must remain open at the sampling instant AFTER every timing
    # uncertainty is charged.  Phase 1 owes Phase 2 the SLACK, measured.
    T = Ps[good[0]]["T"]
    H = int(Ps[good[0]].get("H", 4) or 4)
    II = H * T
    JIT = 61.6          # MEASURED data-dependent zero spread, ps (worst-case data)
    hand = {}
    for k in range(1, nb + 1):
        B = out["banks"][str(k)]
        z = B["EYES"]["EYE2_DATA_FIXED"]["W_EXTENDED"]["0mV"]
        if "EYE" in z:
            hand[str(k)] = dict(EYE="EMPTY")
            continue
        opr = z["opening_minus_own_rail_start_ps"]
        # strict: the driver must be valid before its receiver's rail even starts
        setup_strict = T - opr
        # relaxed: before the receiver's OWN data-eye opens
        nz = (out["banks"][str(k + 1)]["EYES"]["EYE2_DATA_FIXED"]["W_EXTENDED"]["0mV"]
              if k < nb else None)
        setup_relaxed = (None if nz is None or "EYE" in nz else
                         round((nz["opening_ps"]) - z["opening_ps"], 4))
        hand[str(k)] = dict(
            data_valid_after_own_rail_start_ps=opr,
            beat_period_T_ps=T, initiation_interval_H_times_T_ps=II,
            SETUP_SLACK_strict_ps=round(setup_strict, 4),
            setup_slack_strict_definition="T - (data-eye opening after own rail start): how much "
                "earlier than its receiver's rail start the driver's data is already valid",
            SETUP_SLACK_relaxed_ps=setup_relaxed,
            setup_slack_relaxed_definition="the receiver's OWN data-eye opening minus the "
                "driver's: how much of the receiver's evaluation the driver's data precedes",
            EYE_WIDTH_pipelined_DERIVED_ps=round(II - opr, 4),
            eye_width_pipelined_definition="H*T - (data-eye opening after own rail start). "
                "DERIVED: in a pipelined machine the right edge is the NEXT datum on this "
                "bank at the initiation interval; the single-shot deck contains no next datum "
                "(AMENDMENT E4), so the deck WIDTH is only a lower bound.",
            EYE_WIDTH_deck_LOWER_BOUND_ps=z["WIDTH_ps"],
            HEIGHT_at_centre_HIGH_mV=z["HEIGHT_at_centre_HIGH_mV"],
            HEIGHT_at_centre_LOW_mV=z["HEIGHT_at_centre_LOW_mV"],
            post_return_margin_floor_mV=B["POST_RETURN_MARGIN_FLOOR"]
                ["EYE2_DATA_FIXED"]["worst_margin_after_return_close_mV"],
            **{"vs_MEASURED_61.6_ps_data_jitter": dict(
                jitter_ps=JIT,
                setup_slack_over_jitter=round(setup_strict / JIT, 4),
                pipelined_width_over_jitter=round((II - opr) / JIT, 4),
                setup_slack_survives_worst_case_data_jitter=bool(setup_strict > JIT))})
    out["PHASE2_HANDOFF_slack_around_the_sampling_instant"] = dict(
        _note="Phase 1 owes Phase 2 the SLACK, not a pass/fail. The BINDING comparison against "
              "the 61.6 ps measured data-dependent jitter is the SETUP SLACK, not the eye width: "
              "the width is bounded by the initiation interval and is generous, while the setup "
              "slack is the margin between the data becoming valid and the receiver's aperture "
              "opening. Everything here is DERIVED from the measured eyes in this file.",
        _measured_inputs=dict(data_dependent_zero_spread_ps=JIT,
                              timer_drift_ps_per_K=0.46, sigma_trip_mV=SIG),
        per_bank=hand)

    # ---------- M6: do the edges of successive banks coincide after removing T?
    co = {}
    for k in range(1, nb + 1):
        z = out["banks"][str(k)]["EYES"]["EYE2_DATA_FIXED"]["W_EXTENDED"]["0mV"]
        co[k] = (z.get("opening_ps"), z.get("closing_ps"))
    out["_M6_propagating_collapse_test"] = dict(
        reference="EYE2_DATA_FIXED, W_EXTENDED, 0 mV",
        openings_ps={str(k): co[k][0] for k in co},
        opening_delta_minus_T_ps={
            "%d_minus_%d" % (k, k - 1):
            (None if (co[k][0] is None or co[k - 1][0] is None)
             else round(co[k][0] - co[k - 1][0] - T, 4)) for k in range(2, nb + 1)},
        note="HONEST READING, corrected: because c_k advances by exactly T by construction, a "
             "residual of ~0 does NOT establish that bank k's edge is INHERITED from bank k-1. "
             "What it establishes is weaker and still useful: the opening measured from each "
             "bank's OWN rail start is BANK-INVARIANT, i.e. the wave is in steady state and the "
             "eye edge does NOT degrade or accumulate across hops. This test cannot separate "
             "M6 (propagating collapse) from a locally-set edge that happens to be identical "
             "at every bank; distinguishing them needs a perturbation experiment on one bank, "
             "which this study does not run. Bank nb's residual is dominated by its DERIVED "
             "receiver and is not evidence about anything.")
    open(os.path.join(HERE, "EYE.json"), "w").write(json.dumps(out, indent=1))

    # ---------- console
    for ref in ("EYE2_DATA_FIXED", "EYE1_RX_INSTANTANEOUS"):
        print("\n=== %s  (W_EXTENDED, INTERSECTION over %d patterns, 0 mV) ==="
              % (ref, len(good)))
        print("%-5s %-6s %-10s %-10s %-12s %-9s %-9s %-10s %-6s" %
              ("bank", "recv", "open ps", "close ps", "WIDTH ps", "H_HIGH", "H_LOW",
               "open-c_k", "clip"))
        for k in range(1, nb + 1):
            z = out["banks"][str(k)]["EYES"][ref]["W_EXTENDED"]["0mV"]
            if "EYE" in z:
                print("%-5d %-6s EMPTY" % (k, "meas" if k < nb else "DERIV"))
                continue
            print("%-5d %-6s %-10.3f %-10.3f %-12s %-9s %-9s %-10.3f %s/%s" %
                  (k, "meas" if k < nb else "DERIV", z["opening_ps"], z["closing_ps"],
                   "%.3f%s" % (z["WIDTH_ps"], " LB" if z["WIDTH_IS_A_LOWER_BOUND"] else ""),
                   ("%.2f" % z["HEIGHT_at_centre_HIGH_mV"])
                   if z["HEIGHT_at_centre_HIGH_mV"] is not None else "-",
                   ("%.2f" % z["HEIGHT_at_centre_LOW_mV"])
                   if z["HEIGHT_at_centre_LOW_mV"] is not None else "-",
                   z["opening_minus_own_rail_start_ps"],
                   z["clipped_at_window_start"], z["clipped_at_window_end"]))
    print("\npost-return margin floor (EYE2_DATA_FIXED) -- where a right edge would appear:")
    for k in range(1, nb + 1):
        pr = out["banks"][str(k)]["POST_RETURN_MARGIN_FLOOR"]["EYE2_DATA_FIXED"]
        print("  bank%d  %.3f mV at t=%.1f ps" %
              (k, pr["worst_margin_after_return_close_mV"], pr["at_t_ps"]))
    return 0


if __name__ == "__main__":
    pats = sys.argv[1:] or sorted(EH.PATTERNS)
    sys.exit(main(pats))
