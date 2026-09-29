#!/usr/bin/env python3
"""AMENDMENT A5's obligation: measure what the relaxed time step actually costs.
Same configuration, two max steps; report the delta in every headline quantity."""
import json, os, sys
import nm, run_cells

rows = []
for dt, mx, tag in ((0.02, 0.05, "sc_relaxed"), (0.00888317, 0.0177663, "sc_committed")):
    os.environ["NMUX_DT"], os.environ["NMUX_MAXSTEP"] = str(dt), str(mx)
    r = run_cells.canary(run_cells.measure("peer", "nmux", 0.60, "v15", tag))
    r["dt_ps"], r["maxstep_ps"] = dt, mx
    rows.append(r)
out = {"_doc": "A5 step-sensitivity: peer / nmux / w=0.60 / select on 1.5 V rail",
       "rows": rows}
if all("FAIL" not in r for r in rows):
    a, b = rows
    out["delta_relaxed_minus_committed"] = {
        k: (a[k] - b[k]) for k in ("pass_HIGH_V", "pass_LOW_V", "rail_end_V",
                                   "src_high_loaded_V", "E_in_H_fJ", "E_gate_fJ")
        if isinstance(a.get(k), float) and isinstance(b.get(k), float)}
    out["pass_HIGH_delta_mV"] = (a["pass_HIGH_V"] - b["pass_HIGH_V"]) * 1e3
json.dump(out, open(os.path.join(nm.HERE, "cells_stepcheck.json"), "w"), indent=1)
print(json.dumps(out.get("delta_relaxed_minus_committed", out), indent=1))
