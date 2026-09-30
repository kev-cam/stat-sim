#!/bin/bash
cd /usr/local/src/stat-sim/qal/mcsize_skept
export PYMS_DIR=/usr/local/share/xyce/PyMS
export PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize_skept/pyms_shell
export PYMS_CALLBACK_PARAMS=DELVTO
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/mcsize_skept/vc_base
# 1) nominal, zero mismatch -> equivalence test of MY model build against the
#    committed banktank rails (0.6767239 / 0.7312457 / 0.7200878 V).
Xyce sk_nom.cir > sk_nom.log 2>&1; echo "sk_nom RC=$?" >> rep.done
# 2) the actual fresh-seed replication, reusing whatever .so step 1 built
Xyce sk_rep_base.cir > sk_rep_base.log 2>&1; echo "sk_rep_base RC=$?" >> rep.done
