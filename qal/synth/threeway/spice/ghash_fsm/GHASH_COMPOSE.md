# GHASH (GF(2¹²⁸) carry-less MAC) as a self-timed static-CMOS FSM — ENERGY-vs-DUTY composition

**Node:** IHP SG13G2 130 nm / PSP103 / 1.2 V. **Date:** 2026-10-02.
**Target:** the **third** self-timed-FSM design-space point after SHA-256 and AES-128 — same
method — completing the Ethernet **MACsec (802.1AE GCM-AES-128)** primitive (AES-128 encrypts,
GHASH authenticates).
**Reproduce:** `python3 compose_ghash.py` (no SPICE launched here).

> **User directive 2026-10-02:** *"Parity is fine, stat-sim modeling is preferable to
> SPICE."* → **No Xyce.** Energy is **composed** from measured anchors (yosys cell counts ×
> the measured sha_slice per-cell energy + the add8 clock/register coefficients). Per-op parity
> is an acceptable result; the deliverable is the **duty-shaped win + the functional scaling proof**.

Every figure is tagged **[MEAS]** (measured on transistors, this campaign), **[COMPOSED]**
(derived this session — yosys + OpenSTA, scaled by a [MEAS] anchor), or **[EST]** (honest
structural estimate). **The multiplier cell counts & per-mult energy are the multiplier-cost
agent's authoritative feed** (`GFMUL_ANALYSIS.md`, this directory); this composition consumes
them directly and takes **Karatsuba** as the primary form (the agent's "realistic parallel
choice"). Untagged numbers are definitions.

---

## 0. The approach, and the one-line question

A **self-timed static-CMOS FSM** = precharge-free static next-state logic + an edge-triggered
DFF state register + a done-pulsed capture (in-kind replica delay) — **not domino**. It *holds*
state and dissipates *only on transitions*, so it sheds the **clock floor** at low duty → a
**duty-shaped** lower-power win; per-op it is **~parity** with clocked CMOS. Proven on a 4-bit
accumulator, then SHA-256 (register-heavy → big floor win, blurred done) and AES-128
(logic-heavy → small floor win, sharp done).

**GHASH is the far logic/regular corner.** It is a **GF(2¹²⁸) carry-LESS multiply-accumulate**:
for each 128-bit block `C_i`,

> `Y_i = (Y_{i-1} ⊕ C_i) · H  mod P`,  `P = x¹²⁸ + x⁷ + x² + x + 1` (the GCM poly),
> `H = AES_K(0¹²⁸)` = the hash subkey, `·` = carry-less (clmul) GF(2¹²⁸) multiply then reduce.

**No S-box, no carry, no adder ripple — pure XOR/AND trees.** State = the 128-bit accumulator
`Y` (+ `H` held constant). **Question:** what does self-timed give on the *carry-less,
most-regular* round of the three, which idles between MACsec frames?

### Verification — the correct GCM bit-reflection, cross-checked (NOT self-asserted)
GCM's #1 bug is bit order: **bit 0 is the MSB of byte 0** (the x⁰ coefficient); "multiply by x"
is a **right** shift. Two independent layers pin the model:

- **This composition's own ref** (cross-checked vs **pycryptodome**, this session):
  `H = AES_0(0)` = **`66e94bd4ef8a2c3b884cfa59ca342b2e`** (NIST SP 800-38D) — PASS; empty-message
  GCM tag (k=iv=0) = **`58e2fccefa7e3061367f1d57a4e7455a`** (NIST) — PASS; **50/50** random
  (AAD,PT) vectors `GHASH(H,A,C)⊕E_K(J0)` == pycryptodome tag — PASS.
- **The multiplier-cost lane** (`GFMUL_ANALYSIS.md`): three independent python GF(2¹²⁸) multiplies
  agree on 2000 pairs; python ref == pycryptodome on H, the NIST empty tag, and a full random GCM;
  then **each RTL form iverilog-verified 310/310** vs that validated ref *before* its cell count
  was reported.

(The RTL lane's `ghash_fsm.v` = 128 b `Y` + 128 b `H` + 8 b block counter = **264 flops**, one
`ghash_round`/block; its functional NIST proof is the sibling deliverable. This document is the
**energy-vs-duty** half.)

---

## 1. Anchors

### Measured [MEAS] (SG13G2/PSP103, Xyce, this campaign — shared with the SHA & AES compositions)
| quantity | value | source |
|---|---|---|
| sha_slice static-CMOS 8 b round core {maj,ch,add}, E/op @α=0.476 | **232 fJ/op** | `../compose_direct.py` |
| E_clk (clock-pin+internal, per DFF, idle) | **28.2 fJ/DFF/cyc** | add8 `async_power_anchor` |
| E_regtoggle (Q switches + its load) | 45 fJ/DFF/toggle | add8 |
| per-op analog / current-sense completion done | 144–400 fJ | QAL burst ledger |
| add8 replica delay line | 500 fJ / 1.97 ns → **254 fJ/ns** | add8 ("13× costlier" finding) |

per-cell energy = 232 fJ / 63 cells = **3.683 fJ/cell/op** (the same basis the SHA & AES
composes use).

### The GF(2¹²⁸) multiplier — three forms [COMPOSED by the multiplier-cost lane]
yosys 0.58, **identical recipe** to the sha_slice/AES anchors (`synth -flatten; abc -liberty
sg13g2_typ_1p20V_25C; opt_clean; stat; ltp`) + OpenSTA; each form iverilog **310/310** first.

| form | cells | area µm² | depth (lvls) | path ns | E/mult | note |
|---|---|---|---|---|---|---|
| **bit-serial** (step ×128 cyc) | 259/step | 2 830 | **2** (0.126 ns) | 128 cyc | **122.1 pJ** | sharpest per-cycle settle |
| **parallel schoolbook** (clmul + reduce) | 32 999 | 360 079 | 13 | **1.615** | **121.5 pJ** | naïve upper bound |
| **★ Karatsuba parallel** (recursive) | **14 137** | 175 532 | 19 | 3.899 | **52.1 pJ** | **PRIMARY — realistic choice** |

**Karatsuba = 2.33× fewer cells / 2.33× less energy than schoolbook** (AND count 10× down —
1 636 vs 16 384 `nand2`) at **1.46× the depth** (19 vs 13 levels). The bit-serial and schoolbook
forms do the *same* GF algebra time- vs space-unfolded (122.1 ≈ 121.5 pJ, within 0.5 %).

> **The GF multiply is the distinctive GHASH element — the analog of AES's S-box.** It is **99 %+
> of GHASH's combinational energy** (the per-block `Y⊕C` XOR = 471 fJ = 0.9 %). The multiply *is*
> GHASH, as the S-box was AES and the adder was SHA. `compose_ghash.py` consumes the lane's
> `E_block` directly and exposes `E_BLOCK_OVERRIDE` for a later tuned/hybrid-Karatsuba number.

> **Scale surprise (a real finding).** A GF(2¹²⁸) multiply is a full 128×128 bilinear form —
> **large**: schoolbook ≈ 33 k cells ≈ 80× the composite AES S-box; even Karatsuba (14 k) is
> ≈ 0.34× an entire composite-AES-128 encrypt in energy. **GHASH is cheap in latency but
> expensive in area/energy per op** — the opposite balance to AES's deep/compact S-box.

### Structural estimates [EST]
- **Parallel FSM state = 128 (Y) + 128 (H held) + 8 (block ctr) = 264 flops** (RTL lane;
  mult lane feed ≈ 256 = Y+H) — **register-LIGHT, like AES (260), not SHA (774)**.
- Bit-serial ≈ **512 flops** (+ 128 b `V` + 128 b X-shift + counters).
- **α_tog = 0.50** flops toggling per active block (near-random cipher data).

---

## 2. Composition method (identical to SHA-256's and AES-128's)

- combinational block energy = **the multiplier lane's `E_block`** (per-cell 3.683 fJ × real
  cells; bracket folded in that lane).
- register capture per active block = 264 × (E_clk + α_tog·E_regtoggle) = 264 × 50.7 fJ = **13.4 pJ**.
- the **clock floor** the self-timed form sheds = 264 × E_clk = **7.44 pJ / idle cycle**.

---

## 3. Per-block active energy (identical for clocked & self-timed)

| term | Karatsuba (PRIMARY) | schoolbook | tag |
|---|---|---|---|
| E_comb_block (multiply + `Y⊕C`) | **52.5 pJ** | 122.0 pJ | [COMPOSED, mult lane] |
| E_cap_block (264 flops × 50.7 fJ) | **13.4 pJ** | 13.4 pJ | [EST] |
| **E_active_block** | **65.9 pJ** (logic **80 %**) | 135.4 pJ (logic 90 %) | [COMPOSED] |
| round critical path | 3.899 ns (depth 19) → ~256 MHz | 1.615 ns (depth 13) → ~619 MHz | [COMPOSED/STA] |

**Key structural result — GHASH is the EXTREME of the AES direction:** ~**80–90 % logic / 10–20 %
register**, one GF multiply over a **tiny 264-flop register file** — the **most logic-heavy and
(with AES) most register-light** of the three.

### 3′. The two realizations — a real GHASH design-space axis
| form | cyc/block | E/block | floor/active | character |
|---|---|---|---|---|
| **Karatsuba parallel** (PRIMARY) | 1 | **0.066 nJ** | **0.113** | logic-dominated, deeper tree (depth 19), **energy choice** |
| schoolbook parallel | 1 | 0.135 nJ | 0.055 | shallower (depth 13) but 2.3× the energy — upper bound |
| **bit-serial** (128 steps) | 128 | **1.78 nJ** (**27×**) | 0.79/step | depth-**2** per-cycle settle — **area choice**, 128× register toggling |

Bit-serial is **register-light in flop *count*** but clocks the 256 b `V`+`Z` register **128× per
block** → it pays ~27× the Karatsuba energy. **Bit-serial is the area-limited choice** (its gift
is the depth-2 per-cycle settle — the absolute sharpest `done`); **the MACsec-energy-correct
GHASH is the parallel Karatsuba form**, used below.

---

## 4. Clock floor the self-timed form sheds — the 3-cipher contrast

| cipher / form | flops | E_idle_cycle | **floor / active-round** |
|---|---|---|---|
| — SHA-256 (register-heavy) | 774 | 21.83 pJ | **0.475** |
| — AES-128 (logic-heavy) | 260 | 7.33 pJ | **0.154** |
| **GHASH — Karatsuba (PRIMARY)** | **264** | **7.44 pJ** | **0.113** |
| **GHASH — schoolbook** | 264 | 7.44 pJ | **0.055** |

**GHASH has the lowest floor/active of the three** (0.055 schoolbook → 0.113 Karatsuba, both below
AES's 0.154). Its one GF multiply makes active compute enormous relative to its small register
file → the **least clock floor to shed**. Karatsuba (less logic than schoolbook) lifts the ratio
toward AES-class. **GHASH's self-timed value is *not* the floor-shed — it is the regular/sharp
done (§6).**

---

## 5. Energy & power vs duty (free-running clocked golden vs self-timed, detector = 0) — Karatsuba

`d` = active-block fraction. **Within a frame d≈1 → no win;** the win is **between frames** (idle).
MACsec/802.1AE idles between Ethernet frames.

| duty d | E_clk pJ/blk | E_st pJ/blk | **E ratio** | P_clk mW | P_st mW | **P ratio** |
|---|---|---|---|---|---|---|
| 1 (line-rate sustained) | 65.9 | 65.9 | **1.00×** | 16.91 | 16.91 | **1.00×** |
| 0.5 | 73.4 | 65.9 | 1.11× | 9.41 | 8.45 | 1.11× |
| 0.1 (bursty frames) | 132.9 | 65.9 | **2.02×** | 3.41 | 1.69 | 2.02× |
| 0.01 (sparse/event) | 803.0 | 65.9 | 12.2× | 2.06 | 0.17 | 12.2× |
| 0.001 | 7 503 | 65.9 | 114× | 1.92 | 0.017 | 114× |

- **Crossover:** parity at d=1; self-timed wins for **all d<1**, by a margin set by floor/active
  (0.113) — **AES-class**, smaller than SHA, bigger than schoolbook-GHASH.
- **Clocked power never falls below P_floor = 1.91 mW** — the clock keeps toggling 264 flops no
  matter how idle. Self-timed → leakage as d→0.

### 5′. MACsec roll-up (1500-byte frame = 94 blocks, 10 GbE), Karatsuba
E_active/frame = **6.2 nJ**. At 10 Gb/s = 7.81×10⁷ blocks/s:

| regime | P_clk | P_st | ratio |
|---|---|---|---|
| d=1 line-rate sustained | 5.15 mW | 5.15 mW | 1.00× |
| d=0.1 bursty frames | 1.04 mW | 0.52 mW | 2.02× |
| d=0.01 sparse/event | 0.63 mW | 0.05 mW | 12.2× |

GHASH's ~256 MHz block rate (Karatsuba) is **not** throughput-bound for 10 GbE; the model prices
average power at the duty, where the clocked core floors on its clock tree and the self-timed
core tracks duty to leakage.

---

## 6. Charging the completion-detector floor — is current-sense BEST for GHASH?

Self-timed pays a **done** every active block, recovered by the shed idle clock. Break-even
**E_det < 7.44 pJ × (1−d)/d per block**; crossover duty d* = floor/(floor+E_det).

| detector [EST] | E_det | d* (wins below) | penalty @ d=1 |
|---|---|---|---|
| embedded / sparse tap | 50 fJ | 0.993 | 0.08 % |
| current-sense done (lo) | 144 fJ | 0.981 | 0.22 % |
| current-sense done (hi) | 400 fJ | 0.949 | 0.61 % |
| in-kind replica line (3.9 ns Karatsuba round) | 991 fJ | 0.883 | 1.50 % |

**Is current-sense ("power-settle") completion the best fit for GHASH? Yes — the *sharpest* of the
three — but because the carry-less round is REGULAR and DATA-INDEPENDENT in *shape*, not merely
shallow.** Every output bit is a **balanced XOR reduction of AND partial products** — no carry
chain, no S-box LUT — so the critical-path *structure* is fixed (only the toggled values change).
An **in-kind replica delay** therefore matches a *fixed, balanced* cone, and the supply current
collapses on a clean **monotone** edge — exactly what a current-sense *"trip on outputs-GOOD"* done
needs ([[async_impl_v2_domino_cscd]]). SHA's deep **data-dependent carry ripple** blurred that edge;
AES's S-box was shallow-and-sharp; **GHASH's carry-less tree is regular-and-monotone** — the best
completion-detection target in the campaign. (The schoolbook form is also *shallow* — 1.615 ns,
below AES; Karatsuba trades depth for area but keeps the balanced-tree regularity; the bit-serial
step is depth-2 — the absolute sharpest per-cycle settle.)

**The honest caveat — the least floor to hide behind.** GHASH's clock floor is only **7.44 pJ**
(AES 7.33, SHA 21.8), so a 400 fJ done is **5.4 %** of the floor (AES 5.5 %, SHA 1.8 %) → crossover
**d* ≈ 0.95**. GHASH has the **least** floor to amortize a done against — so keep it
**in-kind / current-sense and sharp**, which its regular carry-less round (or the depth-2
bit-serial step) uniquely affords. The per-op *penalty* is negligible (≤0.6 %) because the block
compute is large.

---

## 7. Honesty — vs a **clock-gated** CMOS opponent (Karatsuba)

§5–6 use the *naive free-running* clocked core. A clock-gated CMOS core recovers most of the idle
floor too. Let `r` = idle-clock fraction **not** removed (clock-tree root + ICG + leaf). Energy
ratio = 1 + r·0.113·(1−d)/d.

| duty | r=1 (none) | r=0.3 | r=0.1 (good gating) |
|---|---|---|---|
| 0.5 | 1.11× | 1.03× | 1.01× |
| 0.1 | 2.02× | 1.31× | 1.10× |
| 0.01 | 12.2× | 4.35× | 2.12× |

Against **good gating (r=0.1)** GHASH-Karatsuba wins **~1.10× (d=0.1) / ~2.12× (d=0.01)** —
**AES-class** (AES 1.14× / 2.5×, SHA 1.43× / 5.70×); schoolbook-GHASH would be the smallest of the
three. For GHASH the surviving self-timed advantages are (a) the un-gatable clock-tree root/leaf
residue, (b) zero gating-logic latency/complexity, and (c) a clean GALS / current-sense handshake
that the **regular carry-less round makes the sharpest** of the three. **For GHASH this is almost
entirely a GALS/completion story, not a floor-shed story.**

---

## 8. Bottom line — GHASH, and the completed GCM-AES picture

**Does self-timed static-CMOS GHASH lower power? Yes — in the idle/intermittent regime, not at
line rate — by an AES-class margin with the realistic Karatsuba multiplier (the smallest of the
three with schoolbook).**

- **d=1 (line-rate / sustained MACsec):** ~parity. Self-timed loses only the ≤0.6 % detector
  overhead. **No win** — every block active, nothing to shed.
- **Bursty / event-driven frames:** the win regime. ~**2.0× energy/block at d=0.1**, ~12× at
  d=0.01 vs a free-running clock; ~**1.10× / 2.12× vs *good* clock-gating.** Clocked power floored
  at **1.91 mW** (≈5.15 mW at 10 GbE line rate); self-timed tracks duty to leakage.
- **The 3-cipher arc (the real finding):**

| | SHA-256 | AES-128 | **GHASH** |
|---|---|---|---|
| round character | arithmetic (adders) | substitution (S-box) | **carry-less (XOR/AND)** |
| held flops | 774 | 260 | **264** |
| floor / active | 0.475 | 0.154 | **0.055–0.113** |
| round settle | 5.638 ns deep **data-dependent** ripple | 2.124 ns S-box cone | **regular balanced tree** (schoolbook 1.615 ns / Karatsuba 3.899 ns / step 0.126 ns) |
| clock-floor-shed win (vs good gating @0.01) | **5.70×** | 2.5× | **2.12× (Karatsuba) / smaller (schoolbook)** |
| current-sense done | **blurred** (data-dependent ripple) | sharp (shallow round) | **sharpest** (regular, monotone) |

  **Register-weight predicts the floor win; round *regularity* predicts the done.** SHA is the
  register-heavy clock-floor landslide with a blurred data-dependent done; AES is the logic-heavy
  small-floor win with a sharp done; **GHASH is the far logic/regular corner — the smallest floor
  win, but the sharpest, most monotone current-sense completion the campaign has seen.** GHASH is
  the **best current-sense-done / GALS vehicle and the weakest clock-floor-shed vehicle.**

- **GCM-AES-128 combined (encrypt + authenticate, per 128 b block):**

| AES S-box form | AES/block | GHASH (Karatsuba) | GCM-AES/block | GHASH share |
|---|---|---|---|---|
| LUT (AES headline) | 0.475 nJ | 0.066 nJ | **0.541 nJ** | 12 % (+14 % over AES) |
| composite (low-power) | 0.155 nJ | 0.066 nJ | **0.221 nJ** | 30 % (+43 % over AES) |

  Combined held state **~524 flops** (AES 260 + GHASH 264) → combined idle floor **~14.8 pJ/cyc**.
  **GCM-AES is a GALS/intermittent-power primitive:** parity at line rate, a modest-but-real idle
  win vs good gating (AES-class), and — uniquely in the GHASH half — the sharpest current-sense
  completion available, the natural handshake anchor for a self-timed MACsec datapath.

**Caveats:** energy is **composed** from measured anchors (full-GHASH SPICE is infeasible and,
per directive, not attempted); cell counts/area/depth/ns are real synthesis/STA output from the
multiplier-cost lane; the GF multiply is ~half dense AND partial products and ~half a
high-activity XOR tree, so the per-cell basis (measured on SHA adder/logic cells) is a model
caveat on *absolute* energy — **ratios / shape / the Karatsuba-vs-schoolbook crossover are robust**
(same basis both sides), and α_tog is bracketed in the mult lane. Karatsuba's 3.899 ns is the
full-recursion extreme; a **hybrid Karatsuba** (schoolbook base at 8–16 b) would shrink the done
depth further at ~similar area. The functional scaling proof (a self-timed GHASH FSM authenticates
correctly vs the NIST-validated reference) is the sibling RTL deliverable; **this document
establishes the energy-vs-duty half: self-timed GHASH is a sharp-completion / GALS win, not a
sustained-power one, and the weakest duty play of the three — redeemed by the sharpest, most
regular done its carry-less round uniquely affords.**
