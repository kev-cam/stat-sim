import rv, drives, go
te = 133.0
z = go.zero_from_probe('b2_probe_te%d' % te, tclose=100.0, te=te)
dc = 0.169*te
print('--- M1-A corrected-cut RS sweep (cut-order limit) ---')
for rs in (200.0, 560.0, 1000.0):
    tag = 'm1a2_te%d_r%d' % (te, rs)
    r = go.hop(tag, drives.m1a_edges(tcut=z+dc, te=te, RS=rs), show=False)
    if r: go._finish_m1(r, te, rs, z+dc); r['dcut_ps']=dc; rv.save(tag, r)
print('--- M1-C: the SAME edges through a REAL freeze TG + 4 real clamps ---')
for wfn, wfp in ((0.74, 1.12), (5.0, 10.0)):
    tag = 'm1c_te%d_w%03d' % (te, wfn*100)
    d = drives.m1c_freeze(tcut=z+dc, te=te, RS=25.0, wfn=wfn, wfp=wfp)
    r = go.hop(tag, d, show=(wfn == 0.74))
    if r is None: continue
    for k in ('gt','gtp','pk','afn','afp','bfn','bfp','cal','cah','cbl','cbh'):
        kk = 'Q_%s_fC' % k
        if kk in r: r[kk] /= 2.0
    r['te_ps'], r['RS_ohm'], r['wfn'], r['wfp'] = te, 25.0, wfn, wfp
    r['E_drive_recovered_fJ'] = r['E_gt_fJ'] + r['E_gtp_fJ']
    r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
    r['E_drive_total_fJ'] = (r['E_drive_recovered_fJ'] + r['E_park_conventional_fJ']
                             + r['E_aux_conventional_fJ'])
    r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ']); r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
    print('  freeze %g/%gum | E_drive %8.3f = resonator %.3f + park %.3f + AUX %.3f fJ'
          ' | eta %7.2f%% | N_min %7.1f | VBEND %.5f %s VA %.4f %s E_hop %.3f %s cells %s order %s'
          % (wfn, wfp, r['E_drive_total_fJ'], r['E_drive_recovered_fJ'],
             r['E_park_conventional_fJ'], r['E_aux_conventional_fJ'], r['eta_pct'],
             r['N_min'], r['VBEND'], r['completeness_VBEND'], r['VA_open'],
             r['completeness_VA'], r['E_hop_open_fJ'], r['completeness_Ehop'],
             r['cells_settled'], r['cut_order']))
    for k in sorted(r):
        if k.startswith('aux_'): print('      %-16s %7.3f fJ' % (k, r[k]))
    rv.save(tag, r)
