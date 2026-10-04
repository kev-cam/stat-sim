// sha256_fsm.v
// ---------------------------------------------------------------------------
// Self-timed SHA-256 round FSM wrapper (compression of one 512-bit block).
//
//   256b working state {a..h} + a rolling 16-word message-schedule window +
//   a 7-bit round counter, all in an edge-triggered DFF register; the deep
//   next-state cone is sha256_round (pure static CMOS). 64 rounds, then the
//   H-add. Wt = sigma1(W[t-2]) + W[t-7] + sigma0(W[t-15]) + W[t-16] produced
//   by the rolling window (w[0] always holds W[t]).
//      sigma0(x) = ROTR7(x)  ^ ROTR18(x) ^ SHR3(x)
//      sigma1(x) = ROTR17(x) ^ ROTR19(x) ^ SHR10(x)
//
// SELF-TIMED CAPTURE MODEL (what the SPICE round-slice anchors; here we use a
// synchronous clk so the LOGIC can be proven against a reference):
//   This wrapper is drawn as a conventional clocked FSM. The self-timed build
//   is BIT-IDENTICAL in function -- same sha256_round next-state cone, same
//   edge-triggered DFF state register (the dfrbp master-slave proven on the
//   4-bit accumulator) -- and differs ONLY in WHEN the capture edge fires:
//   instead of a free-running clock, a per-round DONE pulse fires once the
//   round's adder critical path (the T1/a'/e' 32-bit carry chains) has settled,
//   produced by an IN-KIND REPLICA delay (a replica carry chain), NOT a
//   per-op analog comparator -- the completion detector stays embedded/sparse
//   so it never re-dominates the duty crossover (the QAL-cliff). Because the
//   combinational function and the state element are identical, logic
//   correctness proven on this synchronous wrapper transfers verbatim to the
//   done-pulsed self-timed wrapper; only capture TIMING (hence energy-vs-duty)
//   differs, and that is what the transistor round-slice measures.
//
// Single 512-bit block per compression. Multi-block: feed Hout back as Hin.
// Bit order: block[511:480]=W0 ... block[31:0]=W15; Hin[255:224]=h0 ... [31:0]=h7.
// ---------------------------------------------------------------------------
module sha256_fsm(
  input          clk,
  input          rst,          // synchronous: load block + Hin, arm iteration
  input  [511:0] block,
  input  [255:0] Hin,
  output reg [255:0] Hout,
  output reg         done
);
  reg  [31:0] a, b, c, d, e, f, g, h;      // working registers
  reg  [31:0] w [0:15];                    // rolling schedule window, w[0]=W[t]
  reg  [6:0]  round;                       // 0..64
  reg  [31:0] s0h, s1h, s2h, s3h,          // saved initial H for the final add
              s4h, s5h, s6h, s7h;

  // ---- right-rotate / right-shift helpers --------------------------------
  function [31:0] rotr;
    input [31:0] x; input integer n;
    begin rotr = (x >> n) | (x << (32 - n)); end
  endfunction

  // ---- round-constant ROM K[0..63] (FIPS 180-4) --------------------------
  function [31:0] k_rom;
    input [5:0] i;
    begin
      case (i)
        6'd0:  k_rom=32'h428a2f98; 6'd1:  k_rom=32'h71374491;
        6'd2:  k_rom=32'hb5c0fbcf; 6'd3:  k_rom=32'he9b5dba5;
        6'd4:  k_rom=32'h3956c25b; 6'd5:  k_rom=32'h59f111f1;
        6'd6:  k_rom=32'h923f82a4; 6'd7:  k_rom=32'hab1c5ed5;
        6'd8:  k_rom=32'hd807aa98; 6'd9:  k_rom=32'h12835b01;
        6'd10: k_rom=32'h243185be; 6'd11: k_rom=32'h550c7dc3;
        6'd12: k_rom=32'h72be5d74; 6'd13: k_rom=32'h80deb1fe;
        6'd14: k_rom=32'h9bdc06a7; 6'd15: k_rom=32'hc19bf174;
        6'd16: k_rom=32'he49b69c1; 6'd17: k_rom=32'hefbe4786;
        6'd18: k_rom=32'h0fc19dc6; 6'd19: k_rom=32'h240ca1cc;
        6'd20: k_rom=32'h2de92c6f; 6'd21: k_rom=32'h4a7484aa;
        6'd22: k_rom=32'h5cb0a9dc; 6'd23: k_rom=32'h76f988da;
        6'd24: k_rom=32'h983e5152; 6'd25: k_rom=32'ha831c66d;
        6'd26: k_rom=32'hb00327c8; 6'd27: k_rom=32'hbf597fc7;
        6'd28: k_rom=32'hc6e00bf3; 6'd29: k_rom=32'hd5a79147;
        6'd30: k_rom=32'h06ca6351; 6'd31: k_rom=32'h14292967;
        6'd32: k_rom=32'h27b70a85; 6'd33: k_rom=32'h2e1b2138;
        6'd34: k_rom=32'h4d2c6dfc; 6'd35: k_rom=32'h53380d13;
        6'd36: k_rom=32'h650a7354; 6'd37: k_rom=32'h766a0abb;
        6'd38: k_rom=32'h81c2c92e; 6'd39: k_rom=32'h92722c85;
        6'd40: k_rom=32'ha2bfe8a1; 6'd41: k_rom=32'ha81a664b;
        6'd42: k_rom=32'hc24b8b70; 6'd43: k_rom=32'hc76c51a3;
        6'd44: k_rom=32'hd192e819; 6'd45: k_rom=32'hd6990624;
        6'd46: k_rom=32'hf40e3585; 6'd47: k_rom=32'h106aa070;
        6'd48: k_rom=32'h19a4c116; 6'd49: k_rom=32'h1e376c08;
        6'd50: k_rom=32'h2748774c; 6'd51: k_rom=32'h34b0bcb5;
        6'd52: k_rom=32'h391c0cb3; 6'd53: k_rom=32'h4ed8aa4a;
        6'd54: k_rom=32'h5b9cca4f; 6'd55: k_rom=32'h682e6ff3;
        6'd56: k_rom=32'h748f82ee; 6'd57: k_rom=32'h78a5636f;
        6'd58: k_rom=32'h84c87814; 6'd59: k_rom=32'h8cc70208;
        6'd60: k_rom=32'h90befffa; 6'd61: k_rom=32'ha4506ceb;
        6'd62: k_rom=32'hbef9a3f7; 6'd63: k_rom=32'hc67178f2;
      endcase
    end
  endfunction

  // ---- next-state cone (pure static combinational) -----------------------
  wire [31:0] kt = k_rom(round[5:0]);
  wire [31:0] na, nb, nc, nd, ne, nf, ng, nh;
  sha256_round RND(
    .a(a), .b(b), .c(c), .d(d), .e(e), .f(f), .g(g), .h(h),
    .Kt(kt), .Wt(w[0]),
    .na(na), .nb(nb), .nc(nc), .nd(nd), .ne(ne), .nf(nf), .ng(ng), .nh(nh)
  );

  // ---- message-schedule next word (W[t+16]) ------------------------------
  wire [31:0] sig0  = rotr(w[1], 7)  ^ rotr(w[1], 18) ^ (w[1] >> 3);
  wire [31:0] sig1  = rotr(w[14],17) ^ rotr(w[14],19) ^ (w[14] >> 10);
  wire [31:0] nextw = sig1 + w[9] + sig0 + w[0];

  integer i;
  always @(posedge clk) begin
    if (rst) begin
      {a,b,c,d,e,f,g,h}             <= Hin;
      {s0h,s1h,s2h,s3h,s4h,s5h,s6h,s7h} <= Hin;
      for (i = 0; i < 16; i = i + 1)
        w[i] <= block[511 - 32*i -: 32];
      round <= 7'd0;
      done  <= 1'b0;
    end else if (round < 7'd64) begin
      a<=na; b<=nb; c<=nc; d<=nd; e<=ne; f<=nf; g<=ng; h<=nh;
      for (i = 0; i < 15; i = i + 1)
        w[i] <= w[i+1];
      w[15] <= nextw;
      round <= round + 7'd1;
      if (round == 7'd63) begin
        // 64th round just captured into na..nh -> emit H + working state.
        Hout <= { s0h+na, s1h+nb, s2h+nc, s3h+nd,
                  s4h+ne, s5h+nf, s6h+ng, s7h+nh };
        done <= 1'b1;
      end
    end
  end
endmodule
