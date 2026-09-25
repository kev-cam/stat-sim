#!/bin/bash
# Regenerate the Vortex STATIC characterization netlists from the RTL that
# rtlmeter actually simulates (so the static half composes with the dynamic half).
#
# IMPORTANT: this uses /usr/local/src/rtlmeter/designs/Vortex/src, NOT
# /home/claude/vortex. They are DIFFERENT revisions:
#   rtlmeter descriptor.yaml pins vortex e80ee2c81909ecf118fa1b8842613af4b26ab4a1
#   /home/claude/vortex is at d76b7f24d (that sha is not even an object there)
# The existing nulex netlists (mapper/alu/work/alu.json, mapper/exec/work/exec.json)
# were built from /home/claude/vortex, so they are NOT directly comparable to these.
#
# Config = rtlmeter "mini": NUM_CLUSTERS=1 NUM_CORES=1 NUM_WARPS=4 NUM_THREADS=4.
set -e
SRC=/usr/local/src/rtlmeter/designs/Vortex/src
SV2V=/home/claude/tools/bin/sv2v            # v0.0.13
OUT="${1:-/tmp/vxstat}"
mkdir -p "$OUT"
cd "$SRC"

# -DSYNTHESIS: VX_platform.vh only defines IGNORE_UNUSED_BEGIN etc. under it.
# -DXSIM    : skips the SVA `default disable iff` in fpnew/rr_arb_tree.sv:116 that
#             sv2v 0.0.13 cannot parse. XSIM appears ONLY in that file (verified).
# top=Vortex: Vortex.sv has PLAIN ports, so sv2v accepts it as top. VX_core and
#             every other interface-bearing module CANNOT be a top (sv2v errors)
#             and gets INLINED into its parent -- see the note at the bottom.
$SV2V --top=Vortex \
  -DSYNTHESIS=1 -DXLEN_32=1 -DFPU_FPNEW=1 -DNDEBUG=1 -DXSIM=1 \
  -DNUM_CLUSTERS=1 -DNUM_CORES=1 -DNUM_WARPS=4 -DNUM_THREADS=4 \
  -I. -Ifpnew \
  VX_gpu_pkg.sv VX_fpu_pkg.sv VX_trace_pkg.sv \
  fpnew/fpnew_pkg.sv fpnew/cf_math_pkg.sv fpnew/defs_div_sqrt_mvp.sv fpnew/control_mvp.sv \
  $(ls *.sv | grep -v '^tb.sv$' | grep -v '_pkg.sv$') \
  $(ls fpnew/*.sv | grep -v '_pkg.sv$' | grep -v 'cf_math\|defs_div_sqrt\|control_mvp') \
  -w "$OUT/vortex_mini.v"

# strip unreachable elaboration-error branches ($finish outside initial block)
sed -e '/\$display("Fatal/d' -e '/\$finish(1);/d' \
    "$OUT/vortex_mini.v" > "$OUT/vortex_mini_synth.v"

cd "$OUT"
# (1) hierarchical: per-module counts for modules that SURVIVED as modules
yosys -q -p 'read_verilog -sv vortex_mini_synth.v; hierarchy -check -top Vortex; proc;
             opt_expr; opt_clean; memory_collect; opt -full; techmap; opt -full;
             simplemap; opt_clean; tee -o stat_hier.txt stat; write_json vortex_hier.json'

# (2) FLATTENED from the top -- the authoritative one. yosys renames each pulled-up
#     cell to  $flatten\<instance.path>.<leaf>  so every gate carries its exact RTL
#     location AND is parameterised exactly as the design instantiates it.
#     Do NOT synthesise a submodule standalone: VX_multiplier, VX_serial_div,
#     fpnew_top_* etc. all have parameters with DEFAULTS that differ from the
#     in-context values (VX_multiplier defaults to A_WIDTH=1 -> 1 cell vs 9,202
#     in context; fpnew_top defaults to RV64D, not Vortex's RV32F).
yosys -q -p 'read_verilog -sv vortex_mini_synth.v; hierarchy -check -top Vortex; proc;
             opt_expr; opt_clean; memory_collect; opt -full; techmap; opt -full;
             simplemap; opt_clean; flatten; opt_clean -purge;
             tee -o stat_flat.txt stat -top Vortex; write_json vortex_flat.json'

echo "now:  python3 flat_islands.py $OUT/vortex_flat.json Vortex"
echo "      python3 partition.py    $OUT/vortex_hier.json Vortex"
echo "      python3 boundary.py     $OUT/vortex_hier.json Vortex 7"
