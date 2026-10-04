// aes_round.v
// ---------------------------------------------------------------------------
// ONE AES-128 round as PURE STATIC combinational next-state logic (FIPS-197
// Sec. 5.1). Ordinary Verilog -> maps to static CMOS gates: the S-box cells
// (see aes_sbox.v), fixed wiring for ShiftRows, and GF(2^8) xtime + XOR trees
// for MixColumns, then a 128-bit XOR for AddRoundKey. PRECHARGE-FREE, NOT
// domino: this cone holds no internal state and dissipates only when an input
// bit toggles. It is the deep next-state cone that the self-timed FSM clocks
// with a DONE pulse once its critical path (S-box substitution depth +
// MixColumns XOR tree -- NOT a long ripple-carry; AES has no wide adder) has
// settled, produced by an in-kind replica delay, not a per-op comparator.
//
// Round pipeline order (FIPS-197 Sec. 5.1):
//     SubBytes -> ShiftRows -> MixColumns -> AddRoundKey
// The FINAL round (round 10) OMITS MixColumns; the `final_round` port selects
// that path. MixColumns is shallow (xtime is one conditional XOR; each output
// byte is a XOR of <=4 partial products), so the power-settle "done" is SHARPER
// here than in SHA's 32-bit carry chains -- good for current-sense completion.
//
// Byte/state convention (consistent across all modules, big-endian / FIPS
// column-major): state byte index i (i=0..15) occupies st[127-8*i -: 8]; the
// AES 4x4 array position is row r = i mod 4, column c = i / 4, i.e. i = r + 4c.
// ---------------------------------------------------------------------------
module aes_round(
  input  [127:0] st,          // current state (round input)
  input  [127:0] rkey,        // round key for THIS round
  input          final_round, // 1 => omit MixColumns (round 10)
  output [127:0] nst          // next state (round output)
);
  genvar gi;

  // ---- SubBytes: 16 parallel S-boxes, one per state byte ------------------
  wire [7:0] sb  [0:15];   // raw state bytes
  wire [7:0] sub [0:15];   // substituted bytes
  generate
    for (gi = 0; gi < 16; gi = gi + 1) begin : SBOX
      assign sb[gi] = st[127 - 8*gi -: 8];
      aes_sbox U(.in(sb[gi]), .o(sub[gi]));
    end
  endgenerate

  // ---- ShiftRows: fixed byte permutation (pure wiring, zero energy) -------
  // out(r,c) = in(r,(c+r) mod 4); with i = r+4c this is the standard map:
  //   0 5 10 15 | 4 9 14 3 | 8 13 2 7 | 12 1 6 11
  wire [7:0] sr [0:15];
  assign sr[0]  = sub[0];   assign sr[1]  = sub[5];   assign sr[2]  = sub[10];  assign sr[3]  = sub[15];
  assign sr[4]  = sub[4];   assign sr[5]  = sub[9];   assign sr[6]  = sub[14];  assign sr[7]  = sub[3];
  assign sr[8]  = sub[8];   assign sr[9]  = sub[13];  assign sr[10] = sub[2];   assign sr[11] = sub[7];
  assign sr[12] = sub[12];  assign sr[13] = sub[1];   assign sr[14] = sub[6];   assign sr[15] = sub[11];

  // ---- MixColumns over GF(2^8), reducing polynomial 0x11b -----------------
  // xtime(x) = multiply-by-2 in GF(2^8); mul3(x) = xtime(x) ^ x.
  function [7:0] xtime;
    input [7:0] x;
    begin
      xtime = (x[7]) ? ((x << 1) ^ 8'h1b) : (x << 1);
    end
  endfunction
  function [7:0] mul3;
    input [7:0] x;
    begin
      mul3 = xtime(x) ^ x;
    end
  endfunction

  // Per column c (bytes b0=sr[4c], b1=sr[4c+1], b2=sr[4c+2], b3=sr[4c+3]):
  //   m0 = 2*b0 ^ 3*b1 ^   b2 ^   b3
  //   m1 =   b0 ^ 2*b1 ^ 3*b2 ^   b3
  //   m2 =   b0 ^   b1 ^ 2*b2 ^ 3*b3
  //   m3 = 3*b0 ^   b1 ^   b2 ^ 2*b3
  wire [7:0] mc [0:15];
  generate
    for (gi = 0; gi < 4; gi = gi + 1) begin : MIXCOL
      wire [7:0] b0 = sr[4*gi+0];
      wire [7:0] b1 = sr[4*gi+1];
      wire [7:0] b2 = sr[4*gi+2];
      wire [7:0] b3 = sr[4*gi+3];
      assign mc[4*gi+0] = xtime(b0) ^ mul3(b1) ^ b2        ^ b3;
      assign mc[4*gi+1] = b0        ^ xtime(b1) ^ mul3(b2) ^ b3;
      assign mc[4*gi+2] = b0        ^ b1        ^ xtime(b2) ^ mul3(b3);
      assign mc[4*gi+3] = mul3(b0)  ^ b1        ^ b2        ^ xtime(b3);
    end
  endgenerate

  // ---- select MixColumns (rounds 1..9) vs bypass (final round 10) ---------
  wire [127:0] sr_vec = { sr[0], sr[1], sr[2], sr[3], sr[4], sr[5], sr[6], sr[7],
                          sr[8], sr[9], sr[10],sr[11],sr[12],sr[13],sr[14],sr[15] };
  wire [127:0] mc_vec = { mc[0], mc[1], mc[2], mc[3], mc[4], mc[5], mc[6], mc[7],
                          mc[8], mc[9], mc[10],mc[11],mc[12],mc[13],mc[14],mc[15] };
  wire [127:0] mixed  = final_round ? sr_vec : mc_vec;

  // ---- AddRoundKey: 128-bit XOR -------------------------------------------
  assign nst = mixed ^ rkey;
endmodule
