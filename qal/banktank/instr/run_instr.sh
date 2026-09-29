#!/bin/bash
cd /usr/local/src/stat-sim/qal/banktank/instr
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_banktank
for f in i1_lsweep_L15_W30_dv120 i2_load691_L4_W30_dv165 i3_chain3_f45; do
  ( /usr/local/src/xyce-build/src/Xyce $f.cir > $f.log 2>&1; echo "$f rc=$?" >> instr.status ) &
done
wait
echo "ALLDONE" >> instr.status
