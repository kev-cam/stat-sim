#!/bin/bash
# Staged, ~3 concurrent heavy Xyce jobs.  Run only with a WARM PyMS cache
# (warm.cir / warm2.cir) -- a cold cache makes every stage pay a ~5 min
# cc1plus per device geometry, redundantly per concurrent process (AMENDMENT A6).
cd /usr/local/src/stat-sim/qal/nmux
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_nmux

echo "=== G2 instrument gate $(date +%T) ==="
python3 -c "
import json, run_cells
r = run_cells.gate_peer()
json.dump({'G2_peer': r}, open('gates.json','w'), indent=1)
print('G2', 'PASS' if r.get('PASS') else 'FAIL', json.dumps(r.get('rel_pct', r))[:300])
"

echo "=== DESIGNS $(date +%T) ==="
python3 run_cells.py designs

echo "=== WIDTHS $(date +%T) ==="
python3 run_cells.py widths

echo "=== STEPCHECK $(date +%T) ==="
python3 stepcheck.py

echo "=== CONTENTION $(date +%T) ==="
python3 cont.py '{"committed_QAL_high_0.6759":0.6759,"nmos_pass_ceiling_100nA_0.8832":0.8832,"nmos_pass_ceiling_10nA_0.9621":0.9621,"nmos_pass_ceiling_1nA_1.0346":1.0346,"peer_rail_0.755":0.755,"tank_rail_1.326":1.326}'

echo "=== CHAIN $(date +%T) ==="
python3 chain.py 0.6

echo "=== ASSEMBLE $(date +%T) ==="
python3 assemble.py
echo "=== ALL DONE $(date +%T) ==="
