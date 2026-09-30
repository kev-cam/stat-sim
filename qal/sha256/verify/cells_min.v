// NOTE: `specify` blocks (timing only, no function) are STRIPPED -- yosys 0.58
// cannot parse the PDK's `ifnone` construct.  13 blocks removed; every gate
// primitive defining the cell FUNCTION is verbatim and untouched.
// verbatim module bodies from the IHP PDK sg13g2_stdcell.v
// (only the combinational cells this track uses; no UDP, no sequential cells)
`timescale 1ns/10ps
module sg13g2_inv_1 (Y, A);
		
	output Y;
	input A;

	// Function

	not (Y, A);

        // Timing


endmodule

module sg13g2_buf_1 (X, A);
		
	output X;
	input A;

	// Function

	buf (X, A);

        // Timing


endmodule

module sg13g2_nand2_1 (Y, A, B);
		
	output Y;
	input A, B;

	// Function

	wire int_fwire_0;

	and (int_fwire_0, A, B);
	not (Y, int_fwire_0);

        // Timing


endmodule

module sg13g2_nor2_1 (Y, A, B);
		
	output Y;
	input A, B;

	// Function

	wire int_fwire_0;

	or (int_fwire_0, A, B);
	not (Y, int_fwire_0);

        // Timing


endmodule

module sg13g2_and2_1 (X, A, B);
		
	output X;
	input A, B;

	// Function

	and (X, A, B);

        // Timing


endmodule

module sg13g2_or2_1 (X, A, B);
		
	output X;
	input A, B;

	// Function

	or (X, A, B);

        // Timing


endmodule

module sg13g2_nor2b_1 (Y, A, B_N);
		
	output Y;
	input A, B_N;

	// Function

	wire B_N__bar, int_fwire_0;

	not (B_N__bar, B_N);
	or (int_fwire_0, A, B_N__bar);
	not (Y, int_fwire_0);

        // Timing


endmodule

module sg13g2_xnor2_1 (Y, A, B);
		
	output Y;
	input A, B;

	// Function

	wire int_fwire_0;

	xor (int_fwire_0, A, B);
	not (Y, int_fwire_0);
        
        // Timing


endmodule

module sg13g2_xor2_1 (X, A, B);
		
	output X;
	input A, B;

	// Function

	xor (X, A, B);

        // Timing


endmodule

module sg13g2_mux2_1 (X, A0, A1, S);
		
	output X;
	input A0, A1, S;

	// Function

	// DECLARED SUBSTITUTION (yosys-only model): the PDK cell body is the UDP
	// `ihp_mux2 (X, A0, A1, S)` whose table is s=0 -> z=a, s=1 -> z=b, plus two
	// x-tolerance rows.  yosys cannot parse UDP tables; the 2-state function is
	// written out here.  The VECTOR run (iverilog) uses the REAL UDP, unmodified.
	assign X = S ? A1 : A0;

        // Timing


endmodule

module sg13g2_a21oi_1 (Y, A1, A2, B1);
		
	output Y;
	input A1, A2, B1;

	// Function

	wire int_fwire_0, int_fwire_1;

	and (int_fwire_0, A1, A2);
	or (int_fwire_1, int_fwire_0, B1);
	not (Y, int_fwire_1);
        
	// Timing


endmodule

module sg13g2_a21o_1 (X, A1, A2, B1);
	
	output X;
	input A1, A2, B1;

	// Function
	wire int_fwire_0;

	and (int_fwire_0, A1, A2);
	or (X, int_fwire_0, B1);

	// Timing


endmodule

module sg13g2_o21ai_1 (Y, A1, A2, B1);
		
	output Y;
	input A1, A2, B1;

	// Function

	wire int_fwire_0, int_fwire_1;

	or (int_fwire_0, A1, A2);
	and (int_fwire_1, int_fwire_0, B1);
	not (Y, int_fwire_1);

        // Timing


endmodule
