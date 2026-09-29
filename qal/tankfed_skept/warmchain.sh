#!/bin/bash
cd /usr/local/src/stat-sim/qal/tankfed_skept
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_tfskept
while pgrep -f "Xyce warm[.]cir" > /dev/null; do sleep 10; done
/usr/local/src/xyce-build/src/Xyce warm2.cir > warm2.out 2>&1
echo "WARM2 DONE rc=$?" >> warm2.out
