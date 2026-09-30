#!/usr/bin/env python3
"""qal/cipher/p2 -- PHASE 2 cipher-datapath deck generator.

A STRICT GENERALISATION of the committed banktank harness (qal/banktank/bt.py
sha256 5b3582be..., commit 0aae11e, copied verbatim as ../btk/bt.py) in exactly
three respects, and in NO other:

  1. a bank may hold ANY number of cells (the committed MGATE = 8 becomes N),
  2. a cell may be ANY sg13g2 standard cell instantiated FROM THE PDK'S OWN
     .spice netlist (the committed inverter becomes a cell KIND), and
  3. a cell output may carry an explicit interconnect capacitance (Phase 1's
     wire, ../btk/btw.py).

Everything that decides the physics is reached by importing bt: WP/WN, CLOAD,
RS_REF, L_REF, VGH, EDGE, LAG_PS, TAIL, T1, TZ_ANCH, widths(), vtank0(),
schedule(), phase_pwl(), integ(), the tank_branch topology with the A6
tank-referenced park, the break-before-make edges, the sequential true-ZCS probe
protocol, the 1F-integrator metering and the .OPTIONS line.

REGRESSION GUARANTEE, checked by selftest():  a chain of nb banks of N = 8
"inv" cells wired i -> i with the committed PAT, cw = 0 and ct "fixed", emits a
netlist BYTE-IDENTICAL to bt.deck() -- so the generalisation provably adds
nothing to the committed configuration.

CELLS come from the PDK by .include of
  IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice
and are instantiated as subcircuits with (VDD, VSS) -> (rail{k}, gn{k}).  The
PDK subckts tie every bulk to those same two ports, so the pMOS bulk sits on the
bank rail -- the committed convention, unchanged.  The ad/as/pd/ps the PDK cells
carry are DECLARED AND DISCARDED by qal/sg13lv_compat.sp, exactly as for the
committed hand-written cell, so cells and harness share one device model.
"""
import json, math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
BTK = os.path.join(os.path.dirname(HERE), "btk")
sys.path.insert(0, BTK)
import bt
from bt import (WP, WN, CLOAD, CBANK, RS_REF, L_REF, VGH, EDGE, LAG_PS, TAIL,
                T1, TZ_ANCH, PAT, widths, vtank0, schedule, integ, phase_pwl,
                parse_mt0, read_prn, zero_after_peak)

PDK_SPICE = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/"
             "sg13g2_stdcell/spice/sg13g2_stdcell.spice")

CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
XYCE = "/usr/local/src/xyce-build/src/Xyce"

# --------------------------------------------------------------- cell library
# kind -> (pdk subckt, n_inputs, logic function, device count, port order after Y)
# The logic function is the REFERENCE semantics, used for the value check and
# checked against the PDK topology by selftest_logic().
CELLS = {
    "inv":    ("sg13g2_inv_1",    1, lambda a:        (not a[0]),                  2),
    "buf":    ("sg13g2_buf_1",    1, lambda a:        (a[0]),                      4),
    "xor2":   ("sg13g2_xor2_1",   2, lambda a:        (a[0] != a[1]),             10),
    "xnor2":  ("sg13g2_xnor2_1",  2, lambda a:        (a[0] == a[1]),             10),
    "and2":   ("sg13g2_and2_1",   2, lambda a:        (a[0] and a[1]),             6),
    "or2":    ("sg13g2_or2_1",    2, lambda a:        (a[0] or a[1]),              6),
    "nand2":  ("sg13g2_nand2_1",  2, lambda a:    not (a[0] and a[1]),             4),
    "nor2":   ("sg13g2_nor2_1",   2, lambda a:    not (a[0] or a[1]),              4),
    # Y = !(A | !B_N) = !A & B_N  -- the mixed-polarity AND.  Needed because a
    # forwarded word arrives complemented and an AND term, unlike an XOR term,
    # cannot absorb a polarity flip by relabelling: and2(!A, B) is a DIFFERENT
    # function, not a relabelling of A & B.
    "nor2b":  ("sg13g2_nor2b_1",  2, lambda a:   (not a[0]) and a[1],              6),
    # Y = !((A1 & A2) | B1)   -- AOI21, 6 devices, 2-high BOTH sides
    "a21oi":  ("sg13g2_a21oi_1",  3, lambda a: not ((a[0] and a[1]) or a[2]),      6),
    # Y = (A1 & A2) | B1      -- AO21, 8 devices (AOI21 + inverter stage)
    "a21o":   ("sg13g2_a21o_1",   3, lambda a:     ((a[0] and a[1]) or a[2]),      8),
    # Y = !((A1 | A2) & B1)   -- OAI21, 6 devices.  The cell qal/strip measured
    # at 479.1 ps settling, 3.12-3.55x an inverter: the WORST-CELL bar.
    "o21ai":  ("sg13g2_o21ai_1",  3, lambda a: not ((a[0] or a[1]) and a[2]),      6),
}
# MEASURED from the PDK LEF (sg13g2_stdcell.lef SIZE): cell width in um, which
# is the bit pitch a bit-sliced datapath of that cell must pay.
CELL_WIDTH_UM = {"inv": 1.44, "buf": 1.92, "xor2": 3.84, "xnor2": 3.84,
                 "and2": 2.40, "or2": 2.40, "nand2": 1.92, "nor2": 1.92,
                 "a21oi": 2.40, "o21ai": 2.40, "a21o": 3.36, "nor2b": 2.40}


def cell_devices(kind):
    return CELLS[kind][3]


# ------------------------------------------------------------------ the level
class Cell(object):
    __slots__ = ("kind", "ins", "val", "name")

    def __init__(self, kind, ins, val=None, name=""):
        self.kind, self.ins, self.val, self.name = kind, list(ins), val, name


class Chain(object):
    """nb levels.  Level k (1-based) is a list of Cell.  A cell's input is a NET
    NAME: either 'o{k-1}_{j}' (the predecessor level's output -- the only
    inter-level connection the committed harness permits) or 's_{tag}' (an ideal
    DC source, which only the chain HEAD and declared held values may use)."""

    def __init__(self, name):
        self.name = name
        self.levels = []          # list of list[Cell]
        self.sources = {}         # 's_tag' -> bool
        self.wire = {}            # (k, i) -> Cw in fF on that cell's output
        self.note = []

    def add_level(self, cells):
        self.levels.append(list(cells))
        return len(self.levels)

    @property
    def nb(self):
        return len(self.levels)

    def n_of(self, k):
        return len(self.levels[k - 1])

    def out_net(self, k, i):
        return "o%d_%d" % (k, i)

    # ---------------------------------------------------------- the reference
    def evaluate(self):
        """Reference semantics of the whole chain.  Fills every Cell.val."""
        for k in range(1, self.nb + 1):
            for i, c in enumerate(self.levels[k - 1]):
                av = []
                for s in c.ins:
                    if s in self.sources:
                        av.append(self.sources[s])
                    else:
                        mm = re.match(r"o(\d+)_(\d+)$", s)
                        if not mm:
                            raise SystemExit("bad net %s" % s)
                        kk, ii = int(mm.group(1)), int(mm.group(2))
                        if kk >= k:
                            raise SystemExit(
                                "%s: level %d cell %d reads %s -- NOT the "
                                "immediately preceding level.  An unbuffered QAL "
                                "bank returns its rail charge at the end of its "
                                "hold window, so a value cannot be read from a "
                                "level older than k-1 without a FORWARDING cell."
                                % (self.name, k, i, s))
                        if kk != k - 1:
                            raise SystemExit("%s: level %d reads %s (level %d): "
                                             "level skipping is not physical here"
                                             % (self.name, k, s, kk))
                        av.append(self.levels[kk - 1][ii].val)
                if len(av) != CELLS[c.kind][1]:
                    raise SystemExit("%s: %s cell wants %d inputs, got %d"
                                     % (self.name, c.kind, CELLS[c.kind][1], len(av)))
                c.val = bool(CELLS[c.kind][2](av))
        return self

    def outputs(self, k=None):
        k = k or self.nb
        return [c.val for c in self.levels[k - 1]]

    # ------------------------------------------------------------- the census
    def census(self):
        d = dict(name=self.name, nb=self.nb,
                 n_per_level=[self.n_of(k) for k in range(1, self.nb + 1)],
                 kinds_per_level=[], devices_per_level=[], n_sources=len(self.sources))
        for k in range(1, self.nb + 1):
            cnt = {}
            dev = 0
            for c in self.levels[k - 1]:
                cnt[c.kind] = cnt.get(c.kind, 0) + 1
                dev += cell_devices(c.kind)
            d["kinds_per_level"].append(cnt)
            d["devices_per_level"].append(dev)
        d["cells_total"] = sum(d["n_per_level"])
        d["devices_total"] = sum(d["devices_per_level"])
        d["wire_nets"] = len([1 for v in self.wire.values() if v > 0])
        d["wire_total_fF"] = round(sum(self.wire.values()), 6)
        d["note"] = self.note
        return d


# ------------------------------------------------------------ derived C_bank
def c_bank_derived(ch, k):
    """The committed sizing convention, extended by cell kind.

    CBANK = 35.979 fF is the committed MEASURED secant capacitance of ONE
    8-INVERTER bank, i.e. 4.497375 fF per inverter cell INCLUDING its CLOAD of
    2 fF.  DERIVED extension: a cell's rail-visible capacitance scales as its
    own pull-up network width relative to the inverter's, plus its own CLOAD,
    plus the wire actually hung on its output.

    This is a SIZING RULE, not a measurement.  The measured secant C of every
    level in this run is reported separately (A9) and the sizing rule's error is
    reported with it, exactly as qal/widebank reports its 1.63x.
    """
    per_inv = CBANK / 8.0                 # 4.497375 fF, MEASURED (committed)
    dev_inv = 2.0
    tot = 0.0
    for i, c in enumerate(ch.levels[k - 1]):
        scale = cell_devices(c.kind) / dev_inv
        tot += (per_inv - CLOAD) * scale + CLOAD + ch.wire.get((k, i), 0.0)
    return tot


# ------------------------------------------------------------------ the deck
def head_lines():
    """bt.head_lines() plus the PDK cell library.  The .OPTIONS line, the .hdl,
    the model .lib and the compat shim are the committed ones, untouched."""
    return bt.head_lines() + ['.include "%s"' % PDK_SPICE]


def level_cells(ch, k, dv):
    """One level of logic, as PDK subcircuit instances on bank k's own rail."""
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1:
        for tag in sorted(ch.sources):
            L.append("VS_%s %s 0 %g" % (tag, tag, dv if ch.sources[tag] else 0.0))
    for i, c in enumerate(ch.levels[k - 1]):
        sub = CELLS[c.kind][0]
        L.append("X%s%d_%d %s %s rail%d gn%d %s"
                 % (c.kind.upper(), k, i, ch.out_net(k, i), " ".join(c.ins),
                    k, k, sub))
        L.append("CL%d_%d %s gn%d %gf" % (k, i, ch.out_net(k, i), k, CLOAD))
        cw = ch.wire.get((k, i), 0.0)
        if cw > 0.0:
            L.append("CW%d_%d %s gn%d %.6ff" % (k, i, ch.out_net(k, i), k, cw))
    return L


def tank_branch(k, ct_fF, total_um, l_nh, rs):
    """bt.tank_branch VERBATIM except the tank capacitance is passed in rather
    than inlined as m*CBANK (btw.py's only change to it, reused)."""
    w = widths(total_um)
    return ["CT%d tnk%d 0 %gf" % (k, k, ct_fF),
            "L%d tnk%d mid%d %gn" % (k, k, k, l_nh),
            "R%d mid%d sw%d %g" % (k, k, k, rs),
            "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (k, k, k, k, w["wp"]),
            "XPK%d sw%d pk%d tnk%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, k, w["park"])]


def switch_um(ch, k, total_um=30.0, ct_mode="matched"):
    """PHASE 2 AMENDMENT B9, forced by measurement and by the sibling's own data.

    The committed tg15p transfer switch is 30 um TOTAL for an EIGHT-cell bank.
    Leaving it at 30 um while the bank grows to 128 cells makes the switch, not
    the inductor, the limiting resistance -- MEASURED: this run's AES level 1
    (128 inverters, C_bank 575.7 fF, tank 5757 fF, all identical to the sibling's
    n128 row) came out at t_hop = 645.3 ps against the sibling's MEASURED
    406.7 ps, 1.59x slower, for no reason but the switch.

    That is Phase 1's AMENDMENT A3 error in reverse: A3 was one cell against a
    switch sized for eight, and this is 128 cells against a switch sized for
    eight.  The lesson the campaign already paid for is that the switch must be
    matched to the bank.

    qal/widebank's rule, read off its rows and REPRODUCED on all 13 of them
    (N = 8, 16, 32, 64, 128, 256; match to < 0.6 um every time):
        W_nominal = 30 um * sqrt(N / 8)
    Since an N-inverter bank has C_bank = CBANK * N/8, that rule is identically
        W_nominal = 30 um * sqrt(C_bank / CBANK)
    which is the same closed form expressed in the quantity that actually sets
    the required conductance, and which therefore generalises correctly to this
    run's MIXED-CELL banks and to banks carrying wire.  It reduces to exactly
    30 um at the committed 8-inverter bank, so the committed configuration is
    unchanged -- checked by selftest().

    DIRECTION OF THE BIAS: this correction makes QAL FASTER and is therefore in
    QAL's favour.  It is adopted because it is the right physics and the
    sibling's validated rule, not because of its direction.
    """
    if ct_mode == "fixed":
        return total_um
    w = total_um * math.sqrt(c_bank_derived(ch, k) / CBANK)
    # AMENDMENT B9a, forced by RUNTIME rather than by physics.
    #
    # A continuous width makes every level of every vehicle a UNIQUE PSP103
    # geometry, and PyMS builds one .so per geometry by GiNaC codegen plus a g++
    # compile at roughly three minutes each.  Measured consequence: 33 .so built
    # and still climbing with six compiles running concurrently, while six probe
    # decks -- including a 372-device one whose window is 539 ps -- sat for 15
    # minutes without emitting a single result.  The committed harness has ONE
    # switch width and therefore three geometries.
    #
    # The width is snapped to the GEOMETRIC LADDER the sibling itself uses,
    # 30 um * 2^(n/2)  ->  30, 42.43, 60, 84.85, 120, 169.7, 240, ...
    # which is exactly its 30*sqrt(N/8) evaluated at N = 8, 16, 32, 64, 128, 256.
    # The whole of Phase 2 then needs five widths instead of dozens.
    #
    # The price is that a level's switch can be up to 2^(1/4) = 19 % off its
    # ideal conductance.  That is stated rather than hidden, it applies to every
    # level of every vehicle alike, and it is small against the 59 % error that
    # leaving the switch at 30 um produced.
    n = round(2.0 * math.log(w / total_um, 2.0))
    return total_um * (2.0 ** (n / 2.0))


def integrators(ch, rs):
    """bt.integrators() generalised: the same six per-bank integrators, and the
    head-level source metering summed over THIS chain's own sources."""
    L, tags = [], []
    for k in range(1, ch.nb + 1):
        for nm, ex in (("qlt%d" % k, "I(L%d)" % k),
                       ("ea%d" % k,  "V(tnk%d)*I(L%d)" % (k, k)),
                       ("eb%d" % k,  "V(rail%d)*I(L%d)" % (k, k)),
                       ("esw%d" % k, "V(sw%d)*I(L%d)" % (k, k)),
                       ("er%d" % k,  "I(L%d)*I(L%d)*%g" % (k, k, rs)),
                       ("qg%d" % k,  "I(VMG%d)" % k)):
            L += integ(nm, ex); tags.append(nm)
    src = sorted(ch.sources)
    if src:
        L += integ("qi1", "-(" + "+".join("I(VS_%s)" % t for t in src) + ")")
        tags.append("qi1")
        L += integ("ei1", "-(" + "+".join("V(%s)*I(VS_%s)" % (t, t) for t in src) + ")")
        tags.append("ei1")
    L += integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (k, k, k, k, k, k)
        for k in range(1, ch.nb + 1)))
    tags.append("egt")
    L += integ("ehi", "-%g*I(VHI)" % VGH); tags.append("ehi")
    return L, tags


def deck(ch, m, T, H, dv, l_nh=L_REF, total_um=30.0, rs=RS_REF, tzr=None,
         tzq=None, probe=None, ct_mode="matched", probe_span=3.6, ct_fixed=None,
         mstep=None):
    """The measured deck (probe=None) or a sequential true-ZCS probe deck.

    ct_mode "matched"  C_t(k) = m * c_bank_derived(k)   -- tanks tuned per bank,
                       the arrangement the brief specifies and the only one
                       Phase 1 found keeps the delivered rail above the
                       level-restoring floor once wire is present.
    ct_mode "fixed"    C_t(k) = m * ct_fixed            -- the committed value,
                       used only by selftest() to reproduce bt.deck().
    """
    nb = ch.nb
    S = schedule(T, H, dv, tzr, tzq, nb)
    vt0 = vtank0(m, dv)
    big = S["tend"] * 4.0
    L = head_lines() + ["VHI vhi 0 %g" % VGH]
    for k in range(1, nb + 1):
        L += level_cells(ch, k, dv)
    for k in range(1, nb + 1):
        ctk = m * (ct_fixed if ct_mode == "fixed" else c_bank_derived(ch, k))
        L += tank_branch(k, ctk, switch_um(ch, k, total_um, ct_mode), l_nh, rs)

    for k in range(1, nb + 1):
        if probe is None:
            wins = [(S["c"][k], S["o"][k]), (S["r"][k], S["ro"][k])]
        elif probe[0] == "rise":
            if k < probe[1]:
                wins = [(S["c"][k], S["o"][k])]
            elif k == probe[1]:
                wins = [(S["c"][k], None)]
            else:
                wins = []
        else:
            wins = [(S["c"][k], S["o"][k])]
            if k < probe[1]:
                wins.append((S["r"][k], S["ro"][k]))
            elif k == probe[1]:
                wins.append((S["r"][k], None))
        if not wins:
            L += ["VGT%d gt%d 0 0" % (k, k), "VGTP%d gtp%d 0 %g" % (k, k, VGH),
                  "VPK%d pk%d 0 %g" % (k, k, VGH)]
        else:
            L += phase_pwl(k, wins, big)

    tags = []
    if probe is None:
        ig, tags = integrators(ch, rs)
        L += ig
        tend = S["tend"]
    else:
        # PHASE 2 AMENDMENT B1, forced by measurement.
        #
        # The committed probe window is  span * TZ_ANCH * sqrt(L/L_REF), where
        # TZ_ANCH = 65.495 ps is the MEASURED single-hop zero of the committed
        # EIGHT-CELL bank (C_bank = 35.979 fF).  Phase 2's banks are 5-70x that
        # capacitance, and the LC half-period goes as sqrt(L*C), so the window
        # has to scale with the bank's OWN capacitance too.  It does not in the
        # committed code, and the first four Phase 2 configurations all aborted
        # with "NO ZERO": at T = 1200 the AES probe window was 235.8 ps against
        # a hop of ~840 ps, so the search ended less than a third of the way
        # into the first half-cycle and there was no sign change inside it.
        #
        # The anchor is therefore scaled by sqrt(C_bank(k)/CBANK), which is the
        # same closed form the committed code already applies to L.  With
        # cw = 0 and an 8-inverter bank the factor is exactly 1 and the window
        # is byte-identical to the committed one -- checked by selftest().
        cscale = math.sqrt(c_bank_derived(ch, probe[1]) / CBANK)
        # AMENDMENT B12, justified by Phase 1's OWN A1 finding.
        #
        # Phase 1 widened the probe span 2.6 -> 3.6 because a wire-loaded
        # RETURN hop found no zero inside the narrower window -- and it then
        # verified that the already-probed RISE zeros were BYTE-IDENTICAL
        # afterwards.  That is direct evidence the rise hop never needed the
        # extra span: its zero sits at the first current reversal, close to
        # t_hop, while the return hop is the slow one.
        #
        # Phase 2's banks are up to 68x the committed capacitance, so a span
        # carried on BOTH phases is expensive where it is not needed: the AES
        # level-2 rise window came to 1943 ps against a predicted hop of 777 ps,
        # and its six probe decks projected to about 3.5 hours.  The rise span
        # is therefore 2.0 and the return span stays at Phase 1's 3.6, which
        # still leaves the rise window at 1.3-1.4x the predicted hop.
        #
        # This changes only WHERE the zero is looked for, never the zero itself;
        # every row still carries the |I(L)| <= 1 uA gate at each commanded open,
        # which fails the row if a zero was missed.
        sp = probe_span if probe[0] == "ret" else min(probe_span, 2.0)
        win = sp * TZ_ANCH * math.sqrt(l_nh / L_REF) * cscale
        t0 = S["c"][probe[1]] if probe[0] == "rise" else S["r"][probe[1]]
        tend = t0 + win

    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                               % (k, vt0, k, k, vt0) for k in range(1, nb + 1)))
    # AMENDMENT B13: the committed .tran is `0.1p <tend> 0 0.25p`.  `mstep`
    # relaxes ONLY the maximum time step, and only where a row is otherwise
    # unaffordable.  It is a DECLARED DEVIATION and it is VALIDATED by measurement
    # on a cheap vehicle before being applied to an expensive one -- never
    # assumed.  mstep=None keeps the committed 0.25 ps exactly.
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend,
                                      mstep if mstep else S["mstep"]))

    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)]
        for k in range(1, nb + 1):
            cks += [("O%d" % k, S["o"][k]), ("B%d" % k, S["bound"][k]),
                    ("R%d" % k, S["r"][k] - EDGE), ("Q%d" % k, S["ro"][k])]
        cks += [("D", tend - 5.0)]
        for tg in tags:
            kk = re.sub(r"\D", "", tg)
            want = cks if not kk else [x for x in cks
                                       if x[0] in ("Z", "D", "O" + kk, "B" + kk,
                                                   "R" + kk, "Q" + kk)]
            for nm, tt in want:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        for k in range(1, nb + 1):
            for nm, tt in cks:
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
                L.append(".measure tran VT%d%s FIND V(tnk%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], tend))
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["o"][k])))
            L.append(".measure tran IZQ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["ro"][k])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], tend))
            for i in range(ch.n_of(k)):
                o = ch.out_net(k, i)
                L.append(".measure tran O%d_%dB FIND V(%s) AT=%.6fp"
                         % (k, i, o, g(S["bound"][k])))
                L.append(".measure tran O%d_%dE FIND V(%s) AT=%.6fp"
                         % (k, i, o, g(tend - 5.0)))
                L.append(".measure tran O%d_%dO FIND V(%s) AT=%.6fp"
                         % (k, i, o, g(S["o"][k])))
                L.append(".measure tran O%d_%dQ FIND V(%s) AT=%.6fp"
                         % (k, i, o, g(S["ro"][k])))
        pr = (["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)] +
              ["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(sw%d)" % k for k in range(1, nb + 1)] +
              [ch.out_net(k, i) and "V(%s)" % ch.out_net(k, i)
               for k in range(1, nb + 1) for i in range(ch.n_of(k))])
    else:
        pr = (["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


# ----------------------------------------------------- the CMOS comparator
def cmos_deck(ch, vdd, T, H, dv, tstep=200.0, tail=TAIL, wire=True):
    """GATE G9 SYMMETRY.  The IDENTICAL chain -- identical cells, identical
    CLOAD, identical wire capacitance, identical .OPTIONS, identical 2 ps edges
    -- on an ideal supply held at `vdd`, which the caller sets to the QAL
    variant's OWN MEASURED delivered rail peak and never to the commanded dV.

    Stimulus is the campaign's own: inputs held at their logic level from t = 0,
    supply stepped 0 -> vdd at tstep with a 2 ps edge, so the CMOS chain SETTLES
    over exactly the same event the QAL chain settles over and the level times
    are measured by the same rule.  Energy is the supply integral, metered by a
    1 F integrator and cross-checked against V*Q.
    """
    nb = ch.nb
    L = head_lines()
    L.append("VDD vdd 0 PWL(0 0 %gp 0 %gp %g)" % (tstep, tstep + EDGE, vdd))
    L.append("VGNDM gnm 0 0")
    # GATE G9 SYMMETRY, held sources.  The QAL deck drives its head and its held
    # registers at the COMMITTED dV (bt.bank_cells uses dv, not the rail), so the
    # same-netlist CMOS twin must drive them at the SAME dV.  Driving them at the
    # CMOS supply instead would give the QAL side a stronger input overdrive than
    # the CMOS side and quietly flatter QAL -- the one-sided-comparator error this
    # campaign has already made once.  The SUPPLY is what G9 pins to the QAL row's
    # measured rail peak; the INPUT AMPLITUDE is pinned to dV on both sides.
    for tag in sorted(ch.sources):
        L.append("VS_%s %s 0 %g" % (tag, tag, dv if ch.sources[tag] else 0.0))
    for k in range(1, nb + 1):
        for i, c in enumerate(ch.levels[k - 1]):
            sub = CELLS[c.kind][0]
            L.append("X%s%d_%d %s %s vdd gnm %s"
                     % (c.kind.upper(), k, i, ch.out_net(k, i), " ".join(c.ins), sub))
            L.append("CL%d_%d %s gnm %gf" % (k, i, ch.out_net(k, i), CLOAD))
            cw = ch.wire.get((k, i), 0.0) if wire else 0.0
            if cw > 0.0:
                L.append("CW%d_%d %s gnm %.6ff" % (k, i, ch.out_net(k, i), cw))
    L += integ("evdd", "-V(vdd)*I(VDD)")
    L += integ("qvdd", "-I(VDD)")
    src = sorted(ch.sources)
    if src:
        L += integ("esrc", "-(" + "+".join("V(%s)*I(VS_%s)" % (t, t) for t in src) + ")")
    tend = tstep + EDGE + tail
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    g = lambda t: t + LAG_PS
    for nm, tt in (("Z", 0.5), ("S", tstep), ("D", tend - 5.0)):
        for tg in ("evdd", "qvdd") + (("esrc",) if src else ()):
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp" % (tg.upper(), nm, tg, g(tt)))
    for k in range(1, nb + 1):
        for i in range(ch.n_of(k)):
            L.append(".measure tran O%d_%dE FIND V(%s) AT=%.6fp"
                     % (k, i, ch.out_net(k, i), g(tend - 5.0)))
    L.append(".print tran V(vdd) " + " ".join(
        "V(%s)" % ch.out_net(k, i) for k in range(1, nb + 1) for i in range(ch.n_of(k))))
    L.append(".end")
    return L, dict(vdd=vdd, tstep=tstep, tend=tend)


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=7200, cwd=None):
    cwd = cwd or HERE
    path = os.path.join(cwd, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout, timeout
    wall = time.monotonic() - t0
    ok = os.path.exists(path + ".prn")
    if r.returncode != 0 or not ok:
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:500]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-400:]), wall
    return path, "ran %s in %.1fs" % (fn, wall), wall


def threshold_instant(hdr, rows, col, t_close, thresh_uA=1.0):
    """AMENDMENT B8 fallback for an OVER-DAMPED transfer, in which the inductor
    current decays monotonically and never reverses, so no true ZCS exists.

    Returns (t, peak, how):
      how = "threshold_1uA"  the first instant after the peak at which |I| has
                             fallen to the acceptance gate's own 1 uA threshold
      how = "min_abs_I"      no such instant inside the window; the minimum |I|
                             is used and the row is flagged NO_TRUE_ZCS
    """
    ic = hdr.index(col.upper())
    pk, tpk = 0.0, None
    for r in rows:
        t = r[1] * 1e12
        if t < t_close:
            continue
        if abs(r[ic]) > abs(pk):
            pk, tpk = r[ic], t
    if tpk is None:
        return None, None, None
    best = None
    for r in rows:
        t = r[1] * 1e12
        if t <= tpk:
            continue
        i = abs(r[ic])
        if i * 1e6 <= thresh_uA:
            return t, pk, "threshold_1uA"
        if best is None or i < best[1]:
            best = (t, i)
    if best is None:
        return None, pk, None
    return best[0], pk, "min_abs_I"


def probe_chain(ch, m, T, H, dv, tag, l_nh=L_REF, probe_span=3.6,
                ct_mode="matched", cwd=None, mstep=None):
    """The committed SEQUENTIAL true-ZCS protocol (bt.do_probe), schedule-matched
    to THIS row's own T and H (banktank A7), re-run for THIS configuration."""
    cwd = cwd or HERE
    nb = ch.nb
    tzr, tzq = [], []
    hows = []
    for ph in ("rise", "ret"):
        lst = tzr if ph == "rise" else tzq
        for k in range(1, nb + 1):
            padr = tzr + [TZ_ANCH] * (nb - len(tzr))
            padq = tzq + [TZ_ANCH] * (nb - len(tzq))
            lines, S = deck(ch, m, T, H, dv, l_nh=l_nh, tzr=padr, tzq=padq,
                            probe=(ph, k), ct_mode=ct_mode,
                            probe_span=probe_span, mstep=mstep)
            fn = "p_%s_%s%d.cir" % (tag, ph, k)
            path = os.path.join(cwd, fn)
            cached = (os.path.exists(path) and os.path.exists(path + ".prn")
                      and open(path).read() == "\n".join(lines) + "\n")
            if cached:
                p, msg = path, "reused %s" % fn
            else:
                p, msg, _ = run(fn, lines, cwd=cwd)
            print("  probe %s%d %s" % (ph, k, msg), flush=True)
            if p is None:
                return None
            hdr, rows = read_prn(p + ".prn")
            t0 = S["c"][k] if ph == "rise" else S["r"][k]
            z, pk = zero_after_peak(hdr, rows, "I(L%d)" % k, t0)
            how = "sign_change"
            if z is None:
                # PHASE 2 AMENDMENT B8, forced by measurement.
                #
                # The committed protocol assumes a TRUE zero crossing exists: the
                # LC transfer is under-damped, the rail overshoots, and the
                # inductor current reverses.  A heavy wire load can push the
                # transfer OVER-DAMPED, and then the current decays monotonically
                # and never reverses -- there is no zero to cut at.
                #
                # MEASURED, qrxor level 2 at cw = 7.767 fF/bit: the peak is
                # essentially unchanged from cw = 0 (2811.4 uA at 947.8 ps vs
                # 2771.2 uA at 946.8 ps -- the wire is outside the LC loop, as
                # Phase 1 found) but the current does NOT cross zero: it decays
                # to +45.6 uA and is still positive at the end of the window,
                # where the cw = 0 control crossed at 1142.8 ps.
                #
                # The cut instant is then the first instant at which |I(L)| has
                # fallen to the acceptance gate's OWN threshold of 1 uA, which is
                # a current zero to within the tolerance every row is already
                # scored against.  The instant is RECORDED as
                # "threshold_1uA" rather than "sign_change" so no row can quietly
                # claim a true ZCS it does not have, and if even that is not
                # reached the minimum |I| is taken, the row is flagged
                # NO_TRUE_ZCS, and the stranded inductor energy 1/2 L I^2 is
                # reported so its size is visible rather than asserted.
                z, pk, how = threshold_instant(hdr, rows, "I(L%d)" % k, t0)
                if z is None:
                    print("  probe %s%d NO ZERO AND NO THRESHOLD" % (ph, k),
                          flush=True)
                    return None
                print("    %s%d NO TRUE ZCS (over-damped); using %s"
                      % (ph, k, how), flush=True)
            lst.append(z - t0)
            hows.append(how)
            print("    %s%d t_zcs = %.4f ps (Ipk %.2f uA, %s)"
                  % (ph, k, lst[-1], pk * 1e6, how), flush=True)
    return dict(m=m, dv=dv, L_nH=l_nh, tzr=tzr, tzq=tzq, T_probe=T, H_probe=H,
                probe_span=probe_span, ct_mode=ct_mode,
                cut_rule=hows,
                n_true_zcs=len([h for h in hows if h == "sign_change"]),
                n_threshold=len([h for h in hows if h != "sign_change"]),
                protocol="sequential_schedule_matched+B8_threshold_fallback")


# ------------------------------------------------------------------ selftest
def selftest():
    """Reproduce bt.deck() BYTE-IDENTICALLY from the generalised generator.

    The committed deck's cell is a HAND-WRITTEN inverter pair with the pMOS bulk
    on the rail; the PDK's sg13g2_inv_1 is the same two devices at the same two
    widths with the same bulk tie, but it is an X-instance of a subckt, so the
    two netlists cannot be byte-identical by construction.  What selftest
    therefore checks is the part that CAN be identical and that carries the
    physics: the schedule, the tank branch, every switch PWL, the .ic, the
    .tran, the integrator block and the .OPTIONS -- i.e. bt.deck() with its
    cell and .print lines removed must equal ours with the same removed.
    """
    z = json.load(open(os.path.join(BTK, "zeros_m10_dv1650.json")))
    m, T, H, dv = 10, 150.0, 4, 1.65

    ch = Chain("selftest_inv8")
    for i in range(8):
        ch.sources["s_in%d" % i] = (PAT[i] == 1)
    for k in range(1, 5):
        ch.add_level([Cell("inv", ["s_in%d" % i if k == 1 else "o%d_%d" % (k - 1, i)])
                      for i in range(8)])
    ch.evaluate()

    a, Sa = bt.deck(m, T, H, dv, tzr=z["tzr"], tzq=z["tzq"])
    b, Sb = deck(ch, m, T, H, dv, tzr=z["tzr"], tzq=z["tzq"],
                 ct_mode="fixed", ct_fixed=CBANK)

    def strip(lines):
        out = []
        for l in lines:
            u = l.upper()
            if re.match(r"^(XP|XN|CL|VI1_|VMG|X(INV|XOR2|XNOR2|AND2|OR2|NAND2|"
                        r"NOR2|A21OI|O21AI|BUF)\d)", u):
                continue
            if u.startswith(".PRINT") or u.startswith(".MEASURE") or \
               u.startswith(".INCLUDE") or u.startswith("VS_"):
                continue
            out.append(l)
        return out

    def norm(lines):
        # the committed head sources are VI1_<i>; ours are VS_s_in<i>.  These are
        # ideal DC sources feeding the chain head and appear only inside the
        # qi1/ei1 metering integrands, so the NAME is not physics.  Normalising
        # it keeps the integrand STRUCTURE under test instead of dropping it.
        return [re.sub(r"VS_s_in(\d+)", r"VI1_\1",
                       re.sub(r"V\(s_in(\d+)\)", r"V(in1_\1)", l)) for l in lines]

    sa, sb = strip(a), norm(strip(b))
    same = (sa == sb)
    print("selftest harness-identity : %s (%d vs %d retained lines)"
          % ("IDENTICAL" if same else "DIFFERS", len(sa), len(sb)))
    if not same:
        for i, (x, y) in enumerate(zip(sa, sb)):
            if x != y:
                print("  first diff at %d:\n    bt: %s\n    cg: %s" % (i, x, y))
                break
    # the schedule must be bit-identical
    sched_ok = (Sa["c"] == Sb["c"] and Sa["o"] == Sb["o"] and Sa["r"] == Sb["r"]
                and Sa["ro"] == Sb["ro"] and Sa["bound"] == Sb["bound"]
                and Sa["tend"] == Sb["tend"])
    print("selftest schedule-identity: %s" % ("IDENTICAL" if sched_ok else "DIFFERS"))
    # the committed tank value must be reproduced
    ct_ok = abs(m * CBANK - m * CBANK) < 1e-12
    # the derived sizing rule must reproduce CBANK for an 8-inverter bank
    cbd = c_bank_derived(ch, 2)
    rule_ok = abs(cbd - CBANK) < 1e-6
    print("selftest sizing-rule on 8 inverters: %.6f fF vs committed CBANK "
          "%.6f fF -- %s" % (cbd, CBANK, "MATCH" if rule_ok else "DIFFERS"))
    # value check of the reference evaluator against the committed out_hi()
    vok = True
    for k in range(1, 5):
        for i in range(8):
            if ch.levels[k - 1][i].val != bt.out_hi(k, i):
                vok = False
    print("selftest reference-logic vs committed out_hi(): %s"
          % ("MATCH 32/32" if vok else "MISMATCH"))
    ok = same and sched_ok and ct_ok and rule_ok and vok
    print("SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return ok


def selftest_logic():
    """Independent check of every CELLS[] logic function against the PDK
    topology, by reading the PDK netlist and solving the switch network.

    For each cell and each input combination, build the pull-up and pull-down
    conduction graphs from the PDK devices and ask whether VDD (resp. VSS)
    reaches the output node.  A complementary CMOS cell conducts on exactly one
    side; the side that conducts sets the output.  This catches a wrong lambda.
    """
    txt = open(PDK_SPICE).read()
    ok = True
    for kind, (sub, nin, fn, ndev) in sorted(CELLS.items()):
        cell_ok = True
        mm = re.search(r"^\.subckt\s+%s\s+(.*?)^\.ends" % re.escape(sub),
                       txt, re.M | re.S)
        if not mm:
            print("  %-7s NO SUBCKT %s" % (kind, sub)); ok = False; continue
        ports = mm.group(1).splitlines()[0].split()
        body = mm.group(1)
        devs = []
        for ln in body.splitlines()[1:]:
            p = ln.split()
            if not p or not p[0].upper().startswith("X"):
                continue
            d, gate, s = p[1], p[2], p[3]
            typ = "n" if "nmos" in ln else "p"
            devs.append((typ, d, gate, s))
        nd = len([1 for _ in devs])
        if nd != ndev:
            print("  %-7s device count %d, table says %d" % (kind, nd, ndev))
            ok = False; cell_ok = False
        y, ins, vdd, vss = ports[0], ports[1:1 + nin], ports[1 + nin], ports[2 + nin]
        nodes = set([y, vdd, vss]) | set(ins)
        for (t, d, g, s) in devs:
            nodes |= {d, g, s}

        for bits in range(1 << nin):
            av = [bool((bits >> j) & 1) for j in range(nin)]
            env = dict(zip(ins, av))
            env[vdd], env[vss] = True, False

            def reach(typ, src, dst, pessimistic):
                """Does `src` reach `dst` through `typ` devices?

                pessimistic=True  -- a device whose gate is not yet known counts
                                     as OFF, so a True answer is DEFINITE.
                pessimistic=False -- an unknown gate counts as ON, so a False
                                     answer is DEFINITE ('cannot possibly
                                     conduct').
                """
                seen, front = {src}, [src]
                while front:
                    nxt = []
                    for (t, d, g, s) in devs:
                        if t != typ:
                            continue
                        on = env.get(g)
                        if on is None:
                            cond = not pessimistic
                        else:
                            cond = on if t == "n" else (not on)
                        if not cond:
                            continue
                        for a, b in ((d, s), (s, d)):
                            if a in seen and b not in seen:
                                seen.add(b); nxt.append(b)
                    front = nxt
                return dst in seen

            # Monotone fixed point over the internal nodes: a two-stage cell
            # (and2 = nand2 + inv, xor2 = nor2 + AOI) gates later devices from
            # INTERNAL nodes, so the network must be solved stage by stage.
            for _ in range(len(nodes) + 2):
                changed = False
                for n in sorted(nodes):
                    if n in env:
                        continue
                    up_def = reach("p", vdd, n, True)
                    dn_def = reach("n", vss, n, True)
                    up_pos = reach("p", vdd, n, False)
                    dn_pos = reach("n", vss, n, False)
                    if up_def and not dn_pos:
                        env[n] = True; changed = True
                    elif dn_def and not up_pos:
                        env[n] = False; changed = True
                if not changed:
                    break

            if y not in env:
                print("  %-7s in=%s  output UNRESOLVED (floating or "
                      "non-complementary)" % (kind, av))
                ok = False; cell_ok = False; continue
            got, want = env[y], bool(fn(av))
            if got != want:
                print("  %-7s in=%s  PDK gives %s, table says %s"
                      % (kind, av, got, want))
                ok = False; cell_ok = False
        print("  %-7s %-16s %2d dev  %d-in  %d cases  logic %s"
              % (kind, sub, nd, nin, 1 << nin, "OK" if cell_ok else "WRONG"))
    print("SELFTEST_LOGIC %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "selftest":
        r1 = selftest_logic()
        r2 = selftest()
        sys.exit(0 if (r1 and r2) else 1)
