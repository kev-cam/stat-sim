#!/bin/bash
# qal/mesh3 grid: 12 lanes = {trap,sine} x T_third {70,80,92,105,117,130},
# d = 1..4 inside each lane.  <= 7 concurrent Xyce (box idle, 16 cores).
cd "$(dirname "$0")"
for w in trap sine; do
  for tt in 70 80 92 105 117 130; do
    echo "$w $tt"
  done
done | xargs -P 7 -n 2 sh -c 'python3 mesh3.py lane "$0" "$1" > "log_lane_$0_tt$1.txt" 2>&1; echo "lane $0 $1 done rc=$?"'
echo ALL-LANES-DONE
