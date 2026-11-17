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

// The module bodies above are taken from the IHP Open PDK (sg13g2_stdcell.v) and stay
// under its license. The changes are described at the top of this file.
// A copy of the license is in LICENSES/Apache-2.0.txt at the top of this repository.
// The notice of the original file:
//
// SPDX-License-Identifier: Apache-2.0
//
// Copyright 2024 IHP PDK Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
