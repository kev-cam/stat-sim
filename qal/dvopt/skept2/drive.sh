#!/bin/bash
# run a job list with N concurrent Xyce point-runs.  Each line: "<tag> <L> <W> <dV>"
# Concurrency is capped because two other workflows share this 16-core box.
cd /usr/local/src/stat-sim/qal/dvopt/skept2 || exit 1
N=${N:-3}
LIST=$1
while read -r tag L W dv; do
  [ -z "$tag" ] && continue
  while [ "$(jobs -rp | wc -l)" -ge "$N" ]; do sleep 3; done
  ( timeout 1200 python3 s2.py pt "$tag" "$L" "$W" "$dv" > "log_$tag.txt" 2>&1 ) &
  echo "launched $tag"
done < "$LIST"
wait
echo "ALL DONE"
