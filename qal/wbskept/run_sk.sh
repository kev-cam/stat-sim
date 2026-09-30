#!/bin/bash
# SKEPTIC driver.  Concurrency capped at 4: the box is shared (load was 10.6 at
# launch with other studies' Xyce and g++ resident on 16 cores) and / has only
# ~5 GB free.  N=256 is the long pole and is launched FIRST so it overlaps
# everything else.
set -u
cd /usr/local/src/stat-sim/qal/wbskept
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_wbskept

case "${1:-}" in

chain)
  # N=256 first (longest), then the headline N=64, then 128 / 32.
  { echo "256 1"; echo "64 1"; echo "128 1"; echo "32 1"; } \
   | xargs -P 4 -L 1 bash -c 'python3 pt.py $0 $1 > log_n$0_s$1.txt 2>&1; echo "n$0 s$1 rc=$? :: $(grep -h "^DONE\|FAILED\|Error\|Traceback" log_n$0_s$1.txt | tail -1)"'
  ;;

ctl)
  # S = one UPSIZED point of my own (N=64 s=2), to check the sign of the cell-size
  #     lever inside the real chain rather than inheriting it.
  # E6 = L 15 -> 3.75 nH at s=1.  This is the FASTEST point the whole campaign
  #     found, so it is the best case for "higher performance at a power cost"
  #     and a skeptic must test the best case, not only the worst.
  { echo "64 2 - - - - -";
    echo "64 1 3.75 - - - E6Lcut"; } \
   | xargs -P 2 -L 1 bash -c 'python3 pt.py $0 $1 $2 $3 $4 $5 $6 > log_ctl_${1}_${2}_${6}.txt 2>&1; echo "s=$1 L=$2 $6 rc=$? :: $(grep -h "^DONE\|FAILED\|Error\|Traceback" log_ctl_${1}_${2}_${6}.txt | tail -1)"'
  ;;

crux)
  # A/B/C/D at s=1/2/4/8, at BOTH rails.  0.9422477 V is bank 2's own MEASURED
  # delivered rail and is the physically relevant one; 1.65 V is the nominal dV
  # the record headlines.  Tiny decks, seconds each, so run both.
  for rail in 1.65 0.9422477; do for v in A B C D; do for s in 1 2 4 8; do
    echo "$rail $v $s"; done; done; done \
   | xargs -P 4 -L 1 bash -c 'python3 sk_crux.py $0 $1 $2 2>&1 | tail -1'
  ;;

cruxE)
  # variant E needs MY measured C_j, passed in as $2
  for s in 1 2 4 8; do echo "1.65 E $s $2"; done \
   | xargs -P 4 -L 1 bash -c 'python3 sk_crux.py $0 $1 $2 $3 2>&1 | tail -1'
  ;;

*) echo "usage: run_sk.sh {chain|crux|cruxE CJ}"; exit 2;;
esac
echo "[$(date +%T)] $1 done"
