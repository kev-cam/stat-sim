#!/usr/bin/env python3
"""qal/meshdrv final aggregation -> RESULTS.json.
Applies ledger.py bookings to every run row, builds the decisive comparison
table, the sharing curve, and the verdict against the PRE_REGISTERED
acceptance.  Run after all rows exist."""
import json, os, sys
import ledger

HERE = os.path.dirname(os.path.abspath(__file__))
E_LEDGER = ledger.E_LEDGER


def rows():
    return sorted(os.listdir(os.path.join(HERE, "runs")))


def main():
    out = dict(_doc="qal/meshdrv RESULTS -- flat-top mesh driver pricing at "
                    "trap_tt92_d3 (committed 5b9d05b interface spec). "
                    "Bookings per PRE_REGISTERED + amendments A1-A4 in "
                    "meshdrv.py header.",
               E_ledger_ref_fJ=E_LEDGER)
    got = rows()
    out["rows_present"] = got
    A, B, C = {}, {}, {}
    for t in got:
        try:
            if t.startswith("a_k"):
                A[t] = ledger.price_A(t)
            elif t.startswith("b_"):
                B[t] = ledger.price_B(t)
            elif t.startswith("c_n2"):
                C[t] = ledger.price_C(t, N=2)
            elif t.startswith("c_full"):
                pass  # handled separately
            elif t.startswith("c_"):
                C[t] = ledger.price_C(t, N=1)
        except Exception as e:
            out.setdefault("row_errors", {})[t] = repr(e)
    out["A"], out["B"], out["C"] = A, B, C
    json.dump(out, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    print("rows:", len(got))
    for grp, name in ((A, "A"), (B, "B"), (C, "C")):
        for t, r in grp.items():
            c = r["common"]
            print("%-24s eye=%-9s asym=%s droop=%s ovh=%s%% PASS=%s"
                  % (t, c["erosion_sign"], c["asymptotic_eye_ps"],
                     c["droop_mV"],
                     round(100*r.get("overhead_frac_of_ledger", 9.99), 1),
                     c["acceptance_PASS"]))


if __name__ == "__main__":
    main()
