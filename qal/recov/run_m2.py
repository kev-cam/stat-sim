"""M2: n-step adiabatic capacitive charging WITH the step-switch gate drives counted
at the conventional rate (the recursion trap the brief names)."""
import math, rv, drives, go
te = 133.0
for n, wn, wp in ((2, 0.74, 1.12), (4, 0.74, 1.12)):
    z = go.zero_from_probe('m2_probe_n%d' % n, tclose=100.0, te=te, steps=n)
    j = math.floor(0.2467*n) + 1               # first fall step below the nMOS threshold
    dc = te/2.0 - j*te/n                       # push the cut to the measured zero
    tag = 'm2_n%d' % n
    d = drives.m2_stepwise(n=n, tcut=z+dc, te=te, wn=wn, wp=wp)
    r = go.hop(tag, d, show=(n == 2))
    if r is None: continue
    r['n'], r['te_ps'], r['dcut_ps'], r['wn'], r['wp'] = n, te, dc, wn, wp
    r['Q_pk_fC'] /= 2.0
    r['E_park_conventional_fJ'] = r['Q_pk_fC']*1.5
    r['E_net_sources_fJ'] = r['E_drive_sources_fJ'] - r['E_pk_fJ']
    r['E_drive_total_fJ'] = (r['E_net_sources_fJ'] + r['E_tank_deficit_fJ']
                             + r['E_aux_conventional_fJ'] + r['E_park_conventional_fJ'])
    r['eta_pct'] = 100*rv.eta(r['E_drive_total_fJ']); r['N_min'] = rv.n_min(r['E_drive_total_fJ'])
    print('  n=%d ts=%.1f ps | E_drive %8.3f = rails %+.3f + tankdef %+.3f + STEPSW %.3f'
          ' + park %.3f fJ | eta %8.2f%% | N_min %8.1f'
          % (n, te/n, r['E_drive_total_fJ'], r['E_net_sources_fJ'], r['E_tank_deficit_fJ'],
             r['E_aux_conventional_fJ'], r['E_park_conventional_fJ'], r['eta_pct'], r['N_min']))
    print('      VBEND %.5f %s VA %.4f %s E_hop %.3f %s cells %s order %s [%s]'
          % (r['VBEND'], r['completeness_VBEND'], r['VA_open'], r['completeness_VA'],
             r['E_hop_open_fJ'], r['completeness_Ehop'], r['cells_settled'],
             r['cut_order'], r['order_detail']))
    for k in sorted(r):
        if k.startswith('aux_') or k.startswith('tank_'): print('      %-22s %s' % (k, r[k]))
    rv.save(tag, r)
