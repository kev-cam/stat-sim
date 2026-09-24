#!/bin/bash
# Regular-logic SHA256 baseline: yosys synth to IHP SG13G2 stdcells + OpenSTA timing + power.
# RTL = ldx Sha256.v (standard clocked SHA-256, one round/cycle). Same PDK as the QAL device sims.
set -e
RTL=/usr/local/src/ldx/examples/verilator-bench/sha256/Sha256.v
LIB=/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib
cd "$(dirname "$0")"
yosys -q -p "read_verilog $RTL; hierarchy -top Sha256; synth -top Sha256 -flatten;   dfflibmap -liberty $LIB; abc -liberty $LIB; opt_clean;   tee -o stat.txt stat -liberty $LIB; write_verilog -noattr sha_mapped.v"
# timing (critical path -> max clock)
printf 'read_liberty %s\nread_verilog sha_mapped.v\nlink_design Sha256\ncreate_clock -name clk -period 20 [get_ports clk]\nreport_checks -path_delay max -group_count 1 -digits 3\n' "$LIB" | sta -no_splash -exit /dev/stdin
