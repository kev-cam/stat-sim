#!/bin/bash
cd /usr/local/src/stat-sim/qal/synth/threeway/spice/fsm || exit 1
for d in g_d1 st_d1 g_d4 st_d4 g_d10 st_d10; do
  echo "######## $d ########"
  ./run_one.sh "$d.cir" 1500
  echo "rc=$? $d EVDD=$(grep -i '^EVDD' $d.cir.mt0 2>/dev/null | head -1) prn=$(stat -c%s $d.cir.prn 2>/dev/null)"
done
echo "FSM RUN DONE"

# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
