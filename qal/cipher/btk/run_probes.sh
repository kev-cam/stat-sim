#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher
cd /usr/local/src/stat-sim/qal/cipher/btk
python3 btw.py probe 10 1.65 150 4 "$1" "$2" "$3" "$4" 3.6 > "probe_$2_$3_$1.log" 2>&1
echo "EXIT $? cw=$1 $2 $3" >> probe_status.txt
