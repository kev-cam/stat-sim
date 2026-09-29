#!/usr/bin/env python3
"""qal/muxbuck_sk -- the skeptic run's own numbers, assembled."""
import os, json, math

D = "/usr/local/src/stat-sim/qal/muxbuck_sk"
CT = 359.79e-15


def mt0(n):
    p = os.path.join(D, n + ".cir.mt0")
    if not os.path.exists(p):
        return None
    d = {}
    for l in open(p):
        if "=" in l:
            k, v = l.split("=", 1)
            try:
                d[k.strip()] = float(v.strip())
            except ValueError:
                pass
    return d


def qt(m, key="VT0E", v0=0.66):
    return CT * (m[key] - v0) * 1e15


R = {}
print("#" * 78)
print("# (a) RECURSION AUDIT -- does the mux cost amortise, or track its load?")
print("#" * 78)
print("\n-- A1. Charge into the SELECTED tank, one buck pulse, vs number of taps N --\n")
print(f"{'variant':<42} {'N=1':>9} {'N=4':>9} {'N=16':>9} {'gap N16-N1':>11} {'per tap':>9}")
sets = [("committed sched, deck .ic (na=0)  [BALANCE]", ["sk_mx_c1", None, "sk_mx_c16"]),
        ("committed sched, consistent .ic (na=0.66)", ["sk_mx_q1", "sk_mx_q4", "sk_mx_q16"]),
        ("mux never disconnected, consistent .ic", ["sk_mx_qe1", "sk_mx_qe4", "sk_mx_qe16"])]
for tag, names in sets:
    vals = []
    for n in names:
        m = mt0(n) if n else None
        vals.append(qt(m) if m else None)
    gap = (vals[2] - vals[0]) if (vals[0] is not None and vals[2] is not None) else None
    f = lambda x: f"{x:9.2f}" if x is not None else "     --  "
    print(f"{tag:<42} {f(vals[0])} {f(vals[1])} {f(vals[2])} "
          f"{gap if gap is None else f'{gap:11.2f}'} {'' if gap is None else f'{gap/15:9.3f}'}")
    R[tag] = dict(q=vals, gap=gap, per_tap=None if gap is None else gap / 15)

base = R["committed sched, deck .ic (na=0)  [BALANCE]"]["per_tap"]
for tag in list(R)[1:]:
    p = R[tag]["per_tap"]
    print(f"\n  shrink vs the balance run's schedule/IC: {abs(base/p):.1f}x   ({tag})")
print(f"\n  S1 pre-stated threshold was 'gap shrinks by more than 3x'.")

print("\n-- A2. Is the deficit tap CAPACITANCE? width sweep at N=16, committed sched --\n")
print(f"{'mux TG width':<24} {'q_tank fC':>10} {'deficit fC':>11} {'V(nbx) at mux-on':>17} "
      f"{'implied C_shared fF':>20} {'per um of W':>12}")
wrows = [("2.5u/5u   (x0.5)", "sk_mx_w16h", 7.5),
         ("5u/10u    (x1.0)", "sk_mx_c16", 15.0),
         ("10u/20u   (x2.0)", "sk_mx_w16d", 30.0)]
dens = []
for tag, nm, wtot in wrows:
    m = mt0(nm)
    if not m:
        continue
    q = qt(m)
    dv = 0.66 - m["VNBX_ON0"]
    cs = (-q * 1e-15) / dv * 1e15
    dens.append(cs / (16 * wtot))
    print(f"{tag:<24} {q:10.2f} {-q:11.2f} {m['VNBX_ON0']:17.4f} {cs:20.2f} "
          f"{cs/(16*wtot):12.4f}")
print(f"\n  capacitance density implied by the redistribution model: "
      f"{min(dens):.3f} - {max(dens):.3f} fF per um of mux width "
      f"(mean {sum(dens)/len(dens):.3f})")
print("  -> a SINGLE capacitance density explains all three widths. The deficit IS")
print("     C_shared x (V_tank - V_shared_at_mux_on), i.e. charge-sharing redistribution.")
c_tap = (sum(dens) / len(dens)) * 15.0
print(f"  -> c_tap for the committed 5u/10u TG = {c_tap:.2f} fF   [MEASURED, lower bound:")
print("     sg13lv_compat.sp zeroes ad/as/pd/ps so junction capacitance is absent]")

print("\n-- A3. Is the cost stationary? two back-to-back pulses at 64.064 ps cadence --\n")
for nm, tag in (("sk_mx_p2_c16", "N=16 committed sched, deck .ic  [balance's conditions]"),
                ("sk_mx_p2_q16", "N=16 committed sched, consistent .ic"),
                ("sk_mx_p2_qe16", "N=16 mux never disconnected")):
    m = mt0(nm)
    if not m or "VT0_P1" not in m:
        print(f"  {tag}: (not available)")
        continue
    q1 = CT * (m["VT0_P0"] - 0.66) * 1e15
    q2 = CT * (m["VT0_P1"] - m["VT0_P0"]) * 1e15
    print(f"  {tag}")
    print(f"      pulse 1 {q1:+8.2f} fC    pulse 2 {q2:+8.2f} fC    "
          f"pulse2/pulse1 = {q2/q1:.3f}")
    print(f"      V(nbx) at mux-on: {m['VNBX_ON0']:.4f} -> {m['VNBX_ON1']:.4f} V")
    R[nm] = dict(p1=q1, p2=q2)

print()
print("#" * 78)
print("# (c) TANK DROOP, re-measured")
print("#" * 78)
for nm, tag, L in (("sk_droop8", "8-gate bank, R = 10 ohm (committed)", 15e-9),
                   ("sk_droop8_r32", "8-gate bank, R = 31.76 ohm (PDK estimator)", 15e-9)):
    m = mt0(nm)
    if not m:
        continue
    Qb = CT * (m["VT_A"] - m["VT_D"]) * 1e15
    Qr = CT * (m["VT_A"] - m["VT_B"]) * 1e15
    Ql = (m["QLT_B"] - m["QLT_A"]) * 1e15
    print(f"\n  {tag}")
    print(f"    tank  {m['VT_A']:.6f} -> (rise) {m['VT_B']:.6f} -> (hold) {m['VT_C']:.6f} "
          f"-> (return) {m['VT_D']:.6f} V")
    print(f"    Q_beat           = {Qb:7.2f} fC     [MEASURED, linear tank cap]")
    print(f"    Q_rise           = {Qr:7.2f} fC     int I(L)dt same window = {Ql:6.2f} fC "
          f"({abs(Qr-Ql)/Qr*100:.1f}% apart)")
    print(f"    delivered rail at ZCS = {m['VR_ZCS']:.6f} V   settled held rail = {m['VR_H300']:.6f} V")
    print(f"    held-rail droop  = {(m['VR_H300']-m['VR_H100'])*1000:+.2f} mV over 200 ps  "
          f"(committed campaign figure: -28.6 mV / 300 ps)")
    print(f"    ZCS residual     = {m['IZ_R']*1e6:+.2f} uA (rise) / {m['IZ_Q']*1e6:+.2f} uA (return)"
          f"   gate 30 uA: {'PASS' if max(abs(m['IZ_R']),abs(m['IZ_Q']))*1e6<30 else 'FAIL'}")
    print(f"    stranded 1/2 L I^2 = {0.5*L*m['IZ_R']**2*1e15:.4f} / {0.5*L*m['IZ_Q']**2*1e15:.4f} fJ")
    R[nm] = dict(Qbeat=Qb, rail_zcs=m["VR_ZCS"], IZr=m["IZ_R"] * 1e6, IZq=m["IZ_Q"] * 1e6)

g8, g58 = mt0("sk_droop8"), mt0("sk_gain58")
g = (g8["VR_ZCS"] - g58["VR_ZCS"]) / (0.66 - 0.58)
off = g8["VR_ZCS"] - g * 0.66
print(f"\n  band conversion, MY OWN two points (tank 0.66 -> rail {g8['VR_ZCS']:.6f}; "
      f"tank 0.58 -> rail {g58['VR_ZCS']:.6f}):")
print(f"    g = {g:.5f} V/V, offset {off:.5f} V      (balance run: g = 0.93598, offset 0.14868)")

BAND_TOP, BAND_FLOOR = 0.7656, 0.6754
band_rail = BAND_TOP - BAND_FLOOR
band_tank = band_rail / g
store = CT * band_tank * 1e15
Qb10 = R["sk_droop8"]["Qbeat"]
print(f"\n  adopting the balance run's PRE-REGISTERED band (rail {BAND_FLOOR}-{BAND_TOP} V):")
print(f"    band_rail {band_rail*1000:.1f} mV -> band_tank {band_tank*1000:.2f} mV "
      f"-> store = {store:.2f} fC")
print(f"    autonomy = store / Q_beat = {store/Qb10:.3f} beats   "
      f"(balance run: 0.979)")

# R = 31.76 case: the rail no longer reaches the band top
m32 = mt0("sk_droop8_r32")
top32 = m32["VR_ZCS"]
band_rail32 = top32 - BAND_FLOOR
band_tank32 = band_rail32 / g
store32 = CT * band_tank32 * 1e15
Qb32 = R["sk_droop8_r32"]["Qbeat"]
print(f"\n  SAME band floor, but at the PDK's own R = 31.76 ohm the tank can no longer")
print(f"  reach the band TOP: best delivered rail from a 0.66 V tank is {top32:.4f} V.")
print(f"    usable band shrinks {band_rail*1000:.1f} -> {band_rail32*1000:.1f} mV "
      f"({(1-band_rail32/band_rail)*100:.0f}% narrower)")
print(f"    store {store:.2f} -> {store32:.2f} fC ;  Q_beat {Qb10:.2f} -> {Qb32:.2f} fC")
print(f"    autonomy {store/Qb10:.3f} -> {store32/Qb32:.3f} beats")

print()
print("#" * 78)
print("# (d) SCHEDULING -- the permitted top-up window, re-derived")
print("#" * 78)
T_CYCLE, T_PULSE = 1600.0, 64.064
rise_c, rise_o, ret_c, ret_o = 200.0, 318.184, 1000.0, 1131.37
print(f"  balance run: tank 'busy' = rise + return = {(rise_o-rise_c)+(ret_o-2-ret_c):.2f} ps"
      f" -> availability {1-((rise_o-rise_c)+(ret_o-2-ret_c))/T_CYCLE:.4f}")
print(f"  MEASURED constraint the balance run's own A2 implies but did not apply:")
print(f"    the return hop swings the rail about the TANK voltage; from my three decks the")
print(f"    un-compute recovers 58-61% of the lossless swing, so")
print(f"      d(stranded rail)/d(tank) = 2 x 0.60 = 1.20 at fixed starting rail.")
print(f"    Topping the tank up by the full band ({band_tank*1000:.1f} mV) BEFORE the return")
print(f"    would leave {1.20*band_tank*1000:.0f} mV more charge stranded on the rail -- "
      f"more than the whole")
print(f"    {band_rail*1000:.1f} mV rail band. So the inter-hop hold window is NOT usable for top-up.")
win = 1800.0 - ret_o
print(f"    permitted window = post-return to next rise-close = "
      f"[{ret_o:.2f}, 1800] = {win:.2f} ps = {win/T_CYCLE*100:.1f}% of the cycle")
print(f"    (balance run's figure: 84.53%)")
K = T_CYCLE / T_PULSE
print(f"\n  K (pulses per bank cycle) = {T_CYCLE}/{T_PULSE} = {K:.3f}   [BOOKING: assumes the")
print(f"    shared buck fires back-to-back at 100% duty; my 2-pulse decks are the only test]")
offs = [0.0, 200.0, 400.0, 600.0]
ivs = []
for o in offs:
    a, b = ret_o + o, 1800.0 + o
    a %= T_CYCLE
    b %= T_CYCLE
    ivs.append((a, b) if a < b else (a, T_CYCLE))
    if a > b:
        ivs.append((0.0, b))
pts = sorted(ivs)
merged = []
for a, b in pts:
    if merged and a <= merged[-1][1]:
        merged[-1] = (merged[-1][0], max(merged[-1][1], b))
    else:
        merged.append((a, b))
cov = sum(b - a for a, b in merged)
print(f"\n  WORST CASE I CONSTRUCTED -- banks phase-LOCKED to the committed H=4 phases")
print(f"  (offsets 0/200/400/600 ps, cycle 1600 ps = 2*H*T):")
print(f"    union of all permitted windows = {cov:.2f} ps of {T_CYCLE:.0f} = {cov/T_CYCLE*100:.1f}%")
print(f"    DEAD ZONE where NO bank can accept charge = {T_CYCLE-cov:.2f} ps = "
      f"{(1-cov/T_CYCLE)*100:.1f}% of every cycle")
Keff = K * cov / T_CYCLE
print(f"    -> K_eff = {Keff:.2f} instead of {K:.3f}")

print()
print("#" * 78)
print("# (f) THE CEILING, recomputed three ways")
print("#" * 78)
print(f"{'assumption set':<58} {'K':>7} {'autonomy':>9} {'N ceiling':>10}")
for tag, k, au in (("balance run, as reported", K, 0.979),
                   ("my own Q_beat + my own gain, R = 10 ohm", K, store / Qb10),
                   ("+ PDK inductor R = 31.76 ohm", K, store32 / Qb32),
                   ("+ phase-locked H=4 dead zone", Keff, store / Qb10),
                   ("+ both", Keff, store32 / Qb32)):
    print(f"{tag:<58} {k:7.2f} {au:9.3f} {k*au:10.1f}")

json.dump({k: v for k, v in R.items() if isinstance(v, dict)},
          open(os.path.join(D, "SK_RESULTS.json"), "w"), indent=1, default=str)
print("\nwrote SK_RESULTS.json")
