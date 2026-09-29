#!/bin/bash
# wait for the DC run to finish, then run rx, qdi, and the sync->QAL sweep
# strictly one Xyce at a time (PyMS vae-cache rule).
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_boundT3
cd /usr/local/src/stat-sim/qal/bound
while pgrep -f 'Xyce bd_dc.cir' >/dev/null 2>&1; do sleep 5; done
for d in bd_rx bd_qdi; do
  echo "=== START $d $(date +%T) ==="
  S=$(date +%s)
  /usr/local/src/xyce-build/src/Xyce $d.cir > $d.log 2>&1
  echo "=== DONE $d $(date +%T) rc=$? wall=$(( $(date +%s) - S ))s ==="
done
echo "=== START s2q $(date +%T) ==="
python3 -u bd_s2q.py 1.0 1.2 1.5 > s2q_drive.log 2>&1
echo "=== DONE s2q $(date +%T) rc=$? ==="
echo "=== CHAIN DONE ==="
