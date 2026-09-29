module t (input CLK, input RB, input din, input b, input c, output dout);
  wire q1, n1;
  sg13g2_dfrbpq_1 F1 (.CLK(CLK), .D(din), .RESET_B(RB), .Q(q1));
  sg13g2_a21oi_1 U1 (.A1(q1), .A2(b), .B1(c), .Y(n1));
  sg13g2_dfrbpq_1 F2 (.CLK(CLK), .D(n1), .RESET_B(RB), .Q(dout));
endmodule
