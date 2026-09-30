#!/usr/bin/env python3
"""SKEPTIC block composition -- the unit-fairness audit.

THE PROBLEM.  The crossing is scored per gate against
    CMOS_BLOCK_PER_CELL_FJ = 4.14  =  232 fJ/op  /  56 cells
where 56 is the cell count of the COMMITTED CMOS netlist
(qal/synth/threeway/work/sha_slice.cmos.v -- 56 cells, DEPTH 8, profile
32/12/3/2/2/2/2/1, mostly 2-input complex cells: xnor2 x10, mux2 x8,
a21oi x6, nand2 x5, o21ai x5, nor2 x5, and only 3 inverters).

But the profile the campaign uses for QAL -- and the one the brief quotes for
the bank-width cap, 41/32/26/21/6/5/3/7/4/7/3/4/1/1 -- is `nand_mindepth` from
qal/sha256/REMAP.json: **161 cells at DEPTH 14**.  That is the remap the
campaign's own standing correction requires ("synthesise for WORST-CELL
SETTLING TIME, not cell count: the most restrictive library gave the FASTEST
block").

So the same function is 56 CMOS cells or 161 QAL cells, and the QAL gate in
every row of this sweep is a minimum-size INVERTER.  Scoring QAL's per-inverter
energy against (232 fJ / 56 complex cells) charges QAL for 56 cells while the
QAL implementation needs 161.  The SAME remap supplies the N<=41 width cap the
record does carry -- only half of it reaches the conclusion.

WHAT THIS SCRIPT DOES.  Fits E_bank = b + a*N to MY OWN measured rows (b = the
per-bank fixed cost, a = the marginal per-gate cost), then composes the whole
block both ways and reports the block-level ratio, including the infinite-lane
limit that is the most generous case QAL can ever reach.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS_BLOCK_FJ = 232.0          # committed: sha_slice CMOS, LOGIC ONLY (no clock)
CMOS_BLOCK_PS = 928.0
CMOS_CELLS = 56
CMOS_DEPTH_MAPPED = 8
CMOS_DEPTH_GENERIC = 10        # 105 generic gates; the 92.8 ps/level bar uses this
CMOS_DEVICES = 406
CMOS_WTOT_UM = 352.65
INV_WTOT_UM = 1.12 + 0.74        # one QAL bank gate = one min-size inverter

# MEASURED census from qal/sha256/REMAP.json + REMAP_CONSEQUENCE.json.
# profile / cells / depth / devices / W_tot_um
PROFILES = {
    "nand_mindepth_QAL": dict(
        profile=[41, 32, 26, 21, 6, 5, 3, 7, 4, 7, 3, 4, 1, 1],
        devices=552, wtot=513.36,
        why="the remap the brief's own bank profile comes from, and the one the "
            "campaign's WORST-CELL-SETTLING doctrine requires"),
    "shallow_mindepth": dict(
        profile=[41, 26, 26, 19, 2, 4, 3, 6, 4, 6, 4, 4, 1],
        devices=534, wtot=485.22, why="the other mindepth QAL-able remap"),
    "d2ok_mindepth": dict(
        profile=[32, 24, 22, 8, 3, 3, 5, 4, 4, 3, 2, 1],
        devices=456, wtot=409.32, why="the cheapest QAL-able remap"),
    "full_CMOS_library": dict(
        profile=[32, 12, 3, 2, 2, 2, 2, 1],
        devices=406, wtot=352.65,
        why="the committed CMOS netlist itself -- QAL CAN use it (no cell "
            "family fails) but then the level is set by o21ai at 3.12-3.55x "
            "an inverter, and the per-gate energy of a complex cell in a bank "
            "was never measured by anyone"),
}


def linfit(X, Y):
    n = len(X)
    sx, sy = sum(X), sum(Y)
    sxx = sum(x * x for x in X)
    sxy = sum(x * y for x, y in zip(X, Y))
    d = n * sxx - sx * sx
    a = (n * sxy - sx * sy) / d
    b = (sy - a * sx) / n
    yb = sy / n
    sst = sum((y - yb) ** 2 for y in Y)
    ssr = sum((y - (b + a * x)) ** 2 for x, y in zip(X, Y))
    return a, b, (1.0 - ssr / sst if sst else None)


def main():
    L = json.load(open(os.path.join(HERE, "SK_LEDGER.json")))
    S = [a for a in L if a["scale"] == 1.0 and "E6" not in a["tag"]]
    S.sort(key=lambda a: a["N"])
    if len(S) < 3:
        print("need >=3 main-series rows, have %d" % len(S))
        return

    out = {"_what": "SKEPTIC block composition from MY OWN rows",
           "_cmos": dict(block_fJ=CMOS_BLOCK_FJ, block_ps=CMOS_BLOCK_PS,
                         cells=CMOS_CELLS, depth_mapped=CMOS_DEPTH_MAPPED,
                         depth_generic=CMOS_DEPTH_GENERIC,
                         per_cell_fJ=CMOS_BLOCK_FJ / CMOS_CELLS,
                         basis="LOGIC ONLY -- the committed record states 'No "
                               "timing hardware is counted in either'.  So the "
                               "CMOS clock tree is EXCLUDED and QAL's timer is "
                               "0: this is a strictly logic-vs-logic question "
                               "and QAL's clock-elimination claim is outside it "
                               "on BOTH sides.")}

    # ---- fit E_bank = b + a*N on three ledger conventions
    #
    # SENSITIVITY.  The main series sizes the switch by the constant-Q rule
    # W ~ sqrt(N), and the record's own width sub-sweep shows that rule is
    # energy-optimal at N=256 (wmul 1 beats 0.25/0.5/2) but OVER-sizes at
    # N=32 (wmul 0.5 is better: 4.3225 vs 4.5780 fJ/gate).  A suboptimal low-N
    # point inflates the fitted FIXED cost b, so the fit is also reported on
    # the top three N only, where the sizing rule is near-optimal.
    fits = {}
    keys = (("driver_floored_at_zero", "CORRECTED_driver_floored_at_zero"),
            ("as_published_floor_timer0", "AS_PUBLISHED_idealPWL_floor_timer0"),
            ("real_conventional_driver", "CORRECTED_real_conventional_driver"))
    for nm, key in keys:
        X = [a["N"] for a in S]
        Y = [a["LEDGER_ROWS"][key]["E_bank_fJ"] for a in S]
        a_, b_, r2 = linfit(X, Y)
        d = dict(marginal_fJ_per_gate=a_, fixed_fJ_per_bank=b_, R2=r2,
                 N_points=X, E_bank_fJ=Y,
                 break_even_marginal_for_161_cells=CMOS_BLOCK_FJ / 161.0,
                 marginal_over_breakeven_161=a_ / (CMOS_BLOCK_FJ / 161.0))
        if len(X) >= 4:
            a3, b3, r3 = linfit(X[-3:], Y[-3:])
            d["top3_only"] = dict(N_points=X[-3:], marginal_fJ_per_gate=a3,
                                  fixed_fJ_per_bank=b3, R2=r3,
                                  marginal_over_breakeven_161=(
                                      a3 / (CMOS_BLOCK_FJ / 161.0)))
        fits[nm] = d
    out["A_FIT_E_bank_eq_b_plus_aN"] = fits

    # ---- compose the block.  THREE normalisations of "one gate":
    #   cells  : QAL pays a per LIBRARY CELL          (units = 161)
    #   devices: QAL pays a per PAIR of devices       (units = devices/2)
    #   width  : QAL pays a per 1.86 um of device W   (units = W_tot/1.86)
    # The WIDTH basis is PRIMARY: it is what the campaign's own
    # REMAP_CONSEQUENCE.json uses ("E_scaled_by_width_fJ"), and it is the
    # physical one for a resonant cost whose energy is set by the bank
    # capacitance, which tracks device width rather than cell count.
    comp = {}
    for pname, P in PROFILES.items():
        prof = P["profile"]
        cells, depth = sum(prof), len(prof)
        units = dict(cells=float(cells),
                     devices=P["devices"] / 2.0,
                     width=P["wtot"] / INV_WTOT_UM)
        per = {}
        for fname, f in fits.items():
            a_, b_ = f["marginal_fJ_per_gate"], f["fixed_fJ_per_bank"]
            basis = {}
            for bname, u in units.items():
                one = depth * b_ + a_ * u
                rows = {}
                for lanes in (1, 2, 4, 8, 22, 64, 256):
                    tot = depth * b_ + a_ * u * lanes
                    rows["lanes_%d" % lanes] = dict(
                        E_block_per_lane_fJ=tot / lanes,
                        x_CMOS_block=tot / lanes / CMOS_BLOCK_FJ,
                        widest_bank_N=max(prof) * lanes,
                        crosses=bool(tot / lanes < CMOS_BLOCK_FJ))
                basis[bname] = dict(
                    gate_units=u,
                    E_block_1_lane_fJ=one, x_CMOS_1_lane=one / CMOS_BLOCK_FJ,
                    E_block_infinite_lanes_fJ=a_ * u,
                    x_CMOS_infinite_lanes=a_ * u / CMOS_BLOCK_FJ,
                    crosses_at_infinite_lanes=bool(a_ * u < CMOS_BLOCK_FJ),
                    break_even_marginal_fJ_per_gate=CMOS_BLOCK_FJ / u,
                    by_lanes=rows)
            per[fname] = basis
        comp[pname] = dict(
            _why=P["why"], cells=cells, depth=depth, widest_level=max(prof),
            devices=P["devices"], W_tot_um=P["wtot"],
            banks_under_10_gates=sum(1 for x in prof if x < 10),
            x_cells_vs_CMOS=cells / float(CMOS_CELLS),
            x_devices_vs_CMOS=P["devices"] / float(CMOS_DEVICES),
            x_width_vs_CMOS=P["wtot"] / CMOS_WTOT_UM,
            x_depth_vs_CMOS=depth / float(CMOS_DEPTH_MAPPED),
            inverter_equivalents_by_width=P["wtot"] / INV_WTOT_UM,
            by_ledger=per)
    out["B_BLOCK_COMPOSED"] = comp
    out["B_LABEL"] = ("DERIVED.  It composes MY OWN MEASURED per-inverter bank "
                      "cost (E_bank = b + a*N) onto a synthesised netlist's "
                      "MEASURED cell/device/width census that I did NOT "
                      "re-synthesise.  Both inputs are measured; the "
                      "composition is arithmetic.")

    # ---- block TIME, using the real depths
    tm = {}
    for a in S:
        for pname, P in PROFILES.items():
            d = len(P["profile"])
            tm.setdefault(pname, []).append(dict(
                N_per_bank=a["N"], T_ps=a["T_ps"],
                level_floor_ps=a["level_floor_ps"],
                block_ps_scheduled=d * a["T_ps"],
                block_ps_floor=d * (a["level_floor_ps"] or 0),
                x_CMOS_block_scheduled=d * a["T_ps"] / CMOS_BLOCK_PS,
                x_CMOS_block_floor=d * (a["level_floor_ps"] or 0) / CMOS_BLOCK_PS))
    out["C_BLOCK_TIME"] = dict(
        _note="QAL needs the REMAPPED depth (14 levels for nand_mindepth) "
              "against CMOS's 928 ps for the whole block.  The record's "
              "per-level comparison uses 92.8 ps = 928/10, i.e. the GENERIC "
              "depth 10, while its energy bar uses the MAPPED cell count 56 -- "
              "two different countings of the same block.",
        rows=tm)

    # ---- BLOCK AREA, the other half of the trade the user is asking about
    a_gate = S[-1]["area_um2_per_gate"]
    a_tank = S[-1]["tank_um2_per_gate"]
    invq = PROFILES["nand_mindepth_QAL"]["wtot"] / INV_WTOT_UM
    # a CMOS sg13g2 std cell is ~2 um^2 of LAYOUT (0.48 um row pitch class);
    # labelled ASSUMED because I did not lay one out.
    CMOS_CELL_LAYOUT_UM2 = 2.0
    out["D_BLOCK_AREA"] = dict(
        _label="QAL side MEASURED-DERIVED from my own rows (MIM 1.5 fF/um^2, "
               "device active = drawn W x 0.13 um).  CMOS side ASSUMED at "
               "%.1f um^2 of layout per std cell -- I did not lay one out, so "
               "the RATIO is order-of-magnitude, the QAL absolute is not."
               % CMOS_CELL_LAYOUT_UM2,
        qal_total_active_um2_per_gate=a_gate,
        qal_tank_um2_per_gate=a_tank,
        tank_over_cell_active=a_tank / (INV_WTOT_UM * 0.13),
        qal_block_um2_by_width_basis=a_gate * invq,
        cmos_block_um2_ASSUMED=CMOS_CELLS * CMOS_CELL_LAYOUT_UM2,
        x_area_block=(a_gate * invq) / (CMOS_CELLS * CMOS_CELL_LAYOUT_UM2),
        inductors_per_block=len(PROFILES["nand_mindepth_QAL"]["profile"]),
        inductor_nH=15.0,
        note="the tank area per gate is EXACTLY CONSTANT in N by construction "
             "(C_tank ~ N), so bank width does not amortise it at all -- and it "
             "is the dominant term.  ONE 15 nH inductor per bank on top, NOT "
             "area-modelled by anyone, and the committed record calls it the "
             "architecture's largest and scarcest component.")

    json.dump(out, open(os.path.join(HERE, "SK_BLOCK.json"), "w"), indent=1,
              default=str)

    print("CMOS block: %.0f fJ, %.0f ps, %d mapped cells (depth %d), "
          "%d generic gates (depth %d).  LOGIC ONLY, no clock."
          % (CMOS_BLOCK_FJ, CMOS_BLOCK_PS, CMOS_CELLS, CMOS_DEPTH_MAPPED,
             105, CMOS_DEPTH_GENERIC))
    print("per-cell bar as used by the record: %.4f fJ  (232/56)"
          % (CMOS_BLOCK_FJ / CMOS_CELLS))
    print("per-cell bar a QAL block must meet: %.4f fJ  (232/161)\n"
          % (CMOS_BLOCK_FJ / 161.0))
    print("FIT E_bank = b + a*N on my own rows:")
    for nm, f in fits.items():
        print("  %-26s a = %7.4f fJ/gate   b = %8.3f fJ/bank   R2 = %.5f   "
              "a/(232/161) = %.3f"
              % (nm, f["marginal_fJ_per_gate"], f["fixed_fJ_per_bank"],
                 f["R2"], f["marginal_over_breakeven_161"]))
        if "top3_only" in f:
            t = f["top3_only"]
            print("  %-26s   top3 N=%s: a = %7.4f  b = %8.3f  R2 = %.5f  "
                  "a/(232/161) = %.3f"
                  % ("", t["N_points"], t["marginal_fJ_per_gate"],
                     t["fixed_fJ_per_bank"], t["R2"],
                     t["marginal_over_breakeven_161"]))
    print("\nCENSUS (MEASURED, qal/sha256/REMAP*.json):")
    print("  %-22s %6s %6s %8s %9s | %7s %7s %7s %7s | %8s"
          % ("library", "cells", "depth", "devices", "W_tot_um",
             "xcells", "xdev", "xwidth", "xdepth", "inv-eq"))
    for pname, c in comp.items():
        print("  %-22s %6d %6d %8d %9.2f | %7.3f %7.3f %7.3f %7.3f | %8.1f"
              % (pname, c["cells"], c["depth"], c["devices"], c["W_tot_um"],
                 c["x_cells_vs_CMOS"], c["x_devices_vs_CMOS"],
                 c["x_width_vs_CMOS"], c["x_depth_vs_CMOS"],
                 c["inverter_equivalents_by_width"]))
    for bname in ("width", "cells", "devices"):
        print("\nBLOCK COMPOSED, %s basis "
              "(driver floored at zero, free timer, PERFECT converter):" % bname.upper())
        print("  %-22s %11s %8s | %13s %8s | %10s"
              % ("library", "1 lane fJ", "xCMOS", "inf lanes fJ", "xCMOS",
                 "a must be"))
        for pname, c in comp.items():
            f = c["by_ledger"]["driver_floored_at_zero"][bname]
            print("  %-22s %11.1f %8.3f | %13.1f %8.3f | %10.4f%s"
                  % (pname, f["E_block_1_lane_fJ"], f["x_CMOS_1_lane"],
                     f["E_block_infinite_lanes_fJ"], f["x_CMOS_infinite_lanes"],
                     f["break_even_marginal_fJ_per_gate"],
                     "  <-- CROSSES" if f["crosses_at_infinite_lanes"] else ""))
    A = out["D_BLOCK_AREA"]
    print("\nAREA: %.2f um2/gate total active (%.2f um2 of that is MIM tank, "
          "%.0fx the cell active).  One lane of nand_mindepth = %.0f um2 vs "
          "~%.0f um2 of CMOS std cells = %.0fx, plus %d x 15 nH inductors."
          % (A["qal_total_active_um2_per_gate"], A["qal_tank_um2_per_gate"],
             A["tank_over_cell_active"], A["qal_block_um2_by_width_basis"],
             A["cmos_block_um2_ASSUMED"], A["x_area_block"],
             A["inductors_per_block"]))
    print("\nwrote SK_BLOCK.json")


if __name__ == "__main__":
    main()
