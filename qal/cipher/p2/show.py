#!/usr/bin/env python3
"""Print every measured Phase 2 row and comparator as a compact table."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def load(pat):
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, pat))):
        try: out.append((os.path.basename(f), json.load(open(f))))
        except Exception as e: print("  !! %s: %s" % (f, e))
    return out

print("=== QAL ROWS (MEASURED) ===")
hdr = ("%-30s %4s %5s %6s %6s %6s  %9s %8s  %7s %7s  %6s %5s  %s" %
       ("tag","lvl","cells","T_ps","ms_ps","cw_fF","E_tot_fJ","E/gate","lvl_t","op_t","rail","fcrit","gates"))
print(hdr); print("-"*len(hdr))
for nm, v in load("ROW_*.json"):
    if v.get("status") != "OK":
        print("%-30s %s" % (v.get("tag", nm), v.get("status"))); continue
    g = v["GATES"]; gs = "".join(("." if g.get(k) else "X") for k in
        ("G2","G3","G6","G7","G8","G11_value","G11_reference"))
    print("%-30s %4d %5d %6g %5g %6.3f  %9.2f %8.3f  %7s %7s  %6.4f %5s  %s" % (
        v["tag"], v["nb"], v["cells_total"], v["T_ps"], v.get("mstep_ps",0.25),
        v.get("cw_per_bit_fF") or 0.0,
        v["E_tank_lost_total_fJ_CONVENTION_FREE"], v["E_per_gate_fJ"],
        ("%.1f"%v["LEVEL_TIME_measured_max_ps"]) if v.get("LEVEL_TIME_measured_max_ps") else "-",
        ("%.1f"%v["OP_TIME_end_to_end_MEASURED_ps"]) if v.get("OP_TIME_end_to_end_MEASURED_ps") else "-",
        v["G7_worst_rail_V"], v["G6_functional"]["score"], gs))
print("  gates order G2 G3 G6 G7 G8 G11value G11ref   '.'=pass 'X'=FAIL")

for lbl, pat, ek in (("SAME-NETLIST CMOS TWINS", "TWIN_*.json", "E_full_cycle_fJ_CONVENTION_FREE"),
                     ("CMOS-NATIVE", "NAT_*.json", "E_full_cycle_fJ_CONVENTION_FREE")):
    rr = load(pat)
    if not rr: continue
    print("\n=== %s (MEASURED) ===" % lbl)
    print("%-34s %6s %5s %6s %10s %8s %8s %7s %6s" %
          ("tag","vdd","cells","dev","E_cyc_fJ","E/gate","C_sw_fF","delay","act"))
    for nm, v in rr:
        e = v.get(ek) or v.get("E_supply_fJ")
        d = v.get("DELAY_end_to_end_MEASURED_ps") or v.get("OP_TIME_end_to_end_MEASURED_ps")
        a = (v.get("activity") or {}).get("activity")
        print("%-34s %6.4f %5d %6d %10.2f %8.3f %8.1f %7s %6s%s" % (
            v["tag"], v["vdd_V"], v["cells"], v["devices"], e,
            v["E_per_gate_fJ"], v.get("C_switched_fF_DERIVED") or 0,
            ("%.1f"%d) if d else "-", ("%.2f"%a) if a is not None else "-",
            "" if v.get("value_pass") else "  VALUE-FAIL"))
