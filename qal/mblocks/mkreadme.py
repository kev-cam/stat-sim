#!/usr/bin/env python3
"""README.md from RESULTS.json (tables) + the narrative. Run after agg.py."""
import json, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "RESULTS.json")))
PR = json.load(open(os.path.join(HERE, "PRE_REGISTERED.json")))

def f(x, d=1):
    return "n/a" if x is None else ("%.*f" % (d, x) if isinstance(x, (int, float)) else str(x))

L = []
P = L.append
P("# qal/mblocks -- CRC-32 and an array multiplier on the three-phase wave vs pipelined CMOS")
P("")
P("Pre-registered in `PRE_REGISTERED.json` before the first deck (predictions, acceptance, comparator forms).")
P("Simulator: **VACASK 0.3.4 primary** (PSP103 OSDI, kestrel tt cards), **Xyce cross-check** on one anchor row per block.")
P("Wave: the committed `qal/mesh3` point VERBATIM -- ideal three-phase trapezoid (rise/hold/fall thirds), "
  "T_third = 92 ps (period 276 ps), 1.65 V, bank k on phase (k-1) mod 3, outputs direct-wired, no registers, "
  "d = 3 nand-levels per bank as pre-registered (re-mapped to d = 2 after the cell-class calibration, see Verdict). Ideal mesh = BOUND (ASSUMED, standing licence); ideal head = BOOKED (see riders).")
P("Energy is REPORTED, never gated. Model language: tracking lag / eye / margin at the sampling instant.")
P("")
P("## Verdict (all numbers MEASURED unless labelled)")
P("")
P("**Neither block sustains on the three-phase wave at SG13G2 under the pre-registered acceptance, at any T_third tried "
  "(92-165 ps), under either mapping rule.** The pre-registered point (3 nand2 levels per bank at 92 ps) fails by cascade "
  "(falsified, below): the nand2 level is 1.5-1.6x the inverter level, so a bank holds two nand2 levels at 92 ps, not three. "
  "Re-mapped at d = 2 the uniform nand2 calibration lane passes (356 mV margin) but the real blocks do not. Two causes were "
  "isolated on lane experiments, both properties of the wave rather than of the blocks:")
P("")
P("1. **Level order.** A bank's outputs are destroyed by the death of its own inputs one gate delay per level after the "
  "previous bank dies, while the next bank's consumers commit one gate delay per level after their rail rises; the two "
  "rates are equal, so a producer at level-in-bank j may feed a next-bank consumer at level-in-bank i only if j >= i. "
  "The committed alignment rule allowed (1->2) edges (78 in the 8x8 multiplier, 0 in the lane). Rule implemented "
  "(`MB_RETIME=last`, parity-aware inverter-chain retiming; multiplier 13 -> 18 banks, 658 -> 1366 delay inverters). "
  "It removed every value failure from the CRC at 92 ps (0/2910 boundary bits wrong, 6/6 words) but did not rescue the multiplier.")
P("2. **Load.** Fanout lanes (the same nand2(x,x) chain with f identical consumers per node, d = 2): f = 1 passes at 92 ps "
  "(356 mV), f = 2 passes with the margin halved (210 mV, overlap 16 ps, tracking lag 57 -> 85 ps), f = 4 FAILS at 92 and at "
  "117 ps (lag 104-174 ps: the output never reaches the receiver's trip before the hold ends). The multiplier has 302 boundary "
  "signals driving 3-5 gate inputs (FA/HA outputs in the Dadda tree); the CRC has none above 2. The multiplier is extinct "
  "under both rules for this reason; it would need load-limited duplication (every node <= ~4 gate inputs) to be mapped at all.")
P("")
P("The CRC (XOR trees, fanout <= 2) is the only block that computes correctly on the wave at 92 ps; it still misses the "
  "pre-registered B/C gates at one link (margin -218 mV at commit, overlap -18 ps, link 3) because its banks commit "
  "20-40 ps later than the uniform lane (slot + 142..172 ps vs 123 ps, growing ~9 ps per bank) -- see the per-link tables. "
  "Per-signal extraction on a kept waveform (6 words): every HIGH output crosses the receiver's trip on time; the late ones are the "
  "LOW outputs of second-level nands whose two inputs are both rail-tracking HIGHs pulled up through ONE pMOS each (the XOR's "
  "first-level nands). Lane tests of that mechanism (table below): a nand2 chain with the other input held HIGH (one-pMOS pull-up, "
  "own HIGH source per chain) PASSES at 92 ps with the lane's margin (340 vs 356 mV, commit slot+124) -- one-pMOS pull-up alone "
  "is NOT the cause; the dual-rail XOR primitive itself as a lane PASSES (304 mV, commit slot+131, lag 62-86 ps vs 38-57) -- it "
  "costs ~8 ps per bank; 2x pMOS does not buy it back (xorh_wp2 slot+126). The CRC's remaining ~12 ps and its per-bank drift are "
  "UNEXPLAINED here (candidates: random-data vs alternating patterns -- a HIGH that lags the rail by 60-86 ps is still short of "
  "full rail when the next bank samples it, weakening that bank's nMOS stacks and compounding; two data inputs per XOR vs one). "
  "Honest reading: on this node "
  "the wave carries narrow-fanout, uniform-depth logic (hash/XOR/CRC class) at 1 result per 276 ps per lane; arithmetic with "
  "reconvergent fanout does not map without a load-aware synthesis step that was not pre-registered and is not measured here.")
P("")
for name, b in R["blocks"].items():
    a = b["acceptance"]
    if "d2_tt92" not in name:
        continue
    P("* **%s** (%s): %d gates (%d nand2 + %d delay inverters), %d FETs, %d banks; **%s** -- %d/%d boundary bits "
      "correct at every bank on every scored wave, final word == software reference on %d/%d words; worst commit "
      "margin %s mV (budget 69.924), worst handoff overlap %s ps, min link eye %s ps, standing eye %s ps, erosion %s. "
      "Latency %s..%s ps (first input edge -> final word committed; %s ps at the 69.924 mV gate), throughput **1 result / 276 ps = "
      "3.623 G/s per lane** (a new word launched every period, %d/%d landed correct)."
      % (name, b.get("retime", ""), b["gates"], b["nand2"], b.get("delay_inverters", 0), b["fets"], b["NB"],
         "PASS" if a["PASS"] else "FAIL", b["value"]["checked"] - b["value"]["n_fail"], b["value"]["checked"],
         b["value"]["final_vs_reference"]["ok"], b["value"]["final_vs_reference"]["ok"] + len(b["value"]["final_vs_reference"]["bad"]),
         f(a["worst_margin_at_commit_mV"]), f(a["worst_overlap_ps"], 2), f(a["min_eye_0mV_real_links_ps"]), f(a["standing_eye_ps"], 2),
         "/".join(b["erosion_sign"]), f(b["latency_ps"]["min_raw"]), f(b["latency_ps"]["max_raw"]), f(b["latency_ps"]["max_gate69"]),
         b["value"]["final_vs_reference"]["ok"], b["value"]["final_vs_reference"]["ok"] + len(b["value"]["final_vs_reference"]["bad"])))
P("")
P("Other T_third rows (committed rule, nw = 24): CRC d=2 at 117 ps: value PASS (0/10670 bits, 22/22 words), B/C FAIL "
  "(margin -49 mV, overlap -73 ps at link 2); CRC d=3 at 150 ps EXTINCT; multiplier d=2 at 117 and 150 ps and d=3 at 165 ps EXTINCT "
  "(final word right on 2/22, 0/22, 0/22) -- a longer third does not help a load/order failure, as the mechanism predicts.")
P("")
P("### Falsified: d = 3 nand2 levels per bank at 92 ps (the pre-registered point)")
P("")
for name, b in R["blocks"].items():
    if not name.endswith("d3_tt92"):
        continue
    a = b["acceptance"]
    l1 = b["links_summary"]["1"] if "1" in b["links_summary"] else b["links_summary"][1]
    P("* %s (d=3): FAIL -- %d boundary-bit failures (incl. bank-waves with NO commit inside the bank's own powered window), final word "
      "matched the reference on %d/%d words; bank 1 (3 nand2 levels from the ideal head) "
      "commits at slot + %s ps (inverter d=3 anchor: slot + 110..117) with a %s ps minimum eye; bank 2 therefore sees its inputs valid only "
      "during its hold third and cannot resolve 3 more nand2 levels before they die on bank 1's fall -- every downstream bank is "
      "garbage (link margins at the receiver crest around -1 V). Measured tracking lag %s..%s ps vs 77..82 for the inverter bank. "
      "The committed rule 'synthesize for worst-cell traversal time, not count' is exactly this: the nand2 level in the wave is "
      "~1.6x the inverter level (same ratio as the CMOS chains: 83.5/52.5 at 1.2 V)."
      % (name.split("_")[0], b["value"]["n_fail"],
         b["value"]["final_vs_reference"]["ok"], b["value"]["final_vs_reference"]["ok"] + len(b["value"]["final_vs_reference"]["bad"]),
         (f(l1["commit_minus_slot_ps_max"]) if l1["commit_minus_slot_ps_max"] is not None else "(no commit in its own powered window; gated eye opens ~slot+200)"),
         f(l1["eye_0mV_ps_min"]), f(b["rising_lag_ps"]["max"]), f(b["rising_lag_ps"]["min"])))
    ea = b.get("engine_agreement")
    if ea:
        P("  Xyce on the same deck (6 periods): the same failure (final words identical on both engines: %s; worst commit-instant "
          "difference %s ps, eye-width difference %s ps on the links that commit)." % (ea["value_words_identical"], f(ea["worst"]["commit_ps"], 2), f(ea["worst"]["eye_ps"], 2)))
P("")
P("### nand2 cell-class calibration lanes (mesh3 harness, 8 nand2(x,x) chains x 6 banks, P0-alt, VACASK)")
P("")
P("| d levels/bank (fanout = consumers per node, cell variant) | T_third ps | period ps | A value | B eye (>=69.9 mV) | C handoff | worst margin mV | worst overlap ps | min eye ps | commit - slot (bank 2) ps | lag ps | verdict |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|")
for tag, l in sorted(R["nand2_lanes"].items(), key=lambda kv: (kv[1]["d"], int(kv[0].split("_f")[1].split("_")[0]) if "_f" in kv[0] else 1, kv[0], kv[1]["tt"])):
    fo = int(tag.split("_f")[1].split("_")[0]) if "_f" in tag else 1
    var = ("nand(x,HIGH) one-pMOS" if "nandh" in tag else "dual-rail XOR primitive" if "xorh" in tag else "nand(x,x)") + (" 2x pMOS" if "_wp2" in tag else "")
    P("| %d (fanout %d, %s) | %g | %g | %s | %s | %s | %s | %s | %s | %s | %s..%s | **%s** |" % (
        l["d"], fo, var, l["tt"], 3 * l["tt"], l["A"], l["B"], l["C"], f(l["worst_margin_mV"]), f(l["worst_overlap_ps"], 2),
        f(l["eye_min_ps"]), f(l["commit_minus_slot_b2_ps"]), f(l["rising_lag_ps"]["min"]), f(l["rising_lag_ps"]["max"]),
        "PASS" if l["PASS"] else "FAIL"))
P("")
P("Reading: the nand2 bank's commit instant moves ~+45 ps per added level; at 92 ps the receiver's rise third can absorb two levels, "
  "not three. d=1 fails on handoff (negative overlap at link 5: the input-death channel mesh3 pre-identified for shallow banks).")
P("")
tl = R["t_level_ps"]["used"]
P("CMOS comparator (same nand2/inv netlist, registers every D levels): period = D*t_level + t_reg with **t_level(nand2, 2 fF) "
  "= %s ps @1.2 V (campaign comparator supply; inverter 52.51 reproduced) / %s ps @1.65 V (iso-voltage, MEASURED here)**, "
  "t_reg(2 fF) = 315.378 ps DERIVED (lower bound). OpenSTA on the actual netlist (vendor liberty, real fanout) alongside."
  % (f(tl.get("nand2_1.2V"), 2), f(tl.get("nand2_1.65V"), 2)))
P("")
P("**Where the win lives:** results/s per lane (no register tax in the period: 276 ps vs D*t_level + t_reg) and "
  "end-to-end latency vs *registered* CMOS at every D (the single flop tax, 315 ps, is comparable to the wave's whole "
  "bank-to-bank step). It is NOT a per-level latency win against the bare unregistered chain at iso-voltage -- see the "
  "bare-chain rows. Per-bank initiation interval (276 ps) is never conflated with the wavefront level-rate (d levels per 92 ps).")
P("")

# ---- block tables
for name, b in R["blocks"].items():
    if "d2_tt92" not in name:
        continue
    P("## Block %s (d=2, T_third=92 ps, %s)" % (name, b.get("retime", "")))
    P("")
    P("Structure: %s. NB = %d banks, logic nand-levels L = %s, %d delay inverters (bank-alignment tax, real devices). "
      "Boundary signals scored per bank: %s."
      % ("32 dual-rail nand2 XOR trees (24..34 terms each, leaves at XOR-depth D or D-1 only), "
         "4 groups of 8 trees simulated separately (electrical union, PRE_REGISTERED)" if name.startswith("crc32") else
         "AND array (nand2+inv, dual-rail) -> Dadda CSA tree of 16-nand2 dual-rail full adders (depth 4) -> "
         "radix-2 Kogge-Stone (nand2/inv, polarity tracked)",
         b["NB"], b.get("levels_logic"), b.get("delay_inverters", 0),
         json.dumps(b.get("n_boundary", {k: None for k in []}))[:200]))
    P("")
    P("| link k (bank k -> k+1) | eye 0 mV min..max (ps) | commit_raw - slot (ps) | overlap min (ps) | margin at commit min (mV) | receiver |")
    P("|---|---|---|---|---|---|")
    for k, s in b["links_summary"].items():
        P("| %s | %s..%s | %s..%s | %s | %s | %s |" % (
            k, f(s["eye_0mV_ps_min"]), f(s["eye_0mV_ps_max"]), f(s["commit_minus_slot_ps_min"]),
            f(s["commit_minus_slot_ps_max"]), f(s["overlap_ps_min"], 2), f(s["margin_at_commit_mV_min"]),
            "DERIVED ideal next-phase rail" if s["derived_receiver"] else "real (bank k+1 rail)"))
    P("")
    P("Rising-side tracking lag (last boundary HIGH 50%% after own rail 50%%): %s..%s ps. Latency per word (raw commit): "
      "%s..%s ps; at the 69.924 mV gate: %s ps max."
      % (f(b["rising_lag_ps"]["min"]), f(b["rising_lag_ps"]["max"]), f(b["latency_ps"]["min_raw"]),
         f(b["latency_ps"]["max_raw"]), f(b["latency_ps"]["max_gate69"])))
    P("")
    P("Per-bank rail books (REPORTED, not gated; offline trapezoid on the engine grid, mean over scored waves%s):"
      % (", SUMMED over the 4 groups" if name.startswith("crc32") else ""))
    P("")
    P("| bank | phase | Q_rise fC | Q_hold fC | Q_fall fC | E_rise fJ | E_hold fJ | E_fall fJ |")
    P("|---|---|---|---|---|---|---|---|")
    for k, c in b["charge_spec_reported_not_gated"].items():
        P("| %s | %s | %s | %s | %s | %s | %s | %s |" % (k, c["phase"], f(c["Q_rise_fC"]), f(c["Q_hold_fC"]),
                                                    f(c["Q_fall_fC"]), f(c["E_rise_fJ"]), f(c["E_hold_fJ"]), f(c["E_fall_fJ"])))
    tot_e = sum((c["E_rise_fJ"] or 0) + (c["E_hold_fJ"] or 0) + (c["E_fall_fJ"] or 0)
                for c in b["charge_spec_reported_not_gated"].values())
    P("")
    P("Net rail energy per result (sum of thirds over all banks, ideal-source convention, fall third recovers): **%.1f fJ/result** "
      "(ideal mesh; the measured flat-top driver price of qal/meshdrv, 2.2x, applies on top). Delay inverters are inside these books."
      % tot_e)
    P("")
    # CMOS comparison
    P("### CMOS comparison, %s" % name.split("_")[0])
    P("")
    q = b["cmos"]["QAL"]
    P("QAL: %s G results/s per lane (period %s ps), latency %s ps (max over words), %d banks." % (
        f(q["results_per_s_G"], 3), f(q["period_ps"], 0), f(q["latency_ps"]), q["banks"]))
    P("")
    for lab, c in b["cmos"].items():
        if lab == "QAL":
            continue
        if lab.startswith("STA_"):
            P("**OpenSTA, liberty %s** (real fanout incl. head; head-free in parentheses = false-path from the input registers):" % lab[4:])
            P("")
            P("| D | stages | min period ps (head-free) | results/s G | latency ps | QAL/CMOS throughput | CMOS/QAL latency |")
            P("|---|---|---|---|---|---|---|")
            for D, r in c["rows"].items():
                P("| %s | %d | %s (%s) | %s | %s | %sx | %sx |" % (
                    D, r["stages"], f(r["period_ps"]), f(r["period_headfree_ps"]), f(r["results_per_s_G"], 3),
                    f(r["latency_ps"]), f(r["ratio_throughput_QAL_over_CMOS"], 2), f(r["ratio_latency_CMOS_over_QAL"], 2)))
        else:
            P("**Formula comparator, t_level = %s ps (%s), t_reg = 315.378 ps** (corner: +100 ps clock uncertainty):" % (
                f(c["t_level_ps"], 2), lab))
            P("")
            P("| D | stages | period ps (corner) | results/s G (corner) | latency ps (corner) | QAL/CMOS throughput (corner) | CMOS/QAL latency |")
            P("|---|---|---|---|---|---|---|")
            for D, r in c["rows"].items():
                P("| %s | %d | %s (%s) | %s (%s) | %s (%s) | %sx (%sx) | %sx |" % (
                    D, r["stages"], f(r["period_ps"]), f(r["period_corner_ps"]), f(r["results_per_s_G"], 3),
                    f(r["results_corner_G"], 3), f(r["latency_ps"]), f(r["latency_corner_ps"]),
                    f(r["ratio_throughput_QAL_over_CMOS"], 2), f(r["ratio_throughput_corner"], 2),
                    f(r["ratio_latency_CMOS_over_QAL"], 2)))
            P("")
            P("Bare unregistered chain (the load-matched level comparator, no flop): L*t_level = **%s ps**; "
              "bare-chain / QAL latency = **%sx** (%s)." % (f(c["bare_chain_latency_ps"]), f(c["ratio_bare_chain_over_QAL"], 3),
                                                            "QAL is slower end-to-end than the bare chain" if (c["ratio_bare_chain_over_QAL"] or 2) < 1
                                                            else "QAL is faster end-to-end than the bare chain"))
        P("")
    # engine
    ea = b.get("engine_agreement")
    P("### Engine agreement, %s (Xyce anchor = same deck, first 6 periods, waves %s)" % (name.split("_")[0], ea["waves"] if ea else "n/a"))
    P("")
    if ea:
        P("| quantity | worst |Δ| over links x waves | band | verdict |")
        P("|---|---|---|---|")
        for k, band in ea["bands"].items():
            P("| %s | %s | %s | %s |" % (k, f(ea["worst"][k], 4), band, "PASS" if ea["PASS"].get(k.split("_")[0], ea["PASS"].get(k)) else "OUTSIDE"))
        P("")
        P("Final hardware words identical on both engines: %s. Q_rise per bank VACASK %s vs Xyce %s fC. Wall: VACASK %s s / %s pts "
          "(24 words) vs Xyce %s s / %s pts (6 periods)." % (ea["value_words_identical"], ea["Q_rise_vacask_fC"], ea["Q_rise_xyce_fC"],
                                                          ea["wall"]["vacask_s"], ea["wall"]["vacask_npts"], ea["wall"]["xyce_s"], ea["wall"]["xyce_npts"]))
    else:
        P("Xyce anchor not available (see RESULTS.json other_runs).")
    P("")

# ---- cells & harness checks
P("## Cells, level measurement, harness anchor")
P("")
P("* nand2 = sg13g2_nand2_1 vendor sizing VERBATIM (= campaign inverter widths): 2x pMOS 1.12u parallel, 2x nMOS 0.74u series, "
  "l 0.13u, CL 2 fF; stack depth 2 (shallow). XOR2 = dual-rail depth-2 nand2 form (6 nand2) -- the single-rail 4-nand2 XOR is "
  "depth THREE, the vendor xor2_1 has a 2-high pMOS stack (excluded by the shallow rule), the pass-gate XOR is banned.")
d = R["t_level_ps"]["detail"] or {}
P("* CMOS per-level delay, depth-12 chain @2 fF, (t10 - t4)/6 at VDD/2 (fcrit_skept arm-D method), MEASURED:")
P("")
P("| VDD | nand2 both inputs | nand2 one input tied high | inverter | Xyce (a / b / i) |")
P("|---|---|---|---|---|")
for v, dd in d.items():
    P("| %s | %s | %s | %s | %s / %s / %s |" % (v, f(dd["nand2_both_inputs"], 3), f(dd["nand2_one_tied_high"], 3),
                                             f(dd["inverter"], 3), f(dd["xyce"]["a"], 3), f(dd["xyce"]["b"], 3), f(dd["xyce"]["i"], 3)))
P("")
P("  The inverter at 1.2 V reproduces the committed 52.51 ps digit-exact on Xyce (52.637 on VACASK, +0.24%). The nand2 level is "
  "1.59x the inverter level at 1.2 V and 1.50x at 1.65 V.")
ic = R["IC_harness_anchor"]
if ic:
    c = ic["compare"]
    P("* Harness anchor (IC): committed mesh3 `trap_tt92_d3` regenerated by this generator and scored by this extractor on VACASK: "
      "value %d/%d fails on waves 2..6 (mesh3: 144 checks, 0 fails); worst margin_at_commit %s vs %s mV (rel %s -- instantaneous-sample "
      "class, OFFSET_TABLE Amendment 2; %s); worst overlap %s vs %s ps; standing eye %s vs %s ps; commit_raw(bank 2, wave 3) %s vs %s ps; "
      "Q_rise bank 1 %s vs %s fC; rising lag %s vs %s. Wall %s s, %d pts."
      % (c["value"][2], c["value"][0], c["worst_margin"][0], c["worst_margin"][1], ic["margin_rel"],
         "inside 1%" if ic["margin_ok"] else "1.18%, just outside the 1% band stated for it",
         c["worst_overlap"][0], c["worst_overlap"][1], c["standing_eye"][0], c["standing_eye"][1],
         c["commit_raw_b2_w3"][0], c["commit_raw_b2_w3"][1], c["Q_rise_b1"][0], c["Q_rise_b1"][1],
         c["rising_lag"][0], c["rising_lag"][1], ic["wall_s"], ic["npts"]))
P("")
P("## Riders (stated, not discharged)")
P("")
P("* Ideal mesh (BOUND) and ideal head (BOOKED): the head's fanout (CRC inputs fan out to up to 20 trees x 2 polarities) and the head "
  "complements are free to the wave; the formula CMOS comparator is given the same free head; the STA comparator is NOT (its input "
  "registers drive the real fanout -- the head-free column removes it).")
P("* CRC recurrence: the state feedback is not closed inside the wave; one lane sustains one update per period only with "
  "ceil(latency/period) interleaved independent streams (packets/flows). Same for a FIR MAC accumulate.")
P("* The CRC groups are an electrical union (no shared internal node; ideal rails behind 0.001 ohm). Per-bank charges are sums.")
P("* Energy: ideal-source books only; the flat-top driver's measured 2.2x (qal/meshdrv) applies; no energy claim is made.")
P("* Last link scored against the DERIVED ideal next-phase rail (mesh3 convention); interior links are real.")
P("")
P("## Files")
P("")
P("`PRE_REGISTERED.json` (first file), `mblocks.py` (netlists, levelizer/bank aligner, decks for both engines, numpy port of the "
  "mesh3 scorer), `agg.py` -> `RESULTS.json`, `mkreadme.py` -> this file, `IC.json`, `LEVEL.json`, `STA_*.json`, `runs/<tag>/` "
  "(deck + log + OUT.json; no waveforms -- raws/prns lived on the scratchpad and were deleted after extraction).")
open(os.path.join(HERE, "README.md"), "w").write("\n".join(L) + "\n")
print("README.md written, %d lines" % len(L))
