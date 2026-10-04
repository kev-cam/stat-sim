// aes_key_expand.v
// ---------------------------------------------------------------------------
// AES-128 key expansion as a PER-ROUND combinational step (FIPS-197 Sec. 5.2).
//
// The full schedule is 11 round keys = 44 words w[0..43]; w[0..3] is the cipher
// key, and for i>=4:
//     temp = w[i-1]
//     if (i mod 4 == 0) temp = SubWord(RotWord(temp)) ^ Rcon[i/4]
//     w[i] = w[i-4] ^ temp
//
// Rather than precompute and store all 11 keys, the self-timed FSM HOLDS THE
// RUNNING ROUND KEY AS STATE and advances it one round at a time -- exactly the
// way the SHA-256 FSM rolled its 16-word message-schedule window. This module
// is that single advance: given the 4 words of round key (round-1) it produces
// the 4 words of round key (round). It therefore contains the only S-boxes on
// the key path (SubWord = 4 S-box cells, shared cell type with the datapath)
// plus XORs and the Rcon ROM -- all PRECHARGE-FREE static CMOS, dissipating
// only on a key-word toggle, same clock-floor-shedding property as the datapath.
//
// Word layout: a round key's 128 bits are {w0,w1,w2,w3} with w0 in [127:96];
// within a word the first (lowest-index) byte is the most significant 8 bits.
// ---------------------------------------------------------------------------
module aes_key_expand(
  input  [127:0] rk_in,   // round key for round (round_idx-1)
  input  [3:0]   round_idx, // 1..10: which round key to PRODUCE
  output [127:0] rk_out    // round key for round (round_idx)
);
  wire [31:0] w0 = rk_in[127:96];
  wire [31:0] w1 = rk_in[95:64];
  wire [31:0] w2 = rk_in[63:32];
  wire [31:0] w3 = rk_in[31:0];

  // RotWord([a0,a1,a2,a3]) = [a1,a2,a3,a0]  (rotate the 4 bytes left by one)
  wire [31:0] rot = { w3[23:0], w3[31:24] };

  // SubWord: S-box each of the 4 bytes of the rotated word.
  wire [31:0] subw;
  aes_sbox KS0(.in(rot[31:24]), .o(subw[31:24]));
  aes_sbox KS1(.in(rot[23:16]), .o(subw[23:16]));
  aes_sbox KS2(.in(rot[15:8]),  .o(subw[15:8]));
  aes_sbox KS3(.in(rot[7:0]),   .o(subw[7:0]));

  // Rcon[j] = { rc(j), 24'h0 }, rc in GF(2^8): x^(j-1).  j = round_idx.
  function [7:0] rcon_rom;
    input [3:0] j;
    begin
      case (j)
        4'd1:  rcon_rom = 8'h01;
        4'd2:  rcon_rom = 8'h02;
        4'd3:  rcon_rom = 8'h04;
        4'd4:  rcon_rom = 8'h08;
        4'd5:  rcon_rom = 8'h10;
        4'd6:  rcon_rom = 8'h20;
        4'd7:  rcon_rom = 8'h40;
        4'd8:  rcon_rom = 8'h80;
        4'd9:  rcon_rom = 8'h1b;
        4'd10: rcon_rom = 8'h36;
        default: rcon_rom = 8'h00;
      endcase
    end
  endfunction
  wire [31:0] rcon = { rcon_rom(round_idx), 24'h000000 };

  // temp for the first word of the new key; chain the rest.
  wire [31:0] temp = subw ^ rcon;
  wire [31:0] nw0  = w0 ^ temp;
  wire [31:0] nw1  = w1 ^ nw0;
  wire [31:0] nw2  = w2 ^ nw1;
  wire [31:0] nw3  = w3 ^ nw2;

  assign rk_out = { nw0, nw1, nw2, nw3 };
endmodule
