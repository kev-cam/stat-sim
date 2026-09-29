#!/bin/bash
# STRICTLY SERIAL. Concurrent Xyce runs race the PyMS VAE cache and silently
# fall back to a degraded "nonzero-only" model, so exactly one runs at a time.
cd /usr/local/src/stat-sim/qal/buckskep
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/buckskep/vae_cache_skep
XY=/usr/local/src/xyce-build/src/Xyce

for d in K1_buck_L10_T40 K1_nofw_L10_T40 PR_C1 IC_FREE PR_C9 IC_C9 K1_buck_L1_T40 K1_nofw_L1_T40 K1_buck_L40_T40 K1_nofw_L40_T40; do
  [ -f "$d.cir.mt0" ] && { echo "$d SKIP" >> drive.status; continue; }
  echo "$d START" >> drive.status
  $XY $d.cir > $d.log 2>&1
  rc=$?
  deg=$(grep -c "retrying without zero-valued" $d.log 2>/dev/null)
  echo "$d rc=$rc degraded=$deg" >> drive.status
done
echo "DRIVE COMPLETE" >> drive.status
