#!/usr/bin/env python3
"""Energy-vs-duty COMPOSITION for AES-128 as a self-timed static-CMOS FSM.

Companion to ../sha_fsm/compose_sha256.py, SAME method, AES-128 target (the next
self-timed-FSM target after SHA-256). Composes per-round and whole-encrypt energy
of a round-iterative AES-128 core from MEASURED transistor anchors, and prints the
clocked-golden vs self-timed ledger across duty. The approach under test (MEASURED
on a 4-bit accumulator ../fsm/FSM_NUMBERS.txt, then on SHA-256): a self-timed
static-CMOS FSM = precharge-free static next-state logic + edge-triggered DFF state
register + a done-pulsed capture (in-kind replica delay) -- NOT domino. It holds
state and dissipates only on transitions, so it sheds the CLOCK FLOOR at low duty
-> a DUTY-SHAPED lower-power win; per-op it is ~parity with clocked CMOS.

USER DIRECTIVE 2026-10-02: "Parity is fine, stat-sim modeling is preferable to
SPICE." -> NO Xyce here. Energy is composed from measured anchors (yosys cell counts
x the measured sha_slice per-cell energy 3.683 fJ + the add8 clock/register
coefficients). Parity per-op is an acceptable result; the deliverable is the
duty-shaped win + the functional scaling proof.

PROVENANCE TAGS on every figure:
  [MEAS]     measured on SG13G2/PSP103 transistors (Xyce), this campaign
  [COMPOSED] derived this session: yosys synth (same recipe as the sha_slice anchor)
             + OpenSTA, scaled by the [MEAS] sha_slice per-cell energy
  [EST]      honest structural estimate (flop count, activity factor, detector cost)

AES-128 round-iterative structure (the genuine FIPS-197 cipher): 10 rounds over a
128 b state register. Round = SubBytes (16 parallel 8 b S-boxes) + ShiftRows (pure
wiring, free) + MixColumns (GF(2^8) xtime/x3 + XORs per column) + AddRoundKey (128 b
XOR); round 10 OMITS MixColumns. On-the-fly key expansion (RotWord/SubWord/Rcon)
produces one 128 b round key per round. The AES S-box, MixColumns and the full
encrypt were verified against the FIPS-197 vector
  key 000102..0f  pt 00112233..ff -> ct 69c4e0d86a7b0430d8cdb78070b4c55a
(cross-checked vs pycryptodome AND openssl enc -aes-128-ecb -nopad -- NOT self-
asserted) before the round was synthesized for cell counts.

Run:  python3 compose_aes128.py          (no SPICE launched here)
"""

# ============================================================================
# 1. MEASURED ANCHORS  [MEAS]  (shared with the SHA-256 composition)
# ============================================================================
E_SHA_SLICE   = 232.0    # fJ/op, static-CMOS 8b round core {maj,ch,add} @ alpha=0.476 [MEAS]
A_SHA_SLICE_S = 644.11   # um^2, sha_slice re-synth (my recipe) -> calibration basis   [COMPOSED]
N_SHA_SLICE_S = 63       # cells, sha_slice re-synth (my recipe) -> calibration basis   [COMPOSED]
E_CLK         = 28.2     # fJ/DFF/cycle  (clock-pin+internal, idle)                     [MEAS add8]
E_REGTOG      = 45.0     # fJ/DFF/toggle (Q switches + its load)                        [MEAS add8]
E_CMP_DONE    = (144.0, 400.0)   # fJ, per-op analog / current-sense completion done    [MEAS/EST]
E_DLINE_RATE  = 500.0 / 1.968    # = 254 fJ/ns of in-kind replica delay line            [MEAS add8]

# ============================================================================
# 2. SYNTHESIZED STRUCTURE  [COMPOSED]  (yosys 0.58, same recipe as the anchor; this session)
#    recipe: read_verilog; synth -flatten; abc -liberty sg13g2_typ_1p20V_25C; opt_clean; stat
#    AES round/sbox/keyexp Verilog was GF-derived and FIPS-197-verified before synth.
# ============================================================================
N_SBOX   = 410      ; A_SBOX   = 4108.78  ; T_SBOX   = 1.076   # one SubBytes S-box
N_ROUND  = 7555     ; A_ROUND  = 75867.36 ; T_ROUND  = 2.124   # full round (16 S-box+Mix+ARK)
N_MIX    = 460      ; A_MIX    = 6676.99                       # MixColumns alone (4 cols)
N_ARK    = 128      ; A_ARK    = 1857.95                       # AddRoundKey alone (128b XOR)
N_KEYEXP = 1856     ; A_KEYEXP = 18287.04 ; T_KEYEXP = 1.586   # one on-the-fly key-exp step

# OPTIONAL hook: if the S-box cost agent lands a MEASURED per-S-box transistor energy
# (fJ/op), set it here to replace the composed per-S-box number for the SubBytes bulk.
E_SBOX_MEAS = None   # fJ/op/S-box  [MEAS] <- substitute the S-box agent's figure if available

# ============================================================================
# 3. STRUCTURAL ESTIMATES  [EST]
# ============================================================================
N_ROUNDS      = 10          # AES-128: 10 rounds
ALPHA_TOG     = 0.50        # fraction of state flops toggling per active round (random data)
# State held by the round-iterative FSM:
N_DP          = 128         # 128b datapath state register
N_RK_ONFLY    = 128         # 128b CURRENT round key (on-the-fly key schedule)   <- PRIMARY
N_RK_PRESTORE = 11 * 128    # all 11 round keys prestored = 1408b                <- ALT
N_CTR         = 4           # round counter 0..10
N_FLOP        = N_DP + N_RK_ONFLY + N_CTR            # on-the-fly = 260 flops (PRIMARY)
N_FLOP_PRE    = N_DP + N_RK_PRESTORE + N_CTR         # prestored  = 1540 flops (ALT)
N_FLOP_SHA    = 774         # SHA-256 held state, for contrast

# --- per-cell / per-area energy from the MEASURED sha_slice, SAME-recipe basis ---
e_per_cell = E_SHA_SLICE / N_SHA_SLICE_S          # = 3.683 fJ/cell/op (recipe-consistent)
e_per_area = E_SHA_SLICE / A_SHA_SLICE_S          # = 0.360 fJ/um^2/op

def comb_energy(ncells, area):
    """Composed combinational energy (fJ/op): bracket = [cell-scaled, area-scaled]."""
    return ncells * e_per_cell, area * e_per_area

def mid(ncells, area):
    c, a = comb_energy(ncells, area)
    return (c + a) / 2

# ============================================================================
# 4. COMPOSE per-round and per-encrypt active energy
# ============================================================================
# per-S-box: composed, unless the S-box cost agent supplied a measured figure
E_SBOX_cell, E_SBOX_area = comb_energy(N_SBOX, A_SBOX)
E_SBOX = E_SBOX_MEAS if E_SBOX_MEAS is not None else (E_SBOX_cell + E_SBOX_area) / 2
E_SUBBYTES = 16 * E_SBOX                           # fJ, 16 S-boxes per round (the bulk)
E_MIX      = mid(N_MIX, A_MIX)                     # fJ, MixColumns
E_ARK      = mid(N_ARK, A_ARK)                     # fJ, AddRoundKey
E_comb_round = mid(N_ROUND, A_ROUND)               # fJ, full synthesized round (authoritative)
E_comb_key   = mid(N_KEYEXP, A_KEYEXP)             # fJ, one on-the-fly key-expansion step

E_cap_round  = N_FLOP * (E_CLK + ALPHA_TOG * E_REGTOG)        # fJ, capture all state once
E_active_round = E_comb_round + E_comb_key + E_cap_round      # fJ/round (datapath + key + capture)

# whole encrypt (one 128b block): 10 rounds (round 10 omits MixColumns) + 10 key steps.
# Representative-round model (matches the SHA script): E_encrypt = N_ROUNDS * E_active_round.
# Second-order: -E_MIX (final round) + initial AddRoundKey/load (~E_cap_round) roughly cancel.
E_encrypt = N_ROUNDS * E_active_round

# clock floor the self-timed form SHEDS: every held flop clocked every idle cycle
E_IDLE_CYC    = N_FLOP * E_CLK                     # fJ/idle-cycle (on-the-fly, PRIMARY)
E_IDLE_CYC_PRE= N_FLOP_PRE * E_CLK                 # fJ/idle-cycle (prestored ALT)

F_ROUND = 1.0 / (T_ROUND * 1e-9)                   # Hz, back-to-back round rate

def duty_to_idle_cycles(d):
    return N_ROUNDS * (1 - d) / d

def energy_per_encrypt(d, e_det_fJ=0.0, gate_residual=1.0):
    """(E_clocked, E_selftimed) in fJ/encrypt at duty d."""
    idle = duty_to_idle_cycles(d)
    e_clk = E_encrypt + idle * E_IDLE_CYC * gate_residual
    e_st  = E_encrypt + N_ROUNDS * e_det_fJ
    return e_clk, e_st

def power(d, e_det_fJ=0.0, gate_residual=1.0):
    p_clk = F_ROUND * (E_active_round * d + E_IDLE_CYC * gate_residual * (1 - d)) * 1e-15
    p_st  = F_ROUND * ((E_active_round + e_det_fJ) * d) * 1e-15
    return p_clk, p_st

def banner(s):
    print("\n" + "=" * 78 + "\n" + s + "\n" + "=" * 78)


if __name__ == "__main__":
    banner("AES-128 as a self-timed static-CMOS FSM  -  ENERGY-vs-DUTY COMPOSITION")
    print("SG13G2 130nm / PSP103 / 1.2V. Figures tagged [MEAS]/[COMPOSED]/[EST].")
    print("AES S-box/MixColumns/full-encrypt verified vs FIPS-197 (pycryptodome + openssl):")
    print("  69c4e0d86a7b0430d8cdb78070b4c55a  -- PASS (NOT self-asserted).")
    print("Next self-timed-FSM target after SHA-256; same composition method.")

    banner("A. PER-ROUND / PER-ENCRYPT ACTIVE ENERGY  (same for clocked & self-timed)")
    print("per-cell energy  [MEAS/COMPOSED] %.3f fJ/cell  (= %.0f fJ / %d cells, my-recipe)"
          % (e_per_cell, E_SHA_SLICE, N_SHA_SLICE_S))
    print("per-area energy  [MEAS/COMPOSED] %.4f fJ/um^2 (= %.0f fJ / %.1f um^2)"
          % (e_per_area, E_SHA_SLICE, A_SHA_SLICE_S))
    sbtag = "MEAS S-box agent" if E_SBOX_MEAS is not None else "COMPOSED"
    print("%-44s %10s %10s" % ("block [COMPOSED]", "cell-scaled", "area-scaled"))
    print("%-44s %9.0ffJ %9.0ffJ   (x%.1f area vs sha_slice)"
          % ("  one S-box (410 cells)", E_SBOX_cell, E_SBOX_area, A_SBOX/A_SHA_SLICE_S))
    print("%-44s %9.0ffJ            per-S-box used [%s] = %.0f fJ" %
          ("  -> SubBytes = 16 S-boxes", E_SUBBYTES, sbtag, E_SBOX))
    print("%-44s %9.0ffJ %9.0ffJ"
          % ("  MixColumns (460 cells)", *comb_energy(N_MIX, A_MIX)))
    print("%-44s %9.0ffJ %9.0ffJ"
          % ("  AddRoundKey (128 cells)", *comb_energy(N_ARK, A_ARK)))
    print("%-44s %9.0ffJ %9.0ffJ   (x%.1f area vs sha_slice)"
          % ("  full round (7555 cells)", *comb_energy(N_ROUND, A_ROUND), A_ROUND/A_SHA_SLICE_S))
    print("%-44s %9.0ffJ %9.0ffJ"
          % ("  on-the-fly key-exp step (1856 cells)", *comb_energy(N_KEYEXP, A_KEYEXP)))
    print("-" * 70)
    print("E_comb_round   [COMPOSED] %7.0f fJ  (full round, midpoint)" % E_comb_round)
    print("   ** SubBytes (16 S-boxes) = %.0f fJ = %.0f%% of the round logic -- the S-BOX"
          % (E_SUBBYTES, 100*E_SUBBYTES/E_comb_round))
    print("      is the AES round cost (vs SHA = adder/rotation). MixColumns %.0f fJ (%.0f%%),"
          % (E_MIX, 100*E_MIX/E_comb_round))
    print("      AddRoundKey %.0f fJ (%.0f%%): MixColumns is XOR-shallow, no big ripple-carry."
          % (E_ARK, 100*E_ARK/E_comb_round))
    print("E_comb_key     [COMPOSED] %7.0f fJ  (on-the-fly key schedule, per round)" % E_comb_key)
    print("E_cap_round    [EST]      %7.0f fJ  (%d flops x (%.1f + %.2f*%.0f) fJ, alpha_tog=%.2f)"
          % (E_cap_round, N_FLOP, E_CLK, ALPHA_TOG, E_REGTOG, ALPHA_TOG))
    print("                          state = 128 (datapath) + 128 (current round key) + 4 (ctr)")
    print("                          = %d flops [EST]  (on-the-fly key schedule = PRIMARY)" % N_FLOP)
    print("-" * 70)
    print("E_active_round [COMPOSED] %7.0f fJ/round   (logic %.0f%%, registers %.0f%%)"
          % (E_active_round,
             100*(E_comb_round+E_comb_key)/E_active_round,
             100*E_cap_round/E_active_round))
    print("E_active_encrypt [COMPOSED] %6.0f fJ = %.3f nJ / 128b block  (DUTY-FLAT)"
          % (E_encrypt, E_encrypt/1e6))
    print("   ** AES is LOGIC-heavy (S-box), the INVERSE of SHA (85% register). AES holds")
    print("      %d flops vs SHA's %d -> %.1fx fewer -> a SMALLER clock floor to shed, but"
          % (N_FLOP, N_FLOP_SHA, N_FLOP_SHA/N_FLOP))
    print("      the round is SHALLOWER (no big ripple) so the done is cheaper + sharper.")
    print("round critical path [COMPOSED/STA] %.3f ns -> round rate %.0f MHz"
          % (T_ROUND, F_ROUND/1e6))
    print("   (S-box path %.3f ns + MixColumns/ARK ~%.3f ns; vs SHA round 5.638 ns = %.1fx shallower)"
          % (T_SBOX, T_ROUND-T_SBOX, 5.638/T_ROUND))

    banner("B. CLOCK FLOOR the self-timed form SHEDS  [MEAS coefficient]")
    print("E_idle_cycle = %d flops x %.1f fJ(E_clk) = %.2f pJ / idle cycle  [MEAS/EST]"
          % (N_FLOP, E_CLK, E_IDLE_CYC/1e3))
    print("floor / active-round = %.2f / %.1f = %.3f"
          % (E_IDLE_CYC/1e3, E_active_round/1e3, E_IDLE_CYC/E_active_round))
    print("   SHA's was 0.475 (774 flops, register-heavy); accumulator ~0.22. AES's %.3f is"
          % (E_IDLE_CYC/E_active_round))
    print("   SMALLER -> the clock-floor-shed win is SMALLER than SHA's (less to delete).")
    print("ALT prestored-key form: %d flops -> E_idle_cycle %.2f pJ, floor/active %.3f"
          % (N_FLOP_PRE, E_IDLE_CYC_PRE/1e3,
             E_IDLE_CYC_PRE/(E_comb_round+E_comb_key+N_FLOP_PRE*(E_CLK+ALPHA_TOG*E_REGTOG))))
    print("   (prestoring all 11 keys restores a SHA-like floor but WASTES energy clocking")
    print("    1408 idle key flops -> worse absolute design; on-the-fly 260-flop is correct.)")

    banner("C. ENERGY & POWER vs DUTY   (clocked-golden free-running vs self-timed)")
    print("duty d = active-round fraction. WITHIN an encrypt d~1 (all 10 rounds active) -> NO")
    print("win; the win is BETWEEN frames (idle). MACsec/802.1AE GCM-AES idles between frames.")
    print("%-9s %14s %14s %8s %11s %11s %8s" %
          ("duty", "E_clk nJ/enc", "E_st nJ/enc", "E ratio", "P_clk mW", "P_st mW", "P ratio"))
    for d in (1.0, 0.5, 0.1, 0.01, 0.001):
        ec, es = energy_per_encrypt(d)
        pc, ps = power(d)
        print("%-9s %14.3f %14.3f %7.2fx %11.3f %11.4f %7.2fx"
              % (("%.3g" % d), ec/1e6, es/1e6, ec/es, pc*1e3, ps*1e3, pc/ps))
    print("clocked power never falls below P_floor = %.3f mW (clock keeps toggling %d flops);"
          % (F_ROUND * E_IDLE_CYC * 1e-15 * 1e3, N_FLOP))
    print("self-timed -> leakage as d->0. Crossover: parity at d=1, self-timed wins for all d<1.")
    print("vs SHA (d=0.1: 5.28x, d=0.01: 48x): AES's win is ~2x SMALLER -- its floor/active is")
    print("~3x smaller (260 vs 774 flops). Same SHAPE, smaller magnitude.")

    banner("D. CHARGE THE COMPLETION-DETECTOR FLOOR  [EST]  (the QAL guardrail)")
    print("Self-timed pays a 'done' every active round x10, recovered by the shed idle clock.")
    print("Break-even: E_det < E_idle_cycle * (1-d)/d = %.0f*(1-d)/d fJ/round." % E_IDLE_CYC)
    print("AES round is SHALLOW (%.2f ns, S-box-bounded, no deep ripple) -> the power-settle"
          % T_ROUND)
    print("current draw collapses CRISPLY -> current-sense completion is SHARPER/viable here")
    print("(ties back to async_impl_v2 'trip on outputs-GOOD'); SHA's deep 5.6ns ripple was not.")
    print("%-40s %10s %9s %12s" % ("detector [EST]", "E_det fJ", "d*", "penalty@d=1"))
    dets = [("embedded/sparse tap", 50.0),
            ("in-kind replica line (2.12ns round)", T_ROUND * E_DLINE_RATE),
            ("current-sense done (lo)", E_CMP_DONE[0]),
            ("current-sense done (hi)", E_CMP_DONE[1])]
    for nm, ed in dets:
        dstar = E_IDLE_CYC / (E_IDLE_CYC + ed)
        pen = N_ROUNDS * ed / E_encrypt
        print("%-40s %10.0f %8.4f %11.2f%%" % (nm, ed, dstar, 100*pen))
    print("** Viable, but with LESS headroom than SHA: AES's floor is %.1f pJ (vs SHA 21.8 pJ),"
          % (E_IDLE_CYC/1e3))
    print("   so a 400 fJ done is %.1f%% of the floor (SHA: 1.8%%) -> crossover d* ~%.2f (SHA ~0.98)."
          % (100*E_CMP_DONE[1]/E_IDLE_CYC, E_IDLE_CYC/(E_IDLE_CYC+E_CMP_DONE[1])))
    print("   Keep the done in-kind/current-sense and <=~400 fJ; it still wins below ~95% duty.")

    banner("E. HONESTY: vs a CLOCK-GATED CMOS opponent  [EST sensitivity]")
    print("A clock-gated CMOS core recovers most of the idle floor too; residual r = idle-clock")
    print("NOT gated (clock-tree root + ICG + leaf). Energy ratio = 1 + r*%.3f*(1-d)/d."
          % (E_IDLE_CYC/E_active_round))
    print("%-10s %12s %12s %12s" % ("duty", "r=1 (none)", "r=0.3", "r=0.1 (good)"))
    for d in (0.5, 0.1, 0.01):
        row = [1 + r * (E_IDLE_CYC/E_active_round) * (1-d)/d for r in (1.0, 0.3, 0.1)]
        print("%-10s %11.2fx %11.2fx %11.2fx" % (("%.3g" % d), *row))
    print("vs GOOD gating (r=0.1) AES self-timed wins only ~1.14x (d=0.1) / ~2.5x (d=0.01) --")
    print("SMALLER than SHA (1.43x / 5.70x). The surviving AES advantages are the un-gatable")
    print("clock residue, zero gating-logic latency, and a clean GALS/current-sense handshake")
    print("that the SHALLOW S-box round makes crisp -- more a GALS story than a raw-power landslide.")

    banner("BOTTOM LINE")
    r01 = energy_per_encrypt(0.1)[0]/energy_per_encrypt(0.1)[1]
    r001 = energy_per_encrypt(0.01)[0]/energy_per_encrypt(0.01)[1]
    g01 = 1+0.1*(E_IDLE_CYC/E_active_round)*(1-0.1)/0.1
    g001 = 1+0.1*(E_IDLE_CYC/E_active_round)*(1-0.01)/0.01
    print("Self-timed static-CMOS AES-128 LOWERS POWER in the IDLE/INTERMITTENT regime (bursty")
    print("MACsec frames, event-driven), ~parity at d=1 (bulk/sustained MACsec). Win vs a free")
    print("clock: ~%.1fx energy/encrypt at d=0.1, ~%.0fx at d=0.01; vs GOOD gating ~%.1fx / ~%.1fx."
          % (r01, r001, g01, g001))
    print("vs SHA-256: the duty win is SMALLER (AES holds %d flops not %d -> floor/active %.2f"
          % (N_FLOP, N_FLOP_SHA, E_IDLE_CYC/E_active_round))
    print("vs 0.48), because AES is LOGIC-heavy (S-box ~87% of the round), not register-heavy.")
    print("BUT the SHALLOW round (%.1fx faster than SHA's) makes the current-sense done SHARPER"
          % (5.638/T_ROUND))
    print("and viable -- the detector just has less floor to hide behind, so keep it <=400 fJ.")
    print("On-the-fly key schedule (260 flops) is the right self-timed AES; prestoring 11 keys")
    print("would fake a SHA-like floor by wasting clock on 1408 idle key flops.")
