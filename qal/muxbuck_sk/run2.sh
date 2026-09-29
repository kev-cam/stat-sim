#!/bin/bash
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/muxbuck_sk/vae_cache_sk
cd /usr/local/src/stat-sim/qal/muxbuck_sk
for d in sk_mx_q1 sk_mx_q4 sk_mx_q16 sk_mx_qe1 sk_mx_qe4 sk_mx_qe16 sk_droop8 sk_droop8_r32; do
  Xyce $d.cir > $d.log 2>&1
  echo "done $d $(date +%T)"
done
