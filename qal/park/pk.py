#!/usr/bin/env python3
"""TRACK A extractor.  Wraps the committed skeptic extractor qal/recov/skeptic/sk.py
(so every completeness metric is computed by code that has already been audited
against the committed .mt0 to the digit) and ADDS the four things this track needs:

  * the DEVICE-REFERENCED park close/release instants (V(pk) crossing Vtn), not
    the 50 % convention -- the park nMOS source is hard ground, so 0.45 V is the
    physically meaningful level;
  * H1  the hold test on the parked node: max V(sw) over [park close, tD];
  * H2  the hold test on the DELIVERED rail: V(bkb) droop from tC to tD;
  * the park drive ledger, metered on the park tap's own source and cross-checked
    by a trapezoid reconstruction I = (V(pks)-V(pk))/RS that never touches any
    1F integrator.
"""
import sys, os, json
sys.path.insert(0, '/usr/local/src/stat-sim/qal/recov/skeptic')
import sk

TD_PRE = 811.755
VTN = 0.45


def cross_after(rows, ic, val, rising, tmin, it):
    prev = None
    for r in rows:
        t, v = r[it], r[ic]
        if prev is not None and t > tmin * 1e-12:
            p = prev[1]
            if (rising and p < val <= v) or (not rising and p > val >= v):
                f = (val - p) / (v - p) if v != p else 0.0
                return (prev[0] + f * (t - prev[0])) * 1e12
        prev = (t, v)
    return None


def analyse(prn, rs_pk=25.0, td=TD_PRE):
    r = sk.hop(prn)
    hdr, rows = sk.read_prn(prn)
    it = sk.tcol(hdr)
    C = lambda n: sk.col(hdr, n)
    vpk, vsw, vbkb, vbka = C('V(PK)'), C('V(SW)'), C('V(BKB)'), C('V(BKA)')
    tn = r.get('nmos_cut_ps')

    # ---- DEVICE-REFERENCED park timing (source is hard ground) ---------------
    p = {}
    p['V_pk_at_t0'] = rows[0][vpk]
    p['V_pk_max'] = max(x[vpk] for x in rows)
    p['V_pk_min'] = min(x[vpk] for x in rows)
    p['V_pk_at_tD'] = sk.at(rows, vpk, td, it)[0]
    tclose = cross_after(rows, vpk, VTN, True, (r.get('gt_rise_50') or 0) + 20, it)
    p['park_close_dev_ps'] = tclose
    p['park_release_dev_ps'] = cross_after(rows, vpk, VTN, False,
                                           (tclose or 0) + 1, it) if tclose else None
    # is the park ON before the hop?  (the fixture pre-charges bank A at t=0)
    p['park_ON_at_t0'] = bool(rows[0][vpk] > VTN)
    p['park_prehop_release_ps'] = (cross_after(rows, vpk, VTN, False, 0.0, it)
                                   if rows[0][vpk] > VTN else None)
    if tclose is not None and tn:
        p['park_close_minus_nmos_cut_ps'] = tclose - tn
    p['Vgs_park_at_close_plus50ps'] = sk.at(rows, vpk, (tclose or 0) + 50, it)[0] \
        if tclose else None

    # ---- H1: does the park actually hold sw down? ---------------------------
    t0 = (tclose if tclose else (r.get('pk_rise_50') or 0))
    win = [x for x in rows if t0 * 1e-12 <= x[it] <= td * 1e-12]
    if win:
        p['H1_max_V_sw_over_hold'] = max(x[vsw] for x in win)
        p['H1_mean_V_sw_over_hold'] = sum(x[vsw] for x in win) / len(win)
        p['H1_window_ps'] = [round(t0, 3), td]
        # H1 RESTATED (see RESULTS.json h1_gate_correction): the gate as
        # pre-registered included the park's own pull-down transient and so is
        # failed by the COMMITTED baseline itself.  Two-part restatement:
        #   t_settle = first instant after park close from which |V(sw)| stays
        #              <= 0.10 V all the way to tD;
        #   H1a = settling delay t_settle - t_close;  H1b = max |V(sw)| after it.
        ts, run = None, None
        for x in reversed(win):
            if abs(x[vsw]) <= 0.10:
                run = x[it] * 1e12
            else:
                break
        ts = run
        p['H1_t_settle_ps'] = ts
        p['H1_settle_delay_ps'] = (ts - t0) if ts is not None else None
        if ts is not None:
            after = [x for x in win if x[it] * 1e12 >= ts]
            p['H1_max_abs_V_sw_after_settle'] = max(abs(x[vsw]) for x in after)
        p['H1_raw_gate_as_preregistered'] = \
            'PASS' if p['H1_max_V_sw_over_hold'] <= 0.10 else 'FAIL'
    # and with NO park at all the ring is on sw for the whole post-open window
    topen = r.get('t_open_ps')
    if topen:
        w2 = [x for x in rows if topen * 1e-12 <= x[it] <= td * 1e-12]
        p['V_sw_max_post_open'] = max(x[vsw] for x in w2)
        p['V_sw_min_post_open'] = min(x[vsw] for x in w2)
        p['V_bka_max_post_open'] = max(x[vbka] for x in w2)

    # ---- H2: droop of the DELIVERED rail across the hold --------------------
    if topen:
        tC = topen + 7.0
        vC = sk.at(rows, vbkb, tC, it)[0]
        vD = sk.at(rows, vbkb, td, it)[0]
        p['H2_VBKB_at_tC'] = vC
        p['H2_VBKB_at_tD'] = vD
        p['H2_droop_mV'] = (vD - vC) * 1e3
        p['H2_droop_pct'] = 100.0 * (vD - vC) / vC
    r['park'] = p

    # ---- the park drive ledger ----------------------------------------------
    d = {}
    for tg in ('pk',):
        try:
            d['E_%s_1F_fJ' % tg] = sk.integ_ck(rows, hdr, 'e' + tg,
                                               rows[-1][it] * 1e12, it)[0]
            d['Q_%s_rect_1F_fC' % tg] = sk.integ_ck(rows, hdr, 'q' + tg,
                                                    rows[-1][it] * 1e12, it)[0]
            d['E_%s_1F_at_tD_fJ' % tg] = sk.integ_ck(rows, hdr, 'e' + tg, td, it)[0]
        except KeyError:
            pass
    try:                                    # sub-harmonic tap: trapezoid check
        isn, ign = C('V(PKS)'), C('V(PK)')
        cur = lambda x: (x[isn] - x[ign]) / rs_pk
        d['E_pk_source_trapz_fJ'] = sk.trapz(rows, it, lambda x: x[isn] * cur(x)) * 1e15
        d['E_pk_Rseries_fJ'] = sk.trapz(rows, it, lambda x: cur(x) ** 2 * rs_pk) * 1e15
        d['E_pk_into_gate_node_fJ'] = sk.trapz(rows, it,
                                               lambda x: x[ign] * cur(x)) * 1e15
        d['Q_pk_net_fC'] = sk.trapz(rows, it, cur) * 1e15
        d['Q_pk_rect_trapz_fC'] = sk.trapz(rows, it, lambda x: abs(cur(x))) * 1e15
        d['closure_pct'] = 100.0 * (d['E_pk_source_trapz_fJ'] - d['E_pk_Rseries_fJ']
                                    - d['E_pk_into_gate_node_fJ']) \
            / max(abs(d['E_pk_source_trapz_fJ']), 1e-9)
    except KeyError:
        pass
    r['park_drive'] = d

    # ---- VHI over a FULL BEAT as well as at tend (IS7) -----------------------
    try:
        r['ehi_at_580_fJ'] = sk.integ_ck(rows, hdr, 'ehi', 580.0, it)[0]
        r['ehi_at_1160_fJ'] = sk.integ_ck(rows, hdr, 'ehi', 1160.0, it)[0]
        r['qhi_at_580_fC'] = sk.integ_ck(rows, hdr, 'qhi', 580.0, it)[0]
    except (KeyError, IndexError):
        pass
    return r


def gates(r, base=None):
    """compact PASS/FAIL row against the pre-registered band."""
    ck = r['ck'].get('pre_%.3f' % TD_PRE, {})
    p = r.get('park', {})
    g = {
        'VBEND': ck.get('VBEND'), 'VBEND_gate': ck.get('VBEND_gate'),
        'VA_open': r.get('VA_open'), 'VA_gate': r.get('VA_gate'),
        'E_hop_open_fJ': ck.get('E_hop_open_fJ'), 'Ehop_gate': ck.get('Ehop_gate'),
        'cells_settled': ck.get('cells_settled'),
        'nmos_cut_ps': r.get('nmos_cut_ps'),
        'pmos_minus_nmos_ps': r.get('pmos_vs_nmos_ps'),
        'park_close_minus_nmos_ps': p.get('park_close_minus_nmos_cut_ps'),
        'H1_max_V_sw': p.get('H1_max_V_sw_over_hold'), 'H1': p.get('H1'),
        'H2_droop_mV': p.get('H2_droop_mV'),
        'park_ON_at_t0': p.get('park_ON_at_t0'),
    }
    order = 'PASS'
    if g['pmos_minus_nmos_ps'] is None or g['pmos_minus_nmos_ps'] > 5.0:
        order = 'FAIL'
    if g['park_close_minus_nmos_ps'] is not None and g['park_close_minus_nmos_ps'] <= 0:
        order = 'FAIL'
    g['cut_order'] = order
    if base is not None:
        g['H2_droop_vs_base_mV'] = g['H2_droop_mV'] - base
        g['H2'] = 'PASS' if g['H2_droop_vs_base_mV'] >= -1.0 else 'FAIL'
    g['ALL5'] = 'PASS' if (g['VBEND_gate'] == 'PASS' and g['VA_gate'] == 'PASS'
                           and g['Ehop_gate'] == 'PASS'
                           and g['cells_settled'] == 'PASS'
                           and order == 'PASS') else 'FAIL'
    return g


if __name__ == '__main__':
    out = {}
    for p in sys.argv[1:]:
        try:
            out[os.path.basename(p)] = analyse(p)
        except Exception as e:
            out[os.path.basename(p)] = {'ERROR': '%s: %s' % (type(e).__name__, e)}
    print(json.dumps(out, indent=1, sort_keys=True, default=str))
