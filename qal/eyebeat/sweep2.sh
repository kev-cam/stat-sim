#!/bin/bash
# Beat sweep, newton-on-row protocol (AMENDMENT B2). 3 concurrent lanes.
EB=/usr/local/src/stat-sim/qal/eyebeat
cd "$EB" || exit 1
run_batch () {
  local T=$1; shift
  echo "=== T=$T : $* ==="
  for P in "$@"; do
    if [ -f "$EB/T$T/$P/sched.json" ]; then echo "  skip T$T/$P (done)"; continue; fi
    ( cd "$EB" && python3 eb.py lane "$T" "$P" > "log_T${T}_${P}.txt" 2>&1 ) &
  done
  wait
  grep -h "iter\|OK ->\|A6-FAIL\|ROW FAILED" log_T${T}_*.txt 2>/dev/null | tail -12
}
run_batch 60  P0 P1 P2
run_batch 300 P0 P1 P2
run_batch 90  P0 P1 P2
run_batch 250 P0 P1 P2
run_batch 120 P0 P1 P2
run_batch 150 P0 P1 P2
run_batch 200 P0 P1 P2
echo "=== guards: P3 at the sweep ends ==="
run_batch 60 P3
run_batch 300 P3
echo "=== convergence guard: T=60 P0 fine steps, SAME zeros ==="
if [ ! -f "$EB/T60fine/P0/sched.json" ]; then
  mkdir -p "$EB/T60fine/P0"
  python3 - <<'EOF'
import json
z=json.load(open('/usr/local/src/stat-sim/qal/eyebeat/T60/P0/zeros.json'))
z['provenance']='COPIED from T60/P0 zeros.json (newton-converged) so ONLY the .tran steps differ'
open('/usr/local/src/stat-sim/qal/eyebeat/T60fine/P0/zeros.json','w').write(json.dumps(z,indent=1))
EOF
  ( cd "$EB" && python3 eb.py lane 60 P0 --fine > log_T60fine_P0.txt 2>&1 )
fi
echo "SWEEP2 DONE"
