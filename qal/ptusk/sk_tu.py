#!/usr/bin/env python3
"""THE SUSTAINED STAGE-SKIP QAL CHAIN: skip schedule + TOP-UP ON THE HELD BANKS.

REUSED VERBATIM, by import, from qal/skip4/skip.py (whose instrument check is
digit-clean against the committed robust point): widths(), is_hi(), in_net(),
bank_cells(), transfer_switch(), phases(), integ(), head_lines(), supply_tg(),
schedule(), parse_mt0(), read_prn(), zero_after_peak(), trace(), at().
That file is NOT modified and NOT written to.

REUSED VERBATIM, in form, from qal/qal_pulse_topup.py (committed): the
pulsed-inductor top-up -- high-side pMOS + synchronous freewheel nMOS + Ltu,
buck action, and its gate-drive metering B-source.

WHAT IS NEW HERE AND NOWHERE ELSE:
  1. scheme "s4": the 4-bank topology the ask names -- TWO transfer paths, 1->3
     and 2->4, banks 1 and 2 are the power-chain heads.
  2. mode "ptu": a PULSED-INDUCTOR TOP-UP on every HOP-CHARGED bank, fired at
     the START of that bank's hold (after its own charging hop's MEASURED zero).
  3. the delivered input HIGH measured AT EVERY STAGE against the 0.4400 V gate.
  4. the top-up's own SWITCH GATE DRIVE metered on its own integrator -- the
     recursion trap, counted.

Pre-registration: PRE_REGISTERED.json (written before this file existed).
"""
import json, math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK                      # the validated harness, imported not copied

XYCE  = SK.XYCE
CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_skiptu"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

VGH, MGATE, EDGE, LAG_PS = SK.VGH, SK.MGATE, SK.EDGE, SK.LAG_PS
TZ_ANCHOR = SK.TZ_ANCHOR
RSTU = 10.0        # ohm, top-up inductor series resistance (same as the hop's RS_REF)

# the 4-bank schedule the ask names, added to the inherited pair.
SK.SCHED["s4"] = dict(nbank=4, hops=[(1, 3), (2, 4)], heads=[1, 2])
SK.SCHED["s5"] = dict(nbank=5, hops=[(1, 3), (2, 4), (3, 5)], heads=[1, 2])


# ------------------------------------------------------- the top-up itself
def topup_dev(k, ltu_nh, wsw, t_fire, t_on, vsup, tfw, big=None):
    """PULSED-INDUCTOR TOP-UP on bank k's rail -- buck action, ISOLATED.

      tsup --[HS pMOS XTUSW]-- na_k --[Ltu]--[Rtu]-- nb_k --[OUT tg switch]-- rail_k
                                 |
                          [LS nMOS XTUFW]  (freewheel during decay, PARK when idle)
                                 |
                                gnd

    Why the OUT switch exists (AMENDMENT A1b, MEASURED): without it the inductor is
    permanently tied to rail_k, so pinning na to ground between pulses drains the bank
    straight through the inductor (rail -> Ltu -> LS -> gnd), and the measured
    "top-up" delivered NEGATIVE charge.  The committed transfer hop has exactly this
    shape -- a tg-class switch between the inductor and the rail plus a park on the
    inductor island -- and the record's shared-inductor sigma0 architecture needs such
    switches anyway to share one inductor across banks.  Inherited form, not a new
    invention.

    Buck action: the supply sources current only during t_on while the bank receives
    current during t_on AND the freewheel, so Q_sup = D*Q_bank with D = V_rail/V_sup
    and the supply pays the bank's OWN voltage, not the supply's.  That is why this is
    used instead of a flying cap (which dissipates (V_sup - V_rail)*dQ regardless of
    switch quality).

    FOUR DRIVEN GATES per topped bank (HS pMOS, LS nMOS, and the OUT switch's nMOS and
    pMOS).  Every one is a real PWL source whose energy is metered.
    """
    e = EDGE
    a, b = t_fire, t_fire + t_on          # high-side conduction window
    probe_form = tfw is None
    z = (big if probe_form else b + tfw)  # the inductor's MEASURED current zero
    w = SK.widths(wsw * 1.5)              # tg-class sizing via the committed helper
    L = [
        "XTUSW%d na%d gtu%d tsup tsup sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, wsw),
        "XTUFW%d na%d gfw%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, wsw),
        "LTU%d na%d ntm%d %gn" % (k, k, k, ltu_nh),
        "RTU%d ntm%d nb%d %g" % (k, k, k, RSTU),
        # 0 V series source: the ONLY honest place to meter what the top-up actually
        # puts INTO the bank.  Metering I(LTU) instead counts current that merely
        # sloshes between na and nb's parasitics while the OUT switch is OPEN and the
        # inductor branch is isolated from the rail -- charge that never reaches the
        # bank at all.
        "VMTU%d nb%d nbx%d 0" % (k, k, k),
        "XTUON%d nbx%d gto%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
        % (k, k, k, k, w["wn"]),
        "XTUOP%d nbx%d gtop%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
        % (k, k, k, k, w["wp"]),
        # HS gate: idles HIGH (off), pulses LOW across [a, b]
        "VGTU%d gtu%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
        % (k, k, VGH, a - e, VGH, a, b, b + e, VGH),
        # LS gate: HIGH (park) -> LOW exactly as the HS comes ON -> HIGH again for
        # the freewheel and then the park.
        #
        # na MUST NEVER FLOAT, and this is MEASURED, not a precaution.  With the park
        # released 8 ps early (an intentional "dead time"), na became a floating node
        # with almost no capacitance of its own, and the park gate's own falling edge
        # capacitively kicked it to -0.33 V -- which pre-charged the inductor with
        # ~700 uA of REVERSE current before the pulse began.  The current was exactly
        # 0.0 uA until the instant the park released and -577 uA 3 ps later.
        # A real buck tolerates dead time because its inductor current is continuous
        # and a body diode conducts; here the current starts at zero, so there is
        # nothing to hold the node and the gate coupling wins.  So: make-before-break.
        # na hands off directly from ground to the supply, and the brief HS/LS overlap
        # is real shoot-through that is METERED in q_from_supply.
        "VGFW%d gfw%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
        % (k, k, VGH, a - e, VGH, a, b, b + e, VGH),
    ]
    # OUT switch closes SIMULTANEOUSLY with the high side, never before it.
    # MEASURED reason: with OUT closed and the high side still off, the RAIL drives
    # the inductor backwards.  A 2 ps lead at 0.68 V across 5 nH builds
    # 0.68/5e-9*2e-12 = 272 uA of REVERSE current, and the data showed -268 uA --
    # a reverse current the pulse then spends its whole on-time undoing.  The
    # inductor must be energized by the SUPPLY only.
    if probe_form:
        L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)"
              % (k, k, a - e, a, VGH, z, VGH),
              "VGTOP%d gtop%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
              % (k, k, VGH, a - e, VGH, a, z)]  # probe: never opens
    else:
        L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (k, k, a - e, a, VGH, z, VGH, z + e),
              "VGTOP%d gtop%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (k, k, VGH, a - e, VGH, a, z, z + e, VGH)]
    return L, (None if probe_form else tfw)


def topup_integrators(banks):
    """Per-bank delivered charge and energy, plus the ONE thing that decides the
    cost question: the top-up switches' own GATE DRIVE."""
    L, tags = [], []
    for k in banks:
        for nm, ex in (("qtu%d" % k, "I(VMTU%d)" % k),
                       ("etu%d" % k, "V(rail%d)*I(VMTU%d)" % (k, k)),
                       ("qind%d" % k, "I(LTU%d)" % k)):
            L += SK.integ(nm, ex); tags.append(nm)
    L += SK.integ("qsup", "-I(VTSUP)"); tags.append("qsup")
    # THE RECURSION TRAP, counted in full: THREE driven gates per topped bank --
    # the high-side pMOS, the freewheel nMOS, and the park nMOS that pins the
    # inductor island.  None of this drive is recovered.
    L += SK.integ("egtu", "-" + "-".join(
        "V(gtu%d)*I(VGTU%d)-V(gfw%d)*I(VGFW%d)-V(gto%d)*I(VGTO%d)"
        "-V(gtop%d)*I(VGTOP%d)" % (k, k, k, k, k, k, k, k) for k in banks))
    tags.append("egtu")
    # THE GATE CHARGE, which is what a REAL driver actually costs.
    # An IDEAL PWL voltage source RECLAIMS the discharge energy, so the net energy
    # integral above tends toward zero and would flatter the top-up enormously.  A
    # real driver (a CMOS inverter) dissipates Q_gate*VGH per full switching cycle:
    # CV^2/2 in the pull-up charging the gate, CV^2/2 in the pull-down dumping it.
    # So integrate |I| on every gate source; total charge moved per cycle is
    # 2*Q_gate, and E_real_driver = Q_gate*VGH.  MEASURED, not assumed from a Cox.
    L += SK.integ("qgabs", "+".join(
        "abs(I(VGTU%d))+abs(I(VGFW%d))+abs(I(VGTO%d))+abs(I(VGTOP%d))"
        % (k, k, k, k) for k in banks))
    tags.append("qgabs")
    return L, tags


# ------------------------------------------------------------------- the deck
def topup_dev_off(k, ltu_nh, wsw):
    """The top-up cell for bank k, PERMANENTLY OFF (parked): HS pMOS off, LS nMOS
    on (pinning the inductor island at 0), OUT switch open.  Devices present, so
    the OUT switch's drain capacitance loads rail_k -- which is the whole point of
    AMENDMENT A8 and is what the committed ptu probe path omitted."""
    w = SK.widths(wsw * 1.5)
    return [
        "CNAX%d na%d 0 %gf" % (k, k, CNA_OFF_FF),
        "XTUSW%d na%d gtu%d tsup tsup sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, wsw),
        "XTUFW%d na%d gfw%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, wsw),
        "LTU%d na%d ntm%d %gn" % (k, k, k, ltu_nh),
        "RTU%d ntm%d nb%d %g" % (k, k, k, RSTU),
        "VMTU%d nb%d nbx%d 0" % (k, k, k),
        "XTUON%d nbx%d gto%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
        % (k, k, k, k, w["wn"]),
        "XTUOP%d nbx%d gtop%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
        % (k, k, k, k, w["wp"]),
        "VGTU%d gtu%d 0 %g" % (k, k, VGH),   # HS pMOS OFF
        "VGFW%d gfw%d 0 %g" % (k, k, VGH),   # LS nMOS ON  -> na parked at 0
        "VGTO%d gto%d 0 0" % (k, k),         # OUT nMOS OFF
        "VGTOP%d gtop%d 0 %g" % (k, k, VGH), # OUT pMOS OFF
    ]


CNA_OFF_FF = 8.0


def deck(scheme, mode, T, total_um, l_nh, dv, tz=None, probe=None,
         ltu_nh=5.0, wsw=10.0, t_on=12.0, fire_off=0.0, rs=SK.RS_REF,
         tfw=None, tu_probe=None):
    """tfw: {bank: MEASURED freewheel ps}.  tu_probe=k -> build the top-up ZCS probe
    for bank k (its freewheel never opens, and only bank k is topped up)."""
    """mode 'free'  -> no top-up anywhere (MY OWN CONTROL)
       mode 'ptu'   -> pulsed-inductor top-up on every HOP-CHARGED bank
       mode 'ptulate' -> same, fired just BEFORE the stage boundary: the
                         deliberate negative control that reproduces chain3's
                         measured 'moves the goalpost' artifact.
    """
    S = SK.schedule(scheme, T, dv, tz)
    nb, nh = S["nbank"], len(S["hops"])
    big = S["tend"] * 4.0
    L = SK.head_lines() + [".param LT=%gn RS=%g" % (l_nh, rs),
                           "VHI vhi 0 %g" % VGH, "VDV vdv 0 %g" % dv]
    topped = [k for k in range(1, nb + 1) if k in S["c"]] if mode.startswith("ptu") else []
    # mode "rtu": chain3's RESISTIVE top-up, its device and window placement VERBATIM
    # (a tg15p-sized transmission gate to the ideal dV node, conducting for a window at
    # the START of the bank's hold so the rail is restored first and the cells then
    # settle against a restored rail -- chain3's own A5 lesson).  This is NOT the
    # architecture's preferred charge-multiplying form; it is the BOUNDING form.  It
    # restores the rail as hard as a supply can, so if the chain still cannot reach 90%
    # with it, no top-up of any efficiency can rescue the schedule, and the answer stops
    # depending on whether my pulsed-inductor buck works.
    rtopped = [k for k in range(1, nb + 1) if k in S["c"]] if mode == "rtu" else []
    if topped:
        L.append("VTSUP tsup 0 %g" % dv)        # top-up's OWN supply node
    for k in range(1, nb + 1):
        L += SK.bank_cells(k, dv, ())
    for k in range(1, nb + 1):
        if k in S["heads"]:
            L += SK.supply_tg(k, total_um, (0.0, S["head_cut"][k]), "head")
        elif k in rtopped:
            hop = [h for h, (ss, tt) in enumerate(S["hops"], 1) if tt == k][0]
            t0 = S["open"][hop - 1] + EDGE          # start of this bank's hold
            if probe is not None and hop >= probe:
                # In a PROBE deck the hop under test never opens, so firing its
                # destination's top-up would clamp the very rail whose zero is being
                # measured.  The DEVICES are still instantiated (permanently off)
                # because their drain capacitance loads the rail and shifts the LC
                # resonance -- which is exactly why the zeros must be probed in the
                # row's own mode rather than reused from the free-running probe.
                L += SK.supply_tg(k, total_um, None, "topup")
            else:
                L += SK.supply_tg(k, total_um, (t0, t0 + t_on), "topup")
        else:
            L += SK.supply_tg(k, total_um, None, None)
    for h, (s, t) in enumerate(S["hops"], 1):
        L += ["L%d a%d mid%d {LT}" % (h, h, h), "R%d mid%d sw%d {RS}" % (h, h, h)]
        L += SK.transfer_switch(h, s, t, total_um)
    for h in range(1, nh + 1):
        tc, to = S["close"][h - 1], S["open"][h - 1]
        if probe is None or h < probe:
            L += SK.phases(h, tc, to, big)
        elif h == probe:
            L += SK.phases(h, tc, None, big)
        else:
            L += SK.phases(h, None, None, big)
    # ---- the top-up, fired at the START of each topped bank's hold
    fires = {}
    if topped:
        for k in topped:
            hop = [h for h, (s, t) in enumerate(S["hops"], 1) if t == k][0]
            # In a PROBE deck, only banks whose charging hop is already CUT can be
            # topped up: the hop under probe never opens, so a top-up on its
            # destination would clamp the very transfer whose zero we are measuring.
            if probe is not None and hop >= probe:
                # A8 FIX (SKEPTIC): do NOT drop the devices.  Instantiate them in
                # the PARKED state (HS off, LS on, OUT open) so the OUT switch's
                # drain capacitance loads rail_k exactly as it does in the row.
                L += topup_dev_off(k, ltu_nh, wsw)
                continue
            if tu_probe is not None and k != tu_probe:
                L += topup_dev_off(k, ltu_nh, wsw)
                continue          # the top-up ZCS probe tops up ONE bank only
            t_open = S["open"][hop - 1]          # this bank's charging hop's zero
            if mode == "ptulate":
                tf = S["bound"][k] - t_on - 4.0  # deliberately against chain3's A5
            else:
                # The pulse AND its preparation must sit outside the charging hop.
                # The prep (park-off at tf-4*EDGE, OUT-close at tf-2*EDGE) is the
                # binding constraint, not the pulse: MEASURED, a prep that lands
                # inside the hop turns the top-up inductor into a second drain path
                # on the rail while the hop is still delivering.  The hop's own
                # switch is fully open at t_open+EDGE and its park is on by
                # t_open+2*EDGE, so the sequence starts at t_open+6*EDGE.
                tf = t_open + 6 * EDGE + fire_off
            tfw_k = None if (tu_probe == k) else (tfw or {}).get(k)
            if tfw_k is None and tu_probe != k:
                raise ValueError("no MEASURED tfw for bank %d (A1 forbids assuming it)" % k)
            dev, tfw_used = topup_dev(k, ltu_nh, wsw, tf, t_on, dv, tfw_k, big=big)
            L += dev
            fires[k] = dict(t_fire=tf, t_on=t_on, tfw=tfw_used, hop=hop, t_open=t_open,
                            bound=S["bound"][k],
                            tfw_source=("PROBE (never cuts)" if tfw_used is None
                                        else "MEASURED"))
    tend = S["tend"] if probe is None else (S["close"][probe - 1] + 1.8 * S["t_est"])
    tags = []
    if probe is None:
        ig, tags = SK.hop_integrators(S, rs, False)
        L += ig
        if rtopped:
            # the resistive top-up draws from the SAME ideal dV node as the head
            # pre-charge gates, so qdv already contains it; add the per-bank gate drive
            # so its recursion-trap cost is counted the same way.
            L += SK.integ("ergt", "-" + "-".join(
                "V(tun%d)*I(VTUN%d)-V(tup%d)*I(VTUP%d)" % (k, k, k, k) for k in rtopped))
            tags.append("ergt")
            L += SK.integ("qrga", "+".join(
                "abs(I(VTUN%d))+abs(I(VTUP%d))" % (k, k) for k in rtopped))
            tags.append("qrga")
        if fires:
            ig2, tg2 = topup_integrators(sorted(fires))
            L += ig2; tags += tg2
    ic = " ".join("V(rail%d)=%g" % (k, dv if k in S["heads"] else 0.0)
                  for k in range(1, nb + 1))
    L.append(".ic " + ic + " " + " ".join("V(a%d)=0" % h for h in range(1, nh + 1)))
    if fires:
        L[-1] += " " + " ".join("V(na%d)=0 V(nb%d)=0 V(nbx%d)=0" % (k, k, k)
                                for k in sorted(fires))
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"]))
    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)] + [("B%d" % h, S["open"][h - 1]) for h in range(1, nh + 1)] \
              + [("K%d" % k, S["bound"][k]) for k in range(1, nb + 1)] \
              + [("D", tend - 5.0)]
        for tg in tags:
            for nm, tt in cks:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        for nm, tt in cks:
            for k in range(1, nb + 1):
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
        for k in range(1, nb + 1):
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, SK.T1, tend))
            L.append(".measure tran VR%dMN MIN V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, S["bound"][k] - 1.0, S["bound"][k] + 1.0))
            for i in range(MGATE):
                L.append(".measure tran O%d_%dS FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(S["bound"][k])))
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tend - 5.0)))
        # THE HEADLINE MEASURE: the delivered INPUT of every stage, read at THAT
        # stage's own boundary.  For k>=2 the input net IS the predecessor's output.
        for k in range(2, nb + 1):
            for i in range(MGATE):
                L.append(".measure tran G%d_%d FIND V(%s) AT=%.6fp"
                         % (k, i, SK.in_net(k, i), g(S["bound"][k])))
        for h in range(1, nh + 1):
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp"
                     % (h, h, g(S["open"][h - 1])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                     % (h, h, SK.T1, tend))
        for k in sorted(fires):
            L.append(".measure tran ITU%dPK MAX I(LTU%d) FROM=%gp TO=%gp"
                     % (k, k, SK.T1, tend))
        pr = ["V(rail%d)" % k for k in range(1, nb + 1)] + \
             ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(o%d_%d)" % (k, i) for k in range(1, nb + 1) for i in range(MGATE)] + \
             ["V(sw%d)" % h for h in range(1, nh + 1)] + \
             ["V(a%d)" % h for h in range(1, nh + 1)] + \
             ["I(LTU%d)" % k for k in sorted(fires)] + \
             ["V(na%d)" % k for k in sorted(fires)] + \
             ["V(nb%d)" % k for k in sorted(fires)]
    else:
        pr = ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(rail%d)" % k for k in range(1, nb + 1)] + \
             ["V(sw%d)" % h for h in range(1, nh + 1)] + \
             ["V(a%d)" % h for h in range(1, nh + 1)]
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S, fires


def run(fn, lines, timeout=900):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout
    wall = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-300:])
    return path, "ran %s in %.1fs" % (fn, wall)


# ------------------------------------------------------- true-ZCS probe chain
def probe_zeros(scheme, T, total_um, l_nh, dv, tag, mode="free", **kw):
    """RE-PROBE the true current zero PER HOP separately, never the analytic
    pi*sqrt(LC) (measured 33% early).  Hop h is probed with hops 1..h-1 cut at
    their already-measured zeros and later hops idle."""
    nh = len(SK.SCHED[scheme]["hops"])
    tz = []
    for h in range(1, nh + 1):
        lines, S, _ = deck(scheme, mode, T, total_um, l_nh, dv,
                           tz=tz + [TZ_ANCHOR * SK.CHAIN_F] * (nh - len(tz)),
                           probe=h, **kw)
        p, msg = run("p%d_%s.cir" % (h, tag), lines)
        print("   probe hop%d: %s" % (h, msg), flush=True)
        if p is None:
            return None
        hdr, rows = SK.read_prn(p + ".prn")
        z, pk = SK.zero_after_peak(hdr, rows, "I(L%d)" % h, S["close"][h - 1])
        if z is None:
            return None
        tz.append(z - S["close"][h - 1])
        print("      t_zcs = %.3f ps (Ipk %.2f uA)" % (tz[-1], pk * 1e6), flush=True)
    return tz


def topup_zero(hdr, rows, col, t_fire, t_on, t_max):
    """The top-up pulse's OWN current zero: the first downward zero crossing after
    the POSITIVE peak that the high-side pulse creates.

    A plain max-|I| search is WRONG here and it cost two iterations: in the probe form
    the freewheel never cuts, so the rail keeps draining to ground through the
    inductor long after the pulse and the largest |I| in the record is that late
    NEGATIVE excursion, not the pulse.  Search the pulse's own window only."""
    ic = hdr.index(col)
    pk, tpk = 0.0, None
    for r in rows:
        t = r[1] * 1e12
        if t < t_fire or t > t_max:
            continue
        if r[ic] > pk:
            pk, tpk = r[ic], t
    if tpk is None or pk <= 0:
        return None, pk, tpk
    prev = None
    for r in rows:
        t = r[1] * 1e12
        if t <= tpk:
            prev = (t, r[ic]); continue
        if t > t_max:
            break
        if prev is not None and r[ic] <= 0.0 < prev[1]:
            t0, v0 = prev; t1, v1 = t, r[ic]
            tz = t0 if v1 == v0 else t0 + (0.0 - v0) * (t1 - t0) / (v1 - v0)
            return tz, pk, tpk
        prev = (t, r[ic])
    return None, pk, tpk


def probe_topup_zeros(scheme, T, total_um, l_nh, dv, tag, tz, ltu_nh, wsw, t_on,
                      fire_off=0.0, banks=None):
    """AMENDMENT A1: MEASURE each top-up inductor's own true current zero, by the
    same probe-then-cut rule the transfer hops use.  The freewheel closes and never
    opens; the first zero of I(LTU_k) after its peak IS the instant to cut.

    Measured PER BANK, because the two topped banks sit at different rails.
    """
    S = SK.schedule(scheme, T, dv, tz)
    banks = banks or [k for k in range(1, S["nbank"] + 1) if k in S["c"]]
    out = {}
    for k in banks:
        lines, S2, fires = deck(scheme, "ptu", T, total_um, l_nh, dv, tz=tz,
                                ltu_nh=ltu_nh, wsw=wsw, t_on=t_on,
                                fire_off=fire_off, tu_probe=k)
        p, msg = run("q%d_%s.cir" % (k, tag), lines)
        if p is None:
            print("   tu-probe bank%d: %s" % (k, msg), flush=True)
            return None
        hdr, rows = SK.read_prn(p + ".prn")
        tf = fires[k]["t_fire"]
        # Search the WHOLE remaining record, not a resonance-scaled guess.  A
        # resonance-scaled window wrongly reported "no zero" for the
        # resistance-dominated combinations, where the current peaks tens of ps AFTER
        # the high side has already shut off and decays on an RL/RC timescale rather
        # than a resonant one.  If there is genuinely no zero, that is a FINDING about
        # the mechanism (no ZCS is available at that setting) and it is reported as
        # such, not hidden by a too-narrow window.
        t_max = max(r[1] * 1e12 for r in rows)
        z, pk, tpk = topup_zero(hdr, rows, "I(LTU%d)" % k, tf, t_on, t_max)
        if z is None:
            print("   tu-probe bank%d: NO ZCS ANYWHERE in [%.1f, %.1f] ps "
                  "(peak %.1f uA at %s) -- resistance-dominated, no zero to cut at"
                  % (k, tf, t_max, pk * 1e6, tpk), flush=True)
            return None
        # how long after the high side shut off did the current peak?  A peak well
        # after t_on means the inductor is NOT setting the dynamics -- the path is
        # resistance-dominated and the buck's charge multiplication is largely absent.
        print("      (peak %.1f uA at %.2f ps = %.1f ps after the pulse ended)"
              % (pk * 1e6, tpk, tpk - (tf + t_on)), flush=True)
        tfw = z - (tf + t_on)
        if tfw <= 0:
            # the current already reversed before the high side even opened: the
            # pulse is longer than the resonance.  Record it and clamp to the zero.
            print("   tu-probe bank%d: zero INSIDE t_on (tfw=%.3f) -> clamp 0"
                  % (k, tfw), flush=True)
            tfw = 0.0
        out[k] = tfw
        print("   tu-probe bank%d: I(LTU) zero at %.3f ps -> tfw %.3f ps (Ipk %.1f uA)"
              % (k, z, tfw, pk * 1e6), flush=True)
    return out
