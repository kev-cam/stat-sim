#!/bin/bash
# Archive the v1 (pre-AMENDMENT-A4, standard-receiver) run as evidence, then re-run
# every configuration under the A4 skewed receiver.
set -e
cd /usr/local/src/stat-sim/qal/restore5
mkdir -p v1_standard_receiver
cp rows.json v1_standard_receiver/rows_v1_standard_receiver.json 2>/dev/null || true
for f in c_k*_T300.cir s_k*_T300.cir p*_k*_T300.cir; do
  [ -e "$f" ] || continue
  mv "$f" v1_standard_receiver/ 2>/dev/null || true
  [ -e "$f.mt0" ] && mv "$f.mt0" v1_standard_receiver/ 2>/dev/null || true
  [ -e "$f.prn" ] && mv "$f.prn" v1_standard_receiver/ 2>/dev/null || true
done
mv rows.json v1_standard_receiver/rows_v1_raw.json 2>/dev/null || true
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_restore5
export MAXPAR=4
exec python3 go.py 6,300 3,300 2,300 1,300
