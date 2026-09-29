#!/usr/bin/env python3
"""SKEPTIC device-count audit.

Static counts are taken by COUNTING TRANSISTOR CARDS IN THE SHIPPED PDK NETLIST
(/usr/local/src/IHP-Open-PDK/.../sg13g2_stdcell.spice), not from any table.
Stripped counts are taken by COUNTING M-CARDS EMITTED BY cellsk.py, not from
the formula -- the formula is then checked against the count.

The audit charges the dual-rail complement explicitly, under two regimes:
  FABRIC   every signal already exists in both polarities (the implicit
           assumption that makes dual-rail look free)
  BOUNDARY the cell is dropped into single-rail logic and must generate the
           complement of each input it uses complemented: +2 devices per input
"""
import os, re, json, collections
import cellsk as K

PDK = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/"
       "sg13g2_stdcell/spice/sg13g2_stdcell.spice")

# family -> the PDK cell that implements it at drive 1
PDKCELL = {
    "inv": "sg13g2_inv_1", "buf": "sg13g2_buf_1",
    "nand2": "sg13g2_nand2_1", "nor2": "sg13g2_nor2_1",
    "and2": "sg13g2_and2_1", "or2": "sg13g2_or2_1",
    "nor2b": "sg13g2_nor2b_1", "xor2": "sg13g2_xor2_1",
    "xnor2": "sg13g2_xnor2_1", "mux2": "sg13g2_mux2_1",
    "a21oi": "sg13g2_a21oi_1", "a21o": "sg13g2_a21o_1",
    "o21ai": "sg13g2_o21ai_1",
}


def pdk_subckts(path):
    txt = open(path, errors="replace").read().splitlines()
    out, cur, body = {}, None, []
    for ln in txt:
        s = ln.strip()
        low = s.lower()
        if low.startswith(".subckt "):
            cur = s.split()[1]
            body = []
        elif low.startswith(".ends"):
            if cur:
                out[cur] = body
            cur, body = None, []
        elif cur is not None:
            body.append(s)
    return out


def count_devs(body):
    n = p = 0
    for s in body:
        if not s or s.startswith("*"):
            continue
        if re.match(r"^[XM]\S*", s, re.I):
            if "pmos" in s.lower():
                p += 1
            elif "nmos" in s.lower():
                n += 1
    return n, p


def main():
    subs = pdk_subckts(PDK)
    ver = K.verify_trees()
    rows = []
    for fam in K.FUNCS:
        cell = PDKCELL[fam]
        assert cell in subs, cell
        nn, np_ = count_devs(subs[cell])
        static = nn + np_
        # stripped: count emitted M-cards, do not trust the formula
        nl, ndev = K.strip_cell(fam, "AUD", "rail", "q", "qb", "1.12u")
        # cross-check against the tree arithmetic
        formula = ver[fam]["n_f"] + ver[fam]["n_g"] + 2
        assert ndev == formula, (fam, ndev, formula)
        # keeper / precharge / holding-path audit on the emitted netlist
        txt = "\n".join(nl).lower()
        assert "keeper" not in txt
        npre = sum(1 for x in nl if x.startswith("X") and "precharge" in x.lower())
        ncomp = len(ver[fam]["needs_complement"])
        rows.append(dict(
            fam=fam, liberty=ver[fam]["liberty"],
            pdk_cell=cell, pdk_nmos=nn, pdk_pmos=np_,
            static=static,
            inv_overhead=static - 2 * max(ver[fam]["n_f"], ver[fam]["n_g"]),
            tree_f=ver[fam]["n_f"], tree_g=ver[fam]["n_g"],
            stripped_fabric=ndev,
            delta_fabric=ndev - static,
            complement_inputs=ncomp,
            stripped_boundary=ndev + 2 * ncomp,
            delta_boundary=ndev + 2 * ncomp - static,
            precharge_devices=npre,
            nets_per_signal=2,
            vectors_checked=ver[fam]["vectors"],
            tree_mismatches=ver[fam]["mismatches"],
        ))
    rows.sort(key=lambda r: (r["delta_fabric"], r["fam"]))
    hdr = ("fam     static  trees   strip  d_fab  ncomp  strip_bnd  d_bnd")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print("%-7s %5d  %d+%d %7d %+6d %6d %10d %+6d" % (
            r["fam"], r["static"], r["tree_f"], r["tree_g"],
            r["stripped_fabric"], r["delta_fabric"], r["complement_inputs"],
            r["stripped_boundary"], r["delta_boundary"]))
    wins_f = [r["fam"] for r in rows if r["delta_fabric"] < 0]
    ties_f = [r["fam"] for r in rows if r["delta_fabric"] == 0]
    wins_b = [r["fam"] for r in rows if r["delta_boundary"] < 0]
    ties_b = [r["fam"] for r in rows if r["delta_boundary"] == 0]
    print()
    print("FABRIC regime   (complement free): wins=%s ties=%s" % (wins_f or "NONE", ties_f or "NONE"))
    print("BOUNDARY regime (complement paid): wins=%s ties=%s" % (wins_b or "NONE", ties_b or "NONE"))
    d = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(d, "DEVCOUNT_SKEPT.json"), "w") as f:
        json.dump(dict(rows=rows,
                       fabric_wins=wins_f, fabric_ties=ties_f,
                       boundary_wins=wins_b, boundary_ties=ties_b,
                       pdk_source=PDK), f, indent=1)


if __name__ == "__main__":
    main()
