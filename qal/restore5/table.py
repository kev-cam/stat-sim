#!/usr/bin/env python3
"""TABLE.txt: every measured row, per gate, per bank, never aggregated."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    rows = json.load(open(os.path.join(HERE, "rows.json")))
    ks = lambda t: (rows[t].get("k", 99), rows[t].get("T_ps", 0))
    out = []
    out.append("=== RESTORED QAL CHAIN: 6 hop-powered banks, restoring stage every k banks ===")
    out.append("    L=15 nH, tg15p W=30 um, dV=1.2 V, SG13G2/PSP103 tt, sg13_lv shim (NO junction C)")
    out.append("    restoring stage = CMOS inverter PAIR on a FIXED 1.2 V supply, CL 2 fF on both nodes:")
    out.append("      1st (receiving) inverter SKEWED 0.15u pMOS / 1.48u nMOS  (AMENDMENT A4; trip 0.4595 V MEASURED)")
    out.append("      2nd inverter campaign standard 1.12u pMOS / 0.74u nMOS   (its input is full swing)")
    out.append("    k = hop-powered banks per inter-restore segment; each segment has its own 35.979 fF pre-charged reservoir")
    out.append("    k=6 is the NO-RESTORE control (one segment, zero internal restoring stages)")
    out.append("")
    hdr = ("%-5s %-6s %-5s %-6s | %-7s %-7s | %-7s %-7s %-7s | %-9s | %-4s"
           % ("k", "T ps", "tres", "seg", "worst%", "bank", "A1", "A2", "A4", "rails min", "PASS"))
    out.append(hdr)
    out.append("-" * len(hdr))
    for t in sorted(rows, key=ks):
        r = rows[t]
        if "error" in r:
            out.append("%-5s ERROR %s" % (t, r["error"]))
            continue
        rl = min(r["rail_at_own_boundary_V"].values())
        out.append("%-5s %-6g %-5.1f %-6d | %7.2f %-7d | %-7s %-7s %-7s | %9.4f | %-4s"
                   % (r["k"], r["T_ps"], r["tres_ps"], r["nseg"],
                      r["worst_gate_pct_all_banks"], r["worst_gate_bank"],
                      r["A1_all_gates_90_all_banks"], r["A2_pattern_guard_all"],
                      r["A4_IZ_PASS"], rl, r["PASS"]))
    out.append("")
    out.append("=== PER-BANK, PER-GROUP SETTLING AT EACH BANK'S OWN STAGE BOUNDARY (never aggregated) ===")
    out.append("    pos = position of the bank inside its segment; input = what drives its gates")
    for t in sorted(rows, key=ks):
        r = rows[t]
        if "error" in r:
            continue
        out.append("")
        out.append("--- k=%s T=%gps tres=%.1fps  (%d segments)   PASS=%s"
                   % (r["k"], r["T_ps"], r["tres_ps"], r["nseg"], r["PASS"]))
        out.append("  bank pos  rail_V   UPmin%    DOWNmin%  worst%   lim        guard  input")
        for j in sorted(r["settling_groups"], key=lambda x: int(x)):
            g = r["settling_groups"][j]
            out.append("  %-4s %-3d  %6.4f  %7.2f  %8.2f  %6.2f  %-9s  %-5s  %s"
                       % (j, g["pos_in_segment"],
                          r["rail_at_own_boundary_V"][j],
                          g["pullup_min"], g["pulldown_min"], g["worst"],
                          g["limiting"], g["guard_all_pass"], g["input_from"]))
        for j in sorted(r["settling_pct_per_gate"], key=lambda x: int(x)):
            d = r["settling_pct_per_gate"][j]
            out.append("      bank %-2s gates: %s" % (j, " ".join(
                "%s:%6.2f" % (n.split("_")[-1], v) for n, v in sorted(d.items(),
                key=lambda kv: int(kv[0].split("_")[-1])))))
    open(os.path.join(HERE, "TABLE.txt"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
