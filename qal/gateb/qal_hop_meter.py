#!/usr/bin/env python3
"""GATE B: meter the CELLS' supply/ground/input ports separately from the bank
plant during the committed iso-current hop (dV=1.0, L=277.8 nH, t_zcs=342.0 ps)
to CONFIRM or REFUTE the v3 inference that the ~13 fC delivery/static gap is
the cells' dissipative gate current (~8.28 fJ).

Pre-registration (tolerances stated BEFORE any hop run): gateb/PRE_REGISTERED.json.

Topology is qal_hop_gates.py's hop_deck() EXACTLY, with three 0V ammeters and
1F-cap integrators inserted:
    bka --LT-- mid --RT-- sw --[XSWN/XSWP]-- swb --VMSW(0V)-- bkb
    bkb --VMSH(0V)-- vsh -> 4 hi-input cells (pMOS S/B)   } cells' supply port
    bkb --VMSL(0V)-- vsl -> 4 lo-input cells (pMOS S/B)   }
    cell nMOS S/B + CL bottoms -> gnh/gnl --VMGH/VMGL(0V)-- 0   (ground port)
    VIi per input (input port)
Every charge/energy is integral(I) or integral(V*I) on a 1F cap driven by a
B-source (the committed technique; '.measure INTEGRAL' under-reports and is
only emitted for comparison against the committed iso1000_h.cir.mt0).

Stages: calib (instrument check) -> probe (I(LT) zero) -> hop -> pinned -> report.
"""
import math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_gateb"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

DV, L_NH, RS = 1.0, 277.8, 10.0
WSW, VGH     = 20.0, 1.5
WP, WN       = 1.12, 0.74
MGATE, CLOAD = 8, 2.0
CA_FF        = 35.979          # committed C_eff at dV=1.0 (qal_isocurrent.json)
T0           = 50.0            # ps, switch closes
VCHK = [0.167, 0.333, 0.5, 0.667, 0.833, 0.917, 1.0]   # committed checkpoints

HI = [i for i in range(MGATE) if i % 2 == 0]   # inputs at DV (pMOS off, nMOS on)
LO = [i for i in range(MGATE) if i % 2 == 1]   # inputs at 0  (pMOS on,  nMOS off)


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def cells_metered(pinned=False, supply="bkb"):
    """8 inverters with pMOS source+body DIRECTLY on the bank node (as
    committed -- Xyce SILENTLY DROPS an .ic on any node that is a V-source
    terminal, so NO meter may touch bkb). Metered ports: per-group ground
    returns (VMGH/VMGL, nMOS S/B + CL bottoms) and inputs (VIi, or per-group
    pin sources when pinned). The supply-port current is DERIVED by block
    neutrality, I_sup = I_gnd_out + I_in_out, an identity the slow-ramp run
    verified against direct supply meters to 0.001 fC on 20.6 fC.
    pinned=True: transistor gates pinned OFF (pMOS 1.2 V, nMOS 0 V)."""
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    if pinned:
        L += ["VPPH pinph 0 1.2", "VPPL pinpl 0 1.2",
              "VPNH pinnh 0 0",   "VPNL pinnl 0 0"]
    for i in range(MGATE):
        gnd = "gnh" if i in HI else "gnl"
        if pinned:
            gp = "pinph" if i in HI else "pinpl"
            gn = "pinnh" if i in HI else "pinnl"
        else:
            L.append("VI%d in%d 0 %g" % (i, i, DV if i in HI else 0.0))
            gp = gn = "in%d" % i
        L.append("XP%d o%d %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (i, i, gp, supply, supply, WP))
        L.append("XN%d o%d %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, gn, gnd, gnd, WN))
        L.append("CL%d o%d %s %gf" % (i, i, gnd, CLOAD))
    return L


def _sup_expr(group, pinned, supply=None):
    """Neutrality-derived supply-port current of one cell group."""
    if pinned:
        vg = "I(VMGH)" if group == "H" else "I(VMGL)"
        pins = ("I(VPPH)+I(VPNH)") if group == "H" else ("I(VPPL)+I(VPNL)")
        e = "%s+%s" % (vg, pins)
    else:
        idx = HI if group == "H" else LO
        vg = "I(VMGH)" if group == "H" else "I(VMGL)"
        e = vg + "+" + "+".join("I(VI%d)" % i for i in idx)
    return e


def integ(tag, expr):
    """1F-cap integrator: V(x%s) = integral of expr dt. The 0.01 Ohm bleed gives
    the node a DC path while keeping it a true integrator (tau = RC = 0.01 s >>
    run length; leak error ~2e-6 relative over 20 ns). A LARGE bleed is wrong:
    the DC op pre-charges the node to I_leak*R (measured 8 V at R=1e12 from
    ~8 pA of PSP103 gate leakage), swamping fC-scale signals."""
    return ["CX%s x%s 0 1" % (tag, tag), "BX%s 0 x%s I={ %s }" % (tag, tag, expr),
            "RX%s x%s 0 0.01" % (tag, tag)]


def cell_integrators(pinned=False, supply="bkb"):
    L = []
    sh, sl = _sup_expr("H", pinned), _sup_expr("L", pinned)
    L += integ("qsh", sh) + integ("qsl", sl)
    L += integ("esh", "V(%s)*(%s)" % (supply, sh)) + integ("esl", "V(%s)*(%s)" % (supply, sl))
    L += integ("qgh", "I(VMGH)") + integ("qgl", "I(VMGL)")
    if pinned:
        L += integ("qih", "-(I(VPPH)+I(VPPL))")
        L += integ("eih", "-1.2*(I(VPPH)+I(VPPL))")
        L += integ("qil", "-(I(VPNH)+I(VPNL))")
    else:
        L += integ("qih", "-(" + "+".join("I(VI%d)" % i for i in HI) + ")")
        L += integ("eih", "-(" + "+".join("V(in%d)*I(VI%d)" % (i, i) for i in HI) + ")")
        L += integ("qil", "-(" + "+".join("I(VI%d)" % i for i in LO) + ")")
    return L


INTEG_TAGS_CELLS = ["qsh", "qsl", "esh", "esl", "qgh", "qgl", "qih", "eih", "qil"]
INTEG_TAGS_PATH  = ["qlt", "ea", "eb", "qbk", "ebk", "er", "esw", "qgt", "qgtp",
                    "qhi", "egt", "ehi"]


def path_integrators(pinned=False):
    L = []
    L += integ("qlt", "I(LT)") + integ("ea", "V(bka)*I(LT)") + integ("eb", "V(bkb)*I(LT)")
    # total into bkb = cells' total supply intake (KCL: nothing else on bkb)
    tot = "(%s)+(%s)" % (_sup_expr("H", pinned), _sup_expr("L", pinned))
    L += integ("qbk", tot) + integ("ebk", "V(bkb)*(%s)" % tot)
    L += integ("er", "I(LT)*I(LT)*%g" % RS)
    L += integ("esw", "V(sw)*I(LT)")            # energy into the switch block from the path
    L += integ("qgt", "-I(VGT)") + integ("qgtp", "-I(VGTP)") + integ("qhi", "-I(VHI)")
    L += integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)")   # committed Bpg convention
    L += integ("ehi", "-%g*I(VHI)" % VGH)
    return L


def run(fn, lines, timeout=580):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                       timeout=timeout, cwd=HERE, env=ENV)
    wall = time.monotonic() - t0
    ok = os.path.exists(path + ".mt0") or os.path.exists(path + ".prn")
    if r.returncode != 0 or not ok:
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        print("XYCE FAILED %s (%.1fs): %s" % (fn, wall, err or r.stdout[-400:]))
        sys.exit(1)
    print("  ran %s in %.1fs" % (fn, wall))
    return path


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


# ---------------------------------------------------------------- stage: calib
def stage_calib():
    t = 20000.0   # ps, committed 20 ns adiabatic ramp
    L = head() + ["VS bkb 0 PWL(0 0 %gp %g)" % (t, DV)] + cells_metered() + \
        cell_integrators() + \
        ["Bp p 0 V={ -V(bkb)*I(VS) }", "Bq q 0 V={ -I(VS) }",
         ".tran %gp %gp" % (t / 4000.0, t * 1.02)]
    keys = []
    for v in VCHK:
        nm = "E%03d" % int(round(v * 1000))
        L.append(".measure tran %s INTEGRAL V(p) FROM=0 TO=%gp" % (nm, t * v / DV))
        keys.append(nm)
    L.append(".measure tran QTOT INTEGRAL V(q) FROM=0 TO=%gp" % t)
    prn = ["TIME", "V(bkb)"] + ["V(x%s)" % g for g in INTEG_TAGS_CELLS] + \
          ["V(o0)", "V(o1)"]
    L.append(".print tran " + " ".join(prn[1:]))
    L.append(".end")
    run("gb_calib.cir", L)
    print("calib done")


# ---------------------------------------------------------------- stage: probe
def stage_probe():
    ca = CA_FF
    cser = (ca * ca / (2 * ca)) * 1e-15
    tend = 50.0 + 6.0 * math.pi * math.sqrt((L_NH * 1e-9) * cser) * 1e12
    L = head() + [
        ".param LT=%gn RS=%g CA=%gf" % (L_NH, RS, ca),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 48p 0 50p %g %gp %g)" % (VGH, tend * 2, VGH),
        "VGTP gtp 0 PWL(0 %g 48p %g 50p 0 %gp 0)" % (VGH, VGH, tend * 2),
        "XSWN sw gt  bkb 0   sg13_lv_nmos w=%gu l=0.13u" % WSW,
        "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % (2 * WSW),
        "LT bka mid {LT}", "RT mid sw {RS}",
    ] + cells_metered() + [
        # committed .ic EXACTLY; bkb has no V-source touching it (Xyce
        # silently drops .ic on V-source terminal nodes -- measured)
        ".ic V(bka)=%g V(bkb)=0" % DV,
        ".print tran I(LT) V(bkb) V(bka)",
        ".tran 0.1p %gp" % tend, ".end"]
    path = run("gb_probe.cir", L)
    hdr, rows = read_prn(path + ".prn")
    ii = [i for i, h in enumerate(hdr) if "LT" in h][0]
    prev = None
    for r in rows:
        tt, cur = r[1], r[ii]
        if prev is not None and prev > 0 and cur <= 0 and tt > 60e-12:
            print("probe zero: t_half = %.2f ps (committed 342.0)" % (tt * 1e12 - T0))
            return
        prev = cur
    print("probe: NO ZERO FOUND")


# ------------------------------------------------------------------ stage: hop
def hop_lines(t_half_ps, pinned):
    tend = T0 + t_half_ps + 500.0
    L = head() + [
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
    ] + cells_metered(pinned) + cell_integrators(pinned) + path_integrators(pinned) + [
        # committed-style B-sources + INTEGRAL measures, comparison only
        "Bpa pa 0 V={ V(bka)*I(LT) }", "Bpb pb 0 V={ V(bkb)*I(LT) }",
        "Bqt qt 0 V={ I(LT) }",
        ".ic V(bka)=%g V(bkb)=0" % DV]
    if pinned:
        L += [".ic " + " ".join("V(o%d)=0" % i for i in range(MGATE))]
    # dtmax forced: the ~30 near-zero integrator nodes dilute the step-error
    # norm (first try ran 719 steps, 13 s, and MISSED the committed trajectory:
    # VBPK 0.714 vs 0.611); 0.25p caps the step at probe-run resolution.
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    # committed headline measures
    L += [".measure tran EOUTA INTEGRAL V(pa) FROM=0 TO=%gp" % tend,
          ".measure tran EINB  INTEGRAL V(pb) FROM=0 TO=%gp" % tend,
          ".measure tran QTR   INTEGRAL V(qt) FROM=0 TO=%gp" % tend,
          ".measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp" % (T0, tend),
          ".measure tran VBEND FIND V(bkb) AT=%gp" % (tend - 5),
          ".measure tran VAEND FIND V(bka) AT=%gp" % (tend - 5),
          ".measure tran IPK   MAX I(LT) FROM=0 TO=%gp" % tend,
          ".measure tran IZ    FIND I(LT) AT=%gp" % (T0 + t_half_ps)]
    # integrator checkpoints: P1 close-edge end, P2 traverse end (pre-open),
    # P3 open-edge end, P4 final hold
    cks = [("Z", 0.5), ("A", T0 + 5.0), ("B", T0 + t_half_ps),
           ("C", T0 + t_half_ps + 7.0), ("D", tend - 5.0)]
    for tag in INTEG_TAGS_CELLS + INTEG_TAGS_PATH:
        for nm, tt in cks:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%gp" % (tag.upper(), nm, tag, tt))
    for i in range(MGATE):
        L.append(".measure tran O%dZ FIND V(o%d) AT=%gp" % (i, i, T0 + t_half_ps))
        L.append(".measure tran O%dE FIND V(o%d) AT=%gp" % (i, i, tend - 5.0))
    prn = ["V(bka)", "V(bkb)", "V(sw)", "I(LT)",
           "I(VMGH)", "I(VMGL)", "V(xqlt)", "V(xqbk)", "V(xqsh)", "V(xqsl)",
           "V(xqgh)", "V(xqgl)", "V(o0)", "V(o1)"]
    L.append(".print tran " + " ".join(prn))
    L.append(".end")
    return L, tend


def stage_hop(t_half_ps, pinned=False):
    fn = "gb_pin.cir" if pinned else "gb_hop.cir"
    L, tend = hop_lines(t_half_ps, pinned)
    run(fn, L)
    print("%s done (tend=%gp)" % (fn, tend))


if __name__ == "__main__":
    stage = sys.argv[1]
    if stage == "calib":
        stage_calib()
    elif stage == "probe":
        stage_probe()
    elif stage == "hop":
        stage_hop(float(sys.argv[2]))
    elif stage == "pinned":
        stage_hop(float(sys.argv[2]), pinned=True)
