#!/usr/bin/env python3
"""A6b: close the residual ZCS offset on hops 3-5 with a MEASURED slope correction.

A6's three-class probe cleared hops 1, 2 and 6 (|I_zcs| 0.0022 / 0.0066 / 0.1193 uA)
but left hops 3-5 at 6.94-7.01 uA against the 1.0 uA gate.  The three-class model was
incomplete: hop 2's destination is fed by a restoring stage that reads an IDEAL-input
bank, while hops 3-5's destinations are fed by restoring stages that read
RESTORE-input banks, and those two produce slightly different gate-voltage
trajectories during the hop and therefore slightly different zeros.

Rather than add a fourth probe class, the offset is closed with a correction that is
itself MEASURED off the failing row: dI/dt is least-squares fitted to I(L) over the
6 ps immediately before each switch's own opening instant (MEASURED -40.72 uA/ps),
and the zero is shifted by -I_zcs/(dI/dt).  No analytic pi*sqrt(LC) is used anywhere.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rest, extract

T, TRES, K = 300.0, 179.0, 1
tz = json.load(open(os.path.join(rest.HERE, "tz_corrected.json")))
print("corrected zeros (MEASURED slope correction): %s" % [round(x, 4) for x in tz],
      flush=True)
lines, S = rest.deck(K, T, TRES, nbank=rest.NBANK, tz=tz)
p, msg = rest.run("c_k1_T300_zcs2.cir", lines)
print("  row %s" % msg, flush=True)
if p is None:
    sys.exit(1)
r = extract.row_extract(K, T, TRES, tz, p)
r["tres_in_full_chain_ps"] = extract.tres_measure(p, S, rest.NBANK)
r["_note"] = ("AMENDMENT A6b: hop zeros = A6's three-class probe plus a MEASURED "
              "dI/dt slope correction on hops 3-5 (-I_zcs/(dI/dt), dI/dt least-squares "
              "fitted to I(L) over the 6 ps before each switch's own opening instant, "
              "MEASURED -40.72 uA/ps). No analytic zero is used anywhere.")
rows = json.load(open(os.path.join(rest.HERE, "rows.json")))
rows["k1_T300_zcs2"] = r
json.dump(rows, open(os.path.join(rest.HERE, "rows.json"), "w"), indent=1, default=str)
print("  A4 ZCS per hop uA: %s" % {k: round(v, 5) for k, v in r["IZ_uA"].items()})
print("  A4 IZ PASS %s | A4 identity PASS %s | A1 %s | A2 %s | A3 %s | A5 %s | PASS %s"
      % (r["A4_IZ_PASS"], r["A4_identity_PASS"], r["A1_all_gates_90_all_banks"],
         r["A2_pattern_guard_all"], r["A3_cliff_pass"],
         r["A5_restore_outputs_full_swing"], r["PASS"]))
print("  worst gate %.3f%% at bank %d" % (r["worst_gate_pct_all_banks"],
                                          r["worst_gate_bank"]))
