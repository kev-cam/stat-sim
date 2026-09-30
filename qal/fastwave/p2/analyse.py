"""p2 stage 4 -- assemble RESULTS.json.  Reads ROWS.json, CBANK_INSITU.json and
INSTRUMENT_CHECK.json; adds nothing that is not already measured."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W
import comp

HERE = W.HERE
PH1 = json.load(open(os.path.join(W.P1, "RESULTS.json")))


def load(name):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else {}


def key(r):
    return (r.get("wire"), r.get("l_nh"), r.get("vgh"), r.get("m"), r.get("T_ps"))


def prim(rows, wire="W2", l_nh=15.0, vgh=2.4, m=10.0):
    out = [r for r in rows.values() if not r.get("FAILED")
           and r.get("wire") == wire and r.get("l_nh") == l_nh
           and abs(r.get("vgh", 0) - vgh) < 1e-9 and r.get("m") == m]
    return sorted(out, key=lambda r: r["T_ps"])


def sep_by_depth(r):
    o = {}
    for k in range(1, r["nscore"] + 1):
        b = r["banks"][str(k)] if str(k) in r["banks"] else r["banks"][k]
        o["bank%d" % k] = dict(
            min_margin_mV=b["min_margin_mV"],
            sigma_multiples=b["min_margin_mV"] / W.SIG_MV,
            rail_at_bound_V=b["rail_at_bound_V"],
            per_cell_margin_mV=[c["margin_mV"] for c in b["cells"]],
            per_cell_path=[c["path"] for c in b["cells"]])
    ms = [o["bank%d" % k]["min_margin_mV"] for k in range(1, r["nscore"] + 1)]
    o["_min_over_depth_mV"] = min(ms)
    o["_min_over_depth_sigma"] = min(ms) / W.SIG_MV
    o["_floor_note"] = ("the 1-sigma floor is 6.441 mV (qal/vtaudit/AUDIT.md), "
                        "itself a LOWER bound because dw/dl is excluded, so every "
                        "sigma multiple quoted here inherits lower-bound status")
    return o


def settling_by_depth(r):
    o = {}
    for k in range(1, r["nbank"] + 1):
        b = r["banks"].get(str(k)) or r["banks"][k]
        o["bank%d" % k] = dict(
            scored=b["scored"], paths=b["paths"], forms=b["forms"],
            want=b["want"], rail_peak_V=b["rail_peak_V"],
            rail_at_bound_V=b["rail_at_bound_V"],
            commit_ps=b["commit_ps"], bar90_ps=b["bar90_ps"],
            value_all_correct=b["value_all_correct"],
            value_fails=b["value_fails"], value_fail_paths=b["value_fail_paths"],
            K2_all_ok=b["K2_all_ok"], K2_fails=b["K2_fails"],
            per_cell=[dict(cell=c["cell"], path=c["path"], form=c["form"],
                           want=c["want"], V=c["V"],
                           trip=c["trip_at_own_rail"],
                           margin_mV=c["margin_mV"], correct=c["correct"],
                           settled_pct=c["settled_pct_of_own_rail"],
                           K2_floor_ok=c["K2_floor_ok"]) for c in b["cells"]])
    return o


def build(rows, cb, ic):
    R = {}
    R["_what"] = (
        "PHASE 2 of the qal/fastwave run: a SEVEN-BANK TG-XOR QAL wave (six "
        "scored) at the Phase-1 optimum, per-bank tanks, chain-legal source-side "
        "ZCS cuts, dV = 1.65 V, WITH explicit rotate interconnect -- the first "
        "deck in this campaign to carry any interconnect at all.  Objective: the "
        "SUSTAINED BEAT, measured as a difference of two waveform instants, never "
        "composed and never the scheduled T.")
    R["_labels"] = (
        "MEASURED = read off a waveform or a .measure in qal/fastwave/p2.  "
        "DERIVED = arithmetic over MEASURED terms.  ASSUMED = neither, and named.  "
        "BOOKING = modelled as an ideal source; its row is a BOUND.")
    R["A_INSTRUMENT"] = ic
    R["A_INSTRUMENT"]["C_bank_reproduction"] = cb.get("INSTRUMENT_CHECK")
    R["B_THE_INTERCONNECT_AND_THE_IN_SITU_BANK"] = {
        "_method": cb.get("_METHOD"),
        "per_wire": {wr: {k: v for k, v in cb[wr].items()}
                     for wr in ("W2", "W0", "W1", "WL") if wr in cb},
        "phase1_bare_N4_bank_fF": 52.76786735757576,
        "READING": None,
    }
    return R
