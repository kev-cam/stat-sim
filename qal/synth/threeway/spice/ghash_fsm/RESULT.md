# GHASH as a self-timed static-CMOS FSM — RESULT (2026-10-02)

Completes the Ethernet MACsec primitive: AES-128 + GHASH = GCM-AES-128. Third self-
timed-FSM target. Stat-sim modeled (NO Xyce, per directive).

## 1. FUNCTIONAL — scales; NIST-tied (PROVEN)
Self-timed GHASH FSM (ghash_gfmul.v GF(2^128) carry-less mult mod x^128+x^7+x^2+x+1
in GCM bit-reflected convention; ghash_round.v Y'=(Y^C).H; ghash_fsm.v 128b accumulator
+ held H + ctr edge-DFF, absorb N blocks) computes CORRECT GHASH:
  GCM Test Case 4: S = 698e57f70e6ecc7fd9463b7260a9ae5f, derived tag =
  5bc94fbc3221a5db94fae95ae7121a47 == NIST SP800-38D TC4 == pycryptodome.
Python ref validated vs pycryptodome on H=AES_0(0)=66e94bd4.., empty tag 58e2fcce..,
TC3/TC4, 200+ random vectors (independently re-verified; distinct code path). The GCM
BIT-REFLECTION (#1 bug) is correct. Self-timed build bit-identical in logic (same
carry-less cone + DFF), differs only in capture timing -> correctness transfers.

## 2. ENERGY vs DUTY + the 3-CIPHER ARC
Stat-sim composition (compose_ghash.py; yosys cells x measured 3.683 fJ/cell). GHASH =
one GF(2^128) multiply (99% of combinational energy). Multiplier characterized 3 ways
(all 310/310 correct vs NIST ref):
  bit-serial  259 cells/step, depth 2, x128 cyc  -> 1.783 nJ/blk (27x, register-active)
  schoolbook  32999 cells, depth 13              -> 0.135 nJ/blk
  Karatsuba   14137 cells, depth 19  [PRIMARY]   -> 0.066 nJ/blk
Duty (Karatsuba) vs good clock-gating: ~1.10x@d.1 / ~2.12x@d.01 (AES-class).

★★ THE 3-CIPHER ARC (register-weight predicts the clock-floor win; round REGULARITY
   predicts the current-sense done):
     floor/active   clock-floor win (vs good gating)   current-sense DONE
  SHA  0.475 (774 flop, register-heavy)  BIGGEST 1.43/5.70x   blurred (deep carry ripple)
  AES  0.154 (260 flop, logic-heavy)     small  1.14/2.5x     sharp (shallow round)
  GHASH 0.113 (264 flop, MOST logic)     SMALLEST 1.10/2.12x  SHARPEST (carry-less, regular)
  GHASH sits at the far logic/regular corner: worst clock-floor vehicle, best current-
  sense-DONE / GALS vehicle. (bit-serial = depth-2/cycle = absolute sharpest settle,
  at 128 cyc + 27x energy.)

## 3. COMBINED GCM-AES-128 (the full Ethernet MACsec primitive)
Per 128b block [LUT S-box]: AES 0.475 nJ + GHASH 0.066 nJ = 0.541 nJ (GHASH +14%,
~12% of total). Both register-light, both parity-at-line-rate, both win in the bursty/
idle frame regime (~1.1-2.5x vs good gating). The full MACsec datapath is a self-timed-
FSM-viable, current-sense-completion-friendly design — AES carries the energy, GHASH
is the cheap authentication tail and the sharpest completion signal.

## HONEST CAVEATS (verifier-flagged)
- "Sharpest done" is a STATIC-STRUCTURE argument (balanced carry-less XOR tree, data-
  independent settle), NOT transistor-simulated (directive = no Xyce). The sharp-settle
  virtue (bit-serial/depth-2) and the energy-primary form (Karatsuba) are DIFFERENT
  design points -- don't sell them as one win.
- 3.683 fJ/cell anchor (measured on shallow sha_slice adder/logic, alpha 0.48)
  transplanted onto deep (13-19 level) XOR reduction trees UNDERSTATES energy (deep XOR
  trees glitch more). Absolute pJ provisional; ratio/shape/3-cipher ordering robust.
- Scope (as SHA/AES): within-frame duty~1 = parity (line-rate MACsec, fine per
  directive); win is between frames (bursty/event-driven).
