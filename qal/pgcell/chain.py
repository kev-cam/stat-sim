#!/usr/bin/env python3
"""(d)(c) THE DECIDING QUESTION -- do pass-gate cells COMPOUND with the bank's own
non-restoration, or does alternating them with inverter-class cells restore in
between?  Measured in the TANK-FED configuration, which is the only arrangement
that has produced a computing unbuffered multi-bank chain.

The committed banktank generator `bt.py` is IMPORTED, not copied.  Exactly three
module attributes are rebound -- HERE (output directory), ENV (own PYMS_VAE_CACHE)
and the bank composition hooks bank_cells / in_hi / out_hi.  Everything else --
per-bank matched tanks (m = 10, C_tank = 359.79 fF), L = 15 nH, RS = 10 ohm, the
tg15p transfer triple with the TANK-REFERENCED park (amendment A6), VGH = 1.5 V,
2 ps edges, the schedule-matched true-ZCS probe-then-cut (A7), dV = 1.2, the beat
T = 200 ps (the MEASURED earliest correct beat) and H = 4 -- is the committed
configuration VERBATIM.

Three compositions, all 4 banks deep, 8 cells per bank, NOTHING between banks:
  CTL    inv  inv  inv  inv   the control; must reproduce the committed banktank
                              separations in shape (706/612/620/671 mV)
  ALT    inv  tg   inv  tg    the pre-registered alternating arrangement
  ALLTG  tg   tg   tg   tg    the compound test: pass gate on pass gate with no
                              restoring cell anywhere in the chain

The tg bank is tg_mux2 with S = 0, i.e. X = A0 -- the PURE pass-gate case, whose
data path never touches the rail.  Its off path A1 is wired to a REAL predecessor
output (cell i+4 mod 8), not to a convenient ground.

DECLARED: C_tank is sized from CBANK = 35.979 fF, the MEASURED secant capacitance
of an 8-cell INVERTER bank.  A tg bank is a different load, so the rail it is
DELIVERED differs; the delivered rail is measured per bank and reported, never
assumed equal.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_pgcell")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/banktank")
import bt                                                        # noqa: E402
import pg                                                        # noqa: E402

bt.HERE = HERE
bt.CACHE = CACHE
bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

SIGMA_FLOOR_MV = 6.44          # qal/vtaudit/AUDIT.md corrected 1-sigma trip floor
VTN, VTP = 0.5239, 0.4403      # MEASURED, qal/chain3/vt.json
TGW = pg.TGW["tgM"]
WELL = os.environ.get("PGWELL", "vhi")   # "vhi" (fixed n-well on the +1.5 V
                                          # supply the arch already carries) or
                                          # "rail" (the naive port)
COMP = {"CTL":   ["inv", "inv", "inv", "inv"],
        "ALT":   ["inv", "tg",  "inv", "tg"],
        "ALLTG": ["tg",  "tg",  "tg",  "tg"]}
M, DV, T, H = 10.0, 1.2, 200.0, 4


# --------------------------------------------------------------------------
# MEASURED HARNESS DEFECT + FIX (this run).  bt.deck sizes a PROBE window as
# S[phase][k] + 2.6 * TZ_ANCH * sqrt(L/L_REF), i.e. from the committed INVERTER
# bank's single-hop zero.  A pass-gate bank's RETURN half-cycle is much longer:
# its 2 fF cell loads hang on the TG OUTPUT nodes, which are NOT rail-referenced,
# so that charge was never taken from this rail and is not given back to it.
# MEASURED on ALLTG ret1: peak return current is only -40.87 uA (against +874 uA
# on the rise), it peaks at 1111.5 ps and is still -7.27 uA at the 1170.3 ps
# window end -- so `zero_after_peak` correctly reported NO ZERO.  That is a
# WINDOW artifact, not a physical failure, and it is fixed by lengthening the
# probe window only.  Nothing about the measured circuit changes.
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


PROBE_RET_MULT = 3.0
bt.deck = _deck_longprobe


def levels(comp):
    """the EXPECTED bit at each depth: inv complements, tg (S=0 mux) is identity"""
    lv = [list(bt.PAT)]
    for kind in comp:
        lv.append([(1 - b) if kind == "inv" else b for b in lv[-1]])
    return lv


def install(comp):
    lv = levels(comp)

    def in_hi(k, i):   return lv[k - 1][i] == 1
    def out_hi(k, i):  return lv[k][i] == 1

    def bank_cells(k, dv):
        L = ["VMG%d gn%d 0 0" % (k, k)]
        if k == 1:
            for i in range(bt.MGATE):
                L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if in_hi(1, i) else 0.0))
        kind = comp[k - 1]
        for i in range(bt.MGATE):
            a0 = bt.in_net(k, i)
            o = "o%d_%d" % (k, i)
            if kind == "inv":
                L.append("XP%d_%d %s %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                         % (k, i, o, a0, k, k, bt.WP))
                L.append("XN%d_%d %s %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                         % (k, i, o, a0, k, k, bt.WN))
                L.append("CL%d_%d %s gn%d %gf" % (k, i, o, k, bt.CLOAD))
            else:
                a1 = ("in1_%d" % ((i + 4) % bt.MGATE) if k == 1
                      else "o%d_%d" % (k - 1, (i + 4) % bt.MGATE))
                t = "%d_%d" % (k, i)
                L.append("VSEL%s sel_%s 0 0" % (t, t))
                L += pg.tg_mux2(t, o, a0, a1, "sel_" + t,
                                "rail%d" % k, "gn%d" % k, TGW, cl=bt.CLOAD,
                                pbulk=("vhi" if WELL == "vhi" else None))
                L.append("CSB%s sb_%s gn%d %gf" % (t, t, k, pg.CINT))
        return L

    bt.in_hi, bt.out_hi, bt.bank_cells = in_hi, out_hi, bank_cells
    return in_hi, out_hi


def extract(path, S, comp, in_hi, out_hi):
    mt = bt.parse_mt0(path + ".mt0")
    nb = bt.NBANK
    rail = {k: mt["VR%dB%d" % (k, k)] for k in range(1, nb + 1)}
    r = dict(comp=comp, m=M, dv=DV, T_ps=T, H=H,
             rail_at_own_boundary_V=rail,
             rail_peak_V={k: mt["VR%dPK" % k] for k in range(1, nb + 1)},
             tank_t0_V={k: mt["VT%dZ" % k] for k in range(1, nb + 1)},
             tank_end_V={k: mt["VT%dD" % k] for k in range(1, nb + 1)},
             IZ_uA={k: mt["IZ%d" % k] * 1e6 for k in range(1, nb + 1)},
             IZQ_uA={k: mt["IZQ%d" % k] * 1e6 for k in range(1, nb + 1)},
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
    r["C5_separation_holds"] = bool(all(s is not None and s >= SIGMA_FLOOR_MV
                                        for s in seps))
    r["monotone_fade"] = bool(all(seps[j] > seps[j + 1] for j in range(len(seps) - 1)))
    r["rail_depth_spread_mV"] = 1e3 * (max(rail.values()) - min(rail.values()))
    return r


def run_one(name):
    comp = COMP[name]
    in_hi, out_hi = install(comp)
    t0 = time.monotonic()
    # bt.do_probe names its probe decks from (m, dv, T, H) ONLY, so every
    # composition would collide on the same filenames.  Each config gets its own
    # subdirectory; bt.HERE is the only thing that moves.
    sub = os.path.join(HERE, "%s_%s" % (name, WELL))
    os.makedirs(sub, exist_ok=True)
    bt.HERE = sub
    zf = os.path.join(sub, "zeros.json")
    if os.path.exists(zf):
        z = json.load(open(zf))
        print("[%s] reusing zeros" % name)
    else:
        z = bt.do_probe(M, DV, T=T, H=H)
        if z is None:
            return dict(name=name, error="probe failed")
        json.dump(z, open(zf, "w"), indent=1)
    lines, S = bt.deck(M, T, H, DV, mode="free", tzr=z["tzr"], tzq=z["tzq"])
    fn = "F_%s_%s.cir" % (name, WELL)
    p, msg = bt.run(fn, lines, timeout=1800)
    print("[%s] row %s" % (name, msg), flush=True)
    if p is None:
        return dict(name=name, error=msg)
    r = extract(p, S, comp, in_hi, out_hi)
    r["name"] = name
    r["well"] = WELL
    r["wall_s"] = round(time.monotonic() - t0, 1)
    json.dump(r, open(os.path.join(HERE, "CHAIN_%s_%s.json" % (name, WELL)), "w"), indent=1)
    print("[%s] rails %s" % (name, {k: round(v, 4)
                                    for k, v in r["rail_at_own_boundary_V"].items()}))
    print("[%s] separation_mV %s  VALUE %s  90%% %s"
          % (name, [None if s is None else round(s, 2) for s in
                    r["separation_by_depth_mV"]],
             r["VALUE_CHECK"], r["ALL_GATES_90PCT"]))
    return r


if __name__ == "__main__":
    print(json.dumps(run_one(sys.argv[1]), indent=1)[:2500])
