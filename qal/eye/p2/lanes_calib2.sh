#!/bin/bash
cd /usr/local/src/stat-sim/qal/eye/p2 || exit 1
while read -r mode T H _; do
  [ -z "$mode" ] && continue
  echo "[$(date +%T)] launch calib T=$T"
  python3 p2run.py calib "$T" "$H" > "log_calib_T${T}.txt" 2>&1 &
done < "$1"
wait
echo "[$(date +%T)] CALIB2 COMPLETE"
