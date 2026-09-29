#!/bin/bash
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/muxbuck_sk/vae_cache_sk
cd /usr/local/src/stat-sim/qal/muxbuck_sk
for d in sk_mx_p2_q16 sk_mx_p2_qe16; do Xyce $d.cir > $d.log 2>&1; echo "done $d $(date +%T)"; done
echo ALLDONE
