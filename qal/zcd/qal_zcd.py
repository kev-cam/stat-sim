#!/usr/bin/env python3
"""TRACK 3: a REAL zero-current detector for the QAL bank hop, SG13G2/PSP103 at T0.

The ZCD senses the inductor-current zero across the EXISTING 10-ohm series
resistor RT (mid-sw): differential = I(LT)*10 ohm (peak 1.95 mV, slope
-20.7 uV/ps at the zero, MEASURED from gateb/gb_hop.cir.prn). Common mode at
the crossing is 0.578 V, so the input pair is pMOS on the 1.2 V logic rail.

Topology: armed (per-hop) two-stage continuous-time comparator --
  stage 1: pMOS diff pair, nMOS diode load + partial cross-coupled pair
           (regenerative boost, clamped by the diodes), armed by a pMOS tail
           switch; nMOS equalizer across the outputs when disarmed.
  stage 2: pMOS diff pair with nMOS current-mirror load -> single-ended zy;
           idle keeper holds zy high when disarmed.
  output : CMOS inverter -> zout (idle LOW, fires HIGH), 2 fF load.
Energy is metered by the campaign's 1F-cap integrator technique (never
'.measure INTEGRAL'), on the 1.2 V rail and on the arm drivers separately.

Stages:
  wave           extract inp/inn PWL replay tables from gateb/gb_hop.cir.prn
  sa <vos_mV>    standalone comparator, measured-waveform replay + offset
  hop <vos_mV>   full committed hop deck (gateb topology) + comparator on mid/sw
  hopall         hop variant, all-8-inputs-high pattern (shifted t_zcs: tracking)
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
GATEB = "/usr/local/src/stat-sim/qal/gateb"
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_zcd"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# committed hop plant (gateb/qal_hop_meter.py, instrument-checked)
DV, L_NH, RS = 1.0, 277.8, 10.0
WSW, VGH     = 20.0, 1.5
WP, WN       = 1.12, 0.74
MGATE, CLOAD = 8, 2.0
CA_FF        = 35.979
T0           = 50.0
T_HALF       = 342.0          # committed switch-open interval (opens at 392 ps)

# ---- comparator design (iterated; final values are what RESULTS.json reports)
# v3: STREAMING reframe -- QAL banks hop every beat, so stage 1 is ALWAYS
# biased (arming it from discharged nodes needs ~350 ps of slew, misses the
# zero); nMOS source-followers CLAMP/park the zx nodes at the ~0.6 V
# operating point (classic clamped differential pair) so the pair only moves
# them by mV; stage 2 + output are armed per hop; zy1 is pinned to 0 when
# disarmed (v2 bug: it floated to 0.72 V and the keeper burned 50 uA against
# the mirror). Widths restricted to the compiled PYMS geometry set.
# v4: sense COMPOSITE mid->bkb (RT + transmission gate in series): slope at
# the crossing is 74 uV/ps (3.6x the 10-ohm-only sense), MEASURED from the
# committed hop; its zero sits +8.27 ps after true I=0 (TG displacement
# artifact, fixed -> calibratable). Stage currents raised (tails 4u, pairs
# 2u), stage-2 mirror kept small, output inverter skewed high-threshold
# (pMOS 4u) to trip early on zy's fall.
# v5: BOTH stages armed per hop; between hops the clamp followers PARK zx at
# ~0.64 V (uA-scale standby through the follower/diode chain) so arming is a
# ~40 mV excursion, not a 0.6 V slew -- v4's always-on stage 1 burned
# 0.15-0.25 mA whenever the pair saw the large inter-hop differential
# (~80 fJ/hop), and its pre-close slam latched a ~100 mV zx skew that
# outlived the crossing. No equalizer needed: parked state is symmetric
# because the pair is dead when disarmed.
# v9: park followers gated by armb -- as always-on followers they clamped
# the outputs with a 1/gm load at exactly the op point (measured stage gain
# 0.34); now they park when disarmed, RELEASE when armed.
# v8: equalizers across each pair's outputs (on when disarmed -- the pair's
# floating channel otherwise skews the parked nodes 12-36 mV, swamping the
# signal); stage-3 mirror diode parked/assisted by its own clamp follower.
# v10: two-phase arming. Tails on at t_arm WITH the equalizers still held
# (auto-zero phase: common mode establishes at full bias, differential forced
# to zero -- v9's single-edge arm kicked the outputs -180 mV via the eq gate
# charge and the diode loads took the whole window to recover); equalizers
# release at t_rel just before the crossing, so the differential develops
# from the true operating point at full gain.
# v11 (final probe config): gain/BW-balanced loads (2x0.74u diode + 0.74u
# cc -> A~2.5-3/stage at tau~60-80 ps -- v10's 0.9/1.0 cc ratio bought gain
# 10 at tau ~600 ps, GBW conservation); zy parked HIGH by an idle keeper
# (pre-fire state) and zy1 parked low; window extended -- the class verdict
# is a LATE but tracking fire, measured.
CMP = dict(
    wtail1=4.0, win=2.0, wdio=0.74, wcc=0.74, wclamp=0.74, weq=0.74,
    wtail2=4.0, win2=2.0, wmir=0.74, wkeep=0.5, wpin=0.74,
    winv_n=0.74, winv_p=4.0, clout_f=2.0,
    t_arm=200.0, t_rel=300.0, t_dis=820.0, t_edge=4.0)

ZTAGS = ["qzc", "ezc", "earm"]


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


CSCALE = 1e-4     # integrator cap, F. V(x)=integral/CSCALE. tau=RC=1e-6 s >>
                  # 0.7 ns run (leak <0.1%); the 1 F original put the fC-scale
                  # integral 7 digits under the DC pedestal I_idle*R -> below
                  # the prn's 8-sig-fig print resolution. Same instrument,
                  # readable range. Pedestal I_idle*R unchanged and subtracted
                  # by referencing the pre-arm checkpoint.


def integ(tag, expr):
    return ["CX%s x%s 0 %g" % (tag, tag, CSCALE),
            "BX%s 0 x%s I={ %s }" % (tag, tag, expr),
            "RX%s x%s 0 0.01" % (tag, tag)]


def comparator(vos_v, c=CMP):
    ta, td, te, tr = c["t_arm"], c["t_dis"], c["t_edge"], c["t_rel"]

    def diffstage(n, inp, inn, op, on):
        """armed clamped differential stage: pMOS pair, nMOS diode +
        cross-coupled load, clamp followers park the outputs when disarmed."""
        return [
            "XTA%s ztl%s armb tta%s zvdd sg13_lv_pmos w=%gu l=0.13u" % (n, n, n, c["wtail1"]),
            "XIA%s %s %s ztl%s zvdd sg13_lv_pmos w=%gu l=0.13u" % (n, op, inp, n, c["win"]),
            "XIB%s %s %s ztl%s zvdd sg13_lv_pmos w=%gu l=0.13u" % (n, on, inn, n, c["win"]),
            "XDA%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (n, op, op, c["wdio"]),
            "XDA%sb %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (n, op, op, c["wdio"]),
            "XDB%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (n, on, on, c["wdio"]),
            "XDB%sb %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (n, on, on, c["wdio"]),
            "XCA%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (n, op, on, c["wcc"]),
            "XCB%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (n, on, op, c["wcc"]),
            "XUA%s tta%s armb %s 0 sg13_lv_nmos w=%gu l=0.13u" % (n, n, op, c["wclamp"]),
            "XUB%s tta%s armb %s 0 sg13_lv_nmos w=%gu l=0.13u" % (n, n, on, c["wclamp"]),
            "XEQ%s %s eqrel %s 0 sg13_lv_nmos w=%gu l=0.13u" % (n, op, on, c["weq"]),
        ]

    L = [
        "VZC  zvdd 0 1.2",
        "VARM  arm  0 PWL(0 0 %gp 0 %gp 1.2 %gp 1.2 %gp 0)" % (ta - te, ta, td, td + te),
        "VARMB armb 0 PWL(0 1.2 %gp 1.2 %gp 0 %gp 0 %gp 1.2)" % (ta - te, ta, td, td + te),
        "VOS zinp sigp %g" % vos_v,
        "VEQR eqrel 0 PWL(0 1.2 %gp 1.2 %gp 0)" % (tr - te, tr),
        "* branch ammeters (0V) off the rail",
        "VMT1 zvdd tta1 0", "VMT2 zvdd tta2 0", "VMT3 zvdd tta3 0",
        "VMV  zvdd tnv  0",
    ]
    # note polarity: post-crossing inp<inn -> leg A (gate=inp) stronger ->
    # zx1 HIGH. S2 flips: zw2 HIGH... track: fire condition propagates so the
    # mirror stage's OUTPUT falls at fire (see below).
    L += diffstage("1", "zinp", "zinn", "zx1", "zx2")
    L += diffstage("2", "zx1", "zx2", "zw1", "zw2")
    L += [
        "* stage 3: mirror diff-to-single, armed; parked via pass/pulldown",
        "XTB ztail3 armb tta3 zvdd sg13_lv_pmos w=%gu l=0.13u" % c["wtail2"],
        "XI3 zy1 %s ztail3 zvdd sg13_lv_pmos w=%gu l=0.13u" % ("zw1", c["win2"]),
        "XI4 zy  %s ztail3 zvdd sg13_lv_pmos w=%gu l=0.13u" % ("zw2", c["win2"]),
        "XM1 zy1 zy1 0 0 sg13_lv_nmos w=%gu l=0.13u" % c["wmir"],
        "XM2 zy  zy1 0 0 sg13_lv_nmos w=%gu l=0.13u" % c["wmir"],
        "XRD zy1 armb 0 0 sg13_lv_nmos w=%gu l=0.13u" % c["wpin"],
        "XRS zy arm tnv zvdd sg13_lv_pmos w=%gu l=0.13u" % c["wkeep"],
        "* output: skewed inverter (idle zy=0 -> zout=1.2; falls at arm-settle,",
        "* rises when zy falls at ... see polarity note",
        "XON zout zy 0 0 sg13_lv_nmos w=%gu l=0.13u" % c["winv_n"],
        "XOP zout zy tnv zvdd sg13_lv_pmos w=%gu l=0.13u" % c["winv_p"],
        "CLZ zout 0 %gf" % c["clout_f"],
    ]
    L += integ("qzc", "-I(VZC)")
    L += integ("ezc", "-1.2*I(VZC)")
    L += integ("earm", "-V(arm)*I(VARM)-V(armb)*I(VARMB)")
    return L


def cells(all_hi=False):
    hi = list(range(MGATE)) if all_hi else [i for i in range(MGATE) if i % 2 == 0]
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    for i in range(MGATE):
        g = "gnh" if i in hi else "gnl"
        L.append("VI%d in%d 0 %g" % (i, i, DV if i in hi else 0.0))
        L.append("XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, WP))
        L.append("XN%d o%d in%d %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, g, g, WN))
        L.append("CL%d o%d %s %gf" % (i, i, g, CLOAD))
    return L


def hop_plant(t_half_ps=T_HALF, all_hi=False):
    return [
        ".param LT=%gn RS=%g CA=%gf" % (L_NH, RS, CA_FF),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (T0 - 2, T0, VGH, T0 + t_half_ps, VGH, T0 + t_half_ps + 2),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (VGH, T0 - 2, VGH, T0, T0 + t_half_ps, T0 + t_half_ps + 2, VGH),
        "XSWN sw gt  bkb 0   sg13_lv_nmos w=%gu l=0.13u" % WSW,
        "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % (2 * WSW),
        "LT bka mid {LT}", "RT mid sw {RS}",
    ] + cells(all_hi) + [".ic V(bka)=%g V(bkb)=0" % DV]


def run(fn, lines, timeout=580):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                       timeout=timeout, cwd=HERE, env=ENV)
    wall = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:500]
        print("XYCE FAILED %s (%.1fs): %s" % (fn, wall, err or r.stdout[-500:]))
        sys.exit(1)
    print("  ran %s in %.1fs" % (fn, wall))
    return path + ".prn"


def read_prn(path):
    rows, hdr = [], None
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


def cross(rows, it, iv, level, rising, tmin=0.0):
    """first crossing of column iv through level after tmin; linear interp."""
    for k in range(1, len(rows)):
        a, b = rows[k - 1], rows[k]
        if b[it] < tmin:
            continue
        if rising and a[iv] < level <= b[iv] or (not rising and a[iv] > level >= b[iv]):
            f = (level - a[iv]) / (b[iv] - a[iv])
            return a[it] + f * (b[it] - a[it])
    return None


def col(hdr, name):
    return [i for i, h in enumerate(hdr) if name in h][0]


# ------------------------------------------------------------------- stage wave
def stage_wave(r_sns=0.0, t_ins=240.0):
    """Replay tables. r_sns > 0 models a switched-in series sense resistor
    (bypass opens at t_ins): inp = V(mid) = V(sw) + (RS + r_sns(t))*I."""
    hdr, rows = read_prn(os.path.join(GATEB, "gb_hop.cir.prn"))
    it, ii, isw = col(hdr, "TIME"), col(hdr, "I(LT)"), col(hdr, "V(SW)")
    ib = col(hdr, "V(BKB)")
    pts_p, pts_n = [], []
    tlast = -1
    for r in rows:
        t = r[it]
        if t > 850e-12:
            break
        if t - tlast < 2e-12:
            continue
        tlast = t
        rr = RS + (r_sns if t >= t_ins * 1e-12 else 0.0)
        vn = r[ib]                  # composite sense: inn = bkb
        vp = r[isw] + rr * r[ii]    # inp = mid
        pts_n.append((t, vn))
        pts_p.append((t, vp))
    json.dump({"inp": pts_p, "inn": pts_n},
              open(os.path.join(HERE, "zcd_wave.json"), "w"))
    print("wave: %d pts each, to 700 ps, r_sns=%g" % (len(pts_p), r_sns))


def pwl(name, node, pts):
    body = " ".join("%.6gp %.6g" % (t * 1e12, v) for t, v in pts)
    return "%s %s 0 PWL(%s)" % (name, node, body)


# --------------------------------------------------------------- stage sa (standalone)
def stage_sa(vos_mv, tag=None):
    w = json.load(open(os.path.join(HERE, "zcd_wave.json")))
    tend = 878.0
    L = head() + [pwl("VSP", "sigp", w["inp"]), pwl("VSN", "zinn", w["inn"])] \
        + comparator(vos_mv * 1e-3) + [
        ".tran 0.1p %gp 0 0.5p" % tend,
        ".print tran V(sigp) V(zinn) V(zx1) V(zx2) V(zw1) V(zw2) V(zy) V(zy1) V(zout) "
        "I(VZC) I(VMT1) I(VMT2) I(VMT3) I(VMV) I(VARM) I(VARMB) V(xqzc) V(xezc) V(xearm)",
        ".end"]
    fn = "za_%s.cir" % (tag if tag else ("m%+05.0f" % (vos_mv * 100)).replace("+", "p").replace("-", "n"))
    return report(run(fn, L), sa=True)


# --------------------------------------------------------------------- stage hop
def stage_hop(vos_mv, all_hi=False, tag=None, r_sns=140.0, t_ins=240.0,
              t_half=900.0, bypass=False):
    """In-hop probe: committed hop plant, but (a) the switch is HELD CLOSED
    through the window (a real ZCS deployment opens it when the ZCD fires --
    with the committed 392 ps opening in the waveform the detector locks on
    the opening transient, not the zero: measured on the replay), and (b) a
    switched sense resistor r_sns is inserted at t_ins (bypass: 2x20 um nMOS,
    gate drive metered by the egt convention)."""
    tend = 878.0
    L = head() + hop_plant(t_half_ps=t_half, all_hi=all_hi)         + comparator(vos_mv * 1e-3)
    # sense chain: mid --RT(10)-- s1 --[RSNS 140 || bypass]-- sw
    L = [ln.replace("RT mid sw {RS}", "RT mid s1 {RS}") for ln in L]
    L += ["RSNS s1 sw %g" % r_sns]
    if bypass:
        # MEASURED TRAP: the 2x20um bypass's own gate/channel charge grossly
        # perturbs the hop (Ipk 128 vs 195 uA, zero 409 vs 340 ps) -- any
        # added switch on the transfer path costs charge comparable to the
        # 36 fF bank. Kept for the record; default is always-in RSNS.
        L += ["VBYG byg 0 PWL(0 1.5 %gp 1.5 %gp 0 %gp 0 %gp 1.5)"
                  % (t_ins - 4, t_ins, tend - 20, tend - 16),
              "XBY1 s1 byg sw 0 sg13_lv_nmos w=20u l=0.13u",
              "XBY2 s1 byg sw 0 sg13_lv_nmos w=20u l=0.13u"]
        L += integ("ebyp", "-V(byg)*I(VBYG)")
    # comparator senses mid -> bkb (composite: RT + RSNS + TG)
    L += ["RSIGP sigp mid 0.001", "RSIGN zinn bkb 0.001"]
    L += [".tran 0.1p %gp 0 0.25p" % tend,
          ".measure tran VBEND FIND V(bkb) AT=%gp" % (tend - 5),
          ".measure tran IPK MAX I(LT) FROM=0 TO=%gp" % tend,
          ".print tran I(LT) V(bka) V(bkb) V(mid) V(sw) V(zx1) V(zx2) V(zw1) V(zw2) "
          "V(zy1) V(zy) V(zout) I(VZC) V(xqzc) V(xezc) V(xearm)"
          + (" I(VBYG) V(xebyp)" if bypass else ""),
          ".end"]
    fn = tag or ("zh_%s.cir" % ("allhi" if all_hi else
                 ("m%+05.0f" % (vos_mv * 100)).replace("+", "p").replace("-", "n")))
    if not fn.endswith(".cir"):
        fn += ".cir"
    return report(run(fn, L), sa=False)


# ----------------------------------------------------------------------- report
def report(prn, sa):
    hdr, rows = read_prn(prn)
    it = col(hdr, "TIME")
    out = {}
    if sa:
        ip, iN = col(hdr, "V(SIGP)"), col(hdr, "V(ZINN)")
        # true zero of the REPLAYED signal (offset not included: VOS is series)
        tz = None
        for k in range(1, len(rows)):
            a, b = rows[k - 1], rows[k]
            if a[it] < 100e-12:
                continue
            da, db = a[ip] - a[iN], b[ip] - b[iN]
            if da > 0 >= db:
                tz = a[it] + (b[it] - a[it]) * da / (da - db)
                break
    else:
        ii = col(hdr, "I(LT)")
        tz = cross(rows, it, ii, 0.0, rising=False, tmin=100e-12)
        out["vbend"] = rows[-1][col(hdr, "V(BKB)")]
        out["ipk"] = max(r[ii] for r in rows)
    io = col(hdr, "V(ZOUT)")
    tf = cross(rows, it, io, 0.6, rising=True, tmin=(CMP["t_rel"] + 5) * 1e-12)
    iq, ie, ia = col(hdr, "V(XQZC)"), col(hdr, "V(XEZC)"), col(hdr, "V(XEARM)")
    # integrator readout: (V(t) - V(baseline)) * CSCALE cancels the frozen
    # DC pedestal I(0)*Rbleed; baseline at 2 ps (post-DC, pre-activity)
    def at(tps, idx):
        r = min(rows, key=lambda q: abs(q[it] - tps * 1e-12))
        return r[idx]
    def rd(idx, tps=None):
        v = rows[-1][idx] if tps is None else at(tps, idx)
        return (v - at(2.0, idx)) * CSCALE
    # the integrator integrates (inj - inj_DC0): the DC-op current leaks
    # through the bleed for the whole run. Correct with +inj0*t (exact for
    # t << RC) and cross-check against a dense-grid (0.25-0.5 ps forced
    # dtmax) trapezoid of the printed rail current.
    iz = col(hdr, "I(VZC)")
    inj0 = -rows[0][iz]
    tend = rows[-1][it]
    qcor, ecor = inj0 * tend, 1.2 * inj0 * tend
    qtz = etz = 0.0
    for k in range(1, len(rows)):
        dt = rows[k][it] - rows[k - 1][it]
        qtz += -0.5 * (rows[k][iz] + rows[k - 1][iz]) * dt
    etz = 1.2 * qtz
    td = CMP["t_dis"]
    out.update({
        "t_zero_ps": None if tz is None else tz * 1e12,
        "t_fire_ps": None if tf is None else tf * 1e12,
        "delay_ps": None if (tz is None or tf is None) else (tf - tz) * 1e12,
        "q_rail_fC": (rd(iq) + qcor) * 1e15,
        "e_rail_fJ": (rd(ie) + ecor) * 1e15,
        "q_rail_trapz_fC": qtz * 1e15,
        "e_rail_trapz_fJ": etz * 1e15,
        "e_arm_net_fJ": rd(ia) * 1e15,
        "e_arm_delivered_fJ": rd(ia, td) * 1e15,   # before recovery edge
        "e_rail_at_disarm_fJ": rd(ie, td) * 1e15,
        "e_byp_net_fJ": (rd(col(hdr, "V(XEBYP)")) * 1e15
                         if any("XEBYP" in h for h in hdr) else None),
        "e_det_net_fJ": (rd(ie) + ecor + rd(ia)) * 1e15,
        "e_det_norecov_fJ": (rd(ie) + ecor + rd(ia, td)) * 1e15,
        "i_standby_uA": -1e6 * at(CMP["t_arm"] - 30.0, iz),
    })
    print(json.dumps(out, indent=1))
    return out


def stage_sweep(vals_mv, sa=True):
    out = {}
    for v in vals_mv:
        out["%+.2f" % v] = (stage_sa if sa else stage_hop)(v)
    json.dump(out, open(os.path.join(
        HERE, "zcd_sweep_%s.json" % ("sa" if sa else "hop")), "w"), indent=1)
    return out


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "wave":
        stage_wave(float(sys.argv[2]) if len(sys.argv) > 2 else 0.0)
    elif st == "sa":
        stage_sa(float(sys.argv[2]) if len(sys.argv) > 2 else 0.0)
    elif st == "hop":
        stage_hop(float(sys.argv[2]) if len(sys.argv) > 2 else 0.0)
    elif st == "hopall":
        stage_hop(0.0, all_hi=True)
    elif st == "sweepsa":
        stage_sweep([float(x) for x in sys.argv[2].split(",")], sa=True)
    elif st == "sweephop":
        stage_sweep([float(x) for x in sys.argv[2].split(",")], sa=False)
