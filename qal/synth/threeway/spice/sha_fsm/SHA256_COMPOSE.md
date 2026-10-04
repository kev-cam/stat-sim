# SHA-256 as a self-timed static-CMOS FSM — ENERGY-vs-DUTY composition

**Node:** IHP SG13G2 130nm / PSP103 / 1.2 V. **Date:** 2026-10-02.
**Deliverable #2** of the SHA self-timed split (composition; the iverilog functional
proof and the SPICE round-core slice are the sibling deliverables).
**Reproduce:** `python3 compose_sha256.py` (no SPICE launched here).

Every figure is tagged **[MEAS]** (measured on transistors, this campaign),
**[COMPOSED]** (derived this session — yosys + OpenSTA, scaled by a [MEAS] anchor), or
**[EST]** (honest structural estimate). Numbers without a tag are definitions.

---

## 0. The approach, and the one-line question

A **self-timed static-CMOS FSM** = precharge-free static next-state logic + an
edge-triggered DFF state register + a done-pulsed capture (in-kind replica delay) — **not
domino**. It *holds* state and dissipates *only on transitions*, so it sheds the **clock
floor** at low duty. Measured on a 4-bit accumulator (`../fsm/FSM_NUMBERS.txt`): energy is
**duty-flat**, the clocked golden grows with idle, ratio golden/self-timed **0.44× (full) →
0.89× (¼) → 1.88× (1/10)** and widening, crossover ~10 % activity, functional differential
PASS. Per-op it is **~parity** with clocked CMOS; the win is **duty-shaped**.

**Question:** what does that give on a *real, register-heavy crypto round* instead of a
toy? SHA-256 is 64 rounds over 8 working words `a..h` (256 b) plus a 512 b message-schedule
window — deep static combinational logic per round, idle between 512 b blocks/messages.

**The round is the genuine algorithm, not a stand-in.** The round and message-schedule
equations that drive every synthesized cell count below were verified against
`hashlib`: `work/verify_round_eqs.py` reproduces `SHA-256("abc")` =
`ba7816bf…f20015ad` and two other vectors — **PASS**.

---

## 1. Anchors

### Measured [MEAS] (SG13G2/PSP103, Xyce, this campaign)
| quantity | value | source |
|---|---|---|
| sha_slice static-CMOS 8 b round core {maj,ch,add}, E/op @α=0.476 | **232 fJ/op** | `../compose_direct.py`, `work/cmos.vcd` |
| sha_slice CMOS critical path | 0.928 ns | STA on `work/sha_slice.cmos.v` |
| E_clk (clock-pin+internal, per DFF, idle) | **28.2 fJ/DFF/cyc** | add8 `async_power_anchor` |
| E_regtoggle (Q switches + its load) | 45 fJ/DFF/toggle | add8 |
| sync8 idle floor (9 DFF) | 255 fJ → 28.3 fJ/DFF | add8 (confirms E_clk) |
| bundled/self-timed idle | ≈ 0 | add8 |
| accumulator ratio golden/self-timed @ duty 1 / ¼ / 1/10 | 0.44 / 0.89 / 1.88 | `../fsm/FSM_NUMBERS.txt` |
| per-op analog completion comparator | 144–400 fJ | QAL burst ledger |
| add8 replica delay line (1.97 ns, 44-inv) | 500 fJ → 254 fJ/ns | add8 (the "13× costlier" finding) |

### Synthesized this session [COMPOSED] — yosys, identical recipe to the sha_slice anchor
`synth -flatten; abc -liberty sg13g2_typ_1p20V_25C; opt_clean` → cell count + OpenSTA path.

| block | cells | area µm² | crit path | ×area vs sha_slice |
|---|---|---|---|---|
| sha_slice (re-synth = calibration basis) | 63 | 644.11 | — | 1.0× |
| **sha256_round_dp** (full 32 b round next-state) | **1328** | 14 458.95 | **5.64 ns** | 22.4× |
| **sha256_msgsched** (W[t] from the 16-word window) | **557** | 6 475.56 | 4.25 ns | 10.1× |

(The 63-cell re-synth brackets the 56-cell measured deck; using the **same recipe** for the
calibration basis and the target keeps the scaling ratio recipe-invariant.)

### Structural estimates [EST]
- **State flops = 256 (`a..h`) + 512 (W[t−16..t−1] window) + 6 (round counter) = 774.**
- **α_tog = 0.50** flops toggling per active round (near-random crypto data).
- **Schedule active 48/64 rounds** (rounds 0–15 just load the message words).

---

## 2. Composition method

Per-op switching energy scales with switched capacitance ≈ cell count / area at matched
activity. The sha_slice anchor already bakes in a representative α=0.476 (its measured VCD);
SHA internal nodes run at a similar ~0.5. So:

- per-cell energy = 232 fJ / 63 cells = **3.68 fJ/cell/op**; per-area = **0.360 fJ/µm²/op**.
- combinational block energy = (cell-scaled, area-scaled) bracket; midpoint used.
- register capture per active round = 774 × (E_clk + α_tog·E_regtoggle) = 774 × 50.7 fJ.
- the **clock floor** the self-timed form sheds = 774 × E_clk = **21.83 pJ / idle cycle**
  (idle flops don't toggle → E_clk only).

---

## 3. Per-round / per-hash active energy (identical for clocked & self-timed)

| term | value | tag |
|---|---|---|
| E_comb_round (round_dp) | 5.05 pJ | [COMPOSED] |
| E_comb_sched (×0.75 active) | 1.64 pJ/round avg | [COMPOSED] |
| **E_cap_round** (774 flops) | **39.24 pJ** | [EST] |
| **E_active_round** | **45.9 pJ/round** (logic **15 %**, registers **85 %**) | [COMPOSED] |
| **E_active_hash** (64 rounds, sched 48) | **2.94 nJ / 512 b block — DUTY-FLAT** | [COMPOSED] |
| round rate (ripple synth) | 5.64 ns → 177 MHz | [COMPOSED/STA] |

**Key structural result: register capture dominates (~85 %).** SHA-256 holds 774 flops
against a modest per-round compute, so the clocked form's floor is a *large fraction* of its
active energy: **floor/active = 21.83/45.9 = 0.475** (the accumulator's was ~0.22). A
register-heavy block is a *better* self-timed candidate than a logic-heavy toy — more floor
to delete per unit of active work.

> Sensitivity: α_tog ∈ [0.25, 1.0] ⇒ E_active_round ∈ [30, 64] pJ, floor/active ∈ [0.34,
> 0.73]. The win direction is robust across the whole range.

---

## 4. Energy & power vs duty (free-running clocked golden vs self-timed, detector = 0)

`d` = active-round fraction. **Within a hash d≈1 (every round active) → no win there;** the
win is **between** blocks/messages (idle). Clocked pays 21.83 pJ × idle-cycles; self-timed
pays nothing while idle.

| duty d | E_clk nJ/hash | E_st nJ/hash | **E ratio** | P_clk mW | P_st mW | **P ratio** |
|---|---|---|---|---|---|---|
| 1 (back-to-back) | 2.94 | 2.94 | **1.00×** | 8.15 | 8.15 | **1.00×** |
| 0.5 | 4.34 | 2.94 | 1.48× | 6.01 | 4.07 | 1.48× |
| 0.1 | 15.5 | 2.94 | **5.28×** | 4.30 | 0.81 | **5.28×** |
| 0.01 | 141 | 2.94 | 48.0× | 3.91 | 0.082 | 48.0× |
| 0.001 | 1398 | 2.94 | 476× | 3.88 | 0.008 | 476× |

- **Crossover:** parity at d=1; self-timed wins for **all d<1**, win grows ∝ (1−d)/d.
- **Clocked power never falls below P_floor = 3.87 mW** — the clock keeps toggling 774 flops
  no matter how idle the core is. Self-timed → leakage as d→0.
- These ratios exceed the accumulator's (1.88× at 1/10) precisely because SHA's
  floor/active is larger.

> **Leakage ceiling [EST]:** at extreme low duty (idle measured in ms–s) static leakage of
> the held state + parked logic bounds the self-timed floor and caps the ratio; not measured
> here (the accumulator windows were short enough that leakage was negligible and energy was
> flat). Treat the 476× as the dynamic-only asymptote, not a steady-state claim.

---

## 5. Charging the completion-detector floor (the QAL guardrail)

Self-timed pays a **done** every active round ×64, recovered by the shed idle clock.
Break-even: **E_det < 21.83 pJ × (1−d)/d per round**; crossover duty d* = floor/(floor+E_det).

| detector [EST] | E_det | d* (wins below) | penalty @ d=1 |
|---|---|---|---|
| embedded / sparse tap | 50 fJ | 0.998 | 0.11 % |
| in-kind replica slice (round/32) | 153 fJ | 0.993 | 0.33 % |
| per-op analog comparator (lo) | 144 fJ | 0.993 | 0.31 % |
| per-op analog comparator (hi) | 400 fJ | 0.982 | 0.87 % |
| full buffer replica line (5.6 ns) | 1432 fJ | 0.938 | 3.12 % |

**The QAL-cliff does not bite SHA-256.** On the 4-flop accumulator the completion detector
was comparable to the whole datapath (the d=1 loss was 2.27×). Here SHA's **774-flop clock
floor (21.8 pJ/cyc) dwarfs any detector (≤ 1.4 pJ)**: even the "re-dominating" per-op
comparator wins below ~98 % duty, and even a full 5.6 ns buffer replica wins below ~94 %.
**Max tolerable detector for a win at d: E_det < 21.83·(1−d)/d pJ** — e.g. 196 pJ at d=0.1.
Keep the done **embedded/in-kind** anyway (cheap, and it protects the near-d=1 edge).

---

## 6. Honesty — vs a **clock-gated** CMOS opponent

§4–5 use the *naive free-running* clocked core (the accumulator's golden, and the task's
stated baseline). A clock-gated CMOS core recovers most of the idle floor too. Let `r` = the
idle-clock fraction **not** removed (clock-tree root + ICG cells + leaf still toggling).
Energy ratio = 1 + r·0.475·(1−d)/d.

| duty | r=1 (none) | r=0.3 | r=0.1 (good gating) |
|---|---|---|---|
| 0.5 | 1.48× | 1.14× | 1.05× |
| 0.1 | 5.28× | 2.28× | 1.43× |
| 0.01 | 48.0× | 15.1× | 5.70× |

Per `threeway_gals_campaign` ("gating quality is the entire CMOS game", and the QAL burst
regime *closed* against power-gate+SRAM CMOS): the self-timed form **still wins**, but
against good gating the margin shrinks by ~r and is leakage-capped. The honest self-timed
advantages that survive good gating are (a) the un-gatable clock-tree root/leaf residue, (b)
zero gating-logic latency/complexity, and (c) no clock-tree insertion-delay or skew to
close — a GALS-friendly story more than a raw-power landslide.

---

## 7. Bottom line

**Does self-timed static-CMOS SHA-256 lower power? Yes — in the idle/intermittent regime,
not in sustained hashing.**

- **d=1 (back-to-back / continuous miner / streaming):** ~parity. Self-timed loses only the
  <1 % detector overhead. **No win** — every round is active, nothing to shed.
- **Bursty / event-driven (wake → hash a message → sleep):** the win regime.
  ~**5.3× energy/hash and 5.3× power at d=0.1**, ~48× at d=0.01, vs a free-running clock;
  ~**1.4× (d=0.1) / 5.7× (d=0.01) vs *good* (r=0.1) clock-gating.** Clocked power is floored
  at **3.87 mW** no matter how idle; self-timed tracks duty down to leakage.
- **Why SHA fits better than the toy:** 774 flops of held state ⇒ a large clock floor to
  delete and a negligible relative detector cost ⇒ the duty crossover sits at essentially
  d=1 and the QAL-cliff never triggers.

**Caveats:** ripple-carry synthesis (round 5.64 ns; a CSA/CLA core shortens the path and
trims the 15 % combinational share but **not** the 85 % register share — the result gets
*more* register-dominated, strengthening the duty story); α_tog=0.5 and leakage at extreme
idle are [EST]; the honest opponent is clock-gated CMOS, against which the margin is ~r
smaller. The per-round energy wants the SPICE round-core slice (deliverable #3) to replace
the composed 2.94 nJ/hash with a transistor-anchored figure.
