#!/usr/bin/env python3
"""INDEPENDENT re-fit of the Track B 1/T law, written for the audit.
Does not import tsweep/analyse.py.  Reads only the per-row JSON produced by the
simulator and does its own least squares.

Tests, in order:
 1. E_xfer = E_R + E_switchblock  vs T   -- the claimed 1/T term
 2. the MIS-BINNING test: is any part of E_xfer actually per-op?  Fit
        E_xfer(T) = A/T + B
    (a T-dependent term PLUS a constant floor) and report B.  A genuine purely
    resistive term has B ~ 0; a mis-binned per-op term shows up as B > 0.
 3. the charge correction: E_xfer/Q^2 vs T  (the physics says E = pi^2 R Q^2/8T)
 4. the implied series R, and whether it is constant
 5. every OTHER energy term's exponent, so the reader can see what actually falls
 6. E_vhi -- the switch pMOS BULK supply, metered in the row files but summed
    into NO reported QAL total.  Its exponent and its size.
"""
import glob, json, math, os, sys

ROWD = sys.argv[1] if len(sys.argv) > 1 else "/usr/local/src/stat-sim/qal/tsweep/rowd"


def loglog_fit(xs, ys):
    n = len(xs)
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    mx, my = sum(lx) / n, sum(ly) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    sxx = sum((a - mx) ** 2 for a in lx)
    m = sxy / sxx
    c = my - m * mx
    ss_t = sum((b - my) ** 2 for b in ly)
    ss_r = sum((b - (m * a + c)) ** 2 for a, b in zip(lx, ly))
    return m, math.exp(c), (1 - ss_r / ss_t if ss_t else 1.0)


def lin_fit(xs, ys):
    """ys = A*xs + B by ordinary least squares (xs will be 1/T)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    A = sxy / sxx
    B = my - A * mx
    ss_t = sum((b - my) ** 2 for b in ys)
    ss_r = sum((b - (A * a + B)) ** 2 for a, b in zip(xs, ys))
    return A, B, (1 - ss_r / ss_t if ss_t else 1.0)


rows = []
for f in glob.glob(os.path.join(ROWD, "T*.json")):
    j = json.load(open(f))
    if "t_hop_ps" not in j:
        continue
    j["E_xfer"] = j["E_R_toC_fJ"] + j["E_switchblock_toC_fJ"]
    j["T"] = j["t_hop_ps"]
    rows.append(j)
rows.sort(key=lambda r: r["T"])
fn = [r for r in rows if r["FUNCTIONAL"] == "YES"]

print("=" * 112)
print("INDEPENDENT RE-FIT   (%d rows, %d functional)   source: %s" % (len(rows), len(fn), ROWD))
print("=" * 112)
print("%-8s %9s %9s %9s %10s %10s %9s %9s %9s %9s"
      % ("tag", "T_ps", "E_xfer", "E_xfer*T", "Q_C_fC", "R_impl_ohm",
         "E_hop", "E_gate", "E_vhi", "cells"))
for r in fn:
    Q = r["Q_through_L_C_fC"] * 1e-15
    ET = r["E_xfer"] * r["T"]
    R = (ET * 1e-15 * 1e-12) * 8.0 / (math.pi ** 2 * Q * Q)
    r["R_impl"] = R
    print("%-8s %9.2f %9.4f %9.2f %10.4f %10.3f %9.4f %9.4f %9.4f %9.4f"
          % (r["tag"], r["T"], r["E_xfer"], ET, r["Q_through_L_C_fC"], R,
             r["E_hop_open_fJ"], r["E_gate_drive_fJ"], r["E_vhi_fJ"],
             r["cells_burn_fJ"]))

print()
print("--- 1. E_xfer = k*T^-p  (the claimed adiabatic law) ---")
for name, sub in (("FUNCTIONAL band", fn), ("ALL rows", rows),
                  ("T >= 265 ps", [r for r in rows if r["T"] >= 265]),
                  ("T <= 86 ps (broken)", [r for r in rows if r["T"] <= 86])):
    if len(sub) < 3:
        continue
    p, k, r2 = loglog_fit([r["T"] for r in sub], [r["E_xfer"] for r in sub])
    dec = math.log10(sub[-1]["T"] / sub[0]["T"])
    print("  %-22s p = %+.4f   R^2 %.6f   (%.2f decades, n=%d)" % (name, p, r2, dec, len(sub)))

print()
print("--- 2. MIS-BINNING TEST:  E_xfer(T) = A/T + B   (B = a per-op floor hiding inside E_xfer) ---")
A, B, r2 = lin_fit([1.0 / r["T"] for r in fn], [r["E_xfer"] for r in fn])
print("  functional band:  A = %.4f fJ*ps    B = %+.6f fJ    R^2 %.6f" % (A, B, r2))
print("  B as a fraction of E_xfer at the SLOWEST functional T (%.1f ps, E=%.4f): %+.2f%%"
      % (fn[-1]["T"], fn[-1]["E_xfer"], 100.0 * B / fn[-1]["E_xfer"]))
print("  -> a genuinely resistive term has B ~ 0.  A large positive B would mean a")
print("     per-op charge has been mis-binned into the T-dependent bucket.")

print()
print("--- 3. CHARGE CORRECTION:  E_xfer / Q^2  vs T ---")
p, k, r2 = loglog_fit([r["T"] for r in fn],
                      [r["E_xfer"] / (r["Q_through_L_C_fC"] ** 2) for r in fn])
print("  E_xfer/Q^2 :  p = %+.4f   R^2 %.6f" % (p, r2))
qa, qb = fn[0]["Q_through_L_C_fC"], fn[-1]["Q_through_L_C_fC"]
print("  Q grows %.4f -> %.4f fC (+%.2f%%) across the band; Q^2 therefore +%.2f%%"
      % (qa, qb, 100 * (qb / qa - 1), 100 * ((qb / qa) ** 2 - 1)))

print()
print("--- 4. IMPLIED SERIES R (E = pi^2 R Q^2 / 8T) ---")
Rs = [r["R_impl"] for r in fn]
print("  R = %.3f .. %.3f ohm, mean %.3f, spread %.2f%% over a %.1fx range in T"
      % (min(Rs), max(Rs), sum(Rs) / len(Rs),
         100 * (max(Rs) - min(Rs)) / (sum(Rs) / len(Rs)), fn[-1]["T"] / fn[0]["T"]))

print()
print("--- 5. EVERY TERM'S EXPONENT over the functional band ---")
for key, lbl in (("E_xfer", "E_xfer  resistive transfer"),
                 ("cells_burn_fJ", "cells_burn  the cells' own settle"),
                 ("E_Bresid_toC_fJ", "E_Bresid  destination side"),
                 ("E_gate_drive_fJ", "E_gate  switch gate drive (per-op)"),
                 ("E_vhi_fJ", "E_vhi   switch pMOS BULK supply *UNCOUNTED*"),
                 ("E_hop_open_fJ", "E_hop   TOTAL out of bank A")):
    ys = [r[key] for r in fn]
    if min(ys) <= 0:
        continue
    p, k, r2 = loglog_fit([r["T"] for r in fn], ys)
    print("  %-42s p = %+.4f  R^2 %.4f   falls %.3fx  (%.4f -> %.4f fJ)"
          % (lbl, p, r2, ys[0] / ys[-1], ys[0], ys[-1]))

print()
print("--- 6. THE UNCOUNTED TERM:  E_vhi  ---")
print("  E_vhi is metered in every row (integ 'ehi' = -VGH*I(VHI), VGH = 1.5 V) and is")
print("  summed into NO reported QAL total.  VHI is the BULK tie of the transfer")
print("  switch pMOS (XSWP sw gtp bkb vhi).  In the CMOS comparator deck the pMOS bulk")
print("  sits on `vdd`, whose current IS metered by the evdd integrator -- so the same")
print("  physical term is COUNTED on the CMOS side and OMITTED on the QAL side.")
print()
print("%-8s %9s %9s %9s %11s %11s %11s"
      % ("tag", "T_ps", "E_hop", "E_vhi", "E_QAL(i)", "E_QAL(i)+vhi", "understate%"))
for r in fn:
    q = r["E_hop_open_fJ"] + r["E_gate_drive_fJ"]
    qv = q + r["E_vhi_fJ"]
    print("%-8s %9.2f %9.4f %9.4f %11.4f %11.4f %11.2f"
          % (r["tag"], r["T"], r["E_hop_open_fJ"], r["E_vhi_fJ"], q, qv,
             100 * (qv / q - 1)))

E_CMOS_120 = 40.9815
E_CMOS_100 = 30.1626
LEDGER = 23.213
print()
print("--- 7. WHAT IT DOES TO THE HEADLINE RATIOS ---")
print("%-8s %9s | %10s %10s | %10s %10s | %10s %10s"
      % ("tag", "T_ps", "(i) as-rep", "(i) +vhi", "(iii)as-rep", "(iii)+vhi",
         "(iii)isoV", "(iii)isoV+"))
for r in (fn[0], fn[len(fn) // 2], fn[-1]):
    h, v = r["E_hop_open_fJ"], r["E_vhi_fJ"]
    g = r["E_gate_drive_fJ"]
    i1, i2 = h + g, h + g + v
    t1, t2 = h + LEDGER, h + LEDGER + v
    print("%-8s %9.2f | %10.4f %10.4f | %10.4f %10.4f | %10.4f %10.4f"
          % (r["tag"], r["T"], E_CMOS_120 / i1, E_CMOS_120 / i2,
             E_CMOS_120 / t1, E_CMOS_120 / t2,
             E_CMOS_100 / t1, E_CMOS_100 / t2))
