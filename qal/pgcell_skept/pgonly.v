module pg_xor2 (A, B, X);  input A, B; output X; assign X = A ^ B; endmodule
module pg_xnor2 (A, B, Y); input A, B; output Y; assign Y = ~(A ^ B); endmodule
module pg_mux2 (A0, A1, S, X); input A0, A1, S; output X;
  assign X = S ? A1 : A0;
endmodule

// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
