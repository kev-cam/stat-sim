#!/usr/bin/env python3
"""Generate the SKEPTIC's audit decks as TEXT PATCHES of the round's own
best-recovery deck qal/recov/m1d_h5b580_adv6.cir (copied here as sk_best.cir).

Every patch prints exactly which lines it removed and added, so the deltas are
auditable.  Nothing else in the deck is touched: same models, same LT/RS/CA,
same .ic, same resonant gt/gtp taps, same 25 ohm series R.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'sk_best.cir')

EXTRA_PRINT = ' V(xehi) V(xqhi) V(xesw) V(xeb)'


def integ(tag, expr):
    return ['CX%s x%s 0 1' % (tag, tag),
            'BX%s 0 x%s I={ %s }' % (tag, tag, expr),
            'RX%s x%s 0 0.01' % (tag, tag)]


def patch(tag, tend=None, park=None, data=None, extra_print=True, pcols=''):
    """park: list of replacement lines for the 'VPK ...' line (None = keep).
       data: dict {index: value} overriding the VI<i> cell inputs."""
    src = open(BASE).read().splitlines()
    out, removed, added = [], [], []
    for ln in src:
        s = ln.strip()
        if park is not None and s.startswith('VPK '):
            removed.append(ln)
            out.extend(park)
            added.extend(park)
            continue
        if park is not None and (s.startswith('BXepk ') or s.startswith('BXqpk ')):
            # these reference I(VPK), which the real-driver patch deletes; the
            # replacement metering is on the driver rail (xpd/xqd) and its input (xpi)
            removed.append(ln)
            continue
        if data is not None and s.startswith('VI'):
            n = int(s.split()[0][2:])
            if n in data:
                removed.append(ln)
                out.append('VI%d in%d 0 %g' % (n, n, data[n]))
                added.append(out[-1])
                continue
        if tend is not None and s.startswith('.tran'):
            removed.append(ln)
            out.append('.tran 0.1p %gp 0 0.25p' % tend)
            added.append(out[-1])
            continue
        if extra_print and s.startswith('.print'):
            removed.append(ln)
            out.append(ln + EXTRA_PRINT + pcols)
            added.append('(.print + %s%s)' % (EXTRA_PRINT.strip(), pcols))
            continue
        out.append(ln)
    fn = os.path.join(HERE, tag + '.cir')
    open(fn, 'w').write('\n'.join(out) + '\n')
    print('=== %s' % tag)
    for l in removed:
        print('   - %s' % l[:110])
    for l in added:
        print('   + %s' % l[:110])
    return fn


# -------- park-driver variants: the RECURSION the round books at Q_pk*VGH -----
# The round drives the 1 um park nMOS gate from an IDEAL PWL source and books
# 2.403 fJ = Q_pk*VGH.  A real park needs a driver.  These are LOWER BOUNDS:
# bare sg13_lv devices at the sg13g2_inv_1 geometry (w 1.12u/0.74u) with no
# junction area, driven from an ideal input, so the only costs counted are the
# final stage(s)' own rail draw.  No delay chain at all -- the phase is assumed
# free from the resonant network.
PKRAIL = ['VPKR vpkr 0 1.5'] + integ('pd', '-1.5*I(VPKR)') + integ('qd', '-I(VPKR)')
INV = lambda o, i: ['XP%s %s %s vpkr vpkr sg13_lv_pmos w=1.12u l=0.13u' % (o, o, i),
                    'XN%s %s %s 0 0 sg13_lv_nmos w=0.74u l=0.13u' % (o, o, i)]

# 1 stage, FAST ideal input edge (0.5 ps): the absolute floor
park1 = (['* --- SKEPTIC: park driven by ONE real inverter, fast ideal input ---',
          'VPKI pki 0 PWL(0p 1.5 451.417p 1.5 451.917p 0)'] + PKRAIL + INV('pk', 'pki')
         + integ('pi', '-V(pki)*I(VPKI)'))
# 2 stages, fast ideal input: what squaring up + polarity actually needs
park2 = (['* --- SKEPTIC: park driven by TWO real inverters, fast ideal input ---',
          'VPKI pki 0 PWL(0p 0 450.9p 0 451.4p 1.5)'] + PKRAIL
         + INV('pk1', 'pki') + INV('pk', 'pk1') + integ('pi', '-V(pki)*I(VPKI)'))
# 1 stage, SLOW input edge (130 ps): the edge a resonant phase actually delivers
park3 = (['* --- SKEPTIC: park driven by ONE real inverter, 130 ps resonant-slow input ---',
          'VPKI pki 0 PWL(0p 1.5 386.9p 1.5 516.9p 0)'] + PKRAIL + INV('pk', 'pki')
         + integ('pi', '-V(pki)*I(VPKI)'))

if __name__ == '__main__':
    patch('sk_best_p', tend=None)                 # extra prints only, same tend
    patch('sk_best_long', tend=1000)              # reach the pre-registered tD
    PK=' V(xpd) V(xqd) V(xpi) V(pki)'
    patch('sk_park1', tend=1000, park=park1, pcols=PK)
    patch('sk_park2', tend=1000, park=park2, pcols=PK)
    patch('sk_park3', tend=1000, park=park3, pcols=PK)
    # data-word robustness: the fixed-phase drive cannot retune per word, and the
    # LC zero moves with popcount (qal/timer zc_bankN: 61.6 ps full scale at N=8).
    patch('sk_best_k6', tend=1000, data={0: 0, 2: 0})   # 2 more cells load bkb
    patch('sk_best_k2', tend=1000, data={1: 1, 3: 1})   # 2 fewer
