#!/usr/bin/env python3
"""DOES SINGLE-RAIL DATA WANDER FALL AS 1/sqrt(N)?  -- direct measurement, random patterns.

THE CLAIM UNDER TEST. qal_twobank.py:24-31 asserts dual-rail is REQUIRED for QAL's POWER
mechanism because a single-rail bank draws a DATA-DEPENDENT charge ("measured 100% modulation,
qal_a1f.py") so one FIXED flycap top-up would over/under-compensate. That 100% traces to
qal_a1f.py:69 and the decks sr_d1.cir / sr_d0.cir -- ONE ideal 10 fF flying cap, no transistors,
N=1. The hypothesis is that for a bank of N gates with RANDOM data the number switching is
BINOMIAL, so the RELATIVE modulation falls as 1/sqrt(N) and the law of large numbers does the
job dual-rail was there for.

WHAT THIS DECK DOES DIFFERENTLY FROM qal_bankN_modulation.py. That script swept k (how many of
8 gates switch) at FIXED N=8. This one sweeps N itself and drives the bank with ACTUAL RANDOM
INPUT PATTERNS, so the measured quantity is the thing the hypothesis is about: the SPREAD of the
receiving bank's rail across data words, as a function of N.

THE SCALING RULE, and why it makes the test exact. A bank of N = 8*M gates is built as M
PARALLEL COPIES of the N=8 unit: C_A * M, L / M, Rs / M, switch width * M. Those branches are
all tied to the same two nodes, so if every copy carried the same data the node voltages would
be IDENTICAL to the N=8 solution -- the circuit is scale-invariant in the ACTIVITY FRACTION
a = k/N by construction. The only thing that changes with N is the GRANULARITY of a: at N=8 the
data can only put a on {0, 1/8, ..., 1}; at N=128 on a 1/128 grid, and random data concentrates
it near 0.5. So V_rail(a) should be one N-independent curve, and

    sigma_rail(N) = |dV_rail/da| * sigma_a = |dV_rail/da| * sqrt(p(1-p)/N)   [p=0.5 -> 0.5/sqrt(N)]

is the prediction. Both halves are measured here: the curve's N-invariance (same a, different N)
and the spread across random draws.

HELD FIXED ON PURPOSE, because a real pipeline cannot re-tune per data word:
  * source charge: C_A and V_A(0)=dV identical for every pattern  (= recycle + one FIXED top-up,
    exactly the condition the dual-rail argument says single-rail cannot meet)
  * switch timing t_ZCS: fixed at the corrected-topology value for that swing, 396.68 ps
    (dV=0.8) / 400.41 ps (dV=1.0) from qal_hop_corrected.json. Under the parallel-copy scaling
    the current zero is at the same instant for every N at the same a, so one value serves all N.

TOPOLOGY is the CORRECTED one (qal_hop_gates.py:187-190, 2026-09-25): the disconnect switch is
on the RECEIVING side so opening it isolates bank B and B holds its charge. The earlier
sending-side arrangement left L tied to bkb and the bank rang at ~500 ps period.

Devices, loads and swings are unchanged from every other anchor (wp=1.12u, wn=0.74u, 2 fF per
gate output, Rs-per-copy 10 ohm, switch 20u/40u per copy, VGH=1.5 V) so results compose.

CONVENTION: pattern bit 1 = input LOW = that inverter's pMOS charges its 2 fF load to the rail
("switches"); bit 0 = input HIGH = nMOS holds the output at 0 (does not charge). So
all-inputs-LOW is k=N and all-inputs-HIGH is k=0 -- the two worst-case patterns.
"""
import os, re, sys, json, time, random, subprocess

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")
OUT   = "/usr/local/src/stat-sim/qal/qal_bankN_sqrtN.json"

WP, WN, CLOAD, VGH = 1.12, 0.74, 2.0, 1.5
WSW8, RS8, L8, N8 = 20.0, 10.0, 400.0, 8      # the N=8 unit cell

# Switch-gate TURN-ON edge. The anchor decks use 2 ps. At N=128 the switch is 320u/640u and a
# 2 ps corner dumps its whole gate charge in one step: Xyce aborted with "Time step too small
# near step number: 181" on 5 of 12 N=128 patterns -- intermittently, set by node ordering, not
# by data (k=62 and k=64 each both succeeded and failed). Two fixes were tried and rejected:
# splitting the switch into M parallel 20u/40u instances made it fail on 3 of 3, and
# MINTIMESTEPRECOVERY=20 did not help ("Time step too small near step number: 202"). Widening
# the turn-on edge to 10 ps converges at every N. It is applied UNIFORMLY at every N so the
# comparison across N stays controlled; the resulting offset against the 2 ps anchor decks is
# measured and reported (N=128 k=64: 0.58421 at 2 ps -> 0.58314 at 10 ps, 1.1 mV).
TON = 10.0

# dV -> (C_A of the N=8 working bank from its slow-ramp calibration, fixed t_ZCS ps)
UNIT = {0.8: (35.0025, 396.68), 1.0: (35.9790, 400.41)}

def deck_text(N, dv, pattern):
    M  = N / float(N8)
    ca = UNIT[dv][0] * M
    tz = UNIT[dv][1]
    l_nh, rs, wsw = L8 / M, RS8 / M, WSW8 * M
    t0 = 50.0
    tend  = t0 + tz + 500.0
    topen = t0 + tz + 2
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         '.param LT=%gn RS=%g CA=%gf' % (l_nh, rs, ca),
         'CA bka 0 {CA}',
         'VHI vhi 0 %g' % VGH,
         'VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)'
             % (t0-TON, t0, VGH, t0+tz, VGH, t0+tz+2),
         'VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)'
             % (VGH, t0-TON, VGH, t0, t0+tz, t0+tz+2, VGH),
         'XSWN sw gt  bkb 0   sg13_lv_nmos w=%gu l=0.13u' % wsw,
         'XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u' % (2*wsw),
         'LT bka mid {LT}', 'RT mid sw {RS}']
    for i, b in enumerate(pattern):
        L += ['VI%d in%d 0 %g' % (i, i, 0.0 if b else dv),
              'XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u' % (i, i, i, WP),
              'XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u' % (i, i, i, WN),
              'CL%d o%d 0 %gf' % (i, i, CLOAD)]
    L += ['Bqt qt 0 V={ I(LT) }',
          '.ic V(bka)=%g V(bkb)=0' % dv,
          '.tran 0.1p %gp' % tend,
          '.measure tran QTR   INTEGRAL V(qt) FROM=0 TO=%gp' % tend,
          '.measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp' % (t0, tend),
          '.measure tran VBEND FIND V(bkb) AT=%gp' % (tend-5),
          '.measure tran VAEND FIND V(bka) AT=%gp' % (tend-5),
          '.measure tran BKE   FIND V(bkb) AT=900p',
          '.measure tran VBMIN MIN V(bkb) FROM=%gp TO=%gp' % (topen, tend),
          '.measure tran VBMAX MAX V(bkb) FROM=%gp TO=%gp' % (topen, tend)]
    sw = [i for i, b in enumerate(pattern) if b]
    if sw:
        L.append('.measure tran OSW FIND V(o%d) AT=900p' % sw[0])     # a switching gate
        if len(sw) > 1:
            L.append('.measure tran OSW2 FIND V(o%d) AT=900p' % sw[-1])
    L.append('.end')
    return "\n".join(L) + "\n", dict(C_A_fF=ca, t_zcs_ps=tz, L_nH=l_nh, Rs_ohm=rs, Wsw_um=wsw)

KEYS = ("QTR", "VBPK", "VBEND", "VAEND", "BKE", "VBMIN", "VBMAX", "OSW", "OSW2")

def xyce_busy():
    return int(subprocess.run("pgrep Xyce | wc -l", shell=True, capture_output=True,
                              text=True).stdout.strip() or 0) > 0

def run_one(tag, N, dv, pattern, timeout=600, wait_s=2400):
    # STRICTLY ONE XYCE AT A TIME: the main session runs Xyce against the same PyMS vae cache and
    # concurrent runs corrupt it. Wait for the lock rather than refusing, so a long sweep survives
    # the main session taking the machine mid-way.
    waited = 0
    while xyce_busy() and waited < wait_s:
        time.sleep(15); waited += 15
        if waited % 120 == 0:
            print("      (waiting %ds for another Xyce to finish)" % waited, flush=True)
    if xyce_busy():
        return None, "ANOTHER XYCE STILL RUNNING after %ds -- refusing" % wait_s, None, 0.0
    txt, meta = deck_text(N, dv, pattern)
    fn = "/usr/local/src/stat-sim/qal/sq_%s.cir" % tag
    open(fn, "w").write(txt)
    t0 = time.time()
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, env=ENV).stdout
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout, meta, time.time()-t0
    wall = time.time() - t0
    g = {}
    for k in KEYS:
        m = re.search(r"^%s\s*=\s*(\S+)" % k, o, re.M)
        if m:
            try: g[k] = float(m.group(1))
            except ValueError: pass
    if "VBEND" not in g:
        err = "; ".join(l.strip() for l in o.splitlines()
                        if "rror" in l or "bort" in l or "ailure" in l)[:250]
        return None, (err or "no measures"), meta, wall
    return g, None, meta, wall

def load():
    if os.path.exists(OUT):
        try: return json.load(open(OUT))
        except Exception: pass
    return {"_doc": __doc__.strip().split("\n\n")[0], "runs": []}

def save(db):
    db["_doc"] = ("Spread of a SINGLE-RAIL QAL bank's rail across RANDOM data patterns vs bank "
                  "size N. Bank of N=8*M gates = M parallel copies of the N=8 anchor unit "
                  "(C_A*M, L/M, Rs/M, switch width*M), so the circuit is scale-invariant in the "
                  "activity fraction a=k/N and only the granularity of a changes with N. Source "
                  "charge and t_ZCS HELD FIXED across patterns = recycle + one fixed flycap "
                  "top-up. Corrected receiving-side-switch topology. pattern bit 1 = input LOW = "
                  "output charges. Tests whether sigma_rail falls as 1/sqrt(N) and whether the "
                  "wander stays above the functional cliff.")
    json.dump(db, open(OUT, "w"), indent=1)

def main():
    # argv: N dV mode [count]
    N   = int(sys.argv[1])
    dv  = float(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else "rand"
    cnt  = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    seed = int(sys.argv[5]) if len(sys.argv) > 5 else 12345

    pats = []
    if mode in ("ext", "all"):
        pats.append(("allhi_k0",  [0]*N))          # all inputs HIGH  -> nothing switches
        pats.append(("alllo_kN",  [1]*N))          # all inputs LOW   -> everything switches
    if mode in ("rand", "all"):
        rng = random.Random(seed + N*1000 + int(dv*1000))
        for r in range(cnt):
            pats.append(("r%d" % r, [rng.randint(0, 1) for _ in range(N)]))
    if mode == "kgrid":   # explicit activity fractions, to fill in the V(a) curve for the
                          # exact binomial composition (the extremes a=0,1 come from mode "ext")
        for k in sorted(set(int(round(x*N)) for x in
                            (0.125, 0.25, 0.375, 0.4375, 0.5, 0.5625, 0.625, 0.75, 0.875))):
            pats.append(("k%d" % k, [1]*k + [0]*(N-k)))
    if mode == "sgrid":   # k at mean +- n*sigma of Binomial(N,0.5), so the measured V(k) curve
                          # covers the whole binomial bulk out to +-4 sigma and the spread can be
                          # COMPOSED EXACTLY instead of only sampled by a dozen draws
        import math as _m
        sig = 0.5*_m.sqrt(N)
        ks = set()
        for s in (0.5,1,1.5,2,2.5,3,3.5,4):
            for sgn in (-1,1):
                k = int(round(N/2.0 + sgn*s*sig))
                if 0 <= k <= N: ks.add(k)
        for k in sorted(ks):
            pats.append(("k%d" % k, [1]*k + [0]*(N-k)))

    if mode == "perm":                             # same k, different placement: is V a function of k alone?
        rng = random.Random(999)
        base = [1]*(N//2) + [0]*(N - N//2)
        for r in range(cnt):
            p = base[:]; rng.shuffle(p)
            pats.append(("perm%d" % r, p))

    db = load()
    print("N=%d  dV=%.1f  mode=%s  (%d patterns)" % (N, dv, mode, len(pats)))
    _, meta = deck_text(N, dv, [0]*N)
    print("  C_A=%.3f fF  L=%g nH  Rs=%g ohm  Wsw=%g u  t_ZCS=%.2f ps (FIXED)"
          % (meta["C_A_fF"], meta["L_nH"], meta["Rs_ohm"], meta["Wsw_um"], meta["t_zcs_ps"]))
    print("   pattern      k   a=k/N | QTR(fC)  QTR/gate  V_B_end  rail@900p  O_sw@900p settle%  wall")
    for name, p in pats:
        k = sum(p)
        tag = "n%d_dv%d_%s" % (N, int(dv*1000), name)
        # Cache by (N, dV, k), NOT by tag: the rail was MEASURED to be a function of k alone --
        # three different placements of k=4 at N=8 gave 0.58291 to 5 decimals, and k=62 at N=128
        # reproduced 0.5845 from two unrelated random words. So re-running a k already measured
        # at this (N,dV) buys nothing. (Those placement checks are kept in the DB as the evidence.)
        done = [r for r in db["runs"]
                if r["N"] == N and abs(r["dV"] - dv) < 1e-9 and r["k"] == k]
        if done:
            r = done[0]
            print("   %-10s %4d  %.4f | %8.3f %8.4f  %7.4f   %7.4f   %s %s  (cached)"
                  % (name, k, k/float(N), r["QTR_fC"], r["QTR_per_gate_fC"], r["V_B_end"],
                     r["rail_900ps"],
                     ("%8.4f" % r["O_sw_900ps"]) if r["O_sw_900ps"] is not None else "     n/a",
                     ("%6.1f" % r["settle_pct"]) if r["settle_pct"] is not None else "   n/a"))
            continue
        g, err, meta, wall = run_one(tag, N, dv, p)
        if g is None:
            print("   %-10s %4d  %.4f | FAILED after %.0fs: %s" % (name, k, k/float(N), wall, err))
            continue
        q    = g["QTR"]*1e15
        rail = g.get("BKE", 0.0)
        osw  = g.get("OSW")
        st   = (100.0*osw/rail) if (osw is not None and rail) else None
        print("   %-10s %4d  %.4f | %8.3f %8.4f  %7.4f   %7.4f   %s %s  %4.0fs"
              % (name, k, k/float(N), q, q/N, g["VBEND"], rail,
                 ("%8.4f" % osw) if osw is not None else "     n/a",
                 ("%6.1f" % st) if st is not None else "   n/a", wall))
        db["runs"].append({
            "tag": tag, "N": N, "dV": dv, "pattern_name": name, "k": k, "a": round(k/float(N), 6),
            "QTR_fC": round(q, 4), "QTR_per_gate_fC": round(q/N, 5),
            "V_B_end": round(g["VBEND"], 5), "V_B_peak": round(g.get("VBPK", 0.0), 5),
            "rail_900ps": round(rail, 5), "V_A_end": round(g.get("VAEND", 0.0), 5),
            "O_sw_900ps": round(osw, 5) if osw is not None else None,
            "O_sw_last_900ps": round(g["OSW2"], 5) if "OSW2" in g else None,
            "settle_pct": round(st, 2) if st is not None else None,
            "V_B_min_postopen": round(g.get("VBMIN", 0.0), 5),
            "V_B_max_postopen": round(g.get("VBMAX", 0.0), 5),
            "C_A_fF": round(meta["C_A_fF"], 4), "L_nH": meta["L_nH"], "Rs_ohm": meta["Rs_ohm"],
            "Wsw_um": meta["Wsw_um"], "t_zcs_ps": meta["t_zcs_ps"], "wall_s": round(wall, 1),
            "pattern_bits": "".join(str(b) for b in p) if N <= 128 else None})
        save(db)
    save(db)
    print("  wrote %s (%d runs total)" % (OUT, len(db["runs"])))

if __name__ == "__main__":
    main()
