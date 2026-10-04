# GHASH GF(2¹²⁸) multiplier cost characterization — self-timed static-CMOS FSM campaign

**Node:** IHP SG13G2 130 nm / `sg13g2_stdcell_typ_1p20V_25C`. **Date:** 2026-10-02.
**Lane:** the GF(2¹²⁸) carry-less multiply — the *distinctive* element of GHASH, the analog
of the AES S-box and the SHA-256 adder. GHASH's whole datapath *is* this multiply:
`Y_i = (Y_{i-1} ⊕ C_i) · H mod P`, `P = x¹²⁸ + x⁷ + x² + x + 1`, `·` = carry-less
(polynomial / clmul) GF(2¹²⁸) multiply-reduce. **No S-box, no carry chain** — the purest
XOR/AND datapath of the three ciphers.
**Owned files:** `gfmul_cost.py`, `GFMUL_ANALYSIS.md` (this). Nothing else touched.
**Reproduce:** `python3 gfmul_cost.py` (add `--workdir DIR` to keep the generated Verilog +
yosys/STA logs; by default they go to a temp dir so `ghash_fsm/` stays at these two files).

Every figure is tagged **[MEAS-anchor]** (measured on transistors, prior campaign),
**[COMPOSED]** (derived here — real yosys synth + OpenSTA, scaled by a [MEAS] anchor), or
**[EST]** (honest structural estimate). Untagged numbers are definitions/counts.
**No SPICE** was launched (USER DIRECTIVE 2026-10-02: stat-sim modeling over SPICE).

---

## 0. Headline

| form | cells (SG13G2) | area µm² | depth (levels) | max path ns | E / multiply |
|---|---|---|---|---|---|
| **(a) bit-serial** — STEP ×128 cyc | **259** /step → 33 152 eq | 2 830.5 /step | **2** /cycle (0.126 ns) | 128 cycles | **122.1 pJ** |
| **(b) parallel schoolbook** (128×128 clmul + reduce) | **32 999** | 360 078.6 | **13** | **1.615** | **121.5 pJ** |
| **(c) Karatsuba parallel** (recursive, clmul + reduce) | **14 137** | 175 531.9 | **19** | **3.899** | **52.1 pJ** |

**The trade, measured:**
- **Bit-serial ≈ parallel schoolbook in total energy** (122.1 vs 121.5 pJ, within 0.5 %) — the
  *same* GF(2¹²⁸) bilinear algebra, just **time-unfolded (128 cycles) vs space-unfolded (1
  shot)**. Confirms the per-STEP×128 model. The bit-serial's *per-cycle* cone is only **2
  logic levels / 0.126 ns** — the shallowest, sharpest settle anywhere in the campaign — at
  the cost of 128 cycles and 128 register-toggle events.
- **Karatsuba is the parallel winner: 2.33× fewer cells, 2.33× less energy** than schoolbook,
  because it cuts the AND partial-product count **sub-quadratically** (NAND2 ×1 636 vs
  ×16 384, a **10×** reduction). The price is **1.46× deeper** (19 vs 13 levels) and **2.41×
  slower** path. Classic Karatsuba **area/energy ↓, depth ↑** trade. **Karatsuba is the
  realistic parallel choice; schoolbook is the naïve upper bound.**

**The scale surprise (a real finding):** a GF(2¹²⁸) multiply is a full 128×128 bilinear form
— **large**. One parallel multiply = **32 999 cells ≈ 80× the AES composite S-box (182)**;
one parallel GHASH multiply (121.5 pJ) ≈ **0.79× an entire composite-AES-128 encrypt
(154.7 pJ)**; Karatsuba (52.1 pJ) ≈ 0.34×. GHASH is **cheap in depth/latency but expensive
in area/energy per op** — the opposite balance to AES's S-box (deep/compact) and SHA's adder
(deep/cheap). This is what makes GHASH the **third, distinct** design-space point (§6).

---

## 1. What was synthesized, and how it was verified (never self-asserted)

GCM's **#1 bug is the bit reflection**: GF(2¹²⁸) blocks are polynomials with bit 0 = the MSB
of byte 0 = the x⁰ coefficient, and "multiply by x" is a **right** shift. The verification is
layered so no RTL number is reported until the reference is pinned to known-good crypto.

**Layer 1 — three independent python GF(2¹²⁸) multiplies agree (2000 random pairs):**
1. **NIST SP 800-38D Algorithm 1** directly (`R = 0xe1<<120`, right-shift conditional reduce) —
   *the definition*;
2. **reflect → standard clmul → mod-P fold → reflect** (independent reduction);
3. **reflect → clmul → xᵏ-mod-P reduction matrix → reflect** — *the structure the RTL uses*.
→ **PASS** (all three identical on 2000 pairs).

**Layer 2 — the python ref vs known-good crypto (pycryptodome + NIST vectors):**
- `H = AES_{k=0}(0)` == **`66e94bd4ef8a2c3b884cfa59ca342b2e`** — **PASS**.
- empty-message GCM tag (k = iv = 0) == **`58e2fccefa7e3061367f1d57a4e7455a`** (NIST SP 800-38D)
  and == pycryptodome — **PASS**.
- a random full GCM (53 B AAD + 96 B PT): my `GHASH(H,A,C) ⊕ AES_K(J0)` **tag *and*
  ciphertext == pycryptodome** — **PASS**. (Exercises the length block, padding, and
  reflection end-to-end.)

**Layer 3 — each RTL form vs the validated python ref (iverilog):** anchor vectors (H, all-ones,
1, 2¹²⁷, …) + 300 random pairs = **310 vectors each**:
- bit-serial (128-stage unroll): **310/310 PASS**
- parallel schoolbook: **310/310 PASS**
- Karatsuba (recursive): **310/310 PASS**

Cell counts are reported *only after* the form passed Layer 3. Recipe = **the same as the
sha_slice anchor and the AES S-box lane**: `read_verilog -sv; synth -flatten; abc -liberty
sg13g2_typ_1p20V_25C; opt_clean; stat -liberty; ltp`. yosys = `/home/claude/.local/bin/yosys`
0.58 (the `/usr/local/src/yosys-build` binary was built *without* the `abc` command);
OpenSTA = `/home/claude/.local/bin/sta`.

---

## 2. Form (a) — bit-serial (NIST Alg 1, one step reused 128×)

The classic GHASH hardware: a 256-bit state (`Z` accumulator + `V` running `Y·xⁱ`), one
combinational **step** reused for 128 cycles. The step is: `Z ← x_i ? Z⊕V : Z`;
`V ← V[0] ? (V≫1)⊕R : (V≫1)`, with `R = 0xe1‖0¹²⁰`.

- **259 cells, 2 830.5 µm², 2 logic levels, 0.126 ns** per step [COMPOSED/STA].
- Cell mix: `nand2 ×128` (the V-reduction / Z-select AND terms) + `xnor2 ×128` (the ⊕) + 3
  xor2. A clean, tiny, **2-deep** cone — one conditional-XOR layer.
- **Iterative cost = step × 128 cycles = 33 152 cell-evals → 122.1 pJ/multiply** [COMPOSED].
- A **fully-spatial 128-stage unroll** (verification build) synthesizes to **33 021 cells,
  depth 15** — i.e. abc rebalances the 128-stage chain into essentially **the parallel
  multiplier** (§3). So the bit-serial's distinctive value is *only* in the **iterative**
  realization: a **depth-2 per-cycle settle** (the sharpest `done` possible), traded for 128
  cycles of latency and 128 register-toggle events.

## 3. Form (b) — fully-parallel schoolbook (128×128 clmul + reduce)

`p[k] = ⊕_{i+j=k} a[i]·b[j]` (255-bit carry-less product by shift-and-XOR) then `r = p mod P`
via a generated linear XOR network `r[j] = ⊕ p[k]` over `{k : bit j of (xᵏ mod P)}`.

- **32 999 cells, 360 078.6 µm², 13 logic levels, 1.615 ns** [COMPOSED/STA].
- Cell mix: **`nand2 ×16 384`** (the 128×128 AND partial products) + **`xnor2 ×12 528` +
  `xor2 ×4 087`** (the ⊕ reduction tree). ~50 % AND / ~50 % XOR — the signature of a dense
  bilinear form. **This is the naïve upper bound** (no sub-product sharing).

## 4. Form (c) — Karatsuba parallel (2-way recursive, 3 sub-products/level)

Recursive split `a = a₁x⁶⁴+a₀`, `b = b₁x⁶⁴+b₀`; **3** sub-multiplies per level
(`P₀=a₀b₀`, `P₂=a₁b₁`, `P_m=(a₀⊕a₁)(b₀⊕b₁)⊕P₀⊕P₂` — the "3-way recursion"), down to the
1-bit base, then the **same** mod-P reduction.

- **14 137 cells, 175 531.9 µm², 19 logic levels, 3.899 ns** [COMPOSED/STA].
- Cell mix: **XOR-dominated** — `xnor2 ×7 220` + `xor2 ×2 340` = **9 560 XOR (68 % of cells)**,
  **`nand2` only ×1 636** (vs schoolbook's 16 384 — a **10× AND reduction**). Karatsuba
  spends XOR to save AND.
- **2.33× fewer cells / 2.33× less energy than schoolbook**, but **1.46× deeper** — the
  recursion adds a pre-add + post-add XOR layer at each of 7 levels. **Lever (not claimed
  here):** stopping the recursion at an 8- or 16-bit schoolbook base (a *hybrid* Karatsuba)
  trims the deepest XOR layers back — shallower `done` at ~similar area. The full-recursion
  14 137 is the low-area/high-depth extreme.

---

## 5. Energy composition — from the MEASURED anchor

**Anchor [MEAS-anchor]:** `sha_slice = 232 fJ / 63 cells = 3.683 fJ/cell/op` — the *same*
per-cell basis the SHA and AES composes used. `E = cells × 3.683 fJ`.

### Per multiply [COMPOSED]
| form | cells | fJ / multiply | pJ / multiply |
|---|---|---|---|
| **bit-serial** (step ×128) | 259 ×128 | 122 083.6 | **122.1** |
| **parallel schoolbook** | 32 999 | 121 520.1 | **121.5** |
| **Karatsuba parallel** | 14 137 | 52 060.1 | **52.1** |

> **Bit-serial per-STEP = 953.8 fJ; ×128 = 122.1 pJ ≈ the one-shot parallel (121.5 pJ).**
> The two land **within 0.5 %** — the same GF(2¹²⁸) XOR/AND work, time- vs space-unfolded.
> (Bit-serial pays this combinational energy *plus* 128× its register-toggle floor, the
> compose agent's clock-ledger term; parallel pays it once.)

### Per GHASH block [COMPOSED] — `Y_i = (Y_{i-1} ⊕ C_i)·H` (one multiply + a 128 b XOR = 471.4 fJ)
| | bit-serial | parallel | Karatsuba |
|---|---|---|---|
| **fJ / block** | 122 554.9 | 121 991.5 | **52 531.4** |

### Per MACsec frame [COMPOSED] — 1500 B = **94** cipher blocks (+1 AAD SecTAG, +1 length = 96 multiplies)
| | bit-serial | parallel | Karatsuba |
|---|---|---|---|
| **pJ / frame (96 mul)** | 11 765.3 | 11 711.2 | **5 043.0** |
| pJ / 94-block headline | 11 520.2 | 11 467.2 | **4 938.0** |

**→ The GF multiply dominates GHASH entirely** (the per-block ⊕ is 0.4 % of a parallel
multiply, 0.9 % of a Karatsuba one). As the S-box was AES's cost and the adder was SHA's,
the **carry-less multiply is 99 %+ of GHASH's combinational energy.** **Karatsuba roughly
halves the frame energy** and is the form to carry forward.

**Activity sensitivity [EST]** (per-cell ∝ α; anchor ≈ 0.48):

| α | serial fJ/mul | parallel fJ/mul | Karatsuba fJ/mul |
|---|---|---|---|
| 0.25 | 64 119 | 63 824 | 27 343 |
| 0.50 | 128 239 | 127 647 | 54 685 |
| 1.00 | 256 478 | 255 294 | 109 370 |

### ★ FEED TO THE ENERGY-COMPOSITION AGENT (explicit, labeled)
```
per_cell_fJ              = 3.683      [MEAS-anchor]  (232 fJ / 63 cells, sha_slice)
cells_serial_step        = 259        [COMPOSED]     (one bit-serial step)
cells_parallel           = 32999      [COMPOSED]     (schoolbook clmul + reduce)
cells_karatsuba          = 14137      [COMPOSED]     (recursive clmul + reduce)
E_mul_serial_fJ          = 122083.6   [COMPOSED]     (step x128 cycles)
E_mul_parallel_fJ        = 121520.1   [COMPOSED]     (one shot)
E_mul_karatsuba_fJ       =  52060.1   [COMPOSED]     (one shot)  <-- the realistic parallel form
E_block_parallel_fJ      = 121991.5   [COMPOSED]     ((Y XOR C).H, parallel)
E_block_karatsuba_fJ     =  52531.4   [COMPOSED]     ((Y XOR C).H, Karatsuba)
E_frame_karatsuba_pJ     =   5043.0   [COMPOSED]     (96 multiplies, 1500B frame)
depth_parallel_levels    = 13 (1.615 ns) ; depth_karatsuba = 19 (3.899 ns) ; step = 2 (0.126 ns)
GHASH_state_flops        ~ 256        [EST]  128b Y acc + 128b H held            (parallel)
GHASH_state_flops_serial ~ 512        [EST]  + 128b V + 128b X-shift (+ ctr)     (bit-serial)
```
GHASH is **register-LIGHT like AES (≈256 flops), NOT SHA (774)** → its clock-floor-shed duty
win is **AES-class or smaller** (it is the *most* logic-heavy of the three, so floor/active is
the lowest) — but its carry-less settle is the **sharpest `done`** of the three (§6). The
256-flop figure is this lane's input to the compose agent's duty/clock-floor ledger.

---

## 6. Depth → self-timed replica-done, and the three-cipher spectrum

| form / cipher | settle | character of the `done` |
|---|---|---|
| **GHASH bit-serial step** | **2 lvl / 0.126 ns** per cycle | tiniest/sharpest settle, ×128 cycles |
| **GHASH parallel** | **13 lvl / 1.615 ns** | **carry-less XOR tree — O(log), regular, monotone** |
| **GHASH Karatsuba** | 19 lvl / 3.899 ns | deeper (recursive XOR) but still a *balanced tree* |
| *AES-128 round* | *~1.08–3.42 ns* | *substitution cone — shallow, sharp* |
| *SHA-256 round* | *~5.64 ns* | *deep carry-ripple adder — data-dependent, **blurred*** |

**GHASH has no carry chain and no substitution LUT.** Every output bit is a **balanced XOR
reduction of AND partial products** — the settle is **O(log) deep, regular, and
data-independent in *shape*** (only the toggled values change, not the critical-path
structure). That is the ideal substrate for an **in-kind replica delay**: a fixed short
buffer matched to a *fixed, balanced* cone, with the current-sense `done` landing on a clean
monotone power edge. **This is the sharpest `done` of the three ciphers** — SHA's deep,
data-dependent carry ripple blurred it; AES's S-box was shallow-and-sharp; GHASH's carry-less
tree is shallow-*and-regular*, the best completion-detection target in the campaign.

The **spectrum** the three lanes now span:

| | register load | per-op logic | `done` sharpness | clock-floor duty win |
|---|---|---|---|---|
| **SHA-256** | **heavy** (774 flops) | moderate (adders) | **blurred** (carry ripple) | **largest** (1.43×/5.70×) |
| **AES-128** | light (260 flops) | heavy (S-box 87 %) | sharp (shallow round) | smaller (1.14×/2.5×) |
| **GHASH** | **light** (~256 flops) | **heaviest** (GF mult 99 %) | **sharpest** (carry-less tree) | **smallest** (most logic-heavy) |

GHASH extends the AES finding to its limit: it is the **best current-sense-/GALS-done
vehicle** (carry-less, regular, shallow) and the **weakest clock-floor-shed vehicle** (most
logic-heavy, lowest floor/active). Pick **Karatsuba** for the ~2× energy/area win; pick the
**iterative bit-serial** when the depth-2 per-cycle settle (the absolute sharpest `done`)
outweighs its 128-cycle latency and register toggling.

---

## 7. Caveats / provenance

- Absolute pJ is **[COMPOSED]** from the measured `sha_slice` per-cell anchor × real yosys
  cell counts; **no GHASH SPICE** was run (per directive). Cell counts, area, depth, and ns
  are **real synthesis/STA output** this session, not estimates.
- `E = cells × 3.683 fJ` assumes ~uniform per-cell activity at the anchor's α ≈ 0.48. The GF
  multiplier is ~half dense AND partial products (a[i]·b[j], output-prob ~0.25 on random
  data) and ~half a high-activity XOR reduction tree — the per-cell basis, measured on SHA
  adder/logic cells, is a **model caveat on absolute energy** (same caveat the AES lane
  flagged for the S-box). **Ratios / shape / the Karatsuba-vs-schoolbook crossover are
  robust** (same basis both sides); α is bracketed in §5.
- The **schoolbook 32 999** is the naïve no-sharing upper bound; the **Karatsuba 14 137** is
  the realistic parallel form, and a **hybrid Karatsuba** (schoolbook base at 8–16 b) would
  shrink the *depth* further at ~similar area (§4) — so the depth figures are an upper bound
  on a tuned build.
- Depth is yosys `ltp` logic **levels** cross-checked with OpenSTA **ns**; both agree at
  ~0.12–0.21 ns/level for SG13G2 @ 1.2 V. The bit-serial *spatial* unroll rebalances to the
  parallel multiplier (abc); only the **iterative** form carries the depth-2 per-cycle `done`.
