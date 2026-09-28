import json, sys
sys.path.insert(0,'/usr/local/src/stat-sim/qal/park')
import pk as P
BASE_PAIR_1F = 2.98354068
BASE_PAIR_TZ = 2.9742694747776132
BASE_EGTP_1F = 5.7273646000000005
BASE_DROOP   = -28.901825735754727
def row(f):
    r = P.analyse(f); ck = r['ck']['pre_811.755']; p = r['park']; d=r['park_drive']
    egt, egtp = r['drive']['gt']['E_source_1F_fJ'], r['drive']['gtp']['E_source_1F_fJ']
    tgt, tgtp = r['drive']['gt']['E_source_trapz_fJ'], r['drive']['gtp']['E_source_trapz_fJ']
    return dict(row=f.replace('.cir.prn',''),
      VBEND=ck['VBEND'], VBEND_g=ck['VBEND_gate'],
      E_hop=ck.get('E_hop_open_fJ'), Ehop_g=ck.get('Ehop_gate'),
      VA_open=r['VA_open'], VA_g=r['VA_gate'], cells=ck['cells_settled'],
      cellsV=ck['cells_V'][1],
      nmos_cut=r['nmos_cut_ps'], pmos_m_nmos=r['pmos_vs_nmos_ps'],
      park_close=p.get('park_close_dev_ps'), park_m_cut=p.get('park_close_minus_nmos_cut_ps'),
      park_ON_t0=p.get('park_ON_at_t0'), park_prehop_rel=p.get('park_prehop_release_ps'),
      park_release=p.get('park_release_dev_ps'),
      Vpk_t0=p['V_pk_at_t0'], Vpk_max=p['V_pk_max'], Vpk_min=p['V_pk_min'], Vpk_tD=p['V_pk_at_tD'],
      swmax=p['V_sw_max_post_open'], swmin=p['V_sw_min_post_open'],
      H1_raw=p['H1_max_V_sw_over_hold'], H1_settle=p.get('H1_settle_delay_ps'),
      H1_after=p.get('H1_max_abs_V_sw_after_settle'),
      H2_droop=p['H2_droop_mV'], H2_vs_base=p['H2_droop_mV']-BASE_DROOP,
      E_gt_1F=egt, E_gtp_1F=egtp, pair_1F=egt+egtp, d_pair_1F=(egt+egtp)-BASE_PAIR_1F,
      E_gt_tz=tgt, E_gtp_tz=tgtp, pair_tz=tgt+tgtp, d_pair_tz=(tgt+tgtp)-BASE_PAIR_TZ,
      dE_gtp_1F=egtp-BASE_EGTP_1F,
      E_pk_1F=d.get('E_pk_1F_fJ'), E_pk_tz=d.get('E_pk_source_trapz_fJ'),
      E_pk_R=d.get('E_pk_Rseries_fJ'), E_pk_node=d.get('E_pk_into_gate_node_fJ'),
      Q_pk_net=d.get('Q_pk_net_fC'), Q_pk_rect=d.get('Q_pk_rect_1F_fC'),
      pk_closure=d.get('closure_pct'),
      Q_gt_net=r['drive']['gt']['Q_net_fC'], Q_gtp_net=r['drive']['gtp']['Q_net_fC'],
      ehi=r['ehi_fJ'], ehi580=r.get('ehi_at_580_fJ'), EA_C=r['EA_C_fJ'], IPK=r['IPK_uA'])
if __name__=='__main__':
    out=[row(f) for f in sys.argv[1:]]
    json.dump(out, open('/tmp/rows.json','w'), indent=1, default=str)
    for o in out:
        print("=== %s" % o['row'])
        print("   GATES  VBEND %.6f[%s]  Ehop %.5f[%s]  VA %.5f[%s]  cells %s  pMOS-nMOS %+.3f ps" %
              (o['VBEND'],o['VBEND_g'],o['E_hop'],o['Ehop_g'],o['VA_open'],o['VA_g'],o['cells'],o['pmos_m_nmos']))
        print("   PARK   Vpk t0 %+.4f min %+.4f max %+.4f tD %+.4f | close %s  close-cut %s  release %s | ON@t0 %s prehop_rel %s" %
              (o['Vpk_t0'],o['Vpk_min'],o['Vpk_max'],o['Vpk_tD'],
               ('%.3f'%o['park_close']) if o['park_close'] else None,
               ('%+.3f'%o['park_m_cut']) if o['park_m_cut'] is not None else None,
               ('%.3f'%o['park_release']) if o['park_release'] else None,
               o['park_ON_t0'], ('%.3f'%o['park_prehop_rel']) if o['park_prehop_rel'] else None))
        print("   HOLD   sw post-open [%.5f, %.5f] | H1 raw %.5f settle %s ps then max|sw| %s | H2 droop %.3f mV (base %+.3f)" %
              (o['swmin'],o['swmax'],o['H1_raw'],
               ('%.2f'%o['H1_settle']) if o['H1_settle'] is not None else None,
               ('%.5f'%o['H1_after']) if o['H1_after'] is not None else None,
               o['H2_droop'],o['H2_vs_base']))
        print("   LEDGER E_gt %+.6f  E_gtp %+.6f  pair %.6f (dpair %+.6f) | dE_gtp %+.6f | E_pk %s (trapz %s, R %s, node %s, closure %s)" %
              (o['E_gt_1F'],o['E_gtp_1F'],o['pair_1F'],o['d_pair_1F'],o['dE_gtp_1F'],
               ('%.6f'%o['E_pk_1F']) if o['E_pk_1F'] is not None else None,
               ('%.6f'%o['E_pk_tz']) if o['E_pk_tz'] is not None else None,
               ('%.6f'%o['E_pk_R']) if o['E_pk_R'] is not None else None,
               ('%.6f'%o['E_pk_node']) if o['E_pk_node'] is not None else None,
               ('%.2e'%o['pk_closure']) if o['pk_closure'] is not None else None))
        print("   MISC   Qnet gt %.4f gtp %.4f pk %s fC | ehi %.4f (580: %.4f) | EA_C %.5f | IPK %.3f" %
              (o['Q_gt_net'],o['Q_gtp_net'],
               ('%.4f'%o['Q_pk_net']) if o['Q_pk_net'] is not None else None,
               o['ehi'],o['ehi580'],o['EA_C'],o['IPK']))
        print()
