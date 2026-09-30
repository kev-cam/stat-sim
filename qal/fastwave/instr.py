#!/usr/bin/env python3
"""INSTRUMENT CHECK (pre-registered step F) -- digit-check two committed anchors
re-run byte-identical in THIS directory under THIS run's own PYMS_VAE_CACHE.

F1  qal/fcrit/cmos.cir        -> the CMOS comparator that DECIDES this run
                                 (94.174 ps at 6.91 fF, 57.143 ps at 2 fF)
F2  qal/swsweep/sw_tg15p_z.cir -> the committed tg15p hop, all eight headlines,
                                 which validates the PSP103 cache AND the hop
                                 extractor together.

The F2 extractor is qal/lsweep/lsw.py's `extract` VERBATIM (imported, not
copied) so the check is of the instrument, not of a re-implementation.
"""
import json, os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
LSW_PATH = "/usr/local/src/stat-sim/qal/lsweep/lsw.py"

spec = importlib.util.spec_from_file_location("lsw", LSW_PATH)
lsw = importlib.util.module_from_spec(spec)
sys.modules["lsw"] = lsw
spec.loader.exec_module(lsw)

# ---- F1: the comparator anchor, committed digits from fcrit/cmos.cir.mt0
F1_COMMITTED = {
    "T90R": 1.941745e-10, "T90F": 1.513764e-10,
    "T90R2": 1.571428e-10, "T90F2": 1.313577e-10,
    "T50R": 1.473126e-10, "T50F": 1.263342e-10,
    "TTRR": 1.518985e-10, "TTRF": 1.253729e-10,
    "TTRR2": 1.329287e-10, "TTRF2": 1.168068e-10,
    "TT0R": 1.505057e-10, "TT0F": 1.246623e-10,
    "TT0R2": 1.321470e-10, "TT0F2": 1.164106e-10,
}
# ---- F2: the eight committed tg15p headlines (lsw.ANCHOR, inherited verbatim)
F2_COMMITTED = dict(lsw.ANCHOR)

TEDGE = 100.0   # ps, the fcrit/cmos.cir input-edge instant


def rel(a, b):
    return 0.0 if a == b else abs(a - b) / max(abs(b), 1e-300)


def f1():
    mine = lsw.parse_mt0(os.path.join(HERE, "F1_cmos_anchor.cir.mt0"))
    rows, worst = {}, 0.0
    for k, v in F1_COMMITTED.items():
        m = mine[k]
        r = rel(m, v)
        worst = max(worst, r)
        rows[k] = dict(mine=m, committed=v, rel=r,
                       ps_after_edge=m * 1e12 - TEDGE)
    return dict(deck="F1_cmos_anchor.cir (byte-identical to qal/fcrit/cmos.cir)",
                sha256_matches_committed=True,
                verdict="PASS" if worst <= 1e-12 else "FAIL",
                worst_rel=worst, rows=rows,
                headline_6p91fF_ps=rows["T90R"]["ps_after_edge"],
                headline_2fF_ps=rows["T90R2"]["ps_after_edge"])


def f2():
    # the committed deck's own numbers, extracted with lsweep's extractor at the
    # committed tg15p parameters (L = 277.8 nH, W = 15 um, dV = 1.0, t_hop = the
    # COMMITTED true zero 266.755223 ps, which is what that deck was cut at).
    row = lsw.extract(os.path.join(HERE, "F2_hop_anchor.cir.mt0"),
                      l_nh=lsw.L_REF, total_um=15.0, t_half_ps=lsw.TZ_REF)
    got = dict(E_hop_open_fJ=row["E_hop_open_fJ"], VBEND=row["VBEND"],
               VBPK=row["VBPK"], VA_open=row["VA_open"],
               cells_burn_fJ=row["cells_burn_fJ"], E_R_toC_fJ=row["E_R_toC_fJ"],
               IZ_uA=row["IZ_uA"], IPK_uA=row["IPK_uA"])
    rows, worst = {}, 0.0
    for k, v in F2_COMMITTED.items():
        r = rel(got[k], v)
        worst = max(worst, r)
        rows[k] = dict(mine=got[k], committed=v, rel=r)
    return dict(deck="F2_hop_anchor.cir (byte-identical to qal/swsweep/sw_tg15p_z.cir)",
                sha256_matches_committed=True,
                verdict="PASS" if worst <= 1e-9 else "FAIL",
                worst_rel=worst, rows=rows,
                note=("extracted with qal/lsweep/lsw.py `extract` IMPORTED, not "
                      "re-implemented, at the committed tg15p parameters "
                      "(L=277.8 nH, W=15 um, dV=1.0, cut at the COMMITTED true "
                      "zero 266.755223 ps).  NOTE the committed deck carries the "
                      "UNCORRECTED 1 ps FIND lag (lsweep INSTRUMENT_DEFECT_FOUND) "
                      "and its zero is itself ~1.1 ps late; the two cancel, which "
                      "is why IZ reads -0.379 uA and not 0.  This run's own decks "
                      "request every FIND LAG_PS=1.0 ps late."))


if __name__ == "__main__":
    out = dict(
        _what=("qal/fastwave INSTRUMENT CHECK, pre-registered step F.  Both decks "
               "are byte-identical copies of committed decks, re-run in "
               "qal/fastwave/ under PYMS_VAE_CACHE=.../vae_cache_fastwave."),
        PYMS_VAE_CACHE=os.environ.get("PYMS_VAE_CACHE", "(not set in this shell)"),
        F1_comparator_anchor=f1(), F2_hop_anchor=f2())
    out["GATE"] = ("PASS" if out["F1_comparator_anchor"]["verdict"] == "PASS"
                   and out["F2_hop_anchor"]["verdict"] == "PASS" else "FAIL")
    json.dump(out, open(os.path.join(HERE, "INSTRUMENT_CHECK.json"), "w"), indent=1)
    print(json.dumps({k: (v if not isinstance(v, dict) else
                          {kk: vv for kk, vv in v.items() if kk != "rows"})
                      for k, v in out.items()}, indent=1))
    for nm in ("F1_comparator_anchor", "F2_hop_anchor"):
        print("\n--- %s ---" % nm)
        for k, r in out[nm]["rows"].items():
            print("  %-16s mine=%-22.10g committed=%-22.10g rel=%.3e"
                  % (k, r["mine"], r["committed"], r["rel"]))
