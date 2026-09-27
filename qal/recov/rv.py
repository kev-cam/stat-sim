#!/usr/bin/env python3
"""Gate-charge RECOVERY harness (M1 resonant / M2 stepwise / M3 lower-VGH).

Every deck is a TEXT PATCH of the committed swsweep/sw_tg15p_z.cir (gate G3 of
PRE_REGISTERED.json): the only removed lines are the three ideal drive sources
VGT/VGTP/VPK and the drive-integrator B-sources that reference them; the only
additions are the candidate drive network, its own integrators, and .print columns.

Metering: 1F-integrator instrument only (the harness convention).  Every DC source
in a drive network gets BOTH a charge integrator (xq<tag>) and an energy integrator
(xe<tag> = -integral V(node)*I(src)), so the ledger can be closed per row.
"""
import os, subprocess, sys, json, time, math

HERE  = os.path.dirname(os.path.abspath(__file__))
BASE  = "/usr/local/src/stat-sim/qal/swsweep/sw_tg15p_z.cir"
CALIB = "/usr/local/src/stat-sim/qal/swsweep/sw_calib.cir.prn"
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_recov"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- committed anchors (USED, not re-derived) ----------------------------------
IDEAL = dict(E_hop_open=8.3828171771408, VBEND=0.6758936, VBPK=0.7374377,
             VA_open=0.09778203952305342, cells=1.6954746104994207,
             t_zcs=266.76, IPK=194.3655)
REAL  = dict(E_hop_open=8.10914, VBEND=0.68463, VA_open=0.10782, cells=1.92709,
             E_timer=399.84214)
Q_GT, Q_GTP, Q_PK = 10.498, 16.389, 2.1        # fC, MEASURED / DERIVED
CV2_CONV_1P5 = (Q_GT + Q_GTP + Q_PK) * 1.5     # 43.48 fJ
FLOOR_IDEAL = 3.563                            # fJ, EGT_D-EGT_Z committed
TD = 811.755                                   # fixed absolute checkpoint (ps)
TCLOSE = 50.0                                  # committed close (gt 0->VGH at 48..50p)
T_EDGE_MAX = 133.0                             # pre-registered architectural budget

# ---- prn / mt0 io --------------------------------------------------------------
def read_prn(p):
    rows, hdr = [], None
    for ln in open(p):
        f = ln.split()
        if hdr is None and f and f[0].lower() == 'index':
            hdr = [h.upper() for h in f]; continue
        if hdr and f and f[0][0].isdigit():
            try: rows.append([float(x) for x in f])
            except ValueError: pass
    return hdr, rows

def read_mt0(p):
    d = {}
    for ln in open(p):
        if '=' in ln:
            k, v = ln.split('=', 1)
            try: d[k.strip().upper()] = float(v.strip())
            except ValueError: pass
    return d

def col(hdr, n):
    n = n.upper()
    c = [i for i, h in enumerate(hdr) if h == n]
    if not c: c = [i for i, h in enumerate(hdr) if n in h]
    if not c: raise KeyError('no column %s in %s' % (n, hdr))
    return c[0]

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

def at(rows, ic, t_ps, it=1):
    prev = None
    for r in rows:
        t = r[it]
        if prev is not None and prev[0] <= t_ps * 1e-12 <= t:
            f = (t_ps * 1e-12 - prev[0]) / (t - prev[0]) if t != prev[0] else 0.0
            return prev[1] + f * (r[ic] - prev[1])
        prev = (t, r[ic])
    return rows[-1][ic]

# ---- static calibration curve (bank-B cell/rail charge at a given end voltage) --
_SC = None
def static_curve():
    global _SC
    if _SC: return _SC
    hdr, rows = read_prn(CALIB)
    iv = col(hdr, 'V(BKB)')
    cs = {t: col(hdr, 'V(X%s)' % t.upper()) for t in ['qsh','qsl','esh','esl','eih']}
    base = {t: rows[0][c] for t, c in cs.items()}
    def f(vend):
        prev = None
        for r in rows:
            if prev is not None and prev[iv] <= vend <= r[iv]:
                g = (vend-prev[iv])/(r[iv]-prev[iv]) if r[iv] != prev[iv] else 0.0
                d = {t: (prev[c]+g*(r[c]-prev[c])-base[t])*1e15 for t, c in cs.items()}
                return dict(Q_sup=d['qsh']+d['qsl'], E_sup=d['esh']+d['esl'], E_in=d['eih'])
            prev = r
        raise ValueError('vend %.4f outside static ramp' % vend)
    _SC = f
    return f

# ---- G0: reproduce the committed row from the committed .mt0 -------------------
def g0():
    m = read_mt0('/usr/local/src/stat-sim/qal/swsweep/sw_tg15p_z.cir.mt0')
    vbend = m['VBEND']
    st = static_curve()(vbend)
    # every 1F integrator carries a DC-op residual (V = I_dc * 0.01) at the Z
    # checkpoint -- the committed analyzer subtracts it, so this one must too.
    d = lambda k: (m[k + '_C' if False else k] )
    e_hop = (m['EA_C']-m['EA_Z'])*1e15 - st['E_sup']
    cells = ((m['EBK_D']-m['EBK_Z']) + (m['EIH_D']-m['EIH_Z']))*1e15 \
            - st['E_sup'] - st['E_in']
    return dict(VBEND=vbend, VBPK=m['VBPK'], E_hop_open_fJ=e_hop, cells_burn_fJ=cells,
                E_R_toC_fJ=(m['ER_C']-m['ER_Z'])*1e15,
                Q_gt_close_fC=(m['QGT_A']-m['QGT_Z'])*1e15,
                Q_gtp_open_fC=(m['QGTP_C']-m['QGTP_B'])*1e15,
                EGT_floor_fJ=(m['EGT_D']-m['EGT_Z'])*1e15,
                IPK_uA=m['IPK']*1e6, IZ_uA=m['IZ']*1e6,
                VA_open_from_QLT=1.0-((m['QLT_C']-m['QLT_Z'])*1e15)/35.979)

# ---- deck construction --------------------------------------------------------
def integ(tag, expr):
    return ['CX%s x%s 0 1' % (tag, tag), 'BX%s 0 x%s I={ %s }' % (tag, tag, expr),
            'RX%s x%s 0 0.01' % (tag, tag)]

def build(drive_lines, extra_print, tend_ps, temp=27.0, tprint=0.1):
    """text-patch the committed deck.  returns (text, removed_lines)"""
    src = open(BASE).read().splitlines()
    out, removed = [], []
    for ln in src:
        s = ln.strip()
        if s.startswith('VGT ') or s.startswith('VGTP ') or s.startswith('VPK '):
            removed.append(ln); continue
        if s.startswith('.hdl'):
            out.append(ln); continue
        if s.startswith('.include') and 'sg13lv_compat.sp' in s and abs(temp-27.0) > 1e-9:
            out.append('.param GDTA=%g' % (temp-27.0))
            out.append('.include "/usr/local/src/stat-sim/qal/timer/sg13lv_dta.sp"')
            continue
        if s.startswith('VHI '):
            out.append(ln); out.extend(drive_lines); continue
        if s.startswith('BXqgt '):
            removed.append(ln); continue
        if s.startswith('BXqgtp '):
            removed.append(ln); continue
        if s.startswith('BXegt '):
            removed.append(ln); continue
        if s.startswith('CXqgt ') or s.startswith('RXqgt ') or \
           s.startswith('CXqgtp ') or s.startswith('RXqgtp ') or \
           s.startswith('CXegt ') or s.startswith('RXegt '):
            removed.append(ln); continue
        if s.startswith('.measure'):
            continue
        if s.startswith('.tran'):
            out.append('.tran %gp %gp 0 0.25p' % (tprint, tend_ps)); continue
        if s.startswith('.print'):
            base_cols = ('V(bka) V(bkb) V(sw) I(LT) V(gt) V(gtp) V(pk) '
                         'V(xea) V(xeb) V(xer) V(xebk) V(xeih) V(xesh) V(xesl) '
                         'V(xqlt) V(xqbk) V(xqsh) V(xqsl) '
                         'V(o0) V(o1) V(o2) V(o3) V(o4) V(o5) V(o6) V(o7)')
            out.append('.print tran %s %s' % (base_cols, extra_print)); continue
        out.append(ln)
    return '\n'.join(out) + '\n', removed

def run(tag, txt, timeout=600, quiet=False):
    fn = os.path.join(HERE, tag + '.cir')
    open(fn, 'w').write(txt)
    t0 = time.monotonic()
    r = subprocess.run([XYCE, os.path.basename(fn)], capture_output=True, text=True,
                       timeout=timeout, cwd=HERE, env=ENV)
    wall = time.monotonic()-t0
    if not os.path.exists(fn + '.prn'):
        print('XYCE FAILED %s (%.0fs)' % (tag, wall))
        bad = [l for l in (r.stdout+r.stderr).splitlines()
               if any(k in l.lower() for k in ('error','abort','fatal','fail'))]
        print('\n'.join(bad[:25]))
        return None, wall
    if not quiet: print('  %-28s ran %5.1f s' % (tag, wall))
    return fn + '.prn', wall

# ---- analyzer -----------------------------------------------------------------
def analyze(prn, VGH=1.5, drive_tags=(), q_tags=(), tank_caps=None, aux=None,
            td=None, te_meter=None):
    """tank_caps: {tag: (C_fF, node_col_name)}   aux: {name: (charge_tag, V, n_cycles)}
    td       : absolute settled checkpoint for VBEND/cells (default the committed 811.755)
    te_meter : end of the drive-ledger window (default td)"""
    TD = td if td is not None else globals()['TD']
    hdr, rows = read_prn(prn)
    C = lambda n: col(hdr, n)
    gt, gtp, pk, ilt = C('V(GT)'), C('V(GTP)'), C('V(PK)'), C('I(LT)')
    vbka, vbkb, vsw = C('V(BKA)'), C('V(BKB)'), C('V(SW)')
    r = {}
    half, lo8, hi8 = 0.5*VGH, 0.2*VGH, 0.8*VGH
    r['gt_rise_50'] = cross(rows, gt, half, True)
    if r['gt_rise_50'] is None: return None
    tafter = r['gt_rise_50'] + 20
    r['gt_fall_50'] = cross(rows, gt, half, False, tmin=tafter)
    a = cross(rows, gt, hi8, True); b = cross(rows, gt, lo8, True)
    r['gt_rise_20_80'] = (a-b) if (a and b) else None
    f80 = cross(rows, gt, hi8, False, tmin=tafter); f20 = cross(rows, gt, lo8, False, tmin=tafter)
    r['gt_fall_80_20'] = (f20-f80) if (f20 and f80) else None
    r['gtp_fall_50'] = cross(rows, gtp, half, False)
    r['gtp_rise_50'] = cross(rows, gtp, half, True, tmin=tafter)
    r['pk_rise_50']  = cross(rows, pk, half, True, tmin=tafter)
    r['width_50_ps'] = (r['gt_fall_50']-r['gt_rise_50']) if r['gt_fall_50'] else None
    # PHYSICAL cut instants: last time |I(LT)| leaves the +-1uA band for good is the
    # effective open; also report I at the 50% crossings.
    ipk = max(x[ilt] for x in rows)
    r['IPK_uA'] = ipk*1e6
    if r['gt_fall_50']: r['I_at_gt_fall_uA'] = at(rows, ilt, r['gt_fall_50'])*1e6
    if r['gtp_rise_50']: r['I_at_gtp_rise_uA'] = at(rows, ilt, r['gtp_rise_50'])*1e6
    r['t_zero_meas_ps'] = cross(rows, ilt, 0.0, False, tmin=r['gt_rise_50']+30)
    cand = [x for x in (r['gt_fall_50'], r['gtp_rise_50']) if x]
    topen = max(cand) if cand else None
    r['t_open_ps'] = topen
    tC = topen + 7.0
    def ck(name, tp):
        c = C('V(X%s)' % name); return (at(rows, c, tp)-rows[0][c])*1e15
    vbe = at(rows, vbkb, TD)
    st = static_curve()(vbe)
    r['VBEND'], r['VBPK'] = vbe, max(x[vbkb] for x in rows)
    r['VA_open'] = at(rows, vbka, topen)
    r['EA_C_fJ'] = ck('ea', tC)
    r['E_hop_open_fJ'] = r['EA_C_fJ'] - st['E_sup']
    r['E_R_toC_fJ'] = ck('er', tC)
    r['cells_burn_fJ'] = ck('ebk', TD) + ck('eih', TD) - st['E_sup'] - st['E_in']
    r['Q_L_C_fC'] = ck('qlt', tC)
    r['VA_open_from_QLT'] = 1.0 - r['Q_L_C_fC']/35.979
    # cells settled?
    oc = [C('V(O%d)' % i) for i in range(8)]
    ov = [at(rows, c, TD) for c in oc]
    r['cells_V'] = [round(v, 5) for v in ov]
    ok = all(ov[i] <= 0.03*vbe for i in (0,2,4,6)) and all(ov[i] >= 0.97*vbe for i in (1,3,5,7))
    r['cells_settled'] = 'PASS' if ok else 'FAIL'
    # drive ledger
    tE = te_meter if te_meter is not None else min(rows[-1][1]*1e12 - 1.0, TD)
    for t in drive_tags:
        r['E_%s_fJ' % t] = ck('e'+t, tE)
    for t in q_tags:
        r['Q_%s_fC' % t] = ck('q'+t, tE)
    r['E_drive_sources_fJ'] = sum(r['E_%s_fJ' % t] for t in drive_tags)
    # tank stored-energy deficit
    r['E_tank_deficit_fJ'] = 0.0
    if tank_caps:
        for tg, (cf, node) in tank_caps.items():
            cn = C(node)
            v0, v1 = rows[0][cn], at(rows, cn, tE)
            d = 0.5*cf*1e-15*(v0*v0-v1*v1)*1e15
            r['tank_%s_V' % tg] = (round(v0,6), round(v1,6))
            r['tank_%s_deficit_fJ' % tg] = d
            r['E_tank_deficit_fJ'] += d
    # auxiliary (recursion) switch cost, charged CONVENTIONALLY
    r['E_aux_conventional_fJ'] = 0.0
    if aux:
        for nm, (qt, v, nc) in aux.items():
            q = abs(r['Q_%s_fC' % qt])
            c = q*v*nc
            r['aux_%s_fJ' % nm] = c
            r['E_aux_conventional_fJ'] += c
    r['E_drive_total_fJ'] = (r['E_drive_sources_fJ'] + r['E_tank_deficit_fJ']
                             + r['E_aux_conventional_fJ'])
    r['t_end_meter_ps'] = tE
    # gates
    r['completeness_VBEND'] = 'PASS' if 0.66238 <= vbe <= 0.68941 else 'FAIL'
    r['completeness_VA'] = 'PASS' if r['VA_open'] <= 0.1478 else 'FAIL'
    r['completeness_Ehop'] = 'PASS' if abs(r['E_hop_open_fJ']/REAL['E_hop_open']-1) <= 0.05 else 'FAIL'
    # cut order: gtp cut early-or-with (gtp_rise <= gt_fall + 5), pk after gt cut
    o = []
    if r['gtp_rise_50'] is not None and r['gt_fall_50'] is not None:
        o.append('gtp_vs_gt_ps=%.1f' % (r['gtp_rise_50']-r['gt_fall_50']))
    if r['pk_rise_50'] is not None and r['gt_fall_50'] is not None:
        o.append('pk_vs_gt_ps=%.1f' % (r['pk_rise_50']-r['gt_fall_50']))
    r['order_detail'] = ' '.join(o)
    okorder = True
    if r['gtp_rise_50'] is not None and r['gt_fall_50'] is not None:
        okorder &= (r['gtp_rise_50'] - r['gt_fall_50']) <= 5.0
    if r['pk_rise_50'] is not None and r['gt_fall_50'] is not None:
        okorder &= (r['pk_rise_50'] - r['gt_fall_50']) >= -5.0
    r['cut_order'] = 'PASS' if okorder else 'FAIL'
    e = r['gt_rise_20_80'] or 0
    r['T_edge_budget'] = 'PASS' if e <= T_EDGE_MAX else 'BUDGET-VIOLATING'
    return r

def eta(E_drive, cv2=CV2_CONV_1P5):
    return 1.0 - E_drive/cv2

def n_min(E):
    return (39.6 + E)/(0.867-0.0361)

def save(tag, res, fn='RESULTS_RECOV.json'):
    p = os.path.join(HERE, fn)
    db = {}
    if os.path.exists(p):
        try: db = json.load(open(p))
        except Exception: db = {}
    db[tag] = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in res.items()}
    json.dump(db, open(p, 'w'), indent=1, sort_keys=True)

def show(r, keys=None):
    keys = keys or ['width_50_ps','gt_rise_50','gt_fall_50','gtp_rise_50','pk_rise_50',
                    'gt_rise_20_80','gt_fall_80_20','I_at_gt_fall_uA','IPK_uA',
                    't_zero_meas_ps','VBEND','VBPK','VA_open','E_hop_open_fJ',
                    'cells_burn_fJ','cells_settled','E_drive_sources_fJ',
                    'E_tank_deficit_fJ','E_aux_conventional_fJ','E_drive_total_fJ',
                    'completeness_VBEND','completeness_VA','completeness_Ehop',
                    'cut_order','order_detail','T_edge_budget']
    for k in keys:
        if k in r: print('    %-24s %s' % (k, r[k]))
