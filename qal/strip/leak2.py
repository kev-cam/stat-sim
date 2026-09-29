#!/usr/bin/env python3
"""L1/L2 redone as CONSTANT-BIAS TRANSIENTS.

Why not .DC: a .DC sweep of these devices under the PyMS-compiled PSP103 did not
return inside 300 s (leak_off.cir, leak_gate.cir -- both abandoned, no .prn, and
both are left on disk as the record of the attempt).  Why not a slow RAMP: the
capacitive displacement current through a 2 fF node on even a 20 ns ramp is
~40 nA, which SWAMPS the sub-nA leakage the study is trying to measure.  So every
bias point is held CONSTANT and its own device set is instantiated separately;
one short transient then reads all of them at a true steady state, where the
displacement current is identically zero.

Read at t = 50 ps.  Nothing in this deck moves, so that is a DC operating point.
"""
import json, os
import common as C

HERE = C.HERE
RAILS = [0.50, 0.55, 0.5571, 0.60, 0.6077, 0.65, 0.70, 0.75]
OFF = [("n", 0.74), ("n", 1.12), ("n", 0.15),
       ("p", 1.12), ("p", 0.56), ("p", 0.15)]
GATE = [("n", 0.74), ("n", 1.12), ("p", 1.12), ("p", 0.56)]


def tag_of(t, w):
    return "%s%s" % (t, str(w).replace(".", "p"))


def deck():
    L = C.head()
    amm = {}
    for ri, rail in enumerate(RAILS):
        L.append("VR%d r%d 0 %g" % (ri, ri, rail))
        for di, (t, w) in enumerate(OFF):
            a = "VA%d_%d" % (ri, di)
            amm[("off", ri, di)] = a
            if t == "n":
                # OFF nMOS: drain at the rail via a 0 V ammeter, g = s = b = 0
                L += ["%s r%d d%d_%d 0" % (a, ri, ri, di),
                      "XO%d_%d d%d_%d 0 0 0 sg13_lv_nmos w=%gu l=0.13u"
                      % (ri, di, ri, di, w)]
            else:
                # OFF pMOS: s = b = g = rail, drain at 0 V via a 0 V ammeter
                L += ["%s e%d_%d 0 0" % (a, ri, di),
                      "XO%d_%d e%d_%d r%d r%d r%d sg13_lv_pmos w=%gu l=0.13u"
                      % (ri, di, ri, di, ri, ri, ri, w)]
        for di, (t, w) in enumerate(GATE):
            a = "VG%d_%d" % (ri, di)
            amm[("gate", ri, di)] = a
            if t == "n":
                # ON nMOS, gate current only: g = rail via ammeter, d = s = b = 0
                L += ["%s r%d g%d_%d 0" % (a, ri, ri, di),
                      "XG%d_%d 0 g%d_%d 0 0 sg13_lv_nmos w=%gu l=0.13u"
                      % (ri, di, ri, di, w)]
            else:
                # ON pMOS: g = 0 via ammeter, s = d = b = rail
                L += ["%s 0 h%d_%d 0" % (a, ri, di),
                      "XG%d_%d r%d h%d_%d r%d r%d sg13_lv_pmos w=%gu l=0.13u"
                      % (ri, di, ri, ri, di, ri, ri, w)]
    pr = ["I(%s)" % v for v in amm.values()]
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L += [".tran 1p 50p", ".end"]
    return L, amm


def main():
    L, amm = deck()
    p, msg, wall = C.run("leak_bias.cir", L, timeout=900)
    print(msg, flush=True)
    if not p:
        json.dump({"error": msg}, open(os.path.join(HERE, "LEAK_DC.json"), "w"))
        return
    w = C.W(p + ".prn")
    out = {"_read_at_ps": 50.0, "_wall_s": wall,
           "_method": ("constant-bias transient read at a true steady state; "
                       ".DC did not return under PyMS-compiled PSP103 and a "
                       "ramp would inject ~40 nA of displacement current"),
           "off": {}, "gate": {}}
    for di, (t, wid) in enumerate(OFF):
        out["off"][tag_of(t, wid)] = {
            "type": t, "w_um": wid, "l_um": 0.13,
            "Id_off_nA": {("%.4f" % RAILS[ri]):
                          abs(w.at("I(%s)" % amm[("off", ri, di)], 50.0)) * 1e9
                          for ri in range(len(RAILS))}}
    for di, (t, wid) in enumerate(GATE):
        out["gate"][tag_of(t, wid)] = {
            "type": t, "w_um": wid, "l_um": 0.13,
            "Ig_on_nA": {("%.4f" % RAILS[ri]):
                         abs(w.at("I(%s)" % amm[("gate", ri, di)], 50.0)) * 1e9
                         for ri in range(len(RAILS))}}
    json.dump(out, open(os.path.join(HERE, "LEAK_DC.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
