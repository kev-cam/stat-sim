// ghash_fsm.v
// ---------------------------------------------------------------------------
// Self-timed static-CMOS GHASH FSM wrapper (the authentication half of
// GCM-AES / 802.1AE MACsec). Absorbs a stream of N 128-bit blocks:
//
//     Y_0 = 0 ;  Y_i = (Y_{i-1} XOR C_i) . H  mod P ;  output S = Y_N
//
//   State held in edge-triggered DFFs (the dfrbp-class master-slave proven on
//   the 4-bit accumulator, SHA-256 and AES-128): the 128-bit accumulator Y,
//   the 128-bit hash subkey H (held constant, loaded at reset), and an 8-bit
//   block counter. The next-state cone is ghash_round (pure static, carry-LESS
//   XOR/AND -- NO adder, NO S-box). Register-LIGHT like AES (~256 held bits:
//   128 Y + 128 H), NOT register-heavy like SHA (774) -> the clock-floor-shed
//   win is the AES-class (smaller) one; the current-sense DONE win is the
//   sharpest of the three (shallowest, most regular settle).
//
// SELF-TIMED CAPTURE MODEL (what the stat-sim slice composes; a synchronous clk
// is used HERE only so the LOGIC can be proven against NIST):
//   This wrapper is drawn as a conventional clocked FSM. The self-timed build
//   is BIT-IDENTICAL in function -- same ghash_round next-state cone, same
//   edge-triggered DFF state register -- and differs ONLY in WHEN the capture
//   edge fires. Instead of a free-running clock, a per-block DONE pulse fires
//   once the carry-less multiply cone has settled, produced by an IN-KIND
//   REPLICA delay line (a dummy ghash_gfmul cone + DFF loaded identically),
//   NOT a per-op analog comparator -- so the completion detector stays
//   embedded/sparse and never re-dominates the duty crossover (the QAL cliff).
//   The replica delay models the carry-less XOR-tree depth (NOT a comparator),
//   so synchronous logic correctness transfers VERBATIM to the done-pulsed
//   self-timed build; only capture TIMING (hence energy-vs-duty) differs.
//
//   GHASH idles between MACsec frames -> the low-duty regime where shedding the
//   clock floor is the win; per-op it is ~parity with clocked static CMOS.
//
// INTERFACE (streaming): the block to absorb this cycle is presented on `blk`,
// selected by the FSM's own `blk_idx` output (the driver supplies
// blk = mem[blk_idx]). `nblk` = number of blocks (loaded at reset). H loaded at
// reset. Y init 0. `done` pulses high and Y holds S once all blocks absorbed.
// (Parallel form: ONE ghash_round/gfmul evaluation per block = one "round".
//  A bit-serial form would instead expand each gfmul into 128 shallow shift-
//  and-conditional-XOR micro-steps; this file uses the parallel cone.)
// ---------------------------------------------------------------------------
module ghash_fsm(
  input              clk,
  input              rst,      // synchronous: Y<-0, H<-H_in, counter<-0
  input      [127:0] H_in,     // hash subkey = AES_K(0^128)
  input      [7:0]   nblk,     // number of blocks to absorb (>=1 for GHASH)
  input      [127:0] blk,      // block C_i selected by blk_idx (from driver)
  output reg [7:0]   blk_idx,  // index of the block wanted THIS cycle
  output reg [127:0] Y,        // accumulator; == S (GHASH output) when done
  output reg         done
);
  reg [127:0] Hreg;            // held hash subkey

  // ---- next-state cone (pure static, carry-less) --------------------------
  wire [127:0] y_next;
  ghash_round RND(.Y(Y), .C(blk), .H(Hreg), .Ynext(y_next));

  always @(posedge clk) begin
    if (rst) begin
      Y       <= 128'd0;
      Hreg    <= H_in;
      blk_idx <= 8'd0;
      done    <= (nblk == 8'd0);   // empty stream (not used by GHASH): done now
    end else if (blk_idx < nblk) begin
      Y       <= y_next;           // absorb block[blk_idx]
      blk_idx <= blk_idx + 8'd1;
      if (blk_idx + 8'd1 == nblk)  // last block absorbed on this edge
        done  <= 1'b1;
    end
  end
endmodule
