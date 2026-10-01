#!/usr/bin/env python3
"""qal/meshdrv -- pricing the flat-top mesh driver against the committed
qal/mesh3 trap_tt92_d3 interface spec.  PRE_REGISTERED.json (sha256 27394eb3,
mtime 2026-10-01 01:39:26.715 -0700) was the only file in this directory
before this file existed.

AMENDMENT A1 (before the first deck, from the DERIVED Fourier step): the
committed trapezoid (rise = T/3) has NO harmonics at multiples of 3 (sinc
null at n*tau_r/T integer; also exactly why three such phases sum flat) --
the task's "~3 odd harmonics" framing is impossible for THIS waveform; the
series is n = 1,2,4,5,7,8...  Candidate A's K sweep is therefore {1,2,5,8}
(DERIVED droop 173.8 / 79.8 / 41.3 / 27.7 mV), not the pre-registered
{2,3,5} (K=3 is identical to K=2).

AMENDMENT A2 (before the first B deck): booking rule 2 edge case -- if a
free-running sine/harmonic source's NET cycle energy is NEGATIVE (the clamp
pumps charge INTO the tank), the absorbed energy is credited ZERO (a
free-running tank cannot bank net absorbed energy every cycle; the sustainer
becomes a brake and dumps it).  Both readings reported.

AMENDMENT A3 (before the first C deck): the tg15p park lesson is carried but
the park target moves from ground to the MID-RAIL: a ground- or VHOLD-park
on the inductor-side node would put a DC 0.825 V across the inductor for the
whole hold third (dI/dt = 85 uA/ps -- milliamp runaway by arithmetic, no sim
needed).  The park is a 0.5 um nMOS from the switch-side node to VMID,
riding the clamp's own nccl control (no extra generator).

Committed mesh3.py code imported and reused VERBATIM (deck, extract, Trip,
run_xyce, integ, load_grid, parse_mt0); runs on tmpfs scratch; own
PYMS_VAE_CACHE built serially by the instrument check; no .prn in the repo.
"""
import importlib.util, json, math, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
M3 = "/usr/local/src/stat-sim/qal/mesh3/mesh3.py"
spec = importlib.util.spec_from_file_location("mesh3", M3)
mesh3 = importlib.util.module_from_spec(spec)
sys.modules["mesh3"] = mesh3
spec.loader.exec_module(mesh3)

SCRATCH = ("/tmp/claude-1001/-usr-local-src/"
           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad")
CACHE = os.path.join(SCRATCH, "vae_cache_meshdrv")
RUNS = os.path.join(SCRATCH, "meshdrv_runs")
os.makedirs(RUNS, exist_ok=True)
mesh3.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                 PYMS_VAE_CACHE=CACHE)

DV, TT = 1.65, 92.0
T = 3 * TT
F0 = 1e12 / T                    # Hz
LAG = mesh3.LAG_PS
E_LEDGER_B4 = 240.292            # fJ/bank/cycle committed (149.513+206.090-115.311)
ETA_AMP = 0.2546                 # MEASURED qal/amp headline (Q_ind=19)
QG_FIT = 3.635                   # fC/um corrected committed fit (cross-check)
E_PULSEGEN = 15.5                # fJ/cycle MEASURED park-driver band 15.0-16.0
CHAIN_TAX = 1.33
integ = mesh3.integ


def fourier(K):
    import numpy as np
    N = 200000
    t = np.linspace(0, 1.0, N, endpoint=False)
    f = np.where(t < 1/3., DV*3*t, np.where(t < 2/3., DV, DV*3*(1-t)))
    c0 = float(f.mean())
    hs = []
    for n in range(1, K+1):
        a = 2/N*float(np.sum(f*np.cos(2*np.pi*n*t)))
        b = 2/N*float(np.sum(f*np.sin(2*np.pi*n*t)))
        A = math.hypot(a, b)
        if A < 1e-6:
            continue
        ph = math.degrees(math.atan2(a, b))
        hs.append((n, A, ph))
    return c0, hs


def base_deck(rs=0.001):
    return mesh3.deck("trap", TT, 3, "P0", rs)


def splice(lines, bank_nodes, newlines, prints, meas):
    out = []
    for ln in lines:
        hit = None
        for k, drv in bank_nodes.items():
            if ln.startswith("VPH%d phs%d 0 PWL" % (k, k)):
                hit = "VPH%d phs%d %s 0" % (k, k, drv)
                break
        if hit:
            out.append(hit)
            continue
        if ln.startswith(".tran"):
            out.extend(newlines)
            out.append(ln)
            continue
        if ln.startswith(".print tran"):
            out.extend(meas)
            out.append(ln + " " + " ".join(prints))
            continue
        out.append(ln)
    return out


def ctrl_pwl(name, events, v_start, edge=0.5):
    """events = [(t_ps, v)] steps with 2*edge ps edges; events before t=2
    fold into the initial value (phase-C-at-t0 correctness)."""
    v0 = v_start
    evs = []
    for t, v in sorted(events):
        if t < 2.0:
            v0 = v
        else:
            evs.append((t, v))
    pts, cur = [(0.0, v0)], v0
    for t, v in evs:
        if abs(v - cur) < 1e-9:
            continue
        pts += [(t - edge, cur), (t + edge, v)]
        cur = v
    s = " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v for t, v in pts)
    return "V%s %s 0 PWL(%s)" % (name.upper(), name, s)


def meas_reads(tags, times):
    L = []
    for tg in tags:
        for nm, t in times.items():
            L.append(".measure tran DRV_%s_%s FIND V(x%s) AT=%.6fp"
                     % (tg.upper(), nm, tg, t + LAG))
    return L


def cycle_times(ph, waves=(2, 3, 4, 5)):
    return {"W%d" % n: n * T + ph * TT for n in waves}


def clamp_lines(sf, wcl, hold_windows, edge=0.5):
    """tg clamp drv<sf> <-> vh<sf> + metered rail + controls."""
    L = [
        "VHSRC%s vh%s 0 DC %g" % (sf, sf, DV),
        "XCLP%s drv%s pccl%s vh%s vh%s sg13_lv_pmos w=%gu l=0.13u"
        % (sf, sf, sf, sf, sf, wcl*2/3.),
        "XCLN%s vh%s nccl%s drv%s 0 sg13_lv_nmos w=%gu l=0.13u"
        % (sf, sf, sf, sf, wcl/3.),
    ]
    ev_n, ev_p = [], []
    for (tc, to) in hold_windows:
        ev_n += [(tc, DV), (to, 0.0)]
        ev_p += [(tc, 0.0), (to, DV)]
    L.append(ctrl_pwl("nccl%s" % sf, ev_n, 0.0, edge))
    L.append(ctrl_pwl("pccl%s" % sf, ev_p, DV, edge))
    L += integ("qvh%s" % sf, "-I(VHSRC%s)" % sf)
    L += integ("evh%s" % sf, "-V(vh%s)*I(VHSRC%s)" % (sf, sf))
    L += integ("qgncl%s" % sf, "-I(VNCCL%s)" % sf)
    L += integ("qgpcl%s" % sf, "-I(VPCCL%s)" % sf)
    tags = ["qvh%s" % sf, "evh%s" % sf, "qgncl%s" % sf, "qgpcl%s" % sf]
    return L, tags


def gate_edge_meas(tags, edges):
    L = []
    for nm, te in edges.items():
        for tg in tags:
            L.append(".measure tran GE_%s_%s_A FIND V(x%s) AT=%.6fp"
                     % (tg.upper(), nm, tg, te - 3 + LAG))
            L.append(".measure tran GE_%s_%s_B FIND V(x%s) AT=%.6fp"
                     % (tg.upper(), nm, tg, te + 6 + LAG))
    return L


# -------------------------------------------------------------- candidates
def cand_A(K, bank=4, sf=None, phase=0):
    """harmonic-sum stack; the metered current is I(VPH<bank>) -- in shared
    runs the stack's E books meter the NAMED bank only (per-bank books; the
    other bank on the node has its own VPH ammeter)."""
    sf = sf or ("%d" % bank)
    c0, hs = fourier(K)
    L, tags = [], []
    prev = "a%sh0" % sf
    L.append("VA%sH0 %s 0 DC %g" % (sf, prev, c0))
    L += integ("ea%sh0" % sf, "-(V(%s))*I(VPH%d)" % (prev, bank))
    tags.append("ea%sh0" % sf)
    for (n, A, ph) in hs:
        node = "drv%s" % sf if n == hs[-1][0] else "a%sh%d" % (sf, n)
        L.append("VA%sH%d %s %s SIN(0 %.6f %.6f 0 0 %.4f)"
                 % (sf, n, node, prev, A, n * F0, ph - n * phase * 120.0))
        L += integ("ea%sh%d" % (sf, n),
                   "-(V(%s)-V(%s))*I(VPH%d)" % (node, prev, bank))
        tags.append("ea%sh%d" % (sf, n))
        prev = node
    prints = ["V(DRV%s)" % sf]
    meas = meas_reads(tags, cycle_times(phase))
    return L, prints, meas, dict(kind="A", K=K, c0=c0,
                                 harmonics=[[n, round(A, 6), round(p, 3)]
                                            for n, A, p in hs],
                                 tags=tags, phases={"drv%s" % sf: phase})


def cand_B(tank, wcl=24.0, bank=4):
    sf = "%d" % bank
    L = ["VSB%s sb%s 0 SIN(%g %g %g 0 0 -90)" % (sf, sf, DV/2, DV/2, F0)]
    prints = []
    extra = {}
    if tank == "r10":
        L.append("RTB%s sb%s drv%s 10" % (sf, sf, sf))
    else:
        CEFF = 145.544e-15 / DV
        LT = 1.0 / ((2*math.pi*F0)**2 * CEFF)
        RT = 2*math.pi*F0*LT / 19.0
        L.append("LTB%s sb%s tb%s %g IC=0" % (sf, sf, sf, LT))
        L.append("RTB%s tb%s drv%s %g" % (sf, sf, sf, RT))
        L.append("CTB%s tb%s 0 2f" % (sf, sf))   # physical tank-node parasitic
        prints.append("I(LTB%s)" % sf)
        extra = dict(L_tank_nH=round(LT*1e9, 3), R_tank_ohm=round(RT, 2),
                     note="series L at f0 resonance with committed "
                          "Q_rise/dV; R for Q_ind=19 (MEASURED amp ladder); "
                          "2 fF tank-node parasitic + 3 ps clamp edges after "
                          "the t=184.5ps hard-switch convergence abort "
                          "(the release interrupts ~mA of built-up fight "
                          "current -- B's anti-dead-time cousin, logged)")
    # AMENDMENT A4 (before the first B deck): clamp PRE-CLOSES 4 ps before
    # the hold third so the structural 0.4125 V yank (sine is at 0.75*dV at
    # the third boundary) lands inside the rise third; the committed droop
    # metric scores [hold+1, hold_end-1] as always.  Release at the exact
    # third boundary.
    holds = [(m*T + TT - 4, m*T + 2*TT) for m in range(0, 7)]
    CL, ctags = clamp_lines(sf, wcl, holds, edge=1.5)
    L += CL
    L += integ("esb%s" % sf, "-V(sb%s)*I(VSB%s)" % (sf, sf))
    L += integ("qsb%s" % sf, "-I(VSB%s)" % sf)
    tags = ["esb%s" % sf, "qsb%s" % sf] + ctags
    prints += ["V(DRV%s)" % sf, "I(VSB%s)" % sf, "I(VHSRC%s)" % sf]
    meas = meas_reads(tags, cycle_times(0))
    meas += gate_edge_meas(["qgncl%s" % sf, "qgpcl%s" % sf],
                           {"CLNUP": 3*T + TT - 4, "CLPUP": 3*T + 2*TT})
    info = dict(kind="B", tank=tank, wcl=wcl, tags=tags,
                phases={"drv%s" % sf: 0}, **extra)
    return L, prints, meas, info


def cand_C(Lnh, wsw, dz=0.0, wcl=24.0, wpk=3.0, sf="4", phase=0, nb=1,
           mbb=False):
    """AMENDMENT A5 (logged after the dz=58 zero-probe, before the final C
    row): the real mesh3 load has NO inductor-current zero in the hold
    window -- the hold-third corruption drain (~1.4 mA avg, the spec's own
    tracking-AND-corruption current) keeps the LC sourcing through the
    would-be crest (wide-scan zeros 153-159 ps = post-interrupt artifacts;
    no natural zero exists).  True ZCS is therefore IMPOSSIBLE on this load.
    mbb=True closes the clamp 2 ps BEFORE the switch opens (rail-to-rail at
    near-matched potential, 2 ps overlap) so the node never floats into the
    corruption drain; the break-before-make rule (buckfix) was for crowbar
    through OPPOSITE rails and does not apply to this same-potential
    handoff; the fall-side handoff stays BBM."""
    off = phase * TT
    L = [
        "VMID%s vm%s 0 DC %g" % (sf, sf, DV/2),
        "LH%s vm%s swn%s %gn IC=0" % (sf, sf, sf, Lnh),
        "XSSN%s swn%s ncss%s drv%s 0 sg13_lv_nmos w=%gu l=0.13u"
        % (sf, sf, sf, sf, wsw/3.),
        "XSSP%s swn%s pcss%s drv%s vh%s sg13_lv_pmos w=%gu l=0.13u"
        % (sf, sf, sf, sf, sf, wsw*2/3.),
        "XPK%s swn%s nccl%s vm%s 0 sg13_lv_nmos w=%gu l=0.13u"
        % (sf, sf, sf, sf, wpk),
    ]
    ev_n, ev_p, holds = [], [], []
    for m in range(-1, 8):
        t_open = m*T + TT + dz + off
        t_close = m*T + 2*TT + 1 + off
        ev_n += [(t_open, 0.0), (t_close, DV)]
        ev_p += [(t_open, DV), (t_close, 0.0)]
        holds.append((t_open + (-2 if mbb else 2),
                      m*T + 2*TT - 1 + off))
    L.append(ctrl_pwl("ncss%s" % sf, ev_n, DV))
    L.append(ctrl_pwl("pcss%s" % sf, ev_p, 0.0))
    holds = [(a, b) for a, b in holds if b > 2]
    CL, ctags = clamp_lines(sf, wcl, holds)
    L += CL
    L += integ("qvm%s" % sf, "-I(VMID%s)" % sf)
    L += integ("evm%s" % sf, "-V(vm%s)*I(VMID%s)" % (sf, sf))
    L += integ("qgnss%s" % sf, "-I(VNCSS%s)" % sf)
    L += integ("qgpss%s" % sf, "-I(VPCSS%s)" % sf)
    # initial state by phase: A rise-start (0 V), B fall-start (dV),
    # C hold-start (dV, swn parked at mid-rail)
    ic = {0: (0.0, 0.0), 1: (DV, DV), 2: (DV, DV/2)}[phase]
    L.append(".ic V(drv%s)=%g V(swn%s)=%g" % (sf, ic[0], sf, ic[1]))
    tags = ["qvm%s" % sf, "evm%s" % sf,
            "qgnss%s" % sf, "qgpss%s" % sf] + ctags
    prints = ["V(DRV%s)" % sf, "V(SWN%s)" % sf, "I(LH%s)" % sf,
              "I(VHSRC%s)" % sf, "I(VMID%s)" % sf]
    meas = meas_reads(tags, cycle_times(phase))
    to3 = 3*T + TT + dz + off
    tc3 = 3*T + 2*TT + 1 + off
    meas += gate_edge_meas(
        ["qgnss%s" % sf, "qgpss%s" % sf, "qgncl%s" % sf, "qgpcl%s" % sf],
        {"SSPUP": to3, "SSNUP": tc3, "CLNUP": to3 + 2, "CLPUP": tc3 - 2})
    info = dict(kind="C", L_nH=Lnh, wsw=wsw, wcl=wcl, wpk=wpk, dz=dz,
                nb=nb, mbb=mbb, tags=tags,
                phases={"drv%s" % sf: phase}, lcol="I(LH%s)" % sf.upper())
    return L, prints, meas, info


# ---------------------------------------------------------------- run/post
def post_driver(rundir, info):
    mt0f = [f for f in os.listdir(rundir) if f.endswith(".mt0")][0]
    mt0 = mesh3.parse_mt0(os.path.join(rundir, mt0f))
    prnf = [f for f in os.listdir(rundir) if f.endswith(".cir.prn")][0]
    n, C = mesh3.load_grid(os.path.join(rundir, prnf), 7*T)
    d = dict(info={k: v for k, v in info.items() if k != "tags"})
    cyc = {}
    for tg in info.get("tags", []):
        vals = {w: mt0.get(("DRV_%s_W%d" % (tg, w)).upper())
                for w in (2, 3, 4, 5)}
        diffs = [(vals[w+1] - vals[w]) * 1e15 for w in (2, 3, 4)
                 if vals[w] is not None and vals[w+1] is not None]
        if diffs:
            cyc[tg] = dict(per_cycle_f=[round(x, 4) for x in diffs],
                           mean_f=round(sum(diffs)/len(diffs), 4),
                           spread_f=round(max(diffs)-min(diffs), 4))
    d["cycles"] = cyc
    ge = {}
    for k in list(mt0):
        if k.startswith("GE_") and k.endswith("_A"):
            b = mt0.get(k[:-2] + "_B")
            if b is not None:
                ge[k[3:-2]] = round((b - mt0[k]) * 1e15, 4)
    d["gate_edge_fC"] = ge
    stats = {}
    for col, ph in info.get("phases", {}).items():
        cu = "V(%s)" % col.upper()
        if cu not in C:
            continue
        hmins, hmaxs, tmins = [], [], []
        for m in (2, 3, 4):
            h0 = int((m*T + ph*TT + TT + 1) / mesh3.GRID)
            h1 = int((m*T + ph*TT + 2*TT - 1) / mesh3.GRID)
            seg = [C[cu][a] for a in range(h0, min(h1, n-1))]
            hmins.append(min(seg)); hmaxs.append(max(seg))
            t0 = int((m*T + ph*TT - 3) / mesh3.GRID)
            t1 = int((m*T + ph*TT + 3) / mesh3.GRID)
            tmins.append(min(C[cu][a]
                             for a in range(max(0, t0), min(t1, n-1))))
        stats[cu] = dict(hold_min_V=round(min(hmins), 4),
                         hold_max_V=round(max(hmaxs), 4),
                         droop_mV=round(1000*(DV - min(hmins)), 2),
                         ripple_over_mV=round(1000*(max(hmaxs)-DV), 2),
                         trough_min_V=round(min(tmins), 4))
    d["drv_node"] = stats
    lcol = info.get("lcol")
    if lcol and lcol in C:
        ph = list(info["phases"].values())[0]
        zs, zw = [], []
        for m in (2, 3, 4):
            tc = m*T + ph*TT + TT
            a0 = int((tc - 20)/mesh3.GRID); a1 = int((tc + 30)/mesh3.GRID)
            z = None
            for a in range(max(1, a0), min(a1, n-1)):
                if C[lcol][a-1]*C[lcol][a] <= 0 and abs(C[lcol][a-1]) > 1e-12:
                    z = a*mesh3.GRID
                    break
            zs.append(round(z - (m*T + ph*TT), 3) if z else None)
            # wide scan: first downward zero of I_L anywhere in the rise+hold
            a0 = int((m*T + ph*TT + 40)/mesh3.GRID)
            a1 = int((m*T + ph*TT + 2*TT - 5)/mesh3.GRID)
            z2 = None
            for a in range(max(1, a0), min(a1, n-1)):
                if C[lcol][a-1] > 1e-7 and C[lcol][a] <= 0:
                    z2 = a*mesh3.GRID
                    break
            zw.append(round(z2 - (m*T + ph*TT), 3) if z2 else None)
        d["zcs_zero_after_slot_ps"] = zs
        d["zcs_zero_wide_ps"] = zw
        a0 = int((3*T + ph*TT - 5)/mesh3.GRID)
        a1 = int((4*T + ph*TT)/mesh3.GRID)
        d["IL_pk_uA_w3"] = round(max(abs(C[lcol][a])
                                     for a in range(a0, min(a1, n-1)))*1e6, 3)
    return d


def run_candidate(tag, built, bank_nodes, rs=0.001, timeout=2800):
    oj = os.path.join(HERE, "runs", tag, "OUT.json")
    if os.path.exists(oj):
        print("  cached", tag)
        return json.load(open(oj))
    newlines, prints, meas, info = built
    rundir = os.path.join(RUNS, tag)
    lines, S = base_deck(rs)
    lines = splice(lines, bank_nodes, newlines, prints, meas)
    p, msg = mesh3.run_xyce(rundir, "c_%s.cir" % tag, lines, timeout=timeout)
    print("  %s %s" % (tag, msg), flush=True)
    if p is None:
        os.makedirs(os.path.dirname(oj), exist_ok=True)
        json.dump(dict(error=msg, tag=tag), open(oj, "w"), indent=1)
        return dict(error=msg, tag=tag)
    o = mesh3.extract(rundir, S, keep_prn=True)
    o["driver"] = post_driver(rundir, info)
    o["tag"] = tag
    json.dump(o, open(os.path.join(rundir, "OUT.json"), "w"), indent=1)
    dst = os.path.join(HERE, "runs", tag)
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(rundir):
        if f.endswith((".cir", ".mt0")) or f == "OUT.json":
            shutil.copy2(os.path.join(rundir, f), os.path.join(dst, f))
    for f in [f for f in os.listdir(rundir) if f.endswith(".prn")]:
        os.remove(os.path.join(rundir, f))
    a = o["acceptance"]
    e3 = o["erosion"][3]
    dn = o["driver"]["drv_node"]
    print("  %s PASS=%s erosion=%s widths=%s droop=%s"
          % (tag, a["PASS"], e3["sign"], e3["width_0mV_ps_links"],
             {k: v["droop_mV"] for k, v in dn.items()}), flush=True)
    return o


# ------------------------------------------------------------- subcommands
def cmd_ic():
    tag = "ic_trap_tt92_d3"
    rundir = os.path.join(RUNS, tag)
    lines, S = base_deck()
    p, msg = mesh3.run_xyce(rundir, "c_%s.cir" % tag, lines, timeout=4000)
    print("  IC %s" % msg, flush=True)
    if p is None:
        print("IC XYCE FAIL")
        return 1
    o = mesh3.extract(rundir, S)
    ref = json.load(open("/usr/local/src/stat-sim/qal/mesh3/runs/"
                         "trap_tt92_d3/OUT.json"))
    rows, ok = {}, True
    for k in ("1", "4"):
        for f in ("Q_rise_fC", "Q_hold_fC", "Q_fall_fC", "E_hold_fJ"):
            a = o["charge_spec_reported_not_gated"][int(k)][f]
            b = ref["charge_spec_reported_not_gated"][k][f]
            rows["bank%s_%s" % (k, f)] = [a, b, round(a - b, 6)]
            if abs(a - b) > max(1e-3, 1e-3 * abs(b)):
                ok = False
    a = o["erosion"][3]["asymptotic_width_ps"]
    b = ref["erosion"]["3"]["asymptotic_width_ps"]
    rows["asymptotic_eye_ps"] = [a, b, round(a - b, 4)]
    if abs(a - b) > 0.2:
        ok = False
    rows["widths_w3"] = [o["erosion"][3]["width_0mV_ps_links"],
                         ref["erosion"]["3"]["width_0mV_ps_links"]]
    rows["worst_margin_mV"] = [o["acceptance"]["worst_margin_at_commit_mV"],
                               ref["acceptance"]["worst_margin_at_commit_mV"]]
    rows["PASS_flag"] = [o["acceptance"]["PASS"], ref["acceptance"]["PASS"]]
    res = dict(verdict="PASS" if ok else "FAIL", rows=rows,
               note="verbatim committed deck via committed mesh3.deck/extract,"
                    " fresh PYMS_VAE_CACHE built serially by this run")
    json.dump(res, open(os.path.join(HERE, "IC.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0 if ok else 1


def cmd_cal():
    L = mesh3.head_lines()
    rows = []
    for bi, vb in (("hi", 1.65), ("mid", 0.825), ("lo", 0.0)):
        for wi, W in (("w1", 1.0), ("w3", 3.0), ("w10", 10.0), ("w30", 30.0)):
            a = "a%s%s" % (bi, wi); b = "b%s%s" % (bi, wi)
            L.append("V%s %s 0 DC %g" % (a, a, vb))
            L.append("XN%s %s ng %s 0 sg13_lv_nmos w=%gu l=0.13u"
                     % (a, a, b, W/3.))
            L.append("XP%s %s pg %s vdd sg13_lv_pmos w=%gu l=0.13u"
                     % (a, a, b, W*2/3.))
            L.append("IL%s %s 0 DC 1u" % (a, b))
            rows.append((bi, wi, W, a, b))
    L += ["VDD vdd 0 DC %g" % DV, "VNG ng 0 DC %g" % DV, "VPG pg 0 DC 0",
          ".print dc " + " ".join("V(%s) V(%s)" % (a, b)
                                  for _, _, _, a, b in rows),
          ".dc VDD %g %g 1" % (DV, DV), ".end"]
    rundir = os.path.join(RUNS, "cal_ron")
    p, msg = mesh3.run_xyce(rundir, "cal_ron.cir", L, timeout=600)
    print("  cal_ron %s" % msg)
    res = {}
    if p:
        hdr = vals = None
        for ln in open(p + ".prn"):
            ps = ln.split()
            if not ps:
                continue
            if ps[0].lower() == "index":
                hdr = [h.upper() for h in ps]
            elif hdr and ps[0] == "0":
                vals = [float(x) for x in ps]
        got = dict(zip(hdr, vals))
        for bi, wi, W, a, b in rows:
            dvv = got["V(%s)" % a.upper()] - got["V(%s)" % b.upper()]
            res.setdefault("ron_" + bi, {})[wi] = dict(
                W_um=W, Ron_ohm=round(dvv/1e-6, 2),
                Ron_ohm_um=round(dvv/1e-6*W, 1))
    L2 = mesh3.head_lines()
    L2 += ["VD d 0 DC %g" % DV, "VS s 0 DC %g" % DV,
           "XN1 d ng s 0 sg13_lv_nmos w=1u l=0.13u",
           "XP1 d pg s vdd2 sg13_lv_pmos w=2u l=0.13u",
           "VDD2 vdd2 0 DC %g" % DV,
           "VNG ng 0 PWL(0 0 100p 0 102p %g 300p %g 302p 0)" % (DV, DV),
           "VPG pg 0 PWL(0 %g 100p %g 102p 0 300p 0 302p %g)" % (DV, DV, DV)]
    L2 += integ("qng", "-I(VNG)") + integ("qpg", "-I(VPG)")
    for nm, t in (("A", 95.0), ("B", 140.0), ("C", 295.0), ("D", 340.0)):
        L2.append(".measure tran QN%s FIND V(xqng) AT=%.1fp" % (nm, t + LAG))
        L2.append(".measure tran QP%s FIND V(xqpg) AT=%.1fp" % (nm, t + LAG))
    L2 += [".tran 0.1p 400p 0 0.5p", ".print tran V(xqng) V(xqpg)", ".end"]
    rundir2 = os.path.join(RUNS, "cal_qg")
    p2, msg2 = mesh3.run_xyce(rundir2, "cal_qg.cir", L2, timeout=600)
    print("  cal_qg %s" % msg2)
    if p2:
        m = mesh3.parse_mt0(p2 + ".mt0")
        qn = (m["QNB"] - m["QNA"]) * 1e15
        qp = -(m["QPB"] - m["QPA"]) * 1e15
        res["gate_charge"] = dict(
            qn_up_fC=round(qn, 4), qp_dn_fC=round(qp, 4),
            total_fC_per_um_tg=round((abs(qn) + abs(qp))/3.0, 4),
            committed_fit_fC_per_um=QG_FIT,
            note="tg 3um total (wn1/wp2), D/S at 1.65 V, VGH=1.65")
    json.dump(res, open(os.path.join(HERE, "CAL.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


def main():
    cmd = sys.argv[1]
    if cmd == "ic":
        sys.exit(cmd_ic())
    elif cmd == "cal":
        cmd_cal()
    elif cmd == "a":
        K = int(sys.argv[2])
        run_candidate("a_k%d" % K, cand_A(K), {4: "drv4"})
    elif cmd == "b":
        run_candidate("b_%s" % sys.argv[2], cand_B(sys.argv[2]), {4: "drv4"})
    elif cmd == "c":
        Lnh, wsw = float(sys.argv[2]), float(sys.argv[3])
        dz = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
        rs = float(sys.argv[5]) if len(sys.argv) > 5 else 0.001
        wcl = float(sys.argv[6]) if len(sys.argv) > 6 else 24.0
        tg = "c_L%g_w%g" % (Lnh, wsw)
        if dz:
            tg += "_dz%g" % dz
        if rs != 0.001:
            tg += "_rs%g" % rs
        if wcl != 24.0:
            tg += "_wcl%g" % wcl
        mbb = len(sys.argv) > 7 and sys.argv[7] == "mbb"
        if mbb:
            tg += "_mbb"
        run_candidate(tg, cand_C(Lnh, wsw, dz=dz, wcl=wcl,
                                 wpk=(12.0 if mbb else 3.0), mbb=mbb),
                      {4: "drv4"}, rs=rs)
    elif cmd == "cn2":
        Lnh, wsw = float(sys.argv[2]), float(sys.argv[3])
        dz = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
        run_candidate("c_n2_L%g_w%g" % (Lnh, wsw),
                      cand_C(Lnh, wsw, dz=dz, nb=2),
                      {4: "drv4", 1: "drv4"})
    elif cmd == "an2":
        K = int(sys.argv[2])
        run_candidate("a_n2_k%d" % K, cand_A(K), {4: "drv4", 1: "drv4"})
    elif cmd == "afull":
        K = int(sys.argv[2])
        NL, PR, MS, phases, tags = [], [], [], {}, []
        for ph, (sfx, bk) in ((0, ("pa", 4)), (1, ("pb", 2)), (2, ("pc", 3))):
            nl, pr, ms, info = cand_A(K, bank=bk, sf=sfx, phase=ph)
            NL += nl; PR += pr; MS += ms
            phases.update(info["phases"])
            tags += info["tags"]
        info = dict(kind="Afull", K=K, tags=tags, phases=phases)
        bank_nodes = {1: "drvpa", 4: "drvpa", 2: "drvpb", 5: "drvpb",
                      3: "drvpc", 6: "drvpc"}
        run_candidate("a_full_k%d" % K, (NL, PR, MS, info), bank_nodes,
                      timeout=6000)
    elif cmd == "ars":
        K = int(sys.argv[2]); rs = float(sys.argv[3])
        run_candidate("a_k%d_rs%g" % (K, rs), cand_A(K), {4: "drv4"}, rs=rs)
    elif cmd == "cfull":
        Lnh, wsw = float(sys.argv[2]), float(sys.argv[3])
        dz = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
        NL, PR, MS, phases, tags = [], [], [], {}, []
        for ph, sfx in ((0, "pa"), (1, "pb"), (2, "pc")):
            nl, pr, ms, info = cand_C(Lnh, wsw, dz=dz, sf=sfx, phase=ph, nb=2)
            NL += nl; PR += pr; MS += ms
            phases.update(info["phases"])
            tags += info["tags"]
        info = dict(kind="Cfull", L_nH=Lnh, wsw=wsw, dz=dz, nb=2,
                    tags=tags, phases=phases, lcol="I(LHPA)")
        bank_nodes = {1: "drvpa", 4: "drvpa", 2: "drvpb", 5: "drvpb",
                      3: "drvpc", 6: "drvpc"}
        run_candidate("c_full_L%g_w%g" % (Lnh, wsw), (NL, PR, MS, info),
                      bank_nodes, timeout=6000)


if __name__ == "__main__":
    main()
