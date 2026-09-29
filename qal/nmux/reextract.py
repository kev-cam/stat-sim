#!/usr/bin/env python3
"""Re-extract every transient row from the SAVED .prn files -- no re-simulation.

Fixes two extraction defects (AMENDMENT A10):

  1. UNITS.  A 1 F integrator holds V = Q/C = Q, so V(x) is COULOMBS for a charge
     meter and JOULES for a power meter.  The first pass labelled the raw values
     fC and fJ without the 1e15 scale, so every energy printed as 0.000 fJ when it
     was really ~1-12 fJ.  Nothing was wrong with the simulation.

  2. THE GATE-DRIVE WINDOW.  All integrators were t0-referenced at
     t_close - 5 ps, which is AFTER the select edge at t_close - 30 ps.  That
     window cannot see the select transition -- the actual per-operation gate
     cost -- and what it did measure was the data edge pushing charge back out of
     the gate through Cgd, which is why E_gate came out NEGATIVE.  Both windows
     are now reported:
        E_gate_total : from t = 1 ps, includes the select edge (the real cost)
        E_gate_hop   : from t_close - 5 ps, the feedthrough during the hop alone

Also replaces the bogus "closure" check.  It compared the charge drawn from the
driving cell against C_load * V_out, assuming all of it lands on the load.  It
does not: the pass device's own source/drain capacitance is charged too.  The
split is now reported instead of being asserted.
"""
import json, os, sys
import nm, run_cells

HERE = nm.HERE
SCALE = 1e15          # coulombs -> fC, joules -> fJ


def redo(prn, mode, design, wid, gate_src, tag, t_open):
    w = nm.W(prn)
    R = nm.RAIL[mode]
    tc, tend = R["t_close"], R["tend"]
    tZ, tD, tsel = tc - 5.0, tend - 1.0, tc - 30.0

    def d(n, t0=None):
        return (w.at("V(x%s)" % n, tD) - w.at("V(x%s)" % n, t0 if t0 else tZ)) * SCALE

    rail_D = w.at("V(rail)", tD)
    src_h  = w.at("V(o1)", tD)
    src_l  = w.at("V(o2)", tD)
    ref_h  = w.at("V(o7)", tD)
    ref_l  = w.at("V(o6)", tD)
    yh, yl = w.at("V(yh)", tD), w.at("V(yl)", tD)

    t90_src = w.t_reach("V(o1)", 0.9 * src_h, tc)
    t90_y   = w.t_reach("V(yh)", 0.9 * yh, tc) if yh > 0 else None
    t50_y   = w.t_reach("V(yh)", 0.5 * yh, tc) if yh > 0 else None

    # select-edge charge injection on the idle output, BEFORE the rail moves.
    # Two numbers, because they answer different questions:
    #   peak    -- the worst transient excursion the edge causes
    #   residue -- what is still there when the data arrives (the one that can
    #              actually corrupt a level; a TG's complementary edges cancel in
    #              the residue even when their peaks do not)
    pre = [v for t, v in zip(w.t, w.c("V(yh)"))
           if (tsel - 5) * 1e-12 < t < (tc - 2) * 1e-12]
    inj = max((abs(v) for v in pre), default=0.0)
    inj_res = abs(w.at("V(yh)", tc - 2))

    q_in   = d("qih")
    q_load = nm.CY * yh                      # fF * V = fC
    return {
      "tag": tag, "mode": mode, "design": design, "w_um": wid,
      "gate_src": gate_src, "t_open_ps": t_open, "t_hop_ps": t_open - tc,
      "rail_end_V": rail_D, "rail_peak_V": max(w.c("V(rail)")),
      "src_high_loaded_V": src_h, "src_low_loaded_V": src_l,
      "ref_high_unloaded_V": ref_h, "ref_low_unloaded_V": ref_l,
      "capacitive_tax_mV": (ref_h - src_h) * 1e3,
      "pass_HIGH_V": yh, "pass_LOW_V": yl,
      "shortfall_HIGH_mV": (src_h - yh) * 1e3,
      "shortfall_LOW_mV": (yl - src_l) * 1e3,
      "t90_pass_abs_ps": t90_y,
      "t90_pass_after_close_ps": (t90_y - tc) if t90_y else None,
      "t50_pass_after_close_ps": (t50_y - tc) if t50_y else None,
      "t90_src_after_close_ps": (t90_src - tc) if t90_src else None,
      "pass_delay_90_ps": (t90_y - t90_src) if (t90_y and t90_src) else None,
      "select_injection_peak_mV": inj * 1e3,
      "select_injection_residue_mV": inj_res * 1e3,
      # --- energy, correctly scaled ---
      "E_in_HIGH_fJ": d("eih"), "Q_in_HIGH_fC": q_in,
      "E_in_LOW_fJ":  d("eil"), "Q_in_LOW_fC":  d("qil"),
      "E_gate_total_fJ": d("egt", 1.0), "Q_gate_total_fC": d("qgt", 1.0),
      "E_gate_hop_only_fJ": d("egt"), "Q_gate_hop_only_fC": d("qgt"),
      "E_SUPPLY_fJ": d("esup"), "Q_SUPPLY_fC": d("qsup"),
      "E_bank_fJ": d("ebk"), "E_R_fJ": d("er"), "Q_through_L_fC": d("qlt"),
      # --- where the input charge went ---
      "Q_onto_load_fC": q_load,
      "Q_into_pass_device_fC": q_in - q_load,
      "pct_of_input_charge_that_reaches_the_load":
          (100.0 * q_load / q_in) if q_in else None,
      "E_per_operation_fJ": d("eih") + max(d("egt", 1.0), 0.0),
    }


def main():
    out = {}
    for f, rows in (("cells_designs.json", None), ("cells_widths.json", None),
                    ("cells_stepcheck.json", None)):
        p = os.path.join(HERE, f)
        if not os.path.exists(p):
            continue
        data = json.load(open(p))
        rows = data["rows"] if isinstance(data, dict) else data
        new = []
        for r in rows:
            if "FAIL" in r:
                new.append(r); continue
            prn = os.path.join(HERE, r["tag"] + ".cir.prn")
            if not os.path.exists(prn):
                r["FAIL"] = "prn missing"; new.append(r); continue
            try:
                n = redo(prn, r["mode"], r["design"], r["w_um"], r["gate_src"],
                         r["tag"], r["t_open_ps"])
                if "dt_ps" in r:
                    n["dt_ps"], n["maxstep_ps"] = r["dt_ps"], r["maxstep_ps"]
                new.append(n)
            except Exception as e:
                r["FAIL"] = "reextract: %s" % e; new.append(r)
        o = f.replace(".json", "_fixed.json")
        json.dump(new, open(os.path.join(HERE, o), "w"), indent=1)
        out[o] = len(new)
        for r in new:
            if "FAIL" in r:
                print("%-22s %s" % (r.get("tag"), r["FAIL"])); continue
            print("%-22s rail %.4f srcH %.4f passH %.4f (short %6.1f mV) passL %+.5f | "
                  "t90 %6.1f ps | Ein %6.3f fJ Egt_tot %6.3f fJ Esup %9.2e fJ | "
                  "Qin %5.2f fC -> load %4.2f fC (%.0f%%)"
                  % (r["tag"], r["rail_end_V"], r["src_high_loaded_V"],
                     r["pass_HIGH_V"], r["shortfall_HIGH_mV"], r["pass_LOW_V"],
                     r["t90_pass_after_close_ps"] or -1, r["E_in_HIGH_fJ"],
                     r["E_gate_total_fJ"], r["E_SUPPLY_fJ"], r["Q_in_HIGH_fC"],
                     r["Q_onto_load_fC"],
                     r["pct_of_input_charge_that_reaches_the_load"] or 0))
    print(out)


if __name__ == "__main__":
    main()
