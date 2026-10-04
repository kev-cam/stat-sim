// ghash_gfmul.v
// ---------------------------------------------------------------------------
// GF(2^128) CARRY-LESS multiply, GCM convention:  prod = a . b  mod P(x),
//     P(x) = x^128 + x^7 + x^2 + x + 1            (the GCM polynomial)
//
// PRECHARGE-FREE STATIC logic: this cone is pure XOR / AND / fixed shifts --
// carry-LESS, so there is NO ripple-carry adder anywhere. It holds no internal
// state and dissipates only when an input bit toggles (NOT domino, NOT
// precharged). Unrolled, the 128 steps below form ONE combinational cone:
// a 128x128 carry-less partial-product + reduction via XOR trees (the
// "parallel" multiplier form). Being carry-less and regular, its settle edge
// is the SHALLOWEST/most-regular of the three MACsec primitives (vs AES S-box
// depth, vs SHA's 32-bit carry ripple) -> the self-timed current-sense DONE is
// the sharpest of the three.
//
// =========================================================================
// GCM BIT-REFLECTION  --  GHASH's #1 bug, stated EXPLICITLY here.
// =========================================================================
// A 128-bit block is a field element (polynomial of degree < 128). GCM's
// convention is REFLECTED:
//     *** bit 0 of the block = the MSB of byte 0 = the coefficient of x^0 ***
// We carry blocks big-endian in Verilog vectors (byte 0 in bits [127:120], so
// MSB-first), therefore:
//     GCM "bit i"  ==  Verilog bit (127 - i)
//     GCM bit 0    ==  v[127] (MSB)  == coeff of x^0  (the constant term)
//     GCM bit 127  ==  v[0]   (LSB)  == coeff of x^127
// Reduction constant R = 11100001 || 0^120 (GCM bit order) = byte 0xE1 then
// 15 zero bytes = {8'hE1, 120'b0} in Verilog. 0xE1 = GCM bits 0,1,2,7 set =
// x^0+x^1+x^2+x^7 = the low part of P (x^128 reduces to x^7+x^2+x+1).
//
// Multiply-by-x (reflected) = a RIGHT shift of the Verilog vector: GCM bit i
// at Verilog position 127-i moves to GCM bit i+1 at Verilog position 126-i,
// i.e. toward the LSB -- exactly `v >> 1`. The bit shifted off the LSB (GCM
// bit 127) decides whether R is XORed back in. This is the shift-and-add
// multiply of SP 800-38D Sec. 6.3, iterating over the bits of `a` and
// accumulating shifted copies of `b`. This Verilog mirrors ghash_ref.py's
// gf_mult() bit-for-bit (same indexing, same shift, same R).
// ---------------------------------------------------------------------------
module ghash_gfmul(
  input  [127:0] a,
  input  [127:0] b,
  output [127:0] prod
);
  // R = 0xE1 << 120  (GCM reduction constant, big-endian in the vector)
  localparam [127:0] R = {8'hE1, 120'b0};

  reg  [127:0] z;   // accumulator  (== python z)
  reg  [127:0] v;   // running shifted copy of b (== python v)
  integer i;
  always @(*) begin
    z = 128'd0;
    v = b;
    for (i = 0; i < 128; i = i + 1) begin
      if (a[127 - i])            // a's GCM bit i  (bit 0 = MSB = a[127])
        z = z ^ v;
      if (v[0])                  // v's GCM bit 127 (LSB) about to fall off
        v = (v >> 1) ^ R;        //   reduce: * x then + R
      else
        v = (v >> 1);            //   * x
    end
  end
  assign prod = z;
endmodule
