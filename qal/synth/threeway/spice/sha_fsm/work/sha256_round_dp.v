// SHA-256 single round datapath, PURELY COMBINATIONAL (one round's next-state logic).
// a..h working regs in, a'..h' out. Kt,Wt supplied. Rotations are pure wiring.
module sha256_round_dp(
  input  [31:0] a,b,c,d,e,f,g,h,
  input  [31:0] Kt, Wt,
  output [31:0] ao,bo,co,dao,eo,fo,go,ho
);
  function [31:0] rotr; input [31:0] x; input integer n;
    rotr = (x >> n) | (x << (32-n)); endfunction
  wire [31:0] S1  = rotr(e,6)  ^ rotr(e,11) ^ rotr(e,25);
  wire [31:0] S0  = rotr(a,2)  ^ rotr(a,13) ^ rotr(a,22);
  wire [31:0] chv = (e & f) ^ (~e & g);
  wire [31:0] mjv = (a & b) ^ (a & c) ^ (b & c);
  wire [31:0] T1  = h + S1 + chv + Kt + Wt;   // 5-operand add
  wire [31:0] T2  = S0 + mjv;                 // 2-operand add
  assign ho=g; assign go=f; assign fo=e; assign eo = d + T1;   // 2-operand add
  assign dao=c; assign co=b; assign bo=a; assign ao = T1 + T2; // 2-operand add
endmodule
