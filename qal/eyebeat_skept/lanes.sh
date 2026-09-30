#!/bin/bash
# SKEPTIC lanes: 3-wide batches (box shared with other campaign runs).
cd /usr/local/src/stat-sim/qal/eyebeat_skept
set -u
run3 () {  # run3 T : three patterns in parallel at beat T
  local T=$1
  for P in P0 P1 P2; do
    python3 sk.py lane "$T" "$P" > "log_T${T}_${P}.txt" 2>&1 &
  done
  wait
  echo "=== T=$T lanes done $(date +%H:%M:%S) ==="
  grep -h "A6 PASS\|A6-FAIL\|ROW FAILED\|TIMEOUT\|XYCE FAIL" log_T${T}_P*.txt | tail -6
}
run3 150
run3 300
run3 60
echo ALL_MAIN_LANES_DONE
