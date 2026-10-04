#!/usr/bin/env python3
"""Energy-vs-duty COMPOSITION for GHASH (GF(2^128) carry-less MAC) as a self-timed
static-CMOS FSM -- the THIRD self-timed-FSM design-space point after SHA-256 and AES-128,
completing the Ethernet MACsec (802.1AE GCM-AES-128) primitive.

Companion to ../aes_fsm/compose_aes128.py and ../sha_fsm/compose_sha256.py; SAME method.
GHASH is the authentication half of GCM-AES: for each 128b block C_i,
    Y_i = (Y_{i-1} XOR C_i) . H   mod P,   P = x^128 + x^7 + x^2 + x + 1 (the GCM poly),
H = AES_K(0^128) = the hash subkey, "." = carry-LESS GF(2^128) multiply then reduce mod P.
NO S-box, NO carry, NO adder ripple -- pure XOR/AND trees. State = the 128b accumulator Y
(+ H held constant). This is the carry-LESS, most-REGULAR settle of the three.

THE APPROACH (proven on accumulator, SHA-256, AES-128): a self-timed static-CMOS FSM =
precharge-free static next-state logic + edge-triggered DFF state register + a done-pulsed
capture (in-kind replica delay) -- NOT domino. It holds state and dissipates only on
transitions, so it sheds the CLOCK FLOOR at low duty -> a DUTY-SHAPED lower-power win;
per-op it is ~parity with clocked CMOS.

USER DIRECTIVE 2026-10-02: "Parity is fine, stat-sim modeling is preferable to SPICE." ->
NO Xyce. Energy is COMPOSED from measured anchors (yosys cell counts x the measured
sha_slice per-cell energy 3.683 fJ/cell + the add8 clock/register coefficients).

PROVENANCE TAGS on every figure:
  [MEAS]     measured on SG13G2/PSP103 transistors (Xyce), this campaign
  [COMPOSED] derived this session: yosys synth (same recipe as the sha_slice anchor)
             + OpenSTA, scaled by the [MEAS] sha_slice per-cell / per-area energy
  [EST]      honest structural estimate (flop count, activity factor, detector cost)

MULTIPLIER NUMBERS are the MULTIPLIER-COST AGENT's authoritative feed (GFMUL_ANALYSIS.md,
this directory): three GF(2^128) forms, each iverilog-verified 310/310 vs the validated
GHASH reference before its cell count was reported. This compose consumes that feed directly
(the "use the multiplier-cost agent's per-mult number" directive) and makes the KARATSUBA
parallel form the PRIMARY (the agent's "realistic parallel choice"); schoolbook is the naive
upper bound, bit-serial the area form.

VERIFICATION (never self-asserted): an independent Python GHASH reference with the correct
GCM bit-reflection (bit 0 = MSB of byte 0) was cross-checked THIS session vs pycryptodome:
  * H = AES_0(0)          = 66e94bd4ef8a2c3b884cfa59ca342b2e  (NIST SP 800-38D)  PASS
  * empty GCM tag (k=iv=0)= 58e2fccefa7e3061367f1d57a4e7455a  (NIST SP 800-38D)  PASS
  * 50/50 random (AAD,PT) vectors: ref GHASH(H,A,C)^E_K(J0) == pycryptodome tag  PASS
(The RTL lane's ghash_fsm.v = 128b Y + 128b H + 8b block counter = 264 flops, one
ghash_round/block; its functional NIST proof is the sibling deliverable. This file is the
ENERGY-vs-duty half.)

Run:  python3 compose_ghash.py          (no SPICE launched here)
"""

# ============================================================================
# 1. MEASURED ANCHORS  [MEAS]  (shared with the SHA-256 and AES-128 compositions)
# ============================================================================
E_SHA_SLICE   = 232.0    # fJ/op, static-CMOS 8b round core {maj,ch,add} @ alpha=0.476 [MEAS]
A_SHA_SLICE_S = 644.11   # um^2, sha_slice re-synth (my recipe) -> calibration basis   [COMPOSED]
N_SHA_SLICE_S = 63       # cells, sha_slice re-synth (my recipe) -> calibration basis   [COMPOSED]
E_CLK         = 28.2     # fJ/DFF/cycle  (clock-pin+internal, idle)                     [MEAS add8]
E_REGTOG      = 45.0     # fJ/DFF/toggle (Q switches + its load)                        [MEAS add8]
E_CMP_DONE    = (144.0, 400.0)   # fJ, per-op analog / current-sense completion done    [MEAS/EST]
E_DLINE_RATE  = 500.0 / 1.968    # = 254 fJ/ns of in-kind replica delay line            [MEAS add8]

e_per_cell = E_SHA_SLICE / N_SHA_SLICE_S          # = 3.683 fJ/cell/op (recipe-consistent)
e_per_area = E_SHA_SLICE / A_SHA_SLICE_S          # = 0.360 fJ/um^2/op

# ============================================================================
# 2. MULTIPLIER-COST AGENT FEED  [COMPOSED]  (GFMUL_ANALYSIS.md, same recipe + anchor)
#    Three GF(2^128) forms, each iverilog 310/310 vs the validated GHASH ref before count.
#    per_cell = 3.683 fJ (identical anchor). "fJ/block" = one multiply + the 128b (Y^C) XOR.
# ============================================================================
#                     cells    depth   path_ns   E_mult_fJ   E_block_fJ
GFMUL = {
 "bitserial": dict(cells=259,   depth=2,  t=0.126, e_mult=122083.6, e_block=122554.9, cyc=128),
 "schoolbook":dict(cells=32999, depth=13, t=1.615, e_mult=121520.1, e_block=121991.5, cyc=1),
 "karatsuba": dict(cells=14137, depth=19, t=3.899, e_mult=52060.1,  e_block=52531.4,  cyc=1),
}
PRIMARY = "karatsuba"     # the mult agent's "realistic parallel choice" -> carry forward

# OPTIONAL override hook: if the mult-cost agent (or a later tuned/hybrid-Karatsuba build)
# supplies a different per-block energy, drop it in here and it replaces the PRIMARY figure.
E_BLOCK_OVERRIDE = None    # fJ/block  [COMPOSED/MEAS] <- substitute if a newer number lands

# ============================================================================
# 3. STRUCTURAL ESTIMATES  [EST]  (held state; reconciled with the RTL + mult lanes)
# ============================================================================
ALPHA_TOG     = 0.50     # fraction of state flops toggling per active round (random cipher data)
# Parallel GHASH FSM state (ghash_fsm.v): 128 (Y accumulator) + 128 (H held) + 8 (block ctr):
N_Y = 128 ; N_H = 128 ; N_BLKCTR = 8
N_FLOP_PAR    = N_Y + N_H + N_BLKCTR                 # = 264 flops  (mult lane: ~256 = Y+H)  PRIMARY
# Bit-serial adds a shift register V, the X-shift/partial, a step counter (mult lane: ~512):
N_FLOP_SER    = 512                                  # [EST] 128 Y + 128 H + 128 V + 128 X-shift + ctr
N_FLOP_SHA    = 774      # SHA-256 held state, for contrast
N_FLOP_AES    = 260      # AES-128 held state (on-the-fly key), for contrast

# ============================================================================
# 4. COMPOSE per-block active energy  (PRIMARY = Karatsuba parallel)
# ============================================================================
def comb_energy(ncells, area):
    return ncells * e_per_cell, area * e_per_area

def block_active(form):
    """E_active per 128b block for a parallel form (fJ): mult+XOR (agent) + one capture."""
    e_comb = GFMUL[form]["e_block"]
    e_cap  = N_FLOP_PAR * (E_CLK + ALPHA_TOG * E_REGTOG)      # capture all state once
    return e_comb, e_cap, e_comb + e_cap

E_comb_P, E_cap_P, E_block_par = block_active(PRIMARY)
if E_BLOCK_OVERRIDE is not None:
    E_block_par = E_BLOCK_OVERRIDE + E_cap_P
E_comb_S, E_cap_S, E_block_school = block_active("schoolbook")

# bit-serial: tiny per-step logic, but the 256b V+Z register clocked every one of 128 steps
E_comb_step  = GFMUL["bitserial"]["e_mult"] / 128.0          # ~ one step's combinational energy
N_CLK_STEP   = 256                                           # V + Z/X-shift clocked each step
E_cap_step   = N_CLK_STEP * (E_CLK + ALPHA_TOG * E_REGTOG)
E_active_step = E_comb_step + E_cap_step
E_block_ser  = 128 * E_active_step
E_IDLE_CYC_SER = N_FLOP_SER * E_CLK

# clock floor the self-timed form SHEDS: every held flop clocked every idle cycle
E_IDLE_CYC   = N_FLOP_PAR * E_CLK                            # fJ/idle-cycle (parallel, PRIMARY)
T_ROUND      = GFMUL[PRIMARY]["t"]                           # ns, primary round critical path
F_BLOCK = 1.0 / (T_ROUND * 1e-9)                            # Hz, back-to-back block rate

# MACsec framing (802.1AE)
BYTES_FRAME   = 1500
N_BLK_FRAME   = (BYTES_FRAME + 15) // 16                     # 128b blocks / frame (~94)
LINE_RATE_GBPS = 10.0

def duty_to_idle_cycles(d):
    return (1 - d) / d

def energy_per_block(d, e_det_fJ=0.0, gate_residual=1.0):
    idle = duty_to_idle_cycles(d)
    return E_block_par + idle * E_IDLE_CYC * gate_residual, E_block_par + e_det_fJ

def power(d, e_det_fJ=0.0, gate_residual=1.0):
    p_clk = F_BLOCK * (E_block_par * d + E_IDLE_CYC * gate_residual * (1 - d)) * 1e-15
    p_st  = F_BLOCK * ((E_block_par + e_det_fJ) * d) * 1e-15
    return p_clk, p_st

def banner(s):
    print("\n" + "=" * 78 + "\n" + s + "\n" + "=" * 78)


if __name__ == "__main__":
    fa = E_IDLE_CYC / E_block_par                            # floor/active, PRIMARY (Karatsuba)
    fa_school = E_IDLE_CYC / E_block_school
    banner("GHASH (GF(2^128) carry-less MAC) as a self-timed static-CMOS FSM -- ENERGY-vs-DUTY")
    print("SG13G2 130nm / PSP103 / 1.2V. Figures tagged [MEAS]/[COMPOSED]/[EST].")
    print("THIRD design-space point after SHA-256 + AES-128; completes MACsec GCM-AES-128.")
    print("Multiplier cells/energy = the MULTIPLIER-COST AGENT feed (GFMUL_ANALYSIS.md),")
    print("each form iverilog 310/310 vs the GHASH ref (NIST + pycryptodome). PRIMARY = KARATSUBA.")

    banner("A. PER-BLOCK ACTIVE ENERGY (same clocked & self-timed) -- the three GF(2^128) forms")
    print("per-cell energy [MEAS/COMPOSED] %.3f fJ/cell (= %.0f fJ / %d cells, sha_slice anchor)"
          % (e_per_cell, E_SHA_SLICE, N_SHA_SLICE_S))
    print("%-26s %8s %7s %9s %12s %12s" %
          ("GF(2^128) form", "cells", "depth", "path ns", "E_mult pJ", "E_block pJ"))
    for f in ("bitserial", "schoolbook", "karatsuba"):
        g = GFMUL[f]
        tag = "  <- PRIMARY" if f == PRIMARY else ("  (upper bound)" if f=="schoolbook" else "  (x128 cyc)")
        print("%-26s %8d %7d %9.3f %12.1f %12.1f%s"
              % (f, g["cells"], g["depth"], g["t"], g["e_mult"]/1e3, g["e_block"]/1e3, tag))
    print("   Karatsuba = 2.33x fewer cells / 2.33x less energy than schoolbook (AND count 10x")
    print("   down: 1636 vs 16384 nand2) at 1.46x the depth. The GF multiply is 99%+ of GHASH's")
    print("   combinational energy (the 128b Y^C XOR = %.1f fJ = 0.9%%): the multiply IS GHASH,"
          % (GFMUL["karatsuba"]["e_block"] - GFMUL["karatsuba"]["e_mult"]))
    print("   as the S-box was AES and the adder was SHA.")
    print("-" * 74)
    print("E_comb_block   [COMPOSED] %8.0f fJ  (Karatsuba (Y^C).H, mult-agent)" % E_comb_P)
    print("E_cap_block    [EST]      %8.0f fJ  (%d flops x (%.1f + %.2f*%.0f) fJ, alpha=%.2f)"
          % (E_cap_P, N_FLOP_PAR, E_CLK, ALPHA_TOG, E_REGTOG, ALPHA_TOG))
    print("                          state = 128 (Y) + 128 (H held) + 8 (block ctr) = %d flops"
          % N_FLOP_PAR)
    print("                          [EST]  (register-LIGHT: mult lane ~256 Y+H, like AES not SHA)")
    print("-" * 74)
    print("E_active_block [COMPOSED] %8.0f fJ/block = %.3f nJ / 128b block  (DUTY-FLAT, Karatsuba)"
          % (E_block_par, E_block_par/1e6))
    print("   logic %.0f%%, registers %.0f%%  (schoolbook: %.3f nJ, logic %.0f%%)."
          % (100*E_comb_P/E_block_par, 100*E_cap_P/E_block_par,
             E_block_school/1e6, 100*E_comb_S/E_block_school))
    print("   GHASH is the MOST logic-heavy of the three (one GF multiply dwarfs its 264-flop file).")
    print("round critical path [COMPOSED/STA] %.3f ns (depth %d) -> block rate ~%.0f MHz"
          % (T_ROUND, GFMUL[PRIMARY]["depth"], F_BLOCK/1e6))
    print("   (schoolbook %.3f ns depth %d = shallower than AES 2.12 ns; Karatsuba is DEEPER --"
          % (GFMUL["schoolbook"]["t"], GFMUL["schoolbook"]["depth"]))
    print("    recursion adds XOR layers. The done virtue is REGULARITY, not shallowness: see D.)")

    banner("A'. BIT-SERIAL form -- register-ACTIVITY heavy (depth-2/0.126ns per cycle, x128)")
    print("per-step logic %.0f fJ (259 cells, depth 2) + capture %.0f fJ = %.0f fJ/step, x128 ="
          % (E_comb_step, E_cap_step, E_active_step))
    print("   %.3f nJ/block = %.1fx the Karatsuba parallel (%.3f nJ) -- pays 128x register toggling."
          % (E_block_ser/1e6, E_block_ser/E_block_par, E_block_par/1e6))
    print("   Bit-serial total COMBINATIONAL energy ~= parallel (same GF algebra, time- vs space-")
    print("   unfolded; mult lane: 122.1 vs 121.5 pJ), but its 256b V+Z clocked x128 dominates.")
    print("   -> bit-serial = the AREA-limited choice; its gift is the depth-2 per-cycle settle")
    print("      (the absolute sharpest done). Energy analysis below uses the PARALLEL form.")

    banner("B. CLOCK FLOOR the self-timed form SHEDS  [MEAS coefficient] -- 3-cipher contrast")
    print("E_idle_cycle = %d flops x %.1f fJ(E_clk) = %.2f pJ / idle cycle  [MEAS/EST]"
          % (N_FLOP_PAR, E_CLK, E_IDLE_CYC/1e3))
    print("floor / active-block = %.2f / %.1f = %.3f  (Karatsuba);  %.3f (schoolbook)"
          % (E_IDLE_CYC/1e3, E_block_par/1e3, fa, fa_school))
    print("   3-CIPHER CONTRAST (floor/active):")
    print("     SHA  0.475  (774 flops, register-heavy)      -> BIGGEST clock-floor win")
    print("     AES  0.154  (260 flops, logic-heavy)         -> smaller win, sharp done")
    print("     GHASH %.3f (264 flops, MOST logic-heavy)     -> SMALLEST win (Karatsuba %.3f)"
          % (fa_school, fa))
    print("   GHASH is the most logic-heavy of the three -> the lowest floor/active -> the LEAST")
    print("   clock-floor to shed. Karatsuba (less logic) lifts it toward AES-class; schoolbook")
    print("   is the smallest. GHASH's self-timed value is the SHARP/REGULAR done (D), not the floor.")

    banner("C. ENERGY & POWER vs DUTY  (clocked-golden free-running vs self-timed) -- Karatsuba")
    print("duty d = active-block fraction. WITHIN a frame d~1 (back-to-back blocks) -> NO win;")
    print("the win is BETWEEN frames (idle). MACsec/802.1AE idles between Ethernet frames.")
    print("%-9s %14s %14s %8s %11s %11s %8s" %
          ("duty", "E_clk pJ/blk", "E_st pJ/blk", "E ratio", "P_clk mW", "P_st mW", "P ratio"))
    for d in (1.0, 0.5, 0.1, 0.01, 0.001):
        ec, es = energy_per_block(d)
        pc, ps = power(d)
        print("%-9s %14.1f %14.1f %7.3fx %11.3f %11.4f %7.2fx"
              % (("%.3g" % d), ec/1e3, es/1e3, ec/es, pc*1e3, ps*1e3, pc/ps))
    print("clocked power never falls below P_floor = %.3f mW (clock keeps toggling %d flops);"
          % (F_BLOCK * E_IDLE_CYC * 1e-15 * 1e3, N_FLOP_PAR))
    print("self-timed -> leakage as d->0. Parity at d=1; self-timed wins for all d<1, by a margin")
    print("set by floor/active (%.3f): AES-class, smaller than SHA, bigger than schoolbook-GHASH." % fa)

    banner("C'. MACsec ROLL-UP: per-frame / per-second (Karatsuba, %d-byte frame, %gGbE)"
           % (BYTES_FRAME, LINE_RATE_GBPS))
    blk_per_s_line = LINE_RATE_GBPS * 1e9 / 128.0
    e_frame = N_BLK_FRAME * E_block_par
    print("%d blocks/frame; line-rate %g Gb/s = %.2e blocks/s. E_active/frame = %.1f pJ."
          % (N_BLK_FRAME, LINE_RATE_GBPS, blk_per_s_line, e_frame/1e3))
    for d, lbl in ((1.0, "line-rate sustained"), (0.1, "bursty frames"), (0.01, "sparse/event")):
        p_clk = blk_per_s_line * (E_block_par * d + E_IDLE_CYC * (1-d)) * 1e-15 * 1e3
        p_st  = blk_per_s_line * (E_block_par * d) * 1e-15 * 1e3
        print("   duty %-5g (%-20s): P_clk %7.3f mW  P_st %7.4f mW  %5.2fx"
              % (d, lbl, p_clk, p_st, p_clk/p_st))

    banner("D. CHARGE THE COMPLETION-DETECTOR FLOOR  [EST]  (is current-sense BEST for GHASH?)")
    print("Self-timed pays a 'done' every active block, recovered by the shed idle clock.")
    print("Break-even: E_det < E_idle_cycle * (1-d)/d = %.0f*(1-d)/d fJ/block." % E_IDLE_CYC)
    print("Is current-sense / power-settle done the BEST FIT for GHASH? YES -- the SHARPEST of the")
    print("three, because the carry-LESS round is REGULAR + DATA-INDEPENDENT in SHAPE: every output")
    print("bit is a BALANCED XOR reduction of AND partial products -- no carry chain, no S-box LUT.")
    print("The critical-path STRUCTURE is fixed (only the toggled values change) -> an in-kind")
    print("replica delay matches a FIXED balanced cone, and the supply current collapses on a clean")
    print("MONOTONE edge. SHA's deep DATA-DEPENDENT carry ripple blurred that edge; AES's S-box was")
    print("shallow+sharp; GHASH's carry-less tree is shallow(schoolbook)/regular(Karatsuba)-and-")
    print("MONOTONE -> the best 'trip on outputs-GOOD' target in the campaign (async_impl_v2_cscd).")
    print("%-40s %10s %9s %12s" % ("detector [EST]", "E_det fJ", "d*", "penalty@d=1"))
    dets = [("embedded/sparse tap", 50.0),
            ("current-sense done (lo)", E_CMP_DONE[0]),
            ("current-sense done (hi)", E_CMP_DONE[1]),
            ("in-kind replica line (%.2fns round)" % T_ROUND, T_ROUND * E_DLINE_RATE)]
    for nm, ed in dets:
        dstar = E_IDLE_CYC / (E_IDLE_CYC + ed)
        pen = ed / E_block_par
        print("%-40s %10.0f %8.4f %11.3f%%" % (nm, ed, dstar, 100*pen))
    print("** Penalty@d=1 is NEGLIGIBLE (<=%.2f%%: the block compute is huge). But the clock FLOOR"
          % (100*E_CMP_DONE[1]/E_block_par))
    print("   is only %.1f pJ, so a 400 fJ done is %.1f%% of it (AES 5.5%%, SHA 1.8%%) -> crossover"
          % (E_IDLE_CYC/1e3, 100*E_CMP_DONE[1]/E_IDLE_CYC))
    print("   d* ~%.2f. GHASH has the LEAST floor to hide a done behind -> keep it in-kind/current-"
          % (E_IDLE_CYC/(E_IDLE_CYC+E_CMP_DONE[1])))
    print("   sense + sharp, which its regular carry-less round (or depth-2 bit-serial step) affords.")

    banner("E. HONESTY: vs a CLOCK-GATED CMOS opponent  [EST sensitivity] -- Karatsuba")
    print("A clock-gated CMOS core recovers most of the idle floor too; residual r = idle-clock")
    print("NOT gated (clock-tree root + ICG + leaf). Energy ratio = 1 + r*%.3f*(1-d)/d." % fa)
    print("%-10s %12s %12s %12s" % ("duty", "r=1 (none)", "r=0.3", "r=0.1 (good)"))
    for d in (0.5, 0.1, 0.01):
        row = [1 + r * fa * (1-d)/d for r in (1.0, 0.3, 0.1)]
        print("%-10s %11.3fx %11.3fx %11.3fx" % (("%.3g" % d), *row))
    g01 = 1+0.1*fa*0.9/0.1 ; g001 = 1+0.1*fa*0.99/0.01
    print("vs GOOD gating (r=0.1) GHASH-Karatsuba wins ~%.2fx (d=0.1) / ~%.2fx (d=0.01) -- AES-class"
          % (g01, g001))
    print("   (AES 1.14x/2.5x, SHA 1.43x/5.70x); schoolbook-GHASH would be the smallest. For GHASH")
    print("   the surviving self-timed wins are (a) the un-gatable clock residue, (b) zero gating")
    print("   latency, and (c) the crisp current-sense/GALS handshake its REGULAR carry-less round")
    print("   makes the sharpest of the three -- for GHASH this is a GALS/completion story first.")

    banner("BOTTOM LINE  --  GHASH, and the completed GCM-AES picture")
    print("Self-timed static-CMOS GHASH LOWERS POWER only in the IDLE/INTERMITTENT regime (bursty")
    print("MACsec frames), ~parity at line rate. The duty win is AES-class with the realistic")
    print("Karatsuba multiplier (~%.2fx d=0.1 / ~%.2fx d=0.01 vs good gating), the SMALLEST of the"
          % (g01, g001))
    print("three with schoolbook. GHASH is register-LIGHT (%d flops, like AES %d not SHA %d) AND the"
          % (N_FLOP_PAR, N_FLOP_AES, N_FLOP_SHA))
    print("most logic-heavy (GF mult = 99%% of combinational) -> floor/active %.3f = lowest of three." % fa)
    print("BUT its carry-LESS round is the most REGULAR + DATA-INDEPENDENT settle -> the current-")
    print("sense/power-settle DONE is the SHARPEST of the three: GHASH is the best CURRENT-SENSE-")
    print("DONE / GALS vehicle, the weakest clock-floor-shed vehicle. (Bit-serial gives a depth-2")
    print("per-cycle settle -- the absolute sharpest done -- at 128 cyc + ~%.1fx energy.)" % (E_block_ser/E_block_par))
    print("3-CIPHER ARC: SHA (register-heavy -> clock-floor landslide, blurred data-dependent done)")
    print("  -> AES (logic-heavy -> small floor win, sharp S-box done) -> GHASH (extreme logic -> no")
    print("  floor win, SHARPEST regular carry-less done). Register-weight predicts the floor win;")
    print("  round REGULARITY predicts the done. GHASH sits at the far logic/regular corner.")
    e_aes_block_lut  = 0.475e6                                # AES-128 encrypt, LUT S-box (../aes_fsm headline)
    e_aes_block_comp = 154.7e3                                # AES-128 encrypt, composite S-box (low-power)
    for lbl, e_aes in (("LUT S-box", e_aes_block_lut), ("composite S-box", e_aes_block_comp)):
        e_gcm = e_aes + E_block_par
        print("GCM-AES-128/block [%s]: AES %.3f nJ + GHASH %.3f nJ = %.3f nJ (GHASH +%.0f%%, %.0f%% of total)."
              % (lbl, e_aes/1e6, E_block_par/1e6, e_gcm/1e6,
                 100*E_block_par/e_aes, 100*E_block_par/e_gcm))
    print("Combined held state ~%d flops (AES %d + GHASH %d) -> combined idle floor ~%.1f pJ/cyc."
          % (N_FLOP_AES+N_FLOP_PAR, N_FLOP_AES, N_FLOP_PAR, (N_FLOP_AES+N_FLOP_PAR)*E_CLK/1e3))
    print("GCM-AES is a GALS/intermittent-power primitive: parity at line rate, a modest-but-real")
    print("idle win vs good gating, and -- uniquely in the GHASH half -- the sharpest current-sense")
    print("completion the campaign has seen, the natural handshake anchor for a self-timed MACsec datapath.")
