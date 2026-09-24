# QAL vs regular-logic synthesis comparison — SHA-256

Goal: synthesize the *same* RTL as regular clocked CMOS **and** as QAL, and get measured
performance — max speed both, power across the operating range. Vehicle: SHA-256 (`ldx`
`examples/verilator-bench/sha256/Sha256.v`, standard clocked one-round/cycle). Same PDK on
both sides: **IHP SG13G2** (130 nm) — the stdcell liberty for the regular path, and the
SG13G2/PSP103 device the QAL sims (A1b/A1f/two-bank) are anchored on.

Tools: **yosys 0.58** (synth + map), **OpenSTA 3.1** (timing/power). `run_regular.sh` reproduces
the baseline. (The `ldx` SHA-256 also exists as NCL/VHDL — dual-rail, which QAL wants — but the
yosys ghdl-VHDL plugin isn't installed, so the Verilog path is used; the synthesized *gate netlist*
is what the QAL mapping consumes, so the RTL source is common either way.)

## Regular-logic baseline (MEASURED, SG13G2 typ 1.20 V, 25 °C)

| metric | value |
|--|--|
| cells | **9267** (1325 DFF `sg13g2_dfrbpq_1` + ~7942 combinational) |
| area | 148,409 (43.7% sequential) |
| critical path | **15.76 ns** (reg→reg, through the round: 32-bit adder carry chains + K/W mux trees) |
| **max clock** | **63.4 MHz** |
| power @ max clock, α=0.5 | **56.2 mW** (internal 30.5 + switching 25.8 mW; leakage 1.7 µW — negligible at 130 nm) |
| throughput (single block) | ~1.0 M hashes/s (64 rounds/block, one round/cycle) |

Notes: abc's default mapping uses ripple-carry adders + flat mux trees, so 63 MHz is an
*unoptimized* 130 nm baseline — but the QAL version faces the **same** logic, so the comparison
is relative. Power at α=0.5 is a pessimistic (uniform-toggle) upper bound.

## QAL comparison — methodology + the key workload split (NEXT)

The QAL "synthesis" = take the yosys-synthesized **combinational round netlist**, levelize it into
**banks** (wave-pipeline stages), and apply the grounded QAL cost model: dual-rail settling gates
(`qal_crossover_map.py`: E = f_adia·E_cell, speed = register-tax-eliminated) + inductive recycle +
flycap top-up per bank (`qal_twobank.py`), with realistic switch Ron + inductor R damping.

**★ The decisive point for SHA-256 (from `qal_crossover_map.py`):** single-block SHA-256 is a
**latency-bound recurrence** — the a..h state and the W-ring feed back every round — so QAL's
throughput advantage *inverts* (its multi-phase wave latency ≥ CMOS's single-cycle round; CMOS wins
single-stream). **QAL's win lands on the *streaming* case** — many independent blocks hashed in
parallel (bitcoin mining; `ldx/fpga/rtl/sha256/bitcoin_miner.vhdl`), i.e. independent lanes = exactly
the GPU-batched north-star workload. So the fair comparison must report **two regimes**: single-block
(latency; CMOS-favored on speed) and streaming/parallel (throughput; QAL 1.5–3× + the energy Pareto).

## QAL vs regular — result (`qal_sha256_compare.py`)

Netlist stats measured: **logic depth D = 60 levels** (per-level 0.263 ns; path = ripple-adder carry
chains + K/W muxes), 7942 combinational cells + 1325 DFF. The QAL side applies the fairness-verified
crossover map + two-bank recycle/topup to this netlist (projection pending Track C).

**Two regimes, and they split cleanly:**

- **Single-block hash (latency-bound):** the a..h state and the W-ring feed back every round, so the
  QAL wave's latency (D banks × beat) ≥ the regular cycle — **CMOS wins single-stream; QAL does not
  speed one hash.**
- **Streaming / mining (throughput; independent blocks = the north-star GPU-batched lanes):** QAL runs
  **~1.5–2× higher hash throughput** than a regular design pipelined to the same gate-RC limit —
  *purely* by eliminating the pipeline register/clock tax (t_reg). This is the real QAL win here.

**Energy (per round-op, QAL/regular, gate-level iso-swing, incl. dual-rail ×2):** dual-rail doubling +
no activity discount make QAL **~2.7× costlier at max speed** (τ≈3); QAL is gate-energy-cheaper only
when **slowed** (τ>~8 → 0.5–0.9×). **But** a deeply-pipelined regular pays a large clock/FF tax that
QAL's inductive recycle eliminates — so on **total** power (clock included) QAL wins even at speed; the
gate-only view is the pessimistic bound. Leakage is negligible at 130 nm (1.7 µW measured).

**Net:** for SHA-256, QAL buys **throughput on the streaming/mining workload** (1.5–2×, register-tax
elimination) — exactly the independent-lane GPU-batched case the north star targets — while single-block
latency stays CMOS-favored, and the energy verdict hinges on the clock-elimination vs the dual-rail ×2,
i.e. on the **Track-C generator/recharge efficiency** (the load-bearing unbuilt piece; only single-stage
hops are measured — A1b/A1f/two-bank). Next to harden it: replace the projected QAL power with a
measured Track-C generator number, and a coarser (realistic) pipeline depth for the regular streaming
baseline than the level-by-level bound used here.
