#!/usr/bin/env python3
"""SKEPTIC surfaces + the (c) t_settle audit.  Every t_settle here is the floor
MEASURED (my own deck) at that row's OWN delivered VBEND -- no interpolation.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS = 92.8
G_C2, G_C3 = 0.1478, 0.60

rows = json.load(open(os.path.join(HERE, "rows.json")))
FL = {}
for f in ("f1.json", "f4.json", "f5.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        for v in json.load(open(p)).values():
            if v["kind"] == "inv" and v["edge_ps"] == 2.0:
                FL[round(v["vdd"], 7)] = v["t90_measure"]

T = []
for t, r in rows.items():
    if "error" in r:
        continue
    vb = round(r["VBEND"], 7)
    ts = FL.get(vb)
    if ts is None:
        continue
    T.append(dict(tag=t, dv=round(r["dv"], 2), L=r["L_nH"], W=r["total_um"],
                  t_hop=r["t_hop_ps"], VBEND=r["VBEND"], VBPK=r["VBPK"],
                  VA_C=r["VA_open"], VA_Z=r["VA_open_printed"], t_settle=ts,
                  SUM=r["t_hop_ps"] + ts, MAX=max(r["t_hop_ps"], ts),
                  rail90=r["t_rail90_ps"], set90=r["t_settle90_ps"],
                  val90=r["t_valid90_ps"], s_end=r["settling_end_min_pct"],
                  E_hop=r["E_hop_open_fJ"],
                  FUNC=(r["VA_open"] <= G_C2 and r["VBEND"] >= G_C3
                        and r["C4_instrument"] == "PASS"
                        and r["C1_settle_end"] == "PASS"),
                  FUNC_Z=(r["VA_open_printed"] <= G_C2 and r["VBEND"] >= G_C3)))

print("=" * 150)
print("SKEPTIC GRID.  t_settle = MY OWN floor deck MEASURED at that row's exact "
      "delivered VBEND.  VA@C = the published gate quantity (V(bka) 7 ps AFTER the")
print("switch opens); VA@Z = V(bka) AT the ZCS instant, which is what the campaign's "
      "OTHER harness (skept/sk.py) calls VA_open.  Both are MEASURED.")
print("=" * 150)
print("%-18s %5s %5s %4s | %8s %8s %8s | %8s %8s | %8s %8s | %7s %7s %7s | %s"
      % ("tag", "dV", "L nH", "W", "t_hop", "VBEND", "t_set", "VA@C", "VA@Z",
         "SUM", "MAX", "rail90", "set90", "val90", "gate"))
print("-" * 150)
for r in sorted(T, key=lambda r: (-r["dv"], -r["L"], r["W"])):
    print("%-18s %5.2f %5g %4g | %8.3f %8.5f %8.2f | %+8.5f %+8.5f | %8.2f %8.2f | "
          "%7.2f %7.2f %7.2f | %s"
          % (r["tag"], r["dv"], r["L"], r["W"], r["t_hop"], r["VBEND"], r["t_settle"],
             r["VA_C"], r["VA_Z"], r["SUM"], r["MAX"], r["rail90"], r["set90"],
             r["val90"],
             "FUNCTIONAL" if r["FUNC"] else ("C2fail(margin %+.4f)" % (G_C2 - r["VA_C"]))))

print()
print("=" * 150)
print("(c) WHAT IS t_settle?  Three candidate quantities, all MEASURED, all different.")
print("=" * 150)
print("  t_settle(floor)  MEASURED, but in a DIFFERENT CIRCUIT: ideal supply stepped")
print("                   into one inverter + 2 fF, no bank, no switch, 2 ps edge.")
print("  set90 / val90    MEASURED in the bank, but timed from the SWITCH CLOSE, so")
print("                   they are LEVEL times that already CONTAIN t_hop.")
print("  set90 - rail90   the only genuine POST-ARRIVAL settle interval available in")
print("                   the bank deck.  This is what the floor claims to be.")
print()
print("%-18s %8s %8s %8s | %10s %10s | %9s %9s %9s"
      % ("tag", "t_hop", "rail90", "set90", "set90-rail", "floor", "floor/post",
         "SUM", "val90"))
for r in sorted([x for x in T if x["FUNC"]], key=lambda r: (-r["dv"], -r["L"], r["W"])):
    post = r["set90"] - r["rail90"]
    print("%-18s %8.3f %8.2f %8.2f | %10.2f %10.2f | %9.3f %9.2f %9.2f"
          % (r["tag"], r["t_hop"], r["rail90"], r["set90"], post, r["t_settle"],
             r["t_settle"] / post, r["SUM"], r["val90"]))

print()
print("  OVERLAP: SUM(model) vs val90(the SAME event chain, MEASURED end to end)")
for r in sorted([x for x in T if x["FUNC"] and x["dv"] == 1.65],
                key=lambda r: r["SUM"])[:6]:
    print("   %-18s SUM %7.2f  val90 %7.2f  -> the model OVER-states the measured "
          "level time by %+.1f%% (overlap %.1f ps)"
          % (r["tag"], r["SUM"], r["val90"], 100 * (r["SUM"] / r["val90"] - 1),
             r["SUM"] - r["val90"]))

print()
print("=" * 150)
print("OPTIMA, three gate conventions")
print("=" * 150)


def best(f, key):
    g = [r for r in T if f(r)]
    return min(g, key=lambda r: r[key]) if g else None


for lab, f in (("C2 at +7 ps  (AS PUBLISHED)", lambda r: r["FUNC"]),
               ("C2 at the ZCS instant", lambda r: r["FUNC_Z"])):
    for key in ("SUM", "MAX", "val90"):
        b = best(f, key)
        n = len([r for r in T if f(r)])
        print("  %-30s %-6s optimum: dV=%.2f L=%-4g W=%-4g -> %7.2f ps = %.4fx CMOS "
              "(%d/%d functional)"
              % (lab, key, b["dv"], b["L"], b["W"], b[key], b[key] / CMOS, n, len(T)))
    print()

json.dump(dict(grid=T, floor=FL), open(os.path.join(HERE, "s2surfaces.json"), "w"),
          indent=1)
print("wrote s2surfaces.json (%d rows)" % len(T))
