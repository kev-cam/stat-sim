#!/bin/bash
cd /usr/local/src/stat-sim/qal/cipher/skept
export PYMS_VAE_CACHE=/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_ciphskept
# wait for the warm deck to finish so the geometry builds do not race (parent's B11)
while ! grep -qE 'ran warm_sk|XYCE FAIL|TIMEOUT' log_warm_sk.txt 2>/dev/null; do sleep 15; done
echo "=== warm finished $(date +%H:%M:%S) ==="
tail -2 log_warm_sk.txt
echo "=== AES row re-run from scratch $(date +%H:%M:%S) ==="
python3 -u run.py row aes 1150 4.608 1.0
echo "=== row rc=$? $(date +%H:%M:%S) ==="
ls -la ROW_aes*.json c_aes*.cir.mt0 2>/dev/null
