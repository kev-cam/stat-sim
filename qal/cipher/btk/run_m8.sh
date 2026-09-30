#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher
cd /usr/local/src/stat-sim/qal/cipher/btk
python3 micro8.py qal "$1" "$2" 1.65 "$3" > "m8_$2_$1_ct$3.log" 2>&1
echo "EXIT $? qal cw=$1 $2 ct=$3" >> m8_status.txt
