#!/bin/bash
cd /usr/local/src/stat-sim/qal/synth/threeway/spice/fsm || exit 1
for d in g_d4 st_d4; do
  echo "#### $d ####"
  ./run_one.sh "$d.cir" 1200
  echo "rc=$? $d $(grep -i '^EVDD' $d.cir.mt0 2>/dev/null | head -1)"
done
echo "FUNC RUN DONE"
