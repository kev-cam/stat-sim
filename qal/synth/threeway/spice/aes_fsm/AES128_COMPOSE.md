# AES-128 as a self-timed static-CMOS FSM — ENERGY-vs-DUTY composition

**Node:** IHP SG13G2 130 nm / PSP103 / 1.2 V. **Date:** 2026-10-02.
**Target:** the next self-timed-FSM target after SHA-256 — same method, AES-128.
**Reproduce:** `python3 compose_aes128.py` (no SPICE launched here).

> **User directive 2026-10-02:** *"Parity is fine, stat-sim modeling is preferable to
> SPICE."* → **No Xyce this time.** Energy is **composed** from measured anchors (yosys
> cell counts × the measured sha_slice per-cell energy + the add8 clock/register
> coefficients). Per-op parity is an acceptable result; the deliverable is the
> **duty-shaped win + the functional scaling proof**.

Every figure is tagged **[MEAS]** (measured on transistors, this campaign),
**[COMPOSED]** (derived this session — yosys + OpenSTA, scaled by a [MEAS] anchor), or
**[EST]** (honest structural estimate). Untagged numbers are definitions.

---

## 0. The approach, and the one-line question

A **self-timed static-CMOS FSM** = precharge-free static next-state logic + an
edge-triggered DFF state register + a done-pulsed capture (in-kind replica delay) — **not
domino**. It *holds* state and dissipates *only on transitions*, so it sheds the **clock
floor** at low duty → a **duty-shaped** lower-power win; per-op it is **~parity** with
clocked CMOS. Measured on a 4-bit accumulator (`../fsm/FSM_NUMBERS.txt`): energy duty-flat,
golden/self-timed **0.44× (full) → 0.89× (¼) → 1.88× (1/10)** and widening. Proven again on
SHA-256 (`../sha_fsm/`): a register-heavy round (774 flops) made the clock floor dominate
and amortized the done to <1 % → a **bigger** self-timed win than the toy.

**Question:** AES-128 is a *different shape* of crypto round. SHA was adder/rotation;
**AES is substitution — the S-box.** AES is also **less register-heavy** (128–256 b of state
vs SHA's 774 flops) and **more logic-heavy** (16 S-boxes/round). What does self-timed give
on a substitution cipher that idles between frames (MACsec / 802.1AE GCM-AES-128)?

**The round is the genuine FIPS-197 cipher, not a stand-in.** The AES S-box (GF(2⁸) inverse
+ affine, computed from first principles — no transcribed table), MixColumns, and a full
10-round encrypt were verified against the FIPS-197 vector **before** synthesis:

> key `000102030405060708090a0b0c0d0e0f`, pt `00112233445566778899aabbccddeeff`
> → ct **`69c4e0d86a7b0430d8cdb78070b4c55a`** — cross-checked vs **pycryptodome** *and*
> **`openssl enc -aes-128-ecb -nopad`**. **PASS** (not self-asserted).

---

## 1. Anchors

### Measured [MEAS] (SG13G2/PSP103, Xyce, this campaign — shared with the SHA composition)
| quantity | value | source |
|---|---|---|
| sha_slice static-CMOS 8 b round core {maj,ch,add}, E/op @α=0.476 | **232 fJ/op** | `../compose_direct.py` |
| E_clk (clock-pin+internal, per DFF, idle) | **28.2 fJ/DFF/cyc** | add8 `async_power_anchor` |
| E_regtoggle (Q switches + its load) | 45 fJ/DFF/toggle | add8 |
| per-op analog / current-sense completion done | 144–400 fJ | QAL burst ledger |
| add8 replica delay line | 500 fJ / 1.97 ns → **254 fJ/ns** | add8 ("13× costlier" finding) |

### Synthesized this session [COMPOSED] — yosys 0.58, identical recipe to the sha_slice anchor
`read_verilog; synth -flatten; abc -liberty sg13g2_typ_1p20V_25C; opt_clean; stat` → cell
count + area; **OpenSTA** on the mapped netlist → critical path.

| block | cells | area µm² | crit path | ×area vs sha_slice |
|---|---|---|---|---|
| sha_slice (re-synth = calibration basis) | 63 | 644.11 | — | 1.0× |
| **one SubBytes S-box** | **410** | 4 108.78 | **1.076 ns** | 6.4× |
| MixColumns (4 columns) | 460 | 6 676.99 | — | 10.4× |
| AddRoundKey (128 b XOR) | 128 | 1 857.95 | — | 2.9× |
| **full AES round** (16 S-box + ShiftRows + MixColumns + AddRoundKey) | **7 555** | 75 867.36 | **2.124 ns** | 117.8× |
| on-the-fly key-expansion step (RotWord + 4 S-box + Rcon + XOR) | 1 856 | 18 287.04 | 1.586 ns | 28.4× |

16 × 410 = 6 560 S-box cells = **87 %** of the 7 555-cell round. **The S-box is the round.**
(An S-box cost-agent measured per-S-box energy, if it lands, drops straight into
`E_SBOX_MEAS` in the script and replaces the composed per-S-box number for the SubBytes bulk.)

### Structural estimates [EST]
- **State flops (on-the-fly key schedule = PRIMARY) = 128 (datapath) + 128 (current round
  key) + 4 (round counter 0–10) = 260.** Alt: all 11 keys prestored = 128 + 1408 + 4 = **1540**.
- **α_tog = 0.50** flops toggling per active round (near-random cipher data).

---

## 2. Composition method (identical to SHA-256's)

Per-op switching energy scales with switched capacitance ≈ cell count / area at matched
activity. The sha_slice anchor bakes in a representative α≈0.476; AES internal nodes run at a
similar ~0.5. So:

- per-cell energy = 232 fJ / 63 cells = **3.683 fJ/cell/op**; per-area = **0.360 fJ/µm²/op**.
- combinational block energy = (cell-scaled, area-scaled) bracket; midpoint used.
- register capture per active round = 260 × (E_clk + α_tog·E_regtoggle) = 260 × 50.7 fJ.
- the **clock floor** the self-timed form sheds = 260 × E_clk = **7.33 pJ / idle cycle**.

---

## 3. Per-round / per-encrypt active energy (identical for clocked & self-timed)

| term | value | tag |
|---|---|---|
| per-S-box (composed, bracket 1510 / 1480) | **1 495 fJ** | [COMPOSED] |
| **SubBytes** (16 S-boxes) | **23 918 fJ = 87 % of the round** | [COMPOSED] |
| MixColumns | 2 049 fJ (7 %) | [COMPOSED] |
| AddRoundKey | 570 fJ (2 %) | [COMPOSED] |
| **E_comb_round** (full synthesized round) | **27 574 fJ** | [COMPOSED] |
| E_comb_key (on-the-fly key step) | 6 711 fJ | [COMPOSED] |
| **E_cap_round** (260 flops × 50.7 fJ) | **13 182 fJ** | [EST] |
| **E_active_round** | **47 467 fJ/round** (logic **72 %**, registers **28 %**) | [COMPOSED] |
| **E_active_encrypt** (10 rounds) | **0.475 nJ / 128 b block — DUTY-FLAT** | [COMPOSED] |
| round critical path | **2.124 ns → 471 MHz** (S-box 1.076 ns + MixColumns/ARK 1.048 ns) | [COMPOSED/STA] |

**Key structural result — AES is the INVERSE of SHA.** SHA-256 was **85 % register / 15 %
logic** (774 held flops, modest compute). **AES is 72 % logic / 28 % register**: the
**S-box dominates (87 % of the round)**, and the FSM holds only **260 flops — 3.0× fewer than
SHA**. So there is a **smaller clock floor to shed** (point 2 below), but the round is
**shallower** and the done is **cheaper and sharper** (points 3–4).

> Sensitivity: α_tog ∈ [0.25, 1.0] ⇒ E_active_round ∈ [41, 61] pJ, floor/active ∈ [0.12,
> 0.18]. The *direction* (logic-dominated, smaller floor than SHA) is robust across the range.
> Second-order terms folded into the representative-round model: round 10 omits MixColumns
> (−2.0 pJ) and the initial AddRoundKey + state load (+~13.7 pJ) roughly cancel.

---

## 4. Clock floor the self-timed form sheds

| form | flops | E_idle_cycle | floor / active-round |
|---|---|---|---|
| **on-the-fly key schedule (PRIMARY)** | **260** | **7.33 pJ** | **0.154** |
| prestored 11 keys (ALT) | 1 540 | 43.43 pJ | 0.386 |
| — SHA-256, for contrast | 774 | 21.83 pJ | 0.475 |
| — accumulator, for contrast | ~4 | — | ~0.22 |

AES's **floor/active = 0.154 is the smallest of the three** → the clock-floor-shed win is
**smaller than SHA's**. Prestoring all 11 round keys would *restore* a SHA-like floor
(0.386), but only by **wasting clock energy on 1408 idle key flops** — a worse absolute
design. **On-the-fly key expansion (260 flops) is the correct self-timed AES.**

---

## 5. Energy & power vs duty (free-running clocked golden vs self-timed, detector = 0)

`d` = active-round fraction. **Within an encrypt d≈1 (all 10 rounds active) → no win;** the
win is **between frames** (idle). MACsec/802.1AE GCM-AES-128 idles between Ethernet frames.

| duty d | E_clk nJ/enc | E_st nJ/enc | **E ratio** | P_clk mW | P_st mW | **P ratio** |
|---|---|---|---|---|---|---|
| 1 (sustained/bulk MACsec) | 0.475 | 0.475 | **1.00×** | 22.35 | 22.35 | **1.00×** |
| 0.5 | 0.548 | 0.475 | 1.15× | 12.90 | 11.17 | 1.15× |
| 0.1 (bursty frames) | 1.135 | 0.475 | **2.39×** | 5.34 | 2.23 | **2.39×** |
| 0.01 (event-driven) | 7.733 | 0.475 | 16.3× | 3.64 | 0.223 | 16.3× |
| 0.001 | 73.72 | 0.475 | 155× | 3.47 | 0.022 | 155× |

- **Crossover:** parity at d=1; self-timed wins for **all d<1**, win grows ∝ (1−d)/d.
- **Clocked power never falls below P_floor = 3.45 mW** — the clock keeps toggling 260 flops
  no matter how idle. Self-timed → leakage as d→0.
- **vs SHA-256** (5.28× at d=0.1, 48× at d=0.01): AES's win is **~2× smaller at matched duty**,
  exactly because its floor/active (0.154) is ~3× smaller than SHA's (0.475). **Same shape,
  smaller magnitude.**

---

## 6. Charging the completion-detector floor — and is current-sense viable for AES?

Self-timed pays a **done** every active round ×10, recovered by the shed idle clock.
Break-even **E_det < 7.33 pJ × (1−d)/d per round**; crossover duty d* = floor/(floor+E_det).

| detector [EST] | E_det | d* (wins below) | penalty @ d=1 |
|---|---|---|---|
| embedded / sparse tap | 50 fJ | 0.993 | 0.11 % |
| current-sense done (lo) | 144 fJ | 0.981 | 0.30 % |
| current-sense done (hi) | 400 fJ | 0.948 | 0.84 % |
| in-kind replica line (2.12 ns round) | 540 fJ | 0.931 | 1.14 % |

**Is current-sense ("power-settle") completion viable for AES? Yes — and *sharper* than for
SHA.** The AES round is **shallow (2.124 ns, S-box-bounded, no deep ripple carry — MixColumns
is XOR-shallow)**, so the supply current **collapses crisply** when the logic settles, which
is exactly what a current-sense "trip on outputs-GOOD" done needs
([[async_impl_v2_domino_cscd]]). SHA's deep **5.6 ns ripple** round settled slowly and smeared
that edge; AES's **2.7× shallower** round gives a clean current knee.

**The honest caveat — less headroom.** AES's floor is only **7.3 pJ** (SHA's was 21.8 pJ), so
a 400 fJ done is **5.5 %** of the floor (SHA: 1.8 %) → crossover **d* ≈ 0.95** (SHA ≈ 0.98).
The detector is sharper *and* cheaper to build, but it has **less floor to hide behind** — so
keep the done **in-kind / current-sense and ≤ ~400 fJ**. At that budget it still wins across
the whole sub-95 %-duty range, i.e. essentially the entire intermittent regime. The
QAL-cliff that killed the 4-flop accumulator (done = 64 % of the op) does **not** bite AES.

---

## 7. Honesty — vs a **clock-gated** CMOS opponent

§5–6 use the *naive free-running* clocked core. A clock-gated CMOS core recovers most of the
idle floor too. Let `r` = idle-clock fraction **not** removed (clock-tree root + ICG + leaf).
Energy ratio = 1 + r·0.154·(1−d)/d.

| duty | r=1 (none) | r=0.3 | r=0.1 (good gating) |
|---|---|---|---|
| 0.5 | 1.15× | 1.05× | 1.02× |
| 0.1 | 2.39× | 1.42× | 1.14× |
| 0.01 | 16.3× | 5.59× | 2.53× |

Against **good gating (r=0.1)** AES self-timed wins only **~1.14× (d=0.1) / ~2.5× (d=0.01)** —
**smaller than SHA's 1.43× / 5.70×**, because AES's floor/active is ~3× smaller. Per
[[threeway_gals_campaign]] ("gating quality is the entire CMOS game"): the surviving AES
advantages are (a) the un-gatable clock-tree root/leaf residue, (b) zero gating-logic
latency/complexity, and (c) a clean GALS / current-sense handshake that the **shallow S-box
round makes crisp**. For AES this is **more a GALS story than a raw-power landslide** — more
so than for SHA, where the big register floor did carry a raw-power win.

---

## 8. Bottom line

**Does self-timed static-CMOS AES-128 lower power? Yes — in the idle/intermittent regime, not
in sustained encryption — but by *less* than SHA-256.**

- **d=1 (bulk / sustained MACsec):** ~parity. Self-timed loses only the <1 % detector
  overhead. **No win** — every round active, nothing to shed.
- **Bursty / event-driven frames (wake → encrypt a frame → sleep):** the win regime.
  ~**2.4× energy/encrypt at d=0.1**, ~16× at d=0.01 vs a free-running clock;
  ~**1.1× (d=0.1) / 2.5× (d=0.01) vs *good* clock-gating.** Clocked power floored at
  **3.45 mW**; self-timed tracks duty to leakage.
- **vs SHA-256 — the instructive contrast:** AES's duty win is **~2× smaller at matched
  duty**. AES holds **260 flops, not 774** (floor/active **0.154 vs 0.475**) because it is
  **logic-heavy (S-box ≈ 87 % of the round), not register-heavy**. The register floor that
  made SHA a *landslide* self-timed candidate is largely absent in AES.
- **The compensating AES strength:** the round is **2.7× shallower** (2.12 ns, S-box-bounded,
  no ripple), so the **current-sense / power-settle done is sharper and genuinely viable** —
  the detector is cheaper and crisper than SHA's, it just has less floor to amortize against,
  so keep it ≤ 400 fJ.

**Caveats:** energy is **composed** from measured anchors (full-AES SPICE is infeasible and,
per the directive, not attempted); ratio/shape/crossover are scaling-robust, α_tog=0.5 and
leakage at extreme idle are [EST]; the honest opponent is clock-gated CMOS, against which the
margin is ~r smaller and, for AES, modest. The functional scaling proof (that a self-timed
AES round FSM encrypts correctly vs FIPS-197) is the sibling RTL deliverable; this document
establishes the **energy-vs-duty** half: self-timed AES-128 is a **GALS/intermittent-power
win, not a sustained-throughput one, and a weaker duty play than SHA — redeemed by a sharper
done that the shallow substitution round uniquely affords.**
