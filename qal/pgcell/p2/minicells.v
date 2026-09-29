// Minimal 2-state functional models of the sg13g2 combinational cells used by
// any netlist in this run.  yosys 0.58 cannot parse the PDK's `ifnone` specify
// construct nor its UDP tables, so the FORMAL flow reads these instead.
//
// THESE MODELS ARE NOT TRUSTED ON FAITH.  The committed netlist
// qal/synth/threeway/work/sha_slice.cmos.v is put through the SAME E1/E2 formal
// flow against the RTL using these models (anchor G0B in verify.py).  A wrong
// function here makes the committed netlist fail its own equivalence proof, so
// a transcription error cannot pass silently.  The vector flow (E3) uses the
// REAL PDK verilog + UDPs, not these.

module sg13g2_inv_1   (A, Y);       input A;           output Y; assign Y = ~A; endmodule
module sg13g2_buf_1   (A, X);       input A;           output X; assign X =  A; endmodule
module sg13g2_nand2_1 (A, B, Y);    input A, B;        output Y; assign Y = ~(A & B); endmodule
module sg13g2_nor2_1  (A, B, Y);    input A, B;        output Y; assign Y = ~(A | B); endmodule
module sg13g2_and2_1  (A, B, X);    input A, B;        output X; assign X =  (A & B); endmodule
module sg13g2_or2_1   (A, B, X);    input A, B;        output X; assign X =  (A | B); endmodule
module sg13g2_xor2_1  (A, B, X);    input A, B;        output X; assign X =  (A ^ B); endmodule
module sg13g2_xnor2_1 (A, B, Y);    input A, B;        output Y; assign Y = ~(A ^ B); endmodule
module sg13g2_nor2b_1 (A, B_N, Y);  input A, B_N;      output Y; assign Y = ~A & B_N; endmodule
module sg13g2_nand2b_1(A_N, B, Y);  input A_N, B;      output Y; assign Y = A_N | ~B; endmodule
module sg13g2_mux2_1  (A0, A1, S, X); input A0, A1, S; output X; assign X = S ? A1 : A0; endmodule
module sg13g2_a21oi_1 (A1, A2, B1, Y); input A1, A2, B1; output Y; assign Y = ~((A1 & A2) | B1); endmodule
module sg13g2_a21o_1  (A1, A2, B1, X); input A1, A2, B1; output X; assign X =  ((A1 & A2) | B1); endmodule
module sg13g2_o21ai_1 (A1, A2, B1, Y); input A1, A2, B1; output Y; assign Y = ~((A1 | A2) & B1); endmodule
module sg13g2_o21a_1  (A1, A2, B1, X); input A1, A2, B1; output X; assign X =  ((A1 | A2) & B1); endmodule
