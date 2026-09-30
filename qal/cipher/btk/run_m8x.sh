#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher
cd /usr/local/src/stat-sim/qal/cipher/btk
python3 micro8.py qal "$1" "$2" 1.65 "$3" "$4" "$5" > "m8x_$2_$1_L$4_wx$5.log" 2>&1
echo "EXIT $? cw=$1 $2 ct=$3 L=$4 wx=$5" >> m8x_status.txt
