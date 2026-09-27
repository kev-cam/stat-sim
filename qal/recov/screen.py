#!/usr/bin/env python3
"""Device screen: R_on(W) and Q_gate(W) for sg13_lv_nmos/pmos at VGH, hence the
intrinsic device time constant tau = R_on * C_gate that sets BOTH recursion costs
(M2's step switches, M1-C's freeze switch).  tau is the number P3/P4 hinge on, and
it was ESTIMATED in PRE_REGISTERED.json -- this measures it."""
import os, sys, subprocess, time, json
import rv

#   PyMS compiles ONE .so PER GEOMETRY, so the screen deliberately uses only the
#   widths the committed hop deck already instantiates (nmos 0.74/1/5 um, pmos
#   1.12/10 um) -- zero extra compiles, and tau is checked for size-invariance
#   across a 5-7x width span, which is all the recursion arithmetic needs.
WN = [0.74, 1.0, 5.0]
WP = [1.12, 10.0]
VGH = 1.5

def deck(vgh=VGH):
    L = ['.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"',
         '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"',
         '.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"',
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         'VDD vdd 0 %g' % vgh]
    pc = []
    for i, w in enumerate(WN):
        # nMOS: source 0, drain 50 mV, gate ramped 0 -> VGH over 2 ns (quasi-static)
        L += ['VGN%d gn%d 0 PWL(0 0 2000p %g)' % (i, i, vgh),
              'VDN%d dn%d 0 0.05' % (i, i),
              'XN%d dn%d gn%d 0 0 sg13_lv_nmos w=%gu l=0.13u' % (i, i, i, w)]
        L += rv.integ('qn%d' % i, '-I(VGN%d)' % i)
        pc += ['I(VDN%d)' % i, 'V(xqn%d)' % i]
    for i, w in enumerate(WP):
        # pMOS: source VGH, drain VGH-50mV, gate ramped VGH -> 0
        L += ['VGP%d gp%d 0 PWL(0 %g 2000p 0)' % (i, i, vgh),
              'VDP%d dp%d 0 %g' % (i, i, vgh - 0.05),
              'XP%d dp%d gp%d vdd vdd sg13_lv_pmos w=%gu l=0.13u' % (i, i, i, w)]
        L += rv.integ('qp%d' % i, 'I(VGP%d)' % i)
        pc += ['I(VDP%d)' % i, 'V(xqp%d)' % i]
    L += ['.tran 1p 2000p 0 2p', '.print tran ' + ' '.join(pc), '.end']
    return '\n'.join(L) + '\n'

def main():
    txt = deck()
    prn, wall = rv.run('screen_tau', txt)
    if not prn: sys.exit(1)
    hdr, rows = rv.read_prn(prn)
    out = {'_doc': 'MEASURED R_on (linear region, |Vds|=50 mV, |Vgs|=1.5) and '
                   'quasi-static gate charge Q_gate(0->1.5 V) vs width; '
                   'tau = R_on*C_gate with C_gate = Q_gate/1.5.', 'rows': []}
    c = lambda n: rv.col(hdr, n)
    for i, w in enumerate(WN):
        idn = abs(rv.at(rows, c('I(VDN%d)' % i), 1990.0))
        qn = abs(rv.at(rows, c('V(XQN%d)' % i), 1990.0) - rows[0][c('V(XQN%d)' % i)])*1e15
        rn, cn = 0.05/idn, qn/VGH
        out['rows'].append(dict(dev='nmos', w_um=w, Ron_ohm=rn, Qgate_fC=qn,
                                Cgate_fF=cn, tau_ps=rn*cn*1e-3,
                                Ron_x_W=rn*w, Cg_per_W=cn/w))
        print('  nmos W=%5.2f um  Ron %9.1f ohm  Qg %7.3f fC  Cg %6.3f fF  '
              'tau %6.3f ps  (Ron*W %6.0f, Cg/W %5.3f)'
              % (w, rn, qn, cn, rn*cn*1e-3, rn*w, cn/w))
    for i, w in enumerate(WP):
        idp = abs(rv.at(rows, c('I(VDP%d)' % i), 1990.0))
        qp = abs(rv.at(rows, c('V(XQP%d)' % i), 1990.0) - rows[0][c('V(XQP%d)' % i)])*1e15
        rp, cp = 0.05/idp, qp/VGH
        out['rows'].append(dict(dev='pmos', w_um=w, Ron_ohm=rp, Qgate_fC=qp,
                                Cgate_fF=cp, tau_ps=rp*cp*1e-3,
                                Ron_x_W=rp*w, Cg_per_W=cp/w))
        print('  pmos W=%5.2f um  Ron %9.1f ohm  Qg %7.3f fC  Cg %6.3f fF  '
              'tau %6.3f ps  (Ron*W %6.0f, Cg/W %5.3f)'
              % (w, rp, qp, cp, rp*cp*1e-3, rp*w, cp/w))
    nm = [r for r in out['rows'] if r['dev']=='nmos']
    pm = [r for r in out['rows'] if r['dev']=='pmos']
    RWn = sum(r['Ron_x_W'] for r in nm)/len(nm); CWn = sum(r['Cg_per_W'] for r in nm)/len(nm)
    RWp = sum(r['Ron_x_W'] for r in pm)/len(pm); CWp = sum(r['Cg_per_W'] for r in pm)/len(pm)
    out['scaling'] = dict(Ron_x_W_n=RWn, Cg_per_W_n=CWn, Ron_x_W_p=RWp, Cg_per_W_p=CWp)
    tg = []
    for wn in (0.5, 1.0, 2.0, 4.0, 8.0):
        wp = 2*wn
        R = 1.0/(1.0/(RWn/wn) + 1.0/(RWp/wp))
        Cg = CWn*wn + CWp*wp
        tg.append(dict(wn_um=wn, wp_um=wp, R_TG_ohm=R, Cgate_TG_fF=Cg, tau_TG_ps=R*Cg*1e-3))
        print('  TG %4.1f/%4.1f um  R_TG %8.1f ohm  Cgate_TG %7.3f fF  tau_TG %6.3f ps'
              % (wn, wp, R, Cg, R*Cg*1e-3))
    out['TG'] = tg
    out['tau_TG_ps_MEASURED'] = tg[0]['tau_TG_ps']
    json.dump(out, open(os.path.join(rv.HERE, 'RESULTS_SCREEN.json'), 'w'), indent=1)
    print('  tau_TG (mean over sizes) = %.3f ps  [MEASURED]' % out['tau_TG_ps_MEASURED'])

if __name__ == '__main__':
    main()
