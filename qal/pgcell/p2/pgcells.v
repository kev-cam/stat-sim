// Pass-gate cell models for the Phase 2 remap of sha_slice.
//
// FUNCTION ONLY.  These are 2-state Boolean models used by yosys (formal
// equivalence) and iverilog (vectors).  They say NOTHING about level loss,
// settling or rail draw -- that is Phase 1's measurement (qal/pgcell/RESULTS.json),
// and it is INHERITED here, never re-derived from these models.
//
// The transistor-level cells they stand for (qal/pgcell/pg.py, width tgM =
// 0.74u n / 1.12u p, the campaign-standard static widths):
//
//   pg_xnor2 / pg_xor2   8 devices (4n/4p).  inv_A -> Abar, inv_B -> Bbar, then
//                        TG1 = nMOS(gate Bbar) || pMOS(gate B) passing one tap and
//                        TG2 = nMOS(gate B) || pMOS(gate Bbar) passing the other.
//                        XOR and XNOR are the SAME CELL -- exchange the two TG
//                        source taps, zero extra devices.
//                        Pull-up stack depth 1; only the 2 inverter pMOS have any
//                        terminal on the bank rail.
//
//   pg_mux2              6 devices (3n/3p).  inv_S -> Sb, TG0 passes A0 when S=0,
//                        TG1 passes A1 when S=1.  BOTH data paths transparent --
//                        the data path never touches the rail.
//                        Pull-up stack depth 1; 1 rail-connected device.
//
// Polarity matches the PDK cells they replace:
//   sg13g2_xnor2_1  Y = ~(A ^ B)
//   sg13g2_xor2_1   X =  (A ^ B)
//   sg13g2_mux2_1   X = S ? A1 : A0      (verified against the PDK truth table)

module pg_xor2 (A, B, X);
  input A, B;
  output X;
  assign X = A ^ B;
endmodule

module pg_xnor2 (A, B, Y);
  input A, B;
  output Y;
  assign Y = ~(A ^ B);
endmodule

module pg_mux2 (A0, A1, S, X);
  input A0, A1, S;
  output X;
  assign X = S ? A1 : A0;
endmodule
