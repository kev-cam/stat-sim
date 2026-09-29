#!/usr/bin/env python3
"""INDEPENDENT waveform reader/extractor written for the audit.  Does NOT import
sk.py or s2sk.py.  Reads the .prn columns directly and recomputes, from the SAME
single waveform:
   t_hop      = (switch-open instant) - T0, taken as the LAST time I(LT) crosses
                zero going through the peak -- RE-DERIVED here from the hop deck's
                own I(LT), not taken from the probe meta.
   VBPK/VBEND = peak and end rail
   t_valid90  = first time ALL EIGHT cells are simultaneously within 10% of the
                INSTANTANEOUS rail and stay so to the end
   t_level    = max(t_hop, t_valid90)   <-- both from THIS waveform
   per-gate settling at open and at end, all eight, never aggregated
"""
import sys

T0 = 50.0


class W:
    def __init__(self, path):
        f = open(path)
        hdr = f.readline().split()
        # Xyce .prn: "Index TIME <cols...>"
        self.h = [c.upper() for c in hdr]
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

    def col(self, name):
        return self.h.index(name.upper())

    def v(self, name):
        c = self.col(name)
        return [r[c] for r in self.rows]

    def at(self, name, tps):
        c = self.col(name)
        if tps <= self.t[0]:
            return self.rows[0][c]
        for k in range(1, len(self.t)):
            if self.t[k] >= tps:
                t0, t1 = self.t[k - 1], self.t[k]
                y0, y1 = self.rows[k - 1][c], self.rows[k][c]
                f = 0.0 if t1 == t0 else (tps - t0) / (t1 - t0)
                return y0 + f * (y1 - y0)
        return self.rows[-1][c]


HI = (0, 2, 4, 6)          # pull-DOWN cells (input high)
LO = (1, 3, 5, 7)          # pull-UP cells  (input low)


def analyse(path, verbose=True):
    w = W(path)
    ilt = w.v("I(LT)")
    t = w.t
    # peak current, then the FIRST zero crossing after it -> the true ZCS instant
    kpk = max(range(len(ilt)), key=lambda k: ilt[k])
    tz = None
    for k in range(kpk + 1, len(ilt)):
        if ilt[k] <= 0.0:
            a, b = ilt[k - 1], ilt[k]
            f = 0.0 if b == a else a / (a - b)
            tz = t[k - 1] + f * (t[k] - t[k - 1])
            break
    vb = w.v("V(bkb)")
    vbpk = max(vb)
    tE = t[-1] - 5.0
    vbe = w.at("V(bkb)", tE)
    vbo = w.at("V(bkb)", tz) if tz else float("nan")

    def settle_at(tps, ref):
        o = {}
        for i in range(8):
            v = w.at("V(o%d)" % i, tps)
            o["o%d" % i] = 100.0 * ((1.0 - v / ref) if i in HI else (v / ref))
        return o

    s_open = settle_at(tz, vbo) if tz else None
    s_end = settle_at(tE, vbe)
    v_end = {"o%d" % i: w.at("V(o%d)" % i, tE) for i in range(8)}

    oc = [w.col("V(o%d)" % i) for i in range(8)]

    def t_valid(f):
        gf = None
        for k in range(len(t)):
            if t[k] < T0 or vb[k] < 0.05:
                continue
            ok = True
            for i in range(8):
                v = w.rows[k][oc[i]]
                s = (1.0 - v / vb[k]) if i in HI else (v / vb[k])
                if s < f:
                    ok = False
                    break
            if ok and gf is None:
                gf = t[k]
            elif not ok:
                gf = None
        return gf

    tv90 = t_valid(0.90)
    t_hop = tz - T0 if tz else float("nan")
    t_lvl = max(x for x in (t_hop, None if tv90 is None else tv90 - T0) if x is not None)
    r = dict(path=path, t_hop_ps=t_hop, VBPK=vbpk, VBEND=vbe, VBOPEN=vbo,
             t_valid90_ps=None if tv90 is None else tv90 - T0, t_level_ps=t_lvl,
             s_open=s_open, s_end=s_end, v_end=v_end,
             VA_end=w.at("V(bka)", tE), VA_open=w.at("V(bka)", tz) if tz else None)
    if verbose:
        print("%-38s t_hop %11.6f  VBPK %10.7f  VBEND %10.7f  t_v90 %11.6f  t_LEVEL %11.6f"
              % (path.split("/")[-1], r["t_hop_ps"], r["VBPK"], r["VBEND"],
                 r["t_valid90_ps"] or float("nan"), r["t_level_ps"]))
        print("   per-gate s_open %%: " + " ".join("o%d=%8.4f" % (i, s_open["o%d" % i])
                                                   for i in range(8)))
        print("   per-gate s_end  %%: " + " ".join("o%d=%8.4f" % (i, s_end["o%d" % i])
                                                   for i in range(8)))
        print("   per-gate v_end  V: " + " ".join("o%d=%9.6f" % (i, v_end["o%d" % i])
                                                  for i in range(8)))
        print("   tank V(bka): at ZCS %.6f  at end %.6f" % (r["VA_open"], r["VA_end"]))
    return r


if __name__ == "__main__":
    for p in sys.argv[1:]:
        analyse(p)
        print()
