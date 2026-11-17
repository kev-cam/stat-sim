#!/bin/bash
cd /usr/local/src/stat-sim/qal/synth/threeway/spice/fsm || exit 1
for d in g_d2 st_d2 g_d4 st_d4 g_d10 st_d10; do
  echo "######## $d ########"; ./run_one.sh "$d.cir" 1800
  echo "rc=$? $d $(grep -i '^EVDD' $d.cir.mt0 2>/dev/null|head -1)"
done
echo "FSM RUN2 DONE"

# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
