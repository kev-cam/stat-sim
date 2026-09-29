#!/usr/bin/env python3
"""(b) RE-RUN THE ALTERNATING CHAIN and recompute separation by depth.

Configuration as instructed -- the committed banktank arrangement, which is the
only one that has produced a computing unbuffered multi-bank chain: per-bank
matched tanks (m=10), L=15 nH, RS=10 ohm, tg15p transfer triple with the
tank-referenced park, VGH=1.5 V, 2 ps edges, schedule-matched true-ZCS
probe-then-cut, dV=1.2, T=200 ps, H=4, 8 cells/bank, NOTHING between banks.

The committed generator bt.py is IMPORTED (it is the campaign harness, not the
run under review).  Rebound here: HERE, CACHE/ENV (my own vae cache), and the
bank-composition hooks.  The TG cells are emitted by MY sk.py, and the
extraction is written here.

FOUR compositions, so the mechanism can be separated from the verdict:
  CTL   inv inv inv inv   the anchor.  Must reproduce the committed banktank
                          row (706.56 / 612.38 / 619.51 / 671.43 mV) or nothing
                          downstream is evidence.
  ALT   inv tg  inv tg    the arrangement under review.  tg = tg_mux2 with S=0,
                          off path A1 = the REAL neighbour cell (i+4)%8 -- the
                          adversarial wiring the run used.
  ALTB  inv tgb inv tgb   IDENTICAL except the off path is tied to the SAME net
                          as the on path.  A pure pass gate with no data
                          contention.  This is the control that decides WHICH
                          mechanism the collapse is: if ALTB holds and ALT does
                          not, the loss is the mux's off-path short during the
                          ramp, NOT pass-gate non-restoration.  If both collapse,
                          non-restoration is real and compounds.
  ALLTG tg tg tg tg       pass gate on pass gate, no restoring cell anywhere.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_pgcell_SKEPT")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/banktank")
import bt                                                     # noqa: E402
import sk                                                     # noqa: E402

bt.HERE = HERE
bt.CACHE = CACHE
bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

SIGMA_FLOOR_MV = 6.44         # qal/vtaudit corrected 1-sigma trip floor
M, DV, T, H = float(os.environ.get("PGM", 10.0)), 1.2, 200.0, 4
# PGM sweeps the tank multiplier (C_tank = M * CBANK).  The committed m = 10 was
# sized from CBANK = 35.979 fF, the MEASURED secant capacitance of an 8-cell
# INVERTER bank.  A pass-gate bank is a different load, and NEITHER run re-derived
# the tank for it -- both declared the mismatch and left it.  Bracketing m here is
# the cheapest test of whether the ALT failure is a tank-sizing artifact.
COMP = {"CTL":   ["inv", "inv", "inv", "inv"],
        "ALT":   ["inv", "tg", "inv", "tg"],
        "ALTB":  ["inv", "tgb", "inv", "tgb"],
        "ALTI":  ["inv", "tgi", "inv", "tgi"],
        "ALLTG": ["tg", "tg", "tg", "tg"]}
# tgi = the run's own NAMED-BUT-UNTESTED lever: a pass gate whose control is NOT
# derived from its own ramping rail.  nMOS gate on the global +1.5 V supply, pMOS
# gate on ground -- fully ON from t=0, rail-independent, and the off path tied to
# the ON path so there is no contention either.  BOOKING: those two controls are
# IDEAL sources, so this row is an UPPER BOUND on what any rail-independent
# control could deliver, not a design.  It is run as a DIAGNOSTIC: if a
# maximally-on, contention-free pass gate still collapses the separation, the
# loss is the pass structure itself and no control scheme fixes it.

# The run patched bt.deck to lengthen the RETURN probe window 3x, because a
# pass-gate bank's return half-cycle is longer than the inverter bank the
# committed window was sized from and zero_after_peak correctly reported NO ZERO.
# Reproduced here.  It touches ONLY the .tran end time of a return-probe deck;
# every committed constant and every rise window is untouched.  CTL is run WITH
# the patch in place, so if the patch perturbed anything the anchor would move.
PROBE_RET_MULT = 3.0
_BT_DECK = bt.deck


def _deck_longprobe(*a, **kw):
    L, S = _BT_DECK(*a, **kw)
    pr = kw.get("probe")
    if pr is not None and pr[0] == "ret":
        for j, ln in enumerate(L):
            if ln.startswith(".tran "):
                p = ln.split()
                tend = float(p[2].rstrip("p"))
                base = S["r"][pr[1]]
                L[j] = ".tran %s %gp 0 %s" % (p[1], base + PROBE_RET_MULT *
                                              (tend - base), p[4])
                break
    return L, S


bt.deck = _deck_longprobe


def levels(comp):
    lv = [list(bt.PAT)]
    for kind in comp:
        lv.append([(1 - b) if kind == "inv" else b for b in lv[-1]])
    return lv


def install(comp, well):
    lv = levels(comp)
    pbulk = "vhi" if well == "vhi" else None

    def in_hi(k, i):
        return lv[k - 1][i] == 1

    def out_hi(k, i):
        return lv[k][i] == 1

    def bank_cells(k, dv):
        L = ["VMG%d gn%d 0 0" % (k, k)]
        if k == 1:
            for i in range(bt.MGATE):
                L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if in_hi(1, i) else 0.0))
        kind = comp[k - 1]
        for i in range(bt.MGATE):
            a0 = bt.in_net(k, i)
            o = "o%d_%d" % (k, i)
            rail, gnd = "rail%d" % k, "gn%d" % k
            if kind == "inv":
                L += sk.inv("%d_%d" % (k, i), o, a0, rail, gnd,
                            wp=bt.WP, wn=bt.WN)
                L.append("CL%d_%d %s %s %gf" % (k, i, o, gnd, bt.CLOAD))
            elif kind == "tgi":
                # DIAGNOSTIC (booking: two ideal gate controls).  One full
                # transmission gate, no control inverter, nMOS gate on the global
                # +1.5 V and pMOS gate on the bank ground -- fully ON from t=0 and
                # entirely independent of this bank's own ramping rail.  Off path
                # tied to the on path, so there is no data contention either.
                # This is the best case any rail-independent control could give.
                t = "%d_%d" % (k, i)
                L += sk.tg(t, a0, o, "vhi", gnd, gnd, pbulk or rail)
                L.append("CL%s %s %s %gf" % (t, o, gnd, bt.CLOAD))
            else:
                if kind == "tgb":
                    a1 = a0                       # benign off path: no contention
                else:
                    a1 = ("in1_%d" % ((i + 4) % bt.MGATE) if k == 1
                          else "o%d_%d" % (k - 1, (i + 4) % bt.MGATE))
                t = "%d_%d" % (k, i)
                L.append("VSEL%s sel_%s 0 0" % (t, t))
                L += sk.tg_mux2(t, o, a0, a1, "sel_" + t, rail, gnd,
                                pbulk or rail, cl=bt.CLOAD)
                L.append("CSB%s sb_%s %s %gf" % (t, t, gnd, sk.CINT))
        return L

    bt.in_hi, bt.out_hi, bt.bank_cells = in_hi, out_hi, bank_cells
    return in_hi, out_hi


def extract(path, S, comp, well, in_hi, out_hi):
    mt = bt.parse_mt0(path + ".mt0")
    nb = bt.NBANK
    rail = {k: mt["VR%dB%d" % (k, k)] for k in range(1, nb + 1)}
    r = dict(comp=comp, well=well, m=M, dv=DV, T_ps=T, H=H,
             rail_at_own_boundary_V=rail,
             rail_peak_V={k: mt["VR%dPK" % k] for k in range(1, nb + 1)},
             IZ_uA={k: mt["IZ%d" % k] * 1e6 for k in range(1, nb + 1)},
             bound=S["bound"], tzr=S["tzr"], tzq=S["tzq"])
    banks, allok, valok = {}, True, True
    for k in range(1, nb + 1):
        rk = rail[k]
        his, los, per = [], [], {}
        for i in range(bt.MGATE):
            v = mt["O%d_%dB" % (k, i)]
            want = bool(out_hi(k, i))
            pct = 100.0 * ((v / rk) if want else (1.0 - v / rk)) if rk > 0 else None
            ok = bool(v > 0.5 * rk) if want else bool(v < 0.5 * rk)
            per["o%d" % i] = dict(v=v, want_hi=want, settle_pct=pct, correct=ok)
            (his if want else los).append(v)
            valok &= ok
            if pct is not None and pct < 90.0:
                allok = False
        sep = (min(his) - max(los)) * 1e3 if his and los else None
        banks[k] = dict(kind=comp[k - 1], rail_V=rk, per_gate=per,
                        min_HIGH_V=min(his) if his else None,
                        max_LOW_V=max(los) if los else None,
                        separation_mV=sep,
                        x_floor=(sep / SIGMA_FLOOR_MV) if sep is not None else None,
                        worst_settle_pct=min(x["settle_pct"] for x in per.values()),
                        all_correct=all(x["correct"] for x in per.values()))
    r["banks"] = banks
    r["VALUE_CHECK"] = bool(valok)
    r["ALL_GATES_90PCT"] = bool(allok)
    seps = [banks[k]["separation_mV"] for k in range(1, nb + 1)]
    r["separation_by_depth_mV"] = seps
    r["x_floor_by_depth"] = [s / SIGMA_FLOOR_MV for s in seps]
    r["first_bad_bank"] = next((k for k in range(1, nb + 1)
                                if not banks[k]["all_correct"]), None)
    r["C5_separation_holds"] = bool(all(s is not None and s >= SIGMA_FLOOR_MV
                                        for s in seps))
    r["monotone_fade"] = bool(all(seps[j] > seps[j + 1] for j in range(len(seps) - 1)))
    # ABOVE-OWN-RAIL check: a chain whose nodes sit above their own bank rails is
    # a passive wire carrying the ideal head sources, not a computing chain.
    r["nodes_above_own_rail"] = {k: bool(banks[k]["min_HIGH_V"] is not None
                                         and banks[k]["min_HIGH_V"] > rail[k])
                                 for k in range(1, nb + 1)}
    return r


def run_one(name, well):
    comp = COMP[name]
    in_hi, out_hi = install(comp, well)
    sub = os.path.join(HERE, "%s_%s%s" % (name, well, "" if M == 10.0 else "_m%g" % M))
    os.makedirs(sub, exist_ok=True)
    bt.HERE = sub
    t0 = time.monotonic()
    zf = os.path.join(sub, "zeros.json")
    if os.path.exists(zf):
        z = json.load(open(zf))
        print("[%s/%s] reusing zeros" % (name, well), flush=True)
    else:
        z = bt.do_probe(M, DV, T=T, H=H)
        if z is None:
            return dict(name=name, well=well, error="probe failed")
        json.dump(z, open(zf, "w"), indent=1)
    lines, S = bt.deck(M, T, H, DV, mode="free", tzr=z["tzr"], tzq=z["tzq"])
    fn = "F_%s_%s%s.cir" % (name, well, "" if M == 10.0 else "_m%g" % M)
    p, msg = bt.run(fn, lines, timeout=1800)
    print("  main %s" % msg, flush=True)
    if p is None:
        return dict(name=name, well=well, error="main deck failed")
    r = extract(p, S, comp, well, in_hi, out_hi)
    r["name"] = name
    r["wall_s"] = round(time.monotonic() - t0, 1)
    json.dump(r, open(os.path.join(HERE, "CH_%s_%s%s.json" % (name, well, "" if M == 10.0 else "_m%g" % M)), "w"),
              indent=1)
    print("[%s/%s] sep %s  (x floor %s)  VALUE=%s  90pct=%s"
          % (name, well,
             ["%.2f" % s for s in r["separation_by_depth_mV"]],
             ["%.1f" % x for x in r["x_floor_by_depth"]],
             r["VALUE_CHECK"], r["ALL_GATES_90PCT"]), flush=True)
    return r


if __name__ == "__main__":
    jobs = []
    for a in sys.argv[1:]:
        n, _, w = a.partition(":")
        jobs.append((n, w or "vhi"))
    if not jobs:
        jobs = [("CTL", "vhi"), ("ALT", "vhi"), ("ALTB", "vhi"), ("ALT", "rail")]
    out = {}
    for n, w in jobs:
        out["%s_%s" % (n, w)] = run_one(n, w)
    json.dump(out, open(os.path.join(HERE, "CHAIN_SKEPT.json"), "w"), indent=1)
