#!/usr/bin/env python3
"""RE-EXTRACT every row from the .mt0/.prn already on disk -- NO re-simulation.

Each row's MIX and VGH are recovered from the spec files that generated it, so
the per-cell vector set, the TRANSPARENT/RESTORED labelling and the gate-drive
label are the ones the deck was actually built with.  A first version of this
script omitted that and silently re-extracted every row as mix="data",
VGH=1.5 -- caught because the mix-control and gate-drive partitions came back
empty.  The probe zero for each row is read back from the row's own stored
probe metadata; no zero is ever recomputed or reused from elsewhere.
"""
import glob, json, os, sys, fw

HERE = os.path.dirname(os.path.abspath(__file__))

# tag -> (mix, vgh) from every spec this run generated
SPEC = {}
for f in sorted(glob.glob(os.path.join(HERE, "spec_*.json"))):
    for tag, kw in json.load(open(f)):
        SPEC[tag] = (kw.get("mix", "data"), kw.get("vgh", 1.5))

rows = json.load(open(os.path.join(HERE, "ROWS.json")))
out, bad, unspec = {}, {}, []
for tag, r in rows.items():
    if r.get("error"):
        out[tag] = r
        continue
    mt0 = os.path.join(HERE, "h_%s.cir.mt0" % tag)
    prn = os.path.join(HERE, "h_%s.cir.prn" % tag)
    if not (os.path.exists(mt0) and os.path.exists(prn)):
        bad[tag] = "missing deck output"
        out[tag] = r
        continue
    if tag in SPEC:
        fw.MIX, fw.VGH = SPEC[tag]
    else:                      # the one hand-run timing probe, plain defaults
        fw.MIX, fw.VGH = "data", 1.5
        unspec.append(tag)
    try:
        out[tag] = fw.extract(tag, r["N"], r["L_nH"], r["total_um"], r["ca_fF"],
                              r["t_hop_ps"], mt0, prn, r["rs_ohm"],
                              r["tail_ps"], r.get("probe"))
    except Exception as e:                                             # noqa
        bad[tag] = repr(e)
        out[tag] = r
json.dump(out, open(os.path.join(HERE, "ROWS.json"), "w"), indent=1)
from collections import Counter
c = Counter((v.get("mix"), v.get("vgh")) for v in out.values() if not v.get("error"))
print("re-extracted %d rows, %d failed %s, %d not in any spec %s"
      % (len(out) - len(bad), len(bad), bad, len(unspec), unspec))
print("partition (mix, VGH):", dict(c))
