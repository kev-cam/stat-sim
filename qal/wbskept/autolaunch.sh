#!/bin/bash
# SKEPTIC autolaunch.  Waits on MY OWN warm PID, passed in as $1.
#
# TRAP CLEARED (SK-A8): the first version waited on `pgrep -f warm_sk.py`.
# A DIFFERENT concurrent study, qal/cipher/skept, has a file with the SAME
# NAME and runs a deck with the same name, in its own directory and its own
# PYMS_VAE_CACHE (vae_cache_ciphskept).  pgrep -f matched its process too, so
# my launch would have waited on an unrelated study's warm.  Same family as the
# campaign's recorded pkill-self-match trap: match by PID, never by pattern.
set -u
cd /usr/local/src/stat-sim/qal/wbskept
SP=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad
MYPID="$1"
while kill -0 "$MYPID" 2>/dev/null; do sleep 15; done
N=$(ls $SP/vae_cache_wbskept/*.so 2>/dev/null | wc -l)
echo "[$(date +%T)] MY warm (pid $MYPID) exited with $N/20 .so"
if [ "$N" -lt 20 ]; then
  echo "[$(date +%T)] WARM INCOMPLETE -- not launching, would trigger concurrent compiles"
  exit 1
fi
bad=0
for f in $SP/vae_cache_wbskept/*.so; do
  file -b "$f" | grep -q "ELF 64-bit LSB shared object" || { echo "BAD SO: $f"; bad=1; }
done
if [ "$bad" -ne 0 ]; then echo "[$(date +%T)] CACHE INTEGRITY FAILED"; exit 1; fi
echo "[$(date +%T)] all 20 .so are valid ELF shared objects -- launching CRUX"
bash run_sk.sh crux > log_crux_sk.txt 2>&1
echo "[$(date +%T)] CRUX done"
bash run_sk.sh chain > log_chain_sk.txt 2>&1
echo "[$(date +%T)] CHAIN done"
bash run_sk.sh ctl > log_ctl_sk.txt 2>&1
echo "[$(date +%T)] CTL done -- ALL SIMULATION COMPLETE"
