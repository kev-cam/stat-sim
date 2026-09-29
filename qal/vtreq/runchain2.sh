#!/bin/bash
cd /usr/local/src/stat-sim/qal/vtreq
go () { python3 chain.py "$1" "$2" "$3" "$4" "$5" > "log_chain_$1.txt" 2>&1; echo "[$(date +%H:%M:%S)] chain $1 rc=$?"; }
go d300B -0.30 -0.30 0.223987 0.139080 &
go d150B -0.15 -0.15 0.373987 0.289653 &
go d300P 0 -0.30 0.523987 0.139080 &
wait
echo "CHAIN SET 2 DONE"
