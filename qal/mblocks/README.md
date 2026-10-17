# qal/mblocks -- CRC-32 and an array multiplier on the three-phase wave vs pipelined CMOS

Pre-registered in `PRE_REGISTERED.json` before the first deck (predictions, acceptance, comparator forms).
Simulator: **VACASK 0.3.4 primary** (PSP103 OSDI, kestrel tt cards), **Xyce cross-check** on one anchor row per block.
Wave: the committed `qal/mesh3` point VERBATIM -- ideal three-phase trapezoid (rise/hold/fall thirds), T_third = 92 ps (period 276 ps), 1.65 V, bank k on phase (k-1) mod 3, outputs direct-wired, no registers, d = 3 nand-levels per bank as pre-registered (re-mapped to d = 2 after the cell-class calibration, see Verdict). Ideal mesh = BOUND (ASSUMED, standing licence); ideal head = BOOKED (see riders).
Energy is REPORTED, never gated. Model language: tracking lag / eye / margin at the sampling instant.

## Verdict (all numbers MEASURED unless labelled)

**Neither block sustains on the three-phase wave at SG13G2 under the pre-registered acceptance, at any T_third tried (92-165 ps), under either mapping rule.** The pre-registered point (3 nand2 levels per bank at 92 ps) fails by cascade (falsified, below): the nand2 level is 1.5-1.6x the inverter level, so a bank holds two nand2 levels at 92 ps, not three. Re-mapped at d = 2 the uniform nand2 calibration lane passes (356 mV margin) but the real blocks do not. Two causes were isolated on lane experiments, both properties of the wave rather than of the blocks:

1. **Level order.** A bank's outputs are destroyed by the death of its own inputs one gate delay per level after the previous bank dies, while the next bank's consumers commit one gate delay per level after their rail rises; the two rates are equal, so a producer at level-in-bank j may feed a next-bank consumer at level-in-bank i only if j >= i. The committed alignment rule allowed (1->2) edges (78 in the 8x8 multiplier, 0 in the lane). Rule implemented (`MB_RETIME=last`, parity-aware inverter-chain retiming; multiplier 13 -> 18 banks, 658 -> 1366 delay inverters). It removed every value failure from the CRC at 92 ps (0/2910 boundary bits wrong, 6/6 words) but did not rescue the multiplier.
2. **Load.** Fanout lanes (the same nand2(x,x) chain with f identical consumers per node, d = 2): f = 1 passes at 92 ps (356 mV), f = 2 passes with the margin halved (210 mV, overlap 16 ps, tracking lag 57 -> 85 ps), f = 4 FAILS at 92 and at 117 ps (lag 104-174 ps: the output never reaches the receiver's trip before the hold ends). The multiplier has 302 boundary signals driving 3-5 gate inputs (FA/HA outputs in the Dadda tree); the CRC has none above 2. The multiplier is extinct under both rules for this reason; it would need load-limited duplication (every node <= ~4 gate inputs) to be mapped at all.

The CRC (XOR trees, fanout <= 2) is the only block that computes correctly on the wave at 92 ps; it still misses the pre-registered B/C gates at one link (margin -218 mV at commit, overlap -18 ps, link 3) because its banks commit 20-40 ps later than the uniform lane (slot + 142..172 ps vs 123 ps) -- see the per-link tables. Honest reading: on this node the wave carries narrow-fanout, uniform-depth logic (hash/XOR/CRC class) at 1 result per 276 ps per lane; arithmetic with reconvergent fanout does not map without a load-aware synthesis step that was not pre-registered and is not measured here.

* **crc32_d2_tt92_rl_nw8** (last(level-order rule)): 1450 gates (1392 nand2 + 58 delay inverters), 5684 FETs, 6 banks; **FAIL** -- 2910/2910 boundary bits correct at every bank on every scored wave, final word == software reference on 6/6 words; worst commit margin -218.1 mV (budget 69.924), worst handoff overlap -17.95 ps, min link eye 79.6 ps, standing eye 97.65 ps, erosion ERODES_SLOW/SUSTAINS. Latency 572.4..597.0 ps (first input edge -> final word committed; 598.1 ps at the 69.924 mV gate), throughput **1 result / 276 ps = 3.623 G/s per lane** (a new word launched every period, 6/6 landed correct).
* **mul8x8_d2_tt92_rl_nw8** (last(level-order rule)): 2626 gates (1130 nand2 + 1366 delay inverters), 7512 FETs, 18 banks; **FAIL** -- 2962/3043 boundary bits correct at every bank on every scored wave, final word == software reference on 1/6 words; worst commit margin -595.1 mV (budget 69.924), worst handoff overlap -38.54 ps, min link eye 20.1 ps, standing eye 102.69 ps, erosion EXTINCT. Latency 1670.3..1670.3 ps (first input edge -> final word committed; 1672.4 ps at the 69.924 mV gate), throughput **1 result / 276 ps = 3.623 G/s per lane** (a new word launched every period, 1/6 landed correct).
* **crc32_d2_tt92** (first(committed)): 1421 gates (1392 nand2 + 29 delay inverters), 5626 FETs, 6 banks; **FAIL** -- 10161/10177 boundary bits correct at every bank on every scored wave, final word == software reference on 22/22 words; worst commit margin -350.4 mV (budget 69.924), worst handoff overlap -30.11 ps, min link eye 28.7 ps, standing eye 86.72 ps, erosion ERODES/ERODES_SLOW/SUSTAINS. Latency 553.0..618.6 ps (first input edge -> final word committed; 622.3 ps at the 69.924 mV gate), throughput **1 result / 276 ps = 3.623 G/s per lane** (a new word launched every period, 22/22 landed correct).
* **mul8x8_d2_tt92** (first(committed)): 1918 gates (1130 nand2 + 658 delay inverters), 6096 FETs, 13 banks; **FAIL** -- 6491/6730 boundary bits correct at every bank on every scored wave, final word == software reference on 0/22 words; worst commit margin -457.6 mV (budget 69.924), worst handoff overlap -65.16 ps, min link eye 4.4 ps, standing eye 69.52 ps, erosion EXTINCT. Latency n/a..n/a ps (first input edge -> final word committed; n/a ps at the 69.924 mV gate), throughput **1 result / 276 ps = 3.623 G/s per lane** (a new word launched every period, 0/22 landed correct).

Other T_third rows (committed rule, nw = 24): CRC d=2 at 117 ps: value PASS (0/10670 bits, 22/22 words), B/C FAIL (margin -49 mV, overlap -73 ps at link 2); CRC d=3 at 150 ps EXTINCT; multiplier d=2 at 117 and 150 ps and d=3 at 165 ps EXTINCT (final word right on 2/22, 0/22, 0/22) -- a longer third does not help a load/order failure, as the mechanism predicts.

### Falsified: d = 3 nand2 levels per bank at 92 ps (the pre-registered point)

* crc32 (d=3): FAIL -- 87 boundary-bit failures (incl. bank-waves with NO commit inside the bank's own powered window), final word matched the reference on 1/22 words; bank 1 (3 nand2 levels from the ideal head) commits at slot + (no commit in its own powered window; gated eye opens ~slot+200) ps (inverter d=3 anchor: slot + 110..117) with a 26.9 ps minimum eye; bank 2 therefore sees its inputs valid only during its hold third and cannot resolve 3 more nand2 levels before they die on bank 1's fall -- every downstream bank is garbage (link margins at the receiver crest around -1 V). Measured tracking lag 171.4..0.0 ps vs 77..82 for the inverter bank. The committed rule 'synthesize for worst-cell traversal time, not count' is exactly this: the nand2 level in the wave is ~1.6x the inverter level (same ratio as the CMOS chains: 83.5/52.5 at 1.2 V).
  Xyce on the same deck (6 periods): the same failure (final words identical on both engines: True; worst commit-instant difference 0.00 ps, eye-width difference 0.76 ps on the links that commit).
* mul8x8 (d=3): FAIL -- 188 boundary-bit failures (incl. bank-waves with NO commit inside the bank's own powered window), final word matched the reference on 0/22 words; bank 1 (3 nand2 levels from the ideal head) commits at slot + 179.9 ps (inverter d=3 anchor: slot + 110..117) with a 22.8 ps minimum eye; bank 2 therefore sees its inputs valid only during its hold third and cannot resolve 3 more nand2 levels before they die on bank 1's fall -- every downstream bank is garbage (link margins at the receiver crest around -1 V). Measured tracking lag 171.0..0.0 ps vs 77..82 for the inverter bank. The committed rule 'synthesize for worst-cell traversal time, not count' is exactly this: the nand2 level in the wave is ~1.6x the inverter level (same ratio as the CMOS chains: 83.5/52.5 at 1.2 V).

### nand2 cell-class calibration lanes (mesh3 harness, 8 nand2(x,x) chains x 6 banks, P0-alt, VACASK)

| d levels/bank (fanout = consumers per node) | T_third ps | period ps | A value | B eye (>=69.9 mV) | C handoff | worst margin mV | worst overlap ps | min eye ps | commit - slot (bank 2) ps | lag ps | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 (fanout 1) | 92 | 276 | True | False | False | -114.7 | -10.19 | 79.4 | 95.0 | 21.2..49.5 | **FAIL** |
| 1 (fanout 1) | 105 | 315 | True | False | False | -244.8 | -41.83 | 77.4 | 106.6 | 22.0..55.6 | **FAIL** |
| 1 (fanout 1) | 117 | 351 | False | False | False | -323.4 | -35.35 | 76.0 | 117.8 | 22.7..182.0 | **FAIL** |
| 2 (fanout 1) | 92 | 276 | True | True | True | 356.1 | 24.07 | 113.7 | 123.4 | 38.3..56.8 | **PASS** |
| 2 (fanout 1) | 105 | 315 | True | True | True | 458.0 | 34.34 | 136.4 | 133.7 | 37.4..57.8 | **PASS** |
| 2 (fanout 1) | 117 | 351 | True | True | True | 552.7 | 46.08 | 157.5 | 140.6 | 36.8..59.1 | **PASS** |
| 2 (fanout 2) | 92 | 276 | True | True | True | 210.2 | 16.15 | 100.7 | 131.6 | 64.4..88.3 | **PASS** |
| 2 (fanout 2) | 117 | 351 | True | True | True | 429.4 | 37.77 | 145.7 | 150.9 | 49.5..84.9 | **PASS** |
| 2 (fanout 4) | 92 | 276 | False | False | True | n/a | n/a | 108.9 | n/a | 103.3..103.9 | **FAIL** |
| 2 (fanout 4) | 117 | 351 | False | False | True | 281.8 | 30.14 | 160.8 | 171.8 | 115.7..174.1 | **FAIL** |
| 3 (fanout 1) | 92 | 276 | False | False | False | -1231.4 | -32.76 | 31.7 | 166.8 | 8.2..134.2 | **FAIL** |
| 3 (fanout 1) | 105 | 315 | True | False | False | -237.4 | -18.72 | 92.6 | 165.9 | 9.1..127.8 | **FAIL** |
| 3 (fanout 1) | 117 | 351 | True | True | True | 206.6 | 17.04 | 134.0 | 168.2 | 80.7..95.2 | **PASS** |
| 3 (fanout 1) | 130 | 390 | True | True | True | 351.9 | 31.83 | 161.8 | 173.1 | 67.3..97.7 | **PASS** |

Reading: the nand2 bank's commit instant moves ~+45 ps per added level; at 92 ps the receiver's rise third can absorb two levels, not three. d=1 fails on handoff (negative overlap at link 5: the input-death channel mesh3 pre-identified for shallow banks).

CMOS comparator (same nand2/inv netlist, registers every D levels): period = D*t_level + t_reg with **t_level(nand2, 2 fF) = 83.54 ps @1.2 V (campaign comparator supply; inverter 52.51 reproduced) / 47.74 ps @1.65 V (iso-voltage, MEASURED here)**, t_reg(2 fF) = 315.378 ps DERIVED (lower bound). OpenSTA on the actual netlist (vendor liberty, real fanout) alongside.

**Where the win lives:** results/s per lane (no register tax in the period: 276 ps vs D*t_level + t_reg) and end-to-end latency vs *registered* CMOS at every D (the single flop tax, 315 ps, is comparable to the wave's whole bank-to-bank step). It is NOT a per-level latency win against the bare unregistered chain at iso-voltage -- see the bare-chain rows. Per-bank initiation interval (276 ps) is never conflated with the wavefront level-rate (d levels per 92 ps).

## Block crc32_d2_tt92_rl_nw8 (d=2, T_third=92 ps, last(level-order rule))

Structure: 32 dual-rail nand2 XOR trees (24..34 terms each, leaves at XOR-depth D or D-1 only), 4 groups of 8 trees simulated separately (electrical union, PRE_REGISTERED). NB = 6 banks, logic nand-levels L = 12, 58 delay inverters (bank-alignment tax, real devices). Boundary signals scored per bank: {}.

| link k (bank k -> k+1) | eye 0 mV min..max (ps) | commit_raw - slot (ps) | overlap min (ps) | margin at commit min (mV) | receiver |
|---|---|---|---|---|---|
| 1 | 100.6..101.3 | 142.2..142.9 | -0.66 | -8.3 | real (bank k+1 rail) |
| 2 | 106.0..111.6 | 148.7..152.1 | 4.39 | 50.2 | real (bank k+1 rail) |
| 3 | 83.1..89.3 | 155.3..161.7 | -17.95 | -218.1 | real (bank k+1 rail) |
| 4 | 86.3..114.0 | 143.1..170.8 | 0.80 | 9.0 | real (bank k+1 rail) |
| 5 | 79.6..111.4 | 133.1..165.5 | 16.09 | 220.7 | real (bank k+1 rail) |
| 6 | 107.4..131.8 | 112.4..137.0 | n/a | n/a | DERIVED ideal next-phase rail |

Rising-side tracking lag (last boundary HIGH 50% after own rail 50%): 9.4..91.7 ps. Latency per word (raw commit): 572.4..597.0 ps; at the 69.924 mV gate: 598.1 ps max.

Per-bank rail books (REPORTED, not gated; offline trapezoid on the engine grid, mean over scored waves, SUMMED over the 4 groups):

| bank | phase | Q_rise fC | Q_hold fC | Q_fall fC | E_rise fJ | E_hold fJ | E_fall fJ |
|---|---|---|---|---|---|---|---|
| 1 | A | 8260.2 | 1814.2 | -7863.4 | 7641.5 | 2993.3 | -6268.5 |
| 2 | B | 3441.8 | 1979.4 | -3660.3 | 3368.0 | 3265.9 | -2859.8 |
| 3 | C | 1814.0 | 995.5 | -2033.3 | 1796.8 | 1642.6 | -1592.9 |
| 4 | A | 931.4 | 565.6 | -1008.7 | 916.4 | 933.3 | -795.8 |
| 5 | B | 458.3 | 282.2 | -522.6 | 461.3 | 465.7 | -413.8 |
| 6 | C | 139.6 | 78.9 | -133.8 | 142.2 | 130.2 | -105.0 |

Net rail energy per result (sum of thirds over all banks, ideal-source convention, fall third recovers): **11721.3 fJ/result** (ideal mesh; the measured flat-top driver price of qal/meshdrv, 2.2x, applies on top). Delay inverters are inside these books.

### CMOS comparison, crc32

QAL: 3.623 G results/s per lane (period 276 ps), latency 597.0 ps (max over words), 6 banks.

**Formula comparator, t_level = 83.54 ps (nand2_1.2V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 566.0 (666.0) | 1.767 (1.501) | 2264.0 (2664.0) | 2.05x (2.41x) | 3.79x |
| 6 | 2 | 816.6 (916.6) | 1.225 (1.091) | 1633.2 (1833.2) | 2.96x (3.32x) | 2.74x |
| 9 | 2 | 1067.2 (1167.2) | 0.937 (0.857) | 2134.5 (2334.5) | 3.87x (4.23x) | 3.58x |
| 12 | 1 | 1317.9 (1417.9) | 0.759 (0.705) | 1317.9 (1417.9) | 4.77x (5.14x) | 2.21x |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **1002.5 ps**; bare-chain / QAL latency = **1.679x** (QAL is faster end-to-end than the bare chain).

**Formula comparator, t_level = 47.74 ps (nand2_1.65V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 458.6 (558.6) | 2.181 (1.790) | 1834.4 (2234.4) | 1.66x (2.02x) | 3.07x |
| 6 | 2 | 601.8 (701.8) | 1.662 (1.425) | 1203.6 (1403.6) | 2.18x (2.54x) | 2.02x |
| 9 | 2 | 745.0 (845.0) | 1.342 (1.183) | 1490.0 (1690.0) | 2.70x (3.06x) | 2.50x |
| 12 | 1 | 888.2 (988.2) | 1.126 (1.012) | 888.2 (988.2) | 3.22x (3.58x) | 1.49x |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **572.8 ps**; bare-chain / QAL latency = **0.960x** (QAL is slower end-to-end than the bare chain).

**OpenSTA, liberty typ_1p20V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 953.2 (499.2) | 1.049 | 3812.8 | 3.45x | 6.39x |
| 6 | 2 | 1100.5 (631.5) | 0.909 | 2201.0 | 3.99x | 3.69x |
| 9 | 2 | 1253.0 (485.2) | 0.798 | 2506.0 | 4.54x | 4.20x |
| 12 | 1 | 1297.8 (n/a) | 0.771 | 1297.8 | 4.70x | 2.17x |

**OpenSTA, liberty typ_1p50V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 647.1 (327.5) | 1.545 | 2588.4 | 2.34x | 4.34x |
| 6 | 2 | 741.8 (418.0) | 1.348 | 1483.6 | 2.69x | 2.49x |
| 9 | 2 | 844.3 (318.9) | 1.184 | 1688.6 | 3.06x | 2.83x |
| 12 | 1 | 874.6 (n/a) | 1.143 | 874.6 | 3.17x | 1.46x |

**OpenSTA, liberty fast_1p65V_m40C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 457.6 (230.0) | 2.185 | 1830.4 | 1.66x | 3.07x |
| 6 | 2 | 531.3 (301.1) | 1.882 | 1062.6 | 1.93x | 1.78x |
| 9 | 2 | 600.0 (226.4) | 1.667 | 1200.0 | 2.17x | 2.01x |
| 12 | 1 | 627.1 (n/a) | 1.595 | 627.1 | 2.27x | 1.05x |

### Engine agreement, crc32 (Xyce anchor = same deck, first 6 periods, waves n/a)

Xyce anchor not available (see RESULTS.json other_runs).

## Block mul8x8_d2_tt92_rl_nw8 (d=2, T_third=92 ps, last(level-order rule))

Structure: AND array (nand2+inv, dual-rail) -> Dadda CSA tree of 16-nand2 dual-rail full adders (depth 4) -> radix-2 Kogge-Stone (nand2/inv, polarity tracked). NB = 18 banks, logic nand-levels L = 26, 1366 delay inverters (bank-alignment tax, real devices). Boundary signals scored per bank: {"1": 167, "2": 127, "3": 118, "4": 129, "5": 117, "6": 102, "7": 91, "8": 90, "9": 84, "10": 93, "11": 98, "12": 96, "13": 80, "14": 52, "15": 40, "16": 29, "17": 20, "18": 16}.

| link k (bank k -> k+1) | eye 0 mV min..max (ps) | commit_raw - slot (ps) | overlap min (ps) | margin at commit min (mV) | receiver |
|---|---|---|---|---|---|
| 1 | 64.7..81.4 | 157.1..172.8 | -24.18 | -325.9 | real (bank k+1 rail) |
| 2 | 30.4..109.7 | 132.1..169.6 | -28.62 | -349.6 | real (bank k+1 rail) |
| 3 | 56.9..89.9 | 146.7..179.4 | -11.43 | -169.4 | real (bank k+1 rail) |
| 4 | 29.9..85.0 | 152.9..156.4 | n/a | -396.3 | real (bank k+1 rail) |
| 5 | 25.0..61.6 | 176.2..176.2 | -38.54 | -478.1 | real (bank k+1 rail) |
| 6 | 54.1..54.1 | 183.8..183.8 | -32.99 | -399.8 | real (bank k+1 rail) |
| 7 | 20.1..20.1 | 178.9..178.9 | n/a | n/a | real (bank k+1 rail) |
| 8 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 9 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 10 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 11 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 12 | n/a..n/a | n/a..n/a | n/a | -595.1 | real (bank k+1 rail) |
| 13 | 65.4..65.4 | 172.1..172.1 | 37.28 | 139.6 | real (bank k+1 rail) |
| 14 | 130.4..130.4 | 108.3..108.3 | 24.83 | 253.0 | real (bank k+1 rail) |
| 15 | 116.5..116.5 | 121.8..121.8 | 22.34 | 222.9 | real (bank k+1 rail) |
| 16 | 121.0..121.0 | 123.9..123.9 | 28.79 | 287.8 | real (bank k+1 rail) |
| 17 | 117.1..117.1 | 124.2..124.2 | 42.93 | 300.0 | real (bank k+1 rail) |
| 18 | 83.0..83.0 | 106.3..106.3 | n/a | n/a | DERIVED ideal next-phase rail |

Rising-side tracking lag (last boundary HIGH 50% after own rail 50%): 20.8..141.2 ps. Latency per word (raw commit): 1670.3..1670.3 ps; at the 69.924 mV gate: 1672.4 ps max.

Per-bank rail books (REPORTED, not gated; offline trapezoid on the engine grid, mean over scored waves):

| bank | phase | Q_rise fC | Q_hold fC | Q_fall fC | E_rise fJ | E_hold fJ | E_fall fJ |
|---|---|---|---|---|---|---|---|
| 1 | A | 1718.5 | 543.8 | -1627.4 | 1635.7 | 897.3 | -1274.2 |
| 2 | B | 2173.9 | 936.4 | -2348.3 | 2145.2 | 1545.1 | -1838.3 |
| 3 | C | 2069.5 | 956.1 | -2277.4 | 2068.2 | 1577.5 | -1774.7 |
| 4 | A | 1775.1 | 880.7 | -1840.1 | 1769.7 | 1453.1 | -1403.3 |
| 5 | B | 1618.3 | 780.1 | -1608.8 | 1603.3 | 1287.1 | -1213.7 |
| 6 | C | 1441.7 | 682.5 | -1407.5 | 1426.7 | 1126.2 | -1054.9 |
| 7 | A | 1315.5 | 591.4 | -1318.8 | 1301.2 | 975.8 | -996.3 |
| 8 | B | 1199.3 | 531.9 | -1163.0 | 1181.0 | 877.6 | -878.6 |
| 9 | C | 1151.6 | 519.8 | -1146.2 | 1132.1 | 857.6 | -865.5 |
| 10 | A | 1164.6 | 546.3 | -1160.3 | 1139.4 | 901.3 | -876.2 |
| 11 | B | 1182.7 | 524.7 | -1207.8 | 1169.0 | 865.7 | -932.1 |
| 12 | C | 1250.7 | 482.7 | -1261.0 | 1246.9 | 796.4 | -974.0 |
| 13 | A | 1170.3 | 454.2 | -1148.3 | 1160.0 | 749.5 | -876.6 |
| 14 | B | 850.1 | 330.5 | -818.7 | 824.6 | 545.3 | -623.8 |
| 15 | C | 533.8 | 201.5 | -535.4 | 519.8 | 332.4 | -417.1 |
| 16 | A | 423.6 | 158.7 | -415.4 | 416.7 | 261.9 | -325.7 |
| 17 | B | 326.2 | 130.6 | -307.3 | 321.1 | 215.6 | -236.8 |
| 18 | C | 181.4 | 73.9 | -174.2 | 175.2 | 121.9 | -134.4 |

Net rail energy per result (sum of thirds over all banks, ideal-source convention, fall third recovers): **19927.0 fJ/result** (ideal mesh; the measured flat-top driver price of qal/meshdrv, 2.2x, applies on top). Delay inverters are inside these books.

### CMOS comparison, mul8x8

QAL: 3.623 G results/s per lane (period 276 ps), latency 1670.3 ps (max over words), 18 banks.

**Formula comparator, t_level = 83.54 ps (nand2_1.2V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 566.0 (666.0) | 1.767 (1.501) | 5094.0 (5994.0) | 2.05x (2.41x) | 3.05x |
| 6 | 5 | 816.6 (916.6) | 1.225 (1.091) | 4083.1 (4583.1) | 2.96x (3.32x) | 2.44x |
| 9 | 3 | 1067.2 (1167.2) | 0.937 (0.857) | 3201.7 (3501.7) | 3.87x (4.23x) | 1.92x |
| 26 | 1 | 2487.4 (2587.4) | 0.402 (0.386) | 2487.4 (2587.4) | 9.01x (9.37x) | 1.49x |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **2172.1 ps**; bare-chain / QAL latency = **1.300x** (QAL is faster end-to-end than the bare chain).

**Formula comparator, t_level = 47.74 ps (nand2_1.65V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 458.6 (558.6) | 2.181 (1.790) | 4127.3 (5027.3) | 1.66x (2.02x) | 2.47x |
| 6 | 5 | 601.8 (701.8) | 1.662 (1.425) | 3009.0 (3509.0) | 2.18x (2.54x) | 1.80x |
| 9 | 3 | 745.0 (845.0) | 1.342 (1.183) | 2235.0 (2535.0) | 2.70x (3.06x) | 1.34x |
| 26 | 1 | 1556.5 (1656.5) | 0.642 (0.604) | 1556.5 (1656.5) | 5.64x (6.00x) | 0.93x |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **1241.2 ps**; bare-chain / QAL latency = **0.743x** (QAL is slower end-to-end than the bare chain).

**OpenSTA, liberty typ_1p20V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 659.6 (558.7) | 1.516 | 5936.4 | 2.39x | 3.55x |
| 6 | 5 | 856.4 (771.7) | 1.168 | 4282.0 | 3.10x | 2.56x |
| 9 | 3 | 1061.6 (953.8) | 0.942 | 3184.8 | 3.85x | 1.91x |
| 26 | 1 | 2088.5 (n/a) | 0.479 | 2088.5 | 7.57x | 1.25x |

**OpenSTA, liberty typ_1p50V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 434.0 (365.6) | 2.304 | 3906.0 | 1.57x | 2.34x |
| 6 | 5 | 564.4 (508.3) | 1.772 | 2822.0 | 2.04x | 1.69x |
| 9 | 3 | 699.9 (627.6) | 1.429 | 2099.7 | 2.54x | 1.26x |
| 26 | 1 | 1386.3 (n/a) | 0.721 | 1386.3 | 5.02x | 0.83x |

**OpenSTA, liberty fast_1p65V_m40C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 305.5 (260.1) | 3.273 | 2749.5 | 1.11x | 1.65x |
| 6 | 5 | 404.7 (367.2) | 2.471 | 2023.5 | 1.47x | 1.21x |
| 9 | 3 | 494.8 (452.2) | 2.021 | 1484.4 | 1.79x | 0.89x |
| 26 | 1 | 1006.2 (n/a) | 0.994 | 1006.2 | 3.65x | 0.60x |

### Engine agreement, mul8x8 (Xyce anchor = same deck, first 6 periods, waves n/a)

Xyce anchor not available (see RESULTS.json other_runs).

## Block crc32_d2_tt92 (d=2, T_third=92 ps, first(committed))

Structure: 32 dual-rail nand2 XOR trees (24..34 terms each, leaves at XOR-depth D or D-1 only), 4 groups of 8 trees simulated separately (electrical union, PRE_REGISTERED). NB = 6 banks, logic nand-levels L = 12, 29 delay inverters (bank-alignment tax, real devices). Boundary signals scored per bank: {}.

| link k (bank k -> k+1) | eye 0 mV min..max (ps) | commit_raw - slot (ps) | overlap min (ps) | margin at commit min (mV) | receiver |
|---|---|---|---|---|---|
| 1 | 100.7..101.5 | 142.2..143.0 | -1.32 | -16.7 | real (bank k+1 rail) |
| 2 | 103.0..109.8 | 146.2..153.0 | -18.64 | -174.3 | real (bank k+1 rail) |
| 3 | 59.9..94.9 | 150.0..182.6 | -30.11 | -350.4 | real (bank k+1 rail) |
| 4 | 56.2..112.0 | 143.1..182.8 | -16.41 | -182.8 | real (bank k+1 rail) |
| 5 | 28.7..106.3 | 139.0..181.6 | -5.65 | -202.0 | real (bank k+1 rail) |
| 6 | 80.9..136.8 | 93.0..158.6 | n/a | n/a | DERIVED ideal next-phase rail |

Rising-side tracking lag (last boundary HIGH 50% after own rail 50%): 9.0..119.1 ps. Latency per word (raw commit): 553.0..618.6 ps; at the 69.924 mV gate: 622.3 ps max.

Per-bank rail books (REPORTED, not gated; offline trapezoid on the engine grid, mean over scored waves, SUMMED over the 4 groups):

| bank | phase | Q_rise fC | Q_hold fC | Q_fall fC | E_rise fJ | E_hold fJ | E_fall fJ |
|---|---|---|---|---|---|---|---|
| 1 | A | 8293.9 | 1887.7 | -7822.5 | 7677.3 | 3114.7 | -6265.3 |
| 2 | B | 3365.1 | 1923.0 | -3595.1 | 3285.7 | 3172.8 | -2808.1 |
| 3 | C | 1746.3 | 969.8 | -1968.9 | 1718.9 | 1600.2 | -1541.4 |
| 4 | A | 908.2 | 565.1 | -993.1 | 891.6 | 932.4 | -783.3 |
| 5 | B | 434.5 | 280.7 | -499.4 | 435.3 | 463.1 | -394.0 |
| 6 | C | 91.2 | 62.1 | -97.3 | 90.3 | 102.5 | -77.1 |

Net rail energy per result (sum of thirds over all banks, ideal-source convention, fall third recovers): **11615.5 fJ/result** (ideal mesh; the measured flat-top driver price of qal/meshdrv, 2.2x, applies on top). Delay inverters are inside these books.

### CMOS comparison, crc32

QAL: 3.623 G results/s per lane (period 276 ps), latency 618.6 ps (max over words), 6 banks.

**Formula comparator, t_level = 83.54 ps (nand2_1.2V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 566.0 (666.0) | 1.767 (1.501) | 2264.0 (2664.0) | 2.05x (2.41x) | 3.66x |
| 6 | 2 | 816.6 (916.6) | 1.225 (1.091) | 1633.2 (1833.2) | 2.96x (3.32x) | 2.64x |
| 9 | 2 | 1067.2 (1167.2) | 0.937 (0.857) | 2134.5 (2334.5) | 3.87x (4.23x) | 3.45x |
| 12 | 1 | 1317.9 (1417.9) | 0.759 (0.705) | 1317.9 (1417.9) | 4.77x (5.14x) | 2.13x |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **1002.5 ps**; bare-chain / QAL latency = **1.621x** (QAL is faster end-to-end than the bare chain).

**Formula comparator, t_level = 47.74 ps (nand2_1.65V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 458.6 (558.6) | 2.181 (1.790) | 1834.4 (2234.4) | 1.66x (2.02x) | 2.97x |
| 6 | 2 | 601.8 (701.8) | 1.662 (1.425) | 1203.6 (1403.6) | 2.18x (2.54x) | 1.95x |
| 9 | 2 | 745.0 (845.0) | 1.342 (1.183) | 1490.0 (1690.0) | 2.70x (3.06x) | 2.41x |
| 12 | 1 | 888.2 (988.2) | 1.126 (1.012) | 888.2 (988.2) | 3.22x (3.58x) | 1.44x |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **572.8 ps**; bare-chain / QAL latency = **0.926x** (QAL is slower end-to-end than the bare chain).

**OpenSTA, liberty typ_1p20V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 953.2 (499.2) | 1.049 | 3812.8 | 3.45x | 6.16x |
| 6 | 2 | 1100.5 (631.5) | 0.909 | 2201.0 | 3.99x | 3.56x |
| 9 | 2 | 1253.0 (485.2) | 0.798 | 2506.0 | 4.54x | 4.05x |
| 12 | 1 | 1297.8 (n/a) | 0.771 | 1297.8 | 4.70x | 2.10x |

**OpenSTA, liberty typ_1p50V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 647.1 (327.5) | 1.545 | 2588.4 | 2.34x | 4.18x |
| 6 | 2 | 741.8 (418.0) | 1.348 | 1483.6 | 2.69x | 2.40x |
| 9 | 2 | 844.3 (318.9) | 1.184 | 1688.6 | 3.06x | 2.73x |
| 12 | 1 | 874.6 (n/a) | 1.143 | 874.6 | 3.17x | 1.41x |

**OpenSTA, liberty fast_1p65V_m40C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 4 | 457.6 (230.0) | 2.185 | 1830.4 | 1.66x | 2.96x |
| 6 | 2 | 531.3 (301.1) | 1.882 | 1062.6 | 1.93x | 1.72x |
| 9 | 2 | 600.0 (226.4) | 1.667 | 1200.0 | 2.17x | 1.94x |
| 12 | 1 | 627.1 (n/a) | 1.595 | 627.1 | 2.27x | 1.01x |

### Engine agreement, crc32 (Xyce anchor = same deck, first 6 periods, waves [2, 3, 4, 5])

| quantity | worst |Δ| over links x waves | band | verdict |
|---|---|---|---|
| commit_ps | 1.5250 | 1.0 | OUTSIDE |
| eye_ps | 1.7900 | 1.0 | OUTSIDE |
| margin_rel | 0.7538 | 0.01 | OUTSIDE |
| Q_rel | 0.0315 | 0.02 | OUTSIDE |

Final hardware words identical on both engines: True. Q_rise per bank VACASK [8293.902, 3365.083, 1746.265, 908.192, 434.533, 91.204] vs Xyce [8265.709, 3366.525, 1753.559, 907.064, 434.463, 94.17] fC. Wall: VACASK 2604.9 s / 36784 pts (24 words) vs Xyce 2968.2 s / 11365 pts (6 periods).

## Block mul8x8_d2_tt92 (d=2, T_third=92 ps, first(committed))

Structure: AND array (nand2+inv, dual-rail) -> Dadda CSA tree of 16-nand2 dual-rail full adders (depth 4) -> radix-2 Kogge-Stone (nand2/inv, polarity tracked). NB = 13 banks, logic nand-levels L = 26, 658 delay inverters (bank-alignment tax, real devices). Boundary signals scored per bank: {"1": 168, "2": 130, "3": 102, "4": 92, "5": 79, "6": 78, "7": 70, "8": 79, "9": 85, "10": 80, "11": 63, "12": 31, "13": 16}.

| link k (bank k -> k+1) | eye 0 mV min..max (ps) | commit_raw - slot (ps) | overlap min (ps) | margin at commit min (mV) | receiver |
|---|---|---|---|---|---|
| 1 | 62.2..81.4 | 157.1..177.6 | -28.53 | -373.2 | real (bank k+1 rail) |
| 2 | 8.7..103.8 | 132.1..174.0 | -33.12 | -457.6 | real (bank k+1 rail) |
| 3 | 4.4..74.2 | 147.9..176.9 | -65.16 | -381.4 | real (bank k+1 rail) |
| 4 | 61.2..74.4 | 166.2..175.9 | n/a | n/a | real (bank k+1 rail) |
| 5 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 6 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 7 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 8 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 9 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 10 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 11 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 12 | n/a..n/a | n/a..n/a | n/a | n/a | real (bank k+1 rail) |
| 13 | n/a..n/a | n/a..n/a | n/a | n/a | DERIVED ideal next-phase rail |

Rising-side tracking lag (last boundary HIGH 50% after own rail 50%): 9.9..152.2 ps. Latency per word (raw commit): n/a..n/a ps; at the 69.924 mV gate: n/a ps max.

Per-bank rail books (REPORTED, not gated; offline trapezoid on the engine grid, mean over scored waves):

| bank | phase | Q_rise fC | Q_hold fC | Q_fall fC | E_rise fJ | E_hold fJ | E_fall fJ |
|---|---|---|---|---|---|---|---|
| 1 | A | 1798.7 | 634.3 | -1695.8 | 1721.5 | 1046.6 | -1314.5 |
| 2 | B | 2182.1 | 1036.6 | -2294.4 | 2165.6 | 1710.3 | -1764.2 |
| 3 | C | 1942.4 | 1041.2 | -2104.2 | 1895.6 | 1718.0 | -1612.4 |
| 4 | A | 1564.1 | 966.1 | -1698.1 | 1498.3 | 1594.0 | -1305.1 |
| 5 | B | 1300.9 | 796.9 | -1424.6 | 1258.9 | 1314.8 | -1085.0 |
| 6 | C | 1143.6 | 659.7 | -1248.1 | 1102.0 | 1088.6 | -952.5 |
| 7 | A | 1077.5 | 576.9 | -1152.2 | 1040.1 | 951.9 | -882.1 |
| 8 | B | 1089.1 | 538.6 | -1142.3 | 1061.3 | 888.7 | -881.6 |
| 9 | C | 1098.0 | 521.2 | -1153.9 | 1084.4 | 860.0 | -889.4 |
| 10 | A | 1115.8 | 473.7 | -1143.0 | 1098.3 | 781.6 | -886.6 |
| 11 | B | 957.1 | 385.1 | -990.3 | 943.0 | 635.4 | -769.3 |
| 12 | C | 620.4 | 249.5 | -644.1 | 602.5 | 411.7 | -502.5 |
| 13 | A | 248.5 | 110.3 | -255.3 | 238.0 | 182.0 | -202.2 |

Net rail energy per result (sum of thirds over all banks, ideal-source convention, fall third recovers): **15845.7 fJ/result** (ideal mesh; the measured flat-top driver price of qal/meshdrv, 2.2x, applies on top). Delay inverters are inside these books.

### CMOS comparison, mul8x8

QAL: 3.623 G results/s per lane (period 276 ps), latency n/a ps (max over words), 13 banks.

**Formula comparator, t_level = 83.54 ps (nand2_1.2V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 566.0 (666.0) | 1.767 (1.501) | 5094.0 (5994.0) | 2.05x (2.41x) | n/ax |
| 6 | 5 | 816.6 (916.6) | 1.225 (1.091) | 4083.1 (4583.1) | 2.96x (3.32x) | n/ax |
| 9 | 3 | 1067.2 (1167.2) | 0.937 (0.857) | 3201.7 (3501.7) | 3.87x (4.23x) | n/ax |
| 26 | 1 | 2487.4 (2587.4) | 0.402 (0.386) | 2487.4 (2587.4) | 9.01x (9.37x) | n/ax |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **2172.1 ps**; bare-chain / QAL latency = **n/ax** (QAL is faster end-to-end than the bare chain).

**Formula comparator, t_level = 47.74 ps (nand2_1.65V), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):

| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 458.6 (558.6) | 2.181 (1.790) | 4127.3 (5027.3) | 1.66x (2.02x) | n/ax |
| 6 | 5 | 601.8 (701.8) | 1.662 (1.425) | 3009.0 (3509.0) | 2.18x (2.54x) | n/ax |
| 9 | 3 | 745.0 (845.0) | 1.342 (1.183) | 2235.0 (2535.0) | 2.70x (3.06x) | n/ax |
| 26 | 1 | 1556.5 (1656.5) | 0.642 (0.604) | 1556.5 (1656.5) | 5.64x (6.00x) | n/ax |

Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **1241.2 ps**; bare-chain / QAL latency = **n/ax** (QAL is faster end-to-end than the bare chain).

**OpenSTA, liberty typ_1p20V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 659.6 (558.7) | 1.516 | 5936.4 | 2.39x | n/ax |
| 6 | 5 | 856.4 (771.7) | 1.168 | 4282.0 | 3.10x | n/ax |
| 9 | 3 | 1061.6 (953.8) | 0.942 | 3184.8 | 3.85x | n/ax |
| 26 | 1 | 2088.5 (n/a) | 0.479 | 2088.5 | 7.57x | n/ax |

**OpenSTA, liberty typ_1p50V_25C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 434.0 (365.6) | 2.304 | 3906.0 | 1.57x | n/ax |
| 6 | 5 | 564.4 (508.3) | 1.772 | 2822.0 | 2.04x | n/ax |
| 9 | 3 | 699.9 (627.6) | 1.429 | 2099.7 | 2.54x | n/ax |
| 26 | 1 | 1386.3 (n/a) | 0.721 | 1386.3 | 5.02x | n/ax |

**OpenSTA, liberty fast_1p65V_m40C** (real fanout incl. head; head-free in parentheses = false-path from the input registers):

| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |
|---|---|---|---|---|---|---|
| 3 | 9 | 305.5 (260.1) | 3.273 | 2749.5 | 1.11x | n/ax |
| 6 | 5 | 404.7 (367.2) | 2.471 | 2023.5 | 1.47x | n/ax |
| 9 | 3 | 494.8 (452.2) | 2.021 | 1484.4 | 1.79x | n/ax |
| 26 | 1 | 1006.2 (n/a) | 0.994 | 1006.2 | 3.65x | n/ax |

### Engine agreement, mul8x8 (Xyce anchor = same deck, first 6 periods, waves n/a)

Xyce anchor not available (see RESULTS.json other_runs).

## Cells, level measurement, harness anchor

* nand2 = sg13g2_nand2_1 vendor sizing VERBATIM (= campaign inverter widths): 2x pMOS 1.12u parallel, 2x nMOS 0.74u series, l 0.13u, CL 2 fF; stack depth 2 (shallow). XOR2 = dual-rail depth-2 nand2 form (6 nand2) -- the single-rail 4-nand2 XOR is depth THREE, the vendor xor2_1 has a 2-high pMOS stack (excluded by the shallow rule), the pass-gate XOR is banned.
* CMOS per-level delay, depth-12 chain @2 fF, (t10 - t4)/6 at VDD/2 (fcrit_skept arm-D method), MEASURED:

| VDD | nand2 both inputs | nand2 one input tied high | inverter | Xyce (a / b / i) |
|---|---|---|---|---|
| 1.2V | 83.541 | 82.001 | 52.637 | 83.396 / 81.897 / 52.510 |
| 1.65V | 47.242 | 47.737 | 31.872 | 47.137 / 47.649 / 31.770 |

  The inverter at 1.2 V reproduces the committed 52.51 ps digit-exact on Xyce (52.637 on VACASK, +0.24%). The nand2 level is 1.59x the inverter level at 1.2 V and 1.50x at 1.65 V.
* Harness anchor (IC): committed mesh3 `trap_tt92_d3` regenerated by this generator and scored by this extractor on VACASK: value 0/240 fails on waves 2..6 (mesh3: 144 checks, 0 fails); worst margin_at_commit 503.66 vs 509.67 mV (rel 0.0118 -- instantaneous-sample class, OFFSET_TABLE Amendment 2; 1.18%, just outside the 1% band stated for it); worst overlap 36.638 vs 37.021 ps; standing eye 128.64 vs 129.03 ps; commit_raw(bank 2, wave 3) 1037.104 vs 1036.79 ps; Q_rise bank 1 155.04 vs 155.585 fC; rising lag {'min': 77.3, 'max': 81.7, 'median': 81.6} vs {'min': 77.0, 'max': 81.4, 'median': 81.4}. Wall 49.0 s, 11505 pts.

## Riders (stated, not discharged)

* Ideal mesh (BOUND) and ideal head (BOOKED): the head's fanout (CRC inputs fan out to up to 20 trees x 2 polarities) and the head complements are free to the wave; the formula CMOS comparator is given the same free head; the STA comparator is NOT (its input registers drive the real fanout -- the head-free column removes it).
* CRC recurrence: the state feedback is not closed inside the wave; one lane sustains one update per period only with ceil(latency/period) interleaved independent streams (packets/flows). Same for a FIR MAC accumulate.
* The CRC groups are an electrical union (no shared internal node; ideal rails behind 0.001 ohm). Per-bank charges are sums.
* Energy: ideal-source books only; the flat-top driver's measured 2.2x (qal/meshdrv) applies; no energy claim is made.
* Last link scored against the DERIVED ideal next-phase rail (mesh3 convention); interior links are real.

## Files

`PRE_REGISTERED.json` (first file), `mblocks.py` (netlists, levelizer/bank aligner, decks for both engines, numpy port of the mesh3 scorer), `agg.py` -> `RESULTS.json`, `mkreadme.py` -> this file, `IC.json`, `LEVEL.json`, `STA_*.json`, `runs/<tag>/` (deck + log + OUT.json; no waveforms -- raws/prns lived on the scratchpad and were deleted after extraction).
