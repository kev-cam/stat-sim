#!/usr/bin/env python3
"""Render the (b)(d) matrix rows as a markdown table for the write-up."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
f = sys.argv[1] if len(sys.argv) > 1 else "cells_designs.json"
rows = json.load(open(os.path.join(HERE, f)))
print("| tag | rail end (V) | src HIGH (V) | pass HIGH (V) | shortfall (mV) | pass LOW (V) | t90 pass (ps) | pass delay (ps) | sel inj (mV) | E_in (fJ) | E_gate (fJ) | E_supply (fJ) | cap tax (mV) |")
print("|" + "---|" * 13)
for r in rows:
    if "FAIL" in r:
        print("| %s | **%s** |" % (r.get("tag"), r["FAIL"])); continue
    def g(k, fmt="%.4f"):
        v = r.get(k)
        return (fmt % v) if isinstance(v, (int, float)) else "n/a"
    print("| `%s` | %s | %s | **%s** | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        r["tag"], g("rail_end_V"), g("src_high_loaded_V"), g("pass_HIGH_V"),
        g("shortfall_HIGH_mV", "%.1f"), g("pass_LOW_V", "%.5f"),
        g("t90_pass_ps", "%.1f"), g("pass_delay_ps", "%.1f"),
        g("select_injection_mV", "%.1f"), g("E_in_H_fJ", "%.4f"),
        g("E_gate_fJ", "%.4f"), g("E_supply_fJ", "%.3g"),
        g("capacitive_tax_mV", "%.1f")))
