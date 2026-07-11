#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Annotate the raw IHP SG13G2 30mA-output-pad extraction for the hot-spot demo.

klayout2spef --pdk ihp-sg13g2 emits connectivity-only nets with generated names
($1, $2, ...). This maps them to their GDS-label roles (obtained by probing the
pad's text labels -- pad/iovdd/iovss/vdd/vss/... -- with l2n.probe_net on clevo)
and writes a 30 mA rated-drive current budget, so `hotspot.py --net-currents`
screens the real geometry against the real IHP DCCURRENTDENSITY limits with no
transient sim. Idempotent-ish: re-running after a fresh extraction re-applies the
same map (klayout's net numbering is deterministic for a fixed GDS+connectivity)."""
import json, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
SPEF = os.path.join(HERE, "iopad30_ihp.em.spef")
GEOM = SPEF + ".json"
CURR = os.path.join(HERE, "iopad30_ihp.currents.json")

# generated net name -> role, from probing sg13g2_IOPadOut30mA GDS text labels
RENAME = {"$1": "pad", "$25": "iovdd", "$14": "iovdd_esd", "$13": "iovss",
          "$2": "iovss_gr", "$26": "vdd", "$27": "vss", "$24": "drv_o_p",
          "$4": "drv_o_n", "$28": "c2p_in", "$3": "guard"}
def ren(n): return RENAME.get(n, n.replace("$", "n"))

gj = json.load(open(GEOM))
for s in gj["segments"]:
    s["net"] = ren(s["net"])
json.dump(gj, open(GEOM, "w"), indent=1)

out = []
for ln in open(SPEF):
    m = re.match(r"^(\*\d+)\s+(\S+)\s*$", ln)        # *NAME_MAP row: "*<id> <net>"
    out.append(f"{m.group(1)} {ren(m.group(2))}\n" if m else ln)   # ren() is idempotent
open(SPEF, "w").writelines(out)

# 30 mA rated-drive budget (avg/DC -- what IHP's LEF specifies). The output net +
# its IO supply/return path carry the full drive; core rails + control carry little.
DRIVE = {"pad": 30e-3, "iovdd": 30e-3, "iovdd_esd": 30e-3, "iovss": 30e-3,
         "iovss_gr": 30e-3, "drv_o_p": 30e-3, "drv_o_n": 30e-3,
         "vdd": 3e-3, "vss": 3e-3, "c2p_in": 0.5e-3, "guard": 1e-3}
json.dump({k: {"avg": v} for k, v in DRIVE.items()}, open(CURR, "w"), indent=1)
print(f"annotated {len(gj['segments'])} segments; renamed nets; wrote {os.path.basename(CURR)}")
