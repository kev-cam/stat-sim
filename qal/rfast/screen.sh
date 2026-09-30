#!/bin/bash
# W-ladder screening: per L, T_screen = 200 ps, pattern P0 only (pre-registered
# W_selection rule).  Lanes run concurrently; each lane is serial inside.
set -u
RF=/usr/local/src/stat-sim/qal/rfast
run_lane () {
  L=$1; W=$2
  python3 "$RF"/rf.py lane "$L" "$W" 200 P0 > "$RF"/log_screen_L${L}W${W}.txt 2>&1
  rc=$?
  python3 "$RF"/rf.py extract "$L" "$W" 200 P0 >> "$RF"/log_screen_L${L}W${W}.txt 2>&1
  echo "screen L=$L W=$W lane_rc=$rc"
}
export -f run_lane
export RF
printf '%s\n' "15 30" "15 45" "10 30" "10 45" "10 60" "6 30" "6 45" "6 60" "3 45" "3 60" "3 90" \
 | xargs -P 6 -n 2 bash -c 'run_lane "$0" "$1"'
echo SCREEN_DONE
