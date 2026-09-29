#!/usr/bin/env python3
"""STEP 2 -- C_bank(M) MEASURED per bank size, before any tank is sized.

The matching rule C_tank_k = m * C_bank_k needs C_bank_k as a MEASURED number,
not a per-cell figure multiplied out.  This is the small fixture that supplies
it, and it doubles as an instrument check: the record's 3-bank chain quotes a
36.6 fF incremental bank capacitance for an 8-cell bank, so M=8 here must land
on that.

Method: a bank of M committed cells, inputs held at their DC operating levels,
rail driven by a voltage source through a 0 V series meter.  Settle at
V0 = 0.7138163 V (the committed delivered rail, so the incremental C is taken at
the operating point the chain actually sees), then ramp +0.1 V over 100 ps, and
integrate the meter current with a 1F integrator.  C = dQ/dV.

Both integrator reads are t0-referenced by DIFFERENCING two FIND points, which
removes the 1F integrator's t=0 pedestal by construction.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import tf

HERE = tf.HERE
V0    = 0.7138163      # the committed delivered rail
DVR   = 0.1            # ramp amplitude, V
T_SET = 800.0          # ps, settle
T_RMP = 100.0          # ps, ramp
DV_IN = 1.2            # cell input HIGH level


def build(M):
    L = tf.head_lines() + ["VHI vhi 0 %g" % tf.VGH]
    L += ["VRAMP nvr 0 PWL(0 %g %gp %g %gp %g %gp %g)"
          % (V0, T_SET, V0, T_SET + T_RMP, V0 + DVR, T_SET + 2 * T_RMP, V0 + DVR),
          "VMR nvr rail 0", "VMG gn 0 0"]
    for i in range(M):
        L.append("VI%d in%d 0 %g" % (i, i, DV_IN if (i % 2 == 0) else 0.0))
        L.append("XP%d o%d in%d rail rail sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, tf.WP))
        L.append("XN%d o%d in%d gn gn sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, tf.WN))
        L.append("CL%d o%d gn %gf" % (i, i, tf.CLOAD))
    L += tf.integ("q", "I(VMR)")
    L += [".ic V(rail)=%g" % V0,
          ".tran 0.1p %gp 0 0.0884p" % (T_SET + 2 * T_RMP),
          ".measure tran QA FIND V(xq) AT=%.6fp" % (T_SET + tf.LAG_PS),
          ".measure tran QB FIND V(xq) AT=%.6fp" % (T_SET + T_RMP + tf.LAG_PS),
          ".measure tran VA FIND V(rail) AT=%.6fp" % (T_SET + tf.LAG_PS),
          ".measure tran VB FIND V(rail) AT=%.6fp" % (T_SET + T_RMP + tf.LAG_PS),
          ".print tran V(rail) I(VMR) V(xq)", ".end"]
    return L


def one(M):
    L = build(M)
    p, msg = tf.run("cb_M%d.cir" % M, L, timeout=900)
    if p is None:
        return dict(M=M, error=msg)
    m = tf.parse_mt0(p + ".mt0")
    dq = m["QB"] - m["QA"]
    dv = m["VB"] - m["VA"]
    return dict(M=M, msg=msg, QA=m["QA"], QB=m["QB"], dQ_fC=dq * 1e15,
                VA=m["VA"], VB=m["VB"], dV=dv, C_bank_fF=dq / dv * 1e15,
                C_per_cell_fF=dq / dv * 1e15 / M)


if __name__ == "__main__":
    Ms = [int(x) for x in sys.argv[1:]] or [1, 2, 3, 8, 19, 48]
    out = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for r in ex.map(one, Ms):
            out.append(r)
            print("M=%-3d %s" % (r["M"], r.get("error") or
                                 "C_bank = %.4f fF (%.4f fF/cell)  %s"
                                 % (r["C_bank_fF"], r["C_per_cell_fF"], r["msg"])),
                  flush=True)
    json.dump(out, open(os.path.join(HERE, "CBANK.json"), "w"), indent=1)
    print("wrote CBANK.json")
