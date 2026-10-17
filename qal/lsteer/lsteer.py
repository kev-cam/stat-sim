#!/usr/bin/env python3
"""qal/lsteer -- STEERED-INDUCTOR DRIVE for the mesh3 three-phase trapezoid wave.

Everything scored here was fixed in PRE_REGISTERED.json BEFORE this file existed.

The chain is mesh3.deck('trap', 92, 3, pat) VERBATIM; ONLY the VPHk/RSk source
lines are replaced by:  phase nodes pA/pB/pC, a 0 V ammeter VPHk per bank (same
sign convention), ONE inductor per 3-phase group steered F -> L -> R by 6 steering
switches, 3 hold clamps to a 1.65 V DC rail, 3 zero-clamp pulses, terminal caps.
Extra print columns / measures are APPENDED so mesh3.extract() is unchanged.

  lsteer.py one --regime ccm|dcm --ncopy 1|4 --L <nH> --RL <ohm> --I0 <mA>
                --sw ideal|nmos|tg --Ct <fF> --pat P0|P1 [--tag T] [--keep]
  lsteer.py agg
"""
import argparse, importlib.util, json, math, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "mesh3", "/usr/local/src/stat-sim/qal/mesh3/mesh3.py")
M3 = importlib.util.module_from_spec(spec)
sys.modules["mesh3"] = M3
spec.loader.exec_module(M3)

SCRATCH = M3.SCRATCH
CACHE = os.path.join(SCRATCH, "vae_cache_lsteer")
RUNS_SCRATCH = os.path.join(SCRATCH, "lsteer_runs")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
os.makedirs(CACHE, exist_ok=True)
M3.ENV = ENV          # run_xyce() lives in mesh3; point it at lsteer's OWN VAE cache
XYCE = M3.XYCE
TT, D, NB, MG, DV = 92.0, 3, 6, M3.MG, M3.DV
T = 3 * TT
TEND = 7.0 * T
LAG = M3.LAG_PS
VGH = 2.174           # V, the campaign's binding transfer-gate spec (dV + Vtn)
QG_FIT = 3.7          # fC/um MEASURED gate charge (3.64..3.74); 0.155 is WRONG
E_LEDGER = 240.292    # fJ/bank/cycle mesh3 ideal-rail ledger (bank 4)
E_HARM = 534.0        # fJ/bank/cycle meshdrv harmonic flat-top driver
PH = "ABC"


# ----------------------------------------------------------------- windows
T1 = 0.0   # buck split fraction of the fall third (0 = plain F->L->R); set by build()


def windows(kind, p, zero_ps, t_hand=0.0):
    """on-windows [ta, tb) in ps for phase p (0=A,1=B,2=C), m = -1..7.
    Windows starting before t_hand (the soft-start handover) are dropped.
    T1 > 0 (steered buck): the falling bank feeds L only over the first T1 of
    its fall third, then the 1.65 V rail feeds L ('indd') and the exhausted
    bank is zero-clamped for the rest of the third (disconnected from L)."""
    out = []
    for m in range(-1, 8):
        b = m * T + p * TT
        if kind == "out":
            w = (b, b + TT)
        elif kind == "hold":
            w = (b + TT, b + 2 * TT)
        elif kind == "in":
            w = (b + 2 * TT, b + 2 * TT + (T1 * TT if T1 > 0 else TT))
        elif kind == "indd":
            if T1 <= 0:
                return []
            w = (b + 2 * TT + T1 * TT, b + 3 * TT)
        else:                                  # zero clamp
            if zero_ps <= 0 and T1 <= 0:
                return []
            if T1 > 0:
                w = (b + 2 * TT + T1 * TT, b + 3 * TT)
            else:                              # pulse: last zero_ps of the fall
                w = (b + 3 * TT - zero_ps, b + 3 * TT)
        if w[1] <= 0 or w[0] >= TEND + T or w[0] < t_hand - 1e-9:
            continue
        out.append((max(w[0], 0.0), w[1]))
    return out


def pwl_of(wins, von, voff, e0, e1):
    """control PWL: closing ramps over [ta+e0, ta+e1], opening over [tb-e1, tb-e0]."""
    pts = []
    if wins and wins[0][0] <= 0.0:
        pts.append((0.0, von))
    else:
        pts.append((0.0, voff))
    for (ta, tb) in wins:
        if ta > 0.0:
            pts += [(ta + e0, voff), (ta + e1, von)]
        pts += [(tb - e1, von), (tb - e0, voff)]
    pts = [(t, v) for (t, v) in pts if t >= 0.0]
    pts.sort()
    return "PWL(" + " ".join(("%gp %g" % (t, v)) if t > 0 else ("0 %g" % v)
                             for t, v in pts) + ")"


def check_bbm(zero_ps, e0, t_hand=0.0):
    """assert break-before-make per phase node: out/hold/in windows pairwise
    separated by >= 2*e0 (the dead time); zero pulse inside the in-window."""
    worst = 1e9
    for p in range(3):
        W = {k: windows(k, p, zero_ps, t_hand) for k in ("out", "hold", "in", "zero")}
        segs = [(a, b, k) for k in ("out", "hold", "in") for (a, b) in W[k]]
        segs.sort()
        for i in range(len(segs) - 1):
            gap = segs[i + 1][0] - segs[i][1]
            worst = min(worst, gap)
        if T1 > 0:
            segs = [(a, b, k) for k in ("out", "hold", "in", "zero") for (a, b) in W[k]]
            segs.sort()
            for i in range(len(segs) - 1):
                worst = min(worst, segs[i + 1][0] - segs[i][1])
        else:
            for (a, b) in W["zero"]:
                assert any(ia <= a and b <= ib for (ia, ib) in W["in"]), "zero pulse outside fall"
    # windows touch (gap 0) but the control ramps leave 2*e0 of dead time
    return dict(window_gap_ps=round(worst, 3), control_dead_time_ps=round(2 * e0, 3),
                ok=bool(worst >= -1e-9))


# -------------------------------------------------------------------- deck
def integ(tg, expr):
    return M3.integ(tg, expr)


def build(args):
    lines, S = M3.deck("trap", TT, D, args.pat)
    L = [l for l in lines if not re.match(r"(VPH\d|RS\d)", l)]
    end_idx = L.index(".end")
    L = L[:end_idx]
    ideal = (args.sw == "ideal")
    e0, e1 = (0.2, 0.5) if ideal else (0.5, 2.5)
    zero_ps = (4.0 if ideal else 8.0) if args.zero_ps is None else args.zero_ps
    global T1
    T1 = args.t1
    t_hand = T if args.softstart else 0.0
    net = ["* ---- qal/lsteer steered-inductor network (replaces VPHk/RSk) ----",
           "VDDH vddh 0 %g" % DV, "VZR vzr 0 0"]
    i_seed = args.I0
    if args.softstart and args.I0 > 0:
        # the freewheeling current decays by exp(-R T / L) before the handover;
        # compensate so I(L) at t = T equals the requested I0 (DERIVED)
        i_seed = args.I0 * math.exp(args.RL * T * 1e-12 / (args.L * 1e-9))
    ncopy = args.ncopy
    nbank = NB * ncopy
    # ammeters, same sign convention as the committed 'VPHk phsk 0'
    for k in range(1, nbank + 1):
        net.append("VPH%d ph%d p%s 0" % (k, k, PH[(k - 1) % 3]))
    # inductor + terminal caps
    net += ["Ctin lin 0 %gf" % args.Ct, "Ctout lout 0 %gf" % args.Ct,
            "VML lin lmid 0", "RL1 lmid lx %g" % args.RL,
            "L1 lx lout %gn IC=%.6gm" % (args.L, i_seed)]
    sw_names = []
    net.append(".model SWI VSWITCH RON=0.05 ROFF=1e8 VON=0.7 VOFF=0.3")
    if args.softstart:
        # SOFT START (warm-up wave 0 only, never scored): ideal trapezoid rails on
        # pA/pB/pC through ideal switches over [0, T); the inductor freewheels
        # through Sfw (lin-lout) carrying its seed; everything hands over at t = T
        # with the same break-before-make rule (opening T-0.5..T-0.2, closing T+0.2..+0.5).
        w0 = [(0.0, T)]
        net.append("Vcss css 0 %s" % pwl_of(w0, 1.0, 0.0, 0.2, 0.5))
        net.append("Sfw lin lout css 0 SWI")
        for p, X in enumerate(PH):
            pts = M3.trap_pts(p, TT, T, T + TT)
            sp = " ".join("%gp %g" % (t, v) if t > 1e-12 else "0 %g" % v for t, v in pts)
            net.append("VTR%s tr%s 0 PWL(%s)" % (X, X, sp))
            net.append("Str%s tr%s p%s css 0 SWI" % (X, X, X))
    for p, X in enumerate(PH):
        pn = "p" + X
        for kind in ("in", "out", "hold", "zero", "indd"):
            if kind == "indd" and p > 0:
                continue
            wins = windows(kind, p, zero_ps, t_hand)
            if kind == "indd":          # the 1.65 V in-feed serves EVERY fall third (all phases)
                wins = sorted(w for pp in range(3) for w in windows(kind, pp, zero_ps, t_hand))
            if not wins:
                continue
            nm = kind + X if kind != "indd" else "indd"
            other = {"in": "lin", "out": "lout", "hold": "vddh", "zero": "vzr", "indd": "lin"}[kind]
            if kind == "indd":
                pn = "vddh"
            if ideal:
                net.append("Vc%s c%s 0 %s" % (nm, nm, pwl_of(wins, 1.0, 0.0, e0, e1)))
                net.append("VS%s %s s%s 0" % (nm, pn, nm))
                net.append("S%s s%s %s c%s 0 SWI" % (nm, nm, other, nm))
                sw_names.append((nm, "VS" + nm, pn, other, None))
            else:
                net.append("VS%s %s s%s 0" % (nm, pn, nm))
                if kind in ("in", "out", "indd"):
                    # nMOS steering at VGH (binding spec); TG adds a pMOS, gate 0 = on
                    net.append("VPG%s g%s_s 0 %s" % (nm, nm, pwl_of(wins, VGH, 0.0, e0, e1)))
                    net.append("VG%s g%s_s g%s 0" % (nm, nm, nm))
                    net.append("XS%s s%s g%s %s 0 sg13_lv_nmos w=%gu l=0.13u"
                               % (nm, nm, nm, other, args.Wst))
                    sw_names.append((nm, "VS" + nm, pn, other, ("VG" + nm, VGH, args.Wst)))
                    if args.sw == "tg":
                        net.append("VPGP%s gp%s_s 0 %s" % (nm, nm, pwl_of(wins, 0.0, DV, e0, e1)))
                        net.append("VGP%s gp%s_s gp%s 0" % (nm, nm, nm))
                        net.append("XSP%s s%s gp%s %s vddh sg13_lv_pmos w=%gu l=0.13u"
                                   % (nm, nm, nm, other, args.Wst))
                        sw_names.append(("p" + nm, None, pn, other, ("VGP" + nm, DV, args.Wst)))
                elif kind == "hold":
                    net.append("VPG%s g%s_s 0 %s" % (nm, nm, pwl_of(wins, 0.0, DV, e0, e1)))
                    net.append("VG%s g%s_s g%s 0" % (nm, nm, nm))
                    net.append("XS%s s%s g%s vddh vddh sg13_lv_pmos w=%gu l=0.13u"
                               % (nm, nm, nm, args.Wh))
                    sw_names.append((nm, "VS" + nm, pn, other, ("VG" + nm, DV, args.Wh)))
                else:
                    net.append("VPG%s g%s_s 0 %s" % (nm, nm, pwl_of(wins, DV, 0.0, e0, e1)))
                    net.append("VG%s g%s_s g%s 0" % (nm, nm, nm))
                    net.append("XS%s s%s g%s vzr 0 sg13_lv_nmos w=%gu l=0.13u"
                               % (nm, nm, nm, args.Wz))
                    sw_names.append((nm, "VS" + nm, pn, other, ("VG" + nm, DV, args.Wz)))
    # ---- chain copies (N-sharing): banks 7.., same phases, own input words
    pat = M3.PATS[args.pat]
    for c in range(1, ncopy):
        for i in range(MG):
            pts, cur = [(0.0, DV * pat[i])], DV * pat[i]
            for n in range(1, 8):
                nxt = DV * (pat[i] ^ (n & 1))
                if nxt != cur:
                    pts += [(n * T - M3.EDGE / 2, cur), (n * T + M3.EDGE / 2, nxt)]
                    cur = nxt
            s = " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v for t, v in pts)
            net.append("VI%d_%d in%d_%d 0 PWL(%s)" % (c + 1, i, c + 1, i, s))
        for kb in range(1, NB + 1):
            k = kb + NB * c
            net.append("VMG%d gn%d 0 0" % (k, k))
            for j in range(1, D + 1):
                for i in range(MG):
                    if j == 1:
                        src = "in%d_%d" % (c + 1, i) if kb == 1 else "o%d_%d_%d" % (k - 1, D, i)
                    else:
                        src = "o%d_%d_%d" % (k, j - 1, i)
                    o = "o%d_%d_%d" % (k, j, i)
                    net.append("XP%d_%d_%d %s %s ph%d ph%d sg13_lv_pmos w=%gu l=0.13u"
                               % (k, j, i, o, src, k, k, M3.WP))
                    net.append("XN%d_%d_%d %s %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                               % (k, j, i, o, src, k, k, M3.WN))
                    net.append("CL%d_%d_%d %s gn%d %gf" % (k, j, i, o, k, M3.CLOAD))
    # ---- metering: 1F t0-referenced integrators
    net += integ("qdd", "-I(VDDH)")
    net += integ("qzr", "-I(VZR)")
    net += integ("erl", "I(VML)*I(VML)*%g" % args.RL)
    # switch conduction loss: sum over metered switches of (V(pX)-V(other))*I(VS)
    terms = ["(V(%s)-V(%s))*I(%s)" % (pn, other, am)
             for (nm, am, pn, other, g) in sw_names if am]
    net += integ("esw", "+".join(terms))
    gterms = []
    for (nm, am, pn, other, g) in sw_names:
        if g:
            gam, vg, w = g
            net += integ("qg_" + nm, "I(%s)" % gam)
            gsrc = ("g%s_s" % nm) if not nm.startswith("p") else ("gp%s_s" % nm[1:])
            gterms.append("V(%s)*I(%s)" % (gsrc, gam))
    if gterms:
        net += integ("egn", "+".join(gterms))
    # ---- extra measures (appended): boundary reads at n*T
    ms = []
    lag = lambda t: t + LAG
    for n in (2, 3, 4, 5):
        tb = n * T
        ms.append(".measure tran IL_T%d FIND I(L1) AT=%.6fp" % (n, lag(tb)))
        for tg in ("qdd", "qzr", "erl", "esw") + (("egn",) if gterms else ()):
            ms.append(".measure tran %s_T%d FIND V(x%s) AT=%.6fp" % (tg.upper(), n, tg, lag(tb)))
    # gate up-edge charge per switch, one edge each in wave 3 (period [3T,4T))
    gate_edges = {}
    for (nm, am, pn, other, gt) in sw_names:
        if not gt:
            continue
        kind = re.match(r"p?(indd|in|out|hold|zero)", nm).group(1)
        X = nm[-1] if kind != "indd" else "A"
        p = PH.index(X)
        wins = [w for w in windows(kind, p, zero_ps, t_hand) if 3 * T - 1 <= w[0] < 4 * T]
        ta = wins[0][0]
        ms.append(".measure tran QGA_%s FIND V(xqg_%s) AT=%.6fp" % (nm, nm, lag(ta - 0.5)))
        ms.append(".measure tran QGB_%s FIND V(xqg_%s) AT=%.6fp" % (nm, nm, lag(ta + e1 + 3.0)))
        gate_edges[nm] = dict(t_on_ps=ta, vg=gt[1], W_um=gt[2])
    # copies' crest FINDs (value check for banks 7..)
    co = 1.5 * TT
    for c in range(1, ncopy):
        for kb in range(1, NB + 1):
            k = kb + NB * c
            for n in (2, 3, 4):
                tc = M3.slot(kb, n, T, TT) + co
                ms.append(".measure tran VRK%dW%d FIND V(ph%d) AT=%.6fp" % (k, n, k, lag(tc)))
                for j in (D,):
                    for i in range(MG):
                        ms.append(".measure tran VK%d_%d_%dW%d FIND V(o%d_%d_%d) AT=%.6fp"
                                  % (k, j, i, n, k, j, i, lag(tc)))
    # ---- splice: network after the head, before input words; measures after .tran
    hi = 4                      # head_lines() length
    L = L[:hi] + net + L[hi:]
    ti = [i for i, l in enumerate(L) if l.startswith(".tran")][0]
    L[ti] = ".tran 0.1p %gp 0 0.25p UIC" % TEND
    vl = 0.8 if args.softstart else None
    ic = ["V(pA)=0", "V(pB)=%g" % DV, "V(pC)=%g" % DV, "V(vddh)=%g" % DV,
          "V(lin)=%g" % (vl if vl else DV), "V(lmid)=%g" % (vl if vl else DV),
          "V(lx)=%g" % (vl if vl else DV), "V(lout)=%g" % (vl if vl else 0.0)]
    for k in range(1, nbank + 1):
        ic.append("V(ph%d)=%g" % (k, 0.0 if (k - 1) % 3 == 0 else DV))
    L.insert(ti, ".ic " + " ".join(ic))
    pi = [i for i, l in enumerate(L) if l.startswith(".print")][0]
    extra = [" I(L1)", " V(lin)", " V(lout)", " I(VDDH)", " I(VZR)", " I(VML)",
             " V(pA)", " V(pB)", " V(pC)"]
    if args.diag:
        extra += [" I(%s)" % am for (nm, am, pn, other, g) in sw_names if am]
        extra += [" V(%s)" % (("g%s_s" % nm) if not nm.startswith("p") else ("gp%s_s" % nm[1:]))
                  for (nm, am, pn, other, g) in sw_names if g]
        L[ti + 1] = ".tran 0.1p %gp 0 0.25p UIC" % (3 * T)
    L[pi] = L[pi] + "".join(extra)
    L = L[:pi] + ms + L[pi:] + [".end"]
    S.update(dict(regime=args.regime, ncopy=ncopy, N_per_phase=2 * ncopy, L_nH=args.L,
                  RL_ohm=args.RL, I0_seed_mA=args.I0, sw=args.sw, Ct_fF=args.Ct,
                  e0=e0, e1=e1, zero_ps=zero_ps, Wst=args.Wst, Wh=args.Wh, Wz=args.Wz,
                  bbm=check_bbm(zero_ps, e0, t_hand), gate_edges=gate_edges,
                  softstart=bool(args.softstart), t_handover_ps=t_hand, I_seed_IC_mA=round(i_seed, 5),
                  t1_frac=args.t1, zero_clamp=("buck-clamp" if args.t1 > 0 else ("pulse %g ps" % zero_ps if zero_ps > 0 else "none")),
                  n_switch_metered=len([1 for s in sw_names if s[1]])))
    return L, S


# ------------------------------------------------------------- extraction
def post(rundir, S, o):
    """lsteer-specific books from the .prn grid + .mt0: inductor current, ripple,
    drift, zero crossings, arrival errors, terminal excursions, energy ledger."""
    fn = [f for f in os.listdir(rundir) if f.endswith(".cir.prn")][0]
    prn = os.path.join(rundir, fn)
    mt0 = M3.parse_mt0(prn[:-4] + ".mt0")
    n, C = M3.load_grid(prn, TEND)
    G = M3.GRID
    at = lambda sig, t: C[sig][max(0, min(n - 1, int(round(t / G))))]
    IL = C["I(L1)"]
    R = {}
    # ---- inductor current over the steady waves [2T, 5T)
    a0, a1 = int(2 * T / G), min(n - 1, int(5 * T / G))
    seg = IL[a0:a1 + 1]
    imean = sum(seg) / len(seg)
    imax, imin = max(seg), min(seg)
    ilt = {nn: mt0.get("IL_T%d" % nn) for nn in (2, 3, 4, 5)}
    drift = None
    if None not in (ilt[2], ilt[5]) and abs(imean) > 1e-9:
        drift = 100.0 * (ilt[5] - ilt[2]) / (3.0 * imean)
    R["inductor"] = dict(I_mean_mA=round(imean * 1e3, 4), I_max_mA=round(imax * 1e3, 4),
                         I_min_mA=round(imin * 1e3, 4),
                         ripple_pp_mA=round((imax - imin) * 1e3, 4),
                         ripple_pct_of_mean=(round(100 * (imax - imin) / abs(imean), 2)
                                             if abs(imean) > 1e-6 else None),
                         I_at_nT_mA={nn: (round(v * 1e3, 4) if v is not None else None)
                                     for nn, v in ilt.items()},
                         drift_pct_per_cycle=(round(drift, 3) if drift is not None else None),
                         E_stored_mean_fJ=round(0.5 * S["L_nH"] * 1e-9 * imean ** 2 * 1e15, 2))
    # zero crossings per third (DCM diagnostics; CCM should have none)
    zc = []
    for a in range(a0 + 1, a1 + 1):
        if (IL[a - 1] > 0) != (IL[a] > 0):
            t = (a - 1) * G + G * IL[a - 1] / (IL[a - 1] - IL[a])
            zc.append(round(t, 2))
    rel = [round(((t % TT) if (t % TT) < TT - 1e-9 else 0.0), 2) for t in zc]
    R["zero_crossings"] = dict(n=len(zc), times_ps=zc[:30], after_third_start_ps=rel[:30],
                               mean_after_third_start_ps=(round(sum(rel) / len(rel), 2) if rel else None))
    # per-third current extremes (DCM peak) and reverse-current fraction
    pk, neg = [], 0
    for j in range(9):
        b0 = int((2 * T + j * TT) / G)
        b1 = min(n - 1, int((2 * T + (j + 1) * TT) / G))
        s = IL[b0:b1 + 1]
        pk.append(round(max(s) * 1e3, 3))
        neg += sum(1 for x in s if x < 0)
    R["inductor"]["third_peak_mA"] = pk
    R["inductor"]["reverse_current_fraction"] = round(neg / float(a1 - a0 + 1), 4)
    # per-third ripple (max-min inside each third, mean over the 9 steady thirds):
    # the 3-cycle max-min above also contains the secular drift, so it OVERSTATES ripple
    pp = []
    for j in range(9):
        b0 = int((2 * T + j * TT) / G)
        b1 = min(n - 1, int((2 * T + (j + 1) * TT) / G))
        sgm = IL[b0:b1 + 1]
        pp.append((max(sgm) - min(sgm)) * 1e3)
    R["inductor"]["ripple_pp_3cycles_mA"] = R["inductor"]["ripple_pp_mA"]
    R["inductor"]["ripple_pct_3cycles"] = R["inductor"]["ripple_pct_of_mean"]
    R["inductor"]["ripple_pp_per_third_mA"] = round(sum(pp) / 9.0, 4)
    R["inductor"]["ripple_pp_per_third_list_mA"] = [round(x, 3) for x in pp]
    R["inductor"]["ripple_pct_per_third"] = (round(100 * sum(pp) / 9.0 / abs(imean * 1e3), 2)
                                              if abs(imean) > 1e-6 else None)
    # ---- arrival errors at the clamps, rail excursions, terminal excursions
    rails = {k: C["V(PH%d)" % k] for k in range(1, NB + 1)}
    arr_h, arr_z, step_h, overs, unders = [], [], [], [], []
    e0, zero_ps = S["e0"], S["zero_ps"]
    for k in range(1, NB + 1):
        for nn in (2, 3, 4):
            s0 = M3.slot(k, nn, T, TT)
            tr = s0 + TT                       # rise end: out opens at tr-e1..tr-e0
            v_before = at("V(PH%d)" % k, tr - S["e1"] - 0.2)
            v_after = at("V(PH%d)" % k, tr + S["e1"] + 1.0)
            arr_h.append(round(1000 * (v_before - DV), 2))
            step_h.append(round(1000 * (v_after - v_before), 2))
            tf = s0 + 3 * TT                   # fall end (or the buck split t1): before the zero clamp / in-switch opens
            tz = (s0 + 2 * TT + S["t1_frac"] * TT) if S["t1_frac"] > 0 else (tf - max(zero_ps, 0.0))
            vz = at("V(PH%d)" % k, tz - S["e1"] - 0.2)
            arr_z.append(round(1000 * vz, 2))
            w0, w1 = int(s0 / G), min(n - 1, int((s0 + 3 * TT) / G))
            overs.append(max(rails[k][w0:w1 + 1]))
            unders.append(min(rails[k][w0:w1 + 1]))
    R["arrival"] = dict(
        rise_end_before_hold_clamp_minus_dV_mV=dict(min=min(arr_h), max=max(arr_h),
                                                   mean=round(sum(arr_h) / len(arr_h), 2)),
        hold_clamp_step_mV=dict(min=min(step_h), max=max(step_h)),
        fall_end_before_zero_clamp_mV=dict(min=min(arr_z), max=max(arr_z),
                                          mean=round(sum(arr_z) / len(arr_z), 2)),
        rail_max_V=round(max(overs), 4), rail_min_V=round(min(unders), 4))
    lin, lout = C["V(LIN)"], C["V(LOUT)"]
    R["terminals"] = dict(lin_max_V=round(max(lin[a0:a1 + 1]), 3), lin_min_V=round(min(lin[a0:a1 + 1]), 3),
                          lout_max_V=round(max(lout[a0:a1 + 1]), 3), lout_min_V=round(min(lout[a0:a1 + 1]), 3))
    # ---- energy ledger per bank per cycle, steady waves 2..4 (3 cycles)
    nbank = NB * S["ncopy"]
    def dT(tg):
        a, b = mt0.get("%s_T2" % tg), mt0.get("%s_T5" % tg)
        return None if None in (a, b) else (b - a) / 3.0
    qdd, qzr, erl, esw = dT("QDD"), dT("QZR"), dT("ERL"), dT("ESW")
    e_dd = DV * qdd if qdd is not None else None
    il2, il5 = ilt[2], ilt[5]
    dEL = (0.5 * S["L_nH"] * 1e-9 * (il5 ** 2 - il2 ** 2) / 3.0) if None not in (il2, il5) else None
    ch = o["charge_spec_reported_not_gated"]
    ebank = [v["E_rise_fJ"] + v["E_hold_fJ"] + v["E_fall_fJ"] for v in ch.values()
             if None not in (v["E_rise_fJ"], v["E_hold_fJ"], v["E_fall_fJ"])]
    ebank_mean = sum(ebank) / len(ebank) if ebank else None
    # gate: metered up-edge charge x V (conventional driver booking) + net adiabatic
    gate = {}
    eg_up_total = 0.0
    eg_fit_total = 0.0
    for nm, ge in S["gate_edges"].items():
        qa, qb = mt0.get(("QGA_%s" % nm).upper()), mt0.get(("QGB_%s" % nm).upper())
        qup = abs(qb - qa) * 1e15 if None not in (qa, qb) else None   # |gate charge| of the turn-on edge
        e_up = qup * ge["vg"] if qup is not None else None
        e_fit = QG_FIT * ge["W_um"] * ge["vg"]
        gate[nm] = dict(Q_up_fC=(round(qup, 2) if qup is not None else None),
                        fC_per_um=(round(qup / ge["W_um"], 3) if qup is not None else None),
                        E_up_fJ=(round(e_up, 2) if e_up is not None else None),
                        E_fit_fJ=round(e_fit, 2), W_um=ge["W_um"], Vg=ge["vg"])
        eg_up_total += (e_up or 0.0)
        eg_fit_total += e_fit
    egn = dT("EGN")
    # ideal rows: price the switch gates at the fit as a RIDER (12 switches, widths = real-row defaults)
    if not S["gate_edges"]:
        eg_fit_total = QG_FIT * (6 * S["Wst"] * VGH + 3 * S["Wh"] * DV + 3 * S["Wz"] * DV)
    per = lambda x: (round(x * 1e15 / nbank, 2) if x is not None else None)
    led = dict(
        n_banks_on_inductor=nbank, cycles_averaged=3,
        E_dc_rail_fJ_per_bank=per(e_dd), Q_dc_rail_fC_per_bank=(round(qdd * 1e15 / nbank, 2) if qdd is not None else None),
        Q_zero_rail_fC_per_bank=(round(qzr * 1e15 / nbank, 2) if qzr is not None else None),
        E_resistive_L_fJ_per_bank=per(erl), E_switch_conduction_fJ_per_bank=per(esw),
        E_gate_up_metered_fJ_per_bank=(round(eg_up_total / nbank, 2) if S["gate_edges"] else None),
        E_gate_fit_3p7fCum_fJ_per_bank=round(eg_fit_total / nbank, 2),
        E_gate_net_adiabatic_fJ_per_bank=per(egn),
        dE_L_stored_fJ_per_cycle_group=(round(dEL * 1e15, 2) if dEL is not None else None),
        E_bank_mean_fJ_per_bank_from_books=(round(ebank_mean, 2) if ebank_mean is not None else None),
        E_bank_per_bank_list=[round(x, 2) for x in ebank])
    tot_ideal = None
    if e_dd is not None:
        tot_ideal = (e_dd - (dEL or 0.0)) * 1e15 / nbank
        led["E_total_sources_fJ_per_bank"] = round(tot_ideal, 2)
        led["E_total_plus_gate_metered_fJ_per_bank"] = (
            round(tot_ideal + eg_up_total / nbank, 2) if S["gate_edges"] else None)
        led["E_total_plus_gate_fit_fJ_per_bank"] = round(tot_ideal + eg_fit_total / nbank, 2)
        led["vs_ledger_240p3_pct"] = round(100 * (tot_ideal / E_LEDGER - 1), 1)
        led["vs_ledger_240p3_with_gate_fit_pct"] = round(100 * ((tot_ideal + eg_fit_total / nbank) / E_LEDGER - 1), 1)
        led["vs_harmonic_534_with_gate_fit_pct"] = round(100 * ((tot_ideal + eg_fit_total / nbank) / E_HARM - 1), 1)
        if ebank_mean is not None and erl is not None and esw is not None and S["ncopy"] == 1:
            lhs = (e_dd - (dEL or 0.0)) * 1e15
            rhs = ebank_mean * nbank + (erl + esw) * 1e15
            led["balance_check"] = dict(sources_minus_dEL_fJ=round(lhs, 2),
                                        banks_plus_losses_fJ=round(rhs, 2),
                                        mismatch_pct=round(100 * (lhs - rhs) / max(abs(rhs), 1e-9), 2),
                                        note="terminal-cap and 0 V-rail energies are not in rhs; ideal switch Ron 0.05 ohm is in esw")
    R["ledger"] = led
    R["gate_detail"] = gate
    # ---- copies' value check (banks 7..)
    if S["ncopy"] > 1:
        pat = M3.PATS[S["pat"]]
        fails, checked = [], 0
        for c in range(1, S["ncopy"]):
            for kb in range(1, NB + 1):
                k = kb + NB * c
                for nn in (2, 3, 4):
                    rail = mt0.get("VRK%dW%d" % (k, nn))
                    bb = M3.bits(pat, kb, D, nn, D)
                    for i in range(MG):
                        v = mt0.get("VK%d_%d_%dW%d" % (k, D, i, nn))
                        checked += 1
                        if v is None or rail is None:
                            fails.append([k, i, nn, "missing"]); continue
                        trip, _ = M3.TRIPF(rail)
                        ok = (v > trip) if bb[i] else (v < trip)
                        if not ok:
                            fails.append([k, i, nn, round(v, 4), round(trip, 4)])
        R["copies_value"] = dict(checked=checked, n_fail=len(fails), fails=fails[:20],
                                 PASS=(not fails), note="banks 7.. crest FIND vs trip(rail) at the sampling instant")
    return R


def summarize(o):
    a, v = o["acceptance"], o["value"]
    e3 = o["erosion"][3] if 3 in o["erosion"] else o["erosion"]["3"]
    ls = o["lsteer"]
    return dict(PASS=a["PASS"], value_fail=v["n_fail"], worst_margin_mV=a["worst_margin_at_commit_mV"],
                worst_overlap_ps=a["worst_overlap_ps"], standing_eye_ps=e3["asymptotic_width_ps"],
                widths=e3["width_0mV_ps_links"], sign=e3["sign"],
                I_mean_mA=ls["inductor"]["I_mean_mA"], ripple_pct=ls["inductor"]["ripple_pct_of_mean"],
                ripple_pp_mA=ls["inductor"]["ripple_pp_mA"], drift_pct=ls["inductor"]["drift_pct_per_cycle"],
                ripple_pp_third_mA=ls["inductor"].get("ripple_pp_per_third_mA"),
                ripple_pct_third=ls["inductor"].get("ripple_pct_per_third"),
                zc_mean_ps=ls["zero_crossings"]["mean_after_third_start_ps"], n_zc=ls["zero_crossings"]["n"],
                arrival_rise_mV=ls["arrival"]["rise_end_before_hold_clamp_minus_dV_mV"],
                arrival_fall_mV=ls["arrival"]["fall_end_before_zero_clamp_mV"],
                rail_max_V=ls["arrival"]["rail_max_V"], rail_min_V=ls["arrival"]["rail_min_V"],
                terminals=ls["terminals"], hold_rail_4=o["hold_rail"].get(4, o["hold_rail"].get("4")),
                E_dc=ls["ledger"]["E_dc_rail_fJ_per_bank"], E_R=ls["ledger"]["E_resistive_L_fJ_per_bank"],
                E_sw=ls["ledger"]["E_switch_conduction_fJ_per_bank"],
                E_gate_metered=ls["ledger"]["E_gate_up_metered_fJ_per_bank"],
                E_gate_fit=ls["ledger"]["E_gate_fit_3p7fCum_fJ_per_bank"],
                E_total_sources=ls["ledger"].get("E_total_sources_fJ_per_bank"),
                E_total_gate_fit=ls["ledger"].get("E_total_plus_gate_fit_fJ_per_bank"),
                E_total_gate_metered=ls["ledger"].get("E_total_plus_gate_metered_fJ_per_bank"),
                copies=ls.get("copies_value", {}).get("PASS"))


def cmd_one(args):
    tag = args.tag or ("%s_N%d_L%g_R%g_I%g_%s%s%s" % (args.regime, 2 * args.ncopy, args.L, args.RL,
                                                     args.I0, args.sw, ("_ss" if args.softstart else "")
                                                     + ("_nz" if args.zero_ps == 0 and args.t1 == 0 else "")
                                                     + ("_t1%g" % args.t1 if args.t1 > 0 else ""),
                                                     "" if args.pat == "P0" else "_" + args.pat))
    rdir = os.path.join(HERE, "runs", tag)
    if os.path.exists(os.path.join(rdir, "OUT.json")) and not args.force:
        print("cached", tag); return json.load(open(os.path.join(rdir, "OUT.json")))
    rundir = os.path.join(RUNS_SCRATCH, tag)
    lines, S = build(args)
    S["tag"] = tag
    print(tag, "bbm", S["bbm"], flush=True)
    assert S["bbm"]["ok"]
    t0 = time.monotonic()
    p, msg = M3.run_xyce(rundir, "c_%s.cir" % tag, lines, timeout=args.timeout)
    print("  %s %s" % (tag, msg), flush=True)
    os.makedirs(rdir, exist_ok=True)
    if p is None:
        json.dump(dict(S, error=msg), open(os.path.join(rdir, "OUT.json"), "w"), indent=1)
        for f in os.listdir(rundir):
            if f.endswith((".cir", ".mt0")):
                shutil.copy2(os.path.join(rundir, f), rdir)
        return dict(S, error=msg)
    o = M3.extract(rundir, S, keep_prn=True)
    o["lsteer"] = post(rundir, S, o)
    o["summary"] = summarize(o)
    json.dump(o, open(os.path.join(rundir, "OUT.json"), "w"), indent=1)
    for f in os.listdir(rundir):
        if f.endswith((".cir", ".mt0")) or f == "OUT.json":
            shutil.copy2(os.path.join(rundir, f), rdir)
    if not args.keep:
        os.remove(p + ".prn")
    print("  %s -> %s" % (tag, json.dumps(o["summary"])), flush=True)
    return o


def cmd_agg():
    R = {}
    rd = os.path.join(HERE, "runs")
    for tag in sorted(os.listdir(rd)):
        oj = os.path.join(rd, tag, "OUT.json")
        if os.path.exists(oj):
            o = json.load(open(oj))
            R[tag] = o.get("summary", dict(error=o.get("error")))
            if "summary" in o:
                R[tag].update(dict(regime=o["regime"], N=o["N_per_phase"], L_nH=o["L_nH"], RL=o["RL_ohm"],
                                   I0_seed=o["I0_seed_mA"], sw=o["sw"], pat=o["pat"]))
    json.dump(R, open(os.path.join(HERE, "TABLES.json"), "w"), indent=1)
    for t, r in R.items():
        print(t, json.dumps({k: r.get(k) for k in ("PASS", "worst_margin_mV", "worst_overlap_ps", "standing_eye_ps",
                                                  "I_mean_mA", "ripple_pct", "drift_pct", "zc_mean_ps",
                                                  "E_total_sources", "E_total_gate_fit", "E_total_gate_metered")}))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--regime", default="ccm")
    ap.add_argument("--ncopy", type=int, default=1)
    ap.add_argument("--L", type=float, default=120.0)
    ap.add_argument("--RL", type=float, default=10.0)
    ap.add_argument("--I0", type=float, default=3.15)
    ap.add_argument("--sw", default="ideal")
    ap.add_argument("--Ct", type=float, default=20.0)
    ap.add_argument("--Wst", type=float, default=30.0)
    ap.add_argument("--Wh", type=float, default=60.0)
    ap.add_argument("--Wz", type=float, default=10.0)
    ap.add_argument("--pat", default="P0")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--nosoft", dest="softstart", action="store_false", default=True)
    ap.add_argument("--zero_ps", type=float, default=None, help="zero-clamp pulse width; 0 = no zero clamp")
    ap.add_argument("--t1", type=float, default=0.0, help="buck split fraction of the fall third (0 = off)")
    ap.add_argument("--diag", action="store_true", help="short run (3T) with switch currents + gate voltages printed")
    a = ap.parse_args()
    if a.cmd == "one":
        o = cmd_one(a)
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    if a.cmd == "agg":
        sys.exit(cmd_agg())
    if a.cmd == "regate":
        rdir = os.path.join(HERE, "runs", a.tag)
        o = json.load(open(os.path.join(rdir, "OUT.json")))
        mt0 = M3.parse_mt0([os.path.join(rdir, f) for f in os.listdir(rdir) if f.endswith(".mt0")][0])
        nbank = NB * o["ncopy"]
        gate, eg_up = {}, 0.0
        for nm, ge in o["gate_edges"].items():
            qa, qb = mt0.get(("QGA_%s" % nm).upper()), mt0.get(("QGB_%s" % nm).upper())
            qup = abs(qb - qa) * 1e15 if None not in (qa, qb) else None
            e_up = qup * ge["vg"] if qup is not None else None
            gate[nm] = dict(Q_up_fC=(round(qup, 2) if qup is not None else None),
                            fC_per_um=(round(qup / ge["W_um"], 3) if qup is not None else None),
                            E_up_fJ=(round(e_up, 2) if e_up is not None else None),
                            E_fit_fJ=round(QG_FIT * ge["W_um"] * ge["vg"], 2), W_um=ge["W_um"], Vg=ge["vg"])
            eg_up += (e_up or 0.0)
        led = o["lsteer"]["ledger"]
        led["E_gate_up_metered_fJ_per_bank"] = round(eg_up / nbank, 2)
        tot = led.get("E_total_sources_fJ_per_bank")
        if tot is not None:
            led["E_total_plus_gate_metered_fJ_per_bank"] = round(tot + eg_up / nbank, 2)
        o["lsteer"]["gate_detail"] = gate
        o["summary"] = summarize(o)
        json.dump(o, open(os.path.join(rdir, "OUT.json"), "w"), indent=1)
        print(json.dumps(dict(E_gate_metered=led["E_gate_up_metered_fJ_per_bank"],
                              E_total_gate_metered=led.get("E_total_plus_gate_metered_fJ_per_bank"),
                              per_switch={k: (v["Q_up_fC"], v["fC_per_um"]) for k, v in gate.items()})))
        sys.exit(0)
    if a.cmd == "deck":
        lines, S = build(a)
        print("\n".join(lines)); print(json.dumps({k: v for k, v in S.items() if k != "gate_edges"}), file=sys.stderr)
