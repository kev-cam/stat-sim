#!/usr/bin/env python3
"""One Phase 2 point, end to end: probe -> row -> extract -> row_*.json.

Usage:  pt.py N SCALE [L_nH] [mstep] [cload] [ct_fF] [extra] [T_force]
        SCALE may be "4" (all banks) or "4,4,1" (per bank, control E1).

Each invocation is a separate process, so several points can be launched at
once; the probes WITHIN a point stay sequential because each one needs the
previous bank's zero.
"""
import json, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import up
import upx


def rowonly():
    """pt.py rowonly ZEROSFILE MSTEP EXTRA

    Re-run the ROW from an EXISTING zeros file, changing only the max
    timestep.  Used for B11 (E4): the probe decks of the main s=8 point and of
    the half-step point are byte-identical by construction (the probe .tran
    always uses the default step), so re-probing would only burn 6 more
    simulations to reproduce the same zeros.  Reusing them makes the timestep
    the ONLY difference between the two rows, which is exactly what B11 tests.
    """
    zp = sys.argv[2]
    ms = float(sys.argv[3]) if sys.argv[3] != "-" else None
    ex = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else ""
    zp = zp if os.path.exists(zp) else os.path.join(HERE, zp)
    z = json.load(open(zp))
    t0 = time.monotonic()
    p, S, msg = up.do_row(z["N"], z["T_used"], z["H_probe"], z["dv"], "free", z,
                          nb=z["nb"], l_nh=z.get("L_nH", up.L_REF),
                          wmul=z["wmul"], mstep=ms, extra=ex,
                          scale=z.get("scale", 1.0),
                          cload=z.get("cload", up.CLOAD), ct_fF=z.get("ct_fF"))
    if p is None:
        print("ROWONLY FAILED %s" % msg, flush=True)
        return 1
    wall = time.monotonic() - t0
    row = upx.extract_from_zeros(zp, extra=ex, wall_s=round(wall, 1), mstep=ms)
    print("DONE %s  ACC=%s mstep=%.6f E/gate=%.6f t_hop=%.4f margin=%.4f "
          "worst=%.4f%% wall=%.0fs"
          % (row["tag"], row["ACCEPTED"], row["mstep_ps"],
             row["E_per_gate_headline_fJ"], row["t_hop_rise_ps"],
             row["A2_functional"]["margin_min_mV"], row["worst_gate_pct"],
             wall), flush=True)
    return 0


def main():
    if sys.argv[1] == "rowonly":
        sys.exit(rowonly())
    a = sys.argv[1:]
    n = int(a[0])
    sc = up._pscale(a[1])
    l_nh = float(a[2]) if len(a) > 2 and a[2] != "-" else up.L_REF
    ms = float(a[3]) if len(a) > 3 and a[3] != "-" else None
    cl = float(a[4]) if len(a) > 4 and a[4] != "-" else up.CLOAD
    ct = float(a[5]) if len(a) > 5 and a[5] != "-" else None
    ex = a[6] if len(a) > 6 and a[6] != "-" else ""
    tf = float(a[7]) if len(a) > 7 and a[7] != "-" else None
    t0 = time.monotonic()
    r = up.do_point(n, scale=sc, l_nh=l_nh, mstep=ms, cload=cl, ct_fF=ct,
                    extra=ex, T_force=tf)
    if r is None:
        print("POINT FAILED n=%d s=%s" % (n, sc), flush=True)
        sys.exit(1)
    wall = time.monotonic() - t0
    row = upx.extract_from_zeros(os.path.join(HERE, r["zeros"]), extra=ex,
                                 wall_s=round(wall, 1), mstep=ms)
    A2 = row["A2_functional"]
    B = row["BOUND_BY"]
    print("DONE %s  ACC=%s A1=%s(%d fail) A2=%s(%.1f mV) A4=%s A5=%s A6=%s "
          "worst=%.2f%% | t_hop=%.2f t_set90=%.2f %s slack=%+.2f "
          "stage=%.2f T=%g | E/gate=%.4f (%.3fx) E/gate_conv=%.4f (%.3fx) | "
          "Ipk=%.0fuA W=%.2f Qg=%.2f m_eff=%.2f | wall=%.0fs"
          % (row["tag"], row["ACCEPTED"], row["A1_value_all_banks_pass"],
             row["A1_value_fail_count"],
             A2["PASS_bare"] if A2 else None,
             A2["margin_min_mV"] if A2 else float("nan"),
             row["A4_zcs_pass"], row["A5_path_identity_pass"],
             row["A6_tank_closure_pass"], row["worst_gate_pct"],
             row["t_hop_rise_ps"], B["t_settle90_ps"] or float("nan"),
             B["bound_by"], B["slack_hop_minus_settle90_ps"] or float("nan"),
             row["stage_time_measured_ps"] or float("nan"), row["T_ps"],
             row["E_per_gate_headline_fJ"],
             row["E_per_gate_headline_fJ"] / upx.CMOS_BLOCK_PER_CELL_FJ,
             row["LEDGER"]["rows"]["conventional_from_own_measured_charge__"
                                   "timer0_BOUND"]["E_per_gate_fJ"],
             row["LEDGER"]["rows"]["conventional_from_own_measured_charge__"
                                   "timer0_BOUND"]["x_vs_CMOS_block_4p14"],
             row["IPK_uA"][2], row["W_nominal_um"],
             row["LEDGER"]["Q_gate_MEASURED_fC"],
             row["m_eff_MEASURED"] or float("nan"), wall), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(2)
