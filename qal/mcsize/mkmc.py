#!/usr/bin/env python3
"""qal/mcsize/mkmc.py -- turn a committed QAL chain deck into a mismatch-MC deck.

Every sg13_lv_* instance gets its OWN independent AGAUSS DELVTO draw with the
sigma the PDK prescribes for ITS geometry:
    sigma = A_VT / sqrt(W*L)       A_VT: n 0.0039, p 0.0022  V*um
            (MEASURED, /usr/local/src/IHP-Open-PDK/.../sg13g2_moslv_mismatch.lib)

The deck is otherwise untouched EXCEPT for three cost reductions, all of which
are electrically inert and all of which are declared:
  1. the .print block is dropped              (output only)
  2. the 1F energy integrators CX*/BX*/RX* and their .measure lines are dropped.
     They hang on their OWN isolated nodes and drive nothing in the circuit, so
     removing them cannot change the solution; they exist to meter energy, which
     this study does not ask for.
  3. the transient is truncated just past the last commit instant the criterion
     needs. The RETURN/recovery phase after that is an energy question, not a
     data question.
A --sizing option rescales named device classes for Phase 2.
"""
import re, sys, json, math, argparse

A_VT = {'n': 0.0039, 'p': 0.0022}          # V*um, MEASURED from the PDK mismatch lib

def sigma_of(kind, w_um, l_um):
    return A_VT[kind] / math.sqrt(w_um * l_um)

UNIT = {'u': 1e6, 'n': 1e9, 'm': 1e3, '': 1.0}   # multiplier to convert to um

def to_um(tok):
    m = re.fullmatch(r'([-+0-9.eE]+)([a-zA-Z]*)', tok)
    v = float(m.group(1)); s = m.group(2).lower()
    if s == 'u': return v * 1e6 / 1e6 * 1.0 if False else v      # '0.74u' -> 0.74 um
    if s == 'n': return v * 1e-3
    if s == '':  return v * 1e6                                   # bare metres
    raise ValueError(tok)

XLINE = re.compile(r'^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(sg13_lv_[np]mos)\s+(.*)$', re.I)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--tend', type=float, required=True, help='ps')
    ap.add_argument('--measures', required=True, help='json: {tag:{t_ps:..,nodes:[..]}}')
    ap.add_argument('--nsamp', type=int, default=200)
    ap.add_argument('--seed', type=int, default=1001)
    ap.add_argument('--sizing', default='{}',
                    help='json {"<w_um>:<kind>": mult} or {"class":{"w":..,"l":..}} scale map')
    ap.add_argument('--nomismatch', action='store_true')
    ap.add_argument('--kvt', type=float, default=1.0,
                    help='scale EVERY sigma_Vt by this, geometry UNCHANGED. The pure-sigma '
                         'control: it separates "mismatch got smaller" from "the cell got '
                         'bigger and slower", which is the confound in any sizing sweep. '
                         'kvt=4 is the stress point the committed th22 MC used.')
    a = ap.parse_args()

    sizing = json.loads(a.sizing)          # key "0.74:n" -> {"w":2.0,"l":1.0}
    meas = json.loads(open(a.measures).read())

    src = open(a.src).read().splitlines()
    out, devs = [], []
    ndrop_int = 0
    for ln in src:
        s = ln.strip()
        u = s.upper()
        if u.startswith('.PRINT'):                       continue
        if re.match(r'^(CX|BX|RX)\S*\s', s):             ndrop_int += 1; continue
        if u.startswith('.MEASURE'):                     continue
        if u.startswith('.TRAN'):
            p = s.split()
            out.append(f'.tran {p[1]} {a.tend:.4f}p {p[3] if len(p)>3 else "0"} {p[4] if len(p)>4 else "0.25p"}')
            continue
        if 'sg13lv_compat.sp' in s:
            out.append('.include "/usr/local/src/stat-sim/qal/mcsize/shim_mc.sp"'); continue
        m = XLINE.match(s)
        if m:
            name, d, g, sn, b, mod, rest = m.groups()
            kind = 'n' if mod.lower().endswith('nmos') else 'p'
            wm = re.search(r'\bw=(\S+)', rest, re.I); lm = re.search(r'\bl=(\S+)', rest, re.I)
            w = to_um(wm.group(1)); l = to_um(lm.group(1))
            key = f'{w:g}:{kind}'
            sc = sizing.get(key, {})
            w2 = w * sc.get('w', 1.0); l2 = l * sc.get('l', 1.0)
            sig = 0.0 if a.nomismatch else a.kvt * sigma_of(kind, w2, l2)
            rest2 = re.sub(r'\bw=\S+', f'w={w2:.6g}u', rest, flags=re.I)
            rest2 = re.sub(r'\bl=\S+', f'l={l2:.6g}u', rest2, flags=re.I)
            out.append(f'{name} {d} {g} {sn} {b} {mod} {rest2} dvt={{AGAUSS(0,{sig:.6e},1)}}')
            devs.append(dict(name=name, kind=kind, w_um=w2, l_um=l2, sigma_mV=sig*1e3,
                             w_nom_um=w, l_nom_um=l, node_d=d, node_g=g))
            continue
        if u.startswith('.END') and not u.startswith('.ENDS'):
            break
        out.append(ln)

    mnames = []
    for tag, spec in meas.items():
        t = spec['t_ps']
        for nd in spec['nodes']:
            nm = f'M_{tag}_{nd}'.replace('.', '_')
            out.append(f'.measure tran {nm} FIND V({nd}) AT={t:.6f}p')
            mnames.append(nm)

    out.append('')
    out.append('.SAMPLING useExpr=true')
    out.append(f'.options SAMPLES numsamples={a.nsamp} SAMPLE_TYPE=MC SEED={a.seed}')
    out.append('+ measures=' + ','.join(mnames))
    out.append('+ OUTPUT_SAMPLE_STATS=true stdoutput=true')
    out.append('.end')
    open(a.out, 'w').write('\n'.join(out) + '\n')

    tot_area = sum(d['w_um'] * d['l_um'] for d in devs)
    json.dump(dict(src=a.src, out=a.out, n_dev=len(devs), n_meas=len(mnames),
                   dropped_integrator_lines=ndrop_int, tend_ps=a.tend,
                   nsamp=a.nsamp, seed=a.seed, sizing=sizing, kvt=a.kvt,
                   total_device_area_um2=tot_area, devices=devs),
              open(a.out + '.meta.json', 'w'), indent=1)
    print(f'{a.out}: {len(devs)} mismatched devices, {len(mnames)} measures, '
          f'{ndrop_int} integrator lines dropped, area {tot_area:.3f} um^2')

main()
