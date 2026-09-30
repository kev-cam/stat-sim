#!/bin/bash
# Run patterns in LANES of at most 3 concurrent heavy Xyce jobs (SIM DISCIPLINE:
# the box was at load ~11-23 with 14-20 other Xyce when this study started).
# Each pattern is serial internally (the true-ZCS probe protocol is sequential:
# bank k's zero is measured with banks 1..k-1 cut at THEIR measured zeros).
cd /usr/local/src/stat-sim/qal/eye || exit 1
LANES=3
i=0
for P in "$@"; do
  ( python3 run_pattern.py "$P" > "log_$P.txt" 2>&1; echo "DONE $P rc=$?" >> lanes.log ) &
  i=$((i+1))
  if [ $((i % LANES)) -eq 0 ]; then wait; fi
done
wait
echo "ALL DONE" >> lanes.log
