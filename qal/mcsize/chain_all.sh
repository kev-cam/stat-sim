#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize
echo "chain start $(date +%H:%M:%S)" > chain.log
# 1. wait for the banktank baseline MC
while ! grep -q "ALL BT" bt_mc.done 2>/dev/null; do sleep 15; done
echo "BT done $(date +%H:%M:%S)" >> chain.log
# 2. resv MC, 3 chunks
./run_rv.sh >/dev/null 2>&1
echo "RV done $(date +%H:%M:%S)" >> chain.log
# 3. Phase 2 wave A -- pure-sigma controls, geometry unchanged, .so already built
WAVE="p2_base p2_k4 p2_k8" ./run_p2.sh >/dev/null 2>&1
echo "P2-A done $(date +%H:%M:%S)" >> chain.log
# 4. Phase 2 wave B -- resized geometries, each needs its own PyMS .so build
WAVE="p2_wx2 p2_wx4 p2_lx2" ./run_p2.sh >/dev/null 2>&1
echo "P2-B done $(date +%H:%M:%S)" >> chain.log
echo "CHAIN COMPLETE" >> chain.log
