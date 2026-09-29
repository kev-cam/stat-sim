#!/usr/bin/env python3
"""D1 + D2, generalised: the delivery slope on the TOPPED rail and the resulting
lift on the FEEDING stage's LOW output nodes, computed per row from that row's
OWN schedule so the window is correct at every beat period.

Window = [ open[0] + EDGE , min(bound[3], close[1]) - EDGE ]
  open[0]  = hop 1's MEASURED zero -- bank 3 is charged, its hold begins
  bound[3] = bank 3's stage boundary -- where the settling is read
  close[1] = hop 2's close -- MUST be excluded, it drains bank 2 and would
             swamp the coupling measurement with bank 2's own drain event
At T = 200 that is [300, 399]; at T = 120 hop 2 closes at 320, so the window
shortens automatically instead of silently including the drain.

Works on any row that carries close_ps/open_ps/bound_ps and has a .prn.
"""
import json, os, sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

HERE = os.path.dirname(os.path.abspath(__file__))
SKIPTU = "/usr/local/src/stat-sim/qal/skiptu"
EDGE = SK.EDGE


def col_of(hdr, node):
    want = "v(%s)" % node.lower()
    for c in hdr:
        if c.strip().lower() == want:
            return hdr.index(c)
    return None


def seg_of(hdr, rows, node, t0, t1):
    c = col_of(hdr, node)
    if c is None:
        return None
    return [(r[1] * 1e12, r[c]) for r in rows if t0 <= r[1] * 1e12 <= t1]


def stats(seg):
    if not seg or len(seg) < 3:
        return None
    vs = [v for _, v in seg]
    up, upt, dn = 0.0, None, 0.0
    for j in range(1, len(seg) - 1):
        dt = seg[j + 1][0] - seg[j - 1][0]
        if dt <= 0:
            continue
        s = (seg[j + 1][1] - seg[j - 1][1]) / dt * 1e3
        if s > up:
            up, upt = s, seg[j][0]
        if s < dn:
            dn = s
    return {"V_start": round(vs[0], 6), "V_end": round(vs[-1], 6),
            "V_min": round(min(vs), 6), "V_max": round(max(vs), 6),
            "rise_from_start_mV": round(1e3 * (max(vs) - vs[0]), 3),
            "net_change_mV": round(1e3 * (vs[-1] - vs[0]), 3),
            "max_RISING_dVdt_V_per_ns": round(up, 3),
            "rising_at_ps": round(upt, 3) if upt else None,
            "max_FALLING_dVdt_V_per_ns": round(dn, 3)}


def window(r):
    op = r.get("open_ps") or []
    cl = r.get("close_ps") or []
    bd = r.get("bound_ps") or {}
    b3 = bd.get("3", bd.get(3))
    if not op or not cl or b3 is None:
        return None
    t0 = op[0] + EDGE
    t1 = min(b3, cl[1] if len(cl) > 1 else b3) - EDGE
    return (round(t0, 3), round(t1, 3)) if t1 > t0 else None


def analyse(r, prn):
    w = window(r)
    if w is None or not os.path.exists(prn):
        return None
    hdr, rows = SK.read_prn(prn)
    out = {"window_ps": list(w)}
    for nd in ("rail3", "rail2"):
        s = stats(seg_of(hdr, rows, nd, *w))
        if s:
            out[nd] = s
    lowidx = [i for i in range(SK.MGATE) if SK.is_hi(2, i)]
    lows = {}
    for i in lowidx:
        s = stats(seg_of(hdr, rows, "o2_%d" % i, *w))
        if s:
            lows["o2_%d" % i] = s
    if lows:
        out["stage2_LOW_nodes"] = lows
        out["worst_LOW_lift_mV"] = round(max(v["rise_from_start_mV"]
                                             for v in lows.values()), 3)
        out["worst_LOW_end_V"] = round(max(v["V_end"] for v in lows.values()), 6)
    return out


def main():
    src = []
    for r in json.load(open(os.path.join(SKIPTU, "rows.json"))):
        d = r.get("deck")
        if d and r["scheme"] == "s4":
            src.append((r["mode"], r, os.path.join(SKIPTU, d + ".prn")))
    for f in sorted(os.listdir(HERE)):
        if f.startswith("ROWS_") and f.endswith(".json"):
            for r in json.load(open(os.path.join(HERE, f))):
                if "error" in r or r.get("scheme") != "s4":
                    continue
                d = r.get("deck")
                if d:
                    src.append(("ptu_CORRECTED", r,
                                os.path.join(HERE, d + ".prn")))

    out = {"_what": __doc__.strip(), "rows": {}}
    print("%-13s %5s %4s | %-13s | %8s %9s %8s | %8s | %9s" %
          ("mode", "T", "dv", "window ps", "r3 rise", "r3 dV/dt+", "r3 exc",
           "r2 exc", "LOW lift"))
    print("%-13s %5s %4s | %-13s | %8s %9s %8s | %8s | %9s" %
          ("", "", "", "", "mV", "V/ns", "mV", "mV", "mV"))
    for mode, r, prn in src:
        a = analyse(r, prn)
        if not a:
            continue
        nm = "%s|%s|T%g|dv%g|L%g|t%g" % (mode, r["scheme"], r["T_ps"], r["dv"],
                                         r.get("ltu_nH", 0), r.get("t_on_ps", 0))
        out["rows"][nm] = a
        r3, r2 = a.get("rail3", {}), a.get("rail2", {})
        print("%-13s %5g %4g | %-13s | %8.1f %9.2f %8.1f | %8.2f | %9.3f" %
              (mode, r["T_ps"], r["dv"], "%g-%g" % tuple(a["window_ps"]),
               r3.get("rise_from_start_mV", float("nan")),
               r3.get("max_RISING_dVdt_V_per_ns", float("nan")),
               1e3 * (r3.get("V_max", 0) - r3.get("V_min", 0)),
               1e3 * (r2.get("V_max", 0) - r2.get("V_min", 0)),
               a.get("worst_LOW_lift_mV", float("nan"))))
    json.dump(out, open(os.path.join(HERE, "COUPLING2.json"), "w"), indent=1)
    print("\nwrote COUPLING2.json (%d rows)" % len(out["rows"]))


if __name__ == "__main__":
    main()
