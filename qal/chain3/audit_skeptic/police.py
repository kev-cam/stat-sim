#!/usr/bin/env python3
"""Independent skeptic policing of chain3 rows: read RAW .prn only.
Nothing here imports the campaign's extract.py or trusts its rows.json / .mt0.
Checkpoint times are parsed out of the .cir's own .measure AT= lines so the
convention is the one the deck itself used, but every number is recomputed
from the waveform by linear interpolation.
"""
import re, sys, os, json, bisect

M = 8


def load_prn(path):
    with open(path) as f:
        hdr = f.readline().split()
        cols = {n.upper(): i for i, n in enumerate(hdr)}
        rows = []
        for ln in f:
            p = ln.split()
            if len(p) != len(hdr):
                continue
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                continue
    t = [r[cols['TIME']] for r in rows]
    return cols, rows, t


def at(cols, rows, t, name, tq):
    """linear interpolation of signal `name` at time tq (seconds)"""
    j = cols[name.upper()]
    i = bisect.bisect_left(t, tq)
    if i <= 0:
        return rows[0][j]
    if i >= len(t):
        return rows[-1][j]
    t0, t1 = t[i - 1], t[i]
    v0, v1 = rows[i - 1][j], rows[i][j]
    if t1 == t0:
        return v1
    return v0 + (v1 - v0) * (tq - t0) / (t1 - t0)


def ckpts(cir):
    """pull the K1/K2/K3/D/B1/B2 absolute times (ps) out of the deck"""
    out = {}
    for ln in open(cir):
        m = re.match(r"\.measure tran (VR1|VR2|VR3)(\w+) FIND V\(rail\d\) AT=([\d.]+)p", ln)
        if m:
            out[m.group(2)] = float(m.group(3))
    return out


def analyse(cir, prn, label):
    cp = ckpts(cir)
    cols, rows, t = load_prn(prn)
    # bank k checkpoint: bank1->K1, bank2->K2, bank3->K3 ; D = tail
    res = {'label': label, 'cir': cir, 'ckpt_ps': cp}
    banks = {}
    for k, key in ((1, 'K1'), (2, 'K2'), (3, 'K3')):
        for tag, ck in (('ckpt', key), ('tail', 'D')):
            tq = cp[ck] * 1e-12
            rail = at(cols, rows, t, 'V(RAIL%d)' % k, tq)
            cells = []
            for i in range(M):
                o = at(cols, rows, t, 'V(O%d_%d)' % (k, i), tq)
                # input parity: bank1 in = 1,0,1,0..  every bank inverts
                # bank1 cell i: in = 1 if i even -> PULL-DOWN (output low)
                # bank2 cell i: in = o1_i ; o1_i low for i even -> PULL-UP
                # bank3 cell i: in = o2_i ; o2_i high for i even -> PULL-DOWN
                even = (i % 2 == 0)
                pull_down = even if k in (1, 3) else (not even)
                s = (1.0 - o / rail) if pull_down else (o / rail)
                cells.append({'i': i, 'kind': 'DN' if pull_down else 'UP',
                              'V': o, 'settle_pct': 100.0 * s,
                              'guard_ok': (o <= 0.10 * rail) if pull_down else (o >= 0.50 * rail)})
            banks['b%d_%s' % (k, tag)] = {
                't_ps': cp[ck], 'rail': rail,
                'min_UP': min(c['settle_pct'] for c in cells if c['kind'] == 'UP'),
                'min_DN': min(c['settle_pct'] for c in cells if c['kind'] == 'DN'),
                'worst': min(c['settle_pct'] for c in cells),
                'worst_kind': min(cells, key=lambda c: c['settle_pct'])['kind'],
                'guard_fails': [c['i'] for c in cells if not c['guard_ok']],
                'cells': cells}
    res['banks'] = banks
    return res


if __name__ == '__main__':
    out = {}
    for spec in sys.argv[1:]:
        cir, prn, label = spec.split(',')
        out[label] = analyse(cir, prn, label)
    json.dump(out, open('police_out.json', 'w'), indent=1)
    for lab, r in out.items():
        print('=' * 78)
        print(lab, ' ckpts ps:', {k: round(v, 3) for k, v in r['ckpt_ps'].items()})
        for key in sorted(r['banks']):
            b = r['banks'][key]
            print('  %-10s t=%9.3fps rail=%7.4f  minUP=%7.2f%% minDN=%7.2f%%  worst=%7.2f%%(%s) guardfail=%s'
                  % (key, b['t_ps'], b['rail'], b['min_UP'], b['min_DN'], b['worst'],
                     b['worst_kind'], b['guard_fails']))
        for key in ('b3_ckpt', 'b3_tail'):
            print('   --- %s per-cell:' % key)
            for c in r['banks'][key]['cells']:
                print('        o3_%d %s V=%+.5f  s=%7.2f%%  guard=%s'
                      % (c['i'], c['kind'], c['V'], c['settle_pct'], 'ok' if c['guard_ok'] else 'FAIL'))
