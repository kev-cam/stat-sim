#!/bin/bash
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/muxbuck_sk/vae_cache_sk
cd /usr/local/src/stat-sim/qal/muxbuck_sk
for d in sk_mx_c1 sk_mx_c16 sk_mx_e1 sk_mx_e16 sk_mx_w16h sk_mx_w16d sk_mx_p2_c16 sk_mx_p2_e16; do
  Xyce $d.cir > $d.log 2>&1
  echo "done $d $(date +%T)"
done
