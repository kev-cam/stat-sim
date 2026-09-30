#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize
export PYMS_DIR=/usr/local/share/xyce/PyMS PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize/vae_cache
export PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize/pyms_shell PYMS_CALLBACK_PARAMS=DELVTO
for s in 3001 3002 3003; do
 ( S=$(date +%s); /usr/local/src/xyce-build/src/Xyce rv_mc_$s.cir > rv_mc_$s.log 2>&1
   echo "seed=$s RC=$? WALL=$(( $(date +%s) - S ))s" >> rv_mc.done ) &
done
wait; echo "ALL RV CHUNKS COMPLETE" >> rv_mc.done
