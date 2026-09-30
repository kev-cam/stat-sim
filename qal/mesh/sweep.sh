#!/bin/bash
# qal/mesh sweep driver: 12 core lanes 4-wide (<=4 Xyce concurrent; rfast
# shares the box), then flyback lanes at the 2x point.
cd /usr/local/src/stat-sim/qal/mesh
LANES_CORE=(
 "sine 70 0.2" "sine 80 0.2" "sine 92 0.2" "sine 105 0.2" "sine 117 0.2" "sine 130 0.2"
 "saw 70 0.2"  "saw 80 0.2"  "saw 92 0.2"  "saw 105 0.2"  "saw 117 0.2"  "saw 130 0.2"
)
LANES_FLY=( "saw 92 0.1" "saw 92 0.3" )
run_lane() { python3 mesh.py lane $1 $2 $3 > "log_lane_${1}_th${2}_f${3}.txt" 2>&1; }
export -f run_lane
printf '%s\n' "${LANES_CORE[@]}" | xargs -P 4 -I{} bash -c 'run_lane {}'
printf '%s\n' "${LANES_FLY[@]}"  | xargs -P 2 -I{} bash -c 'run_lane {}'
echo "SWEEP DONE"
