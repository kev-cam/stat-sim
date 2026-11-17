#!/bin/bash
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher
cd /usr/local/src/stat-sim/qal/cipher/btk
python3 micro8.py cmos "$1" "$2" > "m8c_$1_$2.log" 2>&1
echo "EXIT $? cmos cw=$1 vdd=$2" >> m8c_status.txt

# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
