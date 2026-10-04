#!/usr/bin/env python3
"""Analyze the self-timed vs clocked SHA-256 round-slice FSM: functional match +
energy/duty table. Companion to gen_sha_slice_fsm.py.

FUNCTIONAL: decode the 8-bit state s7..s0 over time; BOTH decks must follow the same
round trajectory, and that trajectory must equal an INDEPENDENT reference computed
from the sha_slice.v maj/ch/sum definitions (NOT self-asserted). The reference is the
golden model of the slice recurrence a_{k+1} = (a_k + (maj(a_k,b,c) ^ ch(e,f,g))) & 0xFF.
ENERGY: EVDD per deck (supply integral); the ratio golden/self-timed vs duty is the
clock-floor win -- it should grow with idle duty (the per-round duty-shaped win), the
same shape the 4-bit accumulator measured (0.44x full -> 1.88x at 1/10 and widening).

Reads *.cir.mt0 (EVDD) and *.cir.prn (state) that the orchestrator's Xyce runs produce.
Does NOT run Xyce. If a deck's outputs are missing it is reported as PENDING, not failed.
"""
import json, glob, sys, re, os

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


def state_at(t, ts, S, vth):
    v = 0
    for i in range(NB):
        if at(t, ts, S[i]) > vth:
            v |= (1 << i)
    return v


def ref_traj(bcefg, nops):
    """Independent golden from sha_slice.v maj/ch/sum (the reference, re-derived
    here so the analyzer does not trust the generator's stored copy)."""
    b, c, e, f, g = (bcefg[k] for k in ("b", "c", "e", "f", "g"))
    a = 0; traj = []
    for _ in range(nops):
        maj = (a & b) ^ (a & c) ^ (b & c)
        ch = (e & f) ^ ((~e & 0xFF) & g)
        T = (maj ^ ch) & 0xFF
        a = (a + T) & 0xFF
        traj.append(a)
    return traj


def evdd(base):
    for fn in glob.glob(base + ".cir.mt0") + glob.glob(base + ".mt0"):
        m = re.search(r'EVDD\s*=\s*([-+0-9.eE]+)', open(fn).read())
        if m:
            return float(m.group(1))
    return None


def analyze(base):
    meta = json.load(open(base + ".meta.json"))
    prn = base + ".cir.prn"
    Tc = meta['Tc_ns'] * 1e-9; d = meta['duty_cycles']; n = meta['nops']
    Ttot = meta['Ttot_ns'] * 1e-9; vth = 0.6 * 1.2 if False else 0.6
    out = {"mode": meta['mode'], "duty": d, "nops": n, "Ttot_ns": meta['Ttot_ns'],
           "E_fJ": (evdd(base) or 0) * 1e15, "traj": None, "final": None,
           "have_prn": os.path.exists(prn)}
    if not out["have_prn"]:
        return out, meta
    cols, rows = load(prn)
    ti = col(cols, 'TIME')
    if ti is None or not rows:
        return out, meta
    ts = [r[ti] for r in rows]
    S = [[r[col(cols, 'V(s%d)' % i)] for r in rows] for i in range(NB)]
    traj = []
    for k in range(n):
        # round k capture edge at 0.5n + (1+k*d)*Tc; sample ~1 ns later (settled,
        # next round is d*Tc >= 1.5 ns away)
        t = min(0.5e-9 + (1 + k * d) * Tc + 1.0e-9, Ttot - 0.05e-9)
        traj.append(state_at(t, ts, S, vth))
    out["traj"] = traj
    out["final"] = state_at(Ttot - 0.05e-9, ts, S, vth)
    return out, meta


def hx(lst):
    return "[" + " ".join("0x%02X" % v for v in lst) + "]" if lst is not None else "(pending)"


if __name__ == "__main__":
    duties = [1, 4, 10]
    bcefg = None
    res = {}
    print("=== SHA-256 ROUND-SLICE FSM — FUNCTIONAL (self-timed vs clocked vs reference) ===")
    allmatch = True
    anyhave = False
    for d in duties:
        gb = "g_sha_d%d" % d; sb = "st_sha_d%d" % d
        try:
            g, mg = analyze(gb); st, mst = analyze(sb)
        except FileNotFoundError as ex:
            print("  duty 1/%-2d  meta missing (%s) -> run gen_sha_slice_fsm.py first" % (d, ex))
            continue
        res[d] = (g, st)
        bcefg = mg['bcefg']
        ref = ref_traj(bcefg, mg['nops'])
        have = g["have_prn"] and st["have_prn"] and g["traj"] and st["traj"]
        if not have:
            which = []
            if not g["have_prn"]:
                which.append(gb + ".cir.prn")
            if not st["have_prn"]:
                which.append(sb + ".cir.prn")
            print("  duty 1/%-2d  PENDING (no %s) | reference traj=%s"
                  % (d, ", ".join(which) or "state yet", hx(ref)))
            continue
        anyhave = True
        gm = g["traj"] == ref and g["final"] == ref[-1]
        sm = st["traj"] == ref and st["final"] == ref[-1]
        match = gm and sm
        allmatch = allmatch and match
        print("  duty 1/%-2d  golden=%s%s | selftimed=%s%s | ref=%s  %s"
              % (d, hx(g["traj"]), "" if gm else "!", hx(st["traj"]), "" if sm else "!",
                 hx(ref), "MATCH" if match else "*** MISMATCH ***"))
    if anyhave:
        print("FUNCTIONAL:", "PASS" if allmatch else "*** FAIL ***",
              "(golden == self-timed == independent sha_slice.v reference)")
    else:
        print("FUNCTIONAL: PENDING (orchestrator has not produced .prn outputs yet)")

    print("\n=== ENERGY vs DUTY (EVDD over the window; same %d rounds each) ===" % 4)
    print("%-8s %12s %12s %10s %s" % ("duty", "golden fJ", "selftimed fJ", "ratio", "window"))
    any_e = False
    for d in duties:
        if d not in res:
            continue
        g, st = res[d]
        ge, se = g["E_fJ"], st["E_fJ"]
        if not ge and not se:
            print("1/%-6d %12s %12s %10s  %.4g ns" % (d, "(pending)", "(pending)", "-", g["Ttot_ns"]))
            continue
        any_e = True
        ratio = ge / se if se else float('nan')
        print("1/%-6d %12.1f %12.1f %9.2fx  %.4g ns" % (d, ge, se, ratio, g["Ttot_ns"]))
    print("\nThe clocked (golden) deck clocks every cycle incl. idle; the self-timed")
    print("deck captures only on rounds. Ratio>1 and GROWING with duty = the per-round")
    print("clock-floor win (the completion-detector floor must be charged in separately).")
    if not any_e:
        print("(ENERGY pending: orchestrator must run the decks in Xyce, one at a time.)")
