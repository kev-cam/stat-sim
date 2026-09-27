"""device-referenced cut order: the CUT is the LAST instant the device conducts,
not the first threshold crossing (the committed design's pMOS overdrive dips
mid-transfer as the bank fills, which is not a cut)."""
import rv, sys
VTN, VTP = 0.45, 0.50
def order(tag, tstart=None):
    hdr, rows = rv.read_prn(tag+'.cir.prn'); c = lambda n: rv.col(hdr, n)
    igt, igp, isw, ibb, ipkv, ilt = (c('V(GT)'), c('V(GTP)'), c('V(SW)'),
                                     c('V(BKB)'), c('V(PK)'), c('I(LT)'))
    peak = max(range(len(rows)), key=lambda i: rows[i][igt])
    tn = tp = None; tk = None; zero = None; prev = None
    for i, r in enumerate(rows):
        t = r[1]*1e12; s = max(r[isw], r[ibb])
        if i > peak:
            if r[igt]-s > VTN: tn = t          # last conducting instant
            if s-r[igp] > VTP: tp = t
            if tk is None and r[ipkv] > VTN: tk = t
            if prev is not None and zero is None and prev > 0 >= r[ilt]: zero = t
        prev = r[ilt]
    return dict(zero=zero, nmos_cut=tn, pmos_cut=tp, park_close=tk,
                pmos_vs_nmos=(tp-tn) if (tn and tp) else None,
                park_vs_nmos=(tk-tn) if (tn and tk) else None,
                cut_vs_zero=(tn-zero) if (tn and zero) else None)
if __name__ == '__main__':
    print('  %-22s %8s %8s %8s %8s %10s %10s %9s' % ('row','zero','nMOScut','pMOScut',
          'park','pMOS-nMOS','park-nMOS','cut-zero'))
    for tag in sys.argv[1:]:
        o = order(tag)
        f = lambda x: -999 if x is None else x
        print('  %-22s %8.1f %8.1f %8.1f %8.1f %+10.1f %+10.1f %+9.1f  %s' % (tag,
              f(o['zero']), f(o['nmos_cut']), f(o['pmos_cut']), f(o['park_close']),
              f(o['pmos_vs_nmos']), f(o['park_vs_nmos']), f(o['cut_vs_zero']),
              'ORDER PASS' if (o['pmos_vs_nmos'] is not None and o['pmos_vs_nmos'] <= 5.0
                               and o['park_vs_nmos'] is not None and o['park_vs_nmos'] >= 0)
              else 'ORDER FAIL'))
