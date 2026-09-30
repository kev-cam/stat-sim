#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_SKEPT
cd /usr/local/src/stat-sim/qal/banktank_skept
python3 bt.py probeT 10 1.2 $1 4 > log_probeT_$1.txt 2>&1
echo "PROBE $1 rc=$?"
