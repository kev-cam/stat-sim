#!/bin/bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
#
# emit.sh <directory>: BMC.v, the Verilog of the Berkeley baseband-modem's baseband, modem and
# controller, in <directory>/out.  Fetches the design (github.com/ucb-bar/baseband-modem), the DMA
# whose streams it uses (github.com/ucb-ee290c/sp21-dma) and rocket-chip v1.6 into <directory>, and
# builds them with sbt: needs git, a JDK between 8 and 17 (JAVA_HOME) and sbt (SBT, or sbt on PATH).
# The first run downloads Scala and Chisel and compiles rocket-chip: some minutes.
set -e
here=$(cd "$(dirname "$0")" && pwd)
dir=${1:?emit.sh <directory>}
mkdir -p "$dir"
dir=$(cd "$dir" && pwd)
export GIT_TERMINAL_PROMPT=0
cd "$dir"
[ -d baseband-modem ] || git clone -q --depth 1 https://github.com/ucb-bar/baseband-modem.git
[ -d sp21-dma ] || git clone -q --depth 1 https://github.com/ucb-ee290c/sp21-dma.git
if [ ! -d rocket-chip ]; then
    git clone -q --depth 1 --branch v1.6 https://github.com/chipsalliance/rocket-chip.git
    (cd rocket-chip && git submodule update -q --init --depth 1 hardfloat api-config-chipsalliance)
fi
# sbt writes its targets beside the build: a copy of the project, not the one in the source tree
rm -rf "$dir/bmc/src" && mkdir -p "$dir/bmc/project"
cp "$here/build.sbt" "$dir/bmc/" && cp -r "$here/src" "$dir/bmc/" && cp "$here/project/build.properties" "$dir/bmc/project/"
[ -z "$JAVA_HOME" ] || PATH=$JAVA_HOME/bin:$PATH
cd "$dir/bmc"
UCB_SRC="$dir" ${SBT:-sbt} -batch -J-Xmx6g -J-Xss8m "bmc/runMain emit.Emit $dir/out"
ls -l "$dir/out/BMC.v"
