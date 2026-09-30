#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize_skept
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize_skept/vae_cache
export PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize_skept/pyms_shell
export PYMS_CALLBACK_PARAMS=DELVTO
Xyce $1.cir > $1.log 2>&1
echo "$1 RC=$?" >> rep.done
