#!/bin/bash
# Skeptic re-run lanes, 8-way.  Every lane seeds INDEPENDENTLY (no rfast
# zeros.json is visible under rfast_skept, so rf.py falls back to the
# sqrt-scaled qal/eye seeds -- a different Newton path than the record's).
set -u
SK=/usr/local/src/stat-sim/qal/rfast_skept
lane () { python3 $SK/sk.py lane "$1" "$2" "$3" "$4" > $SK/log_lane_L$1W$2_T$3_$4.txt 2>&1; echo "lane L$1 W$2 T$3 $4 rc=$?"; }
export -f lane; export SK

printf '%s\n' \
  "3 60 105 P0" "3 60 105 P1" "3 60 105 P2" "3 60 105 P3" \
  "3 60 100 P0" "3 60 100 P1" "3 60 100 P2" \
  "10 15 115 P0" "10 15 115 P1" "10 15 115 P2" \
  "15 30 150 P0" "15 30 150 P1" "15 30 150 P2" \
  "15 15 130 P0" "15 15 130 P1" "15 15 130 P2" \
  "6 30 110 P0" "6 30 110 P1" "6 30 110 P2" \
 | xargs -P 8 -n 4 bash -c 'lane "$0" "$1" "$2" "$3"'
echo LANES_DONE

# the sequential-A6 target re-run (serial inside)
python3 $SK/sk.py seqprobe 15 30 140 > $SK/log_seqA6_T140.txt 2>&1
echo "seqprobe T140 rc=$?"
echo ALL_DONE
