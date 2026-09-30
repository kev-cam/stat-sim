#!/bin/bash
# Phase 2 in two waves of 3, to hold the <=3-concurrent-heavy-jobs discipline.
# Wave A reuses the already-built PyMS .so (geometry unchanged); wave B must build.
cd /usr/local/src/stat-sim/qal/mcsize
export PYMS_DIR=/usr/local/share/xyce/PyMS PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize/vae_cache
export PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize/pyms_shell PYMS_CALLBACK_PARAMS=DELVTO
run() { S=$(date +%s); /usr/local/src/xyce-build/src/Xyce $1.cir > $1.log 2>&1
        echo "$1 RC=$? WALL=$(( $(date +%s) - S ))s" >> p2.done; }
for t in $WAVE; do run $t & done
wait
echo "WAVE DONE: $WAVE" >> p2.done
