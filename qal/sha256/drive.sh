#!/bin/bash
# N-way parallel driver, default 3 heavy Xyce jobs (other workflows share this box).
cd /usr/local/src/stat-sim/qal/sha256
MAXJ=${MAXJ:-3}
while read -r name cmd; do
  [ -z "$name" ] && continue
  while [ "$(jobs -rp | wc -l)" -ge "$MAXJ" ]; do sleep 5; done
  echo "LAUNCH $name"
  ( eval "$cmd" > "log_$name.txt" 2>&1; echo "DONE $name rc=$?" ) &
done
wait
echo ALLDONE
