import re
p='/usr/local/src/stat-sim/qal/lsweep/lsw.py'; s=open(p).read()
# CA becomes a per-point parameter (bank-A size); default = committed 35.979 fF
s=s.replace('def probe_lines(l_nh, total_um, rs=RS_REF, edge=EDGE_REF, dv=DV):\n    cser = (CA_FF / 2.0) * 1e-15',
            'def probe_lines(l_nh, total_um, rs=RS_REF, edge=EDGE_REF, dv=DV, ca=CA_FF):\n    cser = (ca / 2.0) * 1e-15')
s=s.replace('        ".param LT=%gn RS=%g CA=%gf" % (l_nh, rs, CA_FF),\n        "CA bka 0 {CA}",\n        "VHI vhi 0 %g" % VGH,\n        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)"',
            '        ".param LT=%gn RS=%g CA=%gf" % (l_nh, rs, ca),\n        "CA bka 0 {CA}",\n        "VHI vhi 0 %g" % VGH,\n        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)"')
s=s.replace('def hop_lines(l_nh, total_um, t_half_ps, rs=RS_REF, edge=EDGE_REF, tail=TAIL_REF, dv=DV):',
            'def hop_lines(l_nh, total_um, t_half_ps, rs=RS_REF, edge=EDGE_REF, tail=TAIL_REF, dv=DV, ca=CA_FF):')
s=s.replace('        ".param LT=%gn RS=%g CA=%gf" % (l_nh, rs, CA_FF),\n        "CA bka 0 {CA}",\n        "VHI vhi 0 %g" % VGH,\n        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"',
            '        ".param LT=%gn RS=%g CA=%gf" % (l_nh, rs, ca),\n        "CA bka 0 {CA}",\n        "VHI vhi 0 %g" % VGH,\n        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"')
s=s.replace('def extract(mt0_path, l_nh, total_um, t_half_ps, rs=RS_REF, edge=EDGE_REF,\n            tail=TAIL_REF, dv=DV):',
            'def extract(mt0_path, l_nh, total_um, t_half_ps, rs=RS_REF, edge=EDGE_REF,\n            tail=TAIL_REF, dv=DV, ca=CA_FF):')
s=s.replace('e_outa_exact = 0.5 * CA_FF * (dv * dv - m["VAEND"] ** 2)','e_outa_exact = 0.5 * ca * (dv * dv - m["VAEND"] ** 2)')
s=s.replace('va_open = dv - qlt[2] / CA_FF','va_open = dv - qlt[2] / ca')
s=s.replace('closQ = (qlt[3] - CA_FF * (dv - m["VAEND"])) / (CA_FF * (dv - m["VAEND"])) * 100',
            'closQ = (qlt[3] - ca * (dv - m["VAEND"])) / (ca * (dv - m["VAEND"])) * 100')
s=s.replace('        L_nH=l_nh, total_um=total_um, rs_ohm=rs, edge_ps=edge, tail_ps=tail, dv=dv,',
            '        L_nH=l_nh, total_um=total_um, rs_ohm=rs, edge_ps=edge, tail_ps=tail, dv=dv, ca_fF=ca,')
s=s.replace('def probe(tag, l_nh, total_um, rs=RS_REF, edge=EDGE_REF, verbose=True, dv=DV):\n    fn = "p_%s.cir" % tag\n    path, msg = run(fn, probe_lines(l_nh, total_um, rs, edge, dv))',
            'def probe(tag, l_nh, total_um, rs=RS_REF, edge=EDGE_REF, verbose=True, dv=DV,\n          ca=CA_FF):\n    fn = "p_%s.cir" % tag\n    path, msg = run(fn, probe_lines(l_nh, total_um, rs, edge, dv, ca))')
s=s.replace('def point(tag, l_nh, total_um, rs=RS_REF, edge=EDGE_REF, tail=TAIL_REF,\n          verbose=True, dv=DV):\n    pr, st = probe(tag, l_nh, total_um, rs, edge, verbose, dv)',
            'def point(tag, l_nh, total_um, rs=RS_REF, edge=EDGE_REF, tail=TAIL_REF,\n          verbose=True, dv=DV, ca=CA_FF):\n    pr, st = probe(tag, l_nh, total_um, rs, edge, verbose, dv, ca)')
s=s.replace('    lines, meta = hop_lines(l_nh, total_um, th, rs, edge, tail, dv)',
            '    lines, meta = hop_lines(l_nh, total_um, th, rs, edge, tail, dv, ca)')
s=s.replace('        row = extract(path + ".mt0", l_nh, total_um, th, rs, edge, tail, dv)',
            '        row = extract(path + ".mt0", l_nh, total_um, th, rs, edge, tail, dv, ca)')
s=s.replace('            row["xc_VA_open"] = dv - lg["qlt_C"] / CA_FF','            row["xc_VA_open"] = dv - lg["qlt_C"] / ca')
open(p,'w').write(s)
import ast; ast.parse(s); print("patch_ca applied, syntax OK")
