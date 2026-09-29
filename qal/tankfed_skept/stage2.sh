#!/bin/bash
cd /usr/local/src/stat-sim/qal/tankfed_skept
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_tfskept
until grep -q "STAGE1 DONE" stage1.out 2>/dev/null; do sleep 15; done
if ! python3 -c "import json,sys; d=json.load(open('ANCHOR_SKEPT.json')); sys.exit(0 if d['PASS'] else 1)"; then
  echo "=== ANCHORS FAILED -- STOPPING, nothing else reports ==="; exit 1
fi
echo "=== ZEROS $(date +%T) ==="
python3 matrix.py zeros
echo "=== ROWS $(date +%T) ==="
python3 matrix.py rows
echo "=== COUPLING $(date +%T) ==="
python3 cp.py ROWS_SKEPT.json COUPLING_SKEPT.json
echo "=== FIXTURE $(date +%T) ==="
python3 fx.py 479
echo "=== STAGE2 DONE $(date +%T) ==="
