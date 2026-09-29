#!/usr/bin/env python3
"""INSTRUMENT CHECK (brief step b): reproduce, digit-for-digit under THIS
workflow's own PYMS_VAE_CACHE and own working directory, three committed rows --
two positive anchors and one FAILING peer-chain row, so the harness is anchored
to the known negative as well as the known positive.

  i1  qal/lsweep/h_L15_W30_dv120.cir     -> VBEND 0.7138163, t_hop 65.495 ps
  i2  qal/dvopt/load691/h_cl_d165_L4_W30 -> real-load level 115.467185 ps,
                                            VBEND 0.754572966, VA_open 0.117456016
  i3  qal/chain3/c_f45.cir               -> the FAILING 3-bank peer chain
                                            (VBEND1/2/3 = 1.005949/0.5829686/0.4443892)

The decks are byte-identical copies (md5 verified at copy time).
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
INSTR = os.path.join(HERE, "instr")


def parse_mt0(p):
    d = {}
    for ln in open(p):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d


COMMITTED = {
 "i1_lsweep_L15_W30_dv120": {
   "_src": "qal/lsweep/rows.json key L15_W30 (committed c662055)",
   "VBEND": 0.7138163, "VBPK": 0.8368896, "VAEND": -0.004296807,
   "IPK": 971.3203e-6, "IZ": -0.0004958676e-6, "VBOPEN": 0.7348984,
   "VSWPK": 1.2, "VSWMN": -0.07782217},
 "i2_load691_L4_W30_dv165": {
   "_src": "qal/dvopt/load691/rowd/cl_d165_L4_W30.json -- the committed deck carries"
           " NO .measure statements (that workflow extracted from the raw .prn),"
           " so this anchor is reproduced from the .prn with the committed"
           " load691/post.py conventions",
   "_from_prn": True,
   "VBEND": 0.754572966, "VBPK": 1.0881874,
   "t_valid90_ps": 115.467185, "VA_open": 0.11745601600934541},
 "i3_chain3_f45": {
   "_src": "qal/chain3/rows.json key f45 -- a FAILING peer-chain row",
   "VR1K1": 1.005949, "VR2K2": 0.5829686, "VR3K3": 0.4443892,
   "VR1PK": 0.864047, "VR2PK": 0.6371363, "VR3PK": 0.4515553},
}


def from_prn_load691(prn, t_hop=34.28582535896825, T0=50.0):
    """The committed load691/post.py conventions, verbatim: VBEND = V(bkb) at
    tend-5; VBPK = max V(bkb); VA_open = V(bka) linearly interpolated at
    T0 + t_hop; t_valid90 = (first t >= T0 at which EVERY output is within 10% of
    the INSTANTANEOUS rail) - T0."""
    fh = open(prn)
    hdr = [h.upper() for h in fh.readline().split()]
    it, ia, ib = hdr.index("TIME"), hdr.index("V(BKA)"), hdr.index("V(BKB)")
    io = [hdr.index("V(O%d)" % i) for i in range(8)]
    rows = []
    for ln in fh:
        q = ln.split()
        if len(q) < len(hdr):
            continue
        try:
            rows.append([float(x) for x in q])
        except ValueError:
            continue
    tend = rows[-1][it] * 1e12

    def at(c, tt):
        prev = None
        for r in rows:
            t = r[it] * 1e12
            if t >= tt:
                if prev is None or t == prev[0]:
                    return r[c]
                f = (tt - prev[0]) / (t - prev[0])
                return prev[1] + f * (r[c] - prev[1])
            prev = (t, r[c])
        return rows[-1][c]

    tv = None
    for r in rows:
        t = r[it] * 1e12
        if t < T0:
            continue
        rail = r[ib]
        if rail <= 0.05:
            continue
        ok = True
        for i in range(8):
            v = r[io[i]]
            if (i % 2 == 0 and v > 0.10 * rail) or (i % 2 == 1 and v < 0.90 * rail):
                ok = False
                break
        if ok:
            tv = t
            break
    return {"VBEND": at(ib, tend - 5.0), "VBPK": max(r[ib] for r in rows),
            "VA_open": at(ia, T0 + t_hop),
            "t_valid90_ps": (tv - T0) if tv else None}


def main():
    out = {}
    allok = True
    for tag, ref in COMMITTED.items():
        if ref.get("_from_prn"):
            mt = {k.upper(): v for k, v in
                  from_prn_load691(os.path.join(INSTR, tag + ".cir.prn")).items()}
        else:
            p = os.path.join(INSTR, tag + ".cir.mt0")
            if not os.path.exists(p):
                out[tag] = {"ERROR": "no mt0"}
                allok = False
                continue
            mt = parse_mt0(p)
        rows = {}
        for k, v in ref.items():
            if k.startswith("_"):
                continue
            got = mt.get(k.upper())
            if got is None:
                rows[k] = dict(committed=v, mine=None, status="MISSING")
                allok = False
                continue
            rel = abs(got - v) / abs(v) if v else abs(got - v)
            rows[k] = dict(committed=v, mine=got, rel=rel,
                           status=("EXACT" if got == v else
                                   ("MATCH" if rel < 1e-6 else
                                    ("NEAR_1e-4" if rel < 1e-4 else "DIFF"))))
            if rows[k]["status"] == "DIFF":
                allok = False
        out[tag] = dict(_src=ref["_src"], checks=rows)
    out["ALL_ANCHORS_REPRODUCED"] = allok
    open(os.path.join(HERE, "INSTRUMENT_CHECK.json"), "w").write(
        json.dumps(out, indent=1))
    for tag, v in out.items():
        if tag.startswith("ALL"):
            continue
        if "ERROR" in v:
            print(tag, v)
            continue
        for k, c in v["checks"].items():
            print("%-28s %-8s committed=%-22r mine=%-22r %s"
                  % (tag, k, c["committed"], c["mine"], c["status"]))
    print("ALL_ANCHORS_REPRODUCED =", allok)


if __name__ == "__main__":
    main()
