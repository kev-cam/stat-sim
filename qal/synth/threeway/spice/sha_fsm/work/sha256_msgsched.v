// SHA-256 message schedule, PURELY COMBINATIONAL: W[t] from the 16-word window.
module sha256_msgsched(
  input [31:0] w2, w7, w15, w16,   // W[t-2], W[t-7], W[t-15], W[t-16]
  output [31:0] wt
);
  function [31:0] rotr; input [31:0] x; input integer n;
    rotr = (x >> n) | (x << (32-n)); endfunction
  wire [31:0] s0 = rotr(w15,7)  ^ rotr(w15,18) ^ (w15 >> 3);
  wire [31:0] s1 = rotr(w2,17)  ^ rotr(w2,19)  ^ (w2  >> 10);
  assign wt = s1 + w7 + s0 + w16;   // 4-operand add
endmodule
