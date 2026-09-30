#!/bin/bash
cd /usr/local/src/stat-sim/qal/eye/p2 || exit 1
MAXJ=3
while read -r mode T H PAT OFF; do
  [ -z "$mode" ] && continue
  while [ "$(jobs -rp | wc -l)" -ge "$MAXJ" ]; do sleep 5; done
  echo "[$(date +%T)] launch $mode T=$T H=$H $PAT off=$OFF"
  python3 p2run.py "$mode" "$T" "$H" "$PAT" "$OFF" \
      > "log_${mode}_T${T}_${PAT}_${OFF}.txt" 2>&1 &
done < "$1"
wait
echo "[$(date +%T)] STRESS QUEUE COMPLETE"
