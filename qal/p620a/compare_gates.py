#!/usr/bin/env python3
"""Digit-identity comparison: P620a gate outputs vs committed LOCAL-XYCE records.
Usage: compare_gates.py <p620a_results_dir>
where the dir holds tg15p/sw_tg15p_z.cir.mt0, banktank/c_...mt0 (+ row json if
re-derived), skept/rows.json.
Writes p620a_xyce_offset.json next to this script if any digit moves.
"""
import json, os, re, sys

QAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1)] = m.group(2)
            except ValueError:
                pass
    return d

def cmp_mt0(name, committed, mine, rep):
    c, p = parse_mt0(committed), parse_mt0(mine)
    same, moved = 0, []
    for k in c:
        if k not in p:
            moved.append((k, c[k], "MISSING"))
            continue
        if c[k] == p[k]:
            same += 1
        else:
            cv, pv = float(c[k]), float(p[k])
            rel = (pv - cv) / cv if cv != 0 else (0.0 if pv == 0 else float("inf"))
            moved.append((k, c[k], p[k], rel))
    rep[name] = dict(
        n_measures=len(c), digit_identical=same, moved=len(moved),
        moved_detail=[dict(measure=m[0], committed=m[1],
                           p620a=(m[2] if len(m) > 2 else None),
                           rel=(m[3] if len(m) > 3 else None)) for m in moved],
        PASS=(len(moved) == 0))
    return rep[name]["PASS"]

def main(rdir):
    rep = {}
    ok1 = cmp_mt0("tg15p",
                  os.path.join(QAL, "swsweep/sw_tg15p_z.cir.mt0"),
                  os.path.join(rdir, "tg15p/sw_tg15p_z.cir.mt0"), rep)
    ok2 = cmp_mt0("banktank",
                  os.path.join(QAL, "banktank/c_m10_T200_H4_dv1200_free.cir.mt0"),
                  os.path.join(rdir, "banktank/c_m10_T200_H4_dv1200_free.cir.mt0"), rep)
    # headline row
    try:
        cm = json.load(open(os.path.join(QAL, "skept/rows.json")))["headline"]
        pm = json.load(open(os.path.join(rdir, "skept/rows.json")))["headline"]
        keys = ("t_hop_ps", "VBPK", "VBEND", "VAEND", "VA_open", "IPK_uA")
        det = {}
        okh = True
        for k in keys:
            cv, pv = cm[k], pm[k]
            rel = (pv - cv) / cv if cv else 0.0
            det[k] = dict(committed=cv, p620a=pv, rel=rel)
            if k == "t_hop_ps":
                okh &= abs(rel) <= 1e-6
            else:
                okh &= ("%.7g" % cv) == ("%.7g" % pv)
        rep["headline"] = dict(detail=det, PASS=okh)
    except Exception as e:
        rep["headline"] = dict(error=str(e), PASS=False)
        okh = False
    rep["ALL_PASS"] = ok1 and ok2 and okh
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "gate_comparison.json")
    json.dump(rep, open(out, "w"), indent=1)
    print(json.dumps({k: (v if k == "ALL_PASS" else
                          {kk: v[kk] for kk in v if kk != "moved_detail"})
                      for k, v in rep.items()}, indent=1, default=str))
    if not rep["ALL_PASS"]:
        offs = {}
        for g in ("tg15p", "banktank"):
            for m in rep[g].get("moved_detail", []):
                offs["%s.%s" % (g, m["measure"])] = m
        json.dump(offs, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "p620a_xyce_offset.json"), "w"), indent=1)
    return 0 if rep["ALL_PASS"] else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
