# AES-128 as a self-timed static-CMOS FSM — RESULT (2026-10-02)

Next self-timed-FSM target after SHA-256. Stat-sim modeled (NO Xyce, per directive).

## 1. FUNCTIONAL — the approach SCALES to AES-128 (PROVEN)
Self-timed AES-128 round FSM (aes_round.v static SubBytes/ShiftRows/MixColumns/
AddRoundKey, final-round MixColumns bypass; aes_key_expand.v on-the-fly round keys;
aes128_fsm.v = 128b state + 128b running key + ctr in edge-triggered DFFs, 10 rounds)
computes CORRECT AES-128:
  key 000102..0f, pt 00112233..ff -> 69c4e0d86a7b0430d8cdb78070b4c55a  PASS
vs openssl + pycryptodome + FIPS-197 (independent; re-verified 3x incl. mine; +200
random vectors 200/200). S-box built from GF(2^8) inverse + affine, ==FIPS table
256/256. Self-timed build bit-identical in LOGIC (same round cone + DFF), differs
only in capture timing (in-kind replica done = S-box + MixColumns depth, no wide
carry, NOT a comparator) -> correctness transfers.

## 2. ENERGY vs DUTY — the AES-vs-SHA contrast is the real finding
Stat-sim composition (compose_aes128.py; yosys cells x measured sha_slice 3.683
fJ/cell + add8 E_clk 28.2 fJ/DFF/cyc). E_active_encrypt 0.475 nJ/128b block, DUTY-FLAT.
  duty    vs FREE clock    vs GOOD gating (r=0.1)
  1.0      1.00x (parity)   parity         <- bulk/line-rate MACsec
  0.1      2.39x            ~1.14x
  0.01    16.3x             ~2.5x          <- bursty/event-driven frames
★ AES is the INVERSE of SHA: LOGIC-heavy (S-box = 87% of round energy), NOT register-
  heavy. Holds 260 flops (on-the-fly key) vs SHA's 774 -> floor/active 0.154 vs 0.475
  -> the clock-floor-shed win is SMALLER than SHA's (1.14x/2.5x vs SHA 1.43x/5.70x).
★ BUT the round is SHALLOW: 2.124 ns vs SHA's 5.638 ns (2.7x), no big ripple -> the
  current-sense/power-settle DONE is SHARPER and VIABLE here (SHA's deep carry ripple
  blurred it). So AES self-timed is more a GALS / clean-handshake story than a raw-
  power landslide. Keep the detector <=400 fJ (the QAL-cliff guardrail; 10 rounds).
HONEST SCOPE: WITHIN an encrypt duty~1 (all 10 rounds active) -> NO win; sustained/
line-rate MACsec = parity (fine, per directive). Win is BETWEEN frames (idle).

## 3. S-BOX FORM (the AES design lever)
  LUT/ROM:    410 cells, 1.076 ns, 1510 fJ/eval  (fast/big)
  composite:  182 cells, 3.421 ns,  670 fJ/eval  (compact/deep, Canright GF((2^4)^2))
Both verified 256/256. Composite = the low-power idle-regime choice (2.25x fewer
cells/energy). CAVEAT: the duty table above used the LUT; the composite would ~halve
the round energy (S-box is 87%), shifting absolute pJ (not shape). And the 3.683
fJ/cell anchor was from SHA adder/logic cells, transplanted onto S-box substitution
cells -- a model caveat on absolute S-box energy; ratio/shape/crossover robust.

## VERDICT
Self-timed static-CMOS AES-128 computes correctly and LOWERS POWER in the idle/
intermittent regime (~1.1-2.5x vs good clock-gating), ~parity sustained. The win is
SMALLER than SHA (AES is logic- not register-heavy) but the SHALLOW round makes
current-sense completion genuinely viable -> AES is the better CURRENT-SENSE-DONE /
GALS vehicle even though it is the weaker clock-floor-shed vehicle.
