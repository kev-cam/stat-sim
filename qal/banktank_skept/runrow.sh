#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_SKEPT
cd /usr/local/src/stat-sim/qal/banktank_skept
python3 bt.py row 10 $1 4 1.2 free $2 > log_row_$1.txt 2>&1
echo "ROW $1 rc=$?"
