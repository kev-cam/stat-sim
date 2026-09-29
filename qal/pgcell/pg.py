#!/usr/bin/env python3
"""PHASE 1 -- pass-gate (transmission-gate) XNOR2/XOR2 and MUX2 on a QAL rail.

Pre-registration: PRE_REGISTERED.json (sha256 6b6d6663df54b5..., written before any
deck of this run existed; qal/pgcell/ held one 0-byte file at that instant).

Protocol inherited VERBATIM from the committed campaign:
  * devices via qal/sg13lv_compat.sp (ad/as/pd/ps ZEROED -> every number a LOWER BOUND)
  * PSP103 via .hdl + sg13g2_psp103_tt.lib, tt only
  * .OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
  * the campaign "qal settle" stimulus: inputs held at their logic level from t=0,
    SUPPLY stepped 0 -> V at TSTEP with a 2 ps edge; the cell settles, not switches
  * the MANDATORY DC-biased companion case in every deck (dvopt AMENDMENT A2: a deck
    of only supply-stepped cases has every node at 0 V at t=0 and will NOT converge)
  * 1 F integrators with an explicit t0 PEDESTAL reference; never .measure INTEGRAL
  * per-bank matched tanks / tank-referenced park / true-ZCS cut for any chain work
"""
import json, os, re, shutil, subprocess, sys, time
from itertools import product

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
PDK   = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/"
         "sg13g2_stdcell.spice")
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_pgcell")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---------------------------------------------------------------- constants
WP, WN  = 1.12, 0.74         # campaign-standard static cell widths (um)
CL      = 2.0                # fF, committed load
EDGE    = 2.0                # ps, committed gate/supply edge
TSTEP   = 100.0              # ps, the supply step instant
TAIL    = 500.0              # ps, committed tail
VREF    = 0.7138163          # V, the committed robust DELIVERED rail
RAILS   = [0.68, 0.7138163, 0.7544, 1.26]
TGW     = {"tgS": (0.37, 0.56), "tgM": (0.74, 1.12), "tgL": (1.48, 2.24)}
SUB     = os.path.join(HERE, "pdk_cells.sp")
CINT    = 0.1                # fF, internal-node cap (census.py convention)


def head(with_sub=False):
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    if with_sub:
        L.append('.include "%s"' % SUB)
    return L


# ---------------------------------------------------- PDK control subcircuits
def emit_pdk_subckts(want=("sg13g2_xnor2_1", "sg13g2_mux2_1", "sg13g2_inv_1",
                          "sg13g2_nand2_1", "sg13g2_o21ai_1")):
    """Copy the PDK's own cells out of sg13g2_stdcell.spice.  Device lines are
    reproduced VERBATIM (so the PDK's own widths and lengths are used); the shim
    ignores ad/as/pd/ps, which is the declared limitation.  A 0.1 fF cap is added
    on each internal node for convergence (qal/sha256/census.py convention)."""
    out, cur, buf, ports = [], None, [], []
    got = {}
    for ln in open(PDK):
        s = ln.strip()
        if s.lower().startswith(".subckt"):
            cur, buf, ports = s.split()[1], [], s.split()[2:]
        elif s.lower().startswith(".ends"):
            if cur in want:
                got[cur] = (ports, buf)
            cur = None
        elif cur is not None and s and not s.startswith("*"):
            p = s.split()
            if len(p) >= 6 and p[0][0].upper() == "X":
                buf.append(p)
    for c in want:
        ports, devs = got[c]
        out.append(".subckt %s %s" % (c, " ".join(ports)))
        nodes = set()
        for p in devs:
            nodes |= {p[1], p[3]}
            out.append(" ".join(p))
        for k, n in enumerate(sorted(n for n in nodes if n not in ports)):
            typs = {("p" if "pmos" in d[5] else "n") for d in devs
                    if n in (d[1], d[3])}
            out.append("CINT%d %s %s %gf" % (k, n, "VDD" if typs == {"p"} else "VSS",
                                             CINT))
        out.append(".ends")
    open(SUB, "w").write("\n".join(out) + "\n")
    return {c: got[c][0] for c in want}


# ------------------------------------------------------------- cell builders
def _inv(tag, o, i, rail, gnd, wp=WP, wn=WN):
    return ["XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, i, rail, rail, wp),
            "XN%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, gnd, gnd, wn)]


def _tg(tag, a, y, gn, gp, rail, gnd, wn, wp, pbulk=None):
    """full complementary transmission gate: nMOS(gate gn, bulk gnd) ||
    pMOS(gate gp, bulk `pbulk`).  NO connection of the DATA path to the rail.

    MEASURED ISSUE, and the reason pbulk is a parameter rather than a constant:
    the naive port of the campaign's static-cell convention puts the pass pMOS
    n-well on the BANK RAIL.  On a QAL rail that ramps from 0, a data input
    already at the predecessor's logic HIGH then sits ~0.7 V ABOVE its own well
    for the whole ramp, i.e. the p+/n-well junction is FORWARD BIASED.  A static
    cell never has this problem (its pMOS source IS the rail).  So both choices
    are built and measured:
        pbulk = rail  -- 'railwell', the naive port
        pbulk = vhi   -- 'fixedwell', the n-well on the global +1.5 V supply that
                         the architecture already carries for the switch drive.
                         No forward bias, at the cost of body effect on |Vt|.
    """
    pb = pbulk or rail
    return ["XTN%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (tag, a, gn, y, gnd, wn),
            "XTP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, a, gp, y, pb, wp)]


def tg_xnor2(tag, y, a, b, rail, gnd, w, cl=CL, xor_form=False, pbulk=None):
    """Y = A XNOR B  (xor_form=True -> Y = A XOR B, the SAME 8 devices with the two
    TG source taps exchanged).  B is the select:
        B=0 -> TG1 conducts (nMOS gate Bbar, pMOS gate B), passes Abar  [RESTORED]
        B=1 -> TG2 conducts (nMOS gate B,    pMOS gate Bbar), passes A  [TRANSPARENT]
    """
    wn, wp = w
    ab, bb = "ab_" + tag, "bb_" + tag
    s1, s2 = (a, ab) if xor_form else (ab, a)
    return (_inv("IA" + tag, ab, a, rail, gnd) + _inv("IB" + tag, bb, b, rail, gnd)
            + _tg("1" + tag, s1, y, bb, b, rail, gnd, wn, wp, pbulk)
            + _tg("2" + tag, s2, y, b, bb, rail, gnd, wn, wp, pbulk)
            + ["CL%s %s %s %gf" % (tag, y, gnd, cl)])


def tg_mux2(tag, x, a0, a1, s, rail, gnd, w, cl=CL, pbulk=None):
    """X = S ? A1 : A0.  BOTH paths transparent -- the data never touches the rail."""
    wn, wp = w
    sb = "sb_" + tag
    return (_inv("IS" + tag, sb, s, rail, gnd)
            + _tg("0" + tag, a0, x, sb, s, rail, gnd, wn, wp, pbulk)
            + _tg("1" + tag, a1, x, s, sb, rail, gnd, wn, wp, pbulk)
            + ["CL%s %s %s %gf" % (tag, x, gnd, cl)])


def o21ai_hand(tag, y, a1, a2, b1, rail, gnd, cl=CL):
    """sk.py cells(kind='o21ai') topology VERBATIM -- the ANCHOR cell."""
    return ["XP0%s nt_%s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, tag, a1, rail, rail, WP),
            "XP1%s %s %s nt_%s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, y, a2, tag, rail, WP),
            "XP2%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, y, b1, rail, rail, WP),
            "XN0%s ns_%s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (tag, tag, a2, gnd, gnd, WN),
            "XN2%s ns_%s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (tag, tag, a1, gnd, gnd, WN),
            "XN1%s %s %s ns_%s %s sg13_lv_nmos w=%gu l=0.13u" % (tag, y, b1, tag, gnd, WN),
            "CX1%s nt_%s %s %gf" % (tag, tag, rail, CINT),
            "CX2%s ns_%s %s %gf" % (tag, tag, gnd, CINT),
            "CL%s %s %s %gf" % (tag, y, gnd, cl)]


# ------------------------------------------------------------------ plumbing
def integ(tg, expr):
    """1 F integrator.  ALWAYS t0-referenced at extraction (pedestal)."""
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def companion():
    """MANDATORY DC-biased companion (dvopt AMENDMENT A2).  Also the per-deck
    instrument check: committed cellcmp2 bc112 = 57.1432 ps, dvopt re-run 57.1429."""
    return (["VSzc s_zc 0 1.2",
             "VIzc i_zc 0 PWL(0 1.2 %gp 1.2 %gp 0)" % (TSTEP, TSTEP + EDGE)]
            + _inv("zc", "o_zc", "i_zc", "s_zc", "0")
            + ["CLzc o_zc 0 %gf" % CL]), "o_zc"


def run(fn, lines, timeout=560):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        print("TIMEOUT %s" % fn); return None
    w = time.monotonic() - t0
    if r.returncode != 0:
        print("FAIL %s (%.0fs)\n%s" % (fn, w, r.stdout[-1500:])); return None
    print("ran %s in %.0fs" % (fn, w))
    return p


def read_prn(p):
    hdr, rows = None, []
    for ln in open(p):
        q = ln.split()
        if hdr is None and q and q[0].lower() == "index":
            hdr = [h.upper() for h in q]; continue
        if hdr and q and q[0][0].isdigit():
            try:
                rows.append([float(x) for x in q])
            except ValueError:
                pass
    return hdr, rows


def col(hdr, rows, name):
    c = hdr.index(name.upper())
    return [r[1] * 1e12 for r in rows], [r[c] for r in rows]


def at_t(ts, y, t):
    for k in range(1, len(ts)):
        if ts[k] >= t:
            f = (t - ts[k - 1]) / (ts[k] - ts[k - 1])
            return y[k - 1] + f * (y[k] - y[k - 1])
    return y[-1]


def cross(ts, y, level, rise=True, t_from=0.0):
    for k in range(1, len(ts)):
        if ts[k] < t_from:
            continue
        a, b = y[k - 1], y[k]
        if (rise and a < level <= b) or ((not rise) and a > level >= b):
            f = (level - a) / (b - a) if b != a else 0.0
            return ts[k - 1] + f * (ts[k] - ts[k - 1])
    return None


def ped(ts, y):
    """t0 pedestal reference for a 1 F integrator."""
    return at_t(ts, y, 0.0)
