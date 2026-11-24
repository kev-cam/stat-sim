#!/bin/bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
#
# AN-2597 across a shared arena, through nvc's resolver plugin + libarena + arena_ctl.py:
#   ref   : the whole link, hand-written arena_resolver.py network (zero delay)
#   mono  : the whole link in one simulation, plugin-generated band-arena resolver
#           with the physical delay of every path (ARENA_DELAY), band not mapped
#   fed   : drone side (role 1) and controller side (role 2) as two simulations
#           in one arena (arena_ctl.py run), each running ahead of the other by
#           the slack between them (the shortest antenna-to-antenna delay)
# fed must match mono line for line.
#
#   NB=<nvc build dir> [SV=<nvc>/lib/sv2vhdl] [W=<work dir>] [DISTS="1.0 30.0 ..."] [PK=<packets>] [TRACE=1] \
#     rf/ad9361/an2597_arena.sh
#
# NB is an nvc build with the arena support (lib/sv2vhdl/libarena.so, SV2VHDL.ARENA_PKG, libresolver.so).
set -e
NB=${NB:?set NB to the nvc build directory}
SV=${SV:-$(cd "$NB" && sed -n 's/^abs_top_srcdir = //p' Makefile)/lib/sv2vhdl}
NVC="$NB/bin/nvc --std=2040 -L $NB/lib"
AD=${AD:-$(cd "$(dirname "$0")" && pwd)}
LIBARENA=$NB/lib/sv2vhdl/libarena.so
DISTS=${DISTS:-"3.0 30.0"}; PK=${PK:-2}
W=${W:-/tmp/an2597_arena}
# timed <label> <command...>: run it, then say "<label> wall <s> s" on the terminal (fd 3), even when the
# command's output is redirected (no /usr/bin/time needed)
exec 3>&1
timed() {
    local label=$1 t0 rc=0; shift
    t0=$(date +%s.%N)
    "$@" || rc=$?
    awk -v a="$t0" -v b="$(date +%s.%N)" -v l="$label" 'BEGIN { printf "%s wall %.2f s\n", l, b - a }' >&3
    return $rc
}
GFLAGS=""; GPY=""; i=0
for d in $DISTS; do GFLAGS="$GFLAGS -gd$i=$d"; GPY="$GPY'd$i': '$d', "; i=$((i+1)); done
rm -rf $W; mkdir -p $W; cd $W
export NVC_NO_EVAL_ARENA=1
SRC="$W/ad9361_pkg.vhd $AD/accel/spectral_accel_off.vhd $AD/accel/spectral_accel_pkg.vhd $AD/rf_spectrum_pkg.vhd $AD/ad9361_spectral_pkg.vhd $AD/ad9361.vhd $AD/rf_spec_antenna.vhd $AD/ofdm_soft_pkg.vhd $AD/an2597_link.vhd"
(cd $AD && python3 -c "import ad9361_vhdl; open('$W/ad9361_pkg.vhd','w').write(ad9361_vhdl.emit())"
 python3 -c "
import arena_resolver, an2597_nvc
g = {$GPY'packets': '$PK', 'role': '0'}
open('$W/ref_resolver.vhd','w').write(arena_resolver.emit('an2597_link', an2597_nvc.WIRES, an2597_nvc.ARENA, g))")

# ref
mkdir -p ref; cd ref
$NVC -a $SRC ../ref_resolver.vhd
timed ref $NVC -e resolved_an2597_link -r > ref.log 2>&1 || { tail -20 ref.log; exit 1; }
grep 'AN2597 dist' ref.log | sed 's/.*AN2597/AN2597/' > ../ref.txt
cd $W

# plugin discovery + generation for one role, in its own directory; leaves resolved_an2597_link elaborated
gen() {   # dir role
    mkdir -p $1/gen; cd $1
    $NVC -a $SRC
    $NVC -e an2597_link $GFLAGS -gpackets=$PK -grole=$2
    NVC_RESOLVER_DIR=$PWD/gen NVC_RCMODE=none SV2VHDL_FORWARD_GENERICS=1 PYTHONPATH=$SV \
      $NVC -r --stop-time=1fs --load=$NB/lib/sv2vhdl/libresolver.so an2597_link > pass1.log 2>&1 || { tail -30 pass1.log; exit 1; }
    $NVC -a $(ls gen/*.vhd | grep -v _wrapper) gen/an2597_link_wrapper.vhd -e resolved_an2597_link
    grep -h '^-- arena band' gen/*.vhd || true
    cd $W
}

# mono
gen mono 0
(cd mono && timed mono $NVC -r --load=$LIBARENA resolved_an2597_link > run.log 2>&1) || { tail -30 mono/run.log; exit 1; }
grep 'AN2597 dist' mono/run.log | sed 's/.*AN2597/AN2597/' > mono.txt
diff ref.txt mono.txt > mono_vs_ref.diff && echo "MONO == HAND-WRITTEN (zero delay): $(wc -l < ref.txt) lines" \
  || echo "MONO differs from the zero-delay reference in $(grep -c "^>" mono_vs_ref.diff) of $(wc -l < ref.txt) lines (path delays)"

# federated
gen drone 1
gen ctrl 2
RUN='"'$NB/bin/nvc'", "--std=2040", "-L", "'$NB/lib'", "-r", "--load='$LIBARENA'", "resolved_an2597_link"'
cat > federation.json <<EOF
{
  "arenas": {"lab-2g4": {"vlan": "rf-lab"}},
  "bands": {"ism2g4": "lab-2g4"},
  "simulations": [
    {"name": "drone", "cwd": "$W/drone", "gen": "$W/drone/gen", "cmd": [$RUN]},
    {"name": "ctrl", "cwd": "$W/ctrl", "gen": "$W/ctrl/gen", "cmd": [$RUN]}
  ]
}
EOF
timed federated timeout 900 python3 $SV/arena_ctl.py run federation.json --logdir logs ${TRACE:+--trace} \
  || { for f in logs/*.log; do tail -20 $f; done; exit 1; }
grep -h libarena: logs/*.log || true
grep 'AN2597 dist' logs/ctrl.log | sed 's/.*AN2597/AN2597/' > fed.txt
cat fed.txt
diff mono.txt fed.txt && echo "FEDERATED == ONE SIMULATION (same resolver): $(wc -l < mono.txt) lines"
