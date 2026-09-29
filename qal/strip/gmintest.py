#!/usr/bin/env python3
"""L5: how much of the measured sub-pA 'leakage' is the simulator's GMIN?

The gate-terminal reading in LEAK_DC.json came out at EXACTLY rail * 1e-12 A for
every nMOS width and every rail -- the signature of a 1e-12 S conductance, not of
gate tunnelling.  That raises the question for the off-state numbers too.  This
deck answers it by measurement rather than by argument:

  RREF   a 2 fF node with a known 1e12 ohm resistor to ground.  This is what a
         1e-12 S path looks like in this harness, exactly.
  HARD   a 2 fF node with an nMOS whose gate is driven to -0.3 V, i.e. 0.3 V
         BELOW its source.  Its channel current is ~3 decades below the Vgs = 0
         case, so whatever it still leaks is the floor, not the device.
  BARE   the real stripped-cell node, repeated here so all three share one
         solver trajectory.
  NULL   capacitor alone.

Whatever the split, note the direction it cuts: any GMIN component INFLATES the
measured leakage, so the study's leakage number is an UPPER BOUND either way.
"""
import json, os
import common as C

HERE = C.HERE
TEND = 100000.0


def deck(rail):
    L = C.head() + ["VR r 0 %g" % rail, "VNEG vneg 0 -0.3"]
    L += ["CN qnull 0 %gf" % C.CLOAD]
    L += ["CR qref 0 %gf" % C.CLOAD, "RREF qref 0 1e12"]
    L += ["CH qhard 0 %gf" % C.CLOAD,
          "XH qhard vneg 0 0 sg13_lv_nmos w=%gu l=0.13u" % C.WTREE]
    L += ["CB qbare 0 %gf" % C.CLOAD,
          "XBN qbare 0 0 0 sg13_lv_nmos w=%gu l=0.13u" % C.WTREE,
          "XBP qbare r r r sg13_lv_pmos w=%gu l=0.13u" % C.WXC]
    nodes = ["qnull", "qref", "qhard", "qbare"]
    L.append(".ic " + " ".join("V(%s)=%g" % (n, rail) for n in nodes))
    L.append(".print tran " + " ".join("V(%s)" % n for n in nodes))
    L += [".tran 5p %gp 0 20p" % TEND, ".end"]
    return L, nodes


def main():
    out = {"_why": ("LEAK_DC's gate reading was exactly rail*1e-12 A, the "
                    "signature of a 1e-12 S conductance. This deck measures what "
                    "a known 1e12 ohm path looks like here (qref) and what a "
                    "hard-off device (Vgs = -0.3 V) still shows (qhard), so the "
                    "GMIN floor is bounded by measurement."),
           "_direction_of_bias": ("any GMIN component INFLATES the measured "
                                  "leakage, so the leakage budget is an UPPER "
                                  "BOUND regardless of how the split lands."),
           "rails": {}}
    for rail in (0.6077,):
        L, nodes = deck(rail)
        p, msg, wall = C.run("leak_gmin.cir", L, timeout=1200)
        print(rail, msg, flush=True)
        if not p:
            out["rails"]["%.4f" % rail] = {"error": msg}
            continue
        w = C.W(p + ".prn")
        d = {"wall_s": wall, "rail_V": rail, "nodes": {}}
        for n in nodes:
            v0 = w.at("V(%s)" % n, 0.0)
            dv = v0 - w.at("V(%s)" % n, TEND)
            d["nodes"][n] = {
                "V0": v0, "droop_uV_at_200ps": (v0 - w.at("V(%s)" % n, 200.0)) * 1e6,
                "droop_uV_at_100ns": dv * 1e6,
                "I_pA": dv * C.CLOAD * 1e-15 / (TEND * 1e-12) * 1e12}
        ref = d["nodes"]["qref"]["I_pA"]
        d["I_of_known_1e12_ohm_pA"] = ref
        d["expected_1e12_ohm_pA"] = rail / 1e12 * 1e12
        out["rails"]["%.4f" % rail] = d
    json.dump(out, open(os.path.join(HERE, "LEAK_GMIN.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
