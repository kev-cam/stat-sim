#!/bin/bash
# Sweep the switch width W -- the parameter that matters most, because it sets
# BOTH terms that compete:
#   wider W -> lower Ron -> higher transfer Q -> LESS inductive/ conduction loss
#   wider W -> larger gate capacitance -> MORE gate-drive energy
# Everything else is held fixed, so the sweep isolates that trade-off and locates
# the optimum (or shows there is none in range).
#
# STRICTLY SEQUENTIAL: concurrent Xyce runs corrupt the PyMS vae .so cache.
set -u
cd /usr/local/src/stat-sim/qal/flycap
NPER=${NPER:-16}
NWARM=${NWARM:-10}
for W in 1u 2u 4u 10u 20u; do
  # keep the gate ATTENUATION ratio roughly constant across widths: CCP tracks W
  case $W in
    1u)  CCP=0.6f ;;
    2u)  CCP=1.2f ;;
    4u)  CCP=2.4f ;;
    10u) CCP=6f   ;;
    20u) CCP=12f  ;;
  esac
  OUT=sw_w${W}.cir
  python3 gen_c5loop.py --out "$OUT" --nper "$NPER" --nwarm "$NWARM" \
      --RTL 10k --DRVTOP rp --DRVBOT rn --VCKH 3.0 --CCP "$CCP" --WSW "$W" >/dev/null
  echo "=== W=$W  CCP=$CCP  -> $OUT ==="
  python3 run_c5.py "$OUT" --brief > "sw_w${W}.report" 2>&1
  grep -E "GATES:|RESIDUAL|the number|BREAKDOWN|switch gate drive|switch devices|gate settle|inductive|FLYCAP|bank A max|bank A min|tier voltages|SWAB gate" "sw_w${W}.report"
done
