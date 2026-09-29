#!/usr/bin/env python3
"""SKEPT: measure the top-up coupling step at a LOGIC node IN THE DECK BEING
SCORED, single-deck excursion method, and VALIDATE the method against the
committed tankfed free-vs-clamp differential (249.0 / 31.1 mV)."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sklib

QAL = "/usr/local/src/stat-sim/qal"

def excursion(w, col, ta, tb, tail=0.0):
    """max |V(t) - V(ta)| over [ta, tb+tail]  -- the step the node actually sees."""
    t, y = w.win(col, ta, (tb if tb else t[-1]) + tail)
    if len(t) < 2:
        return None, None
    v0 = w.at(col, ta)
    j = int(np.argmax(np.abs(y - v0)))
    return float(abs(y[j] - v0) * 1e3), float(t[j])

def scan(cir, prn, feeder_of, gates_of, tail):
    w = sklib.W(prn)
    wins = sklib.topup_windows(cir)
    out = []
    for (k, ta, tb) in wins:
        kf = feeder_of(k)
        if kf is None:
            continue
        rec = dict(topped_bank=k, feeder=kf, win=[ta, tb], per_gate={})
        best = (0.0, None, None)
        for i in gates_of(kf):
            col = "V(O%d_%d)" % (kf, i)
            if not w.has(col):
                continue
            st, tj = excursion(w, col, ta, tb, tail)
            if st is None:
                continue
            rec["per_gate"]["o%d_%d" % (kf, i)] = round(st, 3)
            if st > best[0]:
                best = (st, "o%d_%d" % (kf, i), tj)
        rec["step_at_logic_mV"] = round(best[0], 3)
        rec["step_gate"] = best[1]
        rec["step_at_ps"] = best[2]
        out.append(rec)
    return out

R = {}

# ---------- (1) VALIDATE the single-deck method on tankfed's own clamp decks
R["_method_validation_tankfed"] = {}
for tag, deck, ref in (
        ("matched_m2", "r_bank_matched_m2_clamp_T340_dv1200", 248.997),
        ("uniform_m6", "r_bank_uniform_m6_clamp_T340_dv1200", 31.411)):
    cir = os.path.join(QAL, "tankfed", deck + ".cir")
    prn = cir + ".prn"
    if not os.path.exists(prn):
        R["_method_validation_tankfed"][tag] = "prn missing"
        continue
    got = scan(cir, prn, lambda k: k - 1, lambda kf: range(0, 60), tail=24.0)
    R["_method_validation_tankfed"][tag] = dict(
        committed_step_at_logic_mV=ref, my_windows=got)

# ---------- (2) chain3's OWN coupling step, in its own topology
R["chain3_own_coupling"] = {}
import glob
modes = {k: v.get("mode") for k, v in
         json.load(open(os.path.join(QAL, "chain3", "ROWS_full.json"))).items()}
for cir in sorted(glob.glob(os.path.join(QAL, "chain3", "c_*.cir"))):
    b = os.path.basename(cir)[:-4]
    if modes.get(b[2:]) != "topup":
        continue
    prn = cir + ".prn"
    if not os.path.exists(prn):
        continue
    got = scan(cir, prn, lambda k: k - 1, lambda kf: range(0, 8), tail=20.0)
    ck = sklib.deck_checkpoints(cir)
    R["chain3_own_coupling"][b] = dict(windows=got, committed_checkpoints=ck)

json.dump(R, open("COUPLING_SKEPT.json", "w"), indent=1)
# ---- report
print("=== METHOD VALIDATION (single-deck excursion vs committed differential) ===")
for tag, v in R["_method_validation_tankfed"].items():
    if isinstance(v, str):
        print(tag, v); continue
    print(tag, "committed:", v["committed_step_at_logic_mV"])
    for wd in v["my_windows"]:
        print("   bank%d feeder%d win=%s  mine=%.3f mV at %s (%s ps)"
              % (wd["topped_bank"], wd["feeder"], wd["win"],
                 wd["step_at_logic_mV"], wd["step_gate"], wd["step_at_ps"]))
print()
print("=== chain3 OWN coupling step at a logic node ===")
allst = []
for b, v in sorted(R["chain3_own_coupling"].items()):
    for wd in v["windows"]:
        allst.append(wd["step_at_logic_mV"])
        print("%-16s bank%d feeder%d win=[%.1f,%.1f] step=%8.3f mV  %s @%.1f ps  ck=%s"
              % (b, wd["topped_bank"], wd["feeder"], wd["win"][0], wd["win"][1],
                 wd["step_at_logic_mV"], wd["step_gate"], wd["step_at_ps"] or -1,
                 v["committed_checkpoints"]))
if allst:
    print("\nchain3 own step_at_logic: n=%d  min=%.3f  median=%.3f  MAX=%.3f mV"
          % (len(allst), min(allst), float(np.median(allst)), max(allst)))
