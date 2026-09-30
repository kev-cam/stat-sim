#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize
BTPAT='{"1":[0,0,0,1,0,1,1,0],"2":[1,1,1,0,1,0,0,1],"3":[0,0,0,1,0,1,1,0],"4":[1,1,1,0,1,0,0,1]}'
RVPAT='{"1":[0,1,0,1,0,1,0,1],"2":[1,0,1,0,1,0,1,0],"3":[0,1,0,1,0,1,0,1],"4":[1,0,1,0,1,0,1,0],"5":[0,1,0,1,0,1,0,1],"6":[1,0,1,0,1,0,1,0]}'
echo "analyze start $(date +%H:%M:%S)" > analyze.log

while ! grep -q "ALL BT" bt_mc.done 2>/dev/null; do sleep 15; done
python3 score.py --tag banktank_T200_H4_base --decks bt_mc_2001.cir bt_mc_2002.cir bt_mc_2003.cir \
  --links '[[1,2],[2,3],[3,4]]' --pattern "$BTPAT" --out RES_bt_base.json >> analyze.log 2>&1
echo "BT scored $(date +%H:%M:%S)" >> analyze.log

while ! grep -q "ALL RV" rv_mc.done 2>/dev/null; do sleep 15; done
python3 score.py --tag resv_res20_K6 --decks rv_mc_3001.cir rv_mc_3002.cir rv_mc_3003.cir \
  --links '[[1,2],[2,3],[3,4],[4,5],[5,6]]' --pattern "$RVPAT" --out RES_rv.json >> analyze.log 2>&1
python3 rx6.py --decks rv_mc_3001.cir rv_mc_3002.cir rv_mc_3003.cir --out RES_rv_rx6.json >> analyze.log 2>&1
echo "RV scored $(date +%H:%M:%S)" >> analyze.log

for t in p2_base p2_k4 p2_k8 p2_wx2 p2_wx4 p2_lx2; do
  while ! grep -q "^$t RC=" p2.done 2>/dev/null; do sleep 15; done
  python3 slack.py --tag $t --decks $t.cir --gridspec meas_bt_grid.json \
    --links '[[1,2],[2,3],[3,4]]' --pattern "$BTPAT" --out RES_$t.json >> analyze.log 2>&1
  echo "$t scored $(date +%H:%M:%S)" >> analyze.log
done
echo "ANALYZE COMPLETE" >> analyze.log
