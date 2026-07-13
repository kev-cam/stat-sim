#!/bin/bash
# Simulation-driven EM screen of the real IHP 30mA output pad, via Xyce (WSL).
# Absolute cd -> immune to the harness's stale-cwd on backgrounding. ONE Xyce
# transient (heatmap writes SVG+CSV); the alert summary is derived from the CSV.
cd /usr/local/src/stat-sim || exit 1
# .sim.spef = same nets, realistic simulation R; --geom keeps the EM widths.
A="test/iopad30_ihp.sim.spef --geom test/iopad30_ihp.em.spef.json --em-rules rules/ihp_sg13g2.em.json"
A="$A --sim xyce --harness test/iopad30_ihp.harness.sp"
R=test/iopad30_ihp.xyce.report
: > "$R"
echo "== xyce transient -> heatmap + csv ==" >> "$R"
# the built-in -o SVG is a rough per-net line sketch (mangles real multi-shape nets)
# -> throwaway; the CSV is the product (feeds klayout2spef --em-layout, the real map).
python3 hotspot.py heatmap $A -o /tmp/iopad30_raw.svg --csv test/iopad30_ihp.xyce.csv >> "$R" 2>&1
echo "heatmap rc=$?" >> "$R"
python3 - >> "$R" 2>&1 <<'PY'
import csv
rows=list(csv.DictReader(open("test/iopad30_ihp.xyce.csv")))
rows.sort(key=lambda r: float(r["worst"]), reverse=True)
over=[r for r in rows if float(r["worst"])>1.0]
print(f"\n=== SIMULATED EM screen (Xyce transient): {len(over)}/{len(rows)} segments over IHP limit ===")
print(f"{'segment':<16}{'layer':<10}{'geo':>8}{'I_avg':>11}{'Imax_avg':>11}{'worst':>8}")
for r in rows[:14]:
    geo = f"{r['cuts']}cut" if r['is_via']=='1' else f"{float(r['width_um']):g}um"
    print(f"{r['net']+':'+r['seg']:<16}{r['layer']:<10}{geo:>8}"
          f"{float(r['I_avg']):>11.3e}{float(r['Imax_avg']):>11.3e}{float(r['worst']):>8.2f}")
PY
echo "ALLDONE" >> "$R"
rm -rf /tmp/hs_xyce_* 2>/dev/null
