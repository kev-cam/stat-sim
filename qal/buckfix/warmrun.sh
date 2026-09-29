#!/bin/bash
cd /usr/local/src/stat-sim/qal/buckfix
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_buckfix
/usr/local/src/xyce-build/src/Xyce warm.cir > warm.log 2>&1
echo "warm rc=$?" > warm.status
/usr/local/src/xyce-build/src/Xyce IC_SR_s4_ptu_T200_dv1200_L1_t12.cir > IC_SR_s4_ptu_T200_dv1200_L1_t12.log 2>&1
echo "ic12 rc=$?" >> warm.status
