#!/bin/bash
cd /usr/local/src/stat-sim/qal/tankfed_skept
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_tfskept
# wait for BOTH warm decks (warmchain.sh runs warm2 after warm)
until grep -q "WARM2 DONE" warm2.out 2>/dev/null; do sleep 15; done
echo "=== WARM COMPLETE $(date +%T) ==="
echo "=== ANCHORS ==="
python3 anchor.py
echo "=== CBANK ==="
python3 cb.py
echo "=== STAGE1 DONE $(date +%T) ==="
