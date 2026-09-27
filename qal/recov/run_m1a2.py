"""te sweep with the cut instant corrected for the raised-cosine threshold offset.
A cosine edge crosses the nMOS conduction threshold (~1.13 V for a 0.68 V bank)
at f0+0.331*te, i.e. 0.169*te BEFORE the 50% point -> the naive centring cuts
EARLY (the measured-bad direction).  dcut = +0.169*te restores it."""
import rv, drives, go
for te in (30.0, 60.0, 100.0, 133.0):
    z = go.zero_from_probe('m1a2_probe_te%d' % te, tclose=100.0, te=te)
    for frac in (0.169,):
        dc = frac*te
        tag = 'm1a2_te%d_r25_d%d' % (te, round(dc))
        r = go.hop(tag, drives.m1a_edges(tcut=z+dc, te=te, RS=25.0), show=False)
        if r is None: continue
        go._finish_m1(r, te, 25.0, z+dc); r['dcut_ps'] = dc; rv.save(tag, r)
