#!/usr/bin/env python3
"""SKEPTIC final assembly.  Consumes SK_LEDGER.json (my own rows) and produces
the tables the verdict rests on.  No simulation, no re-fitting of anyone else's
numbers."""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS = 4.14
CMOS_LVL = 92.8
# the sha_slice nand_mindepth level profile from the brief
SHA_PROFILE = [41, 32, 26, 21, 6, 5, 3, 7, 4, 7, 3, 4, 1, 1]


def interp_1_over_sqrtN(pts, target):
    """pts = [(N, y)] on the a + b/sqrt(N) form; solve for N where y = target,
    and also evaluate y at an arbitrary N.  Two-point solve on the two points
    that bracket the target."""
    pts = sorted(pts)
    for (n0, y0), (n1, y1) in zip(pts, pts[1:]):
        if (y0 - target) * (y1 - target) <= 0 and y0 != y1:
            x0, x1 = 1.0 / math.sqrt(n0), 1.0 / math.sqrt(n1)
            b = (y0 - y1) / (x0 - x1)
            a = y0 - b * x0
            if b == 0:
                return None, (a, b)
            x = (target - a) / b
            return (1.0 / x ** 2 if x > 0 else None), (a, b)
    return None, None


def eval_at(pts, N):
    pts = sorted(pts)
    lo = [p for p in pts if p[0] <= N] or pts[:1]
    hi = [p for p in pts if p[0] >= N] or pts[-1:]
    (n0, y0), (n1, y1) = lo[-1], hi[0]
    if n0 == n1:
        return y0
    x0, x1 = 1.0 / math.sqrt(n0), 1.0 / math.sqrt(n1)
    b = (y0 - y1) / (x0 - x1)
    a = y0 - b * x0
    return a + b / math.sqrt(N)


def main():
    L = json.load(open(os.path.join(HERE, "SK_LEDGER.json")))
    main_series = [a for a in L
                   if a["scale"] == 1.0 and "E6" not in a["tag"]
                   and "_s" not in a["tag"]]
    main_series.sort(key=lambda a: a["N"])
    out = {"_what": "SKEPTIC final assembly, from MY OWN measured rows only"}

    # ---- the ledger rows that matter, at every N
    tab = []
    for a in main_series:
        R = a["LEDGER_ROWS"]
        tab.append(dict(
            N=a["N"], T_ps=a["T_ps"], ACCEPTED=a["ACCEPTED"],
            A1_fail=a["A1_fail"], A2_margin_mV=a["A2_margin_mV"],
            worst_gate_pct=a["worst_gate_pct"],
            t_hop_ps=a["t_hop_ps"], t_settle90_ps=a["t_settle90_ps"],
            bound_by=a["bound_by"], level_floor_ps=a["level_floor_ps"],
            x_CMOS_level_scheduled=a["x_CMOS_level_scheduled"],
            x_CMOS_level_floor=a["x_CMOS_level_floor"],
            E_tank_per_gate=a["E_tank_per_gate_fJ"],
            miller_credit_per_gate=a["driver_credit_per_gate_fJ"],
            AS_PUBLISHED_floor_x=R["AS_PUBLISHED_idealPWL_floor_timer0"]["x_CMOS"],
            AS_PUBLISHED_floor_fJ=R["AS_PUBLISHED_idealPWL_floor_timer0"]["E_per_gate_fJ"],
            driver_zero_x=R["CORRECTED_driver_floored_at_zero"]["x_CMOS"],
            driver_zero_fJ=R["CORRECTED_driver_floored_at_zero"]["E_per_gate_fJ"],
            realdrv_x=R["CORRECTED_real_conventional_driver"]["x_CMOS"],
            realdrv_fJ=R["CORRECTED_real_conventional_driver"]["E_per_gate_fJ"],
            A1_published_conv_cycle_x=(
                R.get("AS_PUBLISHED_conventional_FULL_CYCLE_A1") or {}).get("x_CMOS"),
            P1_published_conv_rise_x=R["AS_PUBLISHED_conventional_rise_hop"]["x_CMOS"],
            eta_breakeven=a["eta_breakeven_corrected_floor"],
            wellrail_per_gate=a["E_wellrail_per_gate_fJ"],
            area_um2_per_gate=a["area_um2_per_gate"],
            Q_open_over_close=a["Q_split"]["ratio_open_over_close_rise"],
            Q_real_per_cycle_fC=a["Q_split"]["Q_real_driver_per_QALcycle_fC"],
            Q_instr_rise_fC=a["Q_gate_rise_fC"],
            Q_instr_cycle_fC=a["Q_gate_cycle_fC"]))
    out["A_LEDGER_BY_N"] = tab

    # ---- eta break-even with the Miller credit LEFT IN (generous reading)
    eta = []
    for a in main_series:
        e_tank = a["E_tank_loss_fJ"]
        egd = a["E_gate_drive_idealPWL_per_bank_fJ"]
        n = a["N"]
        need = CMOS * n - egd
        eta.append(dict(N=n, eta_breakeven=(e_tank / need if need > 0 else None),
                        feasible=bool(need > 0 and e_tank / need < 1.0)))
    out["B_CONVERTER_BREAKEVEN"] = dict(
        _what="E_tank_loss/eta + E_gate_drive_net <= 4.14*N.  The Miller credit "
              "is LEFT IN, i.e. this is the reading MOST generous to QAL.  "
              "E_tank_loss is the energy a converter must resupply every cycle "
              "and NO converter is simulated in any row of either phase.",
        rows=eta)

    # ---- crossings, on each ledger convention
    cross = {}
    for nm, key in (("as_published_floor_timer0", "AS_PUBLISHED_floor_x"),
                    ("driver_floored_at_zero", "driver_zero_x"),
                    ("real_conventional_driver", "realdrv_x")):
        pts = [(t["N"], t[key] * CMOS) for t in tab if t[key] is not None]
        first = next((t["N"] for t in tab
                      if t[key] is not None and t[key] < 1.0), None)
        nmin, ab = interp_1_over_sqrtN(pts, CMOS)
        cross[nm] = dict(first_measured_N_that_crosses=first,
                         N_min_interpolated_in_1_over_sqrtN=nmin,
                         fit_a_plus_b_over_sqrtN=ab,
                         asymptote_fJ_per_gate=(ab[0] if ab else None),
                         asymptote_x_CMOS=(ab[0] / CMOS if ab else None))
    out["C_CROSSINGS"] = cross

    # ---- the composition cap: a bank may only hold INDEPENDENT gates
    widest = max(SHA_PROFILE)
    pts = [(t["N"], t["AS_PUBLISHED_floor_fJ"]) for t in tab]
    ptz = [(t["N"], t["driver_zero_fJ"]) for t in tab]
    out["D_COMPOSITION_CAP"] = dict(
        _what="one block instance caps N at its WIDEST LEVEL, because a bank "
              "may only hold gates that do not depend on each other",
        sha_slice_profile=SHA_PROFILE, total_cells=sum(SHA_PROFILE),
        levels=len(SHA_PROFILE), widest_level=widest,
        banks_under_10_gates=sum(1 for x in SHA_PROFILE if x < 10),
        E_per_gate_at_widest_level_published_fJ=eval_at(pts, widest),
        x_CMOS_at_widest_level_published=eval_at(pts, widest) / CMOS,
        E_per_gate_at_widest_level_driverzero_fJ=eval_at(ptz, widest),
        x_CMOS_at_widest_level_driverzero=eval_at(ptz, widest) / CMOS,
        lanes_needed_for_N64_at_level_width_3=math.ceil(64 / 3),
        note="N >= 64 is reachable only by packing INDEPENDENT INSTANCES into "
             "one bank, i.e. a SIMT / GPU-batched lane workload")

    # ---- speed: is anything faster than CMOS anywhere?
    sp = []
    for a in L:
        sp.append(dict(tag=a["tag"], N=a["N"], scale=a["scale"],
                       level_floor_ps=a["level_floor_ps"],
                       x_CMOS_level=a["x_CMOS_level_floor"],
                       T_ps=a["T_ps"], x_CMOS_T=a["x_CMOS_level_scheduled"],
                       bound_by=a["bound_by"]))
    sp.sort(key=lambda d: d["level_floor_ps"] or 1e9)
    faster = [d for d in sp if (d["x_CMOS_level"] or 9) < 1.0]
    out["E_SPEED"] = dict(
        _bar_ps=CMOS_LVL,
        _unit="ONE LEVEL.  Both technologies evaluate a level's gates in "
              "parallel, so gates/ps is NOT a throughput comparison.",
        rows=sp, fastest=sp[0] if sp else None,
        any_point_faster_than_CMOS=bool(faster), faster_points=faster)

    json.dump(out, open(os.path.join(HERE, "SK_ANSWER.json"), "w"), indent=1,
              default=str)

    print("=" * 108)
    print("A. LEDGER BY N  (my own rows; CMOS hard bar 4.14 fJ/cell/op)")
    print("%4s %5s %4s %6s %6s  %7s %7s %6s %7s | %8s %8s %8s %8s | %6s"
          % ("N", "T", "A1f", "A2mV", "wrst%", "t_hop", "t_s90", "bnd",
             "lvl/CM", "pub x", "drv0 x", "real x", "A1cyc x", "eta*"))
    for t in tab:
        print("%4d %5g %4d %6.1f %6.2f  %7.1f %7.1f %6s %7.2f | %8.3f %8.3f "
              "%8.3f %8.3f | %6.4f"
              % (t["N"], t["T_ps"], t["A1_fail"], t["A2_margin_mV"],
                 t["worst_gate_pct"], t["t_hop_ps"], t["t_settle90_ps"],
                 t["bound_by"], t["x_CMOS_level_floor"],
                 t["AS_PUBLISHED_floor_x"], t["driver_zero_x"],
                 t["realdrv_x"], t["A1_published_conv_cycle_x"] or float("nan"),
                 t["eta_breakeven"]))
    print("\nB. CONVERTER BREAK-EVEN (Miller credit left IN -- generous to QAL)")
    for e in eta:
        print("   N=%-4d eta must exceed %s"
              % (e["N"], ("%.4f" % e["eta_breakeven"]) if e["eta_breakeven"]
                 else "IMPOSSIBLE (>1)"))
    print("\nC. CROSSINGS")
    for nm, d in cross.items():
        print("   %-28s first N=%s  N_min(interp)=%s  asymptote=%s fJ (%s x)"
              % (nm, d["first_measured_N_that_crosses"],
                 ("%.1f" % d["N_min_interpolated_in_1_over_sqrtN"])
                 if d["N_min_interpolated_in_1_over_sqrtN"] else None,
                 ("%.3f" % d["asymptote_fJ_per_gate"])
                 if d["asymptote_fJ_per_gate"] else None,
                 ("%.3f" % d["asymptote_x_CMOS"])
                 if d["asymptote_x_CMOS"] else None))
    D = out["D_COMPOSITION_CAP"]
    print("\nD. COMPOSITION CAP: widest level = %d gates -> %.4f fJ/gate "
          "(%.3fx) published / %.4f fJ/gate (%.3fx) driver-zero"
          % (D["widest_level"], D["E_per_gate_at_widest_level_published_fJ"],
             D["x_CMOS_at_widest_level_published"],
             D["E_per_gate_at_widest_level_driverzero_fJ"],
             D["x_CMOS_at_widest_level_driverzero"]))
    print("\nE. SPEED: fastest point anywhere = %s at %.2f ps = %.3fx the "
          "CMOS 92.8 ps/level;  any point faster than CMOS? %s"
          % (out["E_SPEED"]["fastest"]["tag"],
             out["E_SPEED"]["fastest"]["level_floor_ps"],
             out["E_SPEED"]["fastest"]["x_CMOS_level"],
             out["E_SPEED"]["any_point_faster_than_CMOS"]))
    print("\nwrote SK_ANSWER.json")


if __name__ == "__main__":
    main()
