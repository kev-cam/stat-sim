#!/bin/bash
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_skrecov
mkdir -p $PYMS_VAE_CACHE
cd /usr/local/src/stat-sim/qal/recov/skeptic
for d in "$@"; do
  echo "=== START $d $(date +%T) ==="
  S=$(date +%s)
  /usr/local/src/xyce-build/src/Xyce $d.cir > $d.log 2>&1
  RC=$?
  echo "=== LANEDONE $d $(date +%T) rc=$RC wall=$(( $(date +%s) - S ))s ==="
done
echo "=== ALL LANES DONE ==="

# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
