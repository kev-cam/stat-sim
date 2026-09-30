#!/usr/bin/env python3
"""SKEPTIC's DEGRADED-DRIVE probe.  The census (both harnesses) drives every cell
input from an IDEAL source at the FULL swing, so the nMOS pull-down always has
full overdrive and the n-side series stack never binds.  In a real cascade a
cell's input high level is the PREVIOUS bank's DELIVERED rail, which is lower.

BUILD claims that is the mechanism that breaks the block at dV=1.2 and fixes it
at dV=1.65, with a crisp threshold at Vtn+|Vtp|.  This deck tests that claim
independently: same bank, same rail, but the gate drive of the cells whose output
must go LOW is set to a named value instead of the rail.

usage: drv.py <tag> <dv> <vdrive>      tag in nand2 inv
"""
import json, os, sys, time
import myc

HERE = myc.HERE


def bank_drv(tag, dv, vdrive):
    """as myc.bank but the OUTPUT-LOW cells get gate drive `vdrive`, and the
    OUTPUT-HIGH cells get their logic-low inputs at a true 0 (a real previous
    bank does deliver a good 0 -- ground is ground)."""
    cell, vhi, vlo = myc.CASE[tag]
    ports, _ = myc.subckt(cell)
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    for i in range(myc.N):
        g = "gnh" if i in myc.HI else "gnl"
        low_out = i in myc.HI
        vec = vlo if low_out else vhi
        conn = []
        for p in ports:
            if p == ports[0]:
                conn.append("o%d" % i)
            elif p == "VDD":
                conn.append("bkb")
            elif p == "VSS":
                conn.append(g)
            else:
                nd = "i%s_%d" % (p, i)
                lvl = (vdrive if vec[p] else 0.0) if low_out else (dv if vec[p] else 0.0)
                L.append("VI%s_%d %s 0 %g" % (p, i, nd, lvl))
                conn.append(nd)
        L.append("XC%d %s %s" % (i, " ".join(conn), cell))
        L.append("CL%d o%d %s %gf" % (i, i, g, myc.CL))
    return L


if __name__ == "__main__":
    tag, dv, vdrive = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    myc.DV, myc.VGH = dv, max(1.5, dv)
    orig = myc.bank
    myc.bank = lambda t: bank_drv(t, dv, vdrive)
    name = "%s_dv%d_vd%d" % (tag, round(dv * 1000), round(vdrive * 1000))
    t0 = time.monotonic()
    pp, m = myc.run("pd_%s.cir" % name, myc.probe(tag))
    print("probe", m, flush=True)
    assert pp, m
    tz, ipk = myc.zero_after_peak(pp + ".prn")
    print("t_hop %.4f ps" % (tz - myc.T0), flush=True)
    hl, to, tend = myc.hop(tag, tz - myc.T0)
    hp, m = myc.run("hd_%s.cir" % name, hl)
    print("hop", m, flush=True)
    assert hp, m
    r = myc.analyse(hp + ".prn", to, tend)
    r.update(tag=tag, cell=myc.CASE[tag][0], dv=dv, vdrive=vdrive,
             t_hop_ps=tz - myc.T0, wall_s=round(time.monotonic() - t0, 1),
             note="OUTPUT-LOW cells driven at vdrive, not at the rail")
    json.dump(r, open(os.path.join(HERE, "DRV_%s.json" % name), "w"), indent=1)
    lows = {i: r["v_end"][i] for i in myc.HI}
    print("VBEND %.5f  t_valid90 %s  C1 %s" % (r["VBEND"], r["t_valid90_ps"],
                                               r["C1_VALUE"]), flush=True)
    print("output-LOW cells v_end:", {k: round(v, 4) for k, v in lows.items()},
          " half-rail = %.4f" % (0.5 * r["VBEND"]), flush=True)
    print("output-LOW s_end:", {i: round(r["s_end"][i], 2) for i in myc.HI}, flush=True)
