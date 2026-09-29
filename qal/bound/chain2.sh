#!/bin/bash
# runs after chain.sh: the expanded receiver deck, then the capacitive-tax CLOAD sweep.
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_boundT3
cd /usr/local/src/stat-sim/qal/bound
while pgrep -f 'Xyce bd_' >/dev/null 2>&1 || pgrep -f 'Xyce sw_' >/dev/null 2>&1; do sleep 5; done
echo "=== START bd_rx2 $(date +%T) ==="
S=$(date +%s); /usr/local/src/xyce-build/src/Xyce bd_rx2.cir > bd_rx2.log 2>&1
echo "=== DONE bd_rx2 $(date +%T) rc=$? wall=$(( $(date +%s)-S ))s ==="
echo "=== START captax $(date +%T) ==="
python3 -u bd_s2q.py 1.0:4.0 1.0:8.0 > captax_drive.log 2>&1
echo "=== DONE captax $(date +%T) rc=$? ==="
echo "=== CHAIN2 DONE ==="
