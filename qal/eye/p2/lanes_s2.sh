#!/bin/bash
cd /usr/local/src/stat-sim/qal/eye/p2 || exit 1
while read -r mode T H PAT OFF; do
  [ -z "$mode" ] && continue
  echo "[$(date +%T)] launch $mode $PAT off=$OFF"
  python3 p2run.py "$mode" "$T" "$H" "$PAT" "$OFF" > "log_stress_T${T}_${PAT}_${OFF}.txt" 2>&1
done < "$1"
echo "[$(date +%T)] S2 COMPLETE"

# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
