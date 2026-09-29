#!/bin/bash
cd /usr/local/src/stat-sim/qal/buckskep
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/buckskep/vae_cache_skep
# wait for PR_C9 to finish
while pgrep -f "Xyce PR_C9.cir" > /dev/null 2>&1; do sleep 15; done
# stop the rest of the old queue so nothing runs concurrently
for p in $(pgrep -f "drive.sh"); do kill -9 $p 2>/dev/null; done
sleep 2
for p in $(ps -eo pid,args | grep "xyce-build/src/Xyce" | grep -E "IC_C9|K1_buck_L1|K1_nofw_L1|K1_buck_L40|K1_nofw_L40" | grep -v grep | awk '{print $1}'); do kill -9 $p 2>/dev/null; done
sleep 2
for d in K2_fwlate_L10_T40 IC_C9; do
  [ -f "$d.cir.mt0" ] && continue
  echo "$d START" >> k2.status
  /usr/local/src/xyce-build/src/Xyce $d.cir > $d.log 2>&1
  echo "$d rc=$? degraded=$(grep -c 'retrying without zero-valued' $d.log)" >> k2.status
done
echo "K2 QUEUE COMPLETE" >> k2.status
