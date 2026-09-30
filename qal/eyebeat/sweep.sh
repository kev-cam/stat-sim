#!/bin/bash
# THE BEAT SWEEP: 3 concurrent lanes (one per pattern), T values sequential.
# Keeps to ~3 concurrent Xyce processes (other campaign runs share the box).
cd /usr/local/src/stat-sim/qal/eyebeat
for T in 60 300 90 250 120 150; do
  echo "=== T=$T ==="
  python3 eb.py lane $T P0 > log_T${T}_P0.txt 2>&1 &
  python3 eb.py lane $T P1 > log_T${T}_P1.txt 2>&1 &
  python3 eb.py lane $T P2 > log_T${T}_P2.txt 2>&1 &
  wait
  grep -h "A6\|OK ->\|FAIL" log_T${T}_P?.txt | tail -9
done
echo "=== T=200 (reused qal/eye zeros) ==="
python3 eb.py lane 200 P0 > log_T200_P0.txt 2>&1 &
python3 eb.py lane 200 P1 > log_T200_P1.txt 2>&1 &
python3 eb.py lane 200 P2 > log_T200_P2.txt 2>&1 &
wait
grep -h "A6\|OK ->\|FAIL" log_T200_P?.txt | tail -9
echo "=== guards: P3 at T=60 and T=300 ==="
python3 eb.py lane 60 P3 > log_T60_P3.txt 2>&1 &
python3 eb.py lane 300 P3 > log_T300_P3.txt 2>&1 &
wait
echo "=== convergence: T=60 P0 at fine steps, SAME zeros ==="
mkdir -p T60fine/P0 && cp T60/P0/zeros.json T60fine/P0/zeros.json
python3 eb.py lane 60 P0 --fine > log_T60fine_P0.txt 2>&1
echo "SWEEP DONE"
