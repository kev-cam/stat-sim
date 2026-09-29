#!/bin/bash
# Q2 chain points.  Thresholds are passed in from THIS directory's own measured DC
# grid so extract.py's pattern guard uses the point's real Vtn/|Vtp|, not the
# DELVTO = 0 constants it inherits.
cd /usr/local/src/stat-sim/qal/vtreq
mkdir -p rowd
MAXPAR=${MAXPAR:-3}
go () {
  python3 chain.py "$1" "$2" "$3" "$4" "$5" > "log_chain_$1.txt" 2>&1
  echo "[$(date +%H:%M:%S)] chain $1 rc=$?"
}
n=0
while read -r tag dn dp vtn vtp; do
  [ -z "$tag" ] && continue
  go "$tag" "$dn" "$dp" "$vtn" "$vtp" &
  n=$((n+1))
  if [ $((n % MAXPAR)) -eq 0 ]; then wait; fi
done <<'TAGS'
d000 0 0 0.523987 0.440283
d200N -0.20 0 0.323987 0.440283
d300N -0.30 0 0.223987 0.440283
d200P 0 -0.20 0.523987 0.239452
d200B -0.20 -0.20 0.323987 0.239452
TAGS
wait
echo "CHAIN SET DONE"
