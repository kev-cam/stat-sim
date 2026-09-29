#!/usr/bin/env python3
"""Re-run row_extract over every row already simulated, so that every reported
row comes out of ONE code path.  No new simulation."""
import json, os, sys
import skip, extract

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, "rows.json")

rows = json.load(open(ROWS))
for tag in sorted(rows):
    r = rows[tag]
    if "error" in r:
        print("%-28s ERROR (left as is)" % tag)
        continue
    path = os.path.join(HERE, "c_%s.cir" % tag)
    w = r.get("wall_s")
    try:
        rows[tag] = extract.row_extract(r["scheme"], r["mode"] if "mode" in r
                                        else tag.split("_")[1],
                                        r["T_ps"], r["dv"], r["tz_ps"], path)
        rows[tag]["wall_s"] = w
        n = rows[tag]
        print("%-28s worst %6.2f%% st%d  IZ<=%.4f uA  ident<=%.2e fJ  A6 %s/%s"
              % (tag, n["worst_gate_pct_all_stages"], n["worst_gate_stage"],
                 max(abs(v) for v in n["IZ_uA"].values()),
                 max(abs(v) for v in n["identity_at_own_zero_fJ"].values()),
                 n["A6_IZ_PASS"], n["A6_identity_PASS"]))
    except Exception as e:                                          # noqa
        import traceback
        print("%-28s EXTRACT FAIL %s" % (tag, repr(e)))
        traceback.print_exc()
json.dump(rows, open(ROWS, "w"), indent=1)
print("re-extracted %d rows" % len(rows))
