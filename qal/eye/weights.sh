#!/bin/bash
set -u
cd /usr/local/src/stat-sim/qal/eye || exit 1
echo "[$(date +%H:%M:%S)] E5: adding weights 2,3,6,7 (FULL 8-run probe), 3 lanes" >> lanes.log
i=0
for P in W2 W3 W6 W7; do
  ( python3 run_pattern.py "$P" --full > "log_$P.txt" 2>&1; echo "[$(date +%H:%M:%S)] DONE $P rc=$?" >> lanes.log ) &
  i=$((i+1)); if [ $((i % 3)) -eq 0 ]; then wait; fi
done
wait
echo "[$(date +%H:%M:%S)] ALL WEIGHTS DONE" >> lanes.log
