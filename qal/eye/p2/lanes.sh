#!/bin/bash
# Run a queue of p2run.py jobs at most 3 concurrent (pre-registered B8).
# Usage: lanes.sh <jobsfile>   where each line is: <mode> <T> <H> <PAT>
cd /usr/local/src/stat-sim/qal/eye/p2 || exit 1
MAXJ=3
while read -r mode T H PAT; do
  [ -z "$mode" ] && continue
  while [ "$(jobs -rp | wc -l)" -ge "$MAXJ" ]; do sleep 5; done
  echo "[$(date +%T)] launch $mode T=$T H=$H $PAT"
  python3 p2run.py "$mode" "$T" "$H" "$PAT" \
      > "log_${mode}_T${T}_H${H}_${PAT}.txt" 2>&1 &
done < "$1"
wait
echo "[$(date +%T)] QUEUE COMPLETE"
