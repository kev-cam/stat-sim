#!/bin/bash
export PYMS_VAE_CACHE=/usr/local/src/stat-sim/qal/muxbuck_sk/vae_cache_sk
cd /usr/local/src/stat-sim/qal/muxbuck_sk
until [ -f sk_droop8_r32.cir.mt0 ]; do sleep 10; done
Xyce sk_gain58.cir > sk_gain58.log 2>&1
echo "done sk_gain58 $(date +%T)"

# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
