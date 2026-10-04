#!/usr/bin/env python3
"""Analyze the self-timed vs clocked SHA round-core slice: functional match +
per-round energy-vs-duty. Mirror of ../fsm/analyze_fsm.py for the 8-bit q state.

Functional: decode q7..q0 over time; golden and self-timed must capture the SAME
round-op sequence (bit-identical trajectory). Energy: EVDD per deck (supply
integral); ratio golden/self-timed vs duty is the clock-floor win and should GROW
with idle duty — the per-round analogue of the accumulator's 0.44x->1.88x trend.
Run by the ORCHESTRATOR after Xyce has produced sr_*.cir.prn and sr_*.cir.mt0.
"""
import json, glob, re

NB = 8


def load(prn):
    f = open(prn); hdr = f.readline().split(); cols = {n: i for i, n in enumerate(hdr)}; rows = []
    for line in f:
        p = line.split()
        if not p or p[0].lower().startswith('end'):
            continue
        try:
            rows.append([float(x) for x in p])
        except ValueError:
            continue
    return cols, rows


def col(cols, want):
    for k in cols:
        if k.upper().startswith(want.upper()):
            return cols[k]
    return None


def at(t, ts, vs):
    if t <= ts[0]:
        return vs[0]
    for k in range(1, len(ts)):
        if ts[k] >= t:
            f = (t - ts[k - 1]) / (ts[k] - ts[k - 1]) if ts[k] != ts[k - 1] else 0
            return vs[k - 1] + f * (vs[k] - vs[k - 1])
    return vs[-1]


def state_at(t, ts, S):
    v = 0
    for i in range(NB):
        if at(t, ts, S[i]) > 0.6:
            v |= (1 << i)
    return v


def evdd(base):
    for fn in glob.glob(base + ".cir.mt0") + glob.glob(base + ".mt0"):
        m = re.search(r'EVDD\s*=\s*([-+0-9.eE]+)', open(fn).read())
        if m:
            return float(m.group(1))
    return None


def analyze(base):
    meta = json.load(open(base + ".meta.json"))
    cols, rows = load(base + ".cir.prn")
    ti = col(cols, 'TIME'); ts = [r[ti] for r in rows]
    S = [[r[col(cols, 'V(q%d)' % i)] for r in rows] for i in range(NB)]
    Tc = meta['Tc_ns'] * 1e-9; d = meta['duty_cycles']; n = meta['nops']; Ttot = meta['Ttot_ns'] * 1e-9
    traj = []
    for k in range(n):
        t = min(0.5e-9 + (1 + k * d) * Tc + 1.0e-9, Ttot - 0.05e-9)
        traj.append(state_at(t, ts, S))
    final = state_at(Ttot - 0.05e-9, ts, S)
    return {"mode": meta['mode'], "duty": d, "nops": n, "final": final, "traj": traj,
            "E_fJ": (evdd(base) or 0) * 1e15, "Ttot_ns": meta['Ttot_ns']}


if __name__ == "__main__":
    duties = [2, 4, 10]
    print("=== FUNCTIONAL (golden vs self-timed round-core capture sequence) ===")
    allmatch = True; res = {}
    for d in duties:
        g = analyze("sr_g_d%d" % d); st = analyze("sr_st_d%d" % d); res[d] = (g, st)
        match = g['traj'] == st['traj'] and g['final'] == st['final']
        allmatch = allmatch and match
        print("duty 1/%-2d  golden traj=%s | selftimed traj=%s  %s"
              % (d, g['traj'], st['traj'], "MATCH" if match else "*** MISMATCH ***"))
    print("FUNCTIONAL:", "PASS" if allmatch else "*** FAIL ***")
    print("\n=== PER-ROUND ENERGY vs DUTY (EVDD over the window; same %d ops each) ===" % 4)
    print("%-8s %12s %12s %10s %s" % ("duty", "golden fJ", "selftimed fJ", "ratio", "window"))
    for d in duties:
        g, st = res[d]
        ratio = g['E_fJ'] / st['E_fJ'] if st['E_fJ'] else float('nan')
        print("1/%-6d %12.1f %12.1f %9.2fx  %s ns" % (d, g['E_fJ'], st['E_fJ'], ratio, g['Ttot_ns']))
    print("\nPer-op self-timed energy / nops = the ROUND-CORE anchor (fJ/round) for")
    print("composition: E_hash(duty) ~ 64*rounds * E_round + schedule + H-add, with")
    print("the self-timed term DUTY-FLAT and the clocked term carrying the clock floor.")
