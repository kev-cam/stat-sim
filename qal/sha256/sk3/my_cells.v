// SKEPTIC: function bodies extracted VERBATIM from /usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v

// specify blocks stripped (yosys 0.58 cannot parse `ifnone` inside specify).

module sg13g2_inv_1 (Y, A);
		
	output Y;
	input A;

	// Function

	not (Y, A);

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

module sg13g2_and2_1 (X, A, B);
		
	output X;
	input A, B;

	// Function

	and (X, A, B);

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

module sg13g2_or2_1 (X, A, B);
		
	output X;
	input A, B;

	// Function

	or (X, A, B);

        // Timing

	 

endmodule

module sg13g2_buf_1 (X, A);
		
	output X;
	input A;

	// Function

	buf (X, A);

        // Timing

	 

endmodule
