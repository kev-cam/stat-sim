#!/usr/bin/env python3
"""Assemble the recovery round: fit the measured loss laws, map series R to network
Q and inductance, place the analytic optima from MEASURED device constants, run the
campaign admission rule on every row, and print the verdict."""
import json, os, math, sys
import rv, cutorder

HERE = rv.HERE
DB = json.load(open(os.path.join(HERE, 'RESULTS_RECOV.json')))
SCR = json.load(open(os.path.join(HERE, 'RESULTS_SCREEN.json')))
sys.path.insert(0, '/usr/local/src/stat-sim/qal/zcd')
import restate_admission as RA

CV2 = 43.481                  # fJ, PRE-STATED conventional reference (29.0 fC x 1.5 V)
E_ADMIT = 12.747              # fJ, N_min <= 63 exactly
C_NET = (12.512 + 21.402)*1e-15/1.5   # F, MEASURED driven gate C per bank (gt+gtp)

def lsq(xs, ys):
    n = len(xs); sx = sum(xs); sy = sum(ys)
    sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
    m = (n*sxy - sx*sy)/(n*sxx - sx*sx)
    return m, (sy - m*sx)/n

def Qnet(R, beat):
    w = 2*math.pi/(beat*1e-12)
    return 1.0/(w*C_NET*R)

def L_nH(B, beat, k=1):
    w = 2*math.pi/(beat*1e-12)
    return 1e9/((k*w)**2 * C_NET * B)

def main():
    out = {'_doc': 'GATE-CHARGE RECOVERY round (M1 resonant / M2 stepwise / M3 lower VGH) '
                   'on the committed tg15p QAL transfer switch. Every row is a TEXT PATCH '
                   'of swsweep/sw_tg15p_z.cir. Acceptance pre-registered in '
                   'PRE_REGISTERED.json BEFORE the first recovery deck (mtimes in README).',
           'reference': {
             'CV2_conv_PRE_STATED_fJ': CV2,
             'CV2_conv_MEASURED_rectified_fJ': 53.27,
             'ideal_PWL_floor_fJ': 3.522,
             'eta_max_from_ideal_floor_pct': 100*(1-3.522/CV2),
             'E_admit_max_fJ': E_ADMIT,
             'note': 'eta is quoted against the PRE-STATED 43.481 fJ so the handed-down '
                     'threshold is not moved. The rectified charge integral shows a real '
                     'conventional driver must move 35.5 fC/hop (53.27 fJ) because Miller '
                     're-supply while the switch conducts is charge the 29.0 fC one-way '
                     'figure omits; using 53.27 would RAISE every eta, so 43.481 is the '
                     'conservative choice. N_min is computed from E_drive directly, so no '
                     'verdict depends on the denominator.'},
           'tau_TG_ps_MEASURED': SCR['tau_TG_ps_MEASURED'],
           'device_scaling_MEASURED': SCR['scaling'],
           'device_scaling_note': 'Ron*W and Cgate/W are size-invariant over 0.74-10 um '
                                  '(measured), so tau = Ron*Cgate is a single device '
                                  'constant: 1.884 ps for a 1:2 CMOS TG.'}

    # ---------------- loss laws -------------------------------------------------
    laws = {}
    for name, pref, beat in (('m1a_adiabatic_edges_te133', 'm1a2_te133_r', 816.755),):
        rows = sorted((DB[k]['RS_ohm'], DB[k]['E_drive_total_fJ']) for k in DB
                      if k.startswith(pref) and 'dcut_ps' in DB[k])
        m, b = lsq([r[0] for r in rows], [r[1] for r in rows])
        Rad = (E_ADMIT - b)/m
        laws[name] = dict(rows_R_E=rows, slope_fJ_per_ohm=m, intercept_fJ=b,
                          fit='E = %.4f + %.5g*R' % (b, m),
                          R_for_admission_ohm=Rad,
                          linear_RC_predicted_slope=7.02e-3,
                          measured_over_predicted=m/7.02e-3)
    # M1-D harmonic law from the two RS points at beat 534
    if 'm1d_h5' in DB and 'm1d_h5r200' in DB:
        r1, r2 = DB['m1d_h5'], DB['m1d_h5r200']
        R1, R2 = r1.get('RS_ohm', 25.0), r2.get('RS_ohm', 200.0)
        m = (r2['E_drive_total_fJ']-r1['E_drive_total_fJ'])/(R2-R1)
        b = r1['E_drive_total_fJ'] - m*R1
        Rad = (E_ADMIT-b)/m
        laws['m1d_harmonic_nh5'] = dict(
            rows_R_E=[(R1, r1['E_drive_total_fJ']), (R2, r2['E_drive_total_fJ'])],
            slope_fJ_per_ohm=m, intercept_fJ=b, fit='E = %.4f + %.5g*R' % (b, m),
            R_for_admission_ohm=Rad, Q_required_for_admission=Qnet(Rad, 534.0),
            note='steeper than the raised-cosine law because harmonic content raises '
                 'dv/dt, hence I^2R.  Q here is the LUMPED equivalent of a multi-mode '
                 'network, not a per-harmonic Q.')
    out['loss_laws'] = laws

    # ---------------- inductor inventory ---------------------------------------
    best = DB.get('m1d_h5b580_adv6') or DB.get('m1d_h5b580')
    beat_best = best.get('beat_ps', 580.0)
    out['inductor'] = {
        'C_net_per_bank_fF_MEASURED': C_NET*1e15,
        'beat_ps': beat_best,
        'L1_nH_vs_B': {str(B): round(L_nH(B, beat_best), 2) for B in (1,8,16,64,256)},
        'L3_nH_vs_B': {str(B): round(L_nH(B, beat_best, 3), 3) for B in (8,64,256)},
        'L5_nH_vs_B': {str(B): round(L_nH(B, beat_best, 5), 3) for B in (8,64,256)},
        'modes_needed': '3 (fundamental + 3rd + 5th) for the nh=5 waveform',
        'taps_needed': 'gt and gtp are anti-phase (a centre-tapped/differential pair is '
                       'ONE structure) plus a ~12-24 ps phase ADVANCE on the gtp tap to '
                       'satisfy the pMOS-cuts-early rule -> a poly-phase tap or a small '
                       'passive shifter, not a second network.',
        'inductor_count': '3-4 TOTAL for the whole chip, shared by ALL B banks '
                          '(same order as the sigma0 arch already assumes for the rail).',
        'B_invariance_PROVEN_algebraically': 'with B banks on one network the shared series '
              'R is R/B while C is B*C_net, so Q = 1/(omega*C_net*R) is B-INVARIANT; '
              'sharing buys a REALISABLE L (377 nH at B=1 -> 1.5 nH at B=256) without '
              'making Q harder.  This is what divides the per-bank tap cost by B and is '
              'the architectural prize.',
        'ASSUMED_not_measured': 'the inductor is IDEAL in every deck; its ESR is folded '
              'into the swept series R.  No metal inductor Q is measured here.'}

    # ---------------- M1-C switched-resonant recursion -------------------------
    fz = {k: DB[k] for k in DB if k.startswith('m1c_')}
    prod = []
    for k, d in fz.items():
        s = sum(d['aux_sw_%s_fJ' % n] for n in ('afn','afp','bfn','bfp'))
        cl = sum(d['aux_sw_%s_fJ' % n] for n in ('cal','cah','cbl','cbh'))
        R = 342.2/d['wfn']
        prod.append(s*R)
        fz[k] = dict(wfn=d['wfn'], wfp=d['wfp'], freeze_gate_fJ=round(s,3),
                     clamp_gate_fJ=round(cl,3), R_TG_ohm=round(R,1),
                     E_drive_total_fJ=d['E_drive_total_fJ'], eta_pct=d['eta_pct'],
                     N_min=d['N_min'], completeness='VBEND %s / E_hop %s / order %s'
                     % (d['completeness_VBEND'], d['completeness_Ehop'], d['cut_order']))
    K = sum(prod)/len(prod)
    ml, bl = laws['m1a_adiabatic_edges_te133']['slope_fJ_per_ohm'], \
             laws['m1a_adiabatic_edges_te133']['intercept_fJ']
    Ropt = math.sqrt(K/ml); Eopt = bl + ml*Ropt + K/Ropt
    clmin = min(v['clamp_gate_fJ'] for v in fz.values())*0.2027   # scaled 0.74 -> 0.15 um
    out['m1c_switched_resonant'] = dict(
        rows=fz, freeze_cost_times_R_fJ_ohm=round(K,0),
        analytic_optimum=dict(R_opt_ohm=round(Ropt,0),
            E_drive_no_clamps_fJ=round(Eopt,2),
            E_drive_with_minwidth_clamps_fJ=round(Eopt+clmin,2),
            eta_pct=round(100*(1-(Eopt+clmin)/CV2),1),
            N_min=round(rv.n_min(Eopt+clmin),1),
            R_opt_exceeds_cut_order_limit=bool(Ropt > 560.0),
            E_at_the_560ohm_order_limit_fJ=round(bl+ml*560+K/560+clmin,2)),
        verdict='FAIL.  The freeze switch is a B-INVARIANT recursion: its width must track '
                'the load it drives, so its gate charge tracks too and the per-bank cost '
                'does NOT amortise over B.  The cost-optimal R also exceeds the measured '
                'cut-order limit, so the optimum is not even reachable.')

    # ---------------- M2 stepwise ----------------------------------------------
    m2 = {k: dict(n=DB[k]['n'], ts_ps=round(DB[k]['te_ps']/DB[k]['n'],1),
                  E_drive_total_fJ=DB[k]['E_drive_total_fJ'],
                  rails_fJ=round(DB[k]['E_net_sources_fJ'],2),
                  tank_deficit_fJ=round(DB[k]['E_tank_deficit_fJ'],2),
                  step_switch_gates_fJ=round(DB[k]['E_aux_conventional_fJ'],2),
                  park_fJ=round(DB[k]['E_park_conventional_fJ'],2),
                  eta_pct=DB[k]['eta_pct'], N_min=DB[k]['N_min'],
                  completeness='VBEND %s / VA %s / E_hop %s / order %s'
                  % (DB[k]['completeness_VBEND'], DB[k]['completeness_VA'],
                     DB[k]['completeness_Ehop'], DB[k]['cut_order']))
          for k in DB if k.startswith('m2_n')}
    # analytic best case: minimum-width step switches, ideal 1/n rail residual only
    CTG_per_um = SCR['scaling']['Cg_per_W_n']*1.0 + SCR['scaling']['Cg_per_W_p']*2.0
    wmin = 0.15
    sw_cycles = lambda n: 2*n
    best_m2 = None
    for n in (2, 3, 4, 8):
        sw = sw_cycles(n)*(CTG_per_um*wmin*1e-15*1.5)*1.5*1e15*2   # 2 driven nodes
        E = CV2/n + sw + 2.39
        if best_m2 is None or E < best_m2[1]: best_m2 = (n, E, sw)
    out['m2_stepwise'] = dict(
        rows=m2,
        analytic_best_case=dict(
            n=best_m2[0], E_drive_fJ=round(best_m2[1],2),
            step_switch_gates_fJ=round(best_m2[2],2),
            ideal_1_over_n_residual_fJ=round(CV2/best_m2[0],2),
            park_fJ=2.39, eta_pct=round(100*(1-best_m2[1]/CV2),1),
            N_min=round(rv.n_min(best_m2[1]),1),
            assumptions='minimum-width (0.15/0.30 um) step switches, ideal tanks with no '
                        'droop, no hold-switch Miller traffic -- i.e. strictly better than '
                        'anything buildable.'),
        scaling_law='residual/CV2 = 1/n + 2*alpha*tau*n^2/T_edge : the saving saturates as '
                    '1-1/n while the step-switch recursion grows as n^2 (count n, size n, '
                    'because t_step = T_edge/n forces W ~ n).  With the MEASURED tau = '
                    '1.884 ps and T_edge <= 133 ps the optimum is n ~ 2 and the best '
                    'possible recovery is ~10%.',
        verdict='FAIL, and fails WORSE at larger n -- exactly as pre-registered (P3).')

    # ---------------- M3 ------------------------------------------------------
    m3 = {}
    for k in DB:
        if not k.startswith('m3_hop_'): continue
        d = DB[k]
        m3['VGH=%.2f' % d['VGH']] = dict(
            Q_total_fC=round(d['Q_gt_fC']+d['Q_gtp_fC']+d['Q_pk_fC'],3),
            CV2_conv_fJ=round(d['CV2_conv_fJ'],2), VBEND=d['VBEND'],
            VA_open=d['VA_open'], E_hop_open_fJ=d['E_hop_open_fJ'],
            N_min_if_conventional=round(d['N_min_at_CV2'],1),
            completeness='VBEND %s / VA %s / E_hop %s / cells %s'
            % (d['completeness_VBEND'], d['completeness_VA'],
               d['completeness_Ehop'], d['cells_settled']))
    out['m3_lower_VGH'] = dict(
        rows=m3,
        verdict='P1 CONFIRMED.  CV2 scales ~V^1.86 (measured), so reaching 12.747 fJ by '
                'voltage alone needs VGH ~ 0.81 V, but completeness already fails at '
                '1.20 V (VBEND out of band) and E_hop leaves its +-5% band at 1.35 V.  '
                'M3 alone ADMITS NOTHING.  Its honest role is a x0.84 MULTIPLIER at '
                'VGH=1.35 bought for a +5.8% E_hop penalty -- and that penalty is a real '
                'cost on the same ledger, so the multiplier is close to free-standing zero.')

    # ---------------- admission table ------------------------------------------
    tbl = []
    def add(name, E, comp='', note=''):
        v = RA.verdict(E)
        tbl.append(dict(mechanism=name, E_fJ=round(E,3), eta_pct=round(100*(1-E/CV2),2),
                        N_min=v['N_min'], sha_bush=v['sha_slice']['bush_levels'],
                        sha_gates_pct=v['sha_slice']['gates_covered_pct'],
                        alu_bush=v['alu_top_bush']['bush_levels'],
                        alu_gates_pct=v['alu_top_bush']['gates_covered_pct'],
                        fpu63='ADMIT' if 'PASS' in v['alu_fpsat_minbank63'] else 'EXCLUDED',
                        completeness=comp, note=note))
    add('committed as-built stdcell tap (B=8)', 302.8+102.4/8, 'PASS', 'the 28dcece row')
    add('conventional CMOS tap, gate charge only', CV2, 'n/a', 'pre-stated reference')
    add('M3 VGH=1.35 (lowest VBEND-passing)', 44.71, 'E_hop FAIL (+5.8%)', '')
    add('M2 stepwise n=2 MEASURED', m2.get('m2_n2', {}).get('E_drive_total_fJ', 0),
        m2.get('m2_n2', {}).get('completeness',''), '')
    add('M2 stepwise n=4 MEASURED', m2.get('m2_n4', {}).get('E_drive_total_fJ', 0),
        m2.get('m2_n4', {}).get('completeness',''), '')
    add('M2 analytic best case (min-width, ideal tanks)', best_m2[1], 'n/a',
        'strictly better than buildable')
    add('M1-C switched resonant, freeze 0.74/1.12 um MEASURED',
        fz['m1c_te133_w074']['E_drive_total_fJ'], fz['m1c_te133_w074']['completeness'], '')
    add('M1-C analytic optimum (best possible switched)', Eopt+clmin, 'n/a',
        'R_opt violates the cut-order limit')
    for k in sorted(DB):
        if k.startswith('m1a2_te') and 'dcut_ps' in DB[k]:
            d = DB[k]
            add('M1-A adiabatic edges te=%g RS=%g' % (d['te_ps'], d['RS_ohm']),
                d['E_drive_total_fJ'],
                'VBEND %s / VA %s / E_hop %s / cells %s / order %s'
                % (d['completeness_VBEND'], d['completeness_VA'], d['completeness_Ehop'],
                   d['cells_settled'], d['cut_order']),
                'resonator IDEAL, no freeze switch counted')
    for k in sorted(DB):
        if k.startswith('m1b_') or k.startswith('m1d_'):
            d = DB[k]
            o = d.get('order_device_ref') or cutorder.order(k)
            ordv = ('PASS' if (o['pmos_vs_nmos'] is not None and o['pmos_vs_nmos'] <= 5.0
                               and o['park_vs_nmos'] is not None and o['park_vs_nmos'] >= 0)
                    else 'FAIL')
            add('%s (free-running, NO per-edge switch)' % k, d['E_drive_total_fJ'],
                'VBEND %s / VA %s / E_hop %s / cells %s / order %s'
                % (d['completeness_VBEND'], d['completeness_VA'], d['completeness_Ehop'],
                   d['cells_settled'], ordv),
                'pMOS-nMOS %+.1f ps, park-nMOS %+.1f ps'
                % (o['pmos_vs_nmos'] or 0, o['park_vs_nmos'] or 0))
    add('ideal-PWL floor (no mechanism can beat this)', 3.522, 'PASS', 'EGT_D-EGT_Z')
    out['admission_table'] = tbl

    # sustaining-amplifier sensitivity on the best passing row
    Eb = best['E_drive_total_fJ']; park = best['E_park_conventional_fJ']
    res = Eb - park
    out['sustaining_amplifier_sensitivity'] = dict(
        best_row=best['tag'], E_drive_fJ=round(Eb,3), park_conventional_fJ=round(park,3),
        resonant_part_fJ=round(res,3),
        eta_amp_min_for_admission=round(res/(E_ADMIT-park), 4),
        note='a free-running resonant network needs a sustaining amplifier to replenish '
             'its loss; only the RESONANT part of the ledger passes through it.  '
             'Admission survives any sustaining efficiency above this figure.')
    json.dump(out, open(os.path.join(HERE, 'RESULTS.json'), 'w'), indent=1)

    # ---------------- print ---------------------------------------------------
    print('=== MEASURED loss laws ===')
    for k, v in laws.items():
        print('  %-28s %s   R for E<=12.747: %.0f ohm' % (k, v['fit'], v['R_for_admission_ohm']))
        if 'Q_required_for_admission' in v:
            print('  %-28s -> lumped network Q required >= %.1f' % ('', v['Q_required_for_admission']))
    print('=== inductor (ASSUMED ideal; L to resonate the MEASURED %.2f fF/bank at the %g ps beat) ==='
          % (C_NET*1e15, beat_best))
    print('    L1: ' + '  '.join('B=%s:%.1fnH' % (b, l) for b, l in out['inductor']['L1_nH_vs_B'].items()))
    print('    modes %s ; inductors %s' % (out['inductor']['modes_needed'], out['inductor']['inductor_count']))
    print('=== M1-C analytic optimum: R_opt %.0f ohm -> E %.2f fJ (+min clamps %.2f) = eta %.1f%% N_min %.1f%s'
          % (Ropt, Eopt, clmin, 100*(1-(Eopt+clmin)/CV2), rv.n_min(Eopt+clmin),
             '  [R_opt VIOLATES the cut-order limit]' if Ropt > 560 else ''))
    print('=== M2 analytic best case: n=%d -> E %.2f fJ = eta %.1f%% N_min %.1f'
          % (best_m2[0], best_m2[1], 100*(1-best_m2[1]/CV2), rv.n_min(best_m2[1])))
    print('=== sustaining amplifier: admission survives eta_amp >= %.1f%%'
          % (100*out['sustaining_amplifier_sensitivity']['eta_amp_min_for_admission']))
    print()
    print('=== ADMISSION TABLE  (threshold E <= 12.747 fJ/bank/hop  <=>  N_min <= 63) ===')
    print('  %-52s %9s %8s %7s %-9s %-9s %-9s' %
          ('mechanism', 'E fJ', 'eta%', 'N_min', 'sha bush', 'alu bush', 'fpu-63'))
    for t in tbl:
        print('  %-52s %9.3f %8.2f %7.1f %-9s %-9s %-9s' %
              (t['mechanism'][:52], t['E_fJ'], t['eta_pct'], t['N_min'],
               t['sha_bush'], t['alu_bush'], t['fpu63']))
        print('  %-52s   completeness: %s%s' % ('', t['completeness'],
              ('   [%s]' % t['note']) if t['note'] else ''))

if __name__ == '__main__':
    main()
