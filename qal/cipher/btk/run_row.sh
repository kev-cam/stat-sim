#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher
cd /usr/local/src/stat-sim/qal/cipher/btk
# args: cw wire_mode ct_mode rw zerosfile
python3 btw.py row 10 150 4 1.65 free "$1" "$2" "$3" "$4" "$5" > "row_$2_$3_$1.log" 2>&1
rc=$?
if [ $rc = 0 ]; then python3 wext.py 10 150 4 1.65 free "$1" "$2" "$3" "$5" >> "row_$2_$3_$1.log" 2>&1; rc=$?; fi
echo "EXIT $rc cw=$1 $2 $3" >> row_status.txt
