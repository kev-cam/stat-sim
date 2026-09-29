#!/usr/bin/env python3
"""My own C_bank(M) extraction, at TWO operating points.

The matching rule C_tank_k = m*C_bank_k needs C_bank_k.  The committed fixture
measures it at ONE rail voltage (0.7138 V, the committed delivered rail).  But
the chain's deep banks sit at 0.26-0.50 V, and a MOS bank's incremental
capacitance is voltage dependent, so a tank sized from a 0.7138 V measurement is
not m*C_bank at the voltage the deep bank actually runs at.  Measuring at two
points bounds that error instead of assuming it away.

Method: M committed cells, inputs at their DC levels, rail driven through a 0 V
series meter by a ramp; C = dQ/dV from a 1F integrator, t0-referenced by
differencing two FIND points.  The ramp source is IDEAL -- it is a measurement
fixture and the number is labelled a BOUND on that account.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import sk

DVR, T_SET, T_RMP, DV_IN = 0.1, 800.0, 100.0, 1.2


def build(M, V0, parity):
    L = sk.head_lines() + ["VHI vhi 0 %g" % sk.VGH]
    L += ["VRAMP nvr 0 PWL(0 %g %gp %g %gp %g %gp %g)"
          % (V0, T_SET, V0, T_SET + T_RMP, V0 + DVR, T_SET + 2 * T_RMP, V0 + DVR),
          "VMR nvr rail 0", "VMG gn 0 0"]
    for i in range(M):
        hi = (i % 2 == 0) if parity == 0 else (i % 2 == 1)
        L.append("VI%d in%d 0 %g" % (i, i, DV_IN if hi else 0.0))
        L.append("XP%d o%d in%d rail rail sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, sk.WP))
        L.append("XN%d o%d in%d gn gn sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, sk.WN))
        L.append("CL%d o%d gn %gf" % (i, i, sk.CLOAD))
    L += sk.integ("q", "I(VMR)")
    L += [".ic V(rail)=%g" % V0,
          ".tran 0.1p %gp 0 0.0884p" % (T_SET + 2 * T_RMP),
          ".measure tran QA FIND V(xq) AT=%.6fp" % (T_SET + sk.LAG_PS),
          ".measure tran QB FIND V(xq) AT=%.6fp" % (T_SET + T_RMP + sk.LAG_PS),
          ".measure tran VA FIND V(rail) AT=%.6fp" % (T_SET + sk.LAG_PS),
          ".measure tran VB FIND V(rail) AT=%.6fp" % (T_SET + T_RMP + sk.LAG_PS),
          ".print tran V(rail) I(VMR)", ".end"]
    return L


def one(spec):
    M, V0, parity = spec
    L = build(M, V0, parity)
    p, msg = sk.run("cb_M%d_V%d_p%d.cir" % (M, round(V0 * 1000), parity), L, timeout=900)
    if p is None:
        return dict(M=M, V0=V0, parity=parity, error=msg)
    m = sk.parse_mt0(p + ".mt0")
    dq, dv = m["QB"] - m["QA"], m["VB"] - m["VA"]
    return dict(M=M, V0=V0, parity=parity, dQ_fC=dq * 1e15, dV=dv,
                C_bank_fF=dq / dv * 1e15, C_per_cell_fF=dq / dv * 1e15 / M, msg=msg)


if __name__ == "__main__":
    specs = [(M, V0, 0) for V0 in (0.7138163, 0.45) for M in (1, 2, 3, 19, 48)]
    out = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(one, specs):
            out.append(r)
            print("M=%-3d V0=%.4f %s" % (r["M"], r["V0"], r.get("error") or
                  "C_bank %9.4f fF (%.4f fF/cell)  %s" %
                  (r["C_bank_fF"], r["C_per_cell_fF"], r["msg"])), flush=True)
    json.dump(out, open(os.path.join(sk.HERE, "CBANK_SKEPT.json"), "w"), indent=1)
    print("wrote CBANK_SKEPT.json")
