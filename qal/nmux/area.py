#!/usr/bin/env python3
"""(d) transistor count and area, including the n-well saving.

Every rule value below is MEASURED from the IHP-Open-PDK SG13G2 KLayout DRC
source at /usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.tech/klayout/tech/drc/,
quoted with its rule name.  The composition into a cell bounding box is DERIVED.

Cross-check (MEASURED): SG13G2 standard cells are on a 3.78 um row pitch with a
0.48 um width quantum -- sg13g2_inv_1 (the campaign's own 1.12p/0.74n cell) is
5.4432 um2 = 1.44 x 3.78 = 3 columns.  The repeating poly pitch this model
implies is Gat.a + SHARED = 0.13 + 0.38 = 0.51 um, i.e. **6.25 % WIDER than the
real 0.48 um quantum** -- the model is mildly PESSIMISTIC in x and does not
reproduce the foundry's own (staggered / shared-contact) packing.  That matters
not at all for the headline, because x is IDENTICAL for the nMOS-only and the TG
form and therefore CANCELS in the area ratio.  The ratio is a pure y-direction
result, and y is where the n-well lives.
"""
import json, os

R = {   # MEASURED from the PDK DRC deck (rule name -> um)
 "Act.a_min_activ_width":            0.15,
 "Act.b_min_activ_space":            0.21,
 "Act.c_min_sd_extension":           0.23,
 "Gat.a_min_poly_width_1p2V":        0.13,
 "Gat.b_min_poly_space":             0.18,
 "Gat.c_min_poly_endcap_over_activ": 0.18,
 "Gat.d_min_poly_space_to_activ":    0.07,
 "Cnt.a_cont_width":                 0.16,
 "Cnt.b_cont_space":                 0.18,
 "Cnt.c_activ_enclosure_of_cont":    0.07,
 "Cnt.f_cont_on_activ_space_to_poly":0.11,
 "NW.a_min_nwell_width":             0.62,
 "NW.b_min_nwell_space_same_net":    0.62,
 "NW.c_nwell_enclosure_of_pactiv":   0.31,
 "NW.d_nwell_space_to_ext_nactiv":   0.31,
 "NW.e_nwell_enclosure_of_tie":      0.24,
}
STD = {"row_height_um": 3.78, "width_quantum_um": 0.48,
       "sg13g2_inv_1_um2": 5.4432, "sg13g2_mux2_1_um2": 18.1440,
       "sg13g2_xor2_1_um2": 14.5152, "sg13g2_nand2_1_um2": 7.2576}

# x-extent of a 2-input pass strip: outer S/D + gate + shared node + gate + S/D
OUTER = R["Cnt.f_cont_on_activ_space_to_poly"] + R["Cnt.a_cont_width"] + \
        R["Cnt.c_activ_enclosure_of_cont"]                       # 0.34
SHARED = 2 * R["Cnt.f_cont_on_activ_space_to_poly"] + R["Cnt.a_cont_width"] + \
         2 * R["Cnt.c_activ_enclosure_of_cont"] - 2 * R["Cnt.c_activ_enclosure_of_cont"]
SHARED = 2 * R["Cnt.f_cont_on_activ_space_to_poly"] + R["Cnt.a_cont_width"]   # 0.38
XPASS = OUTER + R["Gat.a_min_poly_width_1p2V"] + SHARED + \
        R["Gat.a_min_poly_width_1p2V"] + OUTER                   # 1.32


def cells(w_n, w_p=None):
    w_p = w_n if w_p is None else w_p
    a_n = XPASS * w_n
    y_tg = w_n + R["NW.d_nwell_space_to_ext_nactiv"] + \
           R["NW.c_nwell_enclosure_of_pactiv"] + w_p + \
           R["NW.c_nwell_enclosure_of_pactiv"]
    y_tie = y_tg + R["Act.b_min_activ_space"] + R["Act.a_min_activ_width"] + \
            R["NW.e_nwell_enclosure_of_tie"]
    return {
     "w_n_um": w_n, "w_p_um": w_p,
     "nmos_only": {"devices": 2, "n_well": False,
                   "bbox_x_um": XPASS, "bbox_y_um": w_n,
                   "area_um2": a_n},
     "transmission_gate": {"devices": 4, "n_well": True,
                           "bbox_x_um": XPASS, "bbox_y_um": y_tg,
                           "area_um2": XPASS * y_tg,
                           "nwell_overhead_um_of_y": y_tg - w_n - w_p,
                           "_note": "n-well shared with neighbouring p-devices; "
                                    "no dedicated tie counted"},
     "transmission_gate_with_own_tie": {"devices": 4, "n_well": True,
                                        "bbox_y_um": y_tie,
                                        "area_um2": XPASS * y_tie},
     "area_ratio_tg_over_nmos": XPASS * y_tg / a_n,
     "area_ratio_tg_tie_over_nmos": XPASS * y_tie / a_n,
     "device_count_ratio": 2.0,
    }


def main():
    out = {"_doc": "(d) device count and DRC-grounded area, n-well broken out",
           "rules_MEASURED_from_PDK": R,
           "rules_source": "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.tech/"
                           "klayout/tech/drc/{feol,sg13g2_maximal}.drc",
           "x_extent_DERIVED": {
               "outer_sd_um": OUTER, "shared_node_um": SHARED,
               "two_input_pass_strip_x_um": XPASS,
               "repeating_poly_pitch_um": R["Gat.a_min_poly_width_1p2V"] + SHARED,
               "cross_check_vs_real_std_cell_quantum_um": STD["width_quantum_um"],
               "cross_check_error_pct": 100.0 * (
                   R["Gat.a_min_poly_width_1p2V"] + SHARED -
                   STD["width_quantum_um"]) / STD["width_quantum_um"],
               "_cross_check_verdict": "model is ~6 % PESSIMISTIC in x vs the "
                   "foundry's own packing. x is identical for both forms, so it "
                   "CANCELS in the area ratio; the ratio is a pure y result and "
                   "y is where the n-well lives."},
           "std_cell_anchors_MEASURED": STD,
           "by_width": {}}
    for w in (0.15, 0.30, 0.60, 1.20, 2.00):
        out["by_width"]["w%.2f" % w] = cells(w)
    # what a conventional restoring CMOS mux2/xor2 costs in the same PDK
    out["conventional_CMOS_reference_MEASURED"] = {
        "sg13g2_mux2_1_um2": STD["sg13g2_mux2_1_um2"],
        "sg13g2_xor2_1_um2": STD["sg13g2_xor2_1_um2"],
        "_caveat": "those cells are RESTORING and buffered (they drive a rail); "
                   "a pass structure is not. The comparison bounds what the "
                   "pass form saves only when a restoring stage is present "
                   "anyway -- which in QAL it is, as the next bank's cell."}
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "area.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
