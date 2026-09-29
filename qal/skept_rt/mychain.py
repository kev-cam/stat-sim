#!/usr/bin/env python3
"""INDEPENDENT recomputation of the 6-bank chain separation-by-depth and, in
addition, the PER-STAGE SETTLING COMPLETENESS that the brief demanded and the
track's chain section did not report.

For each bank j the deck prints only the two electrically distinct class
representatives o{j}_0 and o{j}_1 (the vtaudit convention: four cells per class
are degenerate).  At bank j's own stage boundary:
    separation = (the HIGH representative) - (the LOW representative)
    settle_hi  = HIGH / rail_j          <- how much of its own rail the pull-UP
                                           cell has actually reached
    settle_lo  = 1 - LOW / rail_j
The chain inverts every stage, so which representative is HIGH alternates; it is
determined from the data, not assumed.
"""
import json, sys

FLOOR_MV = 6.44


class W:
    def __init__(self, path):
        f = open(path)
        self.h = [c.upper() for c in f.readline().split()]
        self.rows = []
        for ln in f:
            p = ln.split()
            if not p or p[0].startswith("End"):
                continue
            try:
                self.rows.append([float(x) for x in p])
            except ValueError:
                continue
        self.ti = self.h.index("TIME")
        self.t = [r[self.ti] * 1e12 for r in self.rows]

    def at(self, name, tps):
        c = self.h.index(name.upper())
        if tps <= self.t[0]:
            return self.rows[0][c]
        for k in range(1, len(self.t)):
            if self.t[k] >= tps:
                t0, t1 = self.t[k - 1], self.t[k]
                y0, y1 = self.rows[k - 1][c], self.rows[k][c]
                f = 0.0 if t1 == t0 else (tps - t0) / (t1 - t0)
                return y0 + f * (y1 - y0)
        return self.rows[-1][c]


def go(prn, bound, label):
    w = W(prn)
    print("=" * 118)
    print("%s   (my own extraction from %s)" % (label, prn.split("/")[-1]))
    print("   waveform spans %.1f -> %.1f ps, %d samples" % (w.t[0], w.t[-1], len(w.t)))
    print("=" * 118)
    print("%-5s %11s %11s %11s %12s %11s %11s %11s  %s"
          % ("bank", "rail_V", "outA_V", "outB_V", "sep_mV", "HIGH/rail%",
             "1-LOW/rail%", "x floor", "verdict"))
    out = {}
    for j in range(1, 7):
        tb = bound[str(j)] if isinstance(bound, dict) else bound[j - 1]
        rail = w.at("V(RAIL%d)" % j, tb)
        a = w.at("V(O%d_0)" % j, tb)
        b = w.at("V(O%d_1)" % j, tb)
        hi, lo = (a, b) if a > b else (b, a)
        sep = (hi - lo) * 1000.0
        shi = 100.0 * hi / rail if rail else float("nan")
        slo = 100.0 * (1.0 - lo / rail) if rail else float("nan")
        v = "CLEARS" if sep > FLOOR_MV else "**BELOW FLOOR**"
        if shi < 90.0:
            v += "  <-- HIGH CELL NOT SETTLED"
        print("%-5d %11.6f %11.6f %11.6f %12.4f %11.4f %11.4f %11.1f  %s"
              % (j, rail, a, b, sep, shi, slo, sep / FLOOR_MV, v))
        out[j] = dict(rail=rail, o0=a, o1=b, sep_mV=sep, settle_hi_pct=shi,
                      settle_lo_pct=slo)
    print()
    print("  rail ratio bank-to-bank : " + " ".join(
        "%.4f" % (out[j + 1]["rail"] / out[j]["rail"]) for j in range(1, 6)))
    print("  sep  ratio bank-to-bank : " + " ".join(
        "%.4f" % (out[j + 1]["sep_mV"] / out[j]["sep_mV"]) for j in range(1, 6)))
    print("  HIGH-cell settling by depth (%% of own rail): " + " ".join(
        "%.3f" % out[j]["settle_hi_pct"] for j in range(1, 7)))
    return out


if __name__ == "__main__":
    j = json.load(open(sys.argv[1]))
    go(j["prn"] if len(sys.argv) < 3 else sys.argv[2], j["bound_ps"], j["tag"])
