#!/usr/bin/env python3
"""TRACK A -- resonant park tap.  Every deck is a TEXT PATCH of the committed
qal/recov/skeptic/sk_best.cir (itself a committed patch of qal/swsweep/sw_tg15p_z.cir).

The ONLY lines any patch removes are:  XPK / VPK / BXepk / BXqpk / .tran / .print
The ONLY lines it adds are:            the park drive network, its integrators,
                                       and .print columns.
Every removal and addition is printed.
"""
import os, math, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = '/usr/local/src/stat-sim/qal/recov/skeptic/sk_best.cir'
BEAT = 580.0
EXTRA_PRINT = ' V(xehi) V(xqhi) V(xesw) V(xeb) V(mid)'


def integ(tag, expr):
    return ['CX%s x%s 0 1' % (tag, tag),
            'BX%s 0 x%s I={ %s }' % (tag, tag, expr),
            'RX%s x%s 0 0.01' % (tag, tag)]


def _pwl(pts):
    out, last = [], None
    for t, v in pts:
        if last is not None and t <= last:
            t = last + 1e-4
        out.append('%.6gp %.6g' % (t, v))
        last = t
    return ' '.join(out)


def _harm(nh, off, amp, beat, ph, npt=240, ncyc=1):
    """EXACTLY qal/recov/drives.py::_harm (verified bit-identical against the
    committed sk_best.cir PWL), extended to ncyc cycles for the periodic rows."""
    s = lambda th: sum(math.sin(k * th) / k for k in range(1, nh + 1, 2))
    g = [2 * math.pi * i / 4000 for i in range(4001)]
    mx, mn = max(s(t) for t in g), min(s(t) for t in g)
    f = lambda t: off + amp * (2 * (s(2 * math.pi * t / beat - math.pi / 2 + ph)
                                    - mn) / (mx - mn) - 1)
    n = npt * ncyc
    return [(beat * ncyc * i / n, f(beat * ncyc * i / n)) for i in range(n + 1)], f


def sub_sine(off, amp, t0, period, tend, dt=2.41667):
    """+-2 sub-harmonic park tap: off + amp*sin(2*pi*(t-t0)/period).
    Rising crossing of off happens exactly at t0."""
    n = int(tend / dt) + 2
    return [(dt * i, off + amp * math.sin(2 * math.pi * (dt * i - t0) / period))
            for i in range(n)]


def patch(tag, tend=1000.0, park=None, drop_xpk=False, pcols='',
          taps=None, note='', wpk=None):
    """park : replacement lines for 'VPK ...' plus rewritten BXepk/BXqpk (None=keep)
       drop_xpk : delete the XPK device line (the NO-PARK row)
       taps : (gts_pwl_line, gps_pwl_line) replacements (periodic rows)
       wpk  : park nMOS width in um (None = committed 1 um)"""
    src = open(BASE).read().splitlines()
    out, removed, added = [], [], []
    for ln in src:
        s = ln.strip()
        if drop_xpk and s.startswith('XPK '):
            removed.append(ln)
            continue
        if wpk is not None and s.startswith('XPK '):
            removed.append(ln)
            out.append('XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u' % wpk)
            added.append(out[-1])
            continue
        if park is not None and (s.startswith('VPK ')
                                 or s.split()[0] in ('CXepk', 'BXepk', 'RXepk',
                                                     'CXqpk', 'BXqpk', 'RXqpk')):
            removed.append(ln)
            continue
        if taps is not None and s.startswith('VGTS '):
            removed.append(ln[:80] + ' ...(PWL truncated)')
            out.append(taps[0]); added.append(taps[0][:80] + ' ...(PWL truncated)')
            continue
        if taps is not None and s.startswith('VGPS '):
            removed.append(ln[:80] + ' ...(PWL truncated)')
            out.append(taps[1]); added.append(taps[1][:80] + ' ...(PWL truncated)')
            continue
        if s.startswith('.tran'):
            removed.append(ln)
            out.append('.tran 0.1p %gp 0 0.25p' % tend)
            added.append(out[-1])
            continue
        if s.startswith('.print'):
            removed.append(ln)
            out.append(ln + EXTRA_PRINT + pcols)
            added.append('(.print + %s%s)' % (EXTRA_PRINT.strip(), pcols))
            continue
        out.append(ln)
    if park is not None:
        i = out.index('XSWN sw gt bkb 0 sg13_lv_nmos w=5u l=0.13u')
        out = out[:i] + park + out[i:]
        added.extend(park)
    fn = os.path.join(HERE, tag + '.cir')
    open(fn, 'w').write('\n'.join(out) + '\n')
    print('=== %s   %s' % (tag, note))
    for l in removed:
        print('   - %s' % l[:118])
    for l in added:
        print('   + %s' % l[:118])
    return fn


# --------------------------------------------------------------------------
# A2  MERGE: the park nMOS gate taken straight off the EXISTING gtp tap.
#     VPKM is a 0 V series source -> an ideal short that lets the park gate's
#     own current be metered by a path independent of the gtp tap integrator.
MERGE = (['* --- TRACK A (d) MERGE: park gate driven by the EXISTING gtp tap ---',
          'VPKM gtp pk 0']
         + integ('epk', 'V(pk)*I(VPKM)')      # energy INTO the park gate node
         + integ('qpk', 'abs(I(VPKM))'))

# --------------------------------------------------------------------------
# A3  SUB-HARMONIC: a fourth mode at BEAT/2 (period 1160 ps).  off = 0.45 V so
#     the RISING crossing of the park nMOS threshold lands exactly at t0; amp
#     1.05 V so the peak is a full 1.5 V.  Same 25 ohm tap resistance as gt/gtp.
def sub_park(t0=452.0, off=0.45, peak=1.5, c2=0.0, period=2 * BEAT,
             tend=1000.0, RS=25.0, dt=2.41667):
    """park tap = off + amp*[sin(th) + c2*sin(2 th)], th = 2pi(t-t0)/period.
    c2 = 0 -> ONE new mode at BEAT/2.  c2 > 0 adds the SECOND harmonic of that
    sub-fundamental, which IS the existing beat-rate mode f -- so the {f/2, f}
    park tap still costs only ONE new inductor, and buys a steeper edge."""
    import math as _m
    u = lambda th: _m.sin(th) + c2 * _m.sin(2 * th)
    mx = max(u(2 * _m.pi * i / 4000) for i in range(4001))
    amp = (peak - off) / mx
    n = int(tend / dt) + 2
    pts = [(dt * i, off + amp * u(2 * _m.pi * (dt * i - t0) / period))
           for i in range(n)]
    lo = min(v for _, v in pts)
    return (['* --- TRACK A (c) SUB-HARMONIC park tap: period %g ps, off %g, '
             'peak %g, c2 %g (amp %.4f, min %.4f), Vtn crossing at %g ps, RS %g ---'
             % (period, off, peak, c2, amp, lo, t0, RS),
             'VPKS pks 0 PWL(%s)' % _pwl(pts),
             'RPKS pks pk %g' % RS]
            + integ('epk', '-V(pks)*I(VPKS)')
            + integ('qpk', 'abs(I(VPKS))'))


if __name__ == '__main__':
    PK = ' V(pks) V(xepk) V(xqpk)'
    which = sys.argv[1:] or ['all']

    if 'all' in which or 'base' in which:
        patch('pa_base', note='INSTRUMENT CHECK: identical to the committed '
              'sk_best_long.cir (tend 1000, extra prints)')

    if 'all' in which or 'nopark' in which:
        patch('pa_nopark', drop_xpk=True,
              note='(d) ELIMINATE: no park device at all. VPK and its '
                   'integrators stay (they read 0), so the patch is one line.')

    if 'all' in which or 'merge' in which:
        patch('pa_merge', park=MERGE, pcols=' V(xepk) V(xqpk)',
              note='(d) MERGE: park gate on the existing gtp tap')

    if 'all' in which or 'sub' in which:
        patch('pa_sub', park=sub_park(), pcols=PK,
              note='(c) SUB-HARMONIC park tap, Vtn crossing at 452 ps '
                   '(matches the committed park close)')
        patch('pa_sub_e', park=sub_park(t0=430.0), pcols=PK,
              note='(c) SUB-HARMONIC, crossing 22 ps EARLIER (430 ps)')
        patch('pa_sub2', park=sub_park(c2=0.35), pcols=PK,
              note='(a)+(c) {f/2, f} two-mode park tap -- steeper edge, only '
                   'ONE new inductor (the f mode already exists)')
        patch('pa_sub_w3', park=sub_park(), pcols=PK, wpk=3.0,
              note='(c) SUB-HARMONIC with a 3 um park -- 3x conductance to '
                   'offset the slow resonant edge, 3x the gate cap on the tap')
        patch('pa_sub_w05', park=sub_park(), pcols=PK, wpk=0.5,
              note='(c) SUB-HARMONIC with a 0.5 um park -- is the committed '
                   '1 um already oversized?')

    if 'all' in which or 'periodic' in which:
        gt_pts, _ = _harm(5, 0.85, 0.75, BEAT, 0.0, ncyc=2)
        gp_pts, _ = _harm(5, 0.41, -0.75, BEAT, 2 * math.pi * 6.0 / BEAT, ncyc=2)
        taps = ('VGTS gts 0 PWL(%s)' % _pwl(gt_pts),
                'VGPS gps 0 PWL(%s)' % _pwl(gp_pts))
        patch('pa_base_per', tend=1160.0, taps=taps,
              note='HOLD TEST reference: committed ideal 1.5 V park step, but '
                   'the gt/gtp taps made genuinely PERIODIC (2 beats)')
        patch('pa_sub_per', tend=1160.0, taps=taps,
              park=sub_park(tend=1160.0), pcols=PK,
              note='HOLD TEST: sub-harmonic park + PERIODIC gt/gtp taps (2 beats '
                   '= exactly one sub-harmonic period)')
        patch('pa_merge_per', tend=1160.0, taps=taps, park=MERGE,
              pcols=' V(xepk) V(xqpk)',
              note='HOLD TEST: merged park + PERIODIC taps')
