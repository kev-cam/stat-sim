#!/usr/bin/env python3
"""Stage driver for (b)(d): instrument gates -> rail calibration -> probe -> hop.

Gates G2/G3 are BYTE COPIES of the committed decks re-run in MY OWN PyMS cache,
so they validate model + cache + binary + options end to end against committed
numbers before any new configuration is trusted.
"""
import json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import nm

HERE = nm.HERE
OUT  = {}

COMMITTED = {
 "peer": {"src": "/usr/local/src/stat-sim/qal/resv/h_I2_load691_L4.cir",
          "tag": "g2_peer",
          "checks": {"VBEND": 0.754572966, "VBPK": 1.0881874,
                     "VA_open": 0.11745601600934541, "t_hop_ps": 34.28582535896825},
          "t_close": 50.0, "t_open": 84.2858, "tend": 584.286},
 "tank": {"src": "/usr/local/src/stat-sim/qal/resv/ch_res20/c_res20.cir",
          "tag": "g3_tank",
          "checks": {"sep_mV": [1325.7453203187652, 1048.906890280997,
                                879.3138696808401, 721.08425606,
                                562.0507371599999, 282.3151318820968],
                     "rail1_boundary": 1.32574378, "rail1_peak": 1.4502807}},
}


def sh(path):
    t0 = time.monotonic()
    r = subprocess.run([nm.XYCE, path], cwd=HERE, env=nm.ENV,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, time.monotonic() - t0, r.stdout.decode()[-800:]


# ----------------------------------------------------------------- gates
def gate_peer():
    c = COMMITTED["peer"]
    dst = os.path.join(HERE, c["tag"] + ".cir")
    shutil.copyfile(c["src"], dst)
    rc, dt, tail = sh(dst)
    if rc != 0:
        return {"PASS": False, "rc": rc, "tail": tail}
    w = nm.W(dst + ".prn")
    tend = c["tend"]
    got = {"VBEND": w.at("V(bkb)", tend - 0.5),
           "VBPK": max(w.c("V(bkb)")),
           "VA_open": w.at("V(bka)", c["t_open"]),
           "t_hop_ps": (w.zero_after("I(LT)", c["t_close"] + 5) or 0) - c["t_close"]}
    res = {"rc": rc, "sec": round(dt, 1), "committed": c["checks"], "mine": got,
           "rel_pct": {k: 100.0 * (got[k] - v) / v for k, v in c["checks"].items()}}
    res["PASS"] = all(abs(x) < 0.1 for x in res["rel_pct"].values())
    return res


def gate_tank():
    c = COMMITTED["tank"]
    dst = os.path.join(HERE, c["tag"] + ".cir")
    shutil.copyfile(c["src"], dst)
    rc, dt, tail = sh(dst)
    if rc != 0:
        return {"PASS": False, "rc": rc, "tail": tail}
    w = nm.W(dst + ".prn")
    # separation at each bank's own boundary == start of the next bank's window
    bnd = [499.0, 799.0, 1099.0, 1399.0, 1699.0, 2001.0]
    sep, rails = [], []
    # POLARITY ALTERNATES BY BANK.  qal/restore5/rest.py is_hi(j,i) = (i+j)%2==1
    # marks a HIGH *input* (a pull-DOWN cell), so the HIGH *output* of bank k is
    # the cell with (i+k) even -- i.e. index (k % 2).  A fixed tap would read the
    # separation with the wrong sign on every even bank.
    for k, tb in enumerate(bnd, start=1):
        ih, il = k % 2, 1 - k % 2
        hi = w.at("V(o%d_%d)" % (k, ih), tb)
        lo = w.at("V(o%d_%d)" % (k, il), tb)
        sep.append((hi - lo) * 1e3)
        rails.append(w.at("V(rail%d)" % k, tb))
    got = {"sep_mV": sep, "rail1_boundary": rails[0],
           "rail1_peak": max(w.c("V(rail1)"))}
    rel = [100.0 * (a - b) / b for a, b in zip(sep, c["checks"]["sep_mV"])]
    rel += [100.0 * (got["rail1_boundary"] - c["checks"]["rail1_boundary"]) / c["checks"]["rail1_boundary"],
            100.0 * (got["rail1_peak"] - c["checks"]["rail1_peak"]) / c["checks"]["rail1_peak"]]
    return {"rc": rc, "sec": round(dt, 1), "committed": c["checks"], "mine": got,
            "rel_pct": rel, "PASS": all(abs(x) < 0.1 for x in rel)}


# ------------------------------------------------------- probe -> hop rows
def measure(mode, design, w, gate_src, tag, clb=None, t_open_override=None):
    R = dict(nm.RAIL[mode])
    if clb is not None:
        R["clb"] = clb
    save = nm.RAIL[mode]
    nm.RAIL[mode] = R
    try:
        tc = R["t_close"]
        if t_open_override is None:
            p = nm.build(mode, design, w, R["t_open"], probe=True,
                         gate_src=gate_src, tag=tag + "_pr")
            rc, dt, tail = sh(p)
            if rc != 0:
                return {"tag": tag, "FAIL": "probe rc=%d" % rc, "tail": tail}
            wp = nm.W(p + ".prn")
            z = wp.zero_after("I(LT)", tc + 5)
            if z is None:
                return {"tag": tag, "FAIL": "no probe zero"}
        else:
            z, dt = t_open_override, 0.0
        ph = nm.build(mode, design, w, z, probe=False, gate_src=gate_src, tag=tag)
        rc2, dt2, tail2 = sh(ph)
        if rc2 != 0:
            return {"tag": tag, "FAIL": "hop rc=%d" % rc2, "tail": tail2}
        return extract(nm.W(ph + ".prn"), mode, design, w, gate_src, tag, z,
                       R, round(dt + dt2, 1))
    finally:
        nm.RAIL[mode] = save


def extract(w, mode, design, wid, gate_src, tag, t_open, R, sec):
    tc, tend = R["t_close"], R["tend"]
    tZ  = tc - 5.0                    # t0 reference for every integrator
    tD  = tend - 1.0                  # end of the hold window
    tsel = tc - 30.0

    def dI(n):                        # t0-referenced integrator delta
        return w.at("V(x%s)" % n, tD) - w.at("V(x%s)" % n, tZ)

    # TAP MAP (the driver inverters INVERT; see nm.build's docstring):
    #   o1 HIGH / o0 LOW -> instance H legs      o3 HIGH / o2 LOW -> instance L
    #   o5 HIGH / o4 LOW -> select pair when gate_src == "rail"
    #   o7 HIGH / o6 LOW -> UNLOADED references
    rail_D  = w.at("V(rail)", tD)
    src_h   = w.at("V(o1)", tD)       # loaded driver cell, HIGH  (feeds inst H)
    src_l   = w.at("V(o2)", tD)       # loaded driver cell, LOW   (feeds inst L)
    ref_h   = w.at("V(o7)", tD)       # UNLOADED reference HIGH
    ref_l   = w.at("V(o6)", tD)       # UNLOADED reference LOW
    yh      = w.at("V(yh)", tD)
    yl      = w.at("V(yl)", tD)

    # settle to 90 % of the value each node actually reaches, from switch close
    t90_src = w.t_reach("V(o1)", 0.9 * src_h, tc)
    t90_y   = w.t_reach("V(yh)", 0.9 * yh, tc) if yh > 0 else None

    # select-edge charge injection, measured BEFORE the rail moves
    pre = [(t, v) for t, v in zip(w.t, w.c("V(yh)"))
           if tsel * 1e-12 - 5e-12 < t < (tc - 2) * 1e-12]
    inj = max((abs(v) for _, v in pre), default=0.0)

    return {
      "tag": tag, "mode": mode, "design": design, "w_um": wid,
      "gate_src": gate_src, "sec": sec, "t_open_ps": t_open,
      "t_hop_ps": t_open - tc,
      "rail_end_V": rail_D, "rail_peak_V": max(w.c("V(rail)")),
      "src_high_loaded_V": src_h, "src_low_loaded_V": src_l,
      "ref_high_unloaded_V": ref_h, "ref_low_unloaded_V": ref_l,
      "capacitive_tax_mV": (ref_h - src_h) * 1e3,
      "pass_HIGH_V": yh, "pass_LOW_V": yl,
      "shortfall_HIGH_mV": (src_h - yh) * 1e3,
      "shortfall_LOW_mV": (yl - src_l) * 1e3,
      "t90_src_ps": t90_src, "t90_pass_ps": t90_y,
      "pass_delay_ps": (t90_y - t90_src) if (t90_y and t90_src) else None,
      "select_injection_mV": inj * 1e3,
      "E_in_H_fJ": dI("eih"), "Q_in_H_fC": dI("qih"),
      "E_in_L_fJ": dI("eil"), "Q_in_L_fC": dI("qil"),
      "E_gate_fJ": dI("egt"), "Q_gate_fC": dI("qgt"),
      "E_supply_fJ": dI("esup"), "Q_supply_fC": dI("qsup"),
      "E_bank_fJ": dI("ebk"), "E_R_fJ": dI("er"), "Q_L_fC": dI("qlt"),
      "closure_Q_in_vs_CdV_pct": (
          100.0 * (dI("qih") - nm.CY * yh) / (nm.CY * yh) if yh > 1e-3 else None),
    }


def canary(r):
    """null-model guard (AMENDMENT A1): a dead PSP103 gives a dead circuit."""
    if "FAIL" in r:
        return r
    if r.get("rail_peak_V", 0) < 0.1:
        r["FAIL"] = "NULL-MODEL CANARY: rail peak %.4g V < 0.1 V" % r["rail_peak_V"]
    return r


def matrix(which):
    """the (b)(d) matrix: 4 designs x 2 rails x select-drive, + a width sweep"""
    # NOTE: a pass-transistor XOR2 is the SAME netlist as a pass-transistor MUX2
    # -- Y = A ? Bbar : B -- so it is not a separate device structure.  The real
    # difference is WHO DRIVES THE GATES: a MUX select is control and can sit on
    # the 1.5 V rail ("v15"); an XOR operand is data and arrives only at the QAL
    # rail level ("rail").  That is the gate_src axis, and running a separately
    # named "nxor" design would have measured the identical circuit twice.
    jobs = []
    if which in ("all", "designs"):
        for mode in ("peer", "tank"):
            for d in ("nmux", "tgmux"):
                for gs in ("v15", "rail"):
                    jobs.append((mode, d, 0.60, gs,
                                 "m_%s_%s_%s" % (mode, d, gs), None))
    if which in ("all", "widths"):
        # TANK only, and no per-width probe: width changes the pass device, not
        # the resonant bank, and the boundary study MEASURED that capacitance on
        # cell OUTPUTS does not join the resonance (+6 fF/cell moved the zero by
        # 0.94 %).  All width rows therefore open at the w=0.60 tank zero, which
        # is reported so the choice is visible.
        # reuse the tank/nmux/w=0.60 zero that the `designs` stage already probed;
        # fall back to the committed ch_res20 bank-1 open time if it is absent
        zt = nm.RAIL["tank"]["t_open"]
        d = os.path.join(HERE, "cells_designs.json")
        if os.path.exists(d):
            for r in json.load(open(d)):
                if r.get("tag") == "m_tank_nmux_v15" and r.get("t_open_ps"):
                    zt = r["t_open_ps"]
        for w in (0.15, 0.30, 1.20):
            jobs.append(("tank", "nmux", w, "v15",
                         "w_tank_nmux_%03d" % round(w * 100), None, zt))
    with ThreadPoolExecutor(max_workers=3) as ex:
        rows = list(ex.map(
            lambda a: canary(measure(*a[:5], clb=a[5],
                                     t_open_override=(a[6] if len(a) > 6 else None))),
            jobs))
    return rows


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    res = {}
    if what in ("designs", "gatesrc", "widths", "matrix"):
        rows = matrix("all" if what == "matrix" else what)
        f = os.path.join(HERE, "cells_%s.json" % what)
        json.dump(rows, open(f, "w"), indent=1)
        for r in rows:
            if "FAIL" in r:
                print("%-24s %s" % (r.get("tag"), r["FAIL"])); continue
            print("%-24s rail %.4f  srcH %.4f  passH %.4f (short %6.1f mV)  "
                  "passL %.4f  t90 %s  Ein %.3f fJ  Egt %.3f fJ  Esup %.3g fJ"
                  % (r["tag"], r["rail_end_V"], r["src_high_loaded_V"],
                     r["pass_HIGH_V"], r["shortfall_HIGH_mV"], r["pass_LOW_V"],
                     ("%.1f" % r["t90_pass_ps"]) if r["t90_pass_ps"] else "n/a",
                     r["E_in_H_fJ"], r["E_gate_fJ"], r["E_supply_fJ"]))
        return
    if what in ("all", "gates"):
        with ThreadPoolExecutor(max_workers=2) as ex:
            fp = ex.submit(gate_peer); ft = ex.submit(gate_tank)
            res["G2_peer"] = fp.result(); res["G3_tank"] = ft.result()
        print(json.dumps(res, indent=1)[:4000])
        json.dump(res, open(os.path.join(HERE, "gates.json"), "w"), indent=1)
    if what in ("all", "cal"):
        jobs = [("peer", "nmux", 0.6, "v15", "cal_peer", None),
                ("tank", "nmux", 0.6, "v15", "cal_tank", None)]
        with ThreadPoolExecutor(max_workers=2) as ex:
            rows = list(ex.map(lambda a: measure(*a[:5], clb=a[5]), jobs))
        for r in rows:
            print(json.dumps(r, indent=1))
        json.dump(rows, open(os.path.join(HERE, "cal.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
