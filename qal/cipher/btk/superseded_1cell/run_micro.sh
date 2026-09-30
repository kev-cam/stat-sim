#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher
cd /usr/local/src/stat-sim/qal/cipher/btk
python3 micro.py qal "$1" "$2" "$3" ${4:+$4} > "micro_qal_$2_$1${4:+_ct$4}.log" 2>&1
echo "EXIT $? qal cw=$1 $2 ct=${4:-def}" >> micro_status.txt
