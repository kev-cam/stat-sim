#!/bin/bash
# THE BEAT PERIOD, measured directly: sweep T at the maximum workable k.
set -e
cd /usr/local/src/stat-sim/qal/restore5
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_restore5
export MAXPAR=4
exec python3 go.py "$@"
