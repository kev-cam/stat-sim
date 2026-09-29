#!/usr/bin/env python3
"""qal/vtreq -- THE DELVTO (threshold) REQUIREMENT SWEEP.

Answers, as a DEVICE SPEC: what |Vtp| would QAL need, and what does buying it cost.

THE TRAP THIS FILE EXISTS TO AVOID: lowering Vt makes CMOS faster too.  Every Q1
row therefore carries a CMOS comparator measured under the IDENTICAL DELVTO, in
the identical mode, on the identical cell and the identical load.

Nothing is copied: the hop path IMPORTS qal/skept/sk.py + qal/dvopt/skept2/s2sk.py
(the independently-written generator + waveform-only extractor that reproduced the
committed rows bit-identically) and rebinds HERE / ENV / SHIM.  The only change is
the shim: qal/vtreq/shim_dvt.sp is the committed qal/sg13lv_compat.sp with
DELVTO={DVTN} / DELVTO={DVTP} added, driven by two GLOBAL .param values.

Pre-registration: PRE_REGISTERED.json (written before this file existed).
"""
import json, math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
VA = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM = os.path.join(HERE, "shim_dvt.sp")
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_vtreq")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
           PYMS_VAE_CACHE=CACHE, PYMS_CALLBACK_PARAMS="DELVTO")

WP, WN = 1.12, 0.74            # campaign cell widths, um
LCH = 0.13                     # um
MGATE = 8

# campaign Vt criterion: Id = 100 nA * W/L at |Vds| = 0.1 V  (qal/chain3/vt.cir)
ICRIT_N = 100e-9 * (WN / LCH)
ICRIT_P = 100e-9 * (WP / LCH)

# delivered-rail anchors this study quotes against (all MEASURED, DELVTO = 0)
RAIL_L4 = 0.754572966          # VBEND, load691 L=4 nH real-load optimum
RAIL_ROBUST = 0.7138163        # VBEND, committed robust single hop L=15/W=30/dV=1.2

# the grid
DVTS = [0.0, -0.05, -0.10, -0.15, -0.20, -0.30]
MODES = ["P", "N", "B"]


def grid():
    """(tag, dvtn, dvtp) for the 16-point grid.  DELVTO = 0 appears once."""
    out = [("d000", 0.0, 0.0)]
    for d in DVTS[1:]:
        for m in MODES:
            out.append(("d%03d%s" % (int(round(-d * 1000)), m),
                        d if m in ("N", "B") else 0.0,
                        d if m in ("P", "B") else 0.0))
    return out


def head(dvtn, dvtp, opts=True):
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM]
    if opts:
        L.append(".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17")
    L.append(".param DVTN=%.10g DVTP=%.10g" % (dvtn, dvtp))
    return L


def run(fn, lines, timeout=900, cwd=None):
    p = os.path.join(cwd or HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd or HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT %gs" % timeout
    w = time.monotonic() - t
    if not os.path.exists(p + ".prn"):
        return None, "FAIL %s (%.0fs) %s" % (fn, w, r.stdout[-500:])
    return p, "%s ok %.0fs" % (fn, w)


def read_prn(path):
    hdr, rows = None, []
    for ln in open(path):
        p = ln.split()
        if hdr is None and p and p[0].lower() == "index":
            hdr = [h.upper() for h in p]
            continue
        if hdr and p and p[0][0].isdigit():
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                pass
    return hdr, rows


def col(hdr, name):
    n = name.upper()
    for i, h in enumerate(hdr):
        if h == n:
            return i
    for i, h in enumerate(hdr):
        if n in h:
            return i
    raise KeyError(name + " not in " + str(hdr))


# ===================================================================== G1 / DC
def dc_deck(dvtn, dvtp):
    """ONE .DC sweep of VG (0 -> 1.5 V, 1 mV) carrying, for this DELVTO point:

      * Vtn   -- cell nMOS 0.74u, Vds = 0.1 V, campaign criterion (chain3/vt.cir)
      * |Vtp| -- cell pMOS 1.12u, |Vds| = 0.1 V, source/bulk at 1.5, same criterion
      * inverter DC trip point (Vout = Vin) at VDD = 1.20 / 0.754573 / 0.713816
      * the SKEWED restore5-A4 receiving inverter's trip point at VDD = 1.20
      * V_STRAND -- THE Q2 MECHANISM.  A cell pMOS wired exactly as the chain
        strands it: drain AND bulk on the DRAINED rail (0 V), gate at 0 V, SOURCE
        = the held output node, which is the swept node.  The strand level is the
        source voltage at which conduction falls to the same campaign criterion,
        i.e. the level the predecessor's HIGH decays to and stops.  Body effect is
        INCLUDED (Vsb = V_source) because that is how the chain wires it.
      * OFF-state leakage at the delivered rail, gates fixed, both types.
    """
    L = head(dvtn, dvtp) + ["VG g 0 0", "VGZ gz 0 0"]
    # -- threshold extraction, campaign criterion
    L += ["VDN dn 0 0.1", "XN dn g 0 0 sg13_lv_nmos w=%gu l=%gu" % (WN, LCH),
          "VSP sp 0 1.5", "VDP dp 0 1.4",
          "XP dp g sp sp sg13_lv_pmos w=%gu l=%gu" % (WP, LCH)]
    # -- inverter DC transfer curves (trip point = where V(out) crosses V(in))
    for tag, vdd in (("12", 1.2), ("r4", RAIL_L4), ("rb", RAIL_ROBUST), ("15", 1.5)):
        L += ["VD%s d%s 0 %.9g" % (tag, tag, vdd),
              "XPI%s oi%s g d%s d%s sg13_lv_pmos w=%gu l=%gu" % (tag, tag, tag, tag, WP, LCH),
              "XNI%s oi%s g 0 0 sg13_lv_nmos w=%gu l=%gu" % (tag, tag, WN, LCH)]
    # -- the SKEWED receiving inverter of restore5's restoring stage (A4 cell)
    L += ["VDSK dsk 0 1.2",
          "XPSK osk g dsk dsk sg13_lv_pmos w=0.15u l=%gu" % LCH,
          "XNSK osk g 0 0 sg13_lv_nmos w=1.48u l=%gu" % LCH]
    # -- V_STRAND: 0 V ammeter from the swept node into the strand device's source
    L += ["VSTR g gstr 0",
          "XPSTR 0 gz gstr 0 sg13_lv_pmos w=%gu l=%gu" % (WP, LCH)]
    # -- OFF-state leakage at the two delivered rails and at 1.2 V, gates fixed
    for tag, v in (("r4", RAIL_L4), ("rb", RAIL_ROBUST), ("12", 1.2)):
        L += ["VLN%s ln%s 0 %.9g" % (tag, tag, v),
              "XLN%s ln%s gz 0 0 sg13_lv_nmos w=%gu l=%gu" % (tag, tag, WN, LCH),
              "VLP%s lp%s 0 %.9g" % (tag, tag, v), "VLPD%s lpd%s 0 0" % (tag, tag),
              "XLP%s lpd%s lp%s lp%s lp%s sg13_lv_pmos w=%gu l=%gu"
              % (tag, tag, tag, tag, tag, WP, LCH)]
    pr = ["V(g)", "I(VDN)", "I(VDP)", "I(VSTR)", "V(oi12)", "V(oir4)", "V(oirb)",
          "V(oi15)", "V(osk)"] + \
         ["I(VLN%s)" % t for t in ("r4", "rb", "12")] + \
         ["I(VLPD%s)" % t for t in ("r4", "rb", "12")]
    L.append(".dc VG 0 1.5 0.001")
    for k in range(0, len(pr), 8):
        L.append((".print dc " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L


def _cross_current(vs, ii, icrit, rising=True):
    """first interpolated crossing of |i| == icrit, linear in current"""
    for k in range(1, len(vs)):
        a, b = abs(ii[k - 1]), abs(ii[k])
        if (rising and a < icrit <= b) or (not rising and a > icrit >= b):
            if b == a:
                return vs[k]
            return vs[k - 1] + (icrit - a) * (vs[k] - vs[k - 1]) / (b - a)
    return None


def _cross_equal(vs, vo):
    """inverter trip: first crossing of V(out) == V(in)"""
    for k in range(1, len(vs)):
        a, b = vo[k - 1] - vs[k - 1], vo[k] - vs[k]
        if (a > 0 >= b) or (a < 0 <= b):
            if b == a:
                return vs[k]
            return vs[k - 1] - a * (vs[k] - vs[k - 1]) / (b - a)
    return None


def dc_extract(path):
    hdr, rows = read_prn(path)
    g = lambda n: [r[col(hdr, n)] for r in rows]
    # Xyce's .DC .prn does NOT carry the sweep source, so V(G) is printed
    # explicitly; the deck's own node voltage is the sweep axis.
    vg = g("V(G)")
    idn, idp, istr = g("I(VDN)"), g("I(VDP)"), g("I(VSTR)")
    out = {}
    out["Vtn"] = _cross_current(vg, idn, ICRIT_N, rising=True)
    # pMOS: |Vgs| = 1.5 - V(g) DECREASES as V(g) rises -> current falls
    vp = _cross_current(vg, idp, ICRIT_P, rising=False)
    out["Vtp_abs"] = None if vp is None else 1.5 - vp
    # V_STRAND at several current criteria.  The campaign criterion (same one
    # that defines |Vtp|) is the headline so the two are directly comparable;
    # the others show how criterion-sensitive the level is.  A held 2 fF output
    # node moving 1 mV over a 300 ps beat needs only ~6.7 nA, so the low-current
    # criteria are the physically relevant end.
    for nm, ic in (("", ICRIT_P), ("_100nA", 100e-9), ("_10nA", 10e-9),
                   ("_1nA", 1e-9)):
        out["V_strand" + nm] = _cross_current(vg, istr, ic, rising=True)
    for tag, key in (("12", "trip_1p20"), ("r4", "trip_rail_L4"),
                     ("rb", "trip_rail_robust"), ("15", "trip_1p50")):
        out[key] = _cross_equal(vg, g("V(OI%s)" % tag.upper()))
    out["trip_skewed_1p20"] = _cross_equal(vg, g("V(OSK)"))
    # off-state leakage: constant across the sweep, take the median sample
    m = len(rows) // 2
    for tag, key in (("r4", "rail_L4"), ("rb", "rail_robust"), ("12", "v1p20")):
        out["Ioff_n_%s_A" % key] = abs(g("I(VLN%s)" % tag.upper())[m])
        out["Ioff_p_%s_A" % key] = abs(g("I(VLPD%s)" % tag.upper())[m])
    return out


# ============================================================ CMOS comparator
def cmos_deck(dvtn, dvtp, cl_list=(6.91, 2.0)):
    """CMOS_dev: the SAME campaign inverter on a FIXED DC rail, driving the SAME
    load as the QAL bank cell, input an ideal 2 ps edge.  Level time = time to 90%
    of its own rail, worst of RISE (pMOS-limited) and FALL (nMOS-limited).

    This is the committed floor-curve 'zc' form (qal/dvopt/floor_inv_c*.cir): the
    2 fF / 1.2 V case is that deck's own per-deck instrument check, committed at
    57.1429 / 57.1432 ps, and it is carried here for exactly that purpose.

    The deck is DC-biased throughout, so it does not hit the committed A2
    convergence trap (an all-zero initial state will not converge).
    """
    L = head(dvtn, dvtp)
    meas = []
    for vdd in (1.2, 1.5):
        vt = ("%g" % vdd).replace(".", "p")
        L.append("VS%s s%s 0 %g" % (vt, vt, vdd))
        for cl in cl_list:
            ct = ("%g" % cl).replace(".", "p")
            for edge in ("r", "f"):
                n = "%s%s%s" % (vt, ct, edge)
                if edge == "r":     # input falls -> output RISES through the pMOS
                    L.append("VI%s i%s 0 PWL(0 %g 100p %g 102p 0)" % (n, n, vdd, vdd))
                else:               # input rises -> output FALLS through the nMOS
                    L.append("VI%s i%s 0 PWL(0 0 100p 0 102p %g)" % (n, n, vdd))
                L += ["XP%s o%s i%s s%s s%s sg13_lv_pmos w=%gu l=%gu"
                      % (n, n, n, vt, vt, WP, LCH),
                      "XN%s o%s i%s 0 0 sg13_lv_nmos w=%gu l=%gu" % (n, n, n, WN, LCH),
                      "CL%s o%s 0 %gf" % (n, n, cl)]
                if edge == "r":
                    for f, fn in ((0.5, "T50"), (0.9, "T90"), (0.95, "T95")):
                        meas.append(".measure tran %s%s WHEN V(o%s)=%.9g RISE=1"
                                    % (fn, n, n, f * vdd))
                else:
                    for f, fn in ((0.5, "T50"), (0.1, "T90"), (0.05, "T95")):
                        meas.append(".measure tran %s%s WHEN V(o%s)=%.9g FALL=1"
                                    % (fn, n, n, f * vdd))
    L.append(".tran 0.02p 1600p 0 0.1p")
    L += meas
    pr = [x.split()[-1].split("=")[0] for x in []]
    nodes = [ln.split()[1] for ln in L if ln.startswith("CL")]
    for k in range(0, len(nodes), 8):
        L.append((".print tran " if k == 0 else "+ ") +
                 " ".join("V(%s)" % n for n in nodes[k:k + 8]))
    L.append(".end")
    return L


def parse_mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d


def cmos_extract(path):
    d = parse_mt0(path + ".mt0")
    out = {}
    for vdd in (1.2, 1.5):
        vt = ("%g" % vdd).replace(".", "p")
        for cl in (6.91, 2.0):
            ct = ("%g" % cl).replace(".", "p")
            r = d.get(("T90%s%sR" % (vt, ct)).upper())
            f = d.get(("T90%s%sF" % (vt, ct)).upper())
            r50 = d.get(("T50%s%sR" % (vt, ct)).upper())
            f50 = d.get(("T50%s%sF" % (vt, ct)).upper())
            key = "vdd%s_cl%s" % (vt, ct)
            sh = lambda x: None if x is None else (x * 1e12) - 100.0
            r, f, r50, f50 = sh(r), sh(f), sh(r50), sh(f50)
            out[key] = dict(t90_rise_ps=r, t90_fall_ps=f,
                            t50_rise_ps=r50, t50_fall_ps=f50,
                            t90_worst_ps=(max(x for x in (r, f) if x is not None)
                                          if (r is not None or f is not None) else None))
    return out


# ==================================================================== hop path
def hop_point(tag, L_nH, W_um, dv, cl, dvtn, dvtp, kind="inv", tail=500.0):
    """QAL bank hop through the sk.py path, with the DELVTO shim."""
    sys.path.insert(0, "/usr/local/src/stat-sim/qal/skept")
    import sk
    sk.HERE = HERE
    sk.ENV = ENV
    sk.SHIM = SHIM
    sk.VGH = max(1.5, dv)
    _n, _p = dvtn, dvtp

    def _head():
        return ['.hdl "%s"' % sk.VA, '.include "%s"' % sk.MODEL,
                '.include "%s"' % sk.SHIM,
                ".param DVTN=%.10g DVTP=%.10g" % (_n, _p),
                '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    sk.head = _head

    t0 = time.monotonic()
    lp, msg = sk.run("p_%s.cir" % tag, sk.probe(L_nH, W_um, dv, kind=kind, cl=cl))
    if lp is None:
        return dict(tag=tag, error=msg)
    tz, ipk, tipk = sk.zero_of(lp + ".prn")
    if tz is None:
        return dict(tag=tag, error="no current zero after the peak")
    lines, meta = sk.hop(L_nH, W_um, dv, tz - sk.T0, tail=tail, kind=kind, cl=cl)
    hp, msg = sk.run("h_%s.cir" % tag, lines, timeout=1800)
    if hp is None:
        return dict(tag=tag, error=msg)
    r = sk.extract_hop(hp + ".prn", meta, L_nH, W_um, dv)
    r.update(tag=tag, cell_kind=kind, cl_fF=cl, dvtn=dvtn, dvtp=dvtp,
             VGH=sk.VGH, probe_Ipk_uA=ipk, tail_ps=tail,
             wall_s=round(time.monotonic() - t0, 1))
    # ---- Q3: the HELD-RAIL DROOP, read off this very row.  After t_open the
    # transfer switch is open and the park grounds the inductor node, so V(bkb)
    # from t_open onward IS the passively held bank rail.
    w = sk.W(hp + ".prn")
    to = meta["t_open"]
    hold = {}
    for dt in (50.0, 105.0, 120.0, 200.0, 300.0, 400.0):
        if to + dt <= meta["tend"]:
            hold["hold_%dps_V" % int(dt)] = w.at("V(bkb)", to + dt)
            hold["droop_%dps_mV" % int(dt)] = 1e3 * (w.at("V(bkb)", to + dt) - r["VBOPEN"])
    r["held_rail"] = hold
    r["s_end_min"] = min(r["s_end"].values())
    # ---- per-gate output voltages at the end, for the separation metric
    json.dump(r, open(os.path.join(HERE, "row_%s.json" % tag), "w"), indent=1)
    return r


# ============================================ Q3: bank hold current + droop
HOLD_RAIL = RAIL_L4            # 0.754572966 V, the L=4 real-load delivered rail


def hold_deck(dvtn, dvtp, cl=6.91, rail=HOLD_RAIL, dv=1.65, vgh=1.65,
              cbank=35.979, tend=500.0):
    """Q3 as PRE-REGISTERED: the passive hold of a hop-charged bank.

    TWO electrically isolated copies of the same object in one deck:

      A (DC leg)  the 8-cell bank + its transfer switch HELD OPEN + the park,
                  rail pinned by an IDEAL source through per-branch ammeters.
                  I(VRAIL) is the bank's STATIC HOLD CURRENT -- capacitance-free,
                  so the droop it implies can be quoted against the COMMITTED
                  measured bank capacitance (CA = 35.979 fF) instead of against
                  whatever capacitance this shim happens to leave on the node.
                  Split three ways so the source of the current is attributable:
                  VRAIL total, VSWP the transfer pMOS's bulk leg (vhi -> bank),
                  and the cells by difference.
      B (float)   the same bank on a FLOATING rail with the committed 35.979 fF
                  lumped bank capacitance, rail .ic'd to the delivered level and
                  every switch open -- the direct transient the pre-registration
                  asked for.  Outputs are .ic'd to their settled values so the
                  measured decay is HOLD, not residual settling.  (Reading the
                  hold off a hop row's tail does NOT work: there the rail is still
                  giving up 167 mV to the cell loads, which is settling, not leak.)

    Both legs carry the transfer switch because a real held bank has one, and a
    low-|Vtp| transfer pMOS leaking from the 1.65 V gate-drive rail INTO the bank
    is a genuine cost of the cure, not an artefact.
    """
    hi = [i for i in range(MGATE) if i % 2 == 0]
    L = head(dvtn, dvtp) + ["VHI vhi 0 %g" % vgh, "VGT gt 0 0",
                            "VGTP gtp 0 %g" % vgh, "VPK pk 0 %g" % vgh]
    # ---- leg A: rail pinned by an ideal source, current metered
    L += ["VRAIL ra 0 %.9g" % rail, "VSWP swp ra 0", "VGNA gna 0 0"]
    for i in range(MGATE):
        L += ["VIA%d ina%d 0 %g" % (i, i, dv if i in hi else 0.0),
              "XPA%d oa%d ina%d ra ra sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH),
              "XNA%d oa%d ina%d gna gna sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH),
              "CLA%d oa%d gna %gf" % (i, i, cl)]
    L += ["XSWNA swa gt ra 0 sg13_lv_nmos w=10u l=%gu" % LCH,
          "XSWPA swa gtp swp vhi sg13_lv_pmos w=20u l=%gu" % LCH,
          "XPKA swa pk 0 0 sg13_lv_nmos w=2u l=%gu" % LCH]
    # ---- leg B: floating rail + the committed lumped bank capacitance
    L += ["CBK rb 0 %gf" % cbank, "VGNB gnb 0 0"]
    for i in range(MGATE):
        L += ["VIB%d inb%d 0 %g" % (i, i, dv if i in hi else 0.0),
              "XPB%d ob%d inb%d rb rb sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH),
              "XNB%d ob%d inb%d gnb gnb sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH),
              "CLB%d ob%d gnb %gf" % (i, i, cl)]
    L += ["XSWNB swb gt rb 0 sg13_lv_nmos w=10u l=%gu" % LCH,
          "XSWPB swb gtp rb vhi sg13_lv_pmos w=20u l=%gu" % LCH,
          "XPKB swb pk 0 0 sg13_lv_nmos w=2u l=%gu" % LCH]
    ic = ["V(rb)=%.9g" % rail] + \
         ["V(ob%d)=%.9g" % (i, 0.0 if i in hi else rail) for i in range(MGATE)]
    L.append(".ic " + " ".join(ic))
    L.append(".tran 0.05p %gp 0 0.2p" % tend)
    for t in (0.5, 50.0, 105.0, 120.0, 200.0, 300.0, 400.0, tend - 5.0):
        L.append(".measure tran VB%d FIND V(rb) AT=%.6fp" % (int(t * 10), t))
    L += [".measure tran IRAIL FIND I(VRAIL) AT=%.6fp" % (tend - 5.0),
          ".measure tran ISWP FIND I(VSWP) AT=%.6fp" % (tend - 5.0)]
    L.append(".print tran V(rb) I(VRAIL) I(VSWP) V(ob0) V(ob1)")
    L.append(".end")
    return L


def hold_extract(path, rail=HOLD_RAIL, cbank=35.979):
    d = parse_mt0(path + ".mt0")
    out = dict(rail_V=rail, cbank_fF=cbank)
    out["I_hold_total_A"] = d.get("IRAIL")
    out["I_swpmos_A"] = d.get("ISWP")
    if out["I_hold_total_A"] is not None:
        out["I_cells_A"] = -out["I_hold_total_A"] - (out["I_swpmos_A"] or 0.0)
        # droop implied by the static current against the COMMITTED bank C
        for T in (105.0, 120.0, 200.0, 300.0):
            out["droop_DC_%dps_mV" % int(T)] = \
                -1e3 * (-out["I_hold_total_A"]) * (T * 1e-12) / (cbank * 1e-15)
    v0 = d.get("VB5")
    for t in (50.0, 105.0, 120.0, 200.0, 300.0, 400.0):
        v = d.get("VB%d" % int(t * 10))
        out["float_%dps_V" % int(t)] = v
        if v is not None and v0 is not None:
            out["float_droop_%dps_mV" % int(t)] = 1e3 * (v - v0)
    return out
