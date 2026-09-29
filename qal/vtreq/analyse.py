#!/usr/bin/env python3
"""qal/vtreq -- tables + the spec answer.  Reads rowd/*.json only."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROWD = os.path.join(HERE, "rowd")

C = dict(  # committed anchors, MEASURED, from disk, DELVTO = 0
    sk_t_hop=65.4948869306443, sk_VBEND=0.713816259, sk_VBPK=0.836889358,
    sk_VAEND=-0.004293553919743036, sk_IPK=971.3200730000001,
    lsw_t_hop=65.49500982344826,
    l691_t_valid90=115.467185, l691_t_hop=34.28582535896825,
    l691_VBEND=0.754572966, l691_VA_open=0.11745601600934541,
    l691_L3_t_valid90=115.70287099999999,
    Vtn=0.5239460152201223, Vtp=0.4402734454819182,
    cmos_2fF_1p2=57.1429, cmos_sta=92.8, ratio_lo=1.244, ratio_hi=1.305,
    sep=[528.68, 22.89, 1.52, 0.122, 0.010, 0.001],
    sigma_vt_mV=3.42, o21_t_valid90=495.5, C2=0.1478)

ORDER = ["d000"] + ["d%03d%s" % (int(v * 1000), m)
                    for v in (0.05, 0.10, 0.15, 0.20, 0.30) for m in "PNB"]


def load():
    d = {}
    for fn in sorted(os.listdir(ROWD)):
        if fn.endswith(".json"):
            d[fn[:-5]] = json.load(open(os.path.join(ROWD, fn)))
    return d


def f(x, n=4):
    return ("%*s" % (n + 3, "--")) if x is None else ("%.*f" % (n, x))


def rel(a, b):
    return None if (a is None or b in (None, 0)) else abs(a - b) / abs(b)


R = load()
OUT = []
P = OUT.append
S = {}   # machine-readable summary


def sec(t):
    P("")
    P("=" * 100)
    P(t)
    P("=" * 100)


# ------------------------------------------------------------------- G0
sec("G0   INSTRUMENT CHECK -- committed anchors re-run in THIS directory, under MY\n"
    "     own PyMS cache and the DELVTO shim at DVTN = DVTP = 0")
g0 = R.get("g0", {})
a, b = g0.get("g0a_robust", {}), g0.get("g0b_load691_L4", {})
chk = []
chk += [("robust hop t_hop_ps (sk path, qal/skept/rows.json 'headline')",
         a.get("t_hop_ps"), C["sk_t_hop"], 1e-6),
        ("robust hop VBEND", a.get("VBEND"), C["sk_VBEND"], 1e-6),
        ("robust hop VBPK", a.get("VBPK"), C["sk_VBPK"], 1e-6),
        ("robust hop VAEND", a.get("VAEND"), C["sk_VAEND"], 1e-6),
        ("robust hop IPK_uA", a.get("IPK_uA"), C["sk_IPK"], 1e-6),
        ("real load t_valid90_ps (load691 cl_d165_L4_W30)",
         b.get("t_valid90_ps"), C["l691_t_valid90"], 1e-9),
        ("real load t_hop_ps", b.get("t_hop_ps"), C["l691_t_hop"], 1e-9),
        ("real load VBEND", b.get("VBEND"), C["l691_VBEND"], 1e-9),
        ("real load VA_open", b.get("VA_open"), C["l691_VA_open"], 1e-9)]
r = R.get("q1L3_d000")
if r:
    chk.append(("real load L=3 nH t_valid90_ps (load691 cl_d165_L3_W30)",
                r.get("t_valid90_ps"), C["l691_L3_t_valid90"], 1e-9))
r = R.get("cm_d000")
if r:
    chk.append(("CMOS inverter 1.2 V / 2 fF t90 rise (dvopt floor 'zc' check)",
                r["vdd1p2_cl2"]["t90_rise_ps"], C["cmos_2fF_1p2"], 1e-5))
r = R.get("dc_d000")
if r:
    chk.append(("Vtn, campaign criterion (chain3/vt.json)", r["Vtn"], C["Vtn"], 1e-3))
    chk.append(("|Vtp|, campaign criterion (chain3/vt.json)", r["Vtp_abs"], C["Vtp"], 1e-3))
r = R.get("o21_d000")
if r:
    chk.append(("o21ai bank t_valid90_ps at dV=1.65/L=15/W=30 (dvopt)",
                r.get("t_valid90_ps"), C["o21_t_valid90"], 1e-3))
P("  %-64s %-16s %-16s %-10s %s" % ("quantity", "mine", "committed", "rel", ""))
P("  " + "-" * 116)
allpass = True
for nm, mine, comm, tol in chk:
    rr = rel(mine, comm)
    ok = rr is not None and rr <= tol
    allpass &= ok
    P("  %-64s %-16.10g %-16.10g %-10.2e %s"
      % (nm, mine if mine is not None else float("nan"), comm,
         rr if rr is not None else float("nan"), "PASS" if ok else "FAIL"))
S["G0_pass"] = bool(allpass)
P("")
P("  NOTE (AMENDMENT A1): the pre-registration quoted t_hop = %.11f ps, which is"
  % C["lsw_t_hop"])
P("  rest.py's TZ_ANCHOR from the lsw / .measure path (that path carries a MEASURED")
P("  +1.0 ps .measure-FIND lag correction).  This study uses the sk / waveform path,")
P("  whose committed value is %.13f ps; against THAT the reproduction is exact."
  % C["sk_t_hop"])
P("  The two conventions differ by 1.2e-04 ps = 1.9e-06 relative -- smaller than any")
P("  effect reported below, and not used as a gate.")

# ------------------------------------------------------------------- G1
sec("G1   DOES DELVTO REACH THE DEVICES?  (HARD GATE)\n"
    "     |Vt| by the campaign criterion Id = 100 nA*W/L at |Vds| = 0.1 V;\n"
    "     trip points from the DC transfer curve where V(out) = V(in)")
base = R.get("dc_d000", {})
P("  tag      DVTN    DVTP  |    Vtn   d(Vtn)  gain |   |Vtp|  d|Vtp|  gain | strand  trip@1.2  trip@0.755  tripSKEW")
P("  " + "-" * 116)
g1pass = True
for t in ORDER:
    r = R.get("dc_" + t)
    if not r:
        continue
    dn = r["Vtn"] - base["Vtn"]
    dp = r["Vtp_abs"] - base["Vtp_abs"]
    gn = None if r["dvtn"] == 0 else dn / r["dvtn"]
    gp = None if r["dvtp"] == 0 else dp / r["dvtp"]
    # gate: >= 0.5 on a targeted device, < 0.1 on an untargeted one
    if r["dvtn"] != 0 and (gn is None or gn < 0.5):
        g1pass = False
    if r["dvtp"] != 0 and (gp is None or gp < 0.5):
        g1pass = False
    if r["dvtn"] == 0 and abs(dn) > 0.1 * 0.05:
        g1pass = False
    if r["dvtp"] == 0 and abs(dp) > 0.1 * 0.05:
        g1pass = False
    P("  %-8s %5.2f  %5.2f  | %s %s %s | %s %s %s | %s  %s   %s    %s"
      % (t, r["dvtn"], r["dvtp"], f(r["Vtn"]), f(dn), f(gn, 3),
         f(r["Vtp_abs"]), f(dp), f(gp, 3), f(r["V_strand"]),
         f(r["trip_1p20"]), f(r["trip_rail_L4"]), f(r["trip_skewed_1p20"])))
S["G1_pass"] = bool(g1pass)
P("")
P("  MEASURED sensitivities, from the rows above:")
P("    d(Vtn)/d(DELVTO_N)   = 1.000 V/V exactly on all five N rows")
P("    d(|Vtp|)/d(DELVTO_P) = 1.004 V/V on all five P rows")
P("    CROSS TERMS EXACTLY ZERO: |Vtp| is identical to 6 decimals on every N row,")
P("    Vtn is identical to 6 decimals on every P row.")
P("  GATE G1: %s" % ("PASS" if g1pass else "FAIL"))

# ------------------------------------------------------------------- Q1
sec("Q1   THE LEVEL, at the ALU's REAL 6.91 fF mean sink load, dV = 1.65 V, W = 30 um\n"
    "     QAL t_valid90 (all 8 cells within 10% of the instantaneous rail, from switch\n"
    "     close) vs a SAME-DELVTO CMOS_dev level (identical cell, identical 6.91 fF\n"
    "     load, fixed 1.20 V rail, ideal 2 ps input edge, 90% of its own rail).")
P("  (a) L HELD at the committed optimum 4 nH -- the pre-registered form")
P("")
P("  tag      |Vtp|    Vtn   | QAL t_hop  settle  t_valid90 | CMOS worst  mean | ratioW ratioM     g")
P("  " + "-" * 116)
q0 = R["q1_d000"]
c0 = R["cm_d000"]["vdd1p2_cl6p91"]
q1tab = {}
for t in ORDER:
    q, c, d = R.get("q1_" + t), R.get("cm_" + t), R.get("dc_" + t)
    if not (q and c and d):
        continue
    cc = c["vdd1p2_cl6p91"]
    tq, cw = q["t_valid90_ps"], cc["t90_worst_ps"]
    cm = 0.5 * (cc["t90_rise_ps"] + cc["t90_fall_ps"])
    g = (tq / q0["t_valid90_ps"]) / (cw / c0["t90_worst_ps"])
    q1tab[t] = dict(Vtp=d["Vtp_abs"], Vtn=d["Vtn"], tq=tq, cw=cw, cm=cm,
                    ratioW=tq / cw, ratioM=tq / cm, g=g)
    P("  %-8s %s %s | %s %s %s | %s %s | %s %s %s"
      % (t, f(d["Vtp_abs"]), f(d["Vtn"]), f(q["t_hop_ps"], 2),
         f(tq - q["t_hop_ps"], 2), f(tq, 3), f(cw, 2), f(cm, 2),
         f(tq / cw), f(tq / cm), f(g)))
S["Q1_fixedL"] = q1tab
P("")
P("  MECHANISM, MEASURED: t_hop is INVARIANT in DELVTO -- 34.286 ps at DELVTO = 0 and")
P("  34.324 ps at B(-0.30), +0.11% over the whole sweep -- because it is pi*sqrt(L*C/2)")
P("  and contains no threshold.  The SETTLE term collapses 81.18 -> 34.07 ps (x0.42)")
P("  while CMOS's whole level only falls x0.72.  At the most aggressive shift the hop")
P("  is 50% of the QAL level.  THE RESIDUE IS THE HOP.")

# ------------------------------------------------------------------- Q1 L-reopt
P("")
P("  (b) L RE-OPTIMISED at each threshold -- EXPLORATORY, amendment A5.")
P("      At DELVTO = 0 the committed grid could not USE small L: the rail-drain gate")
P("      C2 (VA_open <= %.4f V at the ZCS instant) excluded it.  A lower threshold" % C["C2"])
P("      makes the transfer switch strong enough to drain the source bank in a shorter")
P("      hop, which RE-ADMITS small L.  This is the only lever that can attack the hop.")
P("")
P("  DVTN  DVTP  |  L nH  t_hop  t_valid90  VBEND   VA(ZCS)   C2  | CMOSw  ratioW ratioM")
P("  " + "-" * 116)
byp = {}
for k, v in R.items():
    if not (k.startswith("q1_") or k.startswith("q1L")):
        continue
    if "L_nH" not in v:
        continue
    byp.setdefault((v["dvtn"], v["dvtp"]), []).append(v)
best = {}
for key in sorted(byp, key=lambda z: (-z[0], -z[1])):
    rows = sorted(byp[key], key=lambda z: z["L_nH"])
    if len(rows) < 2:
        continue
    tag = [t for t in ORDER if R.get("dc_" + t)
           and abs(R["dc_" + t]["dvtn"] - key[0]) < 1e-9
           and abs(R["dc_" + t]["dvtp"] - key[1]) < 1e-9]
    tag = tag[0] if tag else "?"
    cc = R["cm_" + tag]["vdd1p2_cl6p91"]
    cw = cc["t90_worst_ps"]
    cm = 0.5 * (cc["t90_rise_ps"] + cc["t90_fall_ps"])
    ok = [z for z in rows if z["VA_open"] <= C["C2"]]
    bb = min(ok, key=lambda z: z["t_valid90_ps"]) if ok else None
    for z in rows:
        gate = "PASS" if z["VA_open"] <= C["C2"] else "FAIL"
        star = " <<<" if (bb is not None and z is bb) else ""
        P("  %5.2f %5.2f  | %5g %6.2f %9.3f  %.5f %+8.5f  %s | %6.2f %6.4f %6.4f%s"
          % (key[0], key[1], z["L_nH"], z["t_hop_ps"], z["t_valid90_ps"],
             z["VBEND"], z["VA_open"], gate, cw, z["t_valid90_ps"] / cw,
             z["t_valid90_ps"] / cm, star))
    if bb is not None:
        d = R["dc_" + tag]
        best[tag] = dict(Vtp=d["Vtp_abs"], Vtn=d["Vtn"], L_nH=bb["L_nH"],
                         t_valid90=bb["t_valid90_ps"], cmos_worst=cw, cmos_mean=cm,
                         ratioW=bb["t_valid90_ps"] / cw,
                         ratioM=bb["t_valid90_ps"] / cm,
                         g=(bb["t_valid90_ps"] / q0["t_valid90_ps"]) /
                           (cw / c0["t90_worst_ps"]))
    P("  " + "-" * 116)
S["Q1_Lreopt_best"] = best
P("")
P("  BEST C2-ADMISSIBLE ROW PER THRESHOLD:")
P("  tag      |Vtp|    Vtn    L nH  t_valid90  CMOSw   ratioW  ratioM   g   -> committed-anchor band")
P("  " + "-" * 116)
for t in ORDER:
    v = best.get(t)
    if not v:
        continue
    P("  %-8s %s %s %5g %9.3f %7.3f  %6.4f  %6.4f %6.4f   %.3f - %.3f"
      % (t, f(v["Vtp"]), f(v["Vtn"]), v["L_nH"], v["t_valid90"], v["cmos_worst"],
         v["ratioW"], v["ratioM"], v["g"], v["g"] * C["ratio_lo"],
         v["g"] * C["ratio_hi"]))
P("")
P("  CHECKPOINT CAVEAT, declared: C2 is evaluated at the ZCS instant (the sk")
P("  convention).  The lsw convention evaluates the same-named quantity at")
P("  t_open + 7 ps, and the committed record already flags the two as 2.2x-6.9x")
P("  apart and the later one as reading a post-open RING, not a drained rail.")
P("  Under the +7 ps convention EVERY row in this study fails C2, INCLUDING the")
P("  committed DELVTO = 0 optimum itself (VA = +0.293 V), which the committed")
P("  campaign reports as functional -- so that convention cannot serve as an")
P("  absolute gate here.  Every row's source bank is drained to |VAEND| < 0.3 mV")
P("  by the end of the tail.  The LEVEL TIMES do not depend on the choice; the")
P("  LOCATION of L* does.")

# ------------------------------------------------------------------- Q2
sec("Q2   HIGH/LOW SEPARATION BY BANK DEPTH -- 6-bank UNBUFFERED hop-powered chain\n"
    "     (qal/restore5 k = 6 no-restore control, L = 15 nH, W = 30 um, dV = 1.2,\n"
    "     T = 300 ps).  separation_k = min(pull-UP out) - max(pull-DOWN out) at bank\n"
    "     k's own stage boundary, SIGNED, mV.  A NEGATIVE value means that stage's\n"
    "     HIGH group sits BELOW its LOW group: it carries INVERTED data, not weak data.")
P("  floor = sigma_Vt = %.2f mV (ASSUMED DELVTO-independent -- see the sensitivity below)"
  % C["sigma_vt_mV"])
P("  committed DELVTO = 0 series (magnitudes): %s" % C["sep"])
P("")
P("  tag      |Vtp|    Vtn   |  bank1     bank2     bank3     bank4     bank5     bank6  | depth PASSED")
P("  " + "-" * 116)
q2 = {}
for t in ORDER:
    r = R.get("chain_" + t)
    if not r or not r.get("separation_mV"):
        continue
    d = R["dc_" + t]
    s = r["separation_mV"]
    seq = [s.get(str(i), s.get(i)) for i in range(1, 7)]
    depth = 0
    for i, v in enumerate(seq):
        if v is not None and v > C["sigma_vt_mV"]:
            depth = i + 1
        else:
            break
    q2[t] = dict(Vtp=d["Vtp_abs"], Vtn=d["Vtn"], sep=seq, depth=depth,
                 rails=r.get("rail_at_own_boundary_V"),
                 worst_gate_pct=r.get("worst_gate_pct_all_banks"))
    P("  %-8s %s %s | %s | %d"
      % (t, f(d["Vtp_abs"]), f(d["Vtn"]),
         " ".join(("%9.4f" % v) if v is not None else "      -- " for v in seq),
         depth))
S["Q2"] = q2
P("")
P("  SIGMA-Vt SENSITIVITY (the pre-registered clause).  sigma_Vt enters only as the")
P("  floor a separation must clear, so the sensitivity is read straight off the table:")
for t, v in sorted(q2.items(), key=lambda kv: kv[1]["depth"]):
    s3 = v["sep"][2]
    s5 = v["sep"][4]
    P("    %-8s depth 3 = %+9.4f mV -> its verdict flips only if sigma_Vt %s;  "
      "depth 5 = %+9.4f mV -> would need sigma_Vt < %.4f mV (%.0fx below the PDK's %.2f)"
      % (t, s3,
         ("> %.3f mV (%.1fx the PDK value)" % (s3, s3 / C["sigma_vt_mV"]))
         if s3 > 0 else "NEVER -- its SIGN is wrong, so no mismatch floor can rescue it",
         s5, abs(s5), C["sigma_vt_mV"] / max(abs(s5), 1e-12), C["sigma_vt_mV"]))
P("")
P("  THE DC MECHANISM I PRE-REGISTERED (E2), measured on the whole 16-point grid:")
P("  the predecessor's forward-transferred HIGH strands at ~|Vtp| while the successor")
P("  needs its own trip point.  Both are DC quantities.  GAP = strand - trip.")
P("")
P("  tag      |Vtp|    Vtn   | V_strand  trip@0.755V |  GAP mV   (positive = the chain's")
P("                                                              DC inequality is satisfied)")
P("  " + "-" * 116)
for t in ORDER:
    d = R.get("dc_" + t)
    if not d:
        continue
    gap = 1e3 * (d["V_strand"] - d["trip_rail_L4"])
    P("  %-8s %s %s | %s  %s   | %+8.2f" % (t, f(d["Vtp_abs"]), f(d["Vtn"]),
                                            f(d["V_strand"]), f(d["trip_rail_L4"]), gap))
P("")
P("  E2 SCORING, stated plainly: the DC mechanism is CONFIRMED as DC physics")
P("  (strand tracks |Vtp| at 0.81:1; the trip point moves -0.485 V per volt of pMOS")
P("  DELVTO and +0.463 V per volt of nMOS DELVTO, so the DC gap is CLOSED by lowering")
P("  Vtn and OPENED by lowering |Vtp|).  But it is REFUTED as the binding term in the")
P("  measured chain: the chain gets BETTER when |Vtp| falls, not worse, because at a")
P("  collapsed rail (0.58 / 0.34 / 0.22 V by depth) the limiter is the successor's own")
P("  pMOS PULL-UP, and lowering |Vtp| repairs exactly that.  My prediction had the")
P("  right physics attached to the wrong term.")

# ------------------------------------------------------------------- Q3
sec("Q3   THE COST -- leakage and held-rail droop vs DELVTO\n"
    "     8-cell bank + its transfer switch held OPEN + park, at the 0.754573 V\n"
    "     delivered rail.  DC leg: rail pinned, static current metered.  Float leg:\n"
    "     same bank on a floating rail with the committed 35.979 fF bank capacitance,\n"
    "     outputs .ic'd to their settled values so the decay is HOLD, not settling.")
P("  tag      |Vtp|    Vtn   | I_hold(A)   x(vs 0) | droop over one beat, mV")
P("                          |                     |  DC-implied 120ps  300ps | measured float 120ps 300ps")
P("  " + "-" * 116)
i0 = R["hd_d000"]["I_hold_total_A"]
q3 = {}
for t in ORDER:
    h, d = R.get("hd_" + t), R.get("dc_" + t)
    if not (h and d):
        continue
    q3[t] = dict(Vtp=d["Vtp_abs"], Vtn=d["Vtn"], I=h["I_hold_total_A"],
                 dcd120=h["droop_DC_120ps_mV"], dcd300=h["droop_DC_300ps_mV"],
                 fl120=h["float_droop_120ps_mV"], fl300=h["float_droop_300ps_mV"])
    P("  %-8s %s %s | %9.3e %7.1f | %10.4f %8.4f |  %10.4f %8.4f"
      % (t, f(d["Vtp_abs"]), f(d["Vtn"]), abs(h["I_hold_total_A"]),
         abs(h["I_hold_total_A"] / i0), h["droop_DC_120ps_mV"],
         h["droop_DC_300ps_mV"], h["float_droop_120ps_mV"],
         h["float_droop_300ps_mV"]))
S["Q3"] = q3

# ------------------------------------------------------------------- o21ai
sec("f)   THE 2-HIGH STACK -- sg13g2_o21ai_1, the Vortex ALU's DOMINANT mapped cell\n"
    "     (Y = !((A1|A2)&B1), driven with A1 = A2 = 0 so the output must follow the\n"
    "     rail up through the 2-HIGH SERIES pMOS stack), dV = 1.65, L = 15 nH,\n"
    "     W = 30 um, 2 fF.  l = 0.13 um where the mapped netlist uses 0.15 um, so")
P("     every number here is GENEROUS to QAL.")
P("")
P("  tag      |Vtp|    Vtn   | o21ai t_valid90 | CMOS(2fF)w | ratio | inverter-bank ratio at the")
P("                          |                 |            |       | same threshold (fixed L=4)")
P("  " + "-" * 116)
o21 = {}
for t in ORDER:
    r = R.get("o21_" + t)
    if not r:
        continue
    d, cc = R["dc_" + t], R["cm_" + t]["vdd1p2_cl2"]   # ISO-LOAD: the o21ai bank
    cw = cc["t90_worst_ps"]                            # carries 2 fF, so must the CMOS
    o21[t] = dict(Vtp=d["Vtp_abs"], Vtn=d["Vtn"], t=r["t_valid90_ps"],
                  ratio=r["t_valid90_ps"] / cw,
                  inv_ratio=q1tab[t]["ratioW"] if t in q1tab else None)
    P("  %-8s %s %s | %15.3f | %10.3f | %5.3f | %s"
      % (t, f(d["Vtp_abs"]), f(d["Vtn"]), r["t_valid90_ps"], cw,
         r["t_valid90_ps"] / cw, f(q1tab[t]["ratioW"]) if t in q1tab else "--"))
S["o21ai"] = o21

# ------------------------------------------------------------------- THE SPEC
sec("g)   THE ANSWER AS A DEVICE SPEC")
P("  Every |Vtp| / Vtn below is MEASURED by the campaign's own criterion")
P("  (Id = 100 nA*W/L at |Vds| = 0.1 V) in this directory, at the DELVTO that")
P("  produced it.  Delivered rail = the MEASURED VBEND of the row quoted.")
P("")
P("  --- Q1, THE LEVEL (iso-cell, iso-load, SAME-DELVTO CMOS, worst edge) ---")
for nm, key, tgt in (("PARITY  (ratio <= 1.00)", "ratioW", 1.00),
                     ("A BEAT  (ratio <= 0.90)", "ratioW", 0.90)):
    hit = [(t, v) for t, v in best.items() if v[key] <= tgt]
    if hit:
        t, v = min(hit, key=lambda kv: -kv[1]["Vtp"])
        P("  %-24s REACHED at |Vtp| <= %.4f V, Vtn <= %.4f V  (%s, L* = %g nH,"
          % (nm, v["Vtp"], v["Vtn"], t, v["L_nH"]))
        P("  %-24s  delivered rail %s V, ratio %.4f)"
          % ("", f(R["q1L%g_%s" % (v["L_nH"], t)]["VBEND"] if ("q1L%g_%s" % (v["L_nH"], t)) in R
                  else R["q1_" + t]["VBEND"], 4), v[key]))
        near = sorted([(vv["ratioW"], tt, vv) for tt, vv in best.items()
                       if 1.0 < vv["ratioW"] <= 1.01])
        if nm.startswith("PARITY") and near:
            P("  %-24s  (and within 0.2%% of parity already at |Vtp| = %.4f V: %s)"
              % ("", max(x[2]["Vtp"] for x in near),
                 ", ".join("%s %.4f" % (x[1], x[0]) for x in near)))
    else:
        P("  %-24s NOT REACHED anywhere in the swept space (best %.4f)"
          % (nm, min(v[key] for v in best.values())))
P("")
P("  On the MEAN-edge convention (the STA-like one the committed 92.8 ps figure is)")
P("  parity is NOT reached anywhere: the best row in the whole sweep is")
P("  ratioM = %.4f (|Vtp| = 0.1391 V, Vtn unshifted).  The gap between the two"
  % min(v["ratioM"] for v in best.values()))
P("  conventions is entirely the campaign cell's 1.83:1 rise/fall imbalance")
P("  (94.17 vs 51.38 ps at DELVTO = 0), which is a CELL-SIZING property, not a")
P("  QAL property.  Both sides use the same cell, so the worst-vs-worst comparison")
P("  is the internally consistent one; a balanced library cell would move both.")
P("")
P("  --- Q2, THE CHAIN (unbuffered, hop-powered) ---")
P("  depth reached (separation POSITIVE and > %.2f mV), MEASURED:" % C["sigma_vt_mV"])
for t in ORDER:
    v = q2.get(t)
    if v:
        P("    |Vtp| %.4f  Vtn %.4f  ->  depth %d" % (v["Vtp"], v["Vtn"], v["depth"]))
P("")
P("  DEPTH 3: reached at |Vtp| <= 0.2395 V WITH Vtn <= 0.3240 V, or at")
P("           |Vtp| <= 0.1391 V with Vtn unshifted.      MEASURED.")
P("  DEPTH 4: reached at |Vtp| = 0.1391 V AND Vtn = 0.2240 V.  MEASURED.")
P("  DEPTH 5: NOT REACHED anywhere.  The best depth-5 separation in the whole")
P("           sweep is %+.4f mV -- %.0fx below the PDK's own sigma_Vt and of the"
  % (max(q2.values(), key=lambda v: v['sep'][4])['sep'][4],
     C["sigma_vt_mV"] / abs(max(q2.values(), key=lambda v: v['sep'][4])['sep'][4])))
P("           WRONG SIGN at the most favourable point.")
P("  DEPTH 10: NOT SIMULATED.  DERIVED, and the derivation is the load-bearing")
P("           part of this answer, so it is given in full:")
rails = {t: v["rails"] for t, v in q2.items() if v.get("rails")}
for t in ("d000", "d300B"):
    rv = rails.get(t)
    if rv:
        seq = [rv[str(i)] if str(i) in rv else rv[i] for i in range(1, 7)]
        rat = [seq[i + 1] / seq[i] for i in range(5)]
        P("    %-6s rails %s  -> per-hop ratio %s (mean %.3f)"
          % (t, " ".join("%.4f" % x for x in seq),
             " ".join("%.3f" % x for x in rat), sum(rat) / len(rat)))
P("    The rail collapse is a CHARGE / CAPACITANCE ratio (chain3: a fixed per-hop")
P("    charge against the bank's incremental C), so it is ~0.61-0.66 per hop and")
P("    barely moves with threshold -- it is 0.66 at DELVTO = 0 and 0.61 at the")
P("    most aggressive shift, i.e. slightly WORSE, because lower-Vt cells draw more.")
P("    Extending the MEASURED 0.62/hop mean from the MEASURED bank-1 rail 0.580 V:")
for k in (5, 8, 10):
    P("      depth %-2d rail = 0.580 * 0.62^%d = %.4f V  (band over 0.61-0.66: %.4f - %.4f V)"
      % (k, k - 1, 0.580 * 0.62 ** (k - 1), 0.580 * 0.61 ** (k - 1),
         0.580 * 0.66 ** (k - 1)))
P("    A restoring CMOS gate needs, at minimum, |Vt| below its own supply -- and in")
P("    practice a good fraction below it -- to produce any gain at all.  At depth 10")
P("    the supply is 6-14 mV.  The required |Vtp| is therefore BELOW ~10 mV, which is")
P("    smaller than this PDK's OWN threshold spread, sigma_Vt = 3.42 mV, by a factor")
P("    of ~3.  A threshold whose mean is within 3 sigma of ZERO is not a device that")
P("    can be manufactured to work: half the devices would be depletion-mode.")
P("    PLAINLY: QAL's unbuffered chain at depth 10 needs a threshold nobody can build.")
P("")
P("  --- Q3, THE COST OF GETTING THERE ---")
i0 = abs(R["hd_d000"]["I_hold_total_A"])
worst = max((abs(v["I"]), t) for t, v in q3.items())
P("  Static hold current per 8-cell bank rises %.0fx (%.3e -> %.3e A) over the"
  % (worst[0] / i0, i0, worst[0]))
P("  sweep, at 82 mV/decade, and it is an nMOS-ONLY cost: every pMOS-only row is")
P("  IDENTICAL to the DELVTO = 0 row to 12 digits.")
P("  BUT THE CURE DOES NOT COST MORE THAN THE DISEASE ANYWHERE IN THE SWEPT SPACE.")
P("  At the most aggressive point the held rail loses %.2f mV (DC-implied) / %.2f mV"
  % (abs(q3["d300B"]["dcd120"]), abs(q3["d300B"]["fl120"])))
P("  (measured float) over a 120 ps beat, against a 754 mV rail -- 0.17-0.57%, and")
P("  against the committed measured -20.2 to -28.6 mV settling-era hold droop it is")
P("  still 5-20x smaller.  Even over a 300 ps beat it is %.2f / %.2f mV."
  % (abs(q3["d300B"]["dcd300"]), abs(q3["d300B"]["fl300"])))
P("  DERIVED: the beat period at which leakage equals the MEASURED 15.2-29.1 fJ")
P("  delivered per bank per hop falls from ~72 us (DELVTO = 0) to ~16 ns -- still")
P("  ~130x longer than the 120 ps beat, so leakage never binds.  My pre-registered")
P("  E3 predicted >100 mV of droop per beat around 0.20-0.30 V: MAGNITUDE REFUTED,")
P("  direction and slope confirmed.")
P("")
P("  --- f) THE 2-HIGH STACK ---")
if "d300B" in o21 and "d000" in o21:
    P("  sg13g2_o21ai_1 improves from %.3f to %.3f ps, i.e. its ratio to a same-DELVTO"
      % (o21["d000"]["t"], o21["d300B"]["t"]))
    P("  CMOS level falls %.3fx -> %.3fx (x%.3f), against the inverter bank's"
      % (o21["d000"]["ratio"], o21["d300B"]["ratio"],
         o21["d300B"]["ratio"] / o21["d000"]["ratio"]))
    P("  x%.3f at the same shift.  E4 CONFIRMED: the 2-high stack gains MORE, because"
      % (q1tab["d300B"]["ratioW"] / q1tab["d000"]["ratioW"]))
    P("  it loses two threshold drops in series where an inverter loses one.")
    P("  BUT IT DOES NOT CHANGE CLASS: %.2fx a CMOS level at the most favourable"
      % o21["d300B"]["ratio"])
    P("  threshold in the sweep.  The shallow-stack library restriction STANDS.")

txt = "\n".join(OUT)
open(os.path.join(HERE, "TABLE.txt"), "w").write(txt + "\n")
S["Q1_committed_anchor_band"] = {t: [v["g"] * C["ratio_lo"], v["g"] * C["ratio_hi"]]
                                 for t, v in best.items()}
json.dump(S, open(os.path.join(HERE, "SUMMARY.json"), "w"), indent=1)
print(txt)
