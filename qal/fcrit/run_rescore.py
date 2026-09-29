#!/usr/bin/env python3
"""Phase 1 driver: re-score every committed chain dataset under the functional
commit criterion.  RE-ANALYSIS ONLY -- no deck in any committed directory is
re-run or written to."""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rescore import Trip, score_deck, NB

HERE = os.path.dirname(os.path.abspath(__file__))
QAL = os.path.dirname(HERE)
TRIP = Trip(os.path.join(HERE, "TRIP.json"), "S")
PAT = [1, 1, 1, 0, 1, 0, 0, 1]          # banktank/bt.py PAT, verbatim


def oh_alt(k, i):
    """chain3 / skip4 / skiptu / restore5: is_hi(k,i) = (i+k)%2==1 -> input HIGH
    -> output LOW.  So out_hi iff (i+k) is even."""
    return (i + k) % 2 == 0


def oh_pat(k, i):
    """banktank: in_hi = PAT[i]==1 for odd k else PAT[i]==0 ; out = not in."""
    in_hi = (PAT[i] == 1) if (k % 2 == 1) else (PAT[i] == 0)
    return not in_hi


def oh_comp(comp):
    """pgcell: inv complements, tg is identity."""
    lv = [list(PAT)]
    for kind in comp:
        lv.append([(1 - b) if kind == "inv" else b for b in lv[-1]])
    return lambda k, i: lv[k][i] == 1


def nb_for(name, tag):
    if tag in ("topup", "rtu", "ptu", "tu", "clamp", "vfull"):
        return "topup_worst"
    return "free"


DATASETS = []

# ---- chain3 : 3 banks, 8 gates, alternating pattern.
# The budget is matched to the row's COMMITTED mode (chain3/ROWS_full.json), not
# to its filename -- c_m10_d120 / c_m10_d180 / c_m45_d150 carry mode="topup"
# with no "topup" in the name, and c_h277_hold carries mode="hold".
_C3MODE = {}
try:
    _C3MODE = {k: v.get("mode") for k, v in
               json.load(open(os.path.join(QAL, "chain3", "ROWS_full.json"))).items()}
except Exception:
    pass
for p in sorted(glob.glob(os.path.join(QAL, "chain3", "c_*.cir"))):
    b = os.path.basename(p)[:-4]
    if not os.path.exists(p + ".prn"):
        continue
    mode = _C3MODE.get(b[2:], "topup" if "topup" in b else "free")
    nbn = {"topup": "topup_worst", "hold": "hold"}.get(mode, "free")
    DATASETS.append(("chain3", b, p, 3, 8, oh_alt, nbn, None))

# ---- skip4 : adjacent decks are 4 banks, skip decks 5
for p in sorted(glob.glob(os.path.join(QAL, "skip4", "c_*.cir"))):
    b = os.path.basename(p)[:-4]
    if not os.path.exists(p + ".prn"):
        continue
    nb = 5 if b.startswith("c_skip") else 4
    DATASETS.append(("skip4", b, p, nb, 8, oh_alt, "free", None))

# ---- skiptu : 4 banks
for p in sorted(glob.glob(os.path.join(QAL, "skiptu", "*.cir"))):
    b = os.path.basename(p)[:-4]
    if not os.path.exists(p + ".prn") or not b.startswith(("r_", "q3_", "q4_")):
        continue
    DATASETS.append(("skiptu", b, p, 4, 8, oh_alt,
                     "topup_worst" if ("tu" in b.split("_")[2:3] or "_rtu_" in b
                                       or "_ptu_" in b) else "free", None))

# ---- banktank : 4 banks, PAT
for p in sorted(glob.glob(os.path.join(QAL, "banktank", "c_*.cir"))):
    b = os.path.basename(p)[:-4]
    if not os.path.exists(p + ".prn"):
        continue
    DATASETS.append(("banktank", b, p, 4, 8, oh_pat,
                     "topup_m6" if ("topup" in b or "vfull" in b) else "free", None))

# ---- resv : 6 banks, only gates 0 and 1 printed
for tagd, sub in (("ctl", "ch_ctl/c_ctl.cir"), ("res20", "ch_res20/c_res20.cir")):
    p = os.path.join(QAL, "resv", sub)
    if os.path.exists(p + ".prn"):
        DATASETS.append(("resv", tagd, p, 6, 2, oh_alt, "free", [0, 1]))

# ---- restore5 : 6 banks, gates 0 and 1
for p in sorted(glob.glob(os.path.join(QAL, "restore5", "c_k*.cir"))):
    b = os.path.basename(p)[:-4]
    if not os.path.exists(p + ".prn"):
        continue
    DATASETS.append(("restore5", b, p, 6, 2, oh_alt, "free", [0, 1]))

# ---- pgcell : 4 banks, composition-dependent pattern
for name, comp in (("CTL_vhi", ["inv"] * 4), ("ALT_vhi", ["inv", "tg", "inv", "tg"]),
                   ("ALT_rail", ["inv", "tg", "inv", "tg"]),
                   ("ALLTG_vhi", ["tg"] * 4)):
    p = os.path.join(QAL, "pgcell", name, "F_%s.cir" % name)
    if os.path.exists(p + ".prn"):
        DATASETS.append(("pgcell", name, p, 4, 8, oh_comp(comp), "free", None))


def main():
    out = {}
    for ds, tag, path, nbank, mgate, oh, nbname, gi in DATASETS:
        try:
            r = score_deck(path, nbank, mgate, oh, TRIP, NB[nbname],
                           gate_idx=gi, label="%s/%s" % (ds, tag))
        except Exception as e:
            print("  ERR %s/%s : %s" % (ds, tag, e))
            continue
        r["dataset"] = ds
        r["tag"] = tag
        r["NB_name"] = nbname
        r["NB_mV"] = round(1000 * NB[nbname], 3)
        # also score at every other budget (same instants, just a different bar)
        alt = {}
        for nm, val in NB.items():
            n = sum(1 for L in r["links"] if L["S3_margin_mV"] >= 1000 * val)
            alt[nm] = dict(links_pass=n,
                           row_pass=bool(r["links"]) and n == len(r["links"]))
        r["at_every_budget"] = alt
        out.setdefault(ds, {})[tag] = r
        print("%-9s %-38s links=%3d  S1(90%%)=%3d  VALUE=%3d  S2=%3d  S3=%3d "
              "[bud=%d late=%d never=%d]  ROW S1=%d VAL=%d S3=%d"
              % (ds, tag, r["n_gates"], r["S1_pass"], r["value_guard_pass"],
                 r["S2_pass"], r["S3_pass"], r["S3_FAIL_budget"],
                 r["S3_FAIL_late"], r["S3_FAIL_never"],
                 r["ROW_S1"], r["ROW_VALUE"], r["ROW_S3"]))
    json.dump(out, open(os.path.join(HERE, "RESCORE.json"), "w"), indent=1)
    print("\nwrote RESCORE.json")


if __name__ == "__main__":
    main()
