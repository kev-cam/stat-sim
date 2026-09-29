#!/usr/bin/env python3
"""The skeptic matrix.  Stage 1 = zeros (sequential per config, 4 configs in
parallel).  Stage 2 = rows.  Stage 3 = extraction.

CONFIGS
  notank      ctk = 0 everywhere.  THE CONTROL THE COMMITTED 2x2 LACKS: both of
              its destinations carry the tank, so it cannot measure the brief's
              "the tank is large, so the same charge makes a smaller step".
  uni_m6      uniform tank, m = 6 (same TOTAL tank C as matched m=6)
  mat_m2      matched tank, C_tank_k = m*C_bank_k, m = 2
  uni_m2      uniform tank at the same total C as mat_m2 -- the fair control
  res_m6      uniform m=6, but the clamp is fed from a FINITE 1 pF reservoir
              instead of the ideal dV source.  THE BOOKING TEST.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import sk, go

T_BEAT, DV = 340.0, 1.2
M_RES_FF = 1000.0


def cbank_from_fit(a, b):
    """C_bank_k for the chain's OWN per-cell classes, counted from the NETLIST
    (true_input_hi), not from the (i+k) parity rule.  The two disagree at bank 5,
    where both cells read o4_0 and are therefore BOTH pull-downs."""
    prof = sk.PROFILE
    out, cnt = {}, {}
    for k in range(1, len(prof) + 1):
        nd = sum(1 for i in range(prof[k - 1]) if sk.true_input_hi(k, i, prof))
        nu = prof[k - 1] - nd
        cnt[k] = (nd, nu)
        out[k] = nd * a + nu * b
    return out, cnt


def configs(cb):
    tot6 = sum(6.0 * cb[k] for k in cb)
    tot2 = sum(2.0 * cb[k] for k in cb)
    n = len(cb)
    C = {}
    C["notank"] = dict(ctk={k: 0.0 for k in cb}, sizing="notank", m=0.0)
    C["uni_m6"] = dict(ctk={k: tot6 / n for k in cb}, sizing="uniform", m=6.0)
    C["mat_m2"] = dict(ctk={k: 2.0 * cb[k] for k in cb}, sizing="matched", m=2.0)
    C["uni_m2"] = dict(ctk={k: tot2 / n for k in cb}, sizing="uniform", m=2.0)
    # matched m=6 is the arrangement the committed run reports as having NO
    # OPERATING POINT (hop 1 never resonates).  Probed here with a long stop to
    # confirm or refute that independently; not carried into the rows.
    C["mat_m6"] = dict(ctk={k: 6.0 * cb[k] for k in cb}, sizing="matched", m=6.0)
    return C


def base(ctk, sizing, m, dest, form, res=None):
    c = dict(T=T_BEAT, dv=DV, ctk=dict(ctk), dest=dest, form=form,
             sizing=sizing, m=m, prof=sk.PROFILE)
    if res:
        c["reservoir_fF"] = res
    return c


def do_zeros(item):
    name, cfg = item
    span = 1400.0 if name == "mat_m6" else 8.0 * sk.TZ_ANCHOR * sk.CHAIN_F
    return name, go.zeros_for(cfg, name, span=span)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    cbj = json.load(open(os.path.join(sk.HERE, "CBANK_SKEPT.json")))
    pts = [r for r in cbj if abs(r["V0"] - 0.7138163) < 1e-6 and "error" not in r]
    # least squares for (a = pull-down cell C, b = pull-up cell C)
    import itertools
    A = [[(M + 1) // 2, M // 2] for M in [r["M"] for r in pts]]
    y = [r["C_bank_fF"] for r in pts]
    s11 = sum(r[0] * r[0] for r in A); s12 = sum(r[0] * r[1] for r in A)
    s22 = sum(r[1] * r[1] for r in A)
    t1 = sum(r[0] * v for r, v in zip(A, y)); t2 = sum(r[1] * v for r, v in zip(A, y))
    det = s11 * s22 - s12 * s12
    a, b = (s22 * t1 - s12 * t2) / det, (s11 * t2 - s12 * t1) / det
    cb, cnt = cbank_from_fit(a, b)
    print("C_pulldown_cell = %.4f fF   C_pullup_cell = %.4f fF  (MEASURED fit)" % (a, b))
    for k in sorted(cb):
        print("  bank %d  M=%-2d  (%d down, %d up)  C_bank = %8.4f fF"
              % (k, sk.PROFILE[k - 1], cnt[k][0], cnt[k][1], cb[k]))
    json.dump(dict(a_pulldown_fF=a, b_pullup_fF=b,
                   C_bank_fF={str(k): cb[k] for k in cb},
                   counts={str(k): cnt[k] for k in cnt},
                   fit_points=[(r["M"], r["C_bank_fF"]) for r in pts]),
              open(os.path.join(sk.HERE, "CBANKFIT.json"), "w"), indent=1)
    C = configs(cb)
    for n in C:
        print("%-8s tanks %s fF" % (n, [round(C[n]["ctk"][k], 2) for k in sorted(cb)]))

    if what in ("all", "zeros"):
        items = [(n, base(C[n]["ctk"], C[n]["sizing"], C[n]["m"], "bank", "free"))
                 for n in ("notank", "uni_m6", "mat_m2", "uni_m2", "mat_m6")]
        Z = {}
        with ThreadPoolExecutor(max_workers=4) as ex:
            for name, (tz, log) in ex.map(do_zeros, items):
                for l in log:
                    print("  " + l, flush=True)
                Z[name] = tz
                print("%-8s tz = %s  spread %s" % (name, tz,
                      round(max(tz) / min(tz), 4) if tz else "N/A"), flush=True)
        json.dump(Z, open(os.path.join(sk.HERE, "ZEROS_SKEPT.json"), "w"), indent=1)

    if what in ("all", "rows"):
        Z = json.load(open(os.path.join(sk.HERE, "ZEROS_SKEPT.json")))
        jobs = []
        for n in ("notank", "uni_m6", "mat_m2", "uni_m2"):
            if Z.get(n) is None:
                print("SKIP %s -- no zeros" % n); continue
            dests = ["bank"] if n == "notank" else ["bank", "tank"]
            forms = ["free", "clamp"]
            for d in dests:
                for f in forms:
                    cfg = base(C[n]["ctk"], C[n]["sizing"], C[n]["m"], d, f)
                    jobs.append((cfg, Z[n], "s_%s_%s_%s.cir" % (n, d, f)))
        # the BOOKING arm: finite reservoir instead of the ideal dV source
        if Z.get("uni_m6"):
            for d in ("bank", "tank"):
                for f in ("free", "clamp"):
                    cfg = base(C["uni_m6"]["ctk"], "uniform_res", 6.0, d, f, res=M_RES_FF)
                    jobs.append((cfg, Z["uni_m6"], "s_res_%s_%s.cir" % (d, f)))
        out = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            for r in ex.map(go.run_row, jobs):
                out.append(r)
                if "error" in r:
                    print("ERROR %s" % r["error"], flush=True)
                else:
                    c = r["cfg"]
                    print("%-8s %-5s %-6s rails %s  worst%% %s  guardfail %s  "
                          "vfail %s (rule %s)  IZ %s"
                          % (c["sizing"], c["dest"], c["form"],
                             [round(v, 4) for v in r["rail_by_stage_V"]],
                             [round(v, 1) for v in r["worst_gate_by_stage_pct"]],
                             r["guard_fail_by_stage"], r["value_fail_by_stage"],
                             r["value_fail_rulelabel_by_stage"],
                             [round(x, 2) for x in r["IZ_uA"]]), flush=True)
        json.dump(out, open(os.path.join(sk.HERE, "ROWS_SKEPT.json"), "w"), indent=1)
        print("wrote ROWS_SKEPT.json")
