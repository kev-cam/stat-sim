#!/bin/bash
# qal/eye full run.  Step (b) instrument check FIRST -- PRE_REGISTERED.json IC4
# says the study STOPS on an instrument failure -- then the six patterns in
# lanes of at most 3 concurrent heavy Xyce jobs (SIM DISCIPLINE).
set -u
cd /usr/local/src/stat-sim/qal/eye || exit 1
: > lanes.log

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a lanes.log; }

say "STEP b: instrument check -- committed 0.25 ps ceiling AND my 0.10 ps ceiling"
( python3 instrcheck.py run      > log_IC_committed.txt 2>&1; echo "IC_committed rc=$?" >> lanes.log ) &
( python3 instrcheck.py run_fine > log_IC_fine.txt      2>&1; echo "IC_fine rc=$?"      >> lanes.log ) &
wait
say "STEP b: scoring"
python3 instrcheck.py score > log_IC_score.txt 2>&1
rc=$?
cat log_IC_score.txt | tee -a lanes.log
if [ $rc -ne 0 ]; then
  say "INSTRUMENT FAILURE -- stopping per PRE_REGISTERED IC4. No eye will be reported."
  exit 1
fi
say "INSTRUMENT OK -- proceeding to the eye"

say "STEP c: six data patterns, 3 lanes"
i=0
for P in P0 P1 P2 P3 P4 P5; do
  ( python3 run_pattern.py "$P" > "log_$P.txt" 2>&1; echo "DONE $P rc=$?" >> lanes.log ) &
  i=$((i+1))
  if [ $((i % 3)) -eq 0 ]; then wait; fi
done
wait
say "all patterns done"

say "STEP d/e: extracting the eye"
python3 eyerun.py P0 P1 P2 P3 P4 P5 > log_eyerun.txt 2>&1
say "eyerun rc=$?"
tail -40 log_eyerun.txt | tee -a lanes.log
say "ALL DONE"
