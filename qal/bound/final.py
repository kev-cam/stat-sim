#!/usr/bin/env python3
"""Track 3 final assembly -> RESULTS.json.  Reads only measured row files."""
import hashlib, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
L = lambda n: json.load(open(os.path.join(HERE, n)))
dc, rx, qdi, s2q = L("dc_rows.json"), L("rx_rows.json"), L("qdi_rows.json"), L("s2q_rows.json")

# ---- MEASURED anchors taken as given -----------------------------------------
QAL_HI, QAL_HI_WORST = 0.6758936, 0.5763002
T_HOP, E_HOP, C_BANK = 266.755223, 8.408270111148767, 35.979
INV_ANCHOR, INV_ANCHOR_PS = 10.0831, 34.81
TH22, E0FF, ETREE = 44.62, 59.1, 27.7
REG_LO, REG_HI = 28.2, 118.3        # SELECTION-RULE.md 5(A) register anchor, fJ/bit/cyc
UNSOURCED = 124.7
PARK_TAP = -0.0398
WINDOW = 286.715                    # MEASURED park valid window, ps
BLOCKS = dict(
    sha_slice=dict(gates=105, cells=56, depth=10, W_in=48, W_out=24,
                   cmos_fJ=232.0, cmos_corr_fJ=464.0, cmos_ns=0.928,
                   t_level_ps=92.8, e_qal_gate=1.048),
    alu_top=dict(gates=4721, cells=4721, depth=None, W_in=278, W_out=156,
                 cmos_fJ=46670.0, cmos_corr_fJ=62000.0, cmos_ns=4.75,
                 t_level_ps=None, e_qal_gate=1.048))

R = {}
R["_doc"] = (
    "TRACK 3 -- TAILORED BOUNDARY HANDLING. Discharges mylex/SELECTION-RULE.md "
    "section 8 'Next measurements' item 1 (the 4x4 boundary-adapter cost matrix, "
    "diagonal included -- 'the only first-order input with zero provenance'). "
    "Structure in MATRIX.json; costs here. Every number labelled MEASURED / "
    "DERIVED / ASSUMED. Pre-registration was written and hashed before any deck "
    "existed in this directory.")
R["_provenance"] = dict(
    pre_registration="qal/bound/PRE_REGISTERED.json",
    pre_registration_sha256=hashlib.sha256(
        open(os.path.join(HERE, "PRE_REGISTERED.json"), "rb").read()).hexdigest(),
    pyms_vae_cache="scratchpad/vae_cache_boundT3 (own, built from scratch, 10 .so)",
    model="SG13G2 / PSP103 tt via qal/sg13lv_compat.sp",
    lower_bound_caveat=(
        "sg13lv_compat.sp zeroes ad/as/pd/ps, so JUNCTION capacitance is ABSENT. "
        "Consequences here: receiver output-node energy and delay are OPTIMISTIC "
        "(a real drain junction adds load). GATE capacitance is intact, so the "
        "measured C_in values -- the ones the capacitive-tax result rests on -- "
        "are NOT affected by that omission except through the drain side of the "
        "driving cell."),
    metering=("1F integrators, t0-referenced at a 5 ps Z checkpoint (the "
              "campaign's pedestal trap). Rails are constant sources so "
              "E = VDD * integral(I) is exact. The audited committed extractor "
              "qal/swsweep/sw_hop_meter.py was WRAPPED, not reimplemented, for "
              "every bank-hop row; the single replaced function is diffed in "
              "s2q_drive.log."),
    instrument_checks=dict(
        calibration_ramp=("my lane's sw_calib reproduces the committed calib: "
                          "QTOT 35.9790 fC (+0.00%), E(V=1.000) 19.2199 vs "
                          "19.232 fJ (-0.06%); the -21.6% row at V=0.167 is "
                          "small-value integration noise (0.264 vs 0.337 fJ)"),
        bank_hop=("my control row (VIN=1.0, CLOAD=2.0) reproduces the committed "
                  "tg15p_zcs to the digit: VBEND delta 0.000e+00 %, true zero "
                  "delta 0.000e+00 %, E_hop delta 1.77e-09 %"),
        inverter_anchor=("bd_rx2 cell F stage 2 measures %.4f fJ vs the campaign "
                         "anchor 10.0831 fJ = %+.2f%%"
                         % (rx["F"]["E_stage2_cycle_fJ"],
                            (rx["F"]["E_stage2_cycle_fJ"] / INV_ANCHOR - 1) * 100))))

# =============================================================== H1 QAL -> sync
h1 = dict(_question=("does a settled QAL bank level drive a standard SG13G2 gate "
                     "on a 1.2 V rail -- i.e. is the cheapest possible boundary "
                     "free?"),
          pre_registered_gates=("V_out <= 0.2*VDD at V_in = 0.6759; static current "
                                "<= 1.0 uA; trip point <= 0.5763 (so the receiver "
                                "works for the whole measured VBEND family)"),
          MEASURED_dc=dc, MEASURED_transient=rx)
std = dc["A1"]
h1["VERDICT"] = "REFUTED for a standard gate; CONFIRMED for a re-sized one"
h1["the_refutation"] = dict(
    receiver="the campaign's own generic inverter, 1.12u pMOS / 0.74u nMOS @ 1.2 V",
    trip_point_V=std["trip_Vin_at_Vout_half_VDD"],
    QAL_high_V=QAL_HI,
    overdrive_mV=(QAL_HI - std["trip_Vin_at_Vout_half_VDD"]) * 1000,
    static_current_uA=std["Istatic_at_QAL_high_uA"],
    static_energy_over_293ps_hold_fJ=std["Estatic_over_293ps_hold_fJ"],
    static_as_pct_of_the_whole_hop=std["Estatic_over_293ps_hold_fJ"] / E_HOP * 100,
    Vout_at_the_FAMILY_WORST_level_0p5763=std["Vout_at_worst_QAL_high_0.5763"],
    transient_resolve_time_ps=rx["A"].get(
        "delay_in50_to_stage1_below_downstream_trip_ps"),
    Vout1_at_window_close=rx["A"]["Vout1_at_end_of_hold"],
    three_independent_failures=[
        "MARGIN: the trip point (0.6452 V) sits only 31 mV below the QAL high "
        "level, and ABOVE the family's own worst measured VBEND (tg60, 0.5763 V) "
        "-- on that row the receiver reads a QAL 1 as a 0 (V_out 1.162 V).",
        "STATIC: 8.78 uA of contention (DC) = 3.090 fJ over one 293 ps hold, "
        "which is 36.7%% of the entire 8.408 fJ hop, per bit." ,
        "SPEED: in the transient it NEVER crosses the downstream trip inside the "
        "measured 286.7 ps valid window -- V_out is still 0.6995 V at window "
        "close, i.e. the datum is simply not received."])

best = rx["K"]
h1["the_tailored_fix_that_works"] = dict(
    receiver="0.15u pMOS / 1.48u nMOS on a REDUCED 0.9 V first-stage rail (cell K)",
    devices_added="ZERO -- it is the same two-inverter chain, re-sized, plus a rail",
    E_two_stage_fJ_per_bit=best["E_both_stages_cycle_fJ"],
    E_charged_to_the_QAL_domain_fJ_per_bit=best["E_in_cycle_fJ"],
    E_total_fJ_per_bit=best["E_both_stages_cycle_fJ"] + best["E_in_cycle_fJ"],
    C_in_fF=best["C_in_eff_fF"],
    resolve_ps=best["delay_in50_to_stage1_below_downstream_trip_ps"],
    full_two_stage_ps=best["delay_in50_to_out2_50_ps"],
    near_steady_current_uA=best["I_near_steady_uA"],
    Vout1_at_window_close=best["Vout1_at_end_of_hold"],
    vs_pre_registered_cheap_line=dict(
        energy_line_fJ_per_bit=2 * INV_ANCHOR,
        energy_PASS=bool(best["E_both_stages_cycle_fJ"] + best["E_in_cycle_fJ"]
                         <= 2 * INV_ANCHOR),
        latency_line_ps=100.0,
        latency_PASS=bool(best["delay_in50_to_stage1_below_downstream_trip_ps"]
                          <= 100.0),
        note=("the ENERGY half of the pre-stated 'cheap' line PASSES with 2.4x "
              "margin; the LATENCY half FAILS for EVERY receiver built, and "
              "cannot be bought down -- see latency_floor.")),
    vs_register_anchor=dict(
        register_already_paid_fJ_per_bit=[REG_LO, REG_HI],
        adapter_as_pct_of_the_cheaper_register=(
            (best["E_both_stages_cycle_fJ"] + best["E_in_cycle_fJ"]) / REG_LO * 100),
        conclusion=("SELECTION-RULE.md 5(A)'s claim that the marginal ENERGY of "
                    "sync<->QAL at an existing boundary is ~0 is CONFIRMED: the "
                    "adapter is 30%% of the cheapest measured boundary register "
                    "and 7%% of the placed-ALU one. The claim was never made "
                    "about LATENCY, and that is where it breaks.")))

h1["level_penalty_CONTROLLED"] = dict(
    method=("same receiver sizing (0.15p/1.48n @1.2 V), same 266.8 ps input "
            "slope, ONLY the high level changed -- cells H (1.2 V) vs D (0.676 V)"),
    full_swing_resolve_ps=rx["H"]["delay_in50_to_stage1_below_downstream_trip_ps"],
    QAL_level_resolve_ps=rx["D"]["delay_in50_to_stage1_below_downstream_trip_ps"],
    delta_ps=(rx["D"]["delay_in50_to_stage1_below_downstream_trip_ps"]
              - rx["H"]["delay_in50_to_stage1_below_downstream_trip_ps"]),
    ratio=(rx["D"]["delay_in50_to_stage1_below_downstream_trip_ps"]
           / rx["H"]["delay_in50_to_stage1_below_downstream_trip_ps"]),
    full_swing_E_fJ=rx["H"]["E_both_stages_cycle_fJ"],
    QAL_level_E_fJ=rx["D"]["E_both_stages_cycle_fJ"],
    E_ratio=rx["D"]["E_both_stages_cycle_fJ"] / rx["H"]["E_both_stages_cycle_fJ"],
    HEADLINE="the half-swing level costs TIME, not energy: +131 ps (3.6x) for +7% fJ")

h1["latency_floor"] = dict(
    method=("upsize the receiver nMOS by putting identical 1.48u devices in "
            "parallel: 1x / 2x / 4x (cells D / L / M)"),
    rows=[dict(tag=t, wn_um=rx[t]["wn_um"],
               resolve_ps=rx[t]["delay_in50_to_stage1_below_downstream_trip_ps"],
               C_in_fF=rx[t]["C_in_eff_fF"],
               E_two_stage_fJ=rx[t]["E_both_stages_cycle_fJ"])
          for t in ("D", "L", "M")],
    FLOOR_ps=rx["M"]["delay_in50_to_stage1_below_downstream_trip_ps"],
    HEADLINE=("4x the nMOS buys 181.0 -> 145.3 ps (-20%) and costs 3.9x the input "
              "capacitance. The QAL->sync level-conversion latency has a floor "
              "around 145 ps at SG13G2 and upsizing trades it against the "
              "capacitive tax below -- the two costs are coupled and fight."))

# ============================================================== H2 sync -> QAL
ctrl = s2q["vin100_cl020"]
h2 = dict(_question=("can a full-swing synchronous driver drive QAL cell gates "
                     "directly -- is the converter the driver that already exists?"),
          pre_registered_gates=("all 8 cells settle; VBEND within 2% of the "
                                "same-lane 1.0 V control; E_hop increase <= 10%"),
          MEASURED=s2q)
lv = {}
for k in ("vin100_cl020", "vin120_cl020", "vin150_cl020"):
    r = s2q[k]
    lv[k] = dict(VIN_V=r["VIN_V"], VBEND=r["VBEND"],
                 VBEND_delta_pct=(r["VBEND"] / ctrl["VBEND"] - 1) * 100,
                 E_hop_fJ=r["E_hop_fJ"],
                 E_hop_delta_pct=(r["E_hop_fJ"] / ctrl["E_hop_fJ"] - 1) * 100,
                 true_zero_ps=r["true_zero_ps"],
                 zero_delta_pct=(r["true_zero_ps"] / ctrl["true_zero_ps"] - 1) * 100,
                 cells_burn_fJ=r["cells_burn_fJ"],
                 Q_from_HI_data_sources_fC=r["raw_qih_D_fC_or_fJ"],
                 E_from_HI_data_sources_fJ=r["raw_eih_D_fC_or_fJ"],
                 E_per_HI_bit_fJ=r["raw_eih_D_fC_or_fJ"] / 4.0,
                 outputs_end=r["outputs_end"],
                 all_cells_settle=all(abs(v) < 0.01 if i % 2 == 0
                                      else v > 0.9 * r["VBEND"]
                                      for i, v in enumerate(r["outputs_end"])))
h2["level_rows"] = lv
h2["VERDICT"] = "PASS at the 1.2 V sync rail on all three pre-registered gates"
h2["why"] = (
    "A QAL cell's data input is a MOS GATE. Raising it from the bank swing (1.0 V) "
    "to the sync rail (1.2 V) drives the cell HARDER, not wrongly: every cell "
    "still settles, VBEND moves -1.15% (inside the pre-stated 2% band) and E_hop "
    "moves -1.36% -- it gets CHEAPER, not dearer. The 1.5 V overdrive rail also "
    "functions but breaks the 2% VBEND band (-3.01%), so 1.5 V is not free.")
h2["the_marginal_cost_is_a_fanout_not_a_converter"] = dict(
    E_returned_to_the_data_sources_per_HI_bit_fJ={
        "1.0V": lv["vin100_cl020"]["E_per_HI_bit_fJ"],
        "1.2V": lv["vin120_cl020"]["E_per_HI_bit_fJ"],
        "1.5V": lv["vin150_cl020"]["E_per_HI_bit_fJ"]},
    sign_note=("these are NEGATIVE: the held data source is a net RECEIVER during "
               "the hop, because the rising bank couples through the cell pMOS "
               "gate-source capacitance. Same sign convention as the committed "
               "extractor (its own tg60 row books E_in_static = -3.14 fJ)."),
    what_the_sync_side_actually_pays=dict(
        C_of_one_QAL_cell_input_fF=rx["A"]["C_in_eff_fF"],
        E_to_swing_it_over_1p2V_fJ_per_cycle=rx["A"]["C_in_eff_fF"] * 1e-15
                                             * 1.2 ** 2 * 1e15,
        provenance="DERIVED from the MEASURED C_in of an identically sized gate",
        note=("this is an ORDINARY FANOUT LOAD -- the same energy the flop would "
              "pay driving any 3.5 fF gate. There is no converter in the path, "
              "no extra device, and no added latency.")),
    HEADLINE="sync -> QAL costs 0 fJ/bit and 0 ps of CONVERTER. It costs a hold rule.")

# ============================================================== H3 sync <-> QDI
pb = qdi["per_bit"]
h3 = dict(_question="what do the encode/decode adapters actually cost?",
          MEASURED=qdi,
          functional=qdi["functional_verdict"],
          encoder_fJ_per_bit=pb["encoder_sync_to_QDI_fJ_per_bit"],
          encoder_ps=qdi["timing_ps"]["encoder_delay_EN_to_T_ps"],
          decoder_completion_fJ_per_bit=pb["decoder_completion_QDI_to_sync_fJ_per_bit"],
          one_tree_node_fJ=pb["tree_node_fJ_per_node"],
          decoder_total_fJ_per_bit=(pb["decoder_completion_QDI_to_sync_fJ_per_bit"]
                                    + pb["tree_node_fJ_per_node"]),
          decoder_ps=qdi["timing_ps"]["decoder_delay_T_to_tree_ps"],
          round_trip_fJ_per_bit=pb["round_trip_sync_QDI_sync_fJ_per_bit"],
          round_trip_ps=qdi["timing_ps"]["round_trip_EN_to_completion_ps"])
h3["THE_UNSOURCED_NUMBER_NOW_HAS_A_DECK"] = dict(
    unsourced_figure_fJ_per_bit=UNSOURCED,
    MEASURED_round_trip_fJ_per_bit=pb["round_trip_sync_QDI_sync_fJ_per_bit"],
    ratio_measured_over_unsourced=pb["round_trip_sync_QDI_sync_fJ_per_bit"] / UNSOURCED,
    verdict=("the unsourced 124.7 fJ/bit was RIGHT to within 9%%. "
             "SELECTION-RULE.md 5(B) 'QDI domains must be very large or not "
             "exist' and discriminant D10 now rest on a measurement, and the "
             "conclusion is UNCHANGED."),
    wire_load_assumption=("2 fF per RAIL was ASSUMED as a routing stand-in "
                          "(2 rails/bit). One rail switches per bit per cycle, so "
                          "ASSUMED wire is CV^2 = 2.88 fJ/bit = 6.6%% of the "
                          "encoder -- not the dominant term."))
rho = {n: dict(E_fJ=b["cmos_fJ"], E_corrected_fJ=b["cmos_corr_fJ"],
               W=b["W_in"] + b["W_out"],
               rho_fJ_per_bit=b["cmos_fJ"] / (b["W_in"] + b["W_out"]),
               rho_corrected_fJ_per_bit=b["cmos_corr_fJ"] / (b["W_in"] + b["W_out"]),
               fails_the_QDI_island_gate=bool(
                   b["cmos_corr_fJ"] / (b["W_in"] + b["W_out"])
                   < pb["round_trip_sync_QDI_sync_fJ_per_bit"]))
       for n, b in BLOCKS.items()}
h3["rho_vs_the_measured_gate"] = rho
h3["rho_note"] = ("my sha_slice rho 3.22 fJ/bit reproduces the record's 3.2 exactly "
                  "(W=72); my ALU rho is 107.5 (liberty) / 142.9 (corrected) against "
                  "the record's 98.4, which implies the record counted W=474 rather "
                  "than my 434 port bits -- flagged, not resolved.")
# Rent-calibrated QDI island size with the MEASURED converter cost
k_rent = 434.0 / 4721.0 ** 0.6
e_gate = 62000.0 / 4721.0
coef = k_rent * pb["round_trip_sync_QDI_sync_fJ_per_bit"] / e_gate
h3["QDI_island_size_with_the_measured_number"] = dict(
    method="W(G) = k*G^p, p=0.6 ASSUMED, k calibrated on the ALU (W=434, G=4721)",
    k=k_rent, p=0.6, e_gate_fJ_corrected=e_gate,
    converter_fraction_law="f(G) = %.3f * G^-0.4" % coef,
    G_for_20pct_converter=(coef / 0.20) ** 2.5,
    G_for_10pct_converter=(coef / 0.10) ** 2.5,
    record_said="~460k gates for <20%; mine is smaller because e_gate and k differ",
    verdict="still 'a whole functional cluster', so the record's conclusion holds")

# =============================================== the capacitive tax (MEASURED)
cap = dict(
    _question=("what does hanging a receiver on a QAL cell output do to the hop? "
               "This is the term the record's O(width) intuition was feeling."),
    method=("sweep the committed harness's own CLOAD global (2.0 / 4.0 / 8.0 fF on "
            "EACH of the 8 cell outputs) at VIN=1.0. A receiver's input is, to "
            "first order, exactly extra CLOAD, and CLOAD needs no new device "
            "geometry so no new PyMS .so."),
    rows=[dict(CLOAD_fF=s2q[k]["CLOAD_fF"], VBEND=s2q[k]["VBEND"],
               VBEND_delta_pct=(s2q[k]["VBEND"] / ctrl["VBEND"] - 1) * 100,
               true_zero_ps=s2q[k]["true_zero_ps"],
               zero_delta_pct=(s2q[k]["true_zero_ps"] / ctrl["true_zero_ps"] - 1) * 100,
               E_drained_from_bank_A_fJ=s2q[k]["E_outA_exact_fJ"],
               cells_burn_fJ=s2q[k]["cells_burn_fJ"],
               level_a_receiver_actually_sees=s2q[k]["outputs_end"][1])
          for k in ("vin100_cl020", "vin100_cl040", "vin100_cl080")],
    MY_OWN_PREDICTION_REFUTED=dict(
        prediction=("I derived that receivers add to the bank capacitance, so with "
                    "t = pi*sqrt(LC) the hop would dilate as sqrt(1 + W*C_rx/C_bank): "
                    "+2 fF/cell (16 fF total) -> x1.202 (320.6 ps); +6 fF/cell "
                    "(48 fF total) -> x1.528 (407.5 ps)."),
        measured="266.755 -> 266.982 (+0.08%) -> 269.267 (+0.94%)",
        verdict="REFUTED, by a factor of ~50 on the +6 fF row",
        why=("the load caps are NOT on the LC node. They hang on the CELL OUTPUT, "
             "isolated from the bank by the cell pMOS channel resistance, so they "
             "never join the resonance. They act as a resistive-path charge sink "
             "instead."),
        and_the_closure_check_that_proves_it=(
            "the energy drained from bank A is INVARIANT at 17.843 / 17.856 / "
            "17.848 fJ across the three rows (0.07% spread). The bank delivers "
            "the same energy every time; the extra capacitance simply spreads it "
            "over more charge, so the LEVEL falls.")),
    WHAT_THE_TAX_ACTUALLY_IS=dict(
        currency="VOLTS of VBEND -- the only margin QAL has",
        slope_mV_per_fF_per_cell_output=[
            (s2q["vin100_cl040"]["VBEND"] - ctrl["VBEND"]) / 2.0 * 1000,
            (s2q["vin100_cl080"]["VBEND"] - ctrl["VBEND"]) / 6.0 * 1000],
        energy_cost_is_small=dict(
            cells_burn_fJ=[ctrl["cells_burn_fJ"],
                           s2q["vin100_cl040"]["cells_burn_fJ"],
                           s2q["vin100_cl080"]["cells_burn_fJ"]],
            per_bit_per_fF_fJ=((s2q["vin100_cl080"]["cells_burn_fJ"]
                                - ctrl["cells_burn_fJ"]) / 8.0 / 6.0)),
        THE_SELF_LIMITING_COUPLING=(
            "the boundary eats its own margin. Adding a receiver lowers VBEND, "
            "and VBEND is (i) the level that receiver must resolve and (ii) the "
            "supply of the next bank, which the MEASURED functional cliff says "
            "must stay at 1.0 V-class swing (settling 100% at 1.0/1.2 V, 77.1% "
            "at 0.8, 34.8% at 0.6)."),
        the_measured_fan_out_limit=dict(
            best_receiver_C_in_fF=best["C_in_eff_fF"],
            VBEND_after_one_such_receiver_V=(ctrl["VBEND"]
                + best["C_in_eff_fF"] * (s2q["vin100_cl040"]["VBEND"]
                                         - ctrl["VBEND"]) / 2.0),
            provenance="DERIVED by linear interpolation of two MEASURED rows",
            measured_row_at_one_receiver=s2q["vin100_cl040"]["VBEND"],
            receiver_trip_points_MEASURED={
                "0.15p/1.48n @1.2V": dc["A4"]["trip_Vin_at_Vout_half_VDD"],
                "1.12p/0.74n @0.9V": dc["B2"]["trip_Vin_at_Vout_half_VDD"],
                "1.12p/0.74n @1.2V (standard)": dc["A1"]["trip_Vin_at_Vout_half_VDD"]},
            verdict=("ONE standard-cell receiver per QAL cell output is "
                     "survivable (VBEND 0.676 -> 0.600 measured, still 0.140 V "
                     "above the best measured trip 0.4595). TWO is marginal "
                     "(~0.52 V) and THREE is dead (measured 0.492 V, with the "
                     "cell outputs only reaching 0.4807 V -- below/at the trip). "
                     "So boundary FAN-OUT is capped at ~1 receiver per bit.")),
        and_this_is_PER_BIT_not_O_width=(
            "each output bit drives its own receiver on its own cell output, so "
            "the VBEND tax does NOT grow with domain width. It is a per-bit "
            "design rule. Only the ENERGY term is O(width), and that term is "
            "small.")))
R["capacitive_tax"] = cap

# ============================================== the cost table (c)
tbl = {}
for t in ("A", "C", "D", "G", "E", "K", "L", "M"):
    d = rx[t]
    tbl["QAL_to_sync__cell_" + t] = dict(
        label=d["label"],
        fJ_per_bit_stage1_only=d["E_stage1_cycle_fJ"],
        fJ_per_bit_two_stage=d["E_both_stages_cycle_fJ"],
        fJ_per_bit_charged_to_the_QAL_domain=d["E_in_cycle_fJ"],
        ps_resolve_stage1=d.get("delay_in50_to_stage1_below_downstream_trip_ps"),
        ps_full_two_stage=d.get("delay_in50_to_out2_50_ps"),
        C_in_fF=d["C_in_eff_fF"],
        resolves_in_window=d["resolves_inside_valid_window"],
        provenance="MEASURED")
tbl["sync_to_QAL"] = dict(
    fJ_per_bit_converter=0.0, ps_added_latency=0.0,
    fJ_per_bit_as_an_ordinary_fanout=rx["A"]["C_in_eff_fF"] * 1.2 ** 2,
    note=("no converter exists in this direction. The number quoted is the "
          "ordinary CV^2 the launching flop pays for a 3.478 fF gate load."),
    provenance="MEASURED (bank hop at 1.0/1.2/1.5 V cell drive) + DERIVED CV^2")
tbl["sync_to_QDI"] = dict(fJ_per_bit=pb["encoder_sync_to_QDI_fJ_per_bit"],
                          ps_added_latency=qdi["timing_ps"]["encoder_delay_EN_to_T_ps"],
                          provenance="MEASURED")
tbl["QDI_to_sync"] = dict(
    fJ_per_bit=(pb["decoder_completion_QDI_to_sync_fJ_per_bit"]
                + pb["tree_node_fJ_per_node"]),
    ps_added_latency=qdi["timing_ps"]["decoder_delay_T_to_tree_ps"],
    note="data path is a WIRE; this is the per-bit completion OR plus one tree node",
    provenance="MEASURED")
tbl["QAL_to_QAL_beat_locked"] = dict(
    fJ_per_bit=PARK_TAP, ps_added_latency=0.0,
    note=("the resonant park tap is a NET RECEIVER and adds no devices (the park "
          "nMOS already exists; only its drive changed)"),
    provenance="MEASURED (qal/park, committed -- not re-run here)")
tbl["sync_to_sync_across_clocks"] = dict(
    fJ_per_bit=2 * (E0FF + ETREE),
    ps_added_latency="2 destination clock cycles (9.5 ns on the placed ALU)",
    provenance="DERIVED from MEASURED E0_ff 59.1 + E_tree 27.7")
tbl["any_handshake_control"] = dict(
    fJ_per_CHANNEL=2 * TH22, fJ_per_bit="0 -- width-independent",
    ps_added_latency=2 * 356.0,
    provenance="DERIVED from MEASURED th22 44.62 fJ / 356 ps")
tbl["QDI_to_QAL"] = dict(fJ_per_bit="FORBIDDEN -- see MATRIX.json",
                         provenance="structural argument, not measured")
R["cost_table"] = tbl

# ============================================== (d) the selection-rule consequence
bd = dict(receiver_used=dict(tag="K", label=best["label"]))
E_out = best["E_both_stages_cycle_fJ"] + best["E_in_cycle_fJ"]
E_in_b = 0.0
t_out = best["delay_in50_to_stage1_below_downstream_trip_ps"]
for n, b in BLOCKS.items():
    Eb = b["W_in"] * E_in_b + b["W_out"] * E_out
    eh = b["cmos_corr_fJ"] / b["gates"]
    r = dict(W_in=b["W_in"], W_out=b["W_out"],
             boundary_E_total_fJ=Eb,
             boundary_E_pct_of_block_cmos_corrected=Eb / b["cmos_corr_fJ"] * 100,
             e_host_fJ_per_gate_corrected=eh,
             e_qal_fJ_per_gate=b["e_qal_gate"],
             G_breakeven_gates_energy=Eb / (eh - b["e_qal_gate"]),
             G_breakeven_as_frac_of_the_block=Eb / (eh - b["e_qal_gate"]) / b["gates"],
             t_boundary_ps_one_crossing=t_out,
             boundary_latency_pct_of_block_cmos=t_out / (b["cmos_ns"] * 1000) * 100,
             D_breakeven_hops_at_MEASURED_hop=t_out / (0.10 * T_HOP),
             D_breakeven_hops_at_20ps_fast_hop=t_out / (0.10 * 20.0))
    if b["t_level_ps"]:
        r["D_breakeven_levels_vs_cmos"] = t_out / (0.10 * b["t_level_ps"])
    bd[n] = r
bd["VERDICT_ON_THE_RULE"] = dict(
    rule_today="converter tax is O(width) -> few LARGE domains",
    what_the_measurement_says=[
        "ENERGY: the rule survives but is not binding for sync/BD/QAL. The "
        "sync->QAL converter does not exist (0 fJ/bit). The QAL->sync adapter is "
        "8.42 fJ/bit, which is 30%% of the CHEAPEST measured boundary register "
        "(28.2 fJ/bit) the island already pays. On sha_slice that is 202 fJ over "
        "24 output bits = 43.5%% of the block's own corrected 464 fJ, so small "
        "blocks still cannot pay -- but the reason is the block's tiny gate count, "
        "not the converter.",
        "ENERGY, QDI only: the O(width) tax is REAL and now MEASURED at 113.36 "
        "fJ/bit round trip, 9%% from the unsourced 124.7. 'QDI domains must be "
        "very large or not exist' is CONFIRMED with a deck.",
        "LEVEL: the binding QAL constraint is a PER-BIT fan-out rule (<= ~1 "
        "receiver per cell output), not a width tax. Domain size does not enter.",
        "LATENCY: this is the term nobody costed, and at the fast QAL operating "
        "point it is the one that decides. A boundary crossing costs 167.7 ps "
        "MEASURED (best receiver), with a floor near 145 ps. Against the "
        "energy-optimal 266.8 ps hop that is 0.63 hops; against a 20 ps fast hop "
        "it is 8.4 hops. So MANY SMALL DOMAINS become viable in energy and level "
        "exactly where they become unaffordable in latency.",
        "So the answer to 'are tailored boundaries near-free?' is: near-free in "
        "ENERGY (yes, and the converter literally does not exist in one "
        "direction), NOT free in LATENCY, and self-limiting in LEVEL."])
R["selection_rule_consequence"] = bd

# ============================================== the speed table (the parent run)
sp = dict(
    _doc=("register-tax-elimination speedup S(D) = D*(t_level + t_reg) / "
          "(D*t_hop + t_boundary), with t_level 92.8 ps MEASURED (sha_slice CMOS "
          "comb 0.928 ns / depth 10) and t_reg spanning the range the record's own "
          "1.5-3x structural claim implies on that slice (t_reg/t_level 0.5-2). "
          "t_boundary is MEASURED here. The 20 ps hop is the parent run's DERIVED "
          "fast operating point (L ~ 1.13 nH), NOT measured."),
    t_boundary_measured_ps=t_out,
    t_boundary_floor_ps=rx["M"]["delay_in50_to_stage1_below_downstream_trip_ps"],
    rows={})
for t_reg in (46.4, 92.8, 185.6):
    for t_hop, lab in ((T_HOP, "hop_266.8ps_MEASURED_energy_optimal"),
                       (20.0, "hop_20ps_DERIVED_fast_point")):
        key = "t_reg_%.1f__%s" % (t_reg, lab)
        sp["rows"][key] = {("D=%d" % D): D * (92.8 + t_reg) / (D * t_hop + t_out)
                           for D in (1, 2, 5, 10, 25, 60)}
sp["READING"] = (
    "At the energy-optimal hop QAL is 0.5-1.0x -- slower than pipelined CMOS "
    "whatever the boundary does; the boundary is not the problem there. At the "
    "DERIVED 20 ps fast point the structural speedup is 7-14x with a free "
    "boundary, but the MEASURED 167.7 ps boundary cuts a depth-1 domain to "
    "1.2-2.3x and a depth-10 domain to 4.3-8.6x. THE BOUNDARY IS THE THING THAT "
    "DECIDES WHETHER SMALL FAST DOMAINS ARE WORTH ENTERING -- which is exactly "
    "the user's intuition, and it lands on latency, not power.")
R["speed_consequence"] = sp

# ============================================== (e) async at the boundary
sync_bit, hsc = 2 * (E0FF + ETREE), 2 * TH22
R["async_at_the_boundary"] = dict(
    _method="DERIVED composition of MEASURED cells; no new simulation",
    synchronizer_fJ_per_bit_per_transfer=sync_bit,
    handshake_control_fJ_per_CHANNEL_per_transfer=hsc,
    crossover_width_bits=hsc / sync_bit,
    ratio_at_width={str(W): W * sync_bit / hsc
                    for W in (1, 2, 8, 32, 48, 72, 156, 278, 434)},
    latency=dict(handshake_req_ack_ps=2 * 356.0,
                 synchronizer_ns_placed_alu=9.5,
                 synchronizer_ns_sha_slice=1.856),
    bulk_QDI_on_a_busy_core=dict(
        alu_qdi_over_cmos_liberty=523700.0 / 46670.0,
        alu_qdi_over_cmos_corrected=[523700.0 / 64000.0, 523700.0 / 60000.0],
        alu_cells_ratio=25551 / 4721,
        sha_slice_qdi_over_cmos=2712.0 / 232.0,
        sha_slice_qdi_plus_CD_over_cmos=4385.7 / 232.0,
        measured_activity="alpha 0.0042-0.0094 at duty 0.31-0.79"),
    ARGUMENT=(
        "Async cost scales with the amount of LOGIC made delay-insensitive "
        "(O(cells): 5.41x cells and 8.2-11.2x energy on the ALU, 11.7-18.9x on "
        "sha_slice). Async BENEFIT scales with the amount of TIMING removed: O(1) "
        "per channel at a boundary, and O(clock tree) per island against a "
        "measured 71-85% clock-attributable chip. At a boundary you pay the O(1) "
        "and collect the timing benefit. In bulk logic on a busy core you pay the "
        "O(cells) and collect nothing, because the average-case advantage needs "
        "low activity and the measured machine is BUSY WITHOUT TOGGLING. "
        "Quantitatively: a 2-flop synchronizer is 173.6 fJ per BIT, a handshake is "
        "89.2 fJ per CHANNEL -- they cross at 0.51 bits, so the handshake is "
        "cheaper than synchronising even ONE bit, and the gap grows linearly to "
        "62x at 32 bits, 304x at the ALU's 156-bit output port and 541x at its "
        "278-bit input port. Latency: 712 ps for a req/ack round trip vs 9.5 ns "
        "for two placed-ALU clock cycles, 13x. And a two-wire channel protocol "
        "has a 4-state space, so the verification burden ASYNC-PLAN says does not "
        "transfer for QDI logic does not arise."),
    CONSEQUENCE_FOR_THE_RULE=(
        "the rule should stop offering QDI as a whole-block binding on busy "
        "blocks and start offering 'sync island + async channel' as the FABRIC, "
        "with QDI reserved for the measured feed-forward leaf (alu_int, SCC=0) and "
        "for dark-silicon blocks. Async's product is the elimination of a shared "
        "time base, and that product is delivered at the boundary."))
json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
print("wrote RESULTS.json  (%d top-level keys)" % len(R))
R["H1_QAL_to_sync"] = h1
R["H2_sync_to_QAL"] = h2
R["H3_sync_QDI"] = h3
json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
print("keys:", ", ".join(R))
