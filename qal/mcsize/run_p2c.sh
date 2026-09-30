#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize
export PYMS_DIR=/usr/local/share/xyce/PyMS PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize/vae_cache
export PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize/pyms_shell PYMS_CALLBACK_PARAMS=DELVTO
BTPAT='{"1":[0,0,0,1,0,1,1,0],"2":[1,1,1,0,1,0,0,1],"3":[0,0,0,1,0,1,1,0],"4":[1,1,1,0,1,0,0,1]}'
while ! grep -q "WAVE DONE: p2_wx2" p2.done 2>/dev/null; do sleep 15; done
for t in p2k8_wx2 p2k8_wx4 p2k8_lx2; do
 ( S=$(date +%s); /usr/local/src/xyce-build/src/Xyce $t.cir > $t.log 2>&1
   echo "$t RC=$? WALL=$(( $(date +%s) - S ))s" >> p2.done ) &
done
wait
echo "WAVE DONE: p2k8 sizing" >> p2.done
for t in p2k8_wx2 p2k8_wx4 p2k8_lx2; do
  python3 slack.py --tag $t --decks $t.cir --gridspec meas_bt_grid.json \
    --links '[[1,2],[2,3],[3,4]]' --pattern "$BTPAT" --out RES_$t.json >> analyze.log 2>&1
  echo "$t scored $(date +%H:%M:%S)" >> analyze.log
done
echo "WAVE C COMPLETE" >> analyze.log
