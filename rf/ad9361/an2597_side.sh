#!/bin/bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
#
# One side of a cross-machine AN-2597 arena (an2597_arena.sh runs both sides on one host).
#
#   NB=<nvc-build> W=<workdir> ROLE=1|2 NAME=drone|ctrl [AD=..] [DISTS=".."] [PK=n] [LEAD=8us] an2597_side.sh gen
#   NB=<nvc-build> W=<workdir> NAME=drone|ctrl RV=host:port an2597_side.sh run
#
# Use the same DISTS/PK/LEAD on both sides.  Start the rendezvous first, on an address both reach:
#   python3 <nvc>/lib/sv2vhdl/arena_ctl.py rendezvous --arena lab-2g4 --listen host:port --expect drone,ctrl
# A side behind NAT only dials out, so rank it first (ROLE=1).  Results land in $W/out.txt.
set -e
: "${NB:?set NB to the nvc build directory}" "${W:?set W to a work directory}" "${NAME:?set NAME}"
NVC="$NB/bin/nvc --std=2040 -L $NB/lib"
SV=$(cd "$NB" && sed -n 's/^abs_top_srcdir = //p' Makefile)/lib/sv2vhdl
AD=${AD:-$(cd "$(dirname "$0")" && pwd)}
DISTS=${DISTS:-"3.0 30.0"}; PK=${PK:-2}
GFLAGS=""; i=0
for d in $DISTS; do GFLAGS="$GFLAGS -gd$i=$d"; i=$((i+1)); done
if [ -n "$LEAD" ]; then GFLAGS="$GFLAGS -gtx_lead=$LEAD"; fi
export NVC_NO_EVAL_ARENA=1
if [ "$1" = gen ]; then
    : "${ROLE:?set ROLE (1 or 2)}"
    rm -rf "$W"; mkdir -p "$W/gen"; cd "$W"
    (cd "$AD" && python3 -c "import ad9361_vhdl; open('$W/ad9361_pkg.vhd','w').write(ad9361_vhdl.emit())")
    SRC="$W/ad9361_pkg.vhd $AD/accel/spectral_accel_off.vhd $AD/accel/spectral_accel_pkg.vhd $AD/rf_spectrum_pkg.vhd $AD/ad9361_spectral_pkg.vhd $AD/ad9361.vhd $AD/rf_spec_antenna.vhd $AD/ofdm_soft_pkg.vhd $AD/an2597_link.vhd"
    $NVC -a $SRC
    $NVC -e an2597_link $GFLAGS -gpackets=$PK -grole=$ROLE
    NVC_RESOLVER_DIR=$PWD/gen NVC_RCMODE=none SV2VHDL_FORWARD_GENERICS=1 PYTHONPATH=$SV \
      $NVC -r --stop-time=1fs --load=$NB/lib/sv2vhdl/libresolver.so an2597_link > pass1.log 2>&1 || { tail -30 pass1.log; exit 1; }
    $NVC -a $(ls gen/*.vhd | grep -v _wrapper) gen/an2597_link_wrapper.vhd -e resolved_an2597_link
    echo "generated $NAME (role $ROLE) in $W"
elif [ "$1" = run ]; then
    : "${RV:?set RV to the rendezvous host:port}"
    cd "$W"
    t0=$(date +%s.%N)
    FED_NAME=$NAME FED_ARENAS="ism2g4=lab-2g4@$RV" \
      $NVC -r --load=$NB/lib/sv2vhdl/libarena.so resolved_an2597_link > run.log 2>&1 || { tail -20 run.log; exit 1; }
    awk -v a="$t0" -v b="$(date +%s.%N)" -v l="$NAME" 'BEGIN { printf "%s wall %.2f s\n", l, b - a }'
    grep -E 'libarena:' run.log || true
    grep 'AN2597 dist' run.log | sed 's/.*AN2597/AN2597/' > out.txt || true
else
    echo "usage: $0 gen|run  (see the header)" >&2; exit 2
fi
