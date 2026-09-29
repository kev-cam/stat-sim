#!/bin/bash
# TRACK A (c) -- the CA_MULT sweep, at the ALU's real 6.91 fF sink load and the
# committed level-optimal inductor (L = 4 nH, W = 30 um, dV = 1.65 V).
# CA_MULT = 1 is the committed control and is run as the instrument check (I2).
# 3 concurrent heavy jobs (another workflow shares this 16-core box).
cd /usr/local/src/stat-sim/qal/resv || exit 1
run() { python3 rv.py pt "$1" "$2" "$3" "$4" "$5" 500 inv 6.91 > "log_$1.txt" 2>&1; echo "done $1"; }
export -f run
printf '%s\n' \
  "m2    4 30 1.65 2" \
  "m5    4 30 1.65 5" \
  "m10   4 30 1.65 10" \
  "m20   4 30 1.65 20" \
  "m1000 4 30 1.65 1000" \
| xargs -P 3 -I{} bash -c 'run $0' "{}"
