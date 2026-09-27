"""Interpolated gtp advance: VBEND = 0.68068 + 9.33e-4*adv and pMOS-nMOS = 7.4 - 0.775*adv
(both linear in adv over the measured 0/12/24 ps rows), so adv in [3.1, 9.4] ps satisfies
BOTH the pre-registered two-sided VBEND band and the pMOS-cuts-early rule."""
import rv, drives, go, cutorder
for adv in (6.0, 8.0):
    tag = 'm1d_h5b580_adv%d' % adv
    d = drives.m1d_harmonic(beat=580.0, nh=5, RS=25.0, off_gt=0.85, amp_gt=0.75,
                            off_gp=0.41, amp_gp=0.75, adv_ps=adv)
    r = go.hop(tag, d, tend=580.0, td=580.0*0.96, te_meter=580.0, show=False)
    if r is None: continue
    for k in ('gt','gtp','pk'): r['Q_%s_fC' % k] /= 2.0
    r['E_drive_recovered_fJ'] = r['E_gt_fJ'] + r['E_gtp_fJ']
    r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
    r['E_drive_total_fJ'] = r['E_drive_recovered_fJ'] + r['E_park_conventional_fJ']
    r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ']); r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
    r['adv_ps'] = adv; r['beat_ps'] = 580.0; r['nh'] = 5; r['RS_ohm'] = 25.0
    o = cutorder.order(tag); r['order_device_ref'] = o
    r['cut_order'] = 'PASS' if (o['pmos_vs_nmos'] <= 5.0 and o['park_vs_nmos'] >= 0) else 'FAIL'
    print('  adv=%-4g | E_drive %7.3f fJ (gt %+.3f gtp %+.3f park %.3f) | eta %6.2f%% | '
          'N_min %6.1f || VBEND %.5f %s | VA %.4f %s | E_hop %.3f %s | cells %s | '
          'order %s (pMOS %+.1f park %+.1f cut-zero %+.1f)'
          % (adv, r['E_drive_total_fJ'], r['E_gt_fJ'], r['E_gtp_fJ'],
             r['E_park_conventional_fJ'], r['eta_pct'], r['N_min'], r['VBEND'],
             r['completeness_VBEND'], r['VA_open'], r['completeness_VA'],
             r['E_hop_open_fJ'], r['completeness_Ehop'], r['cells_settled'],
             r['cut_order'], o['pmos_vs_nmos'], o['park_vs_nmos'], o['cut_vs_zero']))
    rv.save(tag, r)
