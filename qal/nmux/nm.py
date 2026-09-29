#!/usr/bin/env python3
"""(b)(d) nMOS-only MUX2 / XOR2 vs a full-TRANSMISSION-GATE control, in ONE harness.

Rail generators are BYTE-FAITHFUL copies of the committed configurations so the
no-mux runs are instrument gates:
  peer  = qal/resv h_I2_load691_L4   (CA 35.979f @ dV 1.65, L 4nH, RS 10, 8 cells CL 6.91f)
          committed: VBEND 0.754572966  VBPK 1.0881874  t_hop 34.2858 ps  VA_open 0.117456016
  tank  = qal/resv ch_res20 bank 1   (CRES 719.58f @ 1.2V, L 15nH, RS 10, 8 cells CL 2f)
          committed: rail_at_own_boundary 1.32574378 V  rail_peak 1.4502807 V

The pass structure hangs on driver-cell outputs.  Metering (protocol P4):
  E_in   -- charge/energy the pass structure draws from the driving cell output,
            through a series 0 V meter source, so it is separable by construction
  E_gate -- the select drive off its own rail
  E_sup  -- any STATIC supply the cell touches.  For nMOS-only there is none; the
            meter is wired anyway and MUST read zero (pre-registered check E8).
            For the TG it is the n-well bias.
"""
import json, math, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_nmux"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

VGH   = 1.5      # select-drive rail (brief: switch gates driven at 1.5 V)
WP, WN = 1.12, 0.74
CY    = 2.0      # fF on the pass output (campaign CLOAD proxy for a gate input)

# committed rail-generator parameters, per mode
RAIL = {
    "peer": dict(csrc=35.979, vsrc=1.65, L=4.0,  RS=10.0, vhi=1.65, clb=6.91,
                 t_close=50.0,  t_open=84.2858,  tend=584.286, vin=1.65,
                 swn=10.0, swp=20.0, park=2.0, kind="cap"),
    "tank": dict(csrc=719.58, vsrc=1.2,  L=15.0, RS=10.0, vhi=1.5,  clb=2.0,
                 t_close=200.0, t_open=345.834, tend=900.0,  vin=1.2,
                 swn=10.0, swp=20.0, park=0.0, kind="res"),
}

# cell library.  Each returns (device lines, list of (meter_name, data_node),
# n_nmos, n_pmos).  `sel` dict maps logical control names -> node names.
def cell_lines(design, inst, w, y, dA, dB, ctl, nw):
    """inst: instance prefix.  dA/dB: the two metered data nodes (post-meter).
    ctl: dict with 's' and 'sb' node names (the two complementary controls).
    nw : n-well bias node for pMOS bodies."""
    s, sb = ctl["s"], ctl["sb"]
    L, nn, npx = [], 0, 0
    if design in ("nmux", "nxor"):
        L += ["XN%sA %s %s %s 0 sg13_lv_nmos w=%gu l=0.13u" % (inst, dA, s,  y, w),
              "XN%sB %s %s %s 0 sg13_lv_nmos w=%gu l=0.13u" % (inst, dB, sb, y, w)]
        nn = 2
    elif design in ("tgmux", "tgxor"):
        L += ["XN%sA %s %s %s 0 sg13_lv_nmos w=%gu l=0.13u" % (inst, dA, s,  y, w),
              "XP%sA %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (inst, dA, sb, y, nw, w),
              "XN%sB %s %s %s 0 sg13_lv_nmos w=%gu l=0.13u" % (inst, dB, sb, y, w),
              "XP%sB %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (inst, dB, s,  y, nw, w)]
        nn, npx = 2, 2
    else:
        raise ValueError(design)
    return L, nn, npx


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17"]


def integ(name, expr):
    return ["CX%s x%s 0 1" % (name, name),
            "BX%s 0 x%s I={ %s }" % (name, name, expr),
            "RX%s x%s 0 0.01" % (name, name)]


def rail_lines(mode, t_open, probe):
    """committed rail generator.  probe=True holds the switch closed to the end."""
    R = RAIL[mode]
    vhi, tc = R["vhi"], R["t_close"]
    to = R["tend"] + 100.0 if probe else t_open
    L = ["VHI vhi 0 %g" % vhi,
         "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
         % (tc - 2, tc, vhi, to, vhi, to + 2),
         "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
         % (vhi, tc - 2, vhi, tc, to, to + 2, vhi),
         "XSWN sw gt rail 0 sg13_lv_nmos w=%gu l=0.13u" % R["swn"],
         "XSWP sw gtp rail vhi sg13_lv_pmos w=%gu l=0.13u" % R["swp"],
         "LT bka mid %gn" % R["L"],
         "RT mid sw %g" % R["RS"]]
    if R["kind"] == "cap":
        L = ["CA bka 0 %gf" % R["csrc"]] + L
        if R["park"]:
            L += ["XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % R["park"],
                  "VPK pk 0 PWL(0 0 %gp 0 %gp %g)" % (to, to + 2, vhi)]
        else:
            L += ["RKPK pk 0 1e9"]
        ic = ".ic V(bka)=%g V(rail)=0" % R["vsrc"]
    else:
        # reservoir: a big cap plus a SOURCE-side transfer switch (ch_res20 form)
        # no park device on the reservoir form (the committed ch_res20 has none);
        # node `pk` is therefore never created and must not be referenced
        L = ["CRES res1 0 %gf" % R["csrc"]] + L + [
            "XSWSN bka gt res1 0 sg13_lv_nmos w=%gu l=0.13u" % R["swn"],
            "XSWSP bka gtp res1 vhi sg13_lv_pmos w=%gu l=0.13u" % R["swp"]]
        ic = ".ic V(res1)=%g V(rail)=0 V(bka)=0" % R["vsrc"]
    return L, ic


def bank_lines(mode):
    """8 driver inverters on the rail, alternating high/low, committed sizing."""
    R = RAIL[mode]
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    for i in range(8):
        hi = (i % 2 == 0)
        gn = "gnh" if hi else "gnl"
        L += ["VI%d in%d 0 %g" % (i, i, R["vin"] if hi else 0.0),
              "XP%d o%d in%d rail rail sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, WP),
              "XN%d o%d in%d %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, gn, gn, WN),
              "CL%d o%d %s %gf" % (i, i, gn, R["clb"])]
    return L


def build(mode, design, w, t_open, probe=False, gate_src="v15", tag="x"):
    """Two instances of the design: H passes a HIGH, L passes a LOW.

    The driver cells INVERT, so the tap polarity is the opposite of the input:
        VI_i = vin (even i)  -> o_i is LOW
        VI_i = 0   (odd  i)  -> o_i is HIGH
    Assignment:
        o1 HIGH / o0 LOW   -> instance H data legs (metered)
        o3 HIGH / o2 LOW   -> instance L data legs (metered)
        o5 HIGH / o4 LOW   -> the SELECT pair when gate_src == "rail"
        o7 HIGH / o6 LOW   -> UNLOADED references, always
    o0/o1 and o2/o3 are genuine complements, so the same netlist IS a real
    XOR2 when the select is an operand and a real MUX2 when it is control."""
    R = RAIL[mode]
    D = head()
    rl, ic = rail_lines(mode, t_open, probe)
    D += rl + bank_lines(mode)

    # Select drive.  gate_src "v15" = dedicated 1.5 V control rail: a datapath
    # MUX select is control, generated once and shared across the word, so it can
    # legitimately live on the switch rail.  gate_src "rail" = the select IS a
    # QAL logic operand and therefore arrives only at the rail level -- the
    # honest case for XOR2, where one operand MUST drive the pass gates.  In that
    # case the select is taken from real cells (o5/o4) so it RAMPS with the rail,
    # which is what actually happens in the machine.
    tsel = R["t_close"] - 30.0
    if gate_src == "v15":
        # sources drive sel/selb from the 1.5 V control rail; current DELIVERED
        # to the gate nodes is -I(Vsrc), the committed sign convention
        D += ["VSEL  sel  0 PWL(0 0 %gp 0 %gp %g)" % (tsel - 2, tsel, VGH),
              "VSELB selb 0 PWL(0 %g %gp %g %gp 0)" % (VGH, tsel - 2, VGH, tsel)]
        gsign = "-"
    else:
        # sel/selb ARE cell outputs o5 (HIGH) / o4 (LOW), reached through 0 V
        # meter sources so the gate-drive charge is still separable.  Here the
        # current delivered to the gate node is +I(Vsrc).
        D += ["VSEL  o5 sel  0", "VSELB o4 selb 0"]
        gsign = "+"
    D += ["VNW nw 0 %g" % VGH, "RKNW nw 0 1e9"]

    D += ["VMH0 o0 mh0 0", "VMH1 o1 mh1 0", "VML0 o2 ml0 0", "VML1 o3 ml1 0"]
    ctl = dict(s="sel", sb="selb")
    # instance H: sel high -> leg A conducts -> leg A must carry the HIGH (mh1)
    lh, nn, npx = cell_lines(design, "H", w, "yh", "mh1", "mh0", ctl, "nw")
    # instance L: sel high -> leg A conducts -> leg A must carry the LOW (ml0)
    ll, _, _    = cell_lines(design, "L", w, "yl", "ml0", "ml1", ctl, "nw")
    D += lh + ll
    D += ["CYH yh 0 %gf" % CY, "CYL yl 0 %gf" % CY]

    # ---- meters (all 1F integrators, t0-referenced downstream) ----
    D += integ("qlt", "I(LT)")
    D += integ("eb",  "V(rail)*I(LT)")
    D += integ("er",  "I(LT)*I(LT)*%g" % R["RS"])
    D += integ("qih", "I(VMH0)+I(VMH1)")
    D += integ("eih", "V(mh0)*I(VMH0)+V(mh1)*I(VMH1)")
    D += integ("qil", "I(VML0)+I(VML1)")
    D += integ("eil", "V(ml0)*I(VML0)+V(ml1)*I(VML1)")
    D += integ("egt", "%sV(sel)*I(VSEL)%sV(selb)*I(VSELB)" % (gsign, gsign))
    D += integ("qgt", "%sI(VSEL)%sI(VSELB)" % (gsign, gsign))
    D += integ("esup", "-V(nw)*I(VNW)")          # E8: must be ~0 for nMOS-only
    D += integ("qsup", "-I(VNW)")
    D += integ("ebk", "V(rail)*((I(VMGH)+I(VI0)+I(VI2)+I(VI4)+I(VI6))"
                      "+(I(VMGL)+I(VI1)+I(VI3)+I(VI5)+I(VI7)))")

    D += [ic]
    D += [".print tran V(rail) V(bka) V(sw) I(LT) V(o0) V(o1) V(o2) V(o3)",
          "+ V(o4) V(o5) V(o6) V(o7) V(yh) V(yl) V(sel) V(selb)",
          "+ V(xqlt) V(xeb) V(xer) V(xqih) V(xeih) V(xqil) V(xeil)",
          "+ V(xegt) V(xqgt) V(xesup) V(xqsup) V(xebk)"]
    # AMENDMENT A5: the committed peer deck's max step (0.0177663 ps) makes these
    # 18-device + 12-integrator decks run 7+ minutes apiece on a box carrying
    # another workflow's ~16 concurrent Xyce jobs.  Relaxed to 0.05 ps, the same
    # step the committed tank chain uses.  Instrument gate G2 still runs the
    # committed deck VERBATIM at its own step, and a step-sensitivity row
    # (STEPCHK below) measures what the relaxation actually costs.
    dt = float(os.environ.get("NMUX_DT", 0.02))
    mx = float(os.environ.get("NMUX_MAXSTEP", 0.05))
    # the probe only has to reach the first current zero; running it over the
    # whole hold window costs ~2x for nothing (the zero is 34 ps after close in
    # peer, 146 ps in tank).
    tend = (R["t_close"] + 300.0) if probe else R["tend"]
    D += [".tran %gp %gp 0 %gp" % (dt, tend, mx), ".end", ""]
    p = os.path.join(HERE, tag + ".cir")
    open(p, "w").write("\n".join(D))
    return p


def run(path):
    t0 = time.monotonic()
    r = subprocess.run([XYCE, path], cwd=HERE, env=ENV,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, time.monotonic() - t0, r.stdout.decode()[-600:]


def read_prn(path):
    cols, data = None, []
    for ln in open(path):
        f = ln.split()
        if not f:
            continue
        if f[0] == "Index":
            cols = f[1:]
            continue
        if f[0] == "End":
            break
        if cols and f[0].isdigit():
            try:
                data.append([float(x) for x in f[1:1 + len(cols)]])
            except ValueError:
                pass
    return cols, data


class W:
    """Xyce writes .prn column headers with node names UPPERCASED -- V(BKB), not
    V(bkb).  Every lookup here is case-insensitive so deck-side lower-case node
    names work; a missing column raises with the available ones listed rather
    than a bare KeyError."""
    def __init__(self, path):
        self.cols, self.d = read_prn(path)
        self.ix = {c.upper(): i for i, c in enumerate(self.cols)}
        self.t = [r[0] for r in self.d]
    def c(self, name):
        k = name.upper()
        if k not in self.ix:
            raise KeyError("%s not in .prn; have %s" % (name, sorted(self.ix)))
        return [r[self.ix[k]] for r in self.d]
    def at(self, name, tps):
        """value at time tps (ps), linear interpolation"""
        tt, v, x = self.t, self.c(name), tps * 1e-12
        for i in range(1, len(tt)):
            if tt[i] >= x:
                if tt[i] == tt[i - 1]:
                    return v[i]
                f = (x - tt[i - 1]) / (tt[i] - tt[i - 1])
                return v[i - 1] + f * (v[i] - v[i - 1])
        return v[-1]
    def zero_after(self, name, t_from_ps):
        """first sign change of `name` strictly after t_from_ps -> ps"""
        tt, v = self.t, self.c(name)
        x0 = t_from_ps * 1e-12
        for i in range(1, len(tt)):
            if tt[i] <= x0:
                continue
            if v[i - 1] != 0 and (v[i - 1] > 0) != (v[i] > 0):
                f = v[i - 1] / (v[i - 1] - v[i])
                return (tt[i - 1] + f * (tt[i] - tt[i - 1])) * 1e12
        return None
    def t_reach(self, name, level, t_from_ps):
        """first time `name` reaches `level` (rising) after t_from_ps -> ps"""
        tt, v = self.t, self.c(name)
        x0 = t_from_ps * 1e-12
        for i in range(1, len(tt)):
            if tt[i] <= x0:
                continue
            if v[i - 1] < level <= v[i]:
                f = (level - v[i - 1]) / (v[i] - v[i - 1])
                return (tt[i - 1] + f * (tt[i] - tt[i - 1])) * 1e12
        return None
