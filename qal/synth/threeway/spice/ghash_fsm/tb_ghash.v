// tb_ghash.v
// ---------------------------------------------------------------------------
// Functional proof for the self-timed GHASH FSM against a NIST SP 800-38D
// vector. The expected values are NOT self-asserted: they are produced by
// ghash_ref.py (a python GHASH whose derived GCM tag was checked EQUAL to
// pycryptodome on NIST vectors) and read in at run time via $readmemh from
// "ghash_tv.hex". The vector here is GCM-spec Test Case 4 (20-byte AAD +
// 60-byte ciphertext -> 7 GHASH blocks, S = 698e57f70e6ecc7fd9463b7260a9ae5f).
//
// ghash_tv.hex flat layout (one 128-bit word per line, // comments skipped):
//   mem[0]           = H (hash subkey)
//   mem[1]           = nblocks N        (as a 128-bit word; low 8 bits used)
//   mem[2   .. 1+N]  = C_1 .. C_N       (the absorbed GHASH blocks)
//   mem[2+N .. 1+2N] = Y_1 .. Y_N       (running accumulator after each block)
//   mem[2+2N]        = S  (= Y_N, the GHASH output)
// ---------------------------------------------------------------------------
`timescale 1ns/1ps
module tb_ghash;
  reg          clk = 1'b0;
  reg          rst;
  integer      fails = 0;
  integer      i;

  // sized to the emitted TC4 vector: 2 + 2N + 1 = 17 words (N=7). ghash_ref.py
  // and this tb are a matched pair; a different vector resizes both together.
  reg  [127:0] mem [0:16];
  reg  [127:0] H;
  reg  [7:0]   N;
  reg  [127:0] S;

  // ---- DUT: self-timed GHASH FSM -----------------------------------------
  wire [7:0]   blk_idx;
  wire [127:0] Y;
  wire         done;
  reg  [127:0] blk;                  // block selected by the DUT's blk_idx
  reg  [7:0]   Nreg;

  ghash_fsm DUT(.clk(clk), .rst(rst), .H_in(H), .nblk(Nreg),
                .blk(blk), .blk_idx(blk_idx), .Y(Y), .done(done));

  // driver presents mem[2 + blk_idx] combinationally
  always @(*) blk = mem[2 + blk_idx];

  always #5 clk = ~clk;

  // ---- combinational round checker (proves each step vs validated trace) --
  reg  [127:0] chk_Yprev, chk_C;
  wire [127:0] chk_Ynext;
  ghash_round CHK(.Y(chk_Yprev), .C(chk_C), .H(H), .Ynext(chk_Ynext));

  initial begin
    $readmemh("ghash_tv.hex", mem);
    H = mem[0];
    N = mem[1][7:0];
    S = mem[2 + 2*N];
    Nreg = N;

    $display("GHASH self-timed FSM functional proof (vs validated python ref)");
    $display("-----------------------------------------------------------------");
    $display("H        = %h", H);
    $display("nblocks  = %0d", N);

    if (H === 128'hx || N === 8'hx || N == 8'd0) begin
      $display("ERROR: ghash_tv.hex missing/empty -- run ghash_ref.py first");
      fails = fails + 1;
      $finish;
    end

    // ---- (1) step-by-step: ghash_round cone vs every validated intermediate
    $display("[1] per-block round cone  (Y_i = (Y_{i-1} XOR C_i).H)");
    for (i = 0; i < N; i = i + 1) begin
      chk_Yprev = (i == 0) ? 128'd0 : mem[2 + N + (i-1)];
      chk_C     = mem[2 + i];
      #1;   // settle the combinational cone
      if (chk_Ynext === mem[2 + N + i]) begin
        $display("    block %0d  Y = %h  OK", i, chk_Ynext);
      end else begin
        $display("    block %0d  Y = %h  != ref %h  FAIL",
                 i, chk_Ynext, mem[2 + N + i]);
        fails = fails + 1;
      end
    end

    // ---- (2) full self-timed FSM run: absorb all N blocks, compare Y to S --
    $display("[2] full FSM stream -> S");
    @(negedge clk); rst = 1'b1;
    @(negedge clk); rst = 1'b0;
    wait (done);
    @(negedge clk);
    $display("    DUT Y (= S) = %h", Y);
    $display("    ref S       = %h", S);
    if (Y === S) begin
      $display("    RESULT: DUT S == validated reference  -> PASS");
    end else begin
      $display("    RESULT: DUT S != validated reference  -> FAIL");
      fails = fails + 1;
    end

    $display("-----------------------------------------------------------------");
    if (fails == 0)
      $display("ALL PASS (%0d/%0d steps + FSM): self-timed GHASH FSM computes real GHASH",
               N, N);
    else
      $display("FAILURES: %0d", fails);
    $finish;
  end

  // safety timeout
  initial begin
    #100000;
    $display("TIMEOUT: done never asserted");
    $finish;
  end
endmodule
