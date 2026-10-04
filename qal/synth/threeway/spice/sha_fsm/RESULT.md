# SHA-256 as a self-timed static-CMOS FSM — RESULT (2026-10-02)

"Try the self-timed FSM approach on SHA-256." DONE. Two findings, both honest.

## 1. FUNCTIONAL — the approach SCALES to a real crypto round (PROVEN)
The self-timed SHA-256 round FSM (sha256_round.v = pure static combinational
next-state: Sigma0/Sigma1/Maj/Ch/T1/T2/shift; sha256_fsm.v = 8x32b a..h DFF state
+ rolling W schedule + K ROM + 64 rounds + H-add) computes SHA-256 CORRECTLY:
  abc   -> ba7816bf...f20015ad  PASS
  empty -> e3b0c442...7852b855  PASS
vs python hashlib (independent; re-verified 3x: both verifiers + orchestrator
re-compiled iverilog and re-derived via hashlib; +'a'*64 2-block and 'quick brown
fox' also match). Exact FIPS 180-4. The self-timed build is bit-identical in LOGIC
(same round cone + same edge-triggered dfrbp DFF), differing only in WHEN capture
fires (in-kind replica carry-chain DONE pulse, not a comparator) -> correctness
transfers from the synchronous proof.

## 2. ENERGY vs DUTY — lower power in the IDLE/INTERMITTENT regime
Authoritative composition = compose_sha256.py / SHA256_COMPOSE.md (yosys cell
counts: round_dp 1328 cells, msgsched 557; per-cell 3.683 fJ from the MEASURED
232 fJ sha_slice; E_clk 28.2 fJ/DFF/cyc + E_regtoggle 45 fJ add8 anchors). The
other set (compose_energy.py, rtl agent) is INTERNALLY INCONSISTENT -> SUPERSEDED.
  E_active_hash = 2.94 nJ/512b block, DUTY-FLAT for self-timed. Register capture
  DOMINATES (~85%): 774 held flops (256 a..h + 512 W-window + ctr; +256 saved-H
  omitted => true floor slightly LARGER).
  duty   E_clk/hash  E_st/hash   ratio (vs FREE-running clock)
  1        2.94 nJ    2.94 nJ    1.00x  (parity; self-timed loses only <1% detector)
  0.5      4.34       2.94       1.48x
  0.1     15.51       2.94       5.28x
  0.01   141.2        2.94      48x
  vs GOOD CLOCK-GATING (the FAIR opponent): ~1.4x (d=0.5) / ~5.7x (deep idle).
★ SHA is a BETTER self-timed fit than the 4-bit toy: register-heavy (floor/active
  0.475 vs 0.22) so the clock floor dominates, AND the deep round AMORTIZES the
  completion detector to <1% (it was 64% of the toy's op). The two things that
  limited the toy both improve at SHA scale.
HONEST SCOPE: WITHIN a hash duty~1 (every round active) -> NO win; continuous
miner/streaming = parity. The win is BETWEEN hashes/blocks (idle). Target =
bursty/event-driven hashing (wake, hash, sleep).
PROVISIONAL: absolute pJ is COMPOSED from measured anchors (full-SHA SPICE
infeasible). Ratio/shape/crossover are scaling-robust. To pin the absolute per-
round-core energy: run gen_sha_round.py's sr_{g,st}_d{2,4,10}.cir in Xyce (one at
a time, detached; dfrbp-heavy ~600-900s/deck) and set compose E_RC_8B_FJ = EVDD/nops.
