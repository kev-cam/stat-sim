#!/usr/bin/env python3
"""TRACK B -- THE 1/T ENERGY KNOB.

Driver on top of tsw.py (a BYTE-IDENTICAL copy of qal/lsweep/lsw.py, sha256
aff8a89b05a78ed218d6e833a03ecbbea9340e3c152a7963be5798837d27b415).  Nothing in
the hop harness is modified: the deck topology, cells, integrators, .OPTIONS,
dV, CA, RS, VGH, TRUE-ZCS timing and the A2 robust energy metric all come from
tsw.py unchanged.

What this file adds and nothing else:
  * an L list extended UPWARD past the committed 277.8 nH  (T is swept through
    L, t_hop = pi*sqrt(L*C_ser); the zero is RE-PROBED per L by tsw.probe)
  * an RS mechanism check at one L  (is the loss actually resistive?)
  * a DC Ron probe of the transfer TG   (closes the fitted R against a device)
  * a CMOS comparator: the SAME 8 cells, same CL, on a hard rail, energy per
    transition, swept over the same T span  (is CMOS really T-invariant?)
  * an RC_g probe of the cell            (tau = T/RC_g needs a MEASURED RC_g)

Pre-registration: PRE_REGISTERED.json, sha256
f1efead7588b5ef2837717459743abb5fcb08595bef8e435396443a0213b1615, 10424 B,
mtime 2026-09-29 08:39:55 -0700, the only file in this directory at that instant.
"""
import concurrent.futures as cf
import json, math, os, subprocess, sys, time

import tsw

HERE = tsw.HERE
ROWD = os.path.join(HERE, "rowd")
os.makedirs(ROWD, exist_ok=True)

# ---------------------------------------------------------------- the T sweep
# T is varied THROUGH L only.  dV, CA, switch width, RS, VGH, cells, edge and
# tail are all held at the committed values in tsw.py.
L_LIST = [
    ("T01",      1.0), ("T02",      2.0), ("T03",      3.0), ("T06",      6.0),
    ("T10",     10.0), ("T20",     20.0), ("T30",     30.0), ("T45",     45.0),
    ("T60",     60.0), ("T100",   100.0), ("T150",   150.0), ("T200",   200.0),
    ("T278",   277.8),
    # --- new: SLOWER than anything the campaign has measured -----------------
    ("T400",   400.0), ("T600",   600.0), ("T1000", 1000.0), ("T1600", 1600.0),
    ("T2500", 2500.0), ("T4000", 4000.0), ("T6400", 6400.0), ("T10000", 10000.0),
]
L_STRETCH = [("T25000", 25000.0)]

# RS mechanism check, at the committed anchor L
RS_LIST = [("RS1", 1.0), ("RS40", 40.0), ("RS100", 100.0), ("RS200", 200.0)]


def do_point(tag, l_nh, rs=tsw.RS_REF):
    fn = os.path.join(ROWD, tag + ".json")
    if os.path.exists(fn):
        return tag, "cached"
    t0 = time.monotonic()
    try:
        r = tsw.point(tag, l_nh, 15.0, rs, verbose=False)
    except Exception as e:                                          # noqa
        r = dict(tag=tag, L_nH=l_nh, rs_ohm=rs, error="driver: %r" % e)
    r["wall_s"] = time.monotonic() - t0
    r.setdefault("tag", tag)
    json.dump(r, open(fn, "w"), indent=1)
    return tag, ("ERR " + r["error"] if "error" in r else
                 "t_hop %.2f ps  E_R %.4f  E_swblk %.4f  E_gate %.4f  %s"
                 % (r["t_hop_ps"], r["E_R_toC_fJ"], r["E_switchblock_toC_fJ"],
                    r["E_gate_drive_fJ"], r["C4_instrument"]))


def stage_sweep(which="main", workers=4):
    jobs = []
    if which in ("main", "all"):
        jobs += [(t, l, tsw.RS_REF) for t, l in L_LIST]
    if which in ("stretch", "all"):
        jobs += [(t, l, tsw.RS_REF) for t, l in L_STRETCH]
    if which in ("rs", "all"):
        jobs += [(t, tsw.L_REF, rs) for t, rs in RS_LIST]
    print("%d jobs, %d workers" % (len(jobs), workers))
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(do_point, t, l, rs): t for t, l, rs in jobs}
        for f in cf.as_completed(futs):
            tag, msg = f.result()
            print("  %-8s %s" % (tag, msg), flush=True)


# ------------------------------------------------------- DC Ron of the TG
def stage_ron():
    """DC on-resistance of the committed tg15p transfer switch (TG 5/10 um,
    nMOS gate at VGH=1.5, pMOS gate at 0).  Swept over the channel voltage the
    hop actually traverses.  This closes the R that the 1/T fit infers against
    a device number, so the fitted R is not free-floating."""
    w = tsw.widths(15.0)
    L = tsw.head() + [
        "VHI vhi 0 %g" % tsw.VGH,
        "VG  gt  0 %g" % tsw.VGH,
        "VGP gtp 0 0",
        "VA  a   0 0.5",
        "VF  f   0 0",                      # forced small offset -> I -> Ron
        "XSWN a gt b 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
        "XSWP a gtp b vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
        "VMB b bb 0", "RB bb 0 1meg",
        ".dc VA 0.0 1.2 0.02",
        ".print dc V(a) I(VMB)", ".end"]
    # a 1 meg load makes I tiny; instead drive B with a source 10 mV below A
    L = tsw.head() + [
        "VHI vhi 0 %g" % tsw.VGH,
        "VG  gt  0 %g" % tsw.VGH,
        "VGP gtp 0 0",
        "VA  a   0 0.5",
        "BB  b   0 V={ V(a) - 0.010 }",
        "XSWN a gt m 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
        "XSWP a gtp m vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
        "VMB m b 0",
        ".dc VA 0.0 1.2 0.02",
        ".print dc V(a) I(VMB)", ".end"]
    p, msg = tsw.run("ron.cir", L)
    print("  " + msg)
    if p is None:
        return None
    hdr, rows = tsw.read_prn(p + ".prn")
    ia = hdr.index("V(A)"); ii = [i for i, h in enumerate(hdr) if "VMB" in h][0]
    out = [dict(V=r[ia], I_uA=r[ii] * 1e6,
                Ron_ohm=(0.010 / abs(r[ii]) if abs(r[ii]) > 1e-12 else None))
           for r in rows]
    json.dump(out, open(os.path.join(HERE, "ron.json"), "w"), indent=1)
    for o in out:
        if o["Ron_ohm"]:
            print("   V=%.2f  I=%9.3f uA  Ron=%8.2f ohm" % (o["V"], o["I_uA"], o["Ron_ohm"]))
    return out


# ---------------------------------------------------- RC_g of the cell
def stage_rcg(vdd=1.2):
    """MEASURED RC_g: the committed cell (wp=1.12u/wn=0.74u, CL=2 fF) driven by
    an ideal STEP on a hard rail.  RC_g is taken from the 10-90% output rise and
    fall, RC = t1090/2.1972, and separately from t50/ln2.  tau = T/RC_g in the
    crossover map is defined on this quantity, so it is measured here rather
    than inherited."""
    L = tsw.head() + [
        "VDD vdd 0 %g" % vdd,
        "VINR ir 0 PWL(0 %g 100p %g 100.5p 0 800p 0)" % (vdd, vdd),
        "VINF if 0 PWL(0 0 100p 0 100.5p %g 800p %g)" % (vdd, vdd),
        # rising-output cell (input goes high->low)
        "XPR or ir vdd vdd sg13_lv_pmos w=%gu l=0.13u" % tsw.WP,
        "XNR or ir 0 0 sg13_lv_nmos w=%gu l=0.13u" % tsw.WN,
        "CLR or 0 %gf" % tsw.CLOAD,
        # falling-output cell (input goes low->high)
        "XPF of if vdd vdd sg13_lv_pmos w=%gu l=0.13u" % tsw.WP,
        "XNF of if 0 0 sg13_lv_nmos w=%gu l=0.13u" % tsw.WN,
        "CLF of 0 %gf" % tsw.CLOAD,
        ".ic V(or)=0 V(of)=%g" % vdd,
        ".tran 0.005p 800p 0 0.02p",
        ".print tran V(or) V(of)", ".end"]
    p, msg = tsw.run("rcg_v%03d.cir" % int(round(vdd * 100)), L)
    print("  " + msg)
    if p is None:
        return None
    hdr, rows = tsw.read_prn(p + ".prn")
    io, jf = hdr.index("V(OR)"), hdr.index("V(OF)")
    ts = [r[1] * 1e12 for r in rows]

    def cross(col, frac, rising):
        tgt = frac * vdd if rising else (1.0 - frac) * vdd
        prev = None
        for k, r in enumerate(rows):
            if ts[k] < 100.5:
                prev = k
                continue
            v = r[col]
            if prev is not None:
                pv = rows[prev][col]
                hit = (pv < tgt <= v) if rising else (pv > tgt >= v)
                if hit:
                    f = (tgt - pv) / (v - pv) if v != pv else 0.0
                    return ts[prev] + f * (ts[k] - ts[prev]) - 100.5
            prev = k
        return None
    r10, r90, r50 = cross(io, .1, True), cross(io, .9, True), cross(io, .5, True)
    f10, f90, f50 = cross(jf, .1, False), cross(jf, .9, False), cross(jf, .5, False)
    out = dict(vdd=vdd,
               rise_t10=r10, rise_t50=r50, rise_t90=r90,
               fall_t10=f10, fall_t50=f50, fall_t90=f90,
               RC_rise_from_1090=(r90 - r10) / 2.1972 if r10 and r90 else None,
               RC_fall_from_1090=(f90 - f10) / 2.1972 if f10 and f90 else None,
               RC_rise_from_t50=r50 / math.log(2) if r50 else None,
               RC_fall_from_t50=f50 / math.log(2) if f50 else None)
    out["RC_g_ps"] = max(out["RC_rise_from_1090"], out["RC_fall_from_1090"])
    json.dump(out, open(os.path.join(HERE, "rcg_v%03d.json" % int(round(vdd * 100))), "w"),
              indent=1)
    print("   " + json.dumps({k: (round(v, 4) if isinstance(v, float) else v)
                              for k, v in out.items()}))
    return out


# ------------------------------------------------------- CMOS comparator
def cmos_deck(period_ps, edge_ps, vdd, ncyc=4):
    """The SAME 8 cells (4 hi-input, 4 lo-input -> they toggle together) with
    the SAME CL = 2 fF, on a HARD vdd rail.  Supply energy metered with the same
    1F integrator instrument the QAL hop uses, t0-referenced, over WHOLE cycles.

    Two knobs, swept independently in the stages below:
      period_ps -- the cycle time (the 'T' of the comparison)
      edge_ps   -- the input transition time (CMOS short-circuit current lives
                   here; a slowed-down design has slowed-down edges too)
    """
    hi, lo = vdd, 0.0
    tpts, t = [], 0.0
    # square-ish input: low for half a period, high for half, trapezoid edges
    seq = []
    for c in range(ncyc):
        t0 = c * period_ps
        seq += [(t0, lo), (t0 + edge_ps, hi),
                (t0 + period_ps / 2.0, hi), (t0 + period_ps / 2.0 + edge_ps, lo)]
    seq.append((ncyc * period_ps, lo))
    pw = " ".join("%gp %g" % (tt, vv) for tt, vv in seq)
    tend = ncyc * period_ps
    step = min(edge_ps / 20.0, period_ps / 2000.0)
    L = tsw.head() + [
        "VDD vdd 0 %g" % vdd,
        "VIN in 0 PWL(%s)" % pw,
        "VINB inb 0 PWL(%s)" % " ".join("%gp %g" % (tt, (vdd - vv)) for tt, vv in seq),
    ]
    for i in range(tsw.MGATE):
        src = "in" if i in tsw.HI else "inb"
        L += ["XP%d o%d %s vdd vdd sg13_lv_pmos w=%gu l=0.13u" % (i, i, src, tsw.WP),
              "XN%d o%d %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i, i, src, tsw.WN),
              "CL%d o%d 0 %gf" % (i, i, tsw.CLOAD)]
    # supply-energy integrator (1F cap, same instrument as the hop deck)
    L += tsw.integ("evdd", "-%g*I(VDD)" % vdd)
    L += tsw.integ("qvdd", "-I(VDD)")
    # input-drive energy: what it costs to move the 8 cells' gate capacitance
    L += tsw.integ("ein", "-V(in)*I(VIN)-V(inb)*I(VINB)")
    # NO .ic.  An .ic that contradicts the inputs holds the output against a
    # fully-on pMOS and injects a ~186 uA DC short-circuit current at the
    # operating point; its 1F-integrator PEDESTAL (2.235e-6 V) then quantises
    # the readout at 9 printed digits to a 10 fJ LSB, which is larger than the
    # whole signal.  Caught by the periodicity check reading exactly +-100%.
    # DCOP finds the correct state on its own from the t=0 input levels.
    L += [".tran %gp %gp 0 %gp" % (step, tend, min(step * 4, period_ps / 500.0)),
          ".print tran V(in) V(o0) V(o1) V(xevdd) V(xqvdd) V(xein)", ".end"]
    return L, tend


def leak_deck(vdd, thold_ps=2000.0):
    """STATIC leakage of the same 8 cells, inputs held, nothing switching.
    This is the only T-PROPORTIONAL term on the CMOS side; measuring it
    separately lets the comparator's T-dependence be attributed, not assumed."""
    L = tsw.head() + ["VDD vdd 0 %g" % vdd, "VIN in 0 0", "VINB inb 0 %g" % vdd]
    for i in range(tsw.MGATE):
        src = "in" if i in tsw.HI else "inb"
        L += ["XP%d o%d %s vdd vdd sg13_lv_pmos w=%gu l=0.13u" % (i, i, src, tsw.WP),
              "XN%d o%d %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i, i, src, tsw.WN),
              "CL%d o%d 0 %gf" % (i, i, tsw.CLOAD)]
    L += tsw.integ("evdd", "-%g*I(VDD)" % vdd)
    L += [".tran %gp %gp 0 %gp" % (thold_ps / 2000.0, thold_ps, thold_ps / 500.0),
          ".print tran V(o0) V(o1) V(xevdd)", ".end"]
    return L, thold_ps


def leak_point(vdd, thold_ps=2000.0):
    tag = "lk_v%03d" % int(round(vdd * 100))
    fn = os.path.join(ROWD, tag + ".json")
    if os.path.exists(fn):
        return json.load(open(fn))
    L, tend = leak_deck(vdd, thold_ps)
    p, msg = tsw.run(tag + ".cir", L)
    print("  " + msg)
    if p is None:
        return None
    hdr, rows = tsw.read_prn(p + ".prn")
    ie = hdr.index("V(XEVDD)")
    ts = [r[1] * 1e12 for r in rows]
    e = (rows[-1][ie] - rows[0][ie]) * 1e15
    r = dict(tag=tag, vdd=vdd, window_ps=ts[-1] - ts[0],
             E_leak_fJ=e, P_leak_fJ_per_ps=e / (ts[-1] - ts[0]),
             I_leak_uA=e / (ts[-1] - ts[0]) * 1e-15 / 1e-12 / vdd * 1e6)
    json.dump(r, open(fn, "w"), indent=1)
    print("   leak vdd=%.4f: %.6g fJ over %.1f ps  ->  %.6g fJ/ps  (%.4g uA)"
          % (vdd, e, ts[-1] - ts[0], r["P_leak_fJ_per_ps"], r["I_leak_uA"]))
    return r


def cmos_point(tag, period_ps, edge_ps, vdd, ncyc=4):
    fn = os.path.join(ROWD, "cm_" + tag + ".json")
    if os.path.exists(fn):
        return tag, "cached"
    L, tend = cmos_deck(period_ps, edge_ps, vdd, ncyc)
    t0 = time.monotonic()
    p, msg = tsw.run("cm_%s.cir" % tag, L)
    if p is None:
        r = dict(tag=tag, error=msg)
        json.dump(r, open(fn, "w"), indent=1)
        return tag, "ERR " + msg
    hdr, rows = tsw.read_prn(p + ".prn")
    ie, iq, ii = hdr.index("V(XEVDD)"), hdr.index("V(XQVDD)"), hdr.index("V(XEIN)")
    ts = [r[1] * 1e12 for r in rows]

    def at(t, c):
        # clamp: ts[-1] is the requested tend but 1e-10*1e12 round-trips to
        # 487.99999999999994 for tend=488, which fell OUTSIDE every interval and
        # returned nan.  Caught by the nan guard on the period-122 rows.
        t = min(max(t, ts[0]), ts[-1])
        prev = None
        for k, tt in enumerate(ts):
            if prev is not None and ts[prev] <= t <= tt:
                a, b = ts[prev], tt
                f = (t - a) / (b - a) if b != a else 0.0
                return rows[prev][c] + f * (rows[k][c] - rows[prev][c])
            prev = k
        return float("nan")
    # measure over the LAST full cycle only (settled), t0-referenced inside it
    ta, tb = (ncyc - 1) * period_ps, ncyc * period_ps
    e_cyc = (at(tb, ie) - at(ta, ie)) * 1e15
    q_cyc = (at(tb, iq) - at(ta, iq)) * 1e15
    ein_cyc = (at(tb, ii) - at(ta, ii)) * 1e15
    # and the previous cycle, as a settling / periodicity check
    e_prev = (at(ta, ie) - at((ncyc - 2) * period_ps, ie)) * 1e15
    r = dict(tag=tag, period_ps=period_ps, edge_ps=edge_ps, vdd=vdd, ncyc=ncyc,
             E_supply_per_cycle_fJ=e_cyc, Q_supply_per_cycle_fC=q_cyc,
             E_indrive_per_cycle_fJ=ein_cyc,
             E_supply_prev_cycle_fJ=e_prev,
             periodicity_pct=100.0 * (e_cyc / e_prev - 1.0) if e_prev else None,
             E_supply_per_transition_fJ=e_cyc / 2.0,
             E_per_cell_per_transition_fJ=e_cyc / 2.0 / tsw.MGATE,
             half_CV2_8cell_fJ=0.5 * (tsw.MGATE * tsw.CLOAD * 1e-15) * vdd * vdd * 1e15,
             wall_s=time.monotonic() - t0)
    json.dump(r, open(fn, "w"), indent=1)
    return tag, ("P %8.1f ps edge %6.2f  E/cyc %8.4f fJ  E/trans %8.4f fJ  "
                 "periodicity %+.3f%%" % (period_ps, edge_ps, e_cyc,
                                          e_cyc / 2.0, r["periodicity_pct"] or 0.0))


# The T points the QAL hop actually lands on, so the comparator is like-for-like.
CMOS_T = [16, 28, 50, 86, 106, 122, 158, 194, 226, 266, 320, 392, 506, 640,
          800, 1012, 1280, 1600]


def stage_cmos(workers=4):
    # ANCHOR CHECK: the campaign's committed CMOS inverter energy anchor is
    # 10.0831 fJ/cycle/cell at 1.2 V with a 34.81 ps edge (the CMOS inverter
    # floor delay) -- bound/RESULTS.json.  Reproducing it here makes the
    # comparator an instrument, not a fresh assumption.
    jobs = [("anch_v120", 266.0, 34.81, 1.2)]
    for vdd in (1.2, 1.0):
        for T in CMOS_T:
            # (A) FIXED fast edge: pure test of T-invariance of the dynamic term
            jobs.append(("f%03d_v%03d" % (T, int(vdd * 100)), float(T), 5.0, vdd))
            # (B) edge SCALED with the period (a slowed design slows its edges):
            jobs.append(("s%03d_v%03d" % (T, int(vdd * 100)), float(T),
                         max(2.0, 0.25 * T), vdd))
    print("%d cmos jobs" % len(jobs))
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(cmos_point, t, p, e, v): t for t, p, e, v in jobs}
        for f in cf.as_completed(futs):
            tag, msg = f.result()
            print("  %-14s %s" % (tag, msg), flush=True)


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "sweep":
        stage_sweep(sys.argv[2] if len(sys.argv) > 2 else "main",
                    int(sys.argv[3]) if len(sys.argv) > 3 else 4)
    elif st == "ron":
        stage_ron()
    elif st == "rcg":
        for v in (1.2, 1.0, 0.6754):
            stage_rcg(v)
    elif st == "cmos":
        stage_cmos(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    elif st == "leak":
        for v in (1.2, 1.0):
            leak_point(v)
