// ghash_round.v
// ---------------------------------------------------------------------------
// ONE GHASH step as PURE STATIC next-state logic (SP 800-38D Sec. 6.4):
//
//        Y' = (Y XOR C_i) . H   mod P(x)          P = x^128+x^7+x^2+x+1
//
// = a 128-bit XOR (absorb the incoming block C_i into the accumulator) feeding
// the GF(2^128) carry-less multiply by the hash subkey H. ORDINARY Verilog ->
// maps to static CMOS: an XOR plane and the ghash_gfmul XOR/AND cone. It is
// PRECHARGE-FREE (not domino): no internal state, dissipates only on input
// toggles. This is the deep-but-REGULAR, carry-LESS next-state cone that the
// self-timed FSM clocks with a DONE pulse once it has settled -- and because it
// is carry-less (no ripple adder, unlike SHA; no S-box substitution depth,
// unlike AES) its power-settle edge is the sharpest of the three, making the
// in-kind-replica / current-sense completion detector the most viable here.
//
// H is held constant for the whole message (the hash subkey = AES_K(0^128));
// Y is the 128-bit accumulator carried in the FSM's DFF state register.
// Bit-reflection / field convention: see ghash_gfmul.v (bit 0 = MSB of byte 0).
// ---------------------------------------------------------------------------
module ghash_round(
  input  [127:0] Y,       // current accumulator
  input  [127:0] C,       // incoming block C_i
  input  [127:0] H,       // hash subkey (held constant)
  output [127:0] Ynext    // (Y XOR C) . H  mod P
);
  wire [127:0] xored = Y ^ C;            // absorb the block (static XOR plane)
  ghash_gfmul MUL(.a(xored), .b(H), .prod(Ynext));   // carry-less GF multiply
endmodule
