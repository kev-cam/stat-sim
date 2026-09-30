#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize/vae_cache
export PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize/pyms_shell
export PYMS_CALLBACK_PARAMS=DELVTO
for s in 2001 2002 2003; do
  ( S=$(date +%s); /usr/local/src/xyce-build/src/Xyce bt_mc_$s.cir > bt_mc_$s.log 2>&1
    echo "seed=$s RC=$? WALL=$(( $(date +%s) - S ))s" >> bt_mc.done ) &
done
wait
echo "ALL BT CHUNKS COMPLETE" >> bt_mc.done
