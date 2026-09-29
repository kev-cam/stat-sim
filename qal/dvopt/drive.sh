#!/bin/bash
# N-way parallel driver, max 4 heavy Xyce jobs (two other workflows share this box)
cd /usr/local/src/stat-sim/qal/dvopt
MAXJ=${MAXJ:-4}
while read -r name cmd; do
  [ -z "$name" ] && continue
  while [ "$(jobs -rp | wc -l)" -ge "$MAXJ" ]; do sleep 2; done
  echo "LAUNCH $name"
  ( eval "$cmd" > "log_$name.txt" 2>&1; echo "DONE $name rc=$?" ) &
done
wait
echo ALLDONE
