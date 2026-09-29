#!/usr/bin/env python3
"""Skeptic report: rails, per-gate settling, value/guard, separation, matching,
hop coherence, energy decomposition."""
import json, os, sys
import sk

SIG, CLIFF = 6.44, 0.600


def main():
    rows = json.load(open(os.path.join(sk.HERE, "ROWS_SKEPT.json")))
    ok = [r for r in rows if "error" not in r]
    print("\n================ RAILS / SETTLING / GUARD / VALUE ================")
    hdr = ("%-12s %-5s %-6s | %-42s | %-32s | %-11s | %-11s | %-9s"
           % ("sizing", "dest", "form", "rail by bank (V)", "worst gate % by bank",
              "guardfail", "valuefail", "IZ ok"))
    print(hdr); print("-" * len(hdr))
    for r in sorted(ok, key=lambda x: (x["cfg"]["sizing"], x["cfg"]["dest"], x["cfg"]["form"])):
        c = r["cfg"]
        print("%-12s %-5s %-6s | %-42s | %-32s | %-11s | %-11s | %-9s"
              % (c["sizing"], c["dest"], c["form"],
                 " ".join("%7.4f" % v for v in r["rail_by_stage_V"]),
                 " ".join("%5.1f" % v for v in r["worst_gate_by_stage_pct"]),
                 "".join("%2d" % v for v in r["guard_fail_by_stage"]),
                 "".join("%2d" % v for v in r["value_fail_by_stage"]),
                 "PASS" if r["IZ_gate_pass"] else "FAIL"))
    print("\n================ IZ PER HOP (uA) ================")
    for r in sorted(ok, key=lambda x: (x["cfg"]["sizing"], x["cfg"]["dest"], x["cfg"]["form"])):
        c = r["cfg"]
        print("%-12s %-5s %-6s  %s" % (c["sizing"], c["dest"], c["form"],
              " ".join("%9.3f" % x for x in r["IZ_uA"])))
    print("\n================ PER-GATE, EVERY STAGE (never aggregated) ================")
    for r in sorted(ok, key=lambda x: (x["cfg"]["sizing"], x["cfg"]["dest"], x["cfg"]["form"])):
        c = r["cfg"]
        print("\n--- %s / %s / %s  (deck %s) ---" % (c["sizing"], c["dest"], c["form"], r["deck"]))
        for s in r["stages"]:
            print("  bank %d  M=%-2d rail=%.4f V  bound=%.1f ps  distinct outputs=%d  "
                  "sep %s  guardfail=%d valuefail=%d (rule-label %d)"
                  % (s["bank"], s["M"], s["rail_at_bound_V"], s["bound_ps"],
                     s["n_distinct_outputs"],
                     ("%.3f mV = %.1f sigma" % (s["separation_mV"], s["separation_mV"] / SIG))
                     if s["separation_defined"] else "UNDEFINED/DEGENERATE",
                     s["n_guard_fail"], s["n_value_fail"], s["n_value_fail_rulelabel"]))
            shown = s["cells"] if s["M"] <= 6 else s["cells"][:4]
            for cel in shown:
                print("     i=%-2d %-8s(net %-6s) Vo=%9.5f Vg=%8.5f settle=%7.2f%% "
                      "drive=%+.4f guard=%-5s value=%-5s%s"
                      % (cel["i"], cel["kind_netlist"], cel["in_net"], cel["v_o"],
                         cel["v_gate"], cel["settle_pct"], cel["drive_over_vt_V"],
                         cel["guard_ok"], cel["value_ok"],
                         "  <-- PARITY-RULE MISLABEL" if cel["label_conflict"] else ""))
            if s["M"] > 6:
                print("     ... %d more cells (all in ROWS_SKEPT.json)" % (s["M"] - 4))
    print("\n================ COLLAPSE / MATCHING / COHERENCE ================")
    print("%-12s %-5s %-6s | %-34s | %-7s | %-9s | %-30s | %-7s"
          % ("sizing", "dest", "form", "per-hop collapse ratio", "spread",
             "cliff", "hop t_zcs (ps)", "hopspr"))
    for r in sorted(ok, key=lambda x: (x["cfg"]["sizing"], x["cfg"]["dest"], x["cfg"]["form"])):
        c = r["cfg"]
        print("%-12s %-5s %-6s | %-34s | %7.4f | %-9s | %-30s | %7.4f"
              % (c["sizing"], c["dest"], c["form"],
                 " ".join("%7.4f" % v for v in r["collapse_ratio_by_hop"]),
                 r["collapse_spread"], "PASS" if r["cliff_pass"] else "FAIL",
                 " ".join("%6.1f" % z for z in r["tz_ps"]), r["hop_spread"]))
    print("\n================ ENERGY LEDGER (attributable = topped - free) ================")
    idx = {(r["cfg"]["sizing"], r["cfg"]["dest"], r["cfg"]["form"]): r for r in ok}
    for (sz, d, f), r in sorted(idx.items()):
        if f != "clamp":
            continue
        fr = idx.get((sz, d, "free"))
        if fr is None:
            continue
        dq = r["ledger"]["Q_dv_source_fC"] - fr["ledger"]["Q_dv_source_fC"]
        eg = sum(r["ledger"]["E_topup%d_gate_drive_fJ" % k] for k in sk.TOPPED) \
            - sum(fr["ledger"]["E_topup%d_gate_drive_fJ" % k] for k in sk.TOPPED)
        er_t = sum(r["ledger"]["hop%d_ER_fJ" % h] for h in range(1, 5))
        er_f = sum(fr["ledger"]["hop%d_ER_fJ" % h] for h in range(1, 5))
        # what of the drawn energy ends up STORED on the topped nodes (in
        # principle recoverable) and what is irrecoverably burnt in the clamp
        ctk = r["ctk_fF"]
        stored = 0.0
        for k in sk.TOPPED:
            cn = (float(ctk.get(str(k), 0.0)) + CB.get(k, 0.0)) * 1e-15
            v1 = r["rail_by_stage_V"][k - 1]
            v0 = fr["rail_by_stage_V"][k - 1]
            stored += 0.5 * cn * (v1 * v1 - v0 * v0) * 1e15
        print("%-8s %-5s  dQ_dv %8.3f fC  E_drawn(BOUND) %8.3f fJ  topup gate drive %6.3f fJ"
              "  | E_stored_on_topped_nodes %7.3f fJ  E_irrecoverable %8.3f fJ"
              "  | hop I2R free %6.3f -> topped %6.3f fJ"
              % (sz, d, dq, dq * 1.2, eg, stored, dq * 1.2 - stored, er_f, er_t))
    print("\n  E_drawn is charge from the IDEAL dV source x 1.2 V -> a LOWER BOUND.")
    print("  E_stored is 1/2 C dV^2 on the topped nodes with C = C_bank + C_tank (MEASURED).")
    print("  E_irrecoverable = drawn - stored: the resistive clamp's own 1/2 C dV^2 burn.")


if __name__ == "__main__":
    CB = {int(k): v for k, v in
          json.load(open(os.path.join(sk.HERE, "CBANKFIT.json")))["C_bank_fF"].items()}
    main()
