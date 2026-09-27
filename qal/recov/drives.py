#!/usr/bin/env python3
"""Candidate gate-drive networks for the recovery round.  Each returns
(lines, print_cols, drive_tags, q_tags, aux, tanks) so rv.analyze can close the ledger.

Conventions
-----------
* every DC source gets an energy integrator  xe<tag>  (= -integral V*I dt).
* every source whose cost must be charged CONVENTIONALLY (the recursion: step
  switches, freeze switches, clamps) gets a RECTIFIED charge integrator
  xq<tag> = integral |I| dt, so cost = (xq/2)*V per full cycle regardless of how
  many pulses it makes.
* pk (the 1 um park nMOS, 2.1 fC = 7.2% of the 29.0 fC total) stays on the
  committed ideal PWL in every recovery row and is charged CONVENTIONALLY at
  Q_pk*VGH.  No recovery is ever credited to the park.
"""
import math
from rv import integ

def _pwl(pts):
    out, last = [], None
    for t, v in pts:
        if last is not None and t <= last: t = last + 1e-4
        out.append('%.6gp %.6g' % (t, v)); last = t
    return ' '.join(out)

def _meter(L, items):
    for tag, src, node in items:
        L += integ('e'+tag, '-V(%s)*I(%s)' % (node, src))
        L += integ('q'+tag, 'abs(I(%s))' % src)

# ---------------------------------------------------------------- M3 / control
def ideal_pwl(VGH=1.5, tclose=50.0, tcut=316.755, edge=2.0):
    L = ['* ---- ideal PWL drives, VGH=%g close=%g cut=%g edge=%g ----'
         % (VGH, tclose, tcut, edge)]
    L += ['VGT  gt  0 PWL(%s)' % _pwl([(0,0),(tclose-edge,0),(tclose,VGH),
                                       (tcut,VGH),(tcut+edge,0)])]
    L += ['VGTP gtp 0 PWL(%s)' % _pwl([(0,VGH),(tclose-edge,VGH),(tclose,0),
                                       (tcut,0),(tcut+edge,VGH)])]
    L += ['VPK  pk  0 PWL(%s)' % _pwl([(0,0),(tcut+edge,0),(tcut+2*edge,VGH)])]
    _meter(L, [('gt','VGT','gt'), ('gtp','VGTP','gtp'), ('pk','VPK','pk')])
    pc = 'V(xegt) V(xegtp) V(xepk) V(xqgt) V(xqgtp) V(xqpk)'
    return L, pc, ['gt','gtp','pk'], ['gt','gtp','pk'], None, None

def probe(VGH=1.5, tclose=50.0, te=None, steps=0):
    """switch held ON for the whole window -> locates the TRUE current zero.
    te = None : committed 2 ps edge;  te>0 : raised-cosine turn-on of that width;
    steps = n : n-step STAIRCASE turn-on of width te (the M2 edge shape)."""
    L = ['* ---- probe: switch held on, VGH=%g tclose=%g te=%s steps=%d ----'
         % (VGH, tclose, te, steps)]
    if te and steps:
        r0, ts = tclose - te/2.0, te/float(steps)
        gp, gpp = [(0,0)], [(0,VGH)]
        for j in range(1, steps+1):
            v = VGH*j/float(steps)
            gp += [(r0+(j-1)*ts, gp[-1][1]), (r0+(j-1)*ts+0.5, v)]
            gpp += [(r0+(j-1)*ts, gpp[-1][1]), (r0+(j-1)*ts+0.5, VGH-v)]
        gp += [(2000, VGH)]; gpp += [(2000, 0)]
    elif te:
        gp  = [(0,0)] + rcos(tclose-te/2.0, te, 0, VGH) + [(2000, VGH)]
        gpp = [(0,VGH)] + rcos(tclose-te/2.0, te, VGH, 0) + [(2000, 0)]
    else:
        gp  = [(0,0),(tclose-2,0),(tclose,VGH)]
        gpp = [(0,VGH),(tclose-2,VGH),(tclose,0)]
    L += ['VGT  gt  0 PWL(%s)' % _pwl(gp), 'VGTP gtp 0 PWL(%s)' % _pwl(gpp),
          'VPK  pk  0 0']
    _meter(L, [('gt','VGT','gt'), ('gtp','VGTP','gtp'), ('pk','VPK','pk')])
    pc = 'V(xegt) V(xegtp) V(xepk) V(xqgt) V(xqgtp) V(xqpk)'
    return L, pc, ['gt','gtp','pk'], ['gt','gtp','pk'], None, None

# -------------------------------------------------- M1-A adiabatic/resonant edge
def rcos(t0, te, v0, v1, npt=40):
    """raised-cosine edge -- the waveform a lossless LC half-cycle makes."""
    return [(t0 + te*i/float(npt), v0 + 0.5*(v1-v0)*(1-math.cos(math.pi*i/npt)))
            for i in range(npt+1)]

def m1a_edges(VGH=1.5, tclose=100.0, tcut=366.755, te=133.0, RS=25.0):
    """gt/gtp driven through a series R by an IDEAL (lossless) resonator whose
    output is the raised-cosine half-sine: R carries ALL the network loss, so
    eta(R) maps to eta(Q) with Q = 1/(omega R C).  Freeze/clamp switches are NOT
    in this row -- they are the m1c row."""
    r0, f0 = tclose - te/2.0, tcut - te/2.0
    gt_pts  = [(0,0)]   + rcos(r0, te, 0, VGH) + rcos(f0, te, VGH, 0)
    gtp_pts = [(0,VGH)] + rcos(r0, te, VGH, 0) + rcos(f0, te, 0, VGH)
    L = ['* ---- M1-A adiabatic raised-cosine edges te=%g ps RS=%g ohm ----' % (te, RS)]
    L += ['VGTS gts 0 PWL(%s)' % _pwl(gt_pts), 'RGTS gts gt %g' % RS,
          'VGPS gps 0 PWL(%s)' % _pwl(gtp_pts), 'RGPS gps gtp %g' % RS,
          'VPK  pk  0 PWL(%s)' % _pwl([(0,0),(tcut+2,0),(tcut+4,VGH)])]
    _meter(L, [('gt','VGTS','gts'), ('gtp','VGPS','gps'), ('pk','VPK','pk')])
    pc = 'V(gts) V(gps) V(xegt) V(xegtp) V(xepk) V(xqgt) V(xqgtp) V(xqpk)'
    return L, pc, ['gt','gtp','pk'], ['gt','gtp','pk'], None, None

# ------------------------------------------------ M1-B free-running resonant sine
def m1b_sine2(VGH=1.5, beat=534.0, adv_deg=0.0, RS=25.0,
              off_gt=0.75, amp_gt=0.75, off_gp=0.75, amp_gp=0.75, tpk=None):
    """free-running sine taps with INDEPENDENT common modes, because the two
    switch halves have different threshold levels: the nMOS must be above
    bkb+Vtn (~1.13 V) for the whole conduction window yet below Vtn (~0.45 V)
    when the park holds sw at 0, and the pMOS must be below bkb-|Vtp| (~0.18 V)
    to conduct.  Centring each tap on ITS OWN threshold is what makes the
    above-threshold window equal half the beat."""
    f = 1e12/beat
    tpk = beat*0.76 if tpk is None else tpk
    L = ['* ---- M1-B2 free-running sines beat=%g adv=%g RS=%g gt(%g+-%g) gtp(%g+-%g) ----'
         % (beat, adv_deg, RS, off_gt, amp_gt, off_gp, amp_gp)]
    L += ['VGTS gts 0 SIN(%g %g %g 0 0 -90)' % (off_gt, amp_gt, f),
          'RGTS gts gt %g' % RS,
          'VGPS gps 0 SIN(%g %g %g 0 0 %g)' % (off_gp, amp_gp, f, 90.0-adv_deg),
          'RGPS gps gtp %g' % RS,
          'VPK  pk  0 PWL(%s)' % _pwl([(0,0),(tpk,0),(tpk+2,VGH)])]
    _meter(L, [('gt','VGTS','gts'), ('gtp','VGPS','gps'), ('pk','VPK','pk')])
    pc = 'V(gts) V(gps) V(xegt) V(xegtp) V(xepk) V(xqgt) V(xqgtp) V(xqpk)'
    return L, pc, ['gt','gtp','pk'], ['gt','gtp','pk'], None, None

def m1b_sine(VGH=1.5, beat=534.0, adv_deg=0.0, RS=25.0, amp=None, off=None,
             tpk=None):
    """UNSWITCHED resonant network: a continuous sine tap per gate.  There is no
    per-edge switch at all, hence NO recursion cost -- the open question is
    whether the waveform holds the conduction window and the cut order."""
    amp = VGH/2.0 if amp is None else amp
    off = VGH/2.0 if off is None else off
    f = 1e12/beat
    tpk = beat*0.68 if tpk is None else tpk
    L = ['* ---- M1-B free-running sine taps beat=%g ps adv=%g deg RS=%g amp=%g off=%g ----'
         % (beat, adv_deg, RS, amp, off)]
    L += ['VGTS gts 0 SIN(%g %g %g 0 0 -90)' % (off, amp, f), 'RGTS gts gt %g' % RS,
          'VGPS gps 0 SIN(%g %g %g 0 0 %g)' % (off, amp, f, 90.0-adv_deg),
          'RGPS gps gtp %g' % RS,
          'VPK  pk  0 PWL(%s)' % _pwl([(0,0),(tpk,0),(tpk+2,VGH)])]
    _meter(L, [('gt','VGTS','gts'), ('gtp','VGPS','gps'), ('pk','VPK','pk')])
    pc = 'V(gts) V(gps) V(xegt) V(xegtp) V(xepk) V(xqgt) V(xqgtp) V(xqpk)'
    return L, pc, ['gt','gtp','pk'], ['gt','gtp','pk'], None, None

# ------------------------------------------------- M1-C switched resonant + freeze
def m1c_freeze(VGH=1.5, tclose=100.0, tcut=366.755, te=133.0, RS=25.0,
               wfn=4.0, wfp=8.0, wcln=0.74, wclp=1.12, tend=816.755):
    """the SAME adiabatic edges, but the resonator reaches the gate through a REAL
    CMOS freeze switch (conventionally driven) and the level between edges is held
    by REAL CMOS clamps (2 per node: hold-high and hold-low).  This is the row
    that PAYS the recursion the m1a row leaves out."""
    r0, f0 = tclose - te/2.0, tcut - te/2.0
    gt_pts  = [(0,0)]   + rcos(r0, te, 0, VGH) + rcos(f0, te, VGH, 0)
    gtp_pts = [(0,VGH)] + rcos(r0, te, VGH, 0) + rcos(f0, te, 0, VGH)
    L = ['* ---- M1-C adiabatic edges through a REAL freeze TG (%g/%gum) + 4 clamps (%g/%gum) ----'
         % (wfn, wfp, wcln, wclp)]
    L += ['VGTS gts 0 PWL(%s)' % _pwl(gt_pts), 'RGTS gts gtr %g' % RS,
          'VGPS gps 0 PWL(%s)' % _pwl(gtp_pts), 'RGPS gps gpr %g' % RS]
    fz  = [(0,0),(r0-0.5,0),(r0,VGH),(r0+te,VGH),(r0+te+0.5,0),
           (f0-0.5,0),(f0,VGH),(f0+te,VGH),(f0+te+0.5,0)]
    fzi = [(t, VGH-v) for t, v in fz]
    for pre, node in (('A','gt'), ('B','gtp')):
        p, res = pre.lower(), ('gtr' if pre == 'A' else 'gpr')
        L += ['V%sFN %sfn 0 PWL(%s)' % (pre, p, _pwl(fz)),
              'V%sFP %sfp 0 PWL(%s)' % (pre, p, _pwl(fzi)),
              'X%sFN %s %sfn %s 0 sg13_lv_nmos w=%gu l=0.13u' % (pre, res, p, node, wfn),
              'X%sFP %s %sfp %s vhi sg13_lv_pmos w=%gu l=0.13u' % (pre, res, p, node, wfp)]
    # hold windows: gt low [0,r0] and [f0+te,end]; gt high [r0+te,f0].  gtp mirror.
    lo_g = [(0,VGH),(r0-0.5,VGH),(r0,0),(f0+te,0),(f0+te+0.5,VGH)]       # nMOS clamp gate
    hi_g = [(0,VGH),(r0+te,VGH),(r0+te+0.5,0),(f0-0.5,0),(f0,VGH)]       # pMOS clamp gate
    lo_p = [(t, VGH-v) for t, v in hi_g]                                  # gtp nMOS clamp
    hi_p = [(t, VGH-v) for t, v in lo_g]                                  # gtp pMOS clamp
    L += ['VCAL cal 0 PWL(%s)' % _pwl(lo_g),
          'XCAL gt cal 0 0 sg13_lv_nmos w=%gu l=0.13u' % wcln,
          'VCAH cah 0 PWL(%s)' % _pwl(hi_g),
          'XCAH gt cah vhi vhi sg13_lv_pmos w=%gu l=0.13u' % wclp,
          'VCBL cbl 0 PWL(%s)' % _pwl(lo_p),
          'XCBL gtp cbl 0 0 sg13_lv_nmos w=%gu l=0.13u' % wcln,
          'VCBH cbh 0 PWL(%s)' % _pwl(hi_p),
          'XCBH gtp cbh vhi vhi sg13_lv_pmos w=%gu l=0.13u' % wclp]
    L += ['VPK  pk  0 PWL(%s)' % _pwl([(0,0),(tcut+2,0),(tcut+4,VGH)])]
    _meter(L, [('gt','VGTS','gts'), ('gtp','VGPS','gps'), ('pk','VPK','pk'),
               ('afn','VAFN','afn'), ('afp','VAFP','afp'),
               ('bfn','VBFN','bfn'), ('bfp','VBFP','bfp'),
               ('cal','VCAL','cal'), ('cah','VCAH','cah'),
               ('cbl','VCBL','cbl'), ('cbh','VCBH','cbh')])
    dt = ['gt','gtp','pk']
    qt = ['gt','gtp','pk','afn','afp','bfn','bfp','cal','cah','cbl','cbh']
    aux = {}
    for nm in ('afn','afp','bfn','bfp','cal','cah','cbl','cbh'):
        aux['sw_'+nm] = (nm, VGH, 0.5)
    pc = ('V(gts) V(gps) V(gtr) V(gpr) V(xegt) V(xegtp) V(xepk) '
          + ' '.join('V(xq%s)' % t for t in qt))
    return L, pc, dt, qt, aux, None

# ----------------------------------------------------------- M2 stepwise charging
def m2_stepwise(n=4, VGH=1.5, tclose=100.0, tcut=366.755, te=133.0,
                CT_fF=2000.0, wn=1.0, wp=2.0, tend=816.755):
    """n-step adiabatic capacitive charging of gt and gtp.
    Level ladder 0, V/n, ..., V: tanks hold the n-1 intermediate levels, the top
    and bottom switches double as the HOLD clamps (standard stepwise driver), so
    the switch count is n+1 per node and the gate node is never floating."""
    ts = te/float(n)
    L = ['* ---- M2 %d-step adiabatic gate charging te=%g ps (ts=%g ps) TG %g/%g um ----'
         % (n, te, ts, wn, wp)]
    L += ['VTOP vtop 0 %g' % VGH]
    L += integ('etop', '-%g*I(VTOP)' % VGH)
    tags, qtags, aux = ['top'], [], {}
    for k in range(1, n):
        v = k*VGH/float(n)
        L += ['CT%d lv%d 0 %gf' % (k, k, CT_fF), 'VT%d vt%d 0 %g' % (k, k, v),
              'RT%d vt%d lv%d 1e10' % (k, k, k)]
        L += integ('et%d' % k, '-%g*I(VT%d)' % (v, k))
        tags.append('t%d' % k)
    tanks = {('lv%d' % k): (CT_fF, 'V(LV%d)' % k) for k in range(1, n)}
    r0, f0 = tclose - te/2.0, tcut - te/2.0
    g = 0.5                                        # break-before-make gap (ps)
    for node, pre in (('gt','A'), ('gtp','B')):
        p = pre.lower()
        for k in range(0, n+1):
            src = '0' if k == 0 else ('vtop' if k == n else 'lv%d' % k)
            win = []                               # (a,b) on-windows
            if node == 'gt':
                if k == 0:
                    win = [(-10.0, r0), (f0+(n-1)*ts, tend+10)]
                elif k == n:
                    win = [(r0+(n-1)*ts, f0)]
                else:
                    win = [(r0+(k-1)*ts, r0+k*ts), (f0+(n-1-k)*ts, f0+(n-k)*ts)]
            else:                                  # gtp: mirror ladder
                if k == n:
                    win = [(-10.0, r0), (f0+(n-1)*ts, tend+10)]
                elif k == 0:
                    win = [(r0+(n-1)*ts, f0)]
                else:
                    win = [(r0+(n-1-k)*ts, r0+(n-k)*ts), (f0+(k-1)*ts, f0+k*ts)]
            pn, pp = [], []
            v0 = VGH if win and win[0][0] < 0 else 0.0
            pn.append((0.0, v0)); pp.append((0.0, VGH-v0))
            for (a, b) in sorted(win):
                if a < 0:
                    pn += [(max(b-g, 1.0), VGH), (b, 0.0)]
                    pp += [(max(b-g, 1.0), 0.0), (b, VGH)]
                    continue
                pn += [(a, 0.0), (a+g, VGH), (max(b-g, a+g+0.1), VGH), (b, 0.0)]
                pp += [(a, VGH), (a+g, 0.0), (max(b-g, a+g+0.1), 0.0), (b, VGH)]
            L += ['V%sGN%d %sn%d 0 PWL(%s)' % (pre,k,p,k,_pwl(pn)),
                  'V%sGP%d %sp%d 0 PWL(%s)' % (pre,k,p,k,_pwl(pp)),
                  'X%sSN%d %s %sn%d %s 0 sg13_lv_nmos w=%gu l=0.13u' % (pre,k,src,p,k,node,wn),
                  'X%sSP%d %s %sp%d %s vhi sg13_lv_pmos w=%gu l=0.13u' % (pre,k,src,p,k,node,wp)]
        expr = '+'.join('abs(I(V%sGN%d))+abs(I(V%sGP%d))' % (pre,k,pre,k)
                        for k in range(0, n+1))
        L += integ('q%ssw' % p, expr)
        qtags.append('%ssw' % p)
        aux['%s_stepsw' % node] = ('%ssw' % p, VGH, 0.5)
    L += ['VPK  pk  0 PWL(%s)' % _pwl([(0,0),(tcut+2,0),(tcut+4,VGH)])]
    L += integ('epk', '-V(pk)*I(VPK)'); L += integ('qpk', 'abs(I(VPK))')
    tags.append('pk'); qtags.append('pk')
    pc = ' '.join(['V(xe%s)' % t for t in tags]
                  + ['V(xq%s)' % t for t in qtags]
                  + ['V(LV%d)' % k for k in range(1, n)])
    return L, pc, tags, qtags, aux, tanks

# ------------------------------- M1-D free-running MULTI-HARMONIC resonant network
def _harm(nh, off, amp, beat, ph, npt=240):
    """odd-harmonic sum sum_{k odd<=nh} sin(k th)/k, normalised to +-1 then scaled.
    This is what a resonant network with nh-th harmonic modes produces: a flat top
    (long conduction window) with fast edges (so the park can close on time), and
    it needs NO per-edge switch."""
    s = lambda th: sum(math.sin(k*th)/k for k in range(1, nh+1, 2))
    g = [2*math.pi*i/4000 for i in range(4001)]
    mx, mn = max(s(t) for t in g), min(s(t) for t in g)
    f = lambda t: off + amp*(2*(s(2*math.pi*t/beat - math.pi/2 + ph) - mn)/(mx-mn) - 1)
    return [(beat*i/npt, f(beat*i/npt)) for i in range(npt+1)], f

def m1d_harmonic(VGH=1.5, beat=534.0, nh=5, RS=25.0,
                 off_gt=0.85, amp_gt=0.75, off_gp=0.41, amp_gp=0.75, tpk=None,
                 adv_ps=0.0):
    import math as _m
    gt_pts, fg = _harm(nh, off_gt, amp_gt, beat, 0.0)
    # adv_ps ADVANCES the gtp tap in time so the pMOS cuts EARLY-or-with the nMOS
    # (the pre-registered ordering rule); on a shared resonant network this is a
    # phase-shifted tap, i.e. a second phase, not a second network.
    gp_pts, fp = _harm(nh, off_gp, -amp_gp, beat, 2*_m.pi*adv_ps/beat)
    if tpk is None:            # park closes as soon as gt is below Vt (~0.45 V)
        pk = max(range(len(gt_pts)), key=lambda i: gt_pts[i][1])
        tpk = next((gt_pts[i][0] for i in range(pk, len(gt_pts))
                    if gt_pts[i][1] < 0.45), beat*0.85)
    L = ['* ---- M1-D free-running %d-harmonic resonant taps beat=%g RS=%g '
         'gt(%g+-%g) gtp(%g-+%g) park@%.0f ----'
         % (nh, beat, RS, off_gt, amp_gt, off_gp, amp_gp, tpk)]
    L += ['VGTS gts 0 PWL(%s)' % _pwl(gt_pts), 'RGTS gts gt %g' % RS,
          'VGPS gps 0 PWL(%s)' % _pwl(gp_pts), 'RGPS gps gtp %g' % RS,
          'VPK  pk  0 PWL(%s)' % _pwl([(0,0),(tpk,0),(tpk+2,VGH)])]
    _meter(L, [('gt','VGTS','gts'), ('gtp','VGPS','gps'), ('pk','VPK','pk')])
    pc = 'V(gts) V(gps) V(xegt) V(xegtp) V(xepk) V(xqgt) V(xqgtp) V(xqpk)'
    return L, pc, ['gt','gtp','pk'], ['gt','gtp','pk'], None, None
