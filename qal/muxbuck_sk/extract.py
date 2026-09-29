#!/usr/bin/env python3
"""Pull the .mt0 rows and turn them into the numbers the skeptic run needs."""
import os, sys, json, glob

D = "/usr/local/src/stat-sim/qal/muxbuck_sk"
CT = 359.79e-15


def mt0(name):
    p = os.path.join(D, name + ".cir.mt0")
    if not os.path.exists(p):
        return None
    out = {}
    for line in open(p):
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                out[k.strip()] = float(v.strip())
            except ValueError:
                pass
    return out


def fC(x):
    return x * 1e15


print("=" * 78)
print("K1 INSTRUMENT CHECK (my own from-scratch vae_cache_sk)")
print("=" * 78)
me = mt0("sk_instr")
comm = mt0("/usr/local/src/stat-sim/qal/lsweep/h_L15_W30_dv120")
if me is None:
    print("  sk_instr not finished")
else:
    cp = "/usr/local/src/stat-sim/qal/lsweep/h_L15_W30_dv120.cir.mt0"
    comm = {}
    for line in open(cp):
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                comm[k.strip()] = float(v.strip())
            except ValueError:
                pass
    nid, worst, wk = 0, 0.0, None
    for k in sorted(set(me) & set(comm)):
        a, b = me[k], comm[k]
        if a == b:
            nid += 1
            r = 0.0
        else:
            r = abs(a - b) / max(abs(b), 1e-30)
        if r > worst:
            worst, wk = r, k
    print(f"  keys compared {len(set(me)&set(comm))}, bit-identical {nid}")
    print(f"  worst rel {worst:.3e} on {wk}")
    for k in ("VBEND", "VBPK", "IPK", "IZ"):
        if k in me:
            r = 0.0 if me[k] == comm[k] else abs(me[k] - comm[k]) / abs(comm[k])
            print(f"  {k:6s} mine {me[k]:.7g}  committed {comm[k]:.7g}  rel {r:.2e}")
    print(f"  GATE K1 (VBEND rel <= 1e-6): "
          f"{'PASS' if abs(me.get('VBEND',0)-comm.get('VBEND',1))/abs(comm.get('VBEND',1)) <= 1e-6 else 'FAIL'}")

print()
print("=" * 78)
print("RECURSION AUDIT -- charge into the SELECTED tank, one buck pulse")
print("=" * 78)
rows = [("sk_mx_c1", "N=1  committed schedule (mux closes at 41.978 ps)"),
        ("sk_mx_c16", "N=16 committed schedule"),
        ("sk_mx_e1", "N=1  EARLY close (mux closed from t=0)"),
        ("sk_mx_e16", "N=16 EARLY close"),
        ("sk_mx_w16h", "N=16 committed sched, mux TG 2.5u/5u  (HALF width)"),
        ("sk_mx_w16d", "N=16 committed sched, mux TG 10u/20u (DOUBLE width)")]
res = {}
print(f"{'deck':<12} {'q_tank fC':>11} {'q_sup fC':>10} {'Qdel/Qsup':>10} "
      f"{'nbx pk':>8} {'nbx min':>8} {'nbx@mux-on':>11}  desc")
for nm, desc in rows:
    m = mt0(nm)
    if m is None:
        print(f"{nm:<12} {'(pending)':>11}")
        continue
    qt = fC(CT * (m["VT0E"] - 0.66))
    qs = fC(m["QSUP_E"] - m["QSUP_Z"])
    qd = fC(m["QDEL_E"] - m["QDEL_Z"])
    res[nm] = dict(q_tank=qt, q_sup=qs, q_del=qd, nbxpk=m["VNBXPK"],
                   nbxmn=m["VNBXMN"], nbxon=m.get("VNBX_ON0"), ilpk=m["ILPK"] * 1e6)
    print(f"{nm:<12} {qt:11.3f} {qs:10.3f} {qd/qs:10.4f} "
          f"{m['VNBXPK']:8.4f} {m['VNBXMN']:8.4f} {m.get('VNBX_ON0',float('nan')):11.4f}  {desc}")

if "sk_mx_c1" in res and "sk_mx_c16" in res:
    gc = res["sk_mx_c16"]["q_tank"] - res["sk_mx_c1"]["q_tank"]
    print(f"\n  COMMITTED schedule: N16 - N1 gap = {gc:+.3f} fC  "
          f"-> {gc/15:+.4f} fC per idle tap")
if "sk_mx_e1" in res and "sk_mx_e16" in res:
    ge = res["sk_mx_e16"]["q_tank"] - res["sk_mx_e1"]["q_tank"]
    print(f"  EARLY-CLOSE schedule: N16 - N1 gap = {ge:+.3f} fC  "
          f"-> {ge/15:+.4f} fC per idle tap")
    if "sk_mx_c1" in res:
        print(f"  S1 test: gap shrinks by {abs(gc/ge):.2f}x   "
              f"(pre-stated threshold: > 3x confirms H1)")

if "sk_mx_w16h" in res and "sk_mx_w16d" in res and "sk_mx_c16" in res:
    print("\n  S2 WIDTH TEST at N=16 (committed schedule):")
    base = res["sk_mx_c1"]["q_tank"] if "sk_mx_c1" in res else 0.0
    for nm, w in (("sk_mx_w16h", 0.5), ("sk_mx_c16", 1.0), ("sk_mx_w16d", 2.0)):
        d = res[nm]["q_tank"] - base
        print(f"    width x{w:<4} q_tank {res[nm]['q_tank']:9.3f} fC   "
              f"deficit vs N=1 base {d:+9.3f} fC   deficit/width {d/w:+9.3f}")

print()
print("=" * 78)
print("TWO-PULSE TEST -- is the per-pulse cost a transient or steady state?")
print("=" * 78)
for nm, desc in (("sk_mx_p2_c16", "N=16 committed sched, 2 back-to-back pulses"),
                 ("sk_mx_p2_e16", "N=16 EARLY close, 2 back-to-back pulses")):
    m = mt0(nm)
    if m is None:
        print(f"  {nm}: pending")
        continue
    v0, v1 = m["VT0_P0"], m["VT0_P1"]
    q1 = fC(CT * (v0 - 0.66))
    q2 = fC(CT * (v1 - v0))
    print(f"  {desc}")
    print(f"    pulse 1 -> {q1:+9.3f} fC     pulse 2 -> {q2:+9.3f} fC     "
          f"ratio p2/p1 {q2/q1 if q1 else float('nan'):+7.3f}")
    print(f"    nbx at mux-on: pulse1 {m.get('VNBX_ON0',float('nan')):.4f} V   "
          f"pulse2 {m.get('VNBX_ON1',float('nan')):.4f} V")

print()
print("=" * 78)
print("TANK DROOP -- my own measurement")
print("=" * 78)
for nm, desc in (("sk_droop8", "8-gate bank, committed R = 10 ohm"),
                 ("sk_droop8_r32", "8-gate bank, PDK-estimator R = 31.76 ohm")):
    m = mt0(nm)
    if m is None:
        print(f"  {nm}: pending")
        continue
    Qbeat = fC(CT * (m["VT_A"] - m["VT_D"]))
    Qrise = fC(CT * (m["VT_A"] - m["VT_B"]))
    Qlt_rise = fC(m["QLT_B"] - m["QLT_A"])
    print(f"  {desc}")
    print(f"    tank  pre-rise {m['VT_A']:.7f} -> post-rise {m['VT_B']:.7f} "
          f"-> pre-return {m['VT_C']:.7f} -> post-return {m['VT_D']:.7f} V")
    print(f"    Q_beat (full cycle)      = {Qbeat:9.3f} fC")
    print(f"    Q_rise (rise sub-window) = {Qrise:9.3f} fC   "
          f"int I(L)dt over same = {Qlt_rise:9.3f} fC   "
          f"disagreement {abs(Qrise-Qlt_rise)/abs(Qrise)*100:.2f}%")
    print(f"    delivered rail AT ZCS {m['VR_ZCS']:.6f} V   "
          f"after 2 ps gate ramp {m['VR_FT']:.6f} V   "
          f"feedthrough {(m['VR_FT']-m['VR_ZCS'])*1000:+.1f} mV")
    print(f"    rail peak during rise {m['VR_PK']:.6f} V")
    print(f"    held-rail droop: {m['VR_FT']:.6f} -> {m['VR_H300']:.6f} V "
          f"= {(m['VR_H300']-m['VR_FT'])*1000:+.1f} mV over 300 ps")
    print(f"    ZCS residual: rise open {m['IZ_R']*1e6:+.2f} uA   "
          f"return open {m['IZ_Q']*1e6:+.2f} uA   "
          f"(stranded 1/2 L I^2: {0.5*15e-9*m['IZ_R']**2*1e15:.4f} / "
          f"{0.5*15e-9*m['IZ_Q']**2*1e15:.4f} fJ)")
    # A2 coupling check: does the return strand rail at 2*V_tank - V_rail_before?
    pred = 2 * m["VT_C"] - m["VR_END"]
    print(f"    A2 COUPLING CHECK: rail before return {m['VR_END']:.6f}, "
          f"tank at return {m['VT_C']:.6f}")
    print(f"      2*V_tank - V_rail_before = {pred:.6f} V  (predicted stranded rail)")

json.dump(res, open(os.path.join(D, "SK_RAW.json"), "w"), indent=1)
