#!/usr/bin/env python3
"""DIAGNOSIS of the one place my fixed-rail cascade and the run's disagree.

Six of the run's eight fixed-rail TG-cascade rows reproduce here to <= 1.4 mV.
Two disagree by ~660-690 mV, and they are exactly the two LOW-polarity rows.

The cause, pinned rather than guessed:
  the run's cascade ties every mux's OFF path to a single IDEAL source at the
  opposite logic level (level.py: `VOFF<tag> off_<tag> 0 <0.0 if hi else v>`).
  For the LOW cascades that source holds a full 0.7138 V from t = 0 -- BEFORE the
  bank rail has ramped at all.  The deselected transmission gate's pMOS gate is
  Sb, which comes from the cell's own rail-powered inverter and is therefore 0 V
  until the rail arrives, so that pMOS is hard ON and drags the output up to the
  off-path source.  The result is a node at 0.84 V on a 0.714 V rail while it is
  supposed to be at 0.

  For the HIGH cascades the same source sits at 0.0 V, which is what a
  rail-powered predecessor also produces before its rail arrives -- so those rows
  carry no artifact, and they match to 0.17 mV.

This run therefore measures BOTH off-path drivers:
  off = IDEAL source at the opposite level  (the run's construction)
  off = a REAL rail-powered inverter        (what a predecessor QAL bank is)
and reports them side by side.  The tank-fed chain is NOT affected: bt.py wires
each TG bank's off path to a real predecessor cell output (only bank 1's comes
from an ideal source), so the chain verdict stands on its own footing."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
mine = json.load(open(os.path.join(HERE, "LEVEL_SKEPT.json")))
run = json.load(open("/usr/local/src/stat-sim/qal/pgcell/LEVEL.json"))

PAIRS = [("tgmvli", "tgcv0ai", "vhi  LOW  ideal-head"),
         ("tgmvhi", "tgcv1ai", "vhi  HIGH ideal-head"),
         ("tgmrli", "tgcr0ai", "rail LOW  ideal-head"),
         ("tgmrhi", "tgcr1ai", "rail HIGH ideal-head"),
         ("tgmvld", "tgcv0ar", "vhi  LOW  real-head"),
         ("tgmvhd", "tgcv1ar", "vhi  HIGH real-head"),
         ("tgmrld", "tgcr0ar", "rail LOW  real-head"),
         ("tgmrhd", "tgcr1ar", "rail HIGH real-head")]

OUT = {"_doc": __doc__, "rows": {}}
for rk, mk, lab in PAIRS:
    r = [x["loss_ckpt_mV"] for x in run[rk]["by_depth"]]
    rok = [x["correct_ckpt"] for x in run[rk]["by_depth"]]
    m = mine[mk]["loss_ckpt_by_depth_mV"]
    OUT["rows"][lab] = dict(
        run_loss_ckpt_mV=[round(x, 3) for x in r],
        run_correct=rok,
        mine_loss_ckpt_mV=[round(x, 3) for x in m],
        mine_correct=[x["correct"] for x in mine[mk]["by_depth"]],
        max_abs_diff_mV=round(max(abs(a - b) for a, b in zip(r, m)), 3),
        run_off_path=("IDEAL source held at 0.7138 V from t=0, i.e. a full logic "
                      "HIGH before the bank rail exists"
                      if "LOW" in lab else
                      "IDEAL source at 0 V -- same as a rail-powered driver "
                      "before its rail arrives, so NO artifact"),
        mine_off_path=("a REAL rail-powered inverter" if "real-head" in lab
                       else "IDEAL source at the opposite level (as the run)"))
# my own clean rows: off path tied to the ON path (no contention at all)
for mk, lab in (("tgcv0bi", "vhi  LOW  benign-off"), ("tgcv1bi", "vhi  HIGH benign-off"),
                ("tgcr0bi", "rail LOW  benign-off"), ("tgcr1bi", "rail HIGH benign-off")):
    OUT["rows"][lab] = dict(mine_loss_ckpt_mV=[round(x, 3) for x in
                                               mine[mk]["loss_ckpt_by_depth_mV"]],
                            mine_correct=[x["correct"] for x in mine[mk]["by_depth"]],
                            mine_off_path="tied to the ON path: no data contention",
                            run_loss_ckpt_mV=None)
OUT["instrument_t90_ps"] = mine.get("_instr_inv1p2_t90_ps")
json.dump(OUT, open(os.path.join(HERE, "OFFPATH.json"), "w"), indent=1)
print("%-24s %-38s %-38s %s" % ("row", "run loss@ckpt (mV)", "mine loss@ckpt (mV)", "maxdiff"))
for lab, d in OUT["rows"].items():
    print("%-24s %-38s %-38s %s"
          % (lab,
             str([round(x, 1) for x in d["run_loss_ckpt_mV"]]) if d["run_loss_ckpt_mV"] else "-",
             str([round(x, 1) for x in d["mine_loss_ckpt_mV"]]),
             d.get("max_abs_diff_mV", "-")))
print("wrote OFFPATH.json")
