#!/usr/bin/env python3
"""SKEPTIC re-measurement harness -- written here, importing nothing from
qal/pgcell/.  Same declared protocol as the campaign:
  * devices via qal/sg13lv_compat.sp  (ad/as/pd/ps ZEROED -> LOWER BOUNDS)
  * PSP103 via .hdl + sg13g2_psp103_tt.lib, tt only
  * .OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
  * "settle not switch": inputs held from t=0, SUPPLY stepped 0->V at TSTEP
  * MANDATORY DC-biased companion case in every deck (dvopt amendment A2)
  * 1 F integrators, ALWAYS t0-referenced; never `.measure INTEGRAL`
  * OWN PYMS_VAE_CACHE
"""
import os, re, subprocess, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
PDK   = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/"
         "sg13g2_stdcell.spice")
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_pgcell_SKEPT")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

WP, WN = 1.12, 0.74          # campaign-standard static cell widths (um)
TWN, TWP = 0.74, 1.12        # tgM, the reported pass-device widths
CL    = 2.0                  # fF
EDGE  = 2.0                  # ps
TSTEP = 100.0                # ps
CKPT, LONG = 495.0, 1000.0   # ps after TSTEP
VREF  = 0.7138163            # V, committed delivered rail
CINT  = 0.1                  # fF
VHI   = 1.5                  # V, the fixed n-well supply


def head(sub=None):
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    if sub:
        L.append('.include "%s"' % sub)
    return L


def pdk_subckts(want, path):
    """Copy the PDK's own cells out of sg13g2_stdcell.spice VERBATIM (their own
    widths/lengths).  0.1 fF on each internal node for convergence."""
    cur, buf, ports, got = None, [], [], {}
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
    out = []
    for c in want:
        ports, devs = got[c]
        out.append(".subckt %s %s" % (c, " ".join(ports)))
        nodes = set()
        for p in devs:
            nodes |= {p[1], p[3]}
            out.append(" ".join(p))
        for k, n in enumerate(sorted(n for n in nodes if n not in ports)):
            typs = {("p" if "pmos" in d[5] else "n") for d in devs if n in (d[1], d[3])}
            out.append("CINT%d %s %s %gf" % (k, n, "VDD" if typs == {"p"} else "VSS", CINT))
        out.append(".ends")
    open(path, "w").write("\n".join(out) + "\n")
    return {c: got[c][0] for c in want}


# ---------------------------------------------------------------- primitives
def inv(tag, o, i, rail, gnd, wp=WP, wn=WN, pbulk=None):
    return ["XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u"
            % (tag, o, i, rail, pbulk or rail, wp),
            "XN%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, gnd, gnd, wn)]


def tg(tag, a, y, gn, gp, gnd, pbulk, wn=TWN, wp=TWP):
    """full complementary transmission gate.  `pbulk` is the pass pMOS n-well --
    the DATA path has NO other connection to any supply."""
    return ["XTN%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (tag, a, gn, y, gnd, wn),
            "XTP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, a, gp, y, pbulk, wp)]


def tg_mux2(tag, x, a0, a1, s, rail, gnd, pbulk, cl=CL):
    sb = "sb_" + tag
    return (inv("IS" + tag, sb, s, rail, gnd)
            + tg("0" + tag, a0, x, sb, s, gnd, pbulk)
            + tg("1" + tag, a1, x, s, sb, gnd, pbulk)
            + ["CL%s %s %s %gf" % (tag, x, gnd, cl)])


def tg_xnor2(tag, y, a, b, rail, gnd, pbulk, cl=CL, xor_form=False):
    ab, bb = "ab_" + tag, "bb_" + tag
    s1, s2 = (a, ab) if xor_form else (ab, a)
    return (inv("IA" + tag, ab, a, rail, gnd) + inv("IB" + tag, bb, b, rail, gnd)
            + tg("1" + tag, s1, y, bb, b, gnd, pbulk)
            + tg("2" + tag, s2, y, b, bb, gnd, pbulk)
            + ["CL%s %s %s %gf" % (tag, y, gnd, cl)])


# ------------------------------------------------------------------ metering
def integ(tg_, expr):
    return ["CX%s x%s 0 1" % (tg_, tg_), "BX%s 0 x%s I={ %s }" % (tg_, tg_, expr),
            "RX%s x%s 0 0.01" % (tg_, tg_)]


def companion():
    """dvopt amendment A2 + the per-deck instrument check (1.2 V CMOS inverter,
    committed reference t90 = 57.143 ps)."""
    return (["VSzc s_zc 0 1.2",
             "VIzc i_zc 0 PWL(0 1.2 %gp 1.2 %gp 0)" % (TSTEP, TSTEP + EDGE)]
            + inv("zc", "o_zc", "i_zc", "s_zc", "0")
            + ["CLzc o_zc 0 %gf" % CL]), "o_zc"


def run(fn, lines, timeout=900):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        print("TIMEOUT %s" % fn)
        return None
    w = time.monotonic() - t0
    if r.returncode != 0:
        print("FAIL %s (%.0fs)\n%s" % (fn, w, r.stdout[-2000:]))
        return None
    print("ran %s in %.0fs" % (fn, w), flush=True)
    return p


def read_prn(p):
    hdr, rows = None, []
    for ln in open(p):
        q = ln.split()
        if hdr is None and q and q[0].lower() == "index":
            hdr = [h.upper() for h in q]
            continue
        if hdr and q and q[0][0].isdigit():
            try:
                rows.append([float(x) for x in q])
            except ValueError:
                pass
    return hdr, rows


def col(hdr, rows, name):
    j = hdr.index(name.upper())
    t = hdr.index("TIME")
    return [r[t] for r in rows], [r[j] for r in rows]


def at_t(ts, ys, tp):
    tp *= 1e-12
    for k in range(1, len(ts)):
        if ts[k] >= tp:
            t0, t1 = ts[k - 1], ts[k]
            if t1 == t0:
                return ys[k]
            f = (tp - t0) / (t1 - t0)
            return ys[k - 1] + f * (ys[k] - ys[k - 1])
    return ys[-1]


def ped(ts, ys):
    """the t=0 PEDESTAL of a 1 F integrator -- ALWAYS subtracted"""
    return ys[0]


def t_cross(ts, ys, level, t_from):
    t_from *= 1e-12
    for k in range(1, len(ts)):
        if ts[k] < t_from:
            continue
        if (ys[k - 1] - level) * (ys[k] - level) <= 0 and ys[k] != ys[k - 1]:
            f = (level - ys[k - 1]) / (ys[k] - ys[k - 1])
            return (ts[k - 1] + f * (ts[k] - ts[k - 1]) - t_from) * 1e12
    return None
