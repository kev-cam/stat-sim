module small(input [3:0] a, input [3:0] b, input [1:0] op, input c, output [3:0] y, output z);
  wire [3:0] r0 = a & b;
  wire [3:0] r1 = a | b;
  wire [3:0] r2 = a ^ b;
  wire [3:0] r3 = ~a;
  assign y = op[1] ? (op[0] ? r3 : r2) : (op[0] ? r1 : r0);
  assign z = c ? (^a) : (&b);
endmodule

// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
