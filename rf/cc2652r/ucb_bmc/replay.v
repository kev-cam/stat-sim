// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
//
// replay: what the translation of BMC to VHDL is worth.  ucb_bmc_radio (generic trace) writes, clock by
// clock, what it put on the design's inputs and what the translated design showed; this puts the same
// inputs on the Verilog and compares what that shows, before each rising edge as the trace was taken.
//
//   iverilog -g2012 -o replay.vvp -s replay replay.v BMC.v && vvp replay.vvp +trace=<file>
//
// A bit that is not 1 counts as 0 on both sides.  Where the Verilog's value has unknown bits (the design
// reads registers that have no reset: the modulator's filter at the start of the first packet, state
// before the first reset) a difference is counted apart: the translation computes with unknowns as 0.
`timescale 1ns / 1ps
module replay;
  reg clk = 0, rst = 0;
  reg [7:0] adc_i = 0, adc_q = 0;
  reg cmd_valid = 0, rresp_valid = 0, rdata_valid = 0, lut_valid = 0;
  reg [3:0] cmd_prim = 0, cmd_sec = 0, lut_id = 0;
  reg [23:0] cmd_data = 0;
  reg [31:0] cmd_add = 0, rdata_bits = 0;
  reg [8:0] rresp_bytes = 0;
  reg [5:0] lut_addr = 0;
  reg [21:0] lut_value = 0;
  wire tx_on, cmd_ready, rreq_valid, rresp_ready, rdata_ready, wreq_valid;
  wire irq_rx_error, irq_rx_start, irq_rx_finish, irq_tx_error, irq_tx_finish;
  wire msg_rx_error_valid, msg_rx_finish_valid, msg_tx_error_valid;
  wire [7:0] cap_mod; wire [9:0] cap_coarse; wire [5:0] mod_index; wire [2:0] st_main; wire [1:0] st_tx;
  wire [8:0] rreq_bytes; wire [31:0] wreq_addr, wreq_data, msg_rx_finish, msg_rx_error; wire [2:0] wreq_bytes;

  BMC dut (.clock(clk), .reset(rst), .io_adc_clock(clk),
    .io_analog_data_tx_vco_cap_coarse(cap_coarse), .io_analog_data_tx_vco_cap_mod(cap_mod),
    .io_analog_data_rx_i_data(adc_i), .io_analog_data_rx_i_valid(1'b1),
    .io_analog_data_rx_q_data(adc_q), .io_analog_data_rx_q_valid(1'b1),
    .io_analog_offChipMode_tx(tx_on),
    .io_cmd_ready(cmd_ready), .io_cmd_valid(cmd_valid), .io_cmd_bits_inst_primaryInst(cmd_prim),
    .io_cmd_bits_inst_secondaryInst(cmd_sec), .io_cmd_bits_inst_data(cmd_data), .io_cmd_bits_additionalData(cmd_add),
    .io_dma_readReq_ready(1'b1), .io_dma_readReq_valid(rreq_valid), .io_dma_readReq_bits_totalBytes(rreq_bytes),
    .io_dma_readResp_ready(rresp_ready), .io_dma_readResp_valid(rresp_valid), .io_dma_readResp_bits_bytesRead(rresp_bytes),
    .io_dma_readData_ready(rdata_ready), .io_dma_readData_valid(rdata_valid), .io_dma_readData_bits(rdata_bits),
    .io_dma_writeReq_ready(1'b1), .io_dma_writeReq_valid(wreq_valid), .io_dma_writeReq_bits_addr(wreq_addr),
    .io_dma_writeReq_bits_data(wreq_data), .io_dma_writeReq_bits_totalBytes(wreq_bytes),
    .io_interrupt_rxError(irq_rx_error), .io_interrupt_rxStart(irq_rx_start), .io_interrupt_rxFinish(irq_rx_finish),
    .io_interrupt_txError(irq_tx_error), .io_interrupt_txFinish(irq_tx_finish),
    .io_lutCmd_valid(lut_valid), .io_lutCmd_bits_lut(lut_id), .io_lutCmd_bits_address(lut_addr), .io_lutCmd_bits_value(lut_value),
    .io_firCmd_valid(1'b0), .io_firCmd_bits_fir(4'd0), .io_firCmd_bits_coeff(6'd0), .io_firCmd_bits_value(22'd0),
    .io_messages_rxErrorMessage_ready(1'b1), .io_messages_rxErrorMessage_valid(msg_rx_error_valid),
    .io_messages_rxErrorMessage_bits(msg_rx_error),
    .io_messages_rxFinishMessage_ready(1'b1), .io_messages_rxFinishMessage_valid(msg_rx_finish_valid),
    .io_messages_rxFinishMessage_bits(msg_rx_finish),
    .io_messages_txErrorMessage_ready(1'b1), .io_messages_txErrorMessage_valid(msg_tx_error_valid),
    .io_tuning_i_AGC_control_sampleWindow(8'd0), .io_tuning_i_AGC_control_idealPeakToPeak(8'd0),
    .io_tuning_i_AGC_control_toleranceP2P(8'd0), .io_tuning_i_AGC_control_gainInc(8'd0),
    .io_tuning_i_AGC_control_gainDec(8'd0), .io_tuning_i_AGC_control_reset(1'b0), .io_tuning_i_AGC_useAGC(1'b0),
    .io_tuning_i_DCO_control_gain(9'd0), .io_tuning_i_DCO_control_reset(1'b0), .io_tuning_i_DCO_useDCO(1'b0),
    .io_tuning_q_AGC_control_sampleWindow(8'd0), .io_tuning_q_AGC_control_idealPeakToPeak(8'd0),
    .io_tuning_q_AGC_control_toleranceP2P(8'd0), .io_tuning_q_AGC_control_gainInc(8'd0),
    .io_tuning_q_AGC_control_gainDec(8'd0), .io_tuning_q_AGC_control_reset(1'b0), .io_tuning_q_AGC_useAGC(1'b0),
    .io_tuning_q_DCO_control_gain(9'd0), .io_tuning_q_DCO_control_reset(1'b0), .io_tuning_q_DCO_useDCO(1'b0),
    .io_tuning_debug_enabled(1'b0),
    .io_state_txState(st_tx), .io_state_mainControllerState(st_main), .io_state_modIndex(mod_index),
    .io_ifCounter_input_ifTickThreshold(32'd0), .io_ifCounter_input_control_restartCounter(1'b0));

  // a bit that is not 1 is 0
  function [31:0] known(input [31:0] v);
    integer i;
    begin
      for (i = 0; i < 32; i = i + 1) known[i] = (v[i] === 1'b1);
    end
  endfunction

  integer fd, got, n = 0, bad = 0, unk = 0;
  integer f_in, a_i, a_q, c_prim, c_sec, c_data, c_add_h, c_add_l, r_bytes, d_h, d_l, l_id, l_addr, l_value;
  integer o_flags, o_cap, o_coarse, o_mod, o_main, o_tx, o_rreq, o_waddr, o_wd_h, o_wd_l, o_wbytes, o_fin, o_err;
  reg [1023:0] name;
  reg [13:0] flags;

  task differs(input [255:0] what, input unknown, input integer is, input integer want);
    begin
      if (unknown)
        unk = unk + 1;
      else begin
        bad = bad + 1;
        if (bad <= 20) $display("clock %0d: %0s is %0d, in the trace %0d", n, what, is, want);
      end
    end
  endtask

  initial begin
    if (!$value$plusargs("trace=%s", name)) begin $display("+trace=<file>"); $finish; end
    fd = $fopen(name, "r");
    if (fd == 0) begin $display("no trace %0s", name); $finish; end
    forever begin
      got = $fscanf(fd, "%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",
                    f_in, a_i, a_q, c_prim, c_sec, c_data, c_add_h, c_add_l, r_bytes, d_h, d_l, l_id, l_addr, l_value,
                    o_flags, o_cap, o_coarse, o_mod, o_main, o_tx, o_rreq, o_waddr, o_wd_h, o_wd_l, o_wbytes, o_fin, o_err);
      if (got != 27) begin
        $display("REPLAY %0d clocks, %0d differences, and %0d where the Verilog has unknown bits", n, bad, unk);
        $finish;
      end
      rst = f_in[4]; cmd_valid = f_in[3]; rresp_valid = f_in[2]; rdata_valid = f_in[1]; lut_valid = f_in[0];
      adc_i = a_i; adc_q = a_q; cmd_prim = c_prim; cmd_sec = c_sec; cmd_data = c_data;
      cmd_add = {c_add_h[15:0], c_add_l[15:0]}; rresp_bytes = r_bytes; rdata_bits = {d_h[15:0], d_l[15:0]};
      lut_id = l_id; lut_addr = l_addr; lut_value = l_value;
      #10;
      flags = {tx_on, cmd_ready, rreq_valid, rresp_ready, rdata_ready, wreq_valid, irq_rx_error, irq_rx_start,
               irq_rx_finish, irq_tx_error, irq_tx_finish, msg_rx_error_valid, msg_rx_finish_valid, msg_tx_error_valid};
      if (known(flags) !== o_flags) differs("flags", $isunknown(flags), known(flags), o_flags);
      if (known(cap_mod) !== o_cap) differs("cap_mod", $isunknown(cap_mod), known(cap_mod), o_cap);
      if (known(cap_coarse) !== o_coarse) differs("cap_coarse", $isunknown(cap_coarse), known(cap_coarse), o_coarse);
      if (known(mod_index) !== o_mod) differs("modIndex", $isunknown(mod_index), known(mod_index), o_mod);
      if (known(st_main) !== o_main) differs("controller state", $isunknown(st_main), known(st_main), o_main);
      if (known(st_tx) !== o_tx) differs("modulator state", $isunknown(st_tx), known(st_tx), o_tx);
      if (known(rreq_bytes) !== o_rreq) differs("read request bytes", $isunknown(rreq_bytes), known(rreq_bytes), o_rreq);
      if (known(wreq_addr[15:0]) !== o_waddr) differs("write address", $isunknown(wreq_addr[15:0]), known(wreq_addr[15:0]), o_waddr);
      if (known(wreq_data[31:16]) !== o_wd_h) differs("write data high", $isunknown(wreq_data[31:16]), known(wreq_data[31:16]), o_wd_h);
      if (known(wreq_data[15:0]) !== o_wd_l) differs("write data low", $isunknown(wreq_data[15:0]), known(wreq_data[15:0]), o_wd_l);
      if (known(wreq_bytes) !== o_wbytes) differs("write bytes", $isunknown(wreq_bytes), known(wreq_bytes), o_wbytes);
      if (known(msg_rx_finish[15:0]) !== o_fin) differs("finish message", $isunknown(msg_rx_finish[15:0]), known(msg_rx_finish[15:0]), o_fin);
      if (known(msg_rx_error[15:0]) !== o_err) differs("error message", $isunknown(msg_rx_error[15:0]), known(msg_rx_error[15:0]), o_err);
      n = n + 1;
      clk = 1; #15.625; clk = 0; #5.625;
    end
  end
endmodule
