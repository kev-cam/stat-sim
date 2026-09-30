#!/bin/bash
# The (L, T) sweep at the measured W* (15/15/15/45), three patterns per (L,T),
# T=200 P1/P2 first (A3 seeds), then lower T; extract after each (L,T) set.
set -u
RF=/usr/local/src/stat-sim/qal/rfast
lane () { python3 $RF/rf.py lane "$1" "$2" "$3" "$4" >> $RF/log_lane_L$1W$2_T$3_$4.txt 2>&1; echo "lane L$1 W$2 T$3 $4 rc=$?"; }
export -f lane; export RF

# ---- stage 1: T=200 P1/P2 at each (L, W*) --------------------------------
printf '%s\n' "15 15 200 P1" "15 15 200 P2" "10 15 200 P1" "10 15 200 P2" \
              "6 15 200 P1" "6 15 200 P2" "3 45 200 P1" "3 45 200 P2" \
 | xargs -P 8 -n 4 bash -c 'lane "$0" "$1" "$2" "$3"'
for lw in "15 15" "10 15" "6 15" "3 45"; do
  set -- $lw
  python3 $RF/rf.py extract "$1" "$2" 200 P0 P1 P2 > $RF/log_x_L$1W$2_T200.txt 2>&1
  echo "extract L$1 W$2 T200 rc=$?"
done

# ---- stage 2: the beat grids ---------------------------------------------
Q=""
for T in 150 140 130 120 110; do for P in P0 P1 P2; do Q="$Q 15 15 $T $P"; done; done
for T in 150 130 120 110 100; do for P in P0 P1 P2; do Q="$Q 10 15 $T $P"; done; done
for T in 130 110 100 90 85;   do for P in P0 P1 P2; do Q="$Q 6 15 $T $P"; done; done
for T in 100 90 80 70 65;     do for P in P0 P1 P2; do Q="$Q 3 45 $T $P"; done; done
printf '%s\n' $Q | xargs -P 8 -n 4 bash -c 'lane "$0" "$1" "$2" "$3"'

# ---- stage 3: extract everything -----------------------------------------
for T in 150 140 130 120 110; do python3 $RF/rf.py extract 15 15 $T > $RF/log_x_L15W15_T$T.txt 2>&1; echo "x L15 T$T rc=$?"; done
for T in 150 130 120 110 100; do python3 $RF/rf.py extract 10 15 $T > $RF/log_x_L10W15_T$T.txt 2>&1; echo "x L10 T$T rc=$?"; done
for T in 130 110 100 90 85;   do python3 $RF/rf.py extract 6 15 $T > $RF/log_x_L6W15_T$T.txt 2>&1; echo "x L6 T$T rc=$?"; done
for T in 100 90 80 70 65;     do python3 $RF/rf.py extract 3 45 $T > $RF/log_x_L3W45_T$T.txt 2>&1; echo "x L3 T$T rc=$?"; done
echo SWEEP_DONE
