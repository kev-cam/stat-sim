#!/usr/bin/env python3
"""(e, part 1) THE RECEIVER THRESHOLD AND TRANSITION WINDOW -- measured here.

The brief's acceptance target is "the receiver needs ~0.59 x its own rail
(DC-measured) with a transition window only 30-60 mV wide".  Rather than quote
that from another study's files, this run measures it in its own harness, for
BOTH receivers that matter:

  static  the campaign-standard inverter (wp 1.12u / wn 0.74u) on its own rail.
          This is the number the campaign quotes; reproducing it validates the
          method before it is applied to the new cell.
  strip   a STRIPPED o21ai on its own rail, wired so one input controls the
          output (A2 = 0, B1 = rail  =>  q = NOT A1), with BOTH output nodes
          initialised to 0 -- the real QAL initial condition, where the ramping
          rail precharges from zero.  This measures the REGENERATIVE decision
          boundary of the cross-coupled pair, which is the quantity a stripped
          chain actually has to clear, and it is not the same quantity as a
          static inverter's trip point.

METHOD: no .DC (it does not return under the PyMS-compiled PSP103 here -- see
leak2.py).  Instead N INDEPENDENT copies of the receiver, each with its input
held at its own constant voltage, are placed in ONE deck and read at a steady
state.  Two passes: a coarse grid, then a fine grid across the bracket the
coarse pass finds.
"""
import json, os, sys
import common as C
import cells as K

HERE = C.HERE


def deck(kind, rail, vins):
    L = C.head() + ["VR r 0 %g" % rail]
    ics, prs = [], []
    for j, vi in enumerate(vins):
        L.append("VIN%d in%d 0 %.6f" % (j, j, vi))
        if kind == "static":
            L += ["XRP%d y%d in%d r r sg13_lv_pmos w=1.12u l=0.13u" % (j, j, j),
                  "XRN%d y%d in%d 0 0 sg13_lv_nmos w=0.74u l=0.13u" % (j, j, j),
                  "CRL%d y%d 0 %gf" % (j, j, C.CLOAD)]
            ics.append("V(y%d)=0" % j)
            prs.append("V(y%d)" % j)
        else:
            # stripped o21ai wired as an inverter on A1: A2 = 0, B1 = rail
            L += ["VA2_%d a2_%d 0 0" % (j, j), "VA2B_%d a2b_%d 0 %g" % (j, j, rail),
                  "VB1_%d b1_%d 0 %g" % (j, j, rail), "VB1B_%d b1b_%d 0 0" % (j, j),
                  "VINB%d inb%d 0 %.6f" % (j, j, rail - vi)]
            lit = lambda l, j=j: {"A1": "in%d" % j, "A1#": "inb%d" % j,
                                  "A2": "a2_%d" % j, "A2#": "a2b_%d" % j,
                                  "B1": "b1_%d" % j, "B1#": "b1b_%d" % j}[l]
            ln, outs = K.strip_cell(j, "o21ai", "r", "0", C.WXC, C.WTREE,
                                    C.CLOAD, lit)
            L += ln
            ics += ["V(%s)=0" % outs[0], "V(%s)=0" % outs[1]]
            prs += ["V(%s)" % outs[0], "V(%s)" % outs[1]]
    L.append(".ic " + " ".join(ics))
    for k in range(0, len(prs), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(prs[k:k + 8]))
    # 50 ns: a near-threshold pull-up on a 0.56 V rail charges 2 fF
    # slowly, and an earlier read measures SETTLING, not a DC level.
    # (The first attempt read at 400 ps and reported a static-inverter
    # trip of 0.048 V = 0.087 x rail, which is a settling artefact.)
    L += [".tran 20p 50000p", ".end"]
    return L


def curve(kind, rail, vins, tag):
    p, msg, wall = C.run("rx_%s.cir" % tag, deck(kind, rail, vins), timeout=900)
    print(" ", tag, msg, flush=True)
    if not p:
        return None
    w = C.W(p + ".prn")
    out = []
    for j, vi in enumerate(vins):
        if kind == "static":
            out.append((vi, w.at("V(y%d)" % j, 50000.0)))
        else:
            out.append((vi, w.at("V(q%d)" % j, 50000.0)))
    return out


def analyse(cv, rail):
    """trip = input at which the output crosses rail/2 (falling);
    window = input span over which the output goes 90% -> 10% of rail."""
    def xat(level):
        for k in range(1, len(cv)):
            a, b = cv[k - 1][1], cv[k][1]
            if a > level >= b:
                f = (a - level) / (a - b) if a != b else 0.0
                return cv[k - 1][0] + f * (cv[k][0] - cv[k - 1][0])
        return None
    trip = xat(0.5 * rail)
    v90, v10 = xat(0.9 * rail), xat(0.1 * rail)
    return dict(rail_V=rail, trip_V=trip,
                trip_over_rail=None if trip is None else trip / rail,
                v_in_at_out90_V=v90, v_in_at_out10_V=v10,
                window_mV=None if (v90 is None or v10 is None)
                else (v10 - v90) * 1e3,
                curve=[[round(a, 5), round(b, 6)] for a, b in cv])


def main():
    out = {"_method": ("N independent receiver copies at constant input in one "
                       "deck, read at a steady state; .DC does not return under "
                       "PyMS-compiled PSP103 in this environment"),
           "_note": ("the stripped receiver is measured with BOTH output nodes "
                     "initialised to 0 -- the real QAL condition, where the "
                     "ramping rail precharges from zero -- so the number is the "
                     "REGENERATIVE decision boundary of the cross-coupled pair, "
                     "not a static inverter trip point"),
           "static": {}, "strip": {}}
    plan = [("static", r) for r in (0.45, 0.5571, 0.6077, 1.0)] + \
           [("strip", r) for r in (0.5571, 0.6077)]
    for kind, rail in plan:
        tag = "%s_r%s" % (kind, ("%.4f" % rail).replace(".", "p"))
        n = 26 if kind == "static" else 21
        coarse = [rail * i / (n - 1.0) for i in range(n)]
        cv = curve(kind, rail, coarse, tag + "_c")
        if cv is None:
            continue
        a = analyse(cv, rail)
        # fine pass across the bracket
        if a["trip_V"] is not None:
            lo = max(0.0, a["trip_V"] - 0.05)
            hi = min(rail, a["trip_V"] + 0.05)
            fine = [lo + (hi - lo) * i / 24.0 for i in range(25)]
            cf = curve(kind, rail, fine, tag + "_f")
            if cf:
                a = analyse(cf, rail)
                a["coarse"] = [[round(x, 5), round(y, 6)] for x, y in cv]
        out[kind][("%.4f" % rail)] = a
        print("  ->", kind, rail, "trip", a["trip_V"], "=",
              a["trip_over_rail"], "x rail, window", a["window_mV"], "mV",
              flush=True)
    json.dump(out, open(os.path.join(HERE, "RECEIVER.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
