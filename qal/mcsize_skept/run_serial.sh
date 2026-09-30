#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize_skept
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize_skept/pyms_shell
export PYMS_CALLBACK_PARAMS=DELVTO
# SERIAL: one build at a time, each with its OWN vae cache dir so two builds can
# never share a .so.build/ scratch directory (that race corrupted eval.cpp).
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize_skept/vc_base
Xyce sk_rep_base.cir > sk_rep_base.log 2>&1
echo "sk_rep_base RC=$?" >> rep.done
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize_skept/vc_k8
Xyce sk_rep_basek8.cir > sk_rep_basek8.log 2>&1
echo "sk_rep_basek8 RC=$?" >> rep.done
