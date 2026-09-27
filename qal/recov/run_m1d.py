"""M1-D: the free-running MULTI-HARMONIC resonant network -- the architecture that
has NO per-edge switch (so no recursion) AND a flat-topped waveform whose fall is
fast enough for the park to close on time.  This is the row the whole verdict
hangs on."""
import rv, drives, go
beat = 534.0
ROWS = [
 ('h3',    dict(nh=3, off_gt=0.90, amp_gt=0.75, off_gp=0.41, amp_gp=0.75, RS=25.0)),
 ('h5',    dict(nh=5, off_gt=0.85, amp_gt=0.75, off_gp=0.41, amp_gp=0.75, RS=25.0)),
 ('h5r200',dict(nh=5, off_gt=0.85, amp_gt=0.75, off_gp=0.41, amp_gp=0.75, RS=200.0)),
 ('h5b580',dict(nh=5, off_gt=0.85, amp_gt=0.75, off_gp=0.41, amp_gp=0.75, RS=25.0, beat=580.0)),
]
for name, kw in ROWS:
    b = kw.pop('beat', beat)
    tag = 'm1d_%s' % name
    d = drives.m1d_harmonic(beat=b, **kw)
    r = go.hop(tag, d, tend=b, td=b*0.96, te_meter=b, show=(name == 'h3'))
    if r is None: continue
    for k in ('gt','gtp','pk'): r['Q_%s_fC' % k] /= 2.0
    r.update(row=name, beat_ps=b, **kw)
    r['E_drive_recovered_fJ'] = r['E_gt_fJ'] + r['E_gtp_fJ']
    r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
    r['E_drive_total_fJ'] = r['E_drive_recovered_fJ'] + r['E_park_conventional_fJ']
    r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ']); r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
    print('  %-8s beat=%-5g | E_drive %7.3f fJ (gt %+.3f gtp %+.3f park %.3f) | eta %6.2f%%'
          ' | N_min %6.1f | VBEND %.5f %s VA %.4f %s E_hop %.3f %s cells %s order %s [%s] zero %s'
          % (name, b, r['E_drive_total_fJ'], r['E_gt_fJ'], r['E_gtp_fJ'],
             r['E_park_conventional_fJ'], r['eta_pct'], r['N_min'], r['VBEND'],
             r['completeness_VBEND'], r['VA_open'], r['completeness_VA'],
             r['E_hop_open_fJ'], r['completeness_Ehop'], r['cells_settled'],
             r['cut_order'], r['order_detail'],
             None if r['t_zero_meas_ps'] is None else round(r['t_zero_meas_ps'],1)))
    rv.save(tag, r)
