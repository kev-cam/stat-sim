#!/usr/bin/env python3
"""One-shot summary of every measured row + the economics, for the write-up."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import econ, ref

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "rows.json")))
cinv = ref.cinv(); qpre = ref.qpre(); rt = ref.rtrip()
TINV = cinv["t_inv_50pct_mean_ps"]; EINV = cinv["E_inv_hi_lo_mid_fJ"]

print("### REFERENCES (MEASURED) ###")
print("  CMOS inverter 1.12p/0.74n, FO1 + 2 fF, 1.2 V : t_inv(50%%) %.2f ps  E %.4f fJ/hi+lo  C_eff %.2f fF"
      % (TINV, EINV, cinv["per_inverter_hi_lo_cycle"][4]["C_eff_fF"]))
print("  restoring-stage receiver trip points         : std %.6f V (committed %.6f)  A4 %.6f V (committed %.6f)"
      % (rt["S"]["trip_Vin_at_Vout_half_dV"], rt["S"]["committed_trip_V"],
         rt["A"]["trip_Vin_at_Vout_half_dV"], rt["A"]["committed_trip_V"]))
print("  per-segment pre-charge (35.979 fF to 1.2 V)  : Q %.3f fC  E_supply %.3f fJ  E_diss %.3f fJ  -> %.3f fJ/bit supply"
      % (qpre["summary"]["Q_precharge_fC"], qpre["summary"]["E_supply_fJ"],
         qpre["summary"]["E_dissipated_fJ"], qpre["summary"]["per_bit_E_supply_fJ"]))
print()
print("### ROWS ###")
for tag in sorted(rows, key=lambda t: (rows[t].get("k", 99), rows[t].get("T_ps", 0))):
    r = rows[tag]
    if "error" in r:
        print("%-12s ERROR %s" % (tag, r["error"])); continue
    tm = r["tres_measured_ps"]
    print("--- %s : k=%s T=%g ps, %d segments, tres scheduled %.1f ps  (wall %.0f s)"
          % (tag, r["k"], r["T_ps"], r["nseg"], r["tres_ps"], r["wall_s"]))
    print("    A1 all-gates-90 %-5s | A2 guard %-5s | A3 cliff %-5s | A4 ZCS %-5s | A4 ident %-5s | A5 restore %-5s | PASS %-5s | VOID %s"
          % (r["A1_all_gates_90_all_banks"], r["A2_pattern_guard_all"],
             r["A3_cliff_pass"], r["A4_IZ_PASS"], r["A4_identity_PASS"],
             r["A5_restore_outputs_full_swing"], r["PASS"], r.get("VOID_for_acceptance")))
    print("    tres MEASURED: pair %s ps  half-restore(inv1) %s ps  resolved=%s"
          % (("%.2f" % tm["pair_max"]) if tm["pair_max"] is not None else "NOT MEASURABLE",
             ("%.2f" % tm["inv1_max"]) if tm["inv1_max"] is not None else "n/a",
             tm.get("restore_resolved")))
    print("    bank pos rail@bound  UPmin%   DOWNmin%  worst%   limiting   guard  input")
    for j in map(str, range(1, r["nbank"] + 1)):
        g = r["settling_groups"][j]
        print("      %-3s %-3d  %8.4f  %8.3f %8.3f %8.3f  %-10s %-5s  %s"
              % (j, g["pos_in_segment"], r["rail_at_own_boundary_V"][j],
                 g["pullup_min"], g["pulldown_min"], g["worst"], g["limiting"],
                 g["guard_all_pass"], g["input_from"]))
    for j in map(str, range(1, r["nbank"] + 1)):
        d = r["settling_pct_per_gate"][j]
        print("      bank %-2s every gate: %s" % (j, "  ".join(
            "%s:%7.3f" % (n.split("_")[-1], v)
            for n, v in sorted(d.items(), key=lambda kv: int(kv[0].split("_")[-1])))))
    print("    IZ uA per hop: %s" % {k: round(v, 4) for k, v in r["IZ_uA"].items()})
    print("    identity fJ  : %s" % {k: round(v, 5) for k, v in r["identity_at_own_zero_fJ"].items()})
    print("    droop %%/hop  : %s" % {k: (round(v["droop_pct"], 2) if v["droop_pct"] else None)
                                      for k, v in r["per_hop_droop"].items()})
    if r.get("restore_stage_output_check"):
        for j, v in r["restore_stage_output_check"].items():
            print("    restore into bank %s (from bank %s): all bits full swing = %s; levels %s"
                  % (j, v["from_bank"], v["ALL_BITS_FULL_SWING"],
                     {b: round(x["restored_level_V"], 4) for b, x in v["bits"].items()}))
    sl = r["supply_ledger_fJ"]
    print("    restore supply: Q %.3f fC  E %.3f fJ  over %d stages -> %.4f fJ/stage/bit"
          % (sl["Q_restore_supply_fC"], sl["E_restore_supply_fJ"],
             r["n_restore_stages_in_deck"], r["E_restore_per_stage_per_bit_fJ"]))
    print("    restore supply per beat window (fC): %s ; tail %.3f"
          % ({k: round(v, 3) for k, v in r["restore_supply_per_window_fC"].items()},
             r["restore_supply_tail_fC"]))
    print("    E transfer-gate drive %.3f fJ   E vhi %.3f fJ" %
          (sl["E_transfer_gate_drive_fJ"], sl["E_vhi_fJ"]))
    print("    bank gate charge fC: %s" % {k: round(v, 3) for k, v in r["bank_gate_charge_fC"].items()})
    print("    E per hop fJ: %s" % {k: {kk: round(vv, 3) for kk, vv in v.items()}
                                    for k, v in r["energy_per_hop_fJ"].items()})
    print("    eventual settling at end of tail: %s"
          % {k: round(v["worst"], 2) for k, v in r["eventual_settling_at_end_of_tail"].items()})
    print()
