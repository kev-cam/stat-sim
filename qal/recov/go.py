#!/usr/bin/env python3
"""Runner for the gate-charge recovery round.  Stages are independent so each can
be re-run: g2 | m3 | ctrl | m1a | m1b | m1c | m2   (see PRE_REGISTERED.json)."""
import os, sys, json, math
import rv, drives

Q_PK_COST = rv.Q_PK * 1.5          # fJ, the park charged conventionally (never recovered)

def hop(tag, drv, tend=816.755, VGH=1.5, td=None, te_meter=None, tprint=0.1,
        show=True):
    lines, pc, dt, qt, aux, tanks = drv
    txt, removed = rv.build(lines, pc, tend, tprint=tprint)
    prn, wall = rv.run(tag, txt)
    if not prn: return None
    if show:
        print('    patch removed %d committed lines:' % len(removed))
        for l in removed: print('      - %s' % l.strip()[:86])
    r = rv.analyze(prn, VGH=VGH, drive_tags=dt, q_tags=qt, tank_caps=tanks, aux=aux,
                   td=td, te_meter=te_meter)
    if r is None: print('    ANALYZE FAILED'); return None
    r['wall_s'] = round(wall, 1); r['tag'] = tag; r['VGH'] = VGH
    return r

def zero_from_probe(tag, VGH=1.5, tclose=50.0, te=None, steps=0):
    d = drives.probe(VGH=VGH, tclose=tclose, te=te, steps=steps)
    lines, pc, dt, qt, aux, tanks = d
    txt, _ = rv.build(lines, pc, 816.755)
    prn, wall = rv.run(tag, txt)
    if not prn: return None
    hdr, rows = rv.read_prn(prn)
    z = rv.cross(rows, rv.col(hdr, 'I(LT)'), 0.0, False, tmin=tclose+30)
    ipk = max(x[rv.col(hdr,'I(LT)')] for x in rows)*1e6
    print('    probe %s: true I(LT) zero = %.3f ps (%.3f after close), IPK %.2f uA'
          % (tag, z, z-tclose, ipk))
    return z

# ---------------------------------------------------------------- G2 real-drive
def stage_g2():
    """re-run the committed real-drive timer row as instrument gate G2"""
    sys.path.insert(0, '/usr/local/src/stat-sim/qal/timer')
    import importlib.util
    spec = importlib.util.spec_from_file_location('tlh', '/usr/local/src/stat-sim/qal/timer/tl_hop.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.HERE = rv.HERE; m.CACHE = rv.CACHE
    m.ENV = dict(os.environ, PYMS_DIR='/usr/local/share/xyce/PyMS', PYMS_VAE_CACHE=rv.CACHE)
    txt, removed = m.build(7, 25.0, 27.0, 1000.0)
    open(os.path.join(rv.HERE, 'g2_real_drive.cir'), 'w').write(txt)
    print('  G2: patched committed swsweep deck, removed %d lines' % len(removed))
    for l in removed: print('    - %s' % l.strip()[:86])
    prn, wall = rv.run('g2_real_drive', txt, timeout=900)
    if not prn: return None
    r = m.analyze(prn, 1000.0)
    keys = [('E_hop_open_fJ', 8.10914, 0.5), ('VBEND', 0.68463, 0.2),
            ('VA_open', 0.10782, 2.0), ('cells_burn_fJ', 1.92709, 1.0),
            ('E_timer_D_fJ', 399.84214, 1.0), ('etg_D_fJ', 118.04088, 1.0),
            ('etp_D_fJ', 109.79661, 1.0), ('etk_D_fJ', 75.00454, 1.0),
            ('etl_D_fJ', 97.00011, 1.0), ('est_D_fJ', 5.41006, 1.0),
            ('width_50_ps', 269.8418, 1.0), ('gt_rise_20_80', 30.53816, 3.0)]
    ok = True
    print('  %-18s %14s %14s %9s %s' % ('metric','committed','re-run','delta%','gate'))
    for k, c, tol in keys:
        v = r[k]; d = 100*(v/c-1); p = abs(d) <= tol; ok &= p
        print('  %-18s %14.6g %14.6g %+8.3f%%  %s (tol %.1f%%)'
              % (k, c, v, d, 'PASS' if p else 'FAIL', tol))
    print('  G2 VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    r['G2_verdict'] = 'PASS' if ok else 'FAIL'
    rv.save('g2_real_drive', r)
    taps = r['etg_D_fJ']+r['etp_D_fJ']+r['etk_D_fJ']
    print('  tap total %.1f fJ (committed 302.8) | line %.1f (97.0) | trigger %.2f (5.41)'
          % (taps, r['etl_D_fJ'], r['est_D_fJ']))
    return r

# ---------------------------------------------------------------- control row
def stage_ctrl():
    """ideal-PWL control at the committed close (50 ps) and at the shifted close
    (100 ps) used by every slow-edge row, so the shift is shown to be immaterial."""
    out = {}
    for tcl in (50.0, 100.0):
        z = zero_from_probe('ctrl_probe_t%d' % tcl, tclose=tcl)
        r = hop('ctrl_ideal_t%d' % tcl,
                drives.ideal_pwl(tclose=tcl, tcut=z), show=(tcl == 50.0))
        r['t_close'] = tcl; r['t_zero_probe'] = z
        r['E_drive_ideal_floor_fJ'] = r['E_drive_sources_fJ']
        r['Q_gt_fC'] = r['Q_gt_fC']/2.0    # rectified -> one-way charge
        r['Q_gtp_fC'] = r['Q_gtp_fC']/2.0
        r['Q_pk_fC'] = r['Q_pk_fC']/2.0
        r['CV2_conv_fJ'] = (r['Q_gt_fC']+r['Q_gtp_fC']+r['Q_pk_fC'])*1.5
        rv.show(r); print('    Q_gt %.3f Q_gtp %.3f Q_pk %.3f fC -> CV2_conv %.3f fJ; '
                          'ideal floor %.3f fJ'
              % (r['Q_gt_fC'], r['Q_gtp_fC'], r['Q_pk_fC'], r['CV2_conv_fJ'],
                 r['E_drive_ideal_floor_fJ']))
        rv.save('ctrl_ideal_t%d' % tcl, r); out[tcl] = r
    return out

# ---------------------------------------------------------------- M3 VGH sweep
def stage_m3(vghs=(1.5, 1.35, 1.2, 1.05)):
    res = {}
    for v in vghs:
        t = ('%g' % v).replace('.', 'p')
        z = zero_from_probe('m3_probe_%s' % t, VGH=v, tclose=50.0)
        if z is None: continue
        r = hop('m3_hop_%s' % t, drives.ideal_pwl(VGH=v, tcut=z), VGH=v, show=False)
        if r is None: continue
        r['t_zero_probe'] = z
        for k in ('gt','gtp','pk'): r['Q_%s_fC' % k] /= 2.0
        r['CV2_conv_fJ'] = (r['Q_gt_fC']+r['Q_gtp_fC']+r['Q_pk_fC'])*v
        r['E_drive_ideal_floor_fJ'] = r['E_drive_sources_fJ']
        r['N_min_at_CV2'] = rv.n_min(r['CV2_conv_fJ'])
        print('  VGH=%.2f  zero %.1f ps | Q %.2f/%.2f/%.2f fC  CV2_conv %.2f fJ '
              '| VBEND %.5f (%s) VA_open %.4f (%s) E_hop %.3f (%s) cells %s'
              % (v, z, r['Q_gt_fC'], r['Q_gtp_fC'], r['Q_pk_fC'], r['CV2_conv_fJ'],
                 r['VBEND'], r['completeness_VBEND'], r['VA_open'], r['completeness_VA'],
                 r['E_hop_open_fJ'], r['completeness_Ehop'], r['cells_settled']))
        rv.save('m3_hop_%s' % t, r); res[v] = r
    return res

# ---------------------------------------------------------------- M1-A adiabatic
def stage_m1a(tes=(133.0,), rss=(10.0, 50.0, 200.0, 1000.0), extra_te=()):
    res = {}
    zcache = {}
    for te in list(tes)+list(extra_te):
        if te not in zcache:
            zcache[te] = zero_from_probe('m1a_probe_te%d' % te, tclose=100.0, te=te)
    for te in tes:
        for rs in rss:
            tag = 'm1a_te%d_r%d' % (te, rs)
            r = hop(tag, drives.m1a_edges(tcut=zcache[te], te=te, RS=rs),
                    show=(te == tes[0] and rs == rss[0]))
            if r is None: continue
            _finish_m1(r, te, rs, zcache[te]); rv.save(tag, r); res[tag] = r
    for te in extra_te:
        rs = 50.0
        tag = 'm1a_te%d_r%d' % (te, rs)
        r = hop(tag, drives.m1a_edges(tcut=zcache[te], te=te, RS=rs), show=False)
        if r is None: continue
        _finish_m1(r, te, rs, zcache[te]); rv.save(tag, r); res[tag] = r
    return res

def _finish_m1(r, te, rs, z):
    for k in ('gt','gtp','pk'): r['Q_%s_fC' % k] /= 2.0
    r['te_ps'], r['RS_ohm'], r['t_zero_probe'] = te, rs, z
    # gt+gtp are the recovered nodes; pk is charged conventionally
    r['E_drive_recovered_fJ'] = r['E_gt_fJ'] + r['E_gtp_fJ']
    r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
    r['E_drive_total_fJ'] = r['E_drive_recovered_fJ'] + r['E_park_conventional_fJ'] \
                            + r.get('E_aux_conventional_fJ', 0.0)
    r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ'])
    r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
    print('  te=%-5g RS=%-6g | E_drive %7.3f fJ (gt %.3f gtp %.3f park %.3f aux %.3f) '
          '| eta %6.2f%% | N_min %6.1f | VBEND %.5f %s VA %.4f %s E_hop %.3f %s '
          'cells %s order %s [%s] edge %.1f/%.1f ps %s'
          % (te, rs, r['E_drive_total_fJ'], r['E_gt_fJ'], r['E_gtp_fJ'],
             r['E_park_conventional_fJ'], r.get('E_aux_conventional_fJ', 0.0),
             r['eta_pct'], r['N_min'], r['VBEND'], r['completeness_VBEND'],
             r['VA_open'], r['completeness_VA'], r['E_hop_open_fJ'],
             r['completeness_Ehop'], r['cells_settled'], r['cut_order'],
             r['order_detail'], r['gt_rise_20_80'] or -1, r['gt_fall_80_20'] or -1,
             r['T_edge_budget']))

# ---------------------------------------------------------------- M1-B sine
def stage_m1b(rows=((534.0, 0.0, 25.0, None, None),)):
    res = {}
    for beat, adv, rs, amp, off in rows:
        tag = 'm1b_b%d_a%d_r%d%s' % (beat, adv, rs,
              ('' if amp is None else '_A%d' % round(amp*100)))
        tcut = beat*0.75
        d = drives.m1b_sine(beat=beat, adv_deg=adv, RS=rs, amp=amp, off=off,
                            tpk=tcut+6)
        r = hop(tag, d, tend=beat, td=beat*0.96, te_meter=beat, show=(not res))
        if r is None: continue
        for k in ('gt','gtp','pk'): r['Q_%s_fC' % k] /= 2.0
        r['beat_ps'], r['adv_deg'], r['RS_ohm'] = beat, adv, rs
        r['E_drive_recovered_fJ'] = r['E_gt_fJ'] + r['E_gtp_fJ']
        r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
        r['E_drive_total_fJ'] = r['E_drive_recovered_fJ'] + r['E_park_conventional_fJ']
        r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ'])
        r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
        print('  beat=%-6g adv=%-5g RS=%-6g | E_drive %7.3f fJ (gt %.3f gtp %.3f '
              'park %.3f) | eta %6.2f%% | N_min %6.1f | VBEND %.5f %s VA %.4f %s '
              'E_hop %.3f %s cells %s order %s [%s] window50 %.1f ps'
              % (beat, adv, rs, r['E_drive_total_fJ'], r['E_gt_fJ'], r['E_gtp_fJ'],
                 r['E_park_conventional_fJ'], r['eta_pct'], r['N_min'], r['VBEND'],
                 r['completeness_VBEND'], r['VA_open'], r['completeness_VA'],
                 r['E_hop_open_fJ'], r['completeness_Ehop'], r['cells_settled'],
                 r['cut_order'], r['order_detail'], r['width_50_ps'] or -1))
        rv.save(tag, r); res[tag] = r
    return res

# ---------------------------------------------------------------- M1-C freeze
def stage_m1c(te=133.0, rs=25.0, sizes=((4.0, 8.0), (1.0, 2.0))):
    res = {}
    z = zero_from_probe('m1c_probe_te%d' % te, tclose=100.0, te=te)
    for wfn, wfp in sizes:
        tag = 'm1c_te%d_w%d' % (te, wfn*10)
        r = hop(tag, drives.m1c_freeze(tcut=z, te=te, RS=rs, wfn=wfn, wfp=wfp),
                show=(not res))
        if r is None: continue
        for k in ('gt','gtp','pk','afn','afp','bfn','bfp','ch','cl'):
            if 'Q_%s_fC' % k in r: r['Q_%s_fC' % k] /= 2.0
        r['te_ps'], r['RS_ohm'], r['wfn'], r['wfp'] = te, rs, wfn, wfp
        r['E_drive_recovered_fJ'] = r['E_gt_fJ'] + r['E_gtp_fJ']
        r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
        r['E_drive_total_fJ'] = (r['E_drive_recovered_fJ'] + r['E_park_conventional_fJ']
                                 + r['E_aux_conventional_fJ'])
        r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ'])
        r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
        print('  freeze %g/%gum | E_drive %7.3f = net %.3f + park %.3f + AUX %.3f fJ '
              '| eta %6.2f%% | N_min %6.1f | VBEND %.5f %s VA %.4f %s E_hop %.3f %s '
              'cells %s order %s'
              % (wfn, wfp, r['E_drive_total_fJ'], r['E_drive_recovered_fJ'],
                 r['E_park_conventional_fJ'], r['E_aux_conventional_fJ'],
                 r['eta_pct'], r['N_min'], r['VBEND'], r['completeness_VBEND'],
                 r['VA_open'], r['completeness_VA'], r['E_hop_open_fJ'],
                 r['completeness_Ehop'], r['cells_settled'], r['cut_order']))
        for k in ('sw_afn','sw_afp','sw_bfn','sw_bfp','sw_ch','sw_cl'):
            if 'aux_%s_fJ' % k in r: print('      aux %-8s %.3f fJ' % (k, r['aux_%s_fJ' % k]))
        rv.save(tag, r); res[tag] = r
    return res

# ---------------------------------------------------------------- M2 stepwise
def stage_m2(ns=(2, 4, 8), te=133.0, wn=1.0, wp=2.0):
    res = {}
    z = zero_from_probe('m2_probe_te%d' % te, tclose=100.0, te=te)
    for n in ns:
        tag = 'm2_n%d_te%d' % (n, te)
        r = hop(tag, drives.m2_stepwise(n=n, tcut=z, te=te, wn=wn, wp=wp),
                show=(not res))
        if r is None: continue
        for k in list(r):
            pass
        r['n'], r['te_ps'] = n, te
        r['Q_pk_fC'] = r['Q_pk_fC']/2.0
        r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
        # sources: top rail + tanks (+ pk ideal, replaced by the conventional park)
        r['E_net_sources_fJ'] = r['E_drive_sources_fJ'] - r['E_epk_fJ']
        r['E_drive_total_fJ'] = (r['E_net_sources_fJ'] + r['E_tank_deficit_fJ']
                                 + r['E_aux_conventional_fJ']
                                 + r['E_park_conventional_fJ'])
        r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ'])
        r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
        print('  n=%d ts=%.1f ps | E_drive %8.3f = rails %.3f + tankdef %.3f + '
              'STEPSW %.3f + park %.3f fJ | eta %7.2f%% | N_min %7.1f'
              % (n, te/n, r['E_drive_total_fJ'], r['E_net_sources_fJ'],
                 r['E_tank_deficit_fJ'], r['E_aux_conventional_fJ'],
                 r['E_park_conventional_fJ'], r['eta_pct'], r['N_min']))
        print('      VBEND %.5f %s VA %.4f %s E_hop %.3f %s cells %s order %s [%s] '
              'edge %.1f/%.1f ps'
              % (r['VBEND'], r['completeness_VBEND'], r['VA_open'],
                 r['completeness_VA'], r['E_hop_open_fJ'], r['completeness_Ehop'],
                 r['cells_settled'], r['cut_order'], r['order_detail'],
                 r['gt_rise_20_80'] or -1, r['gt_fall_80_20'] or -1))
        for k in sorted(r):
            if k.startswith('aux_') or k.startswith('tank_'): print('      %s = %s' % (k, r[k]))
        rv.save(tag, r); res[tag] = r
    return res

if __name__ == '__main__':
    st = sys.argv[1]
    print('=== stage %s ===' % st)
    if st == 'g2':   stage_g2()
    elif st == 'ctrl': stage_ctrl()
    elif st == 'm3': stage_m3()
    elif st == 'm1a': stage_m1a(extra_te=(60.0, 267.0))
    elif st == 'm1b': stage_m1b()
    elif st == 'm1c': stage_m1c()
    elif st == 'm2': stage_m2(ns=tuple(int(x) for x in sys.argv[2].split(','))
                              if len(sys.argv) > 2 else (2, 4, 8))
    else: print('unknown stage')
