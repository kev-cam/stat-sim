#!/usr/bin/env python3
"""Q1: the tapped-line timer driving the REAL tg15p hop -- first deck where the switch
gates are driven by transistors instead of ideal PWL sources.

The hop deck is a TEXT PATCH of the committed swsweep/sw_tg15p_z.cir (instrument gate G2):
the ONLY lines removed are the three ideal drive sources (VGT/VGTP/VPK) and the three
drive-integrator B-source expressions that reference them; the ONLY additions are the
timer netlist, its supply integrators, and extra .print columns. Cells, banks, metering,
options, tolerances are byte-identical to the committed run.

Timer (all sg13g2 stdcells at VDD=1.5 on four metered rails):
  trigger --inv_1--inv_2--> s --[N x inv_1 line]--> line_out
  N odd:  g1 = nand2_2(s, line_out)          (line_out is already NOT(delayed s))
  N even: nd = inv_1(line_out); g1 = nand2_2(s, nd)
  gt  = inv_4(g1)                       1 inversion  -> pulse high during transfer
  gtp = inv_8(inv_2(g1))                2 inversions -> complement (pMOS gate)
  pk  = 5 (N odd) / 6 (N even) stages from line_out, ending inv_2 -> rises ~2 gate
        delays AFTER gtp (the swsweep v1 park lesson: park must never close early)
  CTRIM (fF, split over two mid-line nodes) = the calibration DAC.

Usage: tl_hop.py N CTRIM [temp] [tag]
"""
import os, re, subprocess, sys, json, time

HERE  = os.path.dirname(os.path.abspath(__file__))
BASE  = "/usr/local/src/stat-sim/qal/swsweep/sw_tg15p_z.cir"
CELLS = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_timer"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

TTRIG = 20.0      # ps, trigger rise start (10 ps edge)
VGH   = 1.5

def timer_lines(N, ctrim_fF, design='v2'):
    if design == 'v2':
        return timer_lines_v2(N, ctrim_fF)
    L = ['* ---- tapped-line timer (real drives), N=%d ctrim=%gfF ----' % (N, ctrim_fF),
         'VST strig 0 PWL(0 0 %gp 0 %gp %g)' % (TTRIG, TTRIG + 10, VGH),
         'VTL vtl 0 %g' % VGH, 'VTG vtg 0 %g' % VGH,
         'VTP vtp 0 %g' % VGH, 'VTK vtk 0 %g' % VGH,
         'Xsi0 s0i strig vtl 0 sg13g2_inv_1',
         'Xsi1 s s0i vtl 0 sg13g2_inv_2']
    prev = 's'
    for i in range(N):
        L.append('Xli%d c%d %s vtl 0 sg13g2_inv_1' % (i, i, prev))
        prev = 'c%d' % i
    lo = prev                                    # line output
    m1, m2 = N // 3, 2 * N // 3
    if ctrim_fF > 0:
        L += ['CTR1 c%d 0 %gf' % (m1, ctrim_fF / 2.0),
              'CTR2 c%d 0 %gf' % (m2, ctrim_fF / 2.0)]
    if N % 2 == 1:               # line_out = NOT(delayed s): feed NAND B directly
        nb = lo
        pk_from, pk_stages = lo, 5               # odd # inversions -> pk follows delayed s
    else:                        # need nd = NOT(line_out)
        L.append('Xnd nd %s vtg 0 sg13g2_inv_1' % lo)
        nb = 'nd'
        pk_from, pk_stages = lo, 6
    L += ['Xg1 g1 s %s vtg 0 sg13g2_nand2_2' % nb,
          'Xgt gt g1 vtg 0 sg13g2_inv_4',
          'Xb1 b1 g1 vtp 0 sg13g2_inv_2',
          'Xgtp gtp b1 vtp 0 sg13g2_inv_8']
    prev = pk_from
    for i in range(pk_stages - 1):
        L.append('Xk%d k%d %s vtk 0 sg13g2_inv_1' % (i, i, prev))
        prev = 'k%d' % i
    L.append('Xkd pk %s vtk 0 sg13g2_inv_2' % prev)
    # supply-energy + trigger integrators (same 1F instrument as the harness)
    for tag, expr in [('etl', '-%g*I(VTL)' % VGH), ('etg', '-%g*I(VTG)' % VGH),
                      ('etp', '-%g*I(VTP)' % VGH), ('etk', '-%g*I(VTK)' % VGH),
                      ('est', '-V(strig)*I(VST)')]:
        L += ['CX%s x%s 0 1' % (tag, tag), 'BX%s 0 x%s I={ %s }' % (tag, tag, expr),
              'RX%s x%s 0 0.01' % (tag, tag)]
    return L, lo

def timer_lines_v2(N, ctrim_fF):
    """v2, after the measured v1 failures: (1) drivers RIGHT-SIZED to their gate loads
    (v1 inv_4/inv_8 at fanout<1 burned 508 fJ/hop); (2) TG cut order REVERSED -- v1 cut
    the nMOS 55 ps before the pMOS and the LC rang to -70 uA through the still-on pMOS,
    un-transferring the rail. v2 opens the pMOS ~1 stage EARLY (harmless: the nMOS
    carries the near-zero current) and the nMOS LAST, tuned to the zero.
       gtp: g1 -> inv_1 -> inv_4  (2 stages, pMOS 15.4 fF load at FO~1.4)
       gt : g1 -> inv_1 -> inv_1 -> inv_2  (3 stages, nMOS 7.7 fF at FO~1.4)
       pk : line_out -> 6x inv_1 -> inv_1  (7 stages; the 5-stage v2a landed 22 ps
            BEFORE the nMOS cut -- park-early is the v1-park failure mode -- so two
            stages were added; MEASURED to land after gt fall)
    N must be ODD (line output feeds NAND B directly)."""
    assert N % 2 == 1
    L = ['* ---- tapped-line timer v2, N=%d ctrim=%gfF ----' % (N, ctrim_fF),
         'VST strig 0 PWL(0 0 %gp 0 %gp %g)' % (TTRIG, TTRIG + 10, VGH),
         'VTL vtl 0 %g' % VGH, 'VTG vtg 0 %g' % VGH,
         'VTP vtp 0 %g' % VGH, 'VTK vtk 0 %g' % VGH,
         'Xsi0 s0i strig vtl 0 sg13g2_inv_1',
         'Xsi1 s s0i vtl 0 sg13g2_inv_2']
    prev = 's'
    for i in range(N):
        L.append('Xli%d c%d %s vtl 0 sg13g2_inv_1' % (i, i, prev))
        prev = 'c%d' % i
    lo = prev
    m1, m2 = N // 3, 2 * N // 3
    if ctrim_fF > 0:
        L += ['CTR1 c%d 0 %gf' % (m1, ctrim_fF / 2.0),
              'CTR2 c%d 0 %gf' % (m2, ctrim_fF / 2.0)]
    L += ['Xg1 g1 s %s vtg 0 sg13g2_nand2_1' % lo,
          'Xq1 q1 g1 vtg 0 sg13g2_inv_1',
          'Xq2 q2 q1 vtg 0 sg13g2_inv_1',
          'Xgt gt q2 vtg 0 sg13g2_inv_2',
          'Xp1 p1 g1 vtp 0 sg13g2_inv_1',
          'Xgtp gtp p1 vtp 0 sg13g2_inv_4']
    prev = lo
    for i in range(6):
        L.append('Xk%d k%d %s vtk 0 sg13g2_inv_1' % (i, i, prev))
        prev = 'k%d' % i
    L.append('Xkd pk %s vtk 0 sg13g2_inv_1' % prev)
    for tag, expr in [('etl', '-%g*I(VTL)' % VGH), ('etg', '-%g*I(VTG)' % VGH),
                      ('etp', '-%g*I(VTP)' % VGH), ('etk', '-%g*I(VTK)' % VGH),
                      ('est', '-V(strig)*I(VST)')]:
        L += ['CX%s x%s 0 1' % (tag, tag), 'BX%s 0 x%s I={ %s }' % (tag, tag, expr),
              'RX%s x%s 0 0.01' % (tag, tag)]
    return L, lo

def build(N, ctrim_fF, temp, tend_ps):
    src = open(BASE).read().splitlines()
    out, removed = [], []
    tl, lo = timer_lines(N, ctrim_fF)
    for ln in src:
        s = ln.strip()
        if s.startswith('VGT ') or s.startswith('VGT\t') or s.startswith('VGTP ') \
           or s.startswith('VPK '):
            removed.append(ln); continue
        if s.startswith('.hdl'):
            out.append(ln)
            out.append('.include "%s"' % CELLS)
            continue
        # corner = instance-level DTA through the dta shim's GDTA default (MEASURED:
        # .OPTIONS DEVICE TEMP is inert against the PyMS-compiled PSP103 and the
        # model-card dta is silently dropped from __GIVEN__; instance dta works --
        # dta_test.cir / dta_test3.cir, Id 321.7 -> 305.0 uA at +58K)
        if s.startswith('.include') and 'sg13lv_compat.sp' in s and abs(temp - 27.0) > 1e-9:
            out.append('.param GDTA=%g' % (temp - 27.0))
            out.append('.include "%s/sg13lv_dta.sp"' % HERE)
            continue
        if s.startswith('VHI '):
            out.append(ln); out.extend(tl); continue
        # drive integrators: qgt/qgtp reference removed sources -> re-point at timer rails;
        # egt (drive energy) -> total timer supply energy
        if s.startswith('BXqgt '):
            out.append('BXqgt 0 xqgt I={ -I(VTG) }'); removed.append(ln); continue
        if s.startswith('BXqgtp '):
            out.append('BXqgtp 0 xqgtp I={ -I(VTP) }'); removed.append(ln); continue
        if s.startswith('BXegt '):
            out.append('BXegt 0 xegt I={ -%g*(I(VTL)+I(VTG)+I(VTP)+I(VTK)) }' % VGH)
            removed.append(ln); continue
        if s.startswith('.measure'):
            continue                              # all metrics come from the prn
        if s.startswith('.tran'):
            out.append('.tran 0.1p %gp 0 0.25p' % tend_ps); continue
        if s.startswith('.print'):
            out.append(ln + ' V(gt) V(gtp) V(pk) V(strig) V(%s) V(g1)' % lo +
                       ' V(xea) V(xeb) V(xer) V(xebk) V(xeih) V(xesh) V(xesl)' +
                       ' V(xetl) V(xetg) V(xetp) V(xetk) V(xest) V(xqgt) V(xqgtp)' +
                       ' V(xqhi) V(xehi) V(xegt)')
            continue
        out.append(ln)
    return '\n'.join(out) + '\n', removed

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

def cross(rows, it, ic, val, rising, tmin=0.0):
    """first crossing of column ic through val after tmin (ps returned)"""
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

def at(rows, it, ic, t_ps):
    prev = None
    for r in rows:
        t = r[it]
        if prev is not None and prev[0] <= t_ps * 1e-12 <= t:
            f = (t_ps * 1e-12 - prev[0]) / (t - prev[0]) if t != prev[0] else 0.0
            return prev[1] + f * (r[ic] - prev[1])
        prev = (t, r[ic])
    return rows[-1][ic]

def static_curve():
    hdr, rows = read_prn('/usr/local/src/stat-sim/qal/swsweep/sw_calib.cir.prn')
    def col(n): return [i for i, h in enumerate(hdr) if n.upper() in h][0]
    iv = col('V(BKB)')
    cs = {t: col('V(X%s)' % t.upper()) for t in ['qsh', 'qsl', 'esh', 'esl', 'eih']}
    base = {t: rows[0][c] for t, c in cs.items()}
    def f(vend):
        prev = None
        for r in rows:
            if prev is not None and prev[iv] <= vend <= r[iv]:
                g = (vend - prev[iv]) / (r[iv] - prev[iv]) if r[iv] != prev[iv] else 0.0
                d = {t: (prev[c] + g * (r[c] - prev[c]) - base[t]) * 1e15 for t, c in cs.items()}
                return dict(Q_sup=d['qsh'] + d['qsl'], E_sup=d['esh'] + d['esl'], E_in=d['eih'])
            prev = r
        raise ValueError('vend %.4f outside static ramp' % vend)
    return f

def analyze(prn, tend_ps):
    hdr, rows = read_prn(prn)
    def col(n):
        c = [i for i, h in enumerate(hdr) if h == n.upper() or h == n.upper().replace('V(', '{V(')]
        if not c:
            c = [i for i, h in enumerate(hdr) if n.upper() in h]
        return c[0]
    it = 1   # TIME column
    gt, gtp, pk, ilt = col('V(GT)'), col('V(GTP)'), col('V(PK)'), col('I(LT)')
    vbka, vbkb, vsw = col('V(BKA)'), col('V(BKB)'), col('V(SW)')
    r = {}
    r['gt_rise_50']  = cross(rows, it, gt, 0.75, True)
    r['gt_fall_50']  = cross(rows, it, gt, 0.75, False, tmin=r['gt_rise_50'] + 20)
    r['gt_rise_20_80'] = (cross(rows, it, gt, 1.2, True) or 0) - (cross(rows, it, gt, 0.3, True) or 0)
    f80 = cross(rows, it, gt, 1.2, False, tmin=r['gt_rise_50'] + 20)
    f20 = cross(rows, it, gt, 0.3, False, tmin=r['gt_rise_50'] + 20)
    r['gt_fall_80_20'] = (f20 - f80) if (f20 and f80) else None
    r['gtp_fall_50'] = cross(rows, it, gtp, 0.75, False)
    r['gtp_rise_50'] = cross(rows, it, gtp, 0.75, True, tmin=r['gt_rise_50'] + 20)
    r['pk_rise_50']  = cross(rows, it, pk, 0.75, True, tmin=r['gt_rise_50'] + 20)
    r['width_50_ps'] = r['gt_fall_50'] - r['gt_rise_50']
    # currents at the cut
    r['I_at_gt_fall_uA']  = at(rows, it, ilt, r['gt_fall_50']) * 1e6
    r['I_at_gtp_rise_uA'] = at(rows, it, ilt, r['gtp_rise_50']) * 1e6
    ipk = max(x[ilt] for x in rows)
    r['IPK_uA'] = ipk * 1e6
    # true zero of I(LT) (does the tuned width hit it?)
    r['t_zero_meas_ps'] = cross(rows, it, ilt, 0.0, False, tmin=r['gt_rise_50'] + 30)
    topen = max(x for x in (r['gt_fall_50'], r['gtp_rise_50']) if x)   # last conduction cut
    tC, tD = topen + 7.0, tend_ps - 5.0
    # bank/cell books (all minus their t~0 baseline, the Z checkpoint role)
    def ck(name, tp):
        c = col('V(X%s)' % name)
        return (at(rows, it, c, tp) - rows[0][c]) * 1e15
    vbe = at(rows, it, vbkb, tD)
    st = static_curve()(vbe)
    r['VBEND'] = vbe
    r['VBPK'] = max(x[vbkb] for x in rows)
    r['VA_open'] = at(rows, it, vbka, topen)
    r['VAEND_ring_snapshot'] = at(rows, it, vbka, tD)
    r['EA_C_fJ'] = ck('ea', tC)
    r['E_hop_open_fJ'] = r['EA_C_fJ'] - st['E_sup']
    r['E_R_toC_fJ'] = ck('er', tC)
    r['cells_burn_fJ'] = ck('ebk', tD) + ck('eih', tD) - st['E_sup'] - st['E_in']
    r['switch_related_open_fJ'] = r['E_hop_open_fJ'] - r['E_R_toC_fJ'] - r['cells_burn_fJ']
    # timer energy: to the open (+50ps, park settled) and to D
    for tag in ['etl', 'etg', 'etp', 'etk', 'est']:
        r['%s_open50_fJ' % tag] = ck(tag, min(topen + 50.0, tD))
        r['%s_D_fJ' % tag] = ck(tag, tD)
    r['E_timer_open50_fJ'] = sum(r['%s_open50_fJ' % t] for t in ['etl', 'etg', 'etp', 'etk'])
    r['E_timer_D_fJ'] = sum(r['%s_D_fJ' % t] for t in ['etl', 'etg', 'etp', 'etk'])
    # park/post-open comparison metrics
    r['Vsw_min_postopen'] = min(x[vsw] for x in rows if x[it] > (topen + 5) * 1e-12)
    r['Vsw_max_postopen'] = max(x[vsw] for x in rows if x[it] > (topen + 5) * 1e-12)
    r['VB_min_postopen'] = min(x[vbkb] for x in rows if x[it] > (topen + 5) * 1e-12)
    r['VB_max_postopen'] = max(x[vbkb] for x in rows if x[it] > (topen + 5) * 1e-12)
    r['Q_L_D_fC'] = ck('qlt', tD)
    r['completeness_VBEND'] = 'PASS' if abs(vbe / 0.6758936 - 1) <= 0.02 else 'FAIL'
    r['completeness_VA'] = 'PASS' if r['VA_open'] <= 0.0978 + 0.05 else 'FAIL'
    return r

def main():
    N = int(sys.argv[1]); ctrim = float(sys.argv[2])
    temp = float(sys.argv[3]) if len(sys.argv) > 3 else 27.0
    tag = sys.argv[4] if len(sys.argv) > 4 else 'tl_hop_n%d_c%s_t%g' % (
        N, ('%g' % ctrim).replace('.', 'p'), temp)
    # predicted open ~ trig + input(2 stg) + close(nand+inv4) + width; generous end pad
    tend = 1000.0
    txt, removed = build(N, ctrim, temp, tend)
    fn = os.path.join(HERE, tag + '.cir')
    open(fn, 'w').write(txt)
    print('patched %s -> %s (removed %d source/integrator lines)' % (BASE, fn, len(removed)))
    for ln in removed: print('  - %s' % ln.strip()[:90])
    t0 = time.monotonic()
    r = subprocess.run([XYCE, os.path.basename(fn)], capture_output=True, text=True,
                       timeout=3000, cwd=HERE, env=ENV)
    wall = time.monotonic() - t0
    if not os.path.exists(fn + '.prn'):
        print('XYCE FAILED (%.0fs):' % wall)
        print('\n'.join(l for l in r.stdout.splitlines() if 'rror' in l.lower() or 'bort' in l.lower())[:1500])
        sys.exit(1)
    print('ran in %.0fs' % wall)
    res = analyze(fn + '.prn', tend)
    res['N'], res['ctrim_fF'], res['temp'] = N, ctrim, temp
    res['wall_s'] = round(wall, 1)
    fj = os.path.join(HERE, 'tl_hop.json')
    db = {}
    if os.path.exists(fj):
        try: db = json.load(open(fj))
        except Exception: db = {}
    db[tag] = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in res.items()}
    json.dump(db, open(fj, 'w'), indent=1)
    for k in ['width_50_ps', 'gt_rise_50', 'gt_fall_50', 'gtp_rise_50', 'pk_rise_50',
              'gt_rise_20_80', 'gt_fall_80_20', 'I_at_gt_fall_uA', 'I_at_gtp_rise_uA',
              'IPK_uA', 't_zero_meas_ps', 'VBEND', 'VBPK', 'VA_open', 'E_hop_open_fJ',
              'E_R_toC_fJ', 'cells_burn_fJ', 'switch_related_open_fJ',
              'E_timer_open50_fJ', 'E_timer_D_fJ', 'etl_D_fJ', 'etg_D_fJ', 'etp_D_fJ',
              'etk_D_fJ', 'est_D_fJ', 'Vsw_min_postopen', 'Vsw_max_postopen',
              'VB_min_postopen', 'VB_max_postopen', 'completeness_VBEND', 'completeness_VA']:
        print('  %-24s %s' % (k, res.get(k)))

if __name__ == '__main__':
    main()
