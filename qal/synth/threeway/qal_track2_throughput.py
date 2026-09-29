#!/usr/bin/env python3
"""TRACK 2 -- the REGISTER-TAX THROUGHPUT claim, tested against measured SG13G2
flop overhead.

THE CLAIM UNDER TEST (qal_crossover_map.py, commit f4fbc9e): a QAL wave settles a
whole LEVEL per hop with NO flop between levels, while a pipelined CMOS stage pays
CQ + setup + clock skew/jitter every stage; therefore QAL out-throughputs pipelined
CMOS by 1.5x (conservative) to 3.0x (aggressive double-banked), "DEVICE-INDEPENDENT".

The original derivation was in normalized units tau = T/RC_g with ASSUMED constants
depth=2, k_reg=5, K_settle=3.  Nothing in it was measured.  This file replaces every
one of those constants with a number taken from the IHP SG13G2 PDK (liberty +
OpenSTA), and from the campaign's own committed QAL hop measurement.

WHAT IS MEASURED HERE (all SG13G2 typ 1.20 V 25 C, sg13g2_stdcell_typ_1p20V_25C.lib):
  * flop overhead t_reg = CLK->Q + library setup, taken as the OpenSTA min period of
    a real FF->FF path (scratch decks v_dfrbpq_1_*.v, reproduced by fn treg_table()).
  * one-logic-level stage time, as the OpenSTA min period of FF->gate->FF for the
    cell types that actually sit on the two critical paths.
  * clock uncertainty: 0.25 ns, the librelane sg13g2 default
    (CLOCK_UNCERTAINTY_CONSTRAINT) -- and the value the peer's own 4.75 ns ALU
    closure actually ran with (mylex probes/layopt/evidence/alu_cmos/work/
    constraints.tcl).  It is a BUDGET, not a measurement: in the routed ALU the
    launch/capture clock delays differ by only 10.8 ps.  Both corners are carried.
  * gate drive resistance R = d(delay)/d(C_load) from the liberty delay tables ->
    the adiabatic SETTLE FLOOR t_hop >= K_settle * R * C_load.
  * d=1 pipeline register COUNT, levelized from the real mapped netlists.

WHAT IS ASSUMED (flagged at every use):
  * K_settle = 3 (the campaign's own constant: below tau=3 a settling gate never
    reaches dV).  Sensitivity is reported.
  * n_beat, the number of power-clock beats per logic level: 2 conservative,
    1 aggressive (double-banked).  This is the single largest lever and it is an
    ARCHITECTURAL unknown, not a measured one.

WHAT IS TAKEN FROM THE COMMITTED QAL RECORD (MEASURED, stat-sim/qal):
  * t_hop = 266.76 ps true zero at the tg15p switch optimum; all 8 bank cells settle.
"""

# ----------------------------------------------------------------------------
# MEASURED: SG13G2 flop overhead and one-level stage time.
# OpenSTA min period = |data arrival| + |library setup| on an FF->[gate]->FF path,
# sg13g2_dfrbpq_1, set_clock_transition 0.15 (the flow's own constraint),
# extra net load applied to both the register output net and the gate output net.
# ps.
# ----------------------------------------------------------------------------
STAGE_PS = {            # load_fF -> {logic : FF->logic->FF min period}
    0.0:  {"none": 307.1, "inv": 330.1, "nand2": 334.7, "a21oi": 366.5,
           "o21ai": 392.5, "mux2": 398.0, "xnor2": 413.4},
    6.91: {"none": 335.7, "inv": 383.8, "nand2": 409.3, "a21oi": 449.2,
           "o21ai": 486.7, "mux2": 457.8, "xnor2": 485.0},
    20.0: {"none": 390.0, "inv": 494.8, "nand2": 559.4, "a21oi": 608.7,
           "o21ai": 666.0, "mux2": 574.3, "xnor2": 654.6},
}
CQ_SETUP = {0.0: (213.4, 93.7), 6.91: (233.6, 102.1), 20.0: (272.0, 118.0)}
UNCERT_PS = 250.0       # librelane sg13g2 CLOCK_UNCERTAINTY_CONSTRAINT (flow budget)
ROUTED_SKEW_PS = 10.8   # MEASURED launch-capture clock delay delta, routed ALU

# MEASURED: gate drive resistance R = d(delay)/d(C_load), liberty (ohm)
R_OHM = {"inv_1": 2772, "nand2_1": 4083, "nor2_1": 5755, "and2_1": 2793,
         "or2_1": 2277, "xnor2_1": 2787, "xor2_1": 2263, "mux2_1": 2286,
         "a21oi_1": 5785, "o21ai_1": 6872, "a21o_1": 2280, "nor2b_1": 5756}
K_SETTLE = 3.0          # ASSUMED (campaign constant)
CL_FF = 6.91            # MEASURED mean sink load, mapped ALU

# MEASURED design anchors
DESIGNS = {
    # comb_path_ps / path_stages: MEASURED OpenSTA critical path.  t_level_mean =
    # path/stages is what a RECURRENCE pays per level; t_level_worst (the slowest
    # single cell on the path) is what a d=1 CLOCK must accommodate.
    "sha_slice": dict(D_map=8, D_gen=10, comb=56, seq=0, comb_path_ps=928.1,
                      path_stages=8, t_level_mean=116.0, worst_cell="o21ai",
                      flops_d1=288, flops_d1_lb=157, shipped_ps=None),
    "vortex_alu": dict(D_map=38, D_gen=37, comb=4027, seq=188, comb_path_ps=4164.8,
                       path_stages=37, t_level_mean=112.6, worst_cell="o21ai",
                       flops_d1=27398, flops_d1_lb=18043, shipped_ps=4750.0),
}
T_HOP_PS = 266.76       # MEASURED (committed), tg15p true zero -- RAIL transfer time
# ---------------------------------------------------------------------------
# MEASURED HERE (track2/ decks, Xyce/PSP103, own PYMS_VAE_CACHE): the committed
# 266.76 ps is the INDUCTOR-TRANSFER time, not the gate-valid time.  At the freeze
# instant the settling cell output is only PART of the way to the rail.  The
# throughput-relevant beat is when the level's outputs are usable as the next
# level's inputs.  Control check: my 8x inv_1 deck reproduces the committed anchor
# (true zero 265.6 vs 266.76 ps; delivered level 0.6759 V vs committed VBEND
# 0.6759-0.6846; IPK 194.4 uA vs the record's ~195 uA).
#   bank            rail_pk  delivered  hop(true0)  90%valid  95%valid  99%valid
#   8x inv_1          0.737     0.6759      265.6      292.1     310.9     352.1
#   8x o21ai_1 same   0.614     ~0.17       272.0      NEVER (29% of rail at 400 ps)
#   8x o21ai_1 hi-sw  0.963     0.737       275.5      437.8     506.3     ~700
# o21ai_1 is the mapped ALU's MOST COMMON cell (855 of 4027).  On the committed
# operating point it DOES NOT SETTLE AT ALL; the bank's extra capacitance drops the
# rail to 0.614 V, inside the campaign's own functional cliff, and the 2-high pMOS
# pull-up has no headroom over |Vt| (worsened by the series device's reverse body
# bias).  Raising the swing to ~0.96 V rescues correctness but the level needs
# 437.8 ps (90%) / 506.3 ps (95%) -- 1.5-1.7x the inverter bank, 1.6-1.9x the hop.
# ---------------------------------------------------------------------------
# MEASURED gate-valid beat, ps after switch-on.  (cell, CL_fF, validity%) -> beat.
# CL=2 fF is the campaign anchor's own load; CL=6.91 fF is the mapped ALU's MEASURED
# mean sink load and is the LOAD-MATCHED condition against the CMOS FF->gate->FF
# numbers above.  Matching the load is what settles the claim.
T_VALID = {("inv", 2.0, 90): 292.1, ("inv", 2.0, 95): 310.9, ("inv", 2.0, 99): 352.1,
           ("o21ai", 2.0, 90): 437.8, ("o21ai", 2.0, 95): 506.3, ("o21ai", 2.0, 99): 700.0,
           ("o21ai", 6.91, 90): 661.0, ("o21ai", 6.91, 95): 796.3}
# CL=6.91 fF o21ai bank MEASURED: hop(true0) 275.8 ps, rail peak 0.9472 V, delivered
# level 0.6112 V, 50% of rail only at 334 ps -- i.e. the gate is barely half-settled
# when the inductor hand-off is already over.
E_FLOP_FJ = 59.05       # MEASURED OpenSTA report_power, dfrbpq_1, alpha=0.226, 1.42 fF
E_GATE_FJ = 1.09        # MEASURED OpenSTA report_power, a21oi_1, same conditions
ALU_SHIPPED_PJ = 46.67  # MEASURED-BY-PEER liberty power, as-shipped ALU


def t_reg(load=6.91, uncertainty=UNCERT_PS):
    cq, su = CQ_SETUP[load]
    return cq + su + uncertainty


def t_level(design, load=6.91):
    """one-logic-level delay = FF->gate->FF minus FF->FF, for the cell type that
    actually binds that design's critical path."""
    d = DESIGNS[design]
    return STAGE_PS[load][d["worst_cell"]] - STAGE_PS[load]["none"]


def cmos_stage_ps(design, load=6.91, uncertainty=UNCERT_PS, levels=1):
    """max-throughput pipelined CMOS stage time.  levels=1 is CMOS's OWN optimum:
    throughput 1/(d*t_level + t_reg) is maximized at d=1."""
    return levels * t_level(design, load) + t_reg(load, uncertainty)


def qal_beat_ps(n_beat=1, t_hop=T_HOP_PS):
    return n_beat * t_hop


def settle_floor_ps(cell, cl=CL_FF, k=K_SETTLE):
    """DERIVED: the hop cannot be shorter than the worst gate's settle time."""
    return k * R_OHM[cell] * cl * 1e-15 * 1e12


def d_star(design, n_beat=1, load=6.91, uncertainty=UNCERT_PS, t_hop=T_HOP_PS):
    """THE ONE NUMBER.  d* = t_reg / (n_beat*t_hop - t_level).
    QAL beats CMOS whenever CMOS must cut stages finer than d* levels -- and loses
    any dependence loop whose body is deeper than d* levels.  Same constant governs
    both, which is exactly why 'streaming wins / recurrence inverts'."""
    tl = t_level(design, load)
    den = n_beat * t_hop - tl
    if den <= 0:
        return float("inf")
    return t_reg(load, uncertainty) / den


def main():
    print("=" * 96)
    print("TRACK 2 -- the register-tax throughput claim vs MEASURED SG13G2 flop overhead")
    print("=" * 96)
    print("\n(a) THE HONEST CMOS SIDE -- flop overhead is MEASURED, not assumed")
    print("-" * 96)
    for load in (0.0, 6.91, 20.0):
        cq, su = CQ_SETUP[load]
        print("  load %5.2f fF : CLK->Q %6.1f + setup %6.1f = t_reg %6.1f ps (ideal clock)"
              "   + uncert %3.0f -> %6.1f ps"
              % (load, cq, su, cq + su, UNCERT_PS, cq + su + UNCERT_PS))
    print("  routed-ALU MEASURED launch-capture clock delta: %.1f ps (the 250 ps is a BUDGET)"
          % ROUTED_SKEW_PS)
    print()
    print("  %-11s %7s %9s %9s %11s %11s" % ("design", "D_map", "t_level", "t_reg", "stage(d=1)", "Gop/s"))
    for nm in DESIGNS:
        for unc, tag in ((UNCERT_PS, "flow-250ps"), (100.0, "good-tree-100"), (0.0, "ideal-clk-0")):
            s = cmos_stage_ps(nm, 6.91, unc)
            print("  %-11s %7d %9.1f %9.1f %11.1f %11.3f  [%s]"
                  % (nm, DESIGNS[nm]["D_map"], t_level(nm), t_reg(6.91, unc), s, 1000.0 / s, tag))
    print("\n  d=1 REGISTER COST (MEASURED, levelized from the mapped netlists):")
    for nm, d in DESIGNS.items():
        for key, tag in (("flops_d1", "output-aligned"), ("flops_d1_lb", "no-align lower bd")):
            area = d[key] * 48.9888
            e = d[key] * E_FLOP_FJ / 1000.0
            print("    %-11s %-18s %6d pipeline flops (%4.1f/comb cell, %5.0fx the %d"
                  " architectural); %9.0f area units; %8.3f pJ/op register energy"
                  % (nm, tag, d[key], d[key] / d["comb"], d[key] / max(1, d["seq"]),
                     d["seq"], area, e))
    dd = DESIGNS["vortex_alu"]
    print("    Vortex ALU: that register energy is %.1fx-%.1fx the ENTIRE as-shipped ALU (%.2f pJ/op),"
          " and %.0fx-%.0fx its area (49118)."
          % (dd["flops_d1_lb"] * E_FLOP_FJ / 1000.0 / ALU_SHIPPED_PJ,
             dd["flops_d1"] * E_FLOP_FJ / 1000.0 / ALU_SHIPPED_PJ, ALU_SHIPPED_PJ,
             dd["flops_d1_lb"] * 48.9888 / 49118, dd["flops_d1"] * 48.9888 / 49118))
    print("    per-level energy ratio MEASURED: 1 flop %.2f fJ/cycle vs 1 a21oi gate %.2f fJ/cycle"
          " = %.0fx register tax." % (E_FLOP_FJ, E_GATE_FJ, E_FLOP_FJ / E_GATE_FJ))

    print("\n(b) THE QAL SIDE -- 1 op per beat, parametric in t_hop")
    print("-" * 96)
    for n in (1, 2):
        b = qal_beat_ps(n)
        print("  n_beat=%d : beat %6.1f ps -> %6.3f Gop/s streaming; latency D*beat"
              " = %6.2f ns (sha_slice) / %6.2f ns (ALU)"
              % (n, b, 1000.0 / b, DESIGNS["sha_slice"]["D_map"] * b / 1000.0,
                 DESIGNS["vortex_alu"]["D_map"] * b / 1000.0))
    print("  DERIVED SETTLE FLOOR (the hop cannot outrun the gates it carries):")
    for c in ("inv_1", "mux2_1", "a21oi_1", "o21ai_1"):
        print("    %-9s R=%5d ohm -> RC@%.2f fF = %5.1f ps -> K=%.0f floor %6.1f ps"
              % (c, R_OHM[c], CL_FF, R_OHM[c] * CL_FF * 1e-3, K_SETTLE, settle_floor_ps(c)))
    fl = settle_floor_ps("o21ai_1")
    print("    worst mapped-ALU cell (o21ai_1, 855 instances) floor %.1f ps."
          "  committed hop %.1f ps = %.2fx the floor -> it DOES settle."
          % (fl, T_HOP_PS, T_HOP_PS / fl))
    print("    *** THAT FLOOR IS REFUTED BY MEASUREMENT AS AN ACHIEVABLE BEAT (see d2). ***")
    print("    Liberty R is the ON resistance at Vgs=1.2 V.  A QAL gate settles on a rail that")
    print("    spends much of the ramp NEAR |Vt|, so the real settle time is 4.6x (inv, 2 fF) to")
    print("    15x (o21ai, 6.91 fF) the K*R*C floor.  MEASURED beats are in T_VALID.  The one")
    print("    thing the floor does establish: a 20 ps hop is %.0fx below even the optimistic"
          % (fl / 20.0))
    print("    floor, so Track 1's L knob cannot buy throughput -- the rail can hop that fast,")
    print("    the gates cannot settle that fast.")

    print("\n(c) THE CROSSOVER -- required t_hop, and the throughput ratio at CMOS's own optimum")
    print("-" * 96)
    print("  QAL wins streaming iff  n_beat*t_hop < t_level + t_reg  =>  t_hop < (t_level+t_reg)/n_beat")
    print("  %-11s %-10s %5s %13s %13s %9s %8s"
          % ("design", "clock", "nb", "req t_hop ps", "measured ps", "clears?", "ratio"))
    for nm in DESIGNS:
        for unc, tag in ((UNCERT_PS, "flow-250"), (100.0, "tree-100"), (0.0, "ideal-0")):
            for n in (1, 2):
                s = cmos_stage_ps(nm, 6.91, unc)
                req = s / n
                print("  %-11s %-10s %5d %13.1f %13.1f %9s %7.2fx"
                      % (nm, tag, n, req, T_HOP_PS, "YES" if T_HOP_PS < req else "no",
                         s / qal_beat_ps(n)))
    print("\n  d* = t_reg/(n_beat*t_hop - t_level)  -- levels/stage below which QAL wins:")
    for nm in DESIGNS:
        for unc, tag in ((UNCERT_PS, "flow-250"), (100.0, "tree-100"), (0.0, "ideal-0")):
            print("    %-11s %-9s n=1 d*=%5.2f levels   n=2 d*=%5.2f levels"
                  % (nm, tag, d_star(nm, 1, 6.91, unc), d_star(nm, 2, 6.91, unc)))
    print("\n  LATCH COUNTER-LEVER -- the strongest pure-CMOS answer, and it nearly kills the claim.")
    print("  MEASURED liberty sg13g2_dlhq_1: transparent D->Q 176.5 ps, GATE->Q 150.5 ps,")
    print("  setup 102.7 ps.  A two-phase time-borrowing latch pipeline pays ONE D->Q per level")
    print("  instead of CQ+setup, and borrowing absorbs skew -- but the phase NON-OVERLAP must")
    print("  cover the skew or the stage races through.  Band = borrow-everything .. non-overlap")
    print("  pays the full 250 ps.  DERIVED from liberty; no latch pipeline was closed.")
    for lo_hi, tag in ((0.0, "borrow-all"), (UNCERT_PS, "non-overlap=uncert")):
        s = t_level("vortex_alu") + 176.5 + lo_hi
        print("    latch stage %6.1f ps [%-19s] -> %.3f Gop/s ; QAL n=1 %.2fx  n=2 %.2fx"
              % (s, tag, 1000.0 / s, s / qal_beat_ps(1), s / qal_beat_ps(2)))
    print("\n  THROUGHPUT PER AREA (the comparison that survives the d=1 strawman):")
    a_logic = 49118.0
    for tag, gops, area in (
            ("CMOS as-shipped (1 cyc/op)", 1000.0 / DESIGNS["vortex_alu"]["shipped_ps"], a_logic),
            ("CMOS d=1 pipelined (flow)", 1000.0 / cmos_stage_ps("vortex_alu"),
             a_logic + DESIGNS["vortex_alu"]["flops_d1"] * 48.9888),
            ("QAL n=2 (single bank)", 1000.0 / qal_beat_ps(2), a_logic),
            ("QAL n=1 (double-banked, 2x logic)", 1000.0 / qal_beat_ps(1), 2 * a_logic)):
        print("    %-34s %6.3f Gop/s  area %9.0f  -> %8.3f Gop/s per Marea"
              % (tag, gops, area, gops / area * 1e6))
    print("\n(d) THE RECURRENCE CAVEAT -- tested, not assumed")
    print("-" * 96)
    print("  A dependence loop cannot be pipelined: its initiation interval IS its latency.")
    print("  CMOS pays t_reg ONCE per loop (one flop, whole comb body); QAL pays n_beat*t_hop")
    print("  per LEVEL with no way to merge levels.  Ratio -> n_beat*t_hop/t_level as D grows.")
    print("  %-11s %-22s %11s %11s %11s" % ("design", "loop", "CMOS ns", "QAL n=1", "QAL n=2"))
    for nm, d in DESIGNS.items():
        cm = (d["comb_path_ps"] + t_reg(6.91, UNCERT_PS)) / 1000.0
        q1 = d["D_map"] * qal_beat_ps(1) / 1000.0
        q2 = d["D_map"] * qal_beat_ps(2) / 1000.0
        print("  %-11s %-22s %11.3f %11.3f %11.3f   QAL slower by %.2fx / %.2fx"
              % (nm, "1 flop + whole body", cm, q1, q2, q1 / cm, q2 / cm))
    d = DESIGNS["vortex_alu"]
    print("  as-shipped ALU recurrence (back-to-back dependent ops) = the closed cycle %.2f ns"
          " -> %.4f Gop/s; QAL %.3f ns -> %.4f Gop/s = %.2fx SLOWER"
          % (d["shipped_ps"] / 1000, 1000 / d["shipped_ps"],
             d["D_map"] * T_HOP_PS / 1000, 1000 / (d["D_map"] * T_HOP_PS),
             d["D_map"] * T_HOP_PS / d["shipped_ps"]))
    for nm, dd in DESIGNS.items():
        tm = dd["t_level_mean"]
        print("  %-11s per-level asymptote = %.1f/%.1f = %.2fx (n=1) / %.2fx (n=2)"
              " -- QAL is permanently this much slower on any deep recurrence."
              % (nm, T_HOP_PS, tm, T_HOP_PS / tm, 2 * T_HOP_PS / tm))
    print("  REDONE ON THE MEASURED LOAD-MATCHED BEAT (o21ai, CL=6.91 fF, 90% valid, 661.0 ps):")
    for nm, dd in DESIGNS.items():
        cm = (dd["comb_path_ps"] + t_reg(6.91, UNCERT_PS)) / 1000.0
        for n in (1, 2):
            q = dd["D_map"] * n * T_VALID[("o21ai", 6.91, 90)] / 1000.0
            print("    %-11s n=%d  QAL loop %7.2f ns vs CMOS %6.3f ns -> QAL %5.2fx SLOWER"
                  % (nm, n, q, cm, q / cm))
    print("    per-level asymptote on the honest beat = %.1f/%.1f = %.2fx (n=1)"
          % (T_VALID[("o21ai", 6.91, 90)], DESIGNS["vortex_alu"]["t_level_mean"],
             T_VALID[("o21ai", 6.91, 90)] / DESIGNS["vortex_alu"]["t_level_mean"]))
    print("  OCCUPANCY: the wave needs D independent ops resident to reach peak.")
    for w in (4, 8, 16, 37, 38):
        eff = min(1.0, w / DESIGNS["vortex_alu"]["D_map"])
        print("    %2d independent ops -> ALU wave %5.1f%% occupied -> %.3f Gop/s (n=1)"
              % (w, 100 * eff, eff * 1000.0 / qal_beat_ps(1)))
    print("    the campaign's Vortex 'mini' config is NUM_WARPS=4 x NUM_THREADS=4:")
    print("    4 independent instruction streams, so 4/38 = 10.5% wave occupancy.")

    print("\n(d2) THE CROSSOVER ON THE MEASURED GATE-VALID BEAT, LOAD-MATCHED")
    print("-" * 96)
    print("  The beat is NOT the rail's true zero.  MEASURED at the freeze instant the settling")
    print("  output sits at 79% of the rail (inv bank, CL=2 fF), 50% (o21ai, CL=2 fF), 41%")
    print("  (o21ai, CL=6.91 fF).  Load-matched rows are the ones that decide the claim.")
    print("  %-9s %5s %6s %3s %9s   %s" % ("bank cell", "CL_fF", "valid", "nb", "beat ps",
                                            "ratio vs CMOS d=1 [flow-250/tree-100/ideal-0]"))
    best = 0.0
    for cell, cl, lvlcell, load in (("inv", 2.0, "inv", 0.0), ("o21ai", 2.0, "o21ai", 0.0),
                                    ("o21ai", 6.91, "o21ai", 6.91)):
        for val in (90, 95):
            for n in (1, 2):
                if (cell, cl, val) not in T_VALID:
                    continue
                b = n * T_VALID[(cell, cl, val)]
                base = STAGE_PS[load][lvlcell]
                rs = [(base + u) / b for u in (UNCERT_PS, 100.0, 0.0)]
                best = max(best, max(rs))
                print("  %-9s %5.2f %5d%% %3d %9.1f   %6.2fx / %6.2fx / %6.2fx %s"
                      % (cell, cl, val, n, b, rs[0], rs[1], rs[2],
                         "" if max(rs) >= 1.5 else "<- under 1.5x at every corner"))
    print("  BEST ratio over ALL load-matched corners: %.2fx   (claimed band was 1.5-3.0x)" % best)
    print("  vs the LATCH pipeline instead of flops: o21ai CL=6.91 90 pct n=1 -> %.2fx-%.2fx"
          % ((STAGE_PS[6.91]["o21ai"] - STAGE_PS[6.91]["none"] + 176.5) / T_VALID[("o21ai", 6.91, 90)],
             (STAGE_PS[6.91]["o21ai"] - STAGE_PS[6.91]["none"] + 176.5 + UNCERT_PS) / T_VALID[("o21ai", 6.91, 90)]))
    print("  and on the COMMITTED operating point the o21ai bank never settles at all -> no beat.")

    print("\n(e) VERDICT ON 1.5-3x")
    print("-" * 96)
    print("  normalized constants, MEASURED vs the ORIGINAL's assumed values:")
    rc = R_OHM["a21oi_1"] * CL_FF * 1e-3
    print("    RC_g (a21oi @6.91 fF)        %.1f ps   [MEASURED]" % rc)
    print("    k_reg = t_reg/RC_g           %.1f (flow) / %.1f (ideal)   vs ASSUMED 5"
          % (t_reg(6.91, UNCERT_PS) / rc, t_reg(6.91, 0.0) / rc))
    print("    K_settle = t_hop/RC_g        %.2f as operated; floor 3        vs ASSUMED 3"
          % (T_HOP_PS / rc))
    print("    t_level/RC_g                 %.2f                            vs ASSUMED 2"
          % (t_level("vortex_alu") / rc))
    print("    => the two errors partially cancel; speed_ratio (2+k_reg)/(n*K_settle) = %.2fx"
          % ((t_level("vortex_alu") / rc + t_reg(6.91, UNCERT_PS) / rc) / (1 * T_HOP_PS / rc)))


if __name__ == "__main__":
    main()
