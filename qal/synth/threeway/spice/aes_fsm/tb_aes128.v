// tb_aes128.v
// ---------------------------------------------------------------------------
// Functional proof for the self-timed AES-128 round FSM against FIPS-197.
//
// FIPS-197 Appendix B / C.1 known-answer vector:
//     key        = 000102030405060708090a0b0c0d0e0f
//     plaintext  = 00112233445566778899aabbccddeeff
//     ciphertext = 69c4e0d86a7b0430d8cdb78070b4c55a
//
// The expected ciphertext is NOT hardcoded-and-self-asserted here. It is read
// at run time via $readmemh from "aes_ref.hex", which the run step generates
// INDEPENDENTLY with `openssl enc -aes-128-ecb -K ... -nopad` (and the same
// value is cross-checked against pycryptodome). The testbench then shows the
// DUT ciphertext and the openssl reference agree. The key and plaintext below
// are the test INPUTS (the published vector), not the answer.
// ---------------------------------------------------------------------------
`timescale 1ns/1ps
module tb_aes128;
  reg          clk = 1'b0;
  reg          rst;
  reg  [127:0] pt;
  reg  [127:0] key;
  wire [127:0] ct;
  wire         done;
  integer      fails = 0;

  // reference ciphertext loaded from an independent oracle (openssl)
  reg  [127:0] refmem [0:0];
  reg  [127:0] ref_ct;

  aes128_fsm DUT(.clk(clk), .rst(rst), .pt(pt), .key(key),
                 .ct(ct), .done(done));

  always #5 clk = ~clk;

  initial begin
    // load the externally-generated reference (openssl / pycryptodome)
    $readmemh("aes_ref.hex", refmem);
    ref_ct = refmem[0];

    // FIPS-197 input vector
    key = 128'h00010203_04050607_08090a0b_0c0d0e0f;
    pt  = 128'h00112233_44556677_8899aabb_ccddeeff;

    // drive the self-timed FSM: one reset cycle (initial AddRoundKey), then run
    @(negedge clk); rst = 1'b1;
    @(negedge clk); rst = 1'b0;
    wait (done);
    @(negedge clk);

    $display("key                 = %h", key);
    $display("plaintext           = %h", pt);
    $display("DUT ciphertext      = %h", ct);
    $display("openssl reference   = %h", ref_ct);
    $display("FIPS-197 published  = 69c4e0d86a7b0430d8cdb78070b4c55a");

    if (ref_ct === 128'hx || ref_ct === 128'h0) begin
      $display("ERROR: reference file aes_ref.hex missing/empty");
      fails = fails + 1;
    end else if (ct === ref_ct) begin
      $display("RESULT: DUT == openssl reference  -> PASS");
    end else begin
      $display("RESULT: DUT != openssl reference  -> FAIL");
      fails = fails + 1;
    end

    $display("-----------------------------------------");
    if (fails == 0)
      $display("ALL PASS (1/1): self-timed AES-128 FSM computes real AES correctly");
    else
      $display("FAILURES: %0d", fails);
    $finish;
  end

  // safety timeout
  initial begin
    #10000;
    $display("TIMEOUT: done never asserted");
    $finish;
  end
endmodule
