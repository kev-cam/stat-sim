---
name: async_power_anchor
description: "add8 transistor anchor (SG13G2/PSP103) of the sync-vs-bundled-data power model; clock floor confirmed, delay line 13x costlier than modeled, duty crossover ~0.51"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4921ad0c-f17b-4b84-986a-5917c9ebd2a6
  modified: 2026-09-23T04:14:51.544Z
---

Transistor-anchored the sync-vs-async power model by simulating an 8-bit adder
BOTH ways on SG13G2 std cells at 1.2V (PSP103 via PyMS). Six decks in
`/home/claude/async_power_anchor/` (durable; sources in scratchpad cmp8/). Feeds the
"Sync vs Async Silicon" artifact https://claude.ai/code/artifact/6aac817a-93f1-4cde-83bb-2d5dc33bd797

**Measured (E = 1.2·|∫I(VVDD)|):** sync8_idle 0.255 pJ (9-DFF floor), sync8_active
0.957 (α=1), bd8_op 1.204 pJ (verified capture sq=0xFF, co=0), bd8_idle ~2e-5 (≈0).
add8 worst-case ripple 1.514 ns; 44-inv delay line 1.968 ns (1.30×).

**Anchored coefficients:** E_clk **0.0282 pJ/DFF/cyc** (model 0.028 — CONFIRMED, 0.7%);
E_logic 0.0076/cell; E_regtoggle 0.045/DFF; E_inv 0.0063/inv/traversal; 108 ps/level; t_inv 42 ps.

**Crossover (common clock, α=duty):** E_sync=0.255+0.702α, E_bd=1.204α → **α*≈0.51**
(2-phase) / 0.33 (4-phase). Bundled-data wins ONLY below ~51% duty on this deep ripple
datapath — the delay-line tax (each op 1.20 vs 0.70 pJ dynamic) is repaid only by
eliminating the clock floor when idle. Shallow/fast datapaths → shorter line → higher α*.

**★ Three errors the anchor caught in the first (unanchored) scatter [[scaling_direction_federation_fpga_asyncfsm]]:**
(1) delay-line energy modeled **13× too cheap** (flat 0.04 pJ vs 0.50, must scale with
datapath depth) — this is why the first scatter over-sold async; (2) per-level delay
67→108 ps (ripple), speeds ~1.6× too high; (3) **unit slip: pJ·GHz = mW**, first scatter
power axis was 1000× low (µW should be mW). The RELATIVE positions held; absolutes didn't.

**vae cache trap:** PSP103 builds one .so per transistor geometry (~1.7 min g++ -O2, 782
params) in /tmp/pyms_vae_cache (~17 for the std-cell set). Cold build is the wall; warm →
~30-60s/deck. Run decks SEQUENTIALLY until cache warm — two g++ on the same hash can
corrupt the .so (I hit this launching acc8 concurrently). Kill stray sims by PID
[[pkill_selfmatch_trap]]. Anchor calibration used PyMS .hdl path (not Xyce YPSP103_VA) to
stay consistent with the add4 calibration — see [[feedback_pyms_emitter_choice]].

Open: GPU-accelerating stat-sim on Vast.AI (user flagged; matches the probability-waveform
GPU-batchable tier [[phone_dev_environment_vision]]) — the real scale lever, not more CPU.
