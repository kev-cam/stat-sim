"""M1-B: the free-running (UNSWITCHED) resonant network -- zero per-edge switch
cost by construction.  Rows: (1) the naive 0..1.5 anti-phase pair; (2) each tap
centred on ITS OWN switch threshold so the above-threshold window equals half
the beat; (3) the same at higher series R."""
import rv, drives, go
ROWS = [
 ('plain',   dict(off_gt=0.75, amp_gt=0.75, off_gp=0.75, amp_gp=0.75, RS=25.0)),
 ('thctr',   dict(off_gt=1.13, amp_gt=0.75, off_gp=0.18, amp_gp=0.75, RS=25.0)),
 ('thctr200',dict(off_gt=1.13, amp_gt=0.75, off_gp=0.18, amp_gp=0.75, RS=200.0)),
 ('thctr_a20',dict(off_gt=1.13, amp_gt=0.75, off_gp=0.18, amp_gp=0.75, RS=25.0, adv_deg=20.0)),
]
beat = 534.0
for name, kw in ROWS:
    tag = 'm1b_%s' % name
    d = drives.m1b_sine2(beat=beat, tpk=beat*0.77, **kw)
    r = go.hop(tag, d, tend=beat, td=beat*0.955, te_meter=beat, show=(name=='plain'))
    if r is None: continue
    for k in ('gt','gtp','pk'): r['Q_%s_fC' % k] /= 2.0
    r.update(row=name, beat_ps=beat, **kw)
    r['E_drive_recovered_fJ'] = r['E_gt_fJ'] + r['E_gtp_fJ']
    r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
    r['E_drive_total_fJ'] = r['E_drive_recovered_fJ'] + r['E_park_conventional_fJ']
    r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ']); r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
    print('  %-10s | E_drive %7.3f fJ (gt %+.3f gtp %+.3f park %.3f) | eta %6.2f%% | '
          'N_min %6.1f | VBEND %.5f %s VA %.4f %s E_hop %.3f %s cells %s order %s [%s] '
          'win50 %s ps zero %s'
          % (name, r['E_drive_total_fJ'], r['E_gt_fJ'], r['E_gtp_fJ'],
             r['E_park_conventional_fJ'], r['eta_pct'], r['N_min'], r['VBEND'],
             r['completeness_VBEND'], r['VA_open'], r['completeness_VA'],
             r['E_hop_open_fJ'], r['completeness_Ehop'], r['cells_settled'],
             r['cut_order'], r['order_detail'],
             None if r['width_50_ps'] is None else round(r['width_50_ps'],1),
             None if r['t_zero_meas_ps'] is None else round(r['t_zero_meas_ps'],1)))
    rv.save(tag, r)
