#!/bin/bash
set -u
cd /usr/local/src/stat-sim/qal/eye || exit 1
echo "[$(date +%H:%M:%S)] E2-followthrough: FULL 8-run re-probe of P1..P5, 3 lanes" >> lanes.log
i=0
for P in P1 P2 P3 P4 P5; do
  ( python3 run_pattern.py "$P" --full > "log_${P}_full.txt" 2>&1; echo "[$(date +%H:%M:%S)] FULL DONE $P rc=$?" >> lanes.log ) &
  i=$((i+1))
  if [ $((i % 3)) -eq 0 ]; then wait; fi
done
wait
echo "[$(date +%H:%M:%S)] ALL FULL REPROBES DONE" >> lanes.log
