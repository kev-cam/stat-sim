#!/usr/bin/env python3
"""SKEPTIC's own extractor for the gate-charge RECOVERY claim.

Written from the netlists, independent of qal/recov/rv.py.  Two things it does
that rv.py does not:
  * re-derives the drive-source energies by TRAPEZOID INTEGRATION of the current
    reconstructed from the printed node voltages, I = (V(gts)-V(gt))/RS, so the
    1F-integrator instrument is checked by a path that never touches it, and the
    series-R loss and the energy actually entering the gate NODE are separated;
  * takes every hop metric at BOTH the deck's last sample and the pre-registered
    absolute checkpoint tD = 811.755 ps, so a deck that ends early is caught.
"""
import sys, math, json

CALIB = "/usr/local/src/stat-sim/qal/swsweep/sw_calib.cir.prn"
TD_PRE = 811.755          # pre-registered absolute checkpoint (ps)


def read_prn(p):
    hdr, rows = None, []
    for ln in open(p):
        f = ln.split()
        if hdr is None and f and f[0].lower() == 'index':
            hdr = [h.upper() for h in f]
            continue
        if hdr and f and f[0][0].isdigit():
            try:
                rows.append([float(x) for x in f])
            except ValueError:
                pass
    return hdr, rows


def read_mt0(p):
    d = {}
    for ln in open(p):
        if '=' in ln:
            k, v = ln.split('=', 1)
            try:
                d[k.strip().upper()] = float(v.strip())
            except ValueError:
                pass
    return d


def col(hdr, n):
    n = n.upper()
    c = [i for i, h in enumerate(hdr) if h == n]
    if not c:
        c = [i for i, h in enumerate(hdr) if n in h]
    if not c:
        raise KeyError('no column %s' % n)
    return c[0]


def tcol(hdr):
    return col(hdr, 'TIME')


def at(rows, ic, t_ps, it=1):
    """linear interpolation; returns (value, clamped?)"""
    tt = t_ps * 1e-12
    if tt > rows[-1][it]:
        return rows[-1][ic], True
    prev = None
    for r in rows:
        if prev is not None and prev[0] <= tt <= r[it]:
            f = (tt - prev[0]) / (r[it] - prev[0]) if r[it] != prev[0] else 0.0
            return prev[1] + f * (r[ic] - prev[1]), False
        prev = (r[it], r[ic])
    return rows[-1][ic], True


def cross(rows, ic, val, rising, tmin=0.0, it=1):
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


def trapz(rows, it, f, t0_ps=0.0, t1_ps=None):
    """integral of f(row) dt over [t0,t1], SI units.  Straight trapezoid on the
    printed samples, with linear interpolation at a partial end panel."""
    t0 = t0_ps * 1e-12
    t1 = rows[-1][it] if t1_ps is None else t1_ps * 1e-12
    s, prev = 0.0, None
    for r in rows:
        t, y = r[it], f(r)
        if prev is not None:
            ta, ya = prev
            if t > t0 and ta < t1 and t > ta:
                a, b = max(ta, t0), min(t, t1)
                if b > a:
                    ya2 = ya + (y - ya) * (a - ta) / (t - ta)
                    yb2 = ya + (y - ya) * (b - ta) / (t - ta)
                    s += 0.5 * (ya2 + yb2) * (b - a)
        prev = (t, y)
    return s


# ---- static bank-B calibration curve (committed) ------------------------------
_SC = None


def static_curve():
    global _SC
    if _SC:
        return _SC
    hdr, rows = read_prn(CALIB)
    iv = col(hdr, 'V(BKB)')
    cs = {t: col(hdr, 'V(X%s)' % t.upper()) for t in ['qsh', 'qsl', 'esh', 'esl', 'eih']}
    base = {t: rows[0][c] for t, c in cs.items()}

    def f(vend):
        prev = None
        for r in rows:
            if prev is not None and prev[iv] <= vend <= r[iv]:
                g = (vend - prev[iv]) / (r[iv] - prev[iv]) if r[iv] != prev[iv] else 0.0
                d = {t: (prev[c] + g * (r[c] - prev[c]) - base[t]) * 1e15 for t, c in cs.items()}
                return dict(Q_sup=d['qsh'] + d['qsl'], E_sup=d['esh'] + d['esl'], E_in=d['eih'])
            prev = r
        raise ValueError('vend %.5f outside static ramp' % vend)
    _SC = f
    return f


def integ_ck(rows, hdr, tag, t_ps, it=1):
    """1F-integrator reading in fJ/fC, DC-op residual at t=0 subtracted."""
    c = col(hdr, 'V(X%s)' % tag)
    v, cl = at(rows, c, t_ps, it)
    return (v - rows[0][c]) * 1e15, cl


def hop(prn, RS_gate=25.0, vtn=0.45, vtp=0.50, td_list=(None, TD_PRE)):
    hdr, rows = read_prn(prn)
    it = tcol(hdr)
    C = lambda n: col(hdr, n)
    gt, gtp, pk = C('V(GT)'), C('V(GTP)'), C('V(PK)')
    ilt, vbka, vbkb, vsw = C('I(LT)'), C('V(BKA)'), C('V(BKB)'), C('V(SW)')
    r = {'prn': prn, 't_end_ps': rows[-1][it] * 1e12, 'nrows': len(rows)}

    # ---- drive waveform timing (50% convention, as the pre-registration says) --
    half = 0.75
    r['gt_rise_50'] = cross(rows, gt, half, True, it=it)
    taft = (r['gt_rise_50'] or 0) + 20
    r['gt_fall_50'] = cross(rows, gt, half, False, tmin=taft, it=it)
    r['gtp_fall_50'] = cross(rows, gtp, half, False, it=it)
    r['gtp_rise_50'] = cross(rows, gtp, half, True, tmin=taft, it=it)
    r['pk_rise_50'] = cross(rows, pk, half, True, tmin=taft, it=it)
    a = cross(rows, gt, 1.2, True, it=it); b = cross(rows, gt, 0.3, True, it=it)
    r['gt_rise_20_80'] = (a - b) if (a and b) else None
    if r['gt_fall_50'] and r['gt_rise_50']:
        r['width_50_ps'] = r['gt_fall_50'] - r['gt_rise_50']

    # ---- the LC zero and the DEVICE-REFERENCED cut instants -------------------
    r['IPK_uA'] = max(x[ilt] for x in rows) * 1e6
    r['t_zero_ps'] = cross(rows, ilt, 0.0, False, tmin=(r['gt_rise_50'] or 0) + 30, it=it)
    # last instant the nMOS is above threshold: V(gt) - V(source) > vtn, source = lower of sw,bkb
    tn = tp = None
    for k in range(1, len(rows)):
        x = rows[k]
        if x[it] * 1e12 < (r['gt_rise_50'] or 0) + 20:
            continue
        vs = min(x[vsw], x[vbkb])
        if x[gt] - vs > vtn:
            tn = x[it] * 1e12
        # pMOS: gate must be below (higher of sw,bkb) - |Vtp|
        vsp = max(x[vsw], x[vbkb])
        if x[gtp] < vsp - vtp:
            tp = x[it] * 1e12
    r['nmos_cut_ps'], r['pmos_cut_ps'] = tn, tp
    if tn and r['t_zero_ps']:
        r['cut_minus_zero_ps'] = tn - r['t_zero_ps']
    if tn and tp:
        r['pmos_vs_nmos_ps'] = tp - tn
    if tn and r['pk_rise_50']:
        r['park_vs_nmos_ps'] = r['pk_rise_50'] - tn
    for nm, t in (('nmos_cut', tn), ('zero', r['t_zero_ps']), ('gt_fall_50', r['gt_fall_50'])):
        if t:
            v, _ = at(rows, ilt, t, it)
            r['I_at_%s_uA' % nm] = v * 1e6

    # ---- hop metrics at each requested checkpoint ------------------------------
    cand = [x for x in (r['gt_fall_50'], r['gtp_rise_50']) if x]
    topen = max(cand) if cand else None
    r['t_open_ps'] = topen
    tC = topen + 7.0
    ea, clc = integ_ck(rows, hdr, 'ea', tC, it)
    r['EA_C_fJ'], r['EA_C_clamped'] = ea, clc
    r['E_R_toC_fJ'] = integ_ck(rows, hdr, 'er', tC, it)[0]
    r['Q_L_C_fC'] = integ_ck(rows, hdr, 'qlt', tC, it)[0]
    r['VA_open_from_QLT'] = 1.0 - r['Q_L_C_fC'] / 35.979
    r['VA_open'] = at(rows, vbka, topen, it)[0]
    r['VBPK'] = max(x[vbkb] for x in rows)
    oc = [C('V(O%d)' % i) for i in range(8)]
    r['ck'] = {}
    for td in td_list:
        t = rows[-1][it] * 1e12 if td is None else td
        lbl = 'last_%.3f' % t if td is None else 'pre_%.3f' % td
        vbe, cl = at(rows, vbkb, t, it)
        d = dict(t_ps=t, clamped=cl, VBEND=vbe)
        try:
            st = static_curve()(vbe)
            d['E_hop_open_fJ'] = ea - st['E_sup']
            d['cells_burn_fJ'] = (integ_ck(rows, hdr, 'ebk', t, it)[0]
                                  + integ_ck(rows, hdr, 'eih', t, it)[0]
                                  - st['E_sup'] - st['E_in'])
        except ValueError as e:
            d['static_curve'] = 'OUT OF RANGE: %s' % e
        ov = [at(rows, c, t, it)[0] for c in oc]
        d['cells_V'] = [round(v, 5) for v in ov]
        lo = [v for v in ov if v < 0.5 * vbe]
        hi = [v for v in ov if v >= 0.5 * vbe]
        d['cells_settled'] = 'PASS' if (all(v <= 0.03 * vbe for v in lo)
                                        and all(v >= 0.97 * vbe for v in hi)) else 'FAIL'
        d['n_lo'], d['n_hi'] = len(lo), len(hi)
        d['VBEND_gate'] = 'PASS' if 0.66238 <= vbe <= 0.68941 else 'FAIL'
        if 'E_hop_open_fJ' in d:
            d['Ehop_gate'] = 'PASS' if abs(d['E_hop_open_fJ'] / 8.10914 - 1) <= 0.05 else 'FAIL'
        r['ck'][lbl] = d
    r['VA_gate'] = 'PASS' if r['VA_open'] <= 0.1478 else 'FAIL'

    # ---- VHI (pMOS bulk) rail: unbooked in the drive ledger --------------------
    for tg in ('ehi', 'qhi', 'esw'):
        try:
            r['%s_fJ' % tg] = integ_ck(rows, hdr, tg, rows[-1][it] * 1e12, it)[0]
        except KeyError:
            pass

    # ---- the drive ledger, BOTH ways ------------------------------------------
    r['drive'] = {}
    for tag, src, snode, gnode in (('gt', 'VGTS', 'V(GTS)', 'V(GT)'),
                                   ('gtp', 'VGPS', 'V(GPS)', 'V(GTP)')):
        try:
            isn, ign = C(snode), C(gnode)
        except KeyError:
            continue
        cur = lambda x, a=isn, b=ign: (x[a] - x[b]) / RS_gate
        d = {}
        d['E_source_trapz_fJ'] = trapz(rows, it, lambda x, a=isn: x[a] * cur(x)) * 1e15
        d['E_Rseries_fJ'] = trapz(rows, it, lambda x: cur(x) ** 2 * RS_gate) * 1e15
        d['E_into_gate_node_fJ'] = trapz(rows, it, lambda x, b=ign: x[b] * cur(x)) * 1e15
        d['Q_net_fC'] = trapz(rows, it, cur) * 1e15
        d['Q_rect_fC'] = trapz(rows, it, lambda x: abs(cur(x))) * 1e15
        try:
            d['E_source_1F_fJ'] = integ_ck(rows, hdr, 'e' + tag, rows[-1][it] * 1e12, it)[0]
            d['Q_rect_1F_fC'] = integ_ck(rows, hdr, 'q' + tag, rows[-1][it] * 1e12, it)[0]
        except KeyError:
            pass
        d['closure_pct'] = 100.0 * (d['E_source_trapz_fJ'] - d['E_Rseries_fJ']
                                    - d['E_into_gate_node_fJ']) / max(abs(d['E_source_trapz_fJ']), 1e-9)
        r['drive'][tag] = d
    for tg in ('pk', 'pd', 'pi'):
        try:
            r['drive']['E_%s_1F_fJ' % tg] = integ_ck(rows, hdr, 'e' + tg, rows[-1][it] * 1e12, it)[0]
            r['drive']['Q_%s_1F_fC' % tg] = integ_ck(rows, hdr, 'q' + tg, rows[-1][it] * 1e12, it)[0]
        except KeyError:
            pass
    return r


def n_min(E):
    return (39.6 + E) / (0.867 - 0.0361)


if __name__ == '__main__':
    out = {}
    for p in sys.argv[1:]:
        try:
            out[p] = hop(p)
        except Exception as e:
            out[p] = {'ERROR': '%s: %s' % (type(e).__name__, e)}
    print(json.dumps(out, indent=1, sort_keys=True, default=str))
