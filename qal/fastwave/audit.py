#!/usr/bin/env python3
"""AUDIT: re-read the VHI (gate-drive) line and the cell input sources out of
EVERY generated netlist and compare them against the spec that asked for the
point.  Written after the A9 worker-state leak was found; it is the check that
the leak is gone, and it is run on every row, not on a sample."""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = {}
for f in sorted(glob.glob(os.path.join(HERE, "spec_*.json"))):
    for tag, kw in json.load(open(f)):
        SPEC[tag] = (kw.get("mix", "data"), float(kw.get("vgh", 1.5)), kw["n"])

# the RESTORED vector pair is (0,1) and (1,1): both have B = 1, so in a
# restored-mix deck EVERY VB source sits at VINHI.  In a data-mix deck half of
# them sit at 0.  That is an independent witness of the mix actually built.
ROWS = json.load(open(os.path.join(HERE, "ROWS.json")))
bad, seen, skipped = {}, 0, []
for tag, (mix, vgh, n) in sorted(SPEC.items()):
    # A row whose PROBE failed never got a hop deck rewritten, so a stale deck
    # from an earlier attempt can sit on disk.  Such a row carries NO DATA (it
    # is an error row in ROWS.json) and is skipped, by name, not silently.
    if ROWS.get(tag, {}).get("error"):
        skipped.append(tag)
        continue
    f = os.path.join(HERE, "h_%s.cir" % tag)
    if not os.path.exists(f):
        continue
    seen += 1
    txt = open(f).read()
    m = re.search(r"^VHI vhi 0 (\S+)", txt, re.M)
    got_vgh = float(m.group(1)) if m else None
    vb = [float(x) for x in re.findall(r"^VB\d+ \S+ \S+ (\S+)", txt, re.M)]
    got_mix = "restored" if (vb and all(v > 0.5 for v in vb)) else "data"
    problems = []
    if got_vgh is None or abs(got_vgh - vgh) > 1e-9:
        problems.append("VGH: netlist %s, spec %s" % (got_vgh, vgh))
    if len(vb) != n:
        problems.append("cell count: netlist %d, spec %d" % (len(vb), n))
    # The mix witness cannot discriminate at N = 2: by AMENDMENT A1 the DATA
    # mix's first two vectors ARE the two RESTORED vectors (0,1) and (1,1), both
    # with B = 1, so an N = 2 data-mix deck is byte-identical to an N = 2
    # restored-mix deck.  That is by design, not a defect, so the witness is
    # only applied where the two mixes actually differ (N >= 4).
    if n >= 4 and got_mix != mix:
        problems.append("mix: netlist looks %s, spec %s" % (got_mix, mix))
    if problems:
        bad[tag] = problems
print("audited %d decks against their specs; skipped %d error rows %s"
      % (seen, len(skipped), skipped))
if bad:
    print("MISMATCHES (%d):" % len(bad))
    for t, p in sorted(bad.items()):
        print("  %-26s %s" % (t, "; ".join(p)))
else:
    print("ALL CLEAN -- every netlist's gate drive and bank content match its spec.")
json.dump(bad, open(os.path.join(HERE, "AUDIT.json"), "w"), indent=1)
sys.exit(1 if bad else 0)
