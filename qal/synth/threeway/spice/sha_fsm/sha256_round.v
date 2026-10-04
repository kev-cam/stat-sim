// sha256_round.v
// ---------------------------------------------------------------------------
// ONE SHA-256 round as PURE STATIC combinational next-state logic.
// FIPS 180-4 round function. Ordinary Verilog -> maps to static CMOS gates
// (xor/and/or/not + ripple-carry CPAs). PRECHARGE-FREE, NOT domino: it holds
// no internal state and dissipates only when an input toggles. This is the
// deep next-state cone that a self-timed FSM clocks with a done pulse once its
// adder critical path (the 32-bit carry chains feeding T1/T2/a'/e') settles.
//
// Inputs : working registers a..h, round constant Kt, schedule word Wt.
// Outputs: next working registers na..nh.
//
//   Sigma0(a) = ROTR2(a)  ^ ROTR13(a) ^ ROTR22(a)
//   Sigma1(e) = ROTR6(e)  ^ ROTR11(e) ^ ROTR25(e)
//   Maj(a,b,c)= (a&b) ^ (a&c) ^ (b&c)
//   Ch(e,f,g) = (e&f) ^ (~e&g)
//   T1 = h + Sigma1(e) + Ch(e,f,g) + Kt + Wt
//   T2 = Sigma0(a) + Maj(a,b,c)
//   a' = T1 + T2 ;  e' = d + T1
//   b'=a  c'=b  d'=c  f'=e  g'=f  h'=g
// ---------------------------------------------------------------------------
module sha256_round(
  input  [31:0] a, b, c, d, e, f, g, h,
  input  [31:0] Kt, Wt,
  output [31:0] na, nb, nc, nd, ne, nf, ng, nh
);
  // 32-bit right-rotate by a constant amount (static barrel wiring).
  function [31:0] rotr;
    input [31:0] x;
    input integer n;
    begin
      rotr = (x >> n) | (x << (32 - n));
    end
  endfunction

  wire [31:0] bigS1 = rotr(e, 6)  ^ rotr(e, 11) ^ rotr(e, 25);
  wire [31:0] bigS0 = rotr(a, 2)  ^ rotr(a, 13) ^ rotr(a, 22);
  wire [31:0] ch    = (e & f) ^ (~e & g);
  wire [31:0] maj   = (a & b) ^ (a & c) ^ (b & c);

  // Adder critical path (carry chains) -> gate the done pulse on these.
  wire [31:0] T1 = h + bigS1 + ch + Kt + Wt;
  wire [31:0] T2 = bigS0 + maj;

  assign na = T1 + T2;
  assign nb = a;
  assign nc = b;
  assign nd = c;
  assign ne = d + T1;
  assign nf = e;
  assign ng = f;
  assign nh = g;
endmodule
