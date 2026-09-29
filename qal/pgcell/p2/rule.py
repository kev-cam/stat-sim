#!/usr/bin/env python3
"""PHASE 2 (d) -- derive the RESTORATION RULE from Phase 1's MEASURED chain data.

The rule is read off qal/pgcell/CHAIN_*.json, which are the tank-fed, per-bank
matched-tank, chain-legal-cut measurements.  Nothing here is theory: the two
budgets below are arithmetic on measured per-bank separations and per-bank
value-correctness flags.

  N_SEP  the SEPARATION budget.  How many consecutive pass-gate levels a signal
         can traverse before min(HIGH) - max(LOW) falls below the corrected
         6.44 mV 1-sigma trip floor, given the measured per-bank transfer ratios
         and a full inverter-bank head separation.

  N_VAL  the VALUE budget.  How many pass-gate levels actually occur before the
         FIRST bank in the measured chain returns a wrong value (all_correct
         False).  This is the binding rule -- a bank can be above the floor and
         still be wrong, and in ALT_vhi bank 2 it is.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
FLOOR = 6.44                       # mV, qal/vtaudit corrected 1-sigma trip floor


def load(tag):
    return json.load(open(os.path.join(P1, "CHAIN_%s.json" % tag)))


res = {"_doc": __doc__, "floor_mV": FLOOR, "source": "qal/pgcell/CHAIN_*.json",
       "chains": {}}

for tag in ("CTL_vhi", "ALT_vhi", "ALT_rail", "ALLTG_vhi"):
    d = load(tag)
    banks = [d["banks"][str(i)] for i in range(1, d["H"] + 1)]
    sep = [b["separation_mV"] for b in banks]
    kind = [b["kind"] for b in banks]
    ok = [b["all_correct"] for b in banks]
    ratio = [None] + [sep[i] / sep[i - 1] for i in range(1, len(sep))]
    # how many pass-gate levels had been traversed when the first wrong bank
    # appeared (counting the wrong bank itself as not-yet-delivered)
    n_tg_before_first_wrong = None
    ntg = 0
    for i, (k, o) in enumerate(zip(kind, ok)):
        if not o:
            n_tg_before_first_wrong = ntg
            break
        if k == "tg":
            ntg += 1
    res["chains"][tag] = {
        "comp": kind, "separation_mV": sep, "all_correct": ok,
        "x_floor": [round(s / FLOOR, 2) for s in sep],
        "bank_transfer_ratio": [None if r is None else round(r, 5) for r in ratio],
        "tg_bank_transfer_ratio": [round(ratio[i], 5) for i in range(1, len(sep))
                                   if kind[i] == "tg"],
        "inv_bank_transfer_ratio": [round(ratio[i], 5) for i in range(1, len(sep))
                                    if kind[i] == "inv"],
        "n_TG_levels_delivered_correct_before_first_wrong_bank":
            n_tg_before_first_wrong,
        "VALUE_CHECK": d["VALUE_CHECK"],
    }

# ---------------------------------------------------------------- N_SEP
# One (inv, tg) PAIR is the repeating unit of the measured ALT arrangement:
# an inverter-class bank followed by a pass-gate bank.  Its measured pair-to-pair
# separation transfer is sep(tg bank 4) / sep(tg bank 2).
pair = {}
for tag in ("ALT_vhi", "ALT_rail"):
    s = res["chains"][tag]["separation_mV"]
    pair[tag] = s[3] / s[1]                 # tg@4 / tg@2, one full (inv,tg) pair
head = res["chains"]["CTL_vhi"]["separation_mV"][0]      # 706.56 mV, a full
#                                                         inverter-bank head
budget = {}
for tag, r in pair.items():
    # sep after n pairs = head * r**n ; solve head * r**n >= FLOOR
    budget[tag] = math.log(FLOOR / head) / math.log(r)
N_SEP = int(math.floor(min(budget.values())))

# ---------------------------------------------------------------- N_VAL
val = {t: res["chains"][t]["n_TG_levels_delivered_correct_before_first_wrong_bank"]
       for t in ("ALT_vhi", "ALT_rail")}
N_VAL = min(v for v in val.values() if v is not None)

res["N_SEP_derivation"] = {
    "unit": "one (inverter bank, pass-gate bank) PAIR, the repeating unit of the "
            "measured ALT arrangement",
    "head_separation_mV": head,
    "head_source": "CTL_vhi bank 1 -- a full inverter-bank separation, the best "
                   "the tank-fed arrangement delivers",
    "pair_transfer_ratio_MEASURED": {k: round(v, 5) for k, v in pair.items()},
    "pairs_to_floor": {k: round(v, 3) for k, v in budget.items()},
    "N_SEP": N_SEP,
    "meaning": "at most %d consecutive pass-gate levels before the separation "
               "reaches the 6.44 mV 1-sigma floor" % N_SEP,
}
res["N_VAL_derivation"] = {
    "n_TG_levels_delivered_correct": val,
    "N_VAL": N_VAL,
    "meaning": "the measured chains deliver %d pass-gate level(s) with every gate "
               "value-correct; the next bank is wrong. ALT_vhi (fixed well) "
               "delivers %s, ALT_rail delivers %s."
               % (N_VAL, val["ALT_vhi"], val["ALT_rail"]),
    "binding": "N_VAL is the BINDING rule: ALT_vhi bank 2 is a pass-gate bank at "
               "8.6x the floor -- above it -- and still all_correct False. Being "
               "above the noise floor is necessary, not sufficient.",
}
res["N_SEP"] = N_SEP
res["N_VAL"] = N_VAL
res["UNSATISFIABLE_NOTE"] = (
    "N_VAL = %d. A pass-gate remap necessarily contains at least one pass-gate "
    "level, so a budget of 0 would be unsatisfiable by any pass-gate mapping. "
    "The fixed-well (vhi) chain measures 0 and is therefore CLOSED to pass-gate "
    "logic in this arrangement; the rail-well chain measures 1 and admits a "
    "remap in which NO pass-gate cell ever drives another pass-gate cell."
    % N_VAL)

json.dump(res, open(os.path.join(OUT, "RESTORE_RULE.json"), "w"), indent=1)
for t, c in res["chains"].items():
    print("%-10s %-24s sep %s" % (t, "/".join(c["comp"]),
                                  " ".join("%8.2f" % x for x in c["separation_mV"])))
    print("%-10s %-24s ok  %s  ratio %s" % ("", "",
          " ".join("%8s" % x for x in c["all_correct"]),
          " ".join("%s" % x for x in c["bank_transfer_ratio"])))
print()
print("N_SEP =", N_SEP, res["N_SEP_derivation"]["pairs_to_floor"])
print("N_VAL =", N_VAL, val)
