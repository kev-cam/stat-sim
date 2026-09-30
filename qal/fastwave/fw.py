#!/usr/bin/env python3
"""qal/fastwave PHASE 1 -- the self-consistent (N_bank, W_switch, L) corner
search for MINIMUM BEAT, on a bank of pass-gate TG-XOR cells.

Pre-registration: PRE_REGISTERED.json, sha256 c23021e9e97089bf60826b118ec44dda
a874dd1f51049df1ae226c062cc05638, written 2026-09-29 19:50:27 -0700, after
DISK_STATE_BEFORE.txt (19:46:26) and BEFORE any deck in this directory.

INHERITED VERBATIM from the committed campaign (qal/lsweep/lsw.py, itself
swsweep/sw_hop_meter.py verbatim, itself gateb's harness verbatim):
  * device shim, PSP103 .hdl + tt lib, .OPTIONS
  * the transfer path  bka --LT-- mid --RT-- sw --[TG]-- bkb  with the
    source-drained park on `sw`
  * the 1:2 n:p transfer-gate width convention wn = W/3, wp = 2W/3
  * VGH = 1.5 V switch drive, 2 ps edges
  * 1 F integrators with a t=0 PEDESTAL always subtracted at extraction
  * LAG_PS = 1.0 ps on every `.measure ... FIND ... AT=` (lsweep's MEASURED
    instrument defect in this Xyce build)
  * the loss-equivalent switch resistance  Ron = Rs * E_switchblock / E_R
    (qal/lsweep/mkresults.py, verbatim)
  * t_level = max(t_hop, t_valid90) with t_valid90 read off the waveform
    (qal/lsweep AMENDMENT A2)

WHAT IS NEW HERE and nowhere else: N_bank (the number of cells per bank), the
TG-XOR cell content, dV = 1.65 V, and a SYMMETRIC source booking CA = the
MEASURED rail capacitance of the same N-cell bank.

Stages:  cbank <N>... | probe <tag> | point <tag> | grid <spec.json>
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or (
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
    "/scratchpad/vae_cache_fastwave")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; not touched) --------------------------
RS_REF   = 10.0      # ohm, committed series R  (MEASURED not to be the limiter)
VGH      = 1.5       # V, committed switch-drive / n-well supply
WP, WN   = 1.12, 0.74   # um, campaign-standard cell inverter widths
TGW      = (0.74, 1.12) # um, pgcell tgM transmission-gate (wn, wp)
CL       = 2.0       # fF, committed per-output load
T0       = 50.0      # ps, the transfer switch closes
EDGE     = 2.0       # ps, committed gate edge
LAG_PS   = 1.0       # ps, MEASURED .measure-FIND lag in this Xyce build
PARK_W   = 1.0       # um -- DEVIATION, see RESULTS.json D_DEVIATIONS

# ---- this run's own constants (pre-registered) -----------------------------
DV       = 1.65      # V, pre-charge.  Vtn + |Vtp| = 0.9642 V is the restoring floor
VINHI    = 1.20      # V, the FIXED cell-input HIGH reference (pre-registered C)
TAIL     = 400.0     # ps, post-open settle window

# The four XOR input vectors, cycled over the bank.  want = A xor B.
#
# AMENDMENT A1 (AMENDMENT.md), forced by cb_n2.cir.prn and applied BEFORE any
# sweep row: a TG-XOR2 has two STRUCTURALLY DIFFERENT paths (qal/pgcell/pg.py).
# In xor_form,  B = 1 -> TG2 conducts -> passes `ab`, the input inverter's
# output, which IS on the bank rail            -> RESTORED  (waits for the rail)
#              B = 0 -> TG1 conducts -> passes `a`, the raw input, which is not
#                                                   -> TRANSPARENT (rail-independent)
# The original order put two B=0 cells in the N=2 bank, so NEITHER waited for the
# rail and the smallest bank -- the corner this whole run is aimed at -- would
# have reported a near-zero settle time as an artefact.  MEASURED proof:
# cb_n2.cir.prn has V(y1) = 0.984 V while its own rail V(bkb) is 0.000 V.
#
# Reordered so the RESTORED pair comes FIRST and the binding cell is present at
# every N.  This makes the small-N rows HARSHER, not easier.
VEC = [(0, 1),   # RESTORED,    want 1  -- THE BINDING CELL (must follow rail UP)
       (1, 1),   # RESTORED,    want 0
       (1, 0),   # TRANSPARENT, want 1
       (0, 0)]   # TRANSPARENT, want 0
PATH = {(0, 1): "RESTORED", (1, 1): "RESTORED",
        (1, 0): "TRANSPARENT", (0, 0): "TRANSPARENT"}


MIX = "data"   # "data" = all four vectors cycled (data-representative)
               # "restored" = ONLY the two RESTORED vectors, so the N axis can
               #   be swept at a FIXED 100%-restored mix.  Needed because the
               #   data mix makes N=2 100% restored and N>=4 only 50% restored,
               #   which CONFOUNDS N with the mix (AMENDMENT A7).
_RESTORED_VEC = [(0, 1), (1, 1)]


def vecs(n, mix=None):
    v = _RESTORED_VEC if (mix or MIX) == "restored" else VEC
    return [v[i % len(v)] for i in range(n)]


def sw_widths(total_um):
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=PARK_W)


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17"]


def integ(tg, expr):
    """1 F integrator.  ALWAYS t0-referenced at extraction (pedestal)."""
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


# ------------------------------------------------------- the TG-XOR bank cell
def xor_cell(i, a, b, rail, gnd):
    """qal/pgcell/pg.py tg_xnor2(xor_form=True) with pbulk = vhi ('fixedwell'),
    widths tgM.  8 devices, data-path depth 1.  Y = A xor B.

        IA: ab = NOT a      IB: bb = NOT b      (the only rail-connected devices)
        TG1: data ab_or_a -> y, nMOS gate bb, pMOS gate b
        TG2: data a_or_ab -> y, nMOS gate b,  pMOS gate bb
    xor_form exchanges the two TG source taps, so TG1 passes `a` and TG2 `ab`.
    The DATA PATH NEVER TOUCHES THE RAIL -- that is the speed reason this cell
    was chosen (PRE_REGISTERED.json C.why_4).
    """
    t = str(i)
    wn, wp = TGW
    ab, bb, y = "ab" + t, "bb" + t, "y" + t
    an, bn = "a" + t, "b" + t
    L = [
        # the two input inverters -- pMOS source AND bulk on the bank rail
        "XPIA%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (t, ab, an, rail, rail, WP),
        "XNIA%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, ab, an, gnd, gnd, WN),
        "XPIB%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (t, bb, bn, rail, rail, WP),
        "XNIB%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, bb, bn, gnd, gnd, WN),
        # TG1: passes `a`  (xor form), gates bb / b
        "XTN1%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, an, bb, y, gnd, wn),
        "XTP1%s %s %s %s vhi sg13_lv_pmos w=%gu l=0.13u" % (t, an, bn, y, wp),
        # TG2: passes `ab`, gates b / bb
        "XTN2%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, ab, bn, y, gnd, wn),
        "XTP2%s %s %s %s vhi sg13_lv_pmos w=%gu l=0.13u" % (t, ab, bb, y, wp),
        "CL%s %s %s %gf" % (t, y, gnd, CL),
        # the input sources ARE the metering points for the input-side charge
        "VA%s %s %s %g" % (t, an, gnd, VINHI if a else 0.0),
        "VB%s %s %s %g" % (t, bn, gnd, VINHI if b else 0.0),
    ]
    return L


def bank(n, rail="bkb", gnd="gcell"):
    L = ["VMG %s 0 0" % gnd]
    for i, (a, b) in enumerate(vecs(n)):
        L += xor_cell(i, a, b, rail, gnd)
    return L


def cellsup(n):
    """Total current the BANK draws from the rail, by KCL: everything that does
    not come from the rail comes from the metered ground or an input source."""
    return "I(VMG)+" + "+".join("I(VA%d)+I(VB%d)" % (i, i) for i in range(n))


def companion():
    """MANDATORY DC-biased companion (dvopt AMENDMENT A2): a deck of only
    supply-stepped cases has every node at 0 V at t=0 and will not converge.
    Doubles as the PER-DECK instrument check -- this is the 1.12/0.74 inverter
    into 2 fF at 1.2 V whose committed t90 is 57.143 ps (qal/fcrit/cmos.cir.mt0
    T90R2, digit-reproduced by this run's INSTRUMENT_CHECK.json)."""
    return ["VSzc s_zc 0 1.2",
            "VIzc i_zc 0 PWL(0 0 %gp 0 %gp 1.2)" % (T0, T0 + EDGE),
            "XPzc o_zc i_zc s_zc s_zc sg13_lv_pmos w=%gu l=0.13u" % WP,
            "XNzc o_zc i_zc 0 0 sg13_lv_nmos w=%gu l=0.13u" % WN,
            "CLzc o_zc 0 %gf" % CL]


def steps(t_est_ps):
    """Time resolution.  100+ points per predicted half-cycle, with a 0.02 ps
    floor so a 400 ps settle tail at L = 0.3 nH does not become 10^5 steps."""
    m = max(0.02, min(0.25, t_est_ps / 100.0))
    return m, m


def t_est(l_nh, c_ser_fF):
    """DERIVED pi*sqrt(LC).  Used ONLY to size timesteps and run lengths -- the
    true zero is always RE-PROBED (the analytic value read 33% early once)."""
    return math.pi * math.sqrt((l_nh * 1e-9) * (c_ser_fF * 1e-15)) * 1e12


# -------------------------------------------------------- stage: bank capacitance
def cbank_deck(n):
    """MEASURE the bank's rail capacitance: ramp the rail slowly and integrate
    the current the bank draws.  C_secant(V) = Q(V)/V is the charge-equivalent
    capacitance, which is the right one for setting a charge-transfer partner;
    C_diff = dQ/dV is reported alongside."""
    TR = 4000.0
    L = head() + ["VS bkb 0 PWL(0 0 %gp %g)" % (TR, DV), "VHI vhi 0 %g" % VGH]
    L += bank(n)
    # AMENDMENT A4: the rail charge is metered AT THE RAIL SOURCE.  The KCL form
    # `I(VMG) + sum I(VA)+I(VB)` that this deck first used is CONTAMINATED -- see
    # AMENDMENT.md A4 and diag_n4.cir: a TRANSPARENT TG-XOR cell draws 176 fC
    # from its own A input through a pass-gate crowbar that never touches the
    # rail, which inflated an N=4 bank from 51.5 fF to 216 fF.
    L += integ("qvs", "-I(VS)") + integ("qbk", cellsup(n))
    L += integ("qmg", "I(VMG)") + integ("qhi", "I(VHI)")
    L += [".print tran V(bkb) V(xqvs) V(xqbk) V(xqmg) V(xqhi) " +
          " ".join("V(y%d)" % i for i in range(n)),
          ".tran %gp %gp 0 %gp" % (TR / 2000.0, TR, TR / 1000.0), ".end"]
    return L


def cbank_extract(prn, n):
    hdr, rows = read_prn(prn)
    iv, iq = hdr.index("V(BKB)"), hdr.index("V(XQVS)")
    iqk, iqm = hdr.index("V(XQBK)"), hdr.index("V(XQMG)")
    q0 = rows[0][iq]
    pts = [(r[iv], (r[iq] - q0) * 1e15) for r in rows if r[iv] >= 0]
    out = {}
    for vt in (0.60, 0.80, 0.9642, 1.00, 1.20, 1.40, DV):
        prev = None
        for v, q in pts:
            if prev and prev[0] <= vt <= v:
                f = (vt - prev[0]) / (v - prev[0]) if v != prev[0] else 0.0
                qq = prev[1] + f * (q - prev[1])
                out["C_secant_at_%.4fV_fF" % vt] = qq / vt
                break
            prev = (v, q)
    # differential capacitance around the level-restoring floor
    lo, hi = 0.90, 1.10
    ql = qh = None
    prev = None
    for v, q in pts:
        if prev and prev[0] <= lo <= v:
            ql = prev[1] + (lo - prev[0]) / (v - prev[0]) * (q - prev[1])
        if prev and prev[0] <= hi <= v:
            qh = prev[1] + (hi - prev[0]) / (v - prev[0]) * (q - prev[1])
        prev = (v, q)
    if ql is not None and qh is not None:
        out["C_diff_0p9_to_1p1V_fF"] = (qh - ql) / (hi - lo)
    out["N"] = n
    out["Q_total_at_dV_fC"] = pts[-1][1]
    out["C_secant_dV_fF"] = out.get("C_secant_at_%.4fV_fF" % DV)
    out["_metered"] = ("rail charge from -I(VS) AT THE RAIL SOURCE (AMENDMENT A4)")
    # reported for the record only: the contaminated KCL form and the ground
    # return, so the size of the pass-gate crowbar is visible and not hidden
    out["Q_KCL_contaminated_at_dV_fC"] = (rows[-1][iqk] - rows[0][iqk]) * 1e15
    out["Q_ground_return_at_dV_fC"] = (rows[-1][iqm] - rows[0][iqm]) * 1e15
    out["crowbar_excess_at_dV_fC"] = (out["Q_KCL_contaminated_at_dV_fC"]
                                      - out["Q_total_at_dV_fC"])
    return out


# ----------------------------------------------------------- the hop/probe decks
def _common(n, l_nh, total_um, ca_fF, rs, t_open_ps, tend_ps, probe):
    w = sw_widths(total_um)
    L = head() + [
        ".param LT=%gn RS=%g CA=%gf" % (l_nh, rs, ca_fF),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
    ]
    if probe:
        L += ["VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)"
              % (T0 - EDGE, T0, VGH, tend_ps * 2, VGH),
              "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
              % (VGH, T0 - EDGE, VGH, T0, tend_ps * 2),
              "VPK pk 0 0"]
    else:
        L += ["VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (T0 - EDGE, T0, VGH, t_open_ps, VGH, t_open_ps + EDGE),
              "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (VGH, T0 - EDGE, VGH, T0, t_open_ps, t_open_ps + EDGE, VGH),
              "VPK pk 0 PWL(0 0 %gp 0 %gp %g)"
              % (t_open_ps + EDGE, t_open_ps + 2 * EDGE, VGH)]
    L += ["XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
          "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
          "XPK  sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % w["park"],
          "LT bka mid {LT}", "RT mid sw {RS}"]
    L += bank(n) + companion()
    return L


def probe_lines(n, l_nh, total_um, ca_fF, rs=RS_REF):
    cser = ca_fF / 2.0
    te = t_est(l_nh, cser)
    tend = T0 + 4.0 * te
    ps, ms = steps(te)
    L = _common(n, l_nh, total_um, ca_fF, rs, None, tend, True)
    L += [".ic V(bka)=%g V(bkb)=0" % DV,
          ".print tran I(LT) V(bkb) V(bka) V(sw) V(o_zc)",
          ".tran %gp %gp 0 %gp" % (ps, tend, ms), ".end"]
    return L, dict(tend=tend, t_est=te, pstep=ps, mstep=ms)


def hop_lines(n, l_nh, total_um, ca_fF, t_half_ps, rs=RS_REF, tail=TAIL):
    t_open = T0 + t_half_ps
    tend = t_open + tail
    te = t_est(l_nh, ca_fF / 2.0)
    ps, ms = steps(te)
    L = _common(n, l_nh, total_um, ca_fF, rs, t_open, tend, False)
    sup = cellsup(n)
    L += integ("qlt", "I(LT)") + integ("ea", "V(bka)*I(LT)")
    L += integ("eb", "V(bkb)*I(LT)") + integ("esw", "V(sw)*I(LT)")
    L += integ("er", "I(LT)*I(LT)*%g" % rs)
    L += integ("qbk", sup) + integ("ebk", "V(bkb)*(%s)" % sup)
    L += integ("qgt", "-I(VGT)") + integ("qgtp", "-I(VGTP)")
    L += integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)")
    L += integ("ehi", "-%g*I(VHI)" % VGH)
    L += [".ic V(bka)=%g V(bkb)=0" % DV,
          ".tran %gp %gp 0 %gp" % (ps, tend, ms)]
    g = lambda t: t + LAG_PS
    L += [".measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp" % (T0, tend),
          ".measure tran VBEND FIND V(bkb) AT=%.6fp" % g(tend - 5),
          ".measure tran VAEND FIND V(bka) AT=%.6fp" % g(tend - 5),
          ".measure tran IPK   MAX I(LT) FROM=0 TO=%gp" % tend,
          ".measure tran TIPK  WHEN I(LT)=0 FROM=%gp TO=%gp FALL=1" % (T0, tend),
          ".measure tran IZ    FIND I(LT) AT=%.6fp" % g(t_open),
          ".measure tran VBOPEN FIND V(bkb) AT=%.6fp" % g(t_open),
          ".measure tran VSWPK MAX V(sw) FROM=0 TO=%gp" % tend,
          ".measure tran T90ZC WHEN V(o_zc)=1.08 RISE=1"]
    cks = [("Z", 0.5), ("B", t_open), ("C", t_open + 3.5 * EDGE), ("D", tend - 5.0)]
    for tg in ["qlt", "ea", "eb", "esw", "er", "qbk", "ebk", "qgt", "qgtp",
               "egt", "ehi"]:
        for nm, tt in cks:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                     % (tg.upper(), nm, tg, g(tt)))
    for i in range(n):
        L.append(".measure tran Y%dB FIND V(y%d) AT=%.6fp" % (i, i, g(t_open)))
        L.append(".measure tran Y%dE FIND V(y%d) AT=%.6fp" % (i, i, g(tend - 5.0)))
    L.append(".print tran V(bka) V(bkb) V(sw) I(LT) V(o_zc) "
             + " ".join("V(y%d)" % i for i in range(n))
             + " V(xea) V(xesw) V(xer) V(xeb) V(xqlt)")
    L.append(".end")
    return L, dict(t_open=t_open, tend=tend, cks=dict(cks), pstep=ps, mstep=ms)


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=560, want_tend_ps=None, _div=1):
    """Run one deck.  AMENDMENT A8: if the solver STALLS -- returns non-zero, or
    returns a .prn that stops short of the requested tend -- the deck is retried
    with the time resolution refined 4x and then 16x, and NOTHING ELSE CHANGED.

    MEASURED justification (try_s4.cir / try_s16.cir / try_reltol4.cir): nine of
    the sixty-eight sweep points stalled at exactly t = 50.000 ps, the
    transfer-gate close, all of them large-bank/wide-switch combinations
    (N = 16 at W = 60; N = 4 at L <= 1 nH, W = 60; N = 8 at L = 1 nH, W >= 120).
    Refining the step 4x converges; so does relaxing RELTOL from 1e-6 to 1e-4,
    and the two agree on every headline to <= 4e-7 relative.  The FINER STEP is
    the one used, because it leaves the committed .OPTIONS tolerances untouched
    and is strictly MORE accurate, not less."""
    path = os.path.join(HERE, fn)
    if _div > 1:
        lines = [(re.sub(r"^\.tran (\S+)p (\S+)p 0 (\S+)p",
                         lambda m: ".tran %gp %sp 0 %gp"
                         % (float(m.group(1)) / _div, m.group(2),
                            float(m.group(3)) / _div), l)
                  if l.startswith(".tran") else l) for l in lines]
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout, timeout
    wall = time.monotonic() - t0
    if "build_vae_so" in r.stdout:
        sys.stderr.write("WARNING %s triggered a PyMS build (cold geometry)\n" % fn)
    ok = os.path.exists(path + ".prn") and r.returncode == 0
    if ok and want_tend_ps is not None:
        try:
            _, rr = read_prn(path + ".prn")
            ok = bool(rr) and rr[-1][1] * 1e12 >= 0.98 * want_tend_ps
        except Exception:                                              # noqa
            ok = False
    if not ok:
        if _div < 16:
            p2, m2, w2 = run(fn, lines, timeout, want_tend_ps, _div * 4)
            return p2, "stalled at div=%d, retried: %s" % (_div, m2), wall + w2
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l.lower() or "bort" in l.lower())[:200]
        return None, ("XYCE STALL %s (%.1fs, div=%d): %s"
                      % (fn, wall, _div, err or "solver stopped short")), wall
    return path, "ok %.1fs%s" % (wall, "" if _div == 1 else " div=%d" % _div), wall


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


def zero_after_peak(prn):
    """The TRUE current zero: the first DOWNWARD zero crossing of I(LT) after
    the current peak, LINEARLY INTERPOLATED (committed rule + lsweep's G0c
    refinement).  Re-probed at EVERY point -- never reused, never predicted."""
    hdr, rows = read_prn(prn)
    it, ii = 1, hdr.index("I(LT)")
    ts = [(r[it] * 1e12, r[ii]) for r in rows if r[it] * 1e12 >= T0]
    ipk, tpk = max(((i, t) for t, i in ts), key=lambda x: x[0])
    prev = None
    for t, i in ts:
        if t <= tpk:
            prev = (t, i)
            continue
        if prev and prev[1] > 0 >= i:
            f = prev[1] / (prev[1] - i) if prev[1] != i else 0.0
            tz = prev[0] + f * (t - prev[0])
            return tz - T0, ipk * 1e6, tpk
        prev = (t, i)
    return None, ipk * 1e6, tpk


def rpeak_from_prn(prn):
    """INDEPENDENT instantaneous switch resistance at the current peak:
    R = (V(sw) - V(bkb)) / I(LT).  A cross-check on the loss-equivalent Ron."""
    hdr, rows = read_prn(prn)
    isw, ib, ii = hdr.index("V(SW)"), hdr.index("V(BKB)"), hdr.index("I(LT)")
    best = None
    for r in rows:
        if r[1] * 1e12 < T0:
            continue
        if best is None or r[ii] > best[ii]:
            best = r
    if best is None or abs(best[ii]) < 1e-9:
        return None
    return (best[isw] - best[ib]) / best[ii]


def timing_from_prn(prn, n, vbend, trip_at, only=None):
    """The MEASURED end-to-end times.  t_validXX: the first instant after which
    ALL n outputs stay within XX% of the INSTANTANEOUS rail, referenced to the
    switch close.  t_commit: the same under the fcrit FUNCTIONAL criterion --
    every output on the correct side of the receiver's MEASURED trip at the
    receiver's DELIVERED rail by the noise budget.  NEITHER is composed."""
    hdr, rows = read_prn(prn)
    ib = hdr.index("V(BKB)")
    sel = [i for i in range(n) if only is None or PATH[vecs(n)[i]] == only]
    iy = {i: hdr.index("V(Y%d)" % i) for i in sel}
    want = [a ^ b for a, b in vecs(n)]
    if not sel:
        return dict(t_rail90_ps=None, t_valid80_ps=None, t_valid90_ps=None,
                    t_valid95_ps=None, t_commit_fcrit_ps=None)
    out = {}
    tr = None
    for r in rows:
        t = r[1] * 1e12
        if t < T0:
            continue
        tr = (t if tr is None else tr) if r[ib] >= 0.90 * vbend else None
    out["t_rail90_ps"] = (tr - T0) if tr is not None else None
    for th, nm in ((0.80, 80), (0.90, 90), (0.95, 95)):
        f = None
        for r in rows:
            t = r[1] * 1e12
            if t < T0:
                continue
            vb = r[ib]
            ok = vb > 1e-6 and all(
                ((r[iy[i]] / vb) >= th) if want[i] else ((1.0 - r[iy[i]] / vb) >= th)
                for i in sel)
            f = (t if f is None else f) if ok else None
        out["t_valid%d_ps" % nm] = (f - T0) if f is not None else None
    # fcrit FUNCTIONAL: trip interpolated at the INSTANTANEOUS rail, NB both ways
    NB = 0.019323
    f = None
    for r in rows:
        t = r[1] * 1e12
        if t < T0:
            continue
        vb = r[ib]
        if vb <= 0.2:
            f = None
            continue
        tv = trip_at(vb)
        ok = all((r[iy[i]] >= tv + NB) if want[i] else (r[iy[i]] <= tv - NB)
                 for i in sel)
        f = (t if f is None else f) if ok else None
    out["t_commit_fcrit_ps"] = (f - T0) if f is not None else None
    # AMENDMENT A6: the rail and the delivered LOGIC LEVEL are DIFFERENT
    # quantities, separated by the bank's own internal charge redistribution
    # (MEASURED in diag_hop.cir: between the rail peak and the tail, 10.3 fC
    # leaves the rail node and is attributed 4.34 fC to the bank's internal
    # nodes via the metered ground, 4.15 fC into the vhi n-well supply, and
    # 1.27 fC onto the output load).  A CASCADE is fed the LEVEL, not the rail,
    # so the level at the instant of use is reported at every checkpoint.
    hi = [i for i in sel if want[i]]
    lo = [i for i in sel if not want[i]]
    def state(t):
        b = min(rows, key=lambda x: abs(x[1] * 1e12 - t))
        return dict(t_ps=b[1] * 1e12 - T0, rail=b[ib],
                    v_hi_min=(min(b[iy[i]] for i in hi) if hi else None),
                    v_lo_max=(max(b[iy[i]] for i in lo) if lo else None))
    marks = {}
    if out["t_commit_fcrit_ps"] is not None:
        marks["at_commit"] = state(T0 + out["t_commit_fcrit_ps"])
    if out["t_valid90_ps"] is not None:
        marks["at_valid90"] = state(T0 + out["t_valid90_ps"])
    marks["at_rail_peak"] = state(max(rows, key=lambda x: x[ib])[1] * 1e12)
    marks["at_tail"] = state(rows[-1][1] * 1e12 - 5.0)
    out["levels"] = marks
    return out


# --------------------------------------------------- the MEASURED receiver trip
_TRIP = None


def trip_at(vdd):
    """qal/fcrit/TRIP.json, receiver S (the 1.12/0.74 cell) -- the MEASURED
    decision threshold at 27 delivered rails, linearly interpolated.  The trip
    FRACTION is NOT a constant (0.7281 at 0.20 V falling to 0.5179 at 1.50 V),
    so it is interpolated at the row's own rail and never assumed."""
    global _TRIP
    if _TRIP is None:
        d = json.load(open("/usr/local/src/stat-sim/qal/fcrit/TRIP.json"))["S"]["rows"]
        _TRIP = sorted((v["vdd"], v["trip_V"]) for v in d.values())
    if vdd <= _TRIP[0][0]:
        return _TRIP[0][1] * vdd / _TRIP[0][0]
    if vdd >= _TRIP[-1][0]:
        return _TRIP[-1][1] * vdd / _TRIP[-1][0]
    for k in range(1, len(_TRIP)):
        if _TRIP[k][0] >= vdd:
            (v0, t0_), (v1, t1_) = _TRIP[k - 1], _TRIP[k]
            return t0_ + (vdd - v0) / (v1 - v0) * (t1_ - t0_)
    return _TRIP[-1][1]


# ------------------------------------------------------------------ extractor
def extract(tag, n, l_nh, total_um, ca_fF, t_half_ps, mt0, prn, rs=RS_REF,
            tail=TAIL, probe_meta=None):
    m = parse_mt0(mt0)
    f = 1e15

    def ck(tg):
        z = m["%s_Z" % tg.upper()]
        return [(m["%s_%s" % (tg.upper(), p)] - z) * f for p in ("B", "C", "D")]

    # AMENDMENT A5: the pedestal-heavy path integrators come from the WAVEFORM
    t_open_ = T0 + t_half_ps
    wav = wave_ledger(prn, t_open_, t_open_ + 3.5 * EDGE, T0 + t_half_ps + tail - 5.0)
    mt0_ck = dict(qlt=ck("qlt"), ea=ck("ea"), eb=ck("eb"),
                  esw=ck("esw"), er=ck("er"))
    qlt = [wav["qlt_B"], wav["qlt_C"], wav["qlt_D"]]
    ea = [wav["ea_B"], wav["ea_C"], wav["ea_D"]]
    eb = [wav["eb_B"], wav["eb_C"], wav["eb_D"]]
    esw = [wav["esw_B"], wav["esw_C"], wav["esw_D"]]
    er = [wav["er_B"], wav["er_C"], wav["er_D"]]
    qbk, ebk = ck("qbk"), ck("ebk")
    qgt, qgtp, egt, ehi = ck("qgt"), ck("qgtp"), ck("egt"), ck("ehi")
    vbe, vbo, vae = m["VBEND"], m["VBOPEN"], m["VAEND"]

    # ---- the three self-consistency quantities, ALL MEASURED
    e_R = er[0]                    # I^2*Rs dissipated TO THE OPEN (checkpoint B)
    e_swblk = esw[0] - eb[0]       # switch channel drop + sw-node storage
    # Ron = Rs * E_switchblock / E_R   (qal/lsweep/mkresults.py, VERBATIM)
    ron = (rs * e_swblk / e_R) if e_R else None
    cser = ((t_half_ps * 1e-12) / math.pi) ** 2 / (l_nh * 1e-9) * 1e15
    z0 = math.sqrt((l_nh * 1e-9) / (cser * 1e-15))
    q = (z0 / (rs + ron)) if ron else None
    ron_pk = rpeak_from_prn(prn)
    q_pk = (z0 / (rs + ron_pk)) if ron_pk and ron_pk > 0 else None

    va_open = DV - qlt[0] / ca_fF
    # ---- per-gate settling and the VALUE check
    vv = vecs(n)
    want = [a ^ b for a, b in vv]
    path = [PATH[v] for v in vv]
    s_end, s_open, val = {}, {}, {}
    for i in range(n):
        ve, vb_ = m["Y%dE" % i], m["Y%dB" % i]
        s_end["y%d" % i] = 100.0 * ((ve / vbe) if want[i] else (1.0 - ve / vbe))
        s_open["y%d" % i] = (100.0 * ((vb_ / vbo) if want[i] else (1.0 - vb_ / vbo))
                             if abs(vbo) > 1e-6 else None)
        tv = trip_at(vbe)
        val["y%d" % i] = dict(want=want[i], path=path[i], v_end=ve,
                              trip_at_rail=tv, correct=bool((ve > tv) == bool(want[i])),
                              margin_mV=1000.0 * (ve - tv if want[i] else tv - ve))

    tim = timing_from_prn(prn, n, vbe, trip_at)
    tim_r = timing_from_prn(prn, n, vbe, trip_at, only="RESTORED")
    t_settle90 = tim["t_valid90_ps"]
    t_level = (max(t_half_ps, t_settle90) if t_settle90 is not None else None)
    t_level_f = (max(t_half_ps, tim["t_commit_fcrit_ps"])
                 if tim["t_commit_fcrit_ps"] is not None else None)

    # ---- instrument closure (K5)
    e_outa = 0.5 * ca_fF * (DV * DV - vae ** 2)
    closQ = ((qlt[2] - ca_fF * (DV - vae)) / (ca_fF * (DV - vae)) * 100
             if abs(DV - vae) > 1e-9 else float("nan"))
    closE = (ea[2] - e_outa) / e_outa * 100 if e_outa else float("nan")
    ident = wav["identity_B"]

    # ---- the .mt0 ledger retained as the INDEPENDENT cross-check
    d_ea = ((abs(mt0_ck["ea"][0] - ea[0]) / abs(ea[0]) * 100)
            if ea[0] else None)

    row = dict(
        tag=tag, N=n, L_nH=l_nh, total_um=total_um, ca_fF=ca_fF, dv=DV,
        mix=MIX, vgh=VGH,
        rs_ohm=rs, vinhi=VINHI, tail_ps=tail, **{("w_" + k): v for k, v
                                                 in sw_widths(total_um).items()},
        t_hop_ps=t_half_ps, t_hop_pred_ps=t_est(l_nh, ca_fF / 2.0),
        C_ser_eff_fF=cser, Z0_ohm=z0,
        Ron_sw_eff_ohm=ron, Q_measured=q,
        Ron_at_Ipk_ohm=ron_pk, Q_at_Ipk=q_pk,
        IPK_uA=m["IPK"] * 1e6, IZ_uA=m["IZ"] * 1e6,
        VBEND=vbe, VBOPEN=vbo, VBPK=m["VBPK"], VAEND=vae, VA_open=va_open,
        VSWPK=m.get("VSWPK"),
        t_rail90_ps=tim["t_rail90_ps"], t_valid80_ps=tim["t_valid80_ps"],
        t_valid90_ps=tim["t_valid90_ps"], t_valid95_ps=tim["t_valid95_ps"],
        t_commit_fcrit_ps=tim["t_commit_fcrit_ps"],
        levels=tim["levels"], levels_RESTORED_only=tim_r.get("levels"),
        VB_at_commit=(tim["levels"].get("at_commit") or {}).get("rail"),
        V_hi_min_at_commit=(tim["levels"].get("at_commit") or {}).get("v_hi_min"),
        V_hi_min_at_tail=(tim["levels"].get("at_tail") or {}).get("v_hi_min"),
        V_lo_max_at_tail=(tim["levels"].get("at_tail") or {}).get("v_lo_max"),
        t_settle_ps=(None if t_settle90 is None else t_settle90 - t_half_ps),
        t_level_ps=t_level, t_level_fcrit_ps=t_level_f,
        E_hop_raw_toB_fJ=ea[0], E_R_toB_fJ=e_R, E_switchblock_toB_fJ=e_swblk,
        E_toB_fJ=eb[0], E_into_cells_D_fJ=ebk[2],
        Q_through_L_B_fC=qlt[0], Q_through_L_D_fC=qlt[2],
        ledger_waveform=wav, ledger_mt0=mt0_ck,
        mt0_vs_waveform_ea_pct=d_ea,
        identity_at_B_mt0_fJ=(mt0_ck["ea"][0] - mt0_ck["esw"][0]
                              - mt0_ck["er"][0]),
        Q_gate_drive_fC=qgt[2] + qgtp[2], E_gate_drive_fJ=egt[2],
        E_vhi_fJ=ehi[2], rails_net_fJ=egt[2] + ehi[2],
        settling_end_pct=s_end, settling_open_pct=s_open,
        settling_end_min_pct=min(s_end.values()),
        cell_path=dict(("y%d" % i, path[i]) for i in range(n)),
        n_restored=sum(1 for p_ in path if p_ == "RESTORED"),
        t_valid90_RESTORED_only_ps=tim_r["t_valid90_ps"],
        t_commit_fcrit_RESTORED_only_ps=tim_r["t_commit_fcrit_ps"],
        value_check=val,
        value_all_correct=all(v["correct"] for v in val.values()),
        value_min_margin_mV=min(v["margin_mV"] for v in val.values()),
        closure_Q_pct=closQ, closure_E_pct=closE, identity_at_B_fJ=ident,
        T90ZC_companion_ps=(m["T90ZC"] * 1e12 - T0 if "T90ZC" in m else None),
        probe=probe_meta)

    # ------------------------------------------------ the PRE-REGISTERED gates
    # K1/K2 EXACTLY AS PRE-REGISTERED (on VBEND, the tail rail).  The two other
    # defensible instants are reported alongside so the verdict can be seen NOT
    # to depend on the choice: `_peak` is the most GENEROUS reading available and
    # `_level` the strictest (the level a cascade is actually handed).
    k1 = vbe >= 0.9642
    k2 = vbe >= 0.60 * DV
    vhi_c = row["V_hi_min_at_commit"]
    row["K1_on_PEAK_rail_most_generous"] = ("PASS" if m["VBPK"] >= 0.9642
                                            else "FAIL")
    row["K1_on_DELIVERED_LEVEL_strictest"] = (
        "PASS" if (vhi_c is not None and vhi_c >= 0.9642) else "FAIL")
    row["K1_on_LEVEL_at_tail"] = (
        "PASS" if (row["V_hi_min_at_tail"] is not None
                   and row["V_hi_min_at_tail"] >= 0.9642) else "FAIL")
    row["restoring_margin_mV_on_level_at_commit"] = (
        None if vhi_c is None else 1000.0 * (vhi_c - 0.9642))
    k3 = va_open <= 0.1478 * DV
    # AMENDMENT A2: K4 is the FUNCTIONAL criterion (qal/fcrit, committed 0ec8de5),
    # not the 90%-of-instantaneous-rail bar, which a TRANSPARENT pass-gate cell
    # fails HARDER the better the delivered rail is.  The 90% reading is still
    # reported on every row (settling_end_min_pct, t_valid90_ps, t_level_ps).
    k4 = row["value_all_correct"] and row["t_commit_fcrit_ps"] is not None
    k4_committed_90pct_bar = (min(s_end.values()) >= 90.0
                              and row["value_all_correct"])
    k5 = (abs(m["IZ"] * 1e6) <= 1.0 and abs(closQ) <= 1.0 and abs(closE) <= 1.0
          and abs(ident) <= 0.02 and (d_ea is None or d_ea <= 1.0))
    fails = [n_ for n_, ok in (("K1_restoring", k1), ("K2_swing", k2),
                               ("K3_drain", k3), ("K4_settle", k4),
                               ("K5_instrument", k5)) if not ok]
    row.update(K1_restoring_rail=("PASS" if k1 else "FAIL"),
               K2_swing=("PASS" if k2 else "FAIL"),
               K3_rail_drain=("PASS" if k3 else "FAIL"),
               K4_settle_and_value=("PASS" if k4 else "FAIL"),
               K4_alt_committed_90pct_bar=("PASS" if k4_committed_90pct_bar
                                           else "FAIL"),
               K5_instrument=("PASS" if k5 else "FAIL"),
               FEASIBLE=("YES" if not fails else "NO"), fails=fails)
    return row


def wave_ledger(prn, t_open, t_C, t_D):
    """AMENDMENT A5 -- the ledger is read from the WAVEFORM at full .prn
    precision, NOT from the .mt0.

    MEASURED reason: a 1 F integrator shunted by the committed 0.01 ohm resistor
    sits at a DC operating point V = R * I(t=0), and at t = 0 this deck has
    41.2 nA of leakage through the transfer path, so the `ea`/`esw` integrators
    carry a t=0 PEDESTAL of 6.8019e-10 V-equivalent = 680187 fJ against a 38 fJ
    signal -- a ratio of 1.8e4.  The .mt0 prints 7 significant digits, so after
    the mandatory pedestal subtraction its absolute resolution is ~0.1 fJ.  The
    path identity `ea - esw - er` is a difference of two nearly equal
    pedestal-heavy numbers and is therefore DESTROYED by that quantisation: the
    .mt0 reports 0.0935 fJ where the .prn (9 significant digits) reports
    0.00050414 fJ, 40x INSIDE the pre-registered 0.02 fJ gate.

    The .mt0 is still used, and still reported, for every quantity that has no
    pedestal -- VBEND / VBOPEN / VAEND / VBPK / IPK / IZ are node voltages and
    branch currents, not integrals.  Both ledgers are carried on every row."""
    hdr, rows = read_prn(prn)
    need = ["V(XEA)", "V(XESW)", "V(XER)", "V(XEB)", "V(XQLT)"]
    if any(x not in hdr for x in need):
        return {}
    c = {x: hdr.index(x) for x in need}
    ts = [r[1] * 1e12 for r in rows]

    def at(t, col):
        for k in range(1, len(ts)):
            if ts[k - 1] <= t <= ts[k]:
                f = ((t - ts[k - 1]) / (ts[k] - ts[k - 1])
                     if ts[k] != ts[k - 1] else 0.0)
                return rows[k - 1][col] + f * (rows[k][col] - rows[k - 1][col])
        return float("nan")

    z = {x: at(0.5, col) for x, col in c.items()}
    v = lambda x, t: (at(t, c[x]) - z[x]) * 1e15
    out = {}
    for nm, tt in (("B", t_open), ("C", t_C), ("D", t_D)):
        out["ea_" + nm] = v("V(XEA)", tt)
        out["esw_" + nm] = v("V(XESW)", tt)
        out["er_" + nm] = v("V(XER)", tt)
        out["eb_" + nm] = v("V(XEB)", tt)
        out["qlt_" + nm] = v("V(XQLT)", tt)
    out["identity_B"] = out["ea_B"] - out["esw_B"] - out["er_B"]
    out["identity_C"] = out["ea_C"] - out["esw_C"] - out["er_C"]
    return out


# ------------------------------------------------------------------- one point
def point(tag, n, l_nh, total_um, ca_fF, rs=RS_REF, tail=TAIL, verbose=True,
          mix="data", vgh=1.5):
    # BUGFIX (AMENDMENT A9): VGH and MIX are module globals read by the deck
    # builders, and drive.py runs points in a ProcessPoolExecutor whose WORKER
    # PROCESSES ARE REUSED.  The first version defaulted vgh=None and only
    # assigned the global "if vgh is not None", so a point with no explicit vgh
    # inherited the PREVIOUS point's gate drive from the same worker.  Seven
    # rows were silently built at VHI = 2.4 V instead of the committed 1.5 V.
    # Both globals are now set UNCONDITIONALLY from the arguments on every call,
    # and audit.py re-reads the VHI line out of every generated netlist and
    # compares it against the spec that asked for it.
    global MIX, VGH
    MIX = mix
    VGH = float(vgh)
    pl, pm = probe_lines(n, l_nh, total_um, ca_fF, rs)
    pp, msg, wp_ = run("p_%s.cir" % tag, pl, want_tend_ps=pm["tend"])
    if pp is None:
        return dict(tag=tag, N=n, L_nH=l_nh, total_um=total_um, error=msg)
    tz, ipk, tpk = zero_after_peak(pp + ".prn")
    if tz is None:
        return dict(tag=tag, N=n, L_nH=l_nh, total_um=total_um,
                    error="no current zero found in probe window", probe_wall_s=wp_)
    pm.update(t_zero_ps=tz, probe_IPK_uA=ipk, probe_t_IPK_ps=tpk,
              probe_wall_s=round(wp_, 1))
    hl, hm = hop_lines(n, l_nh, total_um, ca_fF, tz, rs, tail)
    hp, msg2, wh = run("h_%s.cir" % tag, hl, want_tend_ps=hm["tend"])
    if hp is None:
        return dict(tag=tag, N=n, L_nH=l_nh, total_um=total_um, error=msg2,
                    probe=pm)
    pm["hop_wall_s"] = round(wh, 1)
    pm["probe_msg"], pm["hop_msg"] = msg, msg2
    try:
        row = extract(tag, n, l_nh, total_um, ca_fF, tz,
                      hp + ".mt0", hp + ".prn", rs, tail, pm)
    except Exception as e:                                             # noqa
        return dict(tag=tag, N=n, L_nH=l_nh, total_um=total_um,
                    error="extract: %r" % e, probe=pm)
    if verbose:
        print(brief(row), flush=True)
    return row


def brief(r):
    if r.get("error"):
        return "%-24s ERROR %s" % (r["tag"], r["error"][:110])
    return ("%-24s N=%-3d L=%-6g W=%-5g t_hop=%7.2f Q=%5.2f Ron=%6.1f "
            "VBEND=%.4f VAop=%.4f t_lvl=%s t_fc=%s val=%s %s %s"
            % (r["tag"], r["N"], r["L_nH"], r["total_um"], r["t_hop_ps"],
               r["Q_measured"] or -1, r["Ron_sw_eff_ohm"] or -1, r["VBEND"],
               r["VA_open"],
               ("%7.2f" % r["t_level_ps"]) if r["t_level_ps"] else "   None",
               ("%7.2f" % r["t_level_fcrit_ps"]) if r["t_level_fcrit_ps"] else "   None",
               "Y" if r["value_all_correct"] else "N",
               r["FEASIBLE"], ",".join(r["fails"])))


# --------------------------------------------------------------------- stages
if __name__ == "__main__":
    st = sys.argv[1]
    if st == "cbank":
        out = {}
        for n in [int(x) for x in sys.argv[2:]]:
            p, msg, w = run("cb_n%d.cir" % n, cbank_deck(n))
            print("N=%d %s" % (n, msg), flush=True)
            if p:
                out["N%d" % n] = cbank_extract(p + ".prn", n)
                out["N%d" % n]["wall_s"] = round(w, 1)
                print("   " + json.dumps(out["N%d" % n]), flush=True)
        fn = os.path.join(HERE, "CBANK.json")
        old = json.load(open(fn)) if os.path.exists(fn) else {}
        old.update(out)
        json.dump(old, open(fn, "w"), indent=1)
    elif st == "point":
        tag = sys.argv[2]
        kw = json.loads(sys.argv[3])
        print(json.dumps(point(tag, **kw), indent=1))
    else:
        sys.exit("stages: cbank <N>... | point <tag> <json>")
