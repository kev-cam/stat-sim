#!/bin/bash
# Run ONE Xyce deck, after waiting for any other Xyce to finish.
# Concurrent Xyce runs corrupt the PyMS vae cache -- one at a time, always.
set -u
DECK="$1"; LIM="${2:-900}"
cd /usr/local/src/stat-sim/qal/synth/threeway/spice/cscd || exit 1

for i in $(seq 1 240); do
  n=$(pgrep Xyce | wc -l)
  [ "$n" = "0" ] && break
  echo "waiting: $n Xyce running ($((i*10))s)"
  sleep 10
done
n=$(pgrep Xyce | wc -l)
if [ "$n" != "0" ]; then echo "ABORT: Xyce still busy after 40 min"; exit 2; fi

t0=$(date +%s)
echo "START $DECK $(date -Is)"
env PYMS_DIR=/usr/local/share/xyce/PyMS timeout "$LIM" \
    /usr/local/src/xyce-build/src/Xyce "$DECK" > "${DECK%.cir}.log" 2>&1
rc=$?
echo "DONE  $DECK rc=$rc elapsed=$(( $(date +%s) - t0 ))s"
grep -a "build_vae_so" "${DECK%.cir}.log" | sed 's/^/  /'
grep -aiE "error|fatal|abort|failure" "${DECK%.cir}.log" | grep -vi "no model parameter" | head -10
exit $rc
