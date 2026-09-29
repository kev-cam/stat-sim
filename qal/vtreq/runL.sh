#!/bin/bash
# EXPLORATORY (amendment A5): re-optimise the inductor at each shifted threshold.
# At DELVTO = 0 the committed grid could not USE small L -- the rail-drain gate
# C2 (VA_open <= 0.1478 V) excluded it.  A stronger switch may re-admit it, and
# t_hop is the one term in the QAL level that no threshold can touch, so this is
# the only lever that can attack the residue.
cd /usr/local/src/stat-sim/qal/vtreq
MAXPAR=${MAXPAR:-4}
n=0
for spec in "d150B 1" "d150B 2" "d200B 0.5" "d200B 1" "d200B 2" \
            "d300B 0.3" "d300B 0.5" "d300B 0.7" "d200P 1" "d200P 2" "d300P 0.5" "d300P 1" "d300P 2"; do
  set -- $spec
  ( python3 drive.py q1L "$1" "$2" > "log_q1L$2_$1.txt" 2>&1 ) &
  n=$((n+1)); [ $((n % MAXPAR)) -eq 0 ] && wait
done
wait
echo "L SWEEP DONE"
