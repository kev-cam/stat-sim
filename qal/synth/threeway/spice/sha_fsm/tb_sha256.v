// tb_sha256.v
// ---------------------------------------------------------------------------
// Functional differential proof for the self-timed SHA-256 round FSM.
// Hashes "abc" and the empty string (single padded 512-bit block each) and
// compares the 256-bit digest to the FIPS 180-4 reference produced by python
// hashlib (NOT self-asserted):
//     abc   -> ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
//     ""    -> e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
// ---------------------------------------------------------------------------
`timescale 1ns/1ps
module tb_sha256;
  reg          clk = 1'b0;
  reg          rst;
  reg  [511:0] block;
  reg  [255:0] Hin;
  wire [255:0] Hout;
  wire         done;
  integer      fails = 0;

  sha256_fsm DUT(.clk(clk), .rst(rst), .block(block), .Hin(Hin),
                 .Hout(Hout), .done(done));

  always #5 clk = ~clk;

  // SHA-256 initial hash value (FIPS 180-4, section 5.3.3).
  localparam [255:0] IV =
    256'h6a09e667_bb67ae85_3c6ef372_a54ff53a_510e527f_9b05688c_1f83d9ab_5be0cd19;

  // hashlib reference digests.
  localparam [255:0] REF_ABC =
    256'hba7816bf_8f01cfea_414140de_5dae2223_b00361a3_96177a9c_b410ff61_f20015ad;
  localparam [255:0] REF_EMPTY =
    256'he3b0c442_98fc1c14_9afbf4c8_996fb924_27ae41e4_649b934c_a495991b_7852b855;

  task run_block;
    input [511:0] blk;
    begin
      @(negedge clk); block = blk; Hin = IV; rst = 1'b1;
      @(negedge clk); rst = 1'b0;
      wait (done);
      @(negedge clk);
    end
  endtask

  task check;
    input [255:0] got;
    input [255:0] exp;
    input [127:0] name;
    begin
      $display("%0s digest = %h", name, got);
      $display("%0s expect = %h", name, exp);
      if (got === exp) $display("%0s PASS", name);
      else begin $display("%0s FAIL", name); fails = fails + 1; end
    end
  endtask

  initial begin
    // "abc" : 0x61_62_63, append 0x80, pad zeros, 64-bit length = 24 bits.
    run_block({32'h61626380, {14{32'h00000000}}, 32'h00000018});
    check(Hout, REF_ABC, "abc  ");

    // "" : append 0x80, pad zeros, 64-bit length = 0.
    run_block({32'h80000000, {15{32'h00000000}}});
    check(Hout, REF_EMPTY, "empty");

    $display("-----------------------------------------");
    if (fails == 0) $display("ALL PASS (2/2) vs hashlib reference");
    else            $display("FAILURES: %0d", fails);
    $finish;
  end
endmodule
