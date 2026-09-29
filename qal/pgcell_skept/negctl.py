#!/usr/bin/env python3
"""NEGATIVE CONTROL for the equivalence flow.

A flow that says PASS on everything is worthless unless it is shown to say FAIL
on something.  Three single-edit mutants of the committed netlist and of the
reported pass-gate remap are put through the IDENTICAL E1/E2/E3 flow.  Each must
FAIL all three, or the flow is not evidence."""
import json, os, re, shutil, sys
import veq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "/usr/local/src/stat-sim/qal/pgcell/p2/out"
CMOS = veq.CMOS

MUT = []


def mk(name, src, fn):
    txt = open(src).read()
    new, note = fn(txt)
    assert new != txt, "mutation %s did not change the netlist" % name
    p = os.path.join(HERE, "mut_%s.v" % name)
    open(p, "w").write(new)
    MUT.append((name, p, note))


def swap_first(pat, rep):
    def f(t):
        n = re.sub(pat, rep, t, count=1)
        return n, "%s -> %s (first occurrence)" % (pat, rep)
    return f


if __name__ == "__main__":
    # M1: swap one committed NAND2 for a NOR2 -- identical ports (A,B,Y), so the
    #     mutant still ELABORATES; only the function changes.
    mk("cmos_nand2nor", CMOS, swap_first(r"sg13g2_nand2_1 _37_", "sg13g2_nor2_1 _37_"))
    # M2: swap the two data inputs of one committed mux (ch[3])
    def m2(t):
        n = t.replace(".A0(g[3]),\n    .A1(f[3]),", ".A0(f[3]),\n    .A1(g[3]),", 1)
        return n, "ch[3] mux data inputs exchanged"
    mk("cmos_muxswap", CMOS, m2)
    # M3: in the reported chain-legal pass-gate remap, exchange the two DATA
    #     inputs of one carry mux.  (My first draft targeted the cell TYPE with a
    #     regex that matched the header COMMENT line only -- the mutant was
    #     byte-identical in the logic and correctly came back DETECTED=False.
    #     That is the negative control catching a defect in the negative control.)
    src = os.path.join(OUT, "sha_slice.pgp1c.v")
    def m3(t):
        n = t.replace("pg_mux2 Um10 (.A0(c[0]), .A1(a[0]),",
                      "pg_mux2 Um10 (.A0(a[0]), .A1(c[0]),", 1)
        return n, "pgp1c carry mux Um10 data inputs exchanged"
    mk("pgp1c_muxswap", src, m3)

    models, fun = veq.gen_models()
    R = {}
    for name, p, note in MUT:
        d = dict(mutation=note, path=p)
        d.update(veq.formal("MUT_" + name, p, models))
        d["E3_vectors"] = veq.vectors("MUT_" + name, p, models)
        d["DETECTED"] = bool(not d["E1_sat"]["pass_"] and not d["E2_induct"]["pass_"]
                             and not d["E3_vectors"].get("pass_"))
        R[name] = d
        print("%-18s E1=%s E2=%s E3mism=%s -> DETECTED=%s"
              % (name, d["E1_sat"]["pass_"], d["E2_induct"]["pass_"],
                 d["E3_vectors"].get("mismatches"), d["DETECTED"]), flush=True)
    R["ALL_DETECTED"] = bool(all(v["DETECTED"] for k, v in R.items()
                                 if isinstance(v, dict)))
    json.dump(R, open(os.path.join(HERE, "NEGCTL.json"), "w"), indent=1)
    print("ALL_DETECTED", R["ALL_DETECTED"])
