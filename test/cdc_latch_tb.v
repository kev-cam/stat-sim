// cdc_latch_tb.v -- regular Verilog testbench for the stat-sim CDC latch demo.
// A latch clock and a DATA line that is itself a clock at a slightly different
// frequency (01XZ logic). The VHDL DUT's stat-sim inverters lift the 01XZ logic
// into the probability domain and the stat-sim latch flags the CDC metastability
// risk (it reports a warning each time the data is unsettled as the latch closes).
//
// NOTE: this is the requested Verilog form, but a Verilog module instantiating a
// VHDL entity under nvc --std=2040 is a known toolchain bug -- see
// /usr/local/src/sv2ghdl/BUG_2040_cross_instantiation.md (cross-instantiation,
// reported 2026-05-28). Pure Verilog and pure VHDL both simulate; only the
// cross-language instance binding is the gap. To RUN the demo today use
// test/cdc_latch_tb.vhd -- the identical testbench with std_ulogic (01XZ)
// stimulus, exercising the same stat-sim inverters + latch.
`timescale 1ns/1ps
module cdc_latch_tb;
  reg clk_v = 1'b0;            // latch clock : 2.00 ns period
  reg dat_v = 1'b0;            // data clock  : 2.20 ns period (asynchronous)

  always #1.00 clk_v = ~clk_v;
  always #1.10 dat_v = ~dat_v;

  // VHDL DUT: stat-sim inverters (01XZ -> probability) + metastable latch
  cdc_latch_dut dut (.clk_v(clk_v), .dat_v(dat_v));

  initial #200 $finish;
endmodule
