// SHA-256 datapath slice: the round's core Boolean+arith primitives, 8-bit.
// Maj(a,b,c) and Ch(e,f,g) are the round's majority/choice; add is the CPA that
// dominates the round critical path (carry chain). Pure combinational -> the clean
// three-way small-block anchor (SPICE-validatable, exercises TH majority + adder carry).
module sha_slice(
  input  [7:0] a, b, c, e, f, g,
  output [7:0] maj, ch, sum
);
  assign maj = (a & b) ^ (a & c) ^ (b & c);      // majority -> TH23-natural
  assign ch  = (e & f) ^ (~e & g);               // choice
  assign sum = a + b;                            // 8-bit CPA (carry chain)
endmodule
