"""p2 -- assemble RESULTS.json from the measured files.  Adds no new numbers."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W
import comp

HERE = W.HERE
L = lambda n: json.load(open(os.path.join(HERE, n)))
FR = L("FINAL_ROWS.json")
IC = L("INSTRUMENT_CHECK.json")
CB = L("CBANK_INSITU.json")
CBR = L("CBANK_INSITU_RESTORE.json")
DG = L("DIAG_CROWBAR.json")
RX = L("REANALYSIS_RESTORE.json")
PH1 = L(os.path.join(W.P1, "RESULTS.json"))

PRIM = "W2_L15_g2400_m10_T300_rst"          # deepest full-interconnect row
PRIM4 = "W2_L15_g2400_m10_T400_rst"
CTRL = "W0_L15_g2400_m10_T400_rst"          # zero-interconnect control


def sep(tag):
    r = RX[tag]
    o = {}
    for k in range(1, 7):
        v = r["per_bank_extended"][str(k)]
        bm = v.get("best_margin_inside_interval_mV")
        o["bank%d" % k] = (dict(peak_margin_mV=bm, sigma_multiples=bm / W.SIG_MV)
                           if bm is not None and bm > -1e8 else None)
    return o


def cmpblock(beat, what):
    c = comp.compare(beat, what)
    return c


def row_digest(tag):
    r = FR[tag]
    d = r["deepest_correct_bank"]
    return dict(
        tag=tag, arrangement=r["arrangement"], bank=r["bank"],
        wire=r["wire"], L_nH=r["l_nh"], VGH=r["vgh"], m=r["m"], H=r["H"],
        T_requested_ps=r["T_requested_ps"],
        deepest_correct_bank_of_6=d,
        all_six_correct=r["all_six_correct"],
        SUSTAINED_BEAT_ps=r["SUSTAINED_BEAT_ps"],
        stage_time_ps=r["stage_time_ps"],
        per_bank_own_level_ps={k: r["own_level_ps"][k] for k in r["own_level_ps"]},
        mean_own_level_over_correct_banks_ps=(
            sum(r["own_level_ps"][str(k)] for k in range(1, d + 1)) / d
            if d else None),
        hold_ps=r["hold_ps"],
        cascade_hold=r["cascade_hold"],
        cascade_holds_everywhere=r["cascade_holds_everywhere"],
        latency_by_depth_ps=r["latency_by_depth_ps"],
        separation_by_depth_peak_margin=sep(tag) if tag in RX else None,
        per_deck_instrument_T90ZC_ps=r["per_deck_instrument_T90ZC_ps"],
        per_deck_instrument_rel=r["per_deck_instrument_rel"],
        K4_own_level_within_requested_T=r["K4_own_level_within_requested_T"],
        K5_IZ_max_uA=r["K5_IZ_max_uA"],
        per_bank_settling_and_value=({
            ("bank%d" % k): dict(
                paths="".join(W.logic()[1][k - 1]), want=W.logic()[0][k - 1],
                rail_peak_V=r["per_bank"][str(k)]["rail_peak_V"],
                rail_at_arrival_V=r["per_bank"][str(k)].get("rail_at_arrival_V"),
                min_settled_pct_of_own_rail=r["per_bank"][str(k)].get(
                    "min_settled_pct"),
                K2_floor_all_ok=r["per_bank"][str(k)].get("K2_all_ok"),
                cells=r["per_bank"][str(k)].get("cells"))
            for k in range(1, 8)}))


R = {}
R["_what"] = (
    "PHASE 2 of the qal/fastwave run.  A SEVEN-BANK TG-XOR QAL wave (six scored, "
    "the seventh an unscored terminator load) built at the Phase-1 optimum with "
    "per-bank tanks (qal/banktank 0aae11e arrangement), chain-legal source-side "
    "ZCS cuts, dV = 1.65 V, and -- for the first time in this campaign -- EXPLICIT "
    "rotate interconnect extracted from the PDK.  Objective: the SUSTAINED BEAT, "
    "measured as a difference of two waveform instants.")
R["_labels"] = (
    "MEASURED = read off a waveform or a .measure in qal/fastwave/p2.  DERIVED = "
    "arithmetic over MEASURED terms.  ASSUMED = neither, and named.  BOOKING = "
    "modelled as an ideal source; its row is a BOUND in the optimistic direction.")
R["_definition_used_everywhere"] = (
    "ARRIVAL(k) = start of the FIRST contiguous interval, searched from bank k's "
    "own rail start to the END OF THE DECK, in which all four of bank k's outputs "
    "are on the correct side of the receiver's MEASURED trip (qal/fcrit/TRIP.json, "
    "interpolated at bank k's own INSTANTANEOUS delivered rail -- the trip FRACTION "
    "is not a constant, 0.7281 at 0.20 V falling to 0.5179 at 1.50 V) by the "
    "3-sigma budget 19.323 mV.  HOLD = that interval's length.  STAGE(k) = "
    "ARRIVAL(k) - ARRIVAL(k-1).  SUSTAINED BEAT = max STAGE over the banks that "
    "arrived.  OWN LEVEL(k) = ARRIVAL(k) - bank k's own rail-start instant.  The "
    "definition moved three times during this phase; two of the intermediate "
    "readings were artefacts and are written up in AMENDMENT.md P11-P15.")

R["A_INSTRUMENT"] = {
    "F1_comparator_byte_identical": IC["F1_comparator"],
    "F2_wire_model_rederived": IC["F2_wire_model"],
    "F3_logic_table": IC["F3_logic_table"],
    "F4_C_bank_reproduction_of_Phase1": CB["INSTRUMENT_CHECK"],
    "per_deck_companion": (
        "every deck carries the 1.12/0.74 inverter into 2 fF whose committed t90 "
        "is 57.1428 ps.  AMENDMENT P8: Phase 1's companion measured the WRONG EDGE "
        "and could never have matched -- every pre-fix deck returned FAILED.  After "
        "the fix every deck reads 57.1424-57.1428 ps, rel <= 5.3e-06."),
    "verdict": "F1 PASS at rel 0.00e+00 on all 14 measures; F4 PASS at rel "
               "0.000e+00 on all quantities using Phase 1's OWN deck builder and "
               "extractor; F2 PASS at rel 4.9e-05 (pre-registration rounding).",
}

R["B_THE_INTERCONNECT -- THE FIRST DECK IN THIS CAMPAIGN TO CARRY ANY"] = {
    "model": "one single-segment pi per wire (C/2 at driver, series R, C/2 at "
             "receiver, both returned to global ground).  Every predecessor output "
             "drives TWO segments: a STRAIGHT one to the next bank's A input and a "
             "ROTATE one to its B input.  6 boundaries x 4 bits x 2 = 48 segments.",
    "PRIMARY_W2": {
        "c_fF_per_um": 0.21806223458062743,
        "label": "DERIVED from MEASURED PDK data",
        "provenance": "qal/cipher/WIRE_MODEL.json Metal2 C_bus_minpitch, built "
                      "from IHP-Open-PDK sg13g2_tech.lef (CAREA 0.0181 pF/um^2 + "
                      "CEDGE 0.0447 pF/um per edge) and the OpenRCX nom rules for "
                      "two-sided coupling at minimum spacing.  Split: 0.01140622 "
                      "ground-shielded + 0.20665601 coupling on two sides.",
        "why_bus": "a rotate is a BUS -- all bits run in parallel at pitch -- so "
                   "the min-pitch two-sided figure is the right one.  The LEF "
                   "isolated figure 0.09302 fF/um is the wrong model and 2.34x "
                   "optimistic.",
        "bit_pitch_um": 3.84,
        "bit_pitch_provenance": "MEASURED: sg13g2_xor2_1 cell width in "
                                "sg13g2_stdcell.lef -- the PDK's own width for a "
                                "functionally identical 2-input XOR.",
        "rotate_pitches": 13.484375,
        "rotate_pitches_provenance": "DERIVED: mean |delta index| = 2r(W-r)/W over "
                                     "the four ChaCha20 rotates on a 32-bit word.",
        "rotate_len_um": 51.78, "rotate_C_fF": 11.2913, "rotate_R_ohm": 26.6667,
        "straight_C_fF": 0.8374, "straight_R_ohm": 1.9776,
        "vs_the_brief_figure": "the PDK bus figure is 4.70x the 0.15 fF/um the "
                               "brief named, and the brief's own arithmetic "
                               "(~75 fF for a 32-bit r16 rotate) is reproduced by "
                               "qal/cipher/WIRE_MODEL.json at 76.8 fF.",
        "DECLARED_CONSERVATISM": "the LOGIC is a complete 4-bit word; the WIRE "
                                 "LENGTH is a 32-bit datapath rotate.  Deliberately "
                                 "mismatched in the HARSH direction -- a 4-bit "
                                 "word's own rotate is 1.5-2.0 pitches.  WL is the "
                                 "matched-but-optimistic reading.",
    },
    "CONTROLS": {"W0": "zero interconnect, the campaign status quo",
                 "W1": "the brief's 0.15 fF/um at 1 um/bit x 16 pitches = 2.4 fF",
                 "WL": "the 4-bit word's OWN rotate at the same PDK bus figure"},
    "MEASURED_COST_ON_THE_BANK_RAIL_LOAD": {
        "phase1_bare_N4_bank_fF": 52.76786735757576,
        "in_situ_no_wire_W0_mean_fF": CB["W0"]["_mean_C_TRUE_fF"],
        "in_situ_PDK_wire_W2_mean_fF": CB["W2"]["_mean_C_TRUE_fF"],
        "successor_load_adds_pct": 100.0 * (CB["W0"]["_mean_C_TRUE_fF"]
                                            / 52.76786735757576 - 1.0),
        "interconnect_adds_a_further_pct": 100.0 * (CB["W2"]["_mean_C_TRUE_fF"]
                                                   / CB["W0"]["_mean_C_TRUE_fF"]
                                                   - 1.0),
        "restoring_bank_W2_mean_fF": CBR["W2"]["_mean_C_TRUE_fF"],
        "reading": "Phase 1's ideal-source BOOKING was the larger optimism: the "
                   "successor bank's input load adds 30.4% to the rail, the PDK "
                   "interconnect a further 18.5%.",
    },
    "MEASURED_COST_ON_THE_PER_LEVEL_TIME": {
        "same_first_three_banks_T400_restoring": {
            "W2_own_level_ps": [FR[PRIM4]["own_level_ps"][str(k)] for k in (1, 2, 3)],
            "W0_own_level_ps": [FR[CTRL]["own_level_ps"][str(k)] for k in (1, 2, 3)],
            "W2_mean_ps": 230.68, "W0_mean_ps": 176.63,
            "ratio": 1.3061, "interconnect_penalty_pct": 30.6},
        "cost_in_DEPTH": "with the PDK interconnect the wave reaches 3 of 6 banks; "
                         "with zero interconnect it reaches 5 of 6.  The "
                         "interconnect costs TWO levels of depth.",
        "cost_in_SEPARATION": "peak separation by depth collapses 348.7 -> 296.9 "
                              "-> 21.8 mV (54.1 -> 46.1 -> 3.4 sigma) with the PDK "
                              "interconnect, and HOLDS at 393.3/370.1/414.8/381.5/"
                              "345.5 mV (53.6-64.4 sigma) without it.",
    },
    "C_bank_method": CB["_METHOD"],
    "C_bank_per_bank": {"non_restoring": CB, "restoring": CBR},
}

R["C_WHY_THE_UNBUFFERED_TG_XOR_WAVE_DOES_NOT_WORK -- MEASURED, NOT ARGUED"] = {
    "the_symptom": "all four pre-registered skewed rows (T = 200/250/300/350 ps) "
                   "failed every scored bank by 100-524 mV, and bank 1 -- ideal "
                   "1.20 V inputs, binding cell fully selected -- delivered only "
                   "62.8% of its own rail.",
    "the_test": DG["_what"],
    "THE_NUMBERS": {
        "successor_rail_at_0_THE_CHAIN_CONDITION": {
            "bank1_cell0_I_out_uA": -78.644, "bank1_cell0_V_out_V": 1.4008,
            "bank3_cell1_I_out_uA": -82.505, "bank3_cell1_V_out_V": 1.3864,
            "successor_select_bb_V": 0.2624},
        "successor_rail_at_dV_THE_CONTROL": {
            "bank1_cell0_I_out_uA": -0.000, "bank1_cell0_V_out_V": 1.6476,
            "bank3_cell1_I_out_uA": -0.000, "bank3_cell1_V_out_V": 1.6476,
            "successor_select_bb_V": 1.6500},
        "identical_at_W2_and_W0": True,
    },
    "THE_MECHANISM": "while the successor's rail is at 0 its select node bb cannot "
                     "rise, so BOTH of its transmission-gate pMOS conduct; the cell "
                     "ties the predecessor's output through TG1's pMOS to its own y, "
                     "and TG2's pMOS ties that y to an ab its grounded nMOS holds "
                     "at 0.  Every predecessor output is DC-shorted to ground "
                     "through two series pMOS for the whole beat before its "
                     "successor rises.  A pass-gate output has no strength to hold "
                     "against it, and an LC tank cannot supply a RESISTIVE load: it "
                     "delivers a fixed CHARGE, and a resistive load consumes charge "
                     "in proportion to time.",
    "WHICH_CORRECTS_MY_OWN_AMENDMENT_P4": "P4 measured the slow-ramp crowbar at "
                     "0.018-0.037 uA and concluded it was negligible at wave speed. "
                     "That figure is the current flowing BETWEEN THE IDEAL INPUT "
                     "SOURCES of the calibration deck, not the one flowing OUT OF "
                     "THE RAIL through a pass-gate output in a real chain.  The "
                     "correct figure is 78-83 uA, 2000-4000x larger.  A correction "
                     "of my own correction, caught by the next measurement.",
    "IT_IS_EXACTLY_WHAT_pgcell_PREDICTED": "qal/pgcell recorded that a TG cell is "
                     "not level-restoring on its data path and that restoring the "
                     "chain gives back the whole device saving.  Phase 1 booked "
                     "that away with ideal input sources and said so; Phase 2 pays "
                     "it.",
    "AND_THE_SECOND_MECHANISM": "the synchronous arrangement removes the crowbar by "
                     "construction, and the chain then computes to depth 2 and "
                     "fails at depth 3: bank 2 delivers HIGHs at 0.58-0.69 V while "
                     "bank 3's input inverters need ~0.6 V at their own higher rail "
                     "to read a 1.  A TG cell has no gain, so the HIGH level falls "
                     "below the successor's own trip by the third bank.",
}

R["D_THE_ROWS"] = {t: row_digest(t) for t in sorted(FR) if not FR[t].get("FAILED")}
R["D_ROWS_THAT_NEVER_CONVERGED_named_not_estimated"] = {
    t: FR[t]["FAILED"] for t in sorted(FR) if FR[t].get("FAILED")}

R["E_THE_ANSWER"] = {
    "does_the_wave_compute_at_six_deep": "NO.  Not in any of the 14 converged rows, "
        "not at any beat period from 200 to 400 ps, not in either rail "
        "arrangement, not with or without interconnect, and not with a 1x, 2x or 4x "
        "tank.",
    "the_pre_registered_cell_TG_XOR_alone": "reaches depth 1 of 6 at every beat "
        "period.  It never cascades.  The reason is measured in section C.",
    "the_restoring_bank_still_inside_the_users_two_level_budget": {
        "with_the_PDK_interconnect": "depth 3 of 6",
        "with_zero_interconnect": "depth 5 of 6",
    },
    "THE_DEEPEST_FULL_INTERCONNECT_ROW": row_digest(PRIM),
    "the_beat_depth_trade_MEASURED": {
        "T200": {"beat_ps": FR["W2_L15_g2400_m10_T200_rst"]["SUSTAINED_BEAT_ps"],
                 "depth": 2},
        "T300": {"beat_ps": FR[PRIM]["SUSTAINED_BEAT_ps"], "depth": 3},
        "T400": {"beat_ps": FR[PRIM4]["SUSTAINED_BEAT_ps"], "depth": 3},
        "reading": "a shorter requested beat buys a faster measured beat and less "
                   "depth.  257.35 ps at depth 2, 363.27 ps at depth 3."},
    "the_tank_size_lever_is_COUNTERPRODUCTIVE": {
        "m10": {"beat_ps": 436.47, "depth": 3, "hold_bank3_ps": 151.1},
        "m20": {"beat_ps": 447.77, "depth": 3, "hold_bank3_ps": 65.8},
        "m40": {"beat_ps": 454.99, "depth": 3, "hold_bank3_ps": 51.5},
        "reading": "4x the tank makes the beat 4.2% SLOWER and the hold 3x "
                   "shorter, and buys no depth.  The tank's own capacitance joins "
                   "the resonance -- the same shape as Phase 1's finding that "
                   "widening the switch is counterproductive."},
    "what_DOES_hold": "the cascade hold condition PASSES: banks hold their correct "
        "values for 2049-2796 ps against the 326-436 ps a successor needs.  The "
        "failure is NOT decay -- an earlier draft of this run said it was and was "
        "wrong (AMENDMENT P12).  The failure is that the deeper banks never reach "
        "a correct level at all.",
}

R["F_THE_COMPARISON"] = {
    "comparators_MEASURED": {
        "CMOS_level_6p91fF_ps": comp.CMOS_6p91,
        "CMOS_level_2fF_ps": comp.CMOS_2,
        "source": "qal/fcrit/cmos.cir, copied BYTE-IDENTICAL into this directory "
                  "and re-run under this phase's own PYMS_VAE_CACHE; all 14 .mt0 "
                  "measures reproduce at rel 0.00e+00.",
        "t_reg_ps": comp.TREG, "t_reg_at_2fF_interpolated_ps": comp.TREG_2,
        "liberty_optimism": "transistor cross-check 258.9-302 ps, i.e. liberty is "
                            "1.11-1.21x OPTIMISTIC, so a D* from liberty FLATTERS "
                            "CMOS; the widened range is on every row.",
    },
    "load_matched_comparator_IS_THE_2fF_ONE": "every cell in this phase carries "
        "CL = 2 fF on its output referenced to the cell ground -- the SAME load the "
        "2 fF arm of qal/fcrit/cmos.cir drives.  The 6.91 fF / 94.1745 ps figure is "
        "the committed campaign headline and is reported alongside, but it is NOT "
        "load-matched and it FLATTERS QAL.",
    "AT_THE_SUSTAINED_BEAT_deepest_full_interconnect_row": cmpblock(
        FR[PRIM]["SUSTAINED_BEAT_ps"],
        "THE SUSTAINED BEAT: max measured stage-to-stage time of the deepest "
        "full-interconnect row (restoring bank, true skewed wave, W2, T = 300 ps), "
        "which sustains 3 of 6 banks"),
    "AT_THE_MEAN_PER_LEVEL_TIME_same_row": cmpblock(
        238.58666666666664,
        "the mean MEASURED per-level time of the same row's three working banks "
        "(204.0 / 267.3 / 244.5 ps from each bank's own rail start to its own "
        "arrival).  A per-LEVEL figure, not a pipeline beat -- reported because it "
        "is the most generous number this run can defend."),
    "AT_THE_FASTEST_MEASURED_BEAT_depth_2_only": cmpblock(
        FR["W2_L15_g2400_m10_T200_rst"]["SUSTAINED_BEAT_ps"],
        "the fastest measured beat of any row, 257.35 ps -- but it sustains only "
        "2 of 6 banks, so it is not a pipeline number"),
    "AT_THE_ZERO_INTERCONNECT_CONTROL": cmpblock(
        FR[CTRL]["SUSTAINED_BEAT_ps"],
        "the zero-interconnect control (W0, restoring, T = 400), which reaches "
        "5 of 6 banks -- reported so the interconnect's cost is visible, NOT as a "
        "result, because no real datapath has zero interconnect"),
    "criterion_note": "scored against the FUNCTIONAL criterion: each receiver "
        "commits at its own MEASURED trip at its own DELIVERED rail, the trip "
        "fraction interpolated per row.  THE SAME criterion applies to CMOS -- but "
        "qal/fcrit MEASURED a CMOS stage delay to be bar-INVARIANT (gain "
        "1.0000-1.0001x), so the relaxation helps QAL and not CMOS, and the "
        "comparison is if anything generous to QAL.",
}

R["G_THE_VERDICT -- said as clearly as a positive would be"] = {
    "on_the_wave_rate": "QAL does NOT beat CMOS.  At the sustained beat of the "
        "deepest full-interconnect row, 363.27 ps, it is 6.36x slower than the "
        "load-matched 2 fF CMOS logic level (57.1428 ps) and 3.86x slower than the "
        "6.91 fF one.  Even on the most generous defensible figure -- the mean "
        "per-level time of 238.59 ps -- it is 4.18x and 2.53x slower.",
    "on_CMOS_plus_the_flop_tax": "the crossover D* is 1.03 against the load-matched "
        "comparator at the sustained beat, and 1.74 on the per-level figure "
        "(1.25 and 2.32 against the 6.91 fF one).  Removing the liberty's "
        "1.11-1.21x optimism moves the load-matched pair to 1.14-1.25 and "
        "1.93-2.10.  So QAL wins only at D = 1 -- a flop after every single logic "
        "level -- which is not a design point.",
    "which_of_the_two_comparisons": "NEITHER.  It loses at the level, and it loses "
        "the flop-tax comparison at every pipeline depth a real design would use.",
    "and_the_deeper_answer": "the beat is not even the binding problem.  The wave "
        "does not COMPUTE past 3 of 6 banks with the PDK interconnect present, in "
        "any arrangement, at any beat, with any tank size.  A speed comparison on a "
        "chain that does not cascade is the wrong question, and the honest headline "
        "is the depth limit, not the picoseconds.",
    "what_the_run_DOES_establish_positively": [
        "The rotate interconnect matters and had never been carried: it adds 18.5% "
        "to the bank rail load, 30.6% to the per-level time, and costs TWO LEVELS "
        "OF DEPTH (5 of 6 without it, 3 of 6 with it).  Its cost in separation is "
        "the sharpest figure in the run: 348.7 -> 296.9 -> 21.8 mV by depth with "
        "it, 393-415 mV flat without it.",
        "Phase 1's ideal-input-source BOOKING hid a larger cost than the "
        "interconnect: the successor bank's real input load alone adds 30.4% to the "
        "rail capacitance, so every Phase-1 hop number is a bound in the optimistic "
        "direction by more than Phase 1 could see.",
        "The unbuffered TG-XOR wave fails for a NAMED, MEASURED, quantitative "
        "reason -- a 78-83 uA DC crowbar into a successor whose rail has not yet "
        "risen -- and not for want of tuning.  That is a device/topology fact, not "
        "a fitting failure.",
        "Spending the user's SECOND transistor level on a restoring inverter is "
        "worth 2 levels of depth (1 of 6 -> 3 of 6 with interconnect) and is the "
        "single most effective change found.  It is not enough.",
        "Bigger tanks are counterproductive for speed, in the same direction Phase "
        "1 measured for wider switches.",
    ],
}

R["H_PREDICTIONS_SCORED"] = {
    "Q0_beat_slower_than_Phase1s_243.638_ps_and_lands_280_400": {
        "verdict": "CONFIRMED in direction, and the reason list was incomplete.",
        "measured": "363.27 ps at the deepest full-interconnect row -- inside the "
                    "predicted 280-400 ps band.  But I named three causes "
                    "(real predecessor, interconnect, harsher mix) and MISSED the "
                    "one that dominates: the successor's DC crowbar, which does not "
                    "slow the wave so much as stop it cascading.",
    },
    "Q1_interconnect_delta_on_the_beat_exceeds_15_pct": {
        "verdict": "CONFIRMED, and larger than predicted.",
        "measured": "+30.6% on the per-level time over the same three banks, and "
                    "TWO LEVELS of depth (5 of 6 -> 3 of 6).",
    },
    "Q2_the_TRANSPARENT_path_will_be_the_failing_path": {
        "verdict": "FALSIFIED -- the path makes NO DIFFERENCE.",
        "measured": "over the 336 scored cell-instances of all 14 converged rows, "
                    "89 of 252 RESTORED cells fail (35.3%) and 29 of 84 TRANSPARENT "
                    "cells fail (34.5%).  The rates are equal to within 0.8 "
                    "percentage points.",
        "AND_A_BASE_RATE_ERROR_I_ALMOST_MADE": "the RAW counts are 89 R against 29 "
                    "T, which looks like the restored path failing three times as "
                    "often.  It is not: the pre-registered mix is 3 RESTORED + 1 "
                    "TRANSPARENT per bank by construction, so 3:1 is exactly the "
                    "population ratio.  Only the RATE is informative, and it says "
                    "the path is irrelevant.  An earlier draft of this section "
                    "reported the counts.",
        "why_it_does_not_matter": "the failure is set by the successor's crowbar and "
                    "by the absence of gain, and neither distinguishes the two TG "
                    "paths.",
    },
    "Q3_QAL_will_not_beat_the_load_matched_2fF_57.1428_ps_level_ratio_above_4x": {
        "verdict": "CONFIRMED.",
        "measured": "6.36x at the sustained beat; 4.18x on the most generous "
                    "per-level figure.  Both above 4x.",
    },
    "Q4_crossover_D_star_below_2": {
        "verdict": "CONFIRMED against the load-matched comparator; one of the four "
                   "readings exceeds 2.",
        "measured": "D* = 1.03 (sustained beat, 2 fF), 1.74 (per-level, 2 fF), "
                    "1.25 (sustained beat, 6.91 fF), 2.32 (per-level, 6.91 fF).",
    },
    "Q5_the_chain_WILL_compute_all_24_gates_at_some_T": {
        "verdict": "FALSIFIED, and this is the headline.",
        "measured": "the pre-registered TG-XOR bank reaches depth 1 of 6 at every "
                    "beat.  The restoring variant reaches 3 of 6 with the PDK "
                    "interconnect and 5 of 6 without it.  24 of 24 gates never "
                    "happens.  I gave this 'moderate' confidence and said the "
                    "negative would be the headline if it came; it did.",
    },
    "Q6_the_L6_functional_optimum_will_cascade_WORSE_than_L15": {
        "verdict": "CONFIRMED.",
        "measured": "the only L = 6 nH / VGH = 2.174 V row reaches depth 1 of 6 "
                    "with a 1539.0 ps own-level time, against L = 15 nH's 275.8 ps "
                    "at depth 2 in the same arrangement.  Phase 1's prediction "
                    "about its own functional optimum holds on a real chain.",
    },
}

R["I_WHAT_IS_A_BOOKING AND WHAT THIS PHASE DOES NOT LICENSE"] = [
    "Bank 1's cell inputs are IDEAL DC sources at VINHI = 1.20 V.  Bank 1's row is "
    "a BOUND; the verdict rests on the deeper banks.",
    "Every tank pre-charge is an .ic on an ideal capacitor and the recharge is not "
    "costed, so every energy figure is a BOUND.  Energy gates nothing here.",
    "Interconnect is present ONLY as the declared rotate/straight pi segments.  "
    "Rail routing, tank routing, switch routing and cell-internal layout "
    "parasitics are still absent, so even the W2 rows remain optimistic BOUNDS.",
    "The sg13lv_compat shim DISCARDS ad/as/pd/ps, so JUNCAP200 runs on defaults and "
    "the default PD = 1.00 um is smaller than the 1.12 um pMOS: every leakage "
    "figure is a LOWER bound.",
    "VGH = 2.174/2.4 V is an OVERDRIVE on a 1.5 V-tolerant LV device and the oxide "
    "reliability question is UNANSWERED.  The whole result rests on that device ask, "
    "exactly as Phase 1's frontier did.",
    "The inductors are ideal L with a lumped RS = 10 ohm.  On-die inductor Q, area "
    "and coupling are modelled nowhere in this campaign.",
    "The returns are DISABLED on every beat deck (AMENDMENT P5).  The scored "
    "boundaries are provably identical with and without them, but no energy-recovery "
    "number in this phase is measured on a deck that actually returned its charge, "
    "and the K5 IZQ gate is UNTESTED rather than passed.",
    "Three of five synchronous rows and all four original skewed rows have caveats "
    "named in AMENDMENT.md (non-convergence, and the P8 companion defect).  They are "
    "listed, not estimated.",
]

json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
print("wrote RESULTS.json  (%d bytes)"
      % os.path.getsize(os.path.join(HERE, "RESULTS.json")))
