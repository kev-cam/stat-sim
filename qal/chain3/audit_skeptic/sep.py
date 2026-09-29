#!/usr/bin/env python3
"""Two INDEPENDENT criteria the campaign did not use, computed from raw .prn:
  (1) LOGIC SEPARATION at each bank's checkpoint: (min UP output - max DN output).
      A bank that "settles 35%" but whose UP and DN outputs are 6 mV apart is
      carrying no information at all -- the settling ratio hides that.
  (2) HIGH-LEVEL DELIVERED TO THE SUCCESSOR: bank k's UP output at the instant
      bank k+1 is evaluating, compared with the successor nMOS Vtn. This is the
      direct measurement of the failure mechanism; A1 only sees its symptom.
"""
import sys, os, re, glob, bisect, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from police import load_prn, at, ckpts

VTN = 0.5239   # MEASURED, chain3/vt.json - re-verified independently below
VTP = 0.4403

M = 8


def kinds(k):
    # bank1 even cell -> input 1 -> pull-DOWN ; every bank inverts
    return ['DN' if ((i % 2 == 0) == (k in (1, 3))) else 'UP' for i in range(M)]


def row(cir, prn):
    cp = ckpts(cir)
    cols, rows, t = load_prn(prn)
    out = {'cir': os.path.basename(cir)}
    for k, key in ((1, 'K1'), (2, 'K2'), (3, 'K3')):
        tq = cp[key] * 1e-12
        rail = at(cols, rows, t, 'V(RAIL%d)' % k, tq)
        kk = kinds(k)
        ups = [at(cols, rows, t, 'V(O%d_%d)' % (k, i), tq) for i in range(M) if kk[i] == 'UP']
        dns = [at(cols, rows, t, 'V(O%d_%d)' % (k, i), tq) for i in range(M) if kk[i] == 'DN']
        out['b%d' % k] = {'t_ps': cp[key], 'rail': rail,
                          'UP_min': min(ups), 'DN_max': max(dns),
                          'sep_V': min(ups) - max(dns),
                          'sep_pct_rail': 100.0 * (min(ups) - max(dns)) / rail}
    # HIGH level handed forward: bank k UP output at bank k+1's checkpoint
    for k in (1, 2):
        tq = cp['K%d' % (k + 1)] * 1e-12
        kk = kinds(k)
        ups = [at(cols, rows, t, 'V(O%d_%d)' % (k, i), tq) for i in range(M) if kk[i] == 'UP']
        out['HIGH_%d_at_b%d_ckpt' % (k, k + 1)] = min(ups)
        out['overdrive_%d' % (k + 1)] = min(ups) - VTN
    return out


if __name__ == '__main__':
    res = []
    for cir in sys.argv[1:]:
        prn = cir + '.prn'
        if not os.path.exists(prn):
            continue
        res.append(row(cir, prn))
    hdr = ('%-18s %8s %8s %8s | %8s %8s %8s | %9s %9s %9s' %
           ('deck', 'sep1_V', 'sep2_V', 'sep3_V', 'rail1', 'rail2', 'rail3',
            'HI1@b2', 'HI2@b3', 'Vgs-Vtn'))
    print(hdr)
    print('-' * len(hdr))
    for r in res:
        print('%-18s %8.4f %8.4f %8.4f | %8.4f %8.4f %8.4f | %9.4f %9.4f %+9.4f' %
              (r['cir'].replace('.cir', ''), r['b1']['sep_V'], r['b2']['sep_V'], r['b3']['sep_V'],
               r['b1']['rail'], r['b2']['rail'], r['b3']['rail'],
               r['HIGH_1_at_b2_ckpt'], r['HIGH_2_at_b3_ckpt'], r['overdrive_3']))
    json.dump(res, open('sep_out.json', 'w'), indent=1)
