"""qal/fastwave/p2 -- PHASE 2: THE WAVE.

Builds a >= 6-bank TG-XOR QAL wave at the Phase-1 optimum, with per-bank tanks
(qal/banktank 0aae11e arrangement), chain-legal source-side ZCS cuts, dV = 1.65 V
and EXPLICIT rotate interconnect.  See p2/PRE_REGISTERED.json (sha256 in
p2/PRE_REGISTERED.sha256) -- written before this file ran a single deck.

A9 GUARD, inherited from Phase 1's worst self-inflicted bug: there is NO module
global that a deck builder reads.  Every electrical parameter arrives as an
explicit field of one `Spec` dict, and audit() re-reads the GENERATED netlist for
VGH, dV, L, tank, wire C and every cell input source and compares it against the
spec that asked for it.  On every deck, not a sample.
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
P1    = os.path.dirname(HERE)
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or (
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
    "/scratchpad/vae_cache_fastwave")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; NOT swept, NOT defaults for anything) ---
WP, WN  = 1.12, 0.74          # um, campaign-standard cell inverter widths
TGWN    = 0.74                # um, pgcell tgM transmission gate nMOS
TGWP    = 1.12                # um, pgcell tgM transmission gate pMOS
CL_FF   = 2.0                 # fF, committed per-output load
EDGE    = 2.0                 # ps, committed gate edge
LAG_PS  = 1.0                 # ps, MEASURED .measure-FIND lag of this Xyce build
RS_REF  = 10.0                # ohm, committed inductor series R
VTN     = 0.5240              # V, MEASURED binding threshold (qal/strip, qal/sha256)
VTP     = 0.4403              # V, MEASURED |Vtp|
FLOOR   = VTN + VTP           # 0.9642 V level-restoring floor
SIG_MV  = 6.441               # mV, corrected 1-sigma (qal/vtaudit, a LOWER bound)
NB_V    = 3.0 * SIG_MV / 1000.0   # 19.323 mV noise budget = 3 sigma

# ---- the pre-registered logic (section D), frozen -- read, never recomputed --
X0     = [0, 0, 1, 0]
ROT    = [2, 3, 2, 3, 1, 3, 2]                    # bank 1..7 (7 = P1 terminator)
FORMS  = [["X", "N", "N", "X"], ["X", "X", "X", "N"], ["X", "X", "N", "N"],
          ["X", "N", "X", "X"], ["N", "X", "X", "N"], ["N", "X", "X", "X"],
          ["X", "N", "N", "X"]]                    # bank 7 = P1 terminator
NSCORE = 6                                         # banks 1..6 are SCORED
NCELL  = 4
NBANK  = 7                                         # BUILT (AMENDMENT P1)


def logic():
    """The pre-registered value table, RECOMPUTED from X0/ROT/FORMS so the deck
    and the checker cannot drift apart, and asserted against section D."""
    ws, ps, x = [], [], list(X0)
    for k in range(len(ROT)):
        r, f, y, p = ROT[k], FORMS[k], [], []
        for i in range(NCELL):
            A, B = x[i], x[(i + r) % NCELL]
            y.append(A ^ B if f[i] == "X" else 1 - (A ^ B))
            p.append("R" if ((f[i] == "X" and B == 1) or
                             (f[i] == "N" and B == 0)) else "T")
        ws.append(y); ps.append(p); x = list(y)
    return ws, ps


def check_logic_against_prereg():
    ws, ps = logic()
    pr = json.load(open(os.path.join(HERE, "PRE_REGISTERED.json")))
    for k, b in enumerate(pr["D_THE_LOGIC AND THE VALUE TABLE -- FIXED BEFORE ANY DECK"]["banks"]):
        # banks 1..6 only: bank 7 is the AMENDMENT P1 terminator, added after
        assert b["k"] == k + 1 and b["rot"] == ROT[k]
        assert [("XOR" if c == "X" else "XNOR") for c in FORMS[k]] == b["forms"]
        assert b["expect_out"] == ws[k], (k, b["expect_out"], ws[k])
        assert b["paths"] == ps[k], (k, b["paths"], ps[k])
    return ws, ps


# ------------------------------------------------------------ the wire model
WIRE = {
    # tag: (rotate C fF by rot, rotate R ohm by rot, straight C fF, straight R ohm)
    "W2": dict(rotC={1: 11.2913, 2: 11.2913, 3: 11.2913},
               rotR={1: 26.6667, 2: 26.6667, 3: 26.6667},
               strC=0.8374, strR=1.9776,
               label="PRIMARY: PDK Metal2 min-pitch bus 0.218062 fF/um "
                     "(qal/cipher/WIRE_MODEL.json from IHP tech LEF + OpenRCX), "
                     "PDK sg13g2_xor2_1 bit pitch 3.84 um, ChaCha20 mean rotate "
                     "13.484375 pitches = 51.78 um"),
    "W0": dict(rotC={1: 0.0, 2: 0.0, 3: 0.0}, rotR={1: 0.0, 2: 0.0, 3: 0.0},
               strC=0.0, strR=0.0,
               label="CONTROL: zero interconnect, the campaign status quo"),
    "W1": dict(rotC={1: 2.4, 2: 2.4, 3: 2.4}, rotR={1: 8.24, 2: 8.24, 3: 8.24},
               strC=0.15, strR=0.515,
               label="ASSUMED: the brief's own 0.15 fF/um at 1 um/bit x 16 pitches"),
    "WL": dict(rotC={1: 1.2560, 2: 1.6747, 3: 1.2560},
               rotR={1: 2.9664, 2: 3.9552, 3: 2.9664},
               strC=0.8374, strR=1.9776,
               label="OPTIMISTIC BOUND: the 4-bit word's OWN rotate, same PDK "
                     "bus figure (mean |di| = 2r(4-r)/4 pitches)"),
}


def spec(T, wire="W2", l_nh=15.0, vgh=2.4, dv=1.65, m=10.0, cbank_fF=None,
         w_total=30.0, park_w=1.0, rs=RS_REF, H=4, T1=200.0, vinhi=1.20,
         tail=200.0, nbank=NBANK, tzr=None, tzq=None, probe=None, vt0=None,
         returns=True, sync=False, window=None, restore=False,
         sync_skew=5.0):
    """ONE dict carrying every electrical parameter.  No field has a value that
    is read from a module global at deck-build time (A9 guard)."""
    assert cbank_fF is not None, "C_bank must be MEASURED in this directory first"
    w = WIRE[wire]
    # cbank_fF is EITHER one float OR a per-bank list (AMENDMENT P2: the seven
    # banks' in-situ rail loads span 53.0-113.8 fF at the primary wire setting,
    # a 74% spread, so one number would mis-size six of the seven tanks).
    cb = ([float(x) for x in cbank_fF] if isinstance(cbank_fF, (list, tuple))
          else [float(cbank_fF)] * int(nbank))
    assert len(cb) == int(nbank), "cbank list must have one entry per bank"
    return dict(T=float(T), wire=wire, w=w, l_nh=float(l_nh), vgh=float(vgh),
                dv=float(dv), m=float(m), cbank_fF=cb,
                cbank_mean_fF=sum(cb) / len(cb),
                w_total=float(w_total), park_w=float(park_w), rs=float(rs),
                H=int(H), T1=float(T1), vinhi=float(vinhi), tail=float(tail),
                nbank=int(nbank), tzr=tzr, tzq=tzq, probe=probe,
                returns=bool(returns), sync=bool(sync),
                restore=bool(restore), sync_skew=float(sync_skew),
                window=(float(window) if window is not None else 6.0 * float(T)),
                vt0=(float(vt0) if vt0 is not None
                     else float(dv) * (float(m) + 1.0) / (2.0 * float(m))))


def sw_widths(s):
    return dict(wn=s["w_total"] / 3.0, wp=2.0 * s["w_total"] / 3.0,
                park=s["park_w"])


def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17"]


def integ(tg, expr):
    """1 F integrator.  ALWAYS t0-referenced at extraction (Phase 1 A5)."""
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def companion(s):
    """MANDATORY per-deck instrument check AND DC-biased companion.

    AMENDMENT P8 -- an INHERITED INSTRUMENT DEFECT, fixed here.  Phase 1's
    companion drove its input UPWARD (`PWL(0 0 ... 1.2)`) so its output FELL,
    while the measure asked for `WHEN V(o_zc)=1.08 RISE=1` and the committed
    reference 57.1428 ps is qal/fcrit/cmos.cir's T90R2 -- the RISING output of a
    FALLING input.  Those are three different things.  The measure could never
    have matched, and MEASURED in this directory it does not: every Phase-2 skewed
    deck returned `T90ZC = FAILED`.

    Fixed by driving the input DOWNWARD, which reproduces cmos.cir's `or2` arm
    exactly: same 1.12/0.74 devices, same 1.2 V supply, same 2 fF load, same
    1.2 -> 0 input edge over 2 ps, same 1.08 V threshold.  The committed answer is
    then 157.1428 - 100 = 57.1428 ps and the check is a real check."""
    t = s["T1"]
    return ["VSzc s_zc 0 1.2",
            "VIzc i_zc 0 PWL(0 1.2 %gp 1.2 %gp 0)" % (t, t + EDGE),
            "XPzc o_zc i_zc s_zc s_zc sg13_lv_pmos w=%gu l=0.13u" % WP,
            "XNzc o_zc i_zc 0 0 sg13_lv_nmos w=%gu l=0.13u" % WN,
            "CLzc o_zc 0 %gf" % CL_FF]


# ------------------------------------------------------------------ the cell
def cell(k, i, form, a_net, b_net, rail, gnd, restore=False):
    """qal/pgcell tg_xnor2, tgM widths, fixedwell.  VERBATIM from Phase 1's
    fw.xor_cell for form 'X'; form 'N' exchanges ONLY the two TG source taps,
    which is the same 8 devices at the same widths on the same nodes."""
    t = "%d_%d" % (k, i)
    ab, bb = "ab" + t, "bb" + t
    # AMENDMENT P9 -- THE RESTORING VARIANT, and it is INSIDE the user's budget.
    # "a maximum of two levels of transistor logic per bank": the TG-XOR spends
    # ONE.  Spending the second on an output inverter powered by the bank rail
    # makes the bank LEVEL-RESTORING, which DIAG_CROWBAR.json and the synchronous
    # rows showed is exactly what the unbuffered TG chain lacks.  The cell's FORM
    # is flipped so the composite output is bit-identical to the pre-registered
    # value table -- the logic does not change, only the gain.
    if restore:
        y = "yi" + t                          # the TG output, now an internal node
        form = "N" if form == "X" else "X"
    else:
        y = "y" + t
    tg1 = a_net if form == "X" else ab       # what TG1 (gates bb/b) passes
    tg2 = ab if form == "X" else a_net       # what TG2 (gates b/bb) passes
    L = [
        "XPIA%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (t, ab, a_net, rail, rail, WP),
        "XNIA%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, ab, a_net, gnd, gnd, WN),
        "XPIB%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (t, bb, b_net, rail, rail, WP),
        "XNIB%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, bb, b_net, gnd, gnd, WN),
        "XTN1%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, tg1, bb, y, gnd, TGWN),
        "XTP1%s %s %s %s vhi sg13_lv_pmos w=%gu l=0.13u" % (t, tg1, b_net, y, TGWP),
        "XTN2%s %s %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (t, tg2, b_net, y, gnd, TGWN),
        "XTP2%s %s %s %s vhi sg13_lv_pmos w=%gu l=0.13u" % (t, tg2, bb, y, TGWP),
        "CL%s %s %s %gf" % (t, y, gnd, CL_FF),
    ]
    if restore:
        L += ["XPOR%s y%s %s %s %s sg13_lv_pmos w=%gu l=0.13u"
              % (t, t, y, rail, rail, WP),
              "XNOR%s y%s %s %s %s sg13_lv_nmos w=%gu l=0.13u"
              % (t, t, y, gnd, gnd, WN),
              "CLO%s y%s %s %gf" % (t, t, gnd, CL_FF)]
    return L


def wire_seg(tag, src, dst, c_fF, r_ohm):
    """One single-segment pi.  If the wire is disabled the destination IS the
    source net and no element is emitted -- so the W0 control is a true zero,
    not a tiny resistor."""
    if c_fF <= 0.0:
        return [], src
    return (["CW%sd %s 0 %.6ff" % (tag, src, c_fF / 2.0),
             "RW%s %s %s %.6f" % (tag, src, dst, max(r_ohm, 1e-3)),
             "CW%sr %s 0 %.6ff" % (tag, dst, c_fF / 2.0)], dst)


def build(s):
    """The whole wave.  Returns (lines, schedule)."""
    nb, w = s["nbank"], s["w"]
    ws, ps = logic()
    sw = sw_widths(s)
    L = head_lines() + ["VHI vhi 0 %g" % s["vgh"]]

    # ---- the chain head: ideal per-BIT drivers, then the SAME wire model -----
    for j in range(NCELL):
        L.append("VH%d h%d 0 %g" % (j, j, s["vinhi"] if X0[j] else 0.0))

    # ---- nets: bank k cell i takes A from source bit i, B from bit (i+r)%N ---
    def src_net(k, j):
        return ("h%d" % j) if k == 1 else ("y%d_%d" % (k - 1, j))

    for k in range(1, nb + 1):
        gnd, rail = "gn%d" % k, "rail%d" % k
        L.append("VMG%d %s 0 0" % (k, gnd))
        r = ROT[k - 1]
        for i in range(NCELL):
            ls, a_net = wire_seg("s%d_%d" % (k, i), src_net(k, i),
                                 "a%d_%d" % (k, i), w["strC"], w["strR"])
            L += ls
            ls, b_net = wire_seg("r%d_%d" % (k, i), src_net(k, (i + r) % NCELL),
                                 "b%d_%d" % (k, i), w["rotC"][r], w["rotR"][r])
            L += ls
            L += cell(k, i, FORMS[k - 1][i], a_net, b_net, rail, gnd,
                      restore=s.get("restore", False))

    # ---- per-bank tank branch (banktank tank_branch, park TANK-referenced) ---
    for k in range(1, nb + 1):
        L += ["CT%d tnk%d 0 %.6ff" % (k, k, s["m"] * s["cbank_fF"][k - 1]),
              "L%d tnk%d mid%d %gn" % (k, k, k, s["l_nh"]),
              "R%d mid%d sw%d %g" % (k, k, k, s["rs"]),
              "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
              % (k, k, k, k, sw["wn"]),
              "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
              % (k, k, k, k, sw["wp"]),
              "XPK%d sw%d pk%d tnk%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
              % (k, k, k, k, k, sw["park"])]

    S = schedule(s)
    big = S["tend"] * 4.0
    for k in range(1, nb + 1):
        wins = S["wins"][k]
        if not wins:
            L += ["VGT%d gt%d 0 0" % (k, k),
                  "VGTP%d gtp%d 0 %g" % (k, k, s["vgh"]),
                  "VPK%d pk%d 0 %g" % (k, k, s["vgh"])]
        else:
            L += phase_pwl(k, wins, big, s["vgh"])

    L += companion(s)

    # ---- metering.  Energy gates nothing; these are for the ledger + K5. ----
    if s["probe"] is None:
        for k in range(1, nb + 1):
            L += integ("qlt%d" % k, "I(L%d)" % k)
            L += integ("ea%d" % k, "V(tnk%d)*I(L%d)" % (k, k))
            L += integ("eb%d" % k, "V(rail%d)*I(L%d)" % (k, k))
            L += integ("esw%d" % k, "V(sw%d)*I(L%d)" % (k, k))
            L += integ("er%d" % k, "I(L%d)*I(L%d)*%g" % (k, k, s["rs"]))
            L += integ("qg%d" % k, "I(VMG%d)" % k)
        L += integ("qhd", "-(" + "+".join("I(VH%d)" % j for j in range(NCELL)) + ")")
        L += integ("ehi", "-%g*I(VHI)" % s["vgh"])
        L += integ("egt", "-(" + "+".join(
            "V(gt%d)*I(VGT%d)+V(gtp%d)*I(VGTP%d)+V(pk%d)*I(VPK%d)"
            % (k, k, k, k, k, k) for k in range(1, nb + 1)) + ")")

    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                              % (k, s["vt0"], k, k, s["vt0"])
                              for k in range(1, nb + 1)))
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], S["tend"], S["mstep"]))
    L.append(".measure tran T90ZC WHEN V(o_zc)=1.08 RISE=1")
    if s["probe"] is None:
        g = lambda t: t + LAG_PS
        for k in range(1, nb + 1):
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], S["tend"]))
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["o"][k])))
            if s.get("returns", True):
                L.append(".measure tran IZQ%d FIND I(L%d) AT=%.6fp"
                         % (k, k, g(S["ro"][k])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], S["tend"]))
            for tg in ("qlt", "ea", "eb", "esw", "er", "qg"):
                cks = ([("Z", 0.5), ("B", S["bound"][k]), ("Q", S["ro"][k]),
                        ("D", S["tend"] - 5.0)] if s.get("returns", True)
                       else [("Z", 0.5), ("B", S["bound"][k]),
                             ("D", S["tend"] - 5.0)])
                for nm, tt in cks:
                    L.append(".measure tran %s%d_%s FIND V(x%s%d) AT=%.6fp"
                             % (tg.upper(), k, nm, tg, k, g(tt)))
        for tg in ("qhd", "ehi", "egt"):
            for nm, tt in (("Z", 0.5), ("D", S["tend"] - 5.0)):
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))

    pr = (["V(rail%d)" % k for k in range(1, nb + 1)]
          + ["V(tnk%d)" % k for k in range(1, nb + 1)]
          + ["V(sw%d)" % k for k in range(1, nb + 1)]
          + ["I(L%d)" % k for k in range(1, nb + 1)]
          + ["V(y%d_%d)" % (k, i) for k in range(1, nb + 1) for i in range(NCELL)]
          + ["V(o_zc)"])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


def phase_pwl(k, wins, big, vgh):
    """banktank phase_pwl verbatim: gtp is the exact complement, the park is
    anti-phase and TANK-referenced so it clamps the inductor the instant the
    transfer gate lets go (banktank AMENDMENT A6)."""
    pn, pp, pk = [(0.0, 0.0)], [(0.0, vgh)], [(0.0, vgh)]
    for (tc, to) in wins:
        pn += [(tc - EDGE, 0.0), (tc, vgh)]
        pp += [(tc - EDGE, vgh), (tc, 0.0)]
        pk += [(tc - EDGE, vgh), (tc, 0.0)]
        if to is None:
            pn += [(big, vgh)]; pp += [(big, 0.0)]; pk += [(big, 0.0)]
            break
        pn += [(to, vgh), (to + EDGE, 0.0)]
        pp += [(to, 0.0), (to + EDGE, vgh)]
        pk += [(to, 0.0), (to + EDGE, vgh)]
    f = lambda q: " ".join(("%gp %g" % (t, v)) if t > 0 else ("0 %g" % v)
                           for t, v in q)
    return ["VGT%d gt%d 0 PWL(%s)" % (k, k, f(pn)),
            "VGTP%d gtp%d 0 PWL(%s)" % (k, k, f(pp)),
            "VPK%d pk%d 0 PWL(%s)" % (k, k, f(pk))]


def t_est(s, c_fF):
    return math.pi * math.sqrt((s["l_nh"] * 1e-9) * (c_fF * 1e-15)) * 1e12


def schedule(s):
    """banktank schedule verbatim.  tzr/tzq are MEASURED per bank; the analytic
    pi*sqrt(LC) is used ONLY to size probe run lengths."""
    nb, T, H = s["nbank"], s["T"], s["H"]
    tev = [t_est(s, c * s["m"] / (s["m"] + 1.0)) for c in s["cbank_fF"]]
    te = max(tev)          # ONLY sizes probe run lengths; never a reported time
    tzr = s["tzr"] or list(tev)
    tzq = s["tzq"] or list(tev)
    # AMENDMENT P7: sync = every bank's rail is raised TOGETHER and the wave is
    # carried by the DATA alone.  The skewed arrangement (banktank's, and the one
    # pre-registered) leaves every successor's rail at 0 for a whole beat, and
    # DIAG_CROWBAR.json MEASURED that this shorts the predecessor's output to
    # ground through two series pMOS at 78-83 uA -- a resistive load no LC tank
    # can supply.  Both arrangements are run and both are reported.
    # AMENDMENT P10: seven switch closes at the SAME instant did not converge
    # (the deck stalled at t = 198 ps).  The sync rows stagger them by
    # sync_skew = 5 ps -- 4% of a 125 ps hop and 1.7% of a beat, against the
    # 300 ps of crowbar exposure the skewed arrangement carries.  It is a
    # NUMERICAL measure, declared, and its size is reported on every row.
    c  = ({k: s["T1"] + (k - 1) * s.get("sync_skew", 5.0)
           for k in range(1, nb + 1)} if s.get("sync") else
          {k: s["T1"] + (k - 1) * T for k in range(1, nb + 1)})
    o  = {k: c[k] + tzr[k - 1] for k in range(1, nb + 1)}
    r  = {k: c[k] + H * T for k in range(1, nb + 1)}
    ro = {k: r[k] + tzq[k - 1] for k in range(1, nb + 1)}
    bnd = {}
    if s.get("sync"):
        # one COMMON window end for every bank; the per-stage time then comes
        # entirely from the measured commit instants, not from the schedule.
        be = s["T1"] + s["window"]
        for k in range(1, nb + 1):
            b = be
            if s.get("returns", True):
                b = min(b, r[k] - EDGE)
            bnd[k] = b
    else:
        for k in range(1, nb + 1):
            b = min(c[k] + T, r[k] - EDGE)
            if k > 1:
                b = min(b, r[k - 1] - EDGE)
            bnd[k] = b
    p = s["probe"]
    wins, tend = {}, None
    for k in range(1, nb + 1):
        if p is None:
            # AMENDMENT P5: on the BEAT deck the returns are DISABLED.  For H >= 3
            # the stage boundary is exactly c_k + T for every k (min(c_k+T,
            # c_k+H*T-2, c_k+(H-1)*T-2) = c_k+T whenever (H-2)*T >= 2), so no
            # return can fall inside any scored window and the returns provably
            # cannot move a scored number.  Removing them halves the switch events
            # and is what makes the 7-bank deck converge at all.
            wins[k] = ([(c[k], o[k]), (r[k], ro[k])] if s.get("returns", True)
                       else [(c[k], o[k])])
        elif p[0] == "rise":
            wins[k] = ([(c[k], o[k])] if k < p[1] else
                       [(c[k], None)] if k == p[1] else [])
        else:                                    # 'ret'
            wins[k] = [(c[k], o[k])]
            if k < p[1]:
                wins[k].append((r[k], ro[k]))
            elif k == p[1]:
                wins[k].append((r[k], None))
    if p is None:
        tend = ((max(max(ro.values()), max(bnd.values())) + s["tail"])
                if s.get("returns", True)
                else (max(bnd.values()) + s["tail"]))
    elif p[0] == "rise":
        tend = c[p[1]] + 2.6 * tev[p[1] - 1]
    else:
        tend = r[p[1]] + 2.6 * tev[p[1] - 1]
    return dict(nbank=nb, T=T, H=H, c=c, o=o, r=r, ro=ro, bound=bnd,
                wins=wins, tend=tend, t_est=te, t_est_per_bank=tev,
                tzr=tzr, tzq=tzq,
                pstep=0.25, mstep=0.25)


# --------------------------------------------------------------------- audit
def audit(fn, s):
    """A9 GUARD.  Re-read the GENERATED netlist and check every load-bearing
    number against the spec that asked for it.  Runs on EVERY deck."""
    txt = open(os.path.join(HERE, fn)).read()
    bad = []
    def want(pat, val, nm, tol=1e-6):
        got = re.findall(pat, txt, re.M)   # re.M is LOAD-BEARING: every
        # pattern here is ^-anchored to a netlist line, and without it the
        # audit matched nothing and fail-CLOSED on every deck.
        if not got:
            bad.append("%s: no match for %s" % (nm, pat)); return
        for g in got:
            if abs(float(g) - val) > tol * max(1.0, abs(val)):
                bad.append("%s: netlist %s != spec %g" % (nm, g, val))
    want(r"^VHI vhi 0 ([\d.eE+-]+)", s["vgh"], "VGH")
    for k in range(1, s["nbank"] + 1):
        want(r"^CT%d tnk%d 0 ([\d.eE+-]+)f" % (k, k),
             s["m"] * s["cbank_fF"][k - 1], "CT%d" % k, 1e-5)
        want(r"^L%d tnk%d mid%d ([\d.eE+-]+)n" % (k, k, k), s["l_nh"], "L%d" % k)
        want(r"^R%d mid%d sw%d ([\d.eE+-]+)" % (k, k, k), s["rs"], "RS%d" % k)
    sw = sw_widths(s)
    for nm, v, pat in (("swn", sw["wn"], r"^XSWN1 .* w=([\d.]+)u"),
                       ("swp", sw["wp"], r"^XSWP1 .* w=([\d.]+)u"),
                       ("park", sw["park"], r"^XPK1 .* w=([\d.]+)u")):
        want(pat, v, nm)
    # head drivers carry the pre-registered word at the pre-registered level
    for j in range(NCELL):
        want(r"^VH%d h%d 0 ([\d.eE+-]+)" % (j, j),
             s["vinhi"] if X0[j] else 0.0, "VH%d" % j)
    # .ic tank pre-charge
    want(r"V\(tnk1\)=([\d.eE+-]+)", s["vt0"], "vt0")
    # wire segments: count and value
    w = s["w"]
    nseg_expect = 0 if w["strC"] <= 0 else s["nbank"] * NCELL * 2
    nseg = len(re.findall(r"^RW", txt, re.M))
    if nseg != nseg_expect:
        bad.append("wire segments: netlist %d != expected %d" % (nseg, nseg_expect))
    if w["strC"] > 0:
        for k in range(1, s["nbank"] + 1):
            want(r"^CWs%d_0d \S+ 0 ([\d.]+)f" % k, w["strC"] / 2.0,
                 "strC%d" % k, 1e-4)
            r_ = ROT[k - 1]
            want(r"^CWr%d_0d \S+ 0 ([\d.]+)f" % k, w["rotC"][r_] / 2.0,
                 "rotC%d" % k, 1e-4)
    # every cell's form, by its TG source taps
    for k in range(1, s["nbank"] + 1):
        for i in range(NCELL):
            t = "%d_%d" % (k, i)
            m1 = re.search(r"^XTN1%s (\S+) " % t, txt, re.M)
            if not m1:
                bad.append("cell %s: no TG1" % t); continue
            # the EFFECTIVE form on the netlist: flipped when the output inverter
            # is present, so the composite output still matches the value table
            eff = FORMS[k - 1][i]
            if s.get("restore"):
                eff = "N" if eff == "X" else "X"
                if not re.search(r"^XPOR%s y%s yi%s " % (t, t, t), txt, re.M):
                    bad.append("cell %s: restoring inverter missing" % t)
            if eff == "N" and m1.group(1) != ("ab" + t):
                bad.append("cell %s XNOR TG1 taps %s not ab%s"
                           % (t, m1.group(1), t))
            if eff == "X" and m1.group(1) == ("ab" + t):
                bad.append("cell %s XOR TG1 taps the inverter -- form leaked" % t)
    # bank-to-bank connectivity: bank k's A input must trace to bank k-1's output
    for k in range(2, s["nbank"] + 1):
        for i in range(NCELL):
            if w["strC"] > 0:
                pat = r"^RWs%d_%d y%d_%d a%d_%d " % (k, i, k - 1, i, k, i)
            else:
                pat = r"^XPIA%d_%d ab%d_%d y%d_%d " % (k, i, k, i, k - 1, i)
            if not re.search(pat, txt, re.M):
                bad.append("chain break: bank %d cell %d A not fed by bank %d"
                           % (k, i, k - 1))
            r_ = ROT[k - 1]
            j = (i + r_) % NCELL
            if w["rotC"][r_] > 0:
                pat = r"^RWr%d_%d y%d_%d b%d_%d " % (k, i, k - 1, j, k, i)
            else:
                pat = r"^XPIB%d_%d bb%d_%d y%d_%d " % (k, i, k, i, k - 1, j)
            if not re.search(pat, txt, re.M):
                bad.append("rotate break: bank %d cell %d B not fed by bank %d bit %d"
                           % (k, i, k - 1, j))
    return bad


# --------------------------------------------------------------------- runner
def run(fn, lines, s, timeout=900, _div=1):
    """Phase 1 AMENDMENT A8: a stalled deck is retried with the time resolution
    refined 4x and then 16x and NOTHING ELSE CHANGED.  Committed .OPTIONS
    tolerances are never touched."""
    path = os.path.join(HERE, fn)
    if _div > 1:
        lines = [(re.sub(r"^\.tran (\S+)p (\S+)p 0 (\S+)p",
                         lambda mm: ".tran %gp %sp 0 %gp"
                         % (float(mm.group(1)) / _div, mm.group(2),
                            float(mm.group(3)) / _div), l)
                  if l.startswith(".tran") else l) for l in lines]
    open(path, "w").write("\n".join(lines) + "\n")
    bad = audit(fn, s)
    if bad:
        return None, "AUDIT FAIL: " + "; ".join(bad[:6]), 0.0, _div
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        if _div < 16:
            return run(fn, lines, s, timeout, _div * 4)
        return None, "TIMEOUT after %gs" % timeout, timeout, _div
    wall = time.monotonic() - t0
    if "build_vae_so" in r.stdout:
        sys.stderr.write("WARNING %s triggered a PyMS build (COLD geometry)\n" % fn)
    want_tend = float(re.search(r"^\.tran \S+ (\S+)p", "\n".join(lines),
                                re.M).group(1))
    ok = os.path.exists(path + ".prn") and r.returncode == 0
    if ok:
        try:
            _, rr = read_prn(path + ".prn")
            ok = bool(rr) and rr[-1][1] * 1e12 >= 0.98 * want_tend
        except Exception:                                               # noqa
            ok = False
    if not ok:
        if _div < 16:
            return run(fn, lines, s, timeout, _div * 4)
        tl = (r.stderr or r.stdout or "")[-400:]
        return None, "FAIL rc=%s: %s" % (r.returncode, tl), wall, _div
    return path, None, wall, _div


def parse_mt0(path):
    d = {}
    for ln in open(path):
        mm = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if mm:
            try:
                d[mm.group(1).upper()] = float(mm.group(2))
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


def zero_after_peak(prn, col, t_from):
    """The TRUE current zero: first LINEARLY INTERPOLATED downward crossing of
    I(L_k) after its own current peak.  Re-probed every time."""
    hdr, rows = read_prn(prn)
    ii = hdr.index(col)
    ts = [(r[1] * 1e12, r[ii]) for r in rows if r[1] * 1e12 >= t_from]
    if not ts:
        return None, None
    ipk, tpk = max(((i, t) for t, i in ts), key=lambda x: abs(x[0]))
    sgn = 1.0 if ipk > 0 else -1.0
    prev = None
    for t, i in ts:
        if t <= tpk:
            prev = (t, i); continue
        if prev and sgn * prev[1] > 0 >= sgn * i:
            f = prev[1] / (prev[1] - i) if prev[1] != i else 0.0
            return prev[0] + f * (t - prev[0]) - t_from, ipk * 1e6
        prev = (t, i)
    return None, ipk * 1e6


# ------------------------------------------------- the MEASURED receiver trip
_TRIP = None


def trip_at(vdd):
    """qal/fcrit/TRIP.json receiver S, MEASURED at 27 delivered rails, linearly
    interpolated.  The trip FRACTION is NOT a constant (0.7281 at 0.20 V falling
    to 0.5179 at 1.50 V), so it is interpolated at the row's own rail."""
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
            (v0, a), (v1, b) = _TRIP[k - 1], _TRIP[k]
            return a + (vdd - v0) / (v1 - v0) * (b - a)
    return _TRIP[-1][1]
