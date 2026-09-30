#!/bin/bash
# PHASE 2 driver.  Concurrency is capped at 5 because ~8-12 Xyce jobs from
# OTHER studies are already resident on this 16-core box (checked at launch and
# recorded in RUNLOG.txt); the brief allows ~6 heavy jobs and this study takes
# 5 so it does not starve them.
set -u
cd /usr/local/src/stat-sim/qal/upsize
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_upsize
P=5

stamp() { date +%T; }

case "${1:-}" in

crux)
  # 24 cell-chain decks -- THE CRUX, answered first.  All geometries are warm
  # by now so there is no PyMS compile and therefore no cache race.
  echo "[$(stamp)] CRUX: 24 decks, ${P} at a time"
  for rail in 1.65 0.9422477; do
    for v in A B C D; do
      for s in 1 2 4 8; do echo "$rail $v $s"; done
    done
  done | xargs -P $P -L 1 bash -c 'python3 up.py cc $0 $1 $2 2>&1 | tail -2'
  echo "[$(stamp)] CRUX decks done"
  ;;

chain)
  # the MAIN series, both N.  N=64 s=1 is also the B0b re-run.
  echo "[$(stamp)] CHAIN: 8 points, ${P} at a time"
  { echo "64 1"; echo "8 1"; echo "8 2"; echo "8 4";
    echo "8 8";  echo "64 2"; echo "64 4"; echo "64 8"; } \
    | xargs -P $P -L 1 bash -c 'python3 pt.py $0 $1 > log_n$0_s$1.txt 2>&1; echo "n$0 s$1 rc=$? :: $(grep -h "^DONE\|FAILED\|Error\|Traceback" log_n$0_s$1.txt | tail -1)"'
  echo "[$(stamp)] CHAIN done"
  ;;

ctl)
  # E1 load-not-scaled (banks 1,2 at s=4, bank 3 at x1)
  # E3 iso-hop        (s=4 with L = 15/4 = 3.75 nH, holding t_hop)
  # E4 half timestep  (s=8 at 0.3536 ps vs the pre-registered 0.7071)
  echo "[$(stamp)] CONTROLS: E1 / E3 / E6 (each probes + rows)"
  { echo "64 4,4,1 - - - - E1load";
    echo "64 4 3.75 - - - E3isohop";
    echo "64 1 3.75 - - - E6Lcut"; } \
    | xargs -P 3 -L 1 bash -c 'python3 pt.py $0 $1 $2 $3 $4 $5 $6 > log_ctl_$6.txt 2>&1; echo "$6 rc=$? :: $(grep -h "^DONE\|FAILED\|Error\|Traceback" log_ctl_$6.txt | tail -1)"'
  echo "[$(stamp)] CONTROL E4 (B11 half timestep) -- REUSES the main s=8 zeros"
  python3 pt.py rowonly zeros_n64_dv1650_T1090_H4_nb3_s8.json 0.35355339059327373 E4halfstep \
    > log_ctl_E4halfstep.txt 2>&1
  echo "E4 rc=$? :: $(grep -h "^DONE\|FAILED\|Error\|Traceback" log_ctl_E4halfstep.txt | tail -1)"
  echo "[$(stamp)] CONTROLS done"
  ;;

*)
  echo "usage: run_all.sh {crux|chain|ctl}"; exit 2;;
esac
