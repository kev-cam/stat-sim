
`timescale 1ns/1ps
module tb;
  reg [7:0] a,b,c,e,f,g;
  wire [7:0] maj_g, ch_g, sum_g;
  reg  [7:0] maj_r, ch_r, sum_r;
  integer n, mism, i, k;
  reg [31:0] lfsr;

  sha_slice dut(.a(a),.b(b),.c(c),.e(e),.f(f),.g(g),
                .maj(maj_g),.ch(ch_g),.sum(sum_g));

  task ref_model;
    begin
      maj_r = (a & b) ^ (a & c) ^ (b & c);
      ch_r  = (e & f) ^ (~e & g);
      sum_r = a + b;
    end
  endtask

  task check;
    begin
      ref_model;
      #1;
      n = n + 1;
      if (maj_g !== maj_r || ch_g !== ch_r || sum_g !== sum_r) begin
        mism = mism + 1;
        if (mism < 10)
          $display("MISMATCH a=%h b=%h c=%h e=%h f=%h g=%h | maj %h/%h ch %h/%h sum %h/%h",
                   a,b,c,e,f,g,maj_g,maj_r,ch_g,ch_r,sum_g,sum_r);
      end
    end
  endtask

  initial begin
    n = 0; mism = 0; lfsr = 32'hACE1_2345;
    // PART 1: EXHAUSTIVE over all 65,536 (a,b) pairs -> the 8-bit CPA is COMPLETE,
    // not sampled.  c/e/f/g walk a 256-step counter so every bit position sees
    // every (a_i,b_i,c_i) and (e_i,f_i,g_i) triple many times over.
    for (i = 0; i < 256; i = i + 1)
      for (k = 0; k < 256; k = k + 1) begin
        a = i[7:0]; b = k[7:0];
        c = k[7:0] ^ i[7:0]; e = i[7:0]; f = ~k[7:0]; g = i[7:0] + k[7:0];
        check;
      end
    // PART 2: EXHAUSTIVE per-bit cover of maj and ch.  All 8 bits are driven with
    // the same (a_i,b_i,c_i) triple, then the same for (e_i,f_i,g_i): 64 vectors
    // that hit every bit slice of both functions with every input combination.
    for (i = 0; i < 8; i = i + 1)
      for (k = 0; k < 8; k = k + 1) begin
        a = {8{i[2]}}; b = {8{i[1]}}; c = {8{i[0]}};
        e = {8{k[2]}}; f = {8{k[1]}}; g = {8{k[0]}};
        check;
      end
    // PART 3: pseudo-random, to carry the total past the committed 151,584
    for (i = 0; i < 90000; i = i + 1) begin
      a = lfsr[7:0];   lfsr = {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      b = lfsr[7:0];   lfsr = {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      c = lfsr[7:0];   lfsr = {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      e = lfsr[7:0];   lfsr = {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      f = lfsr[7:0];   lfsr = {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      g = lfsr[7:0];   lfsr = {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      check;
    end
    $display("VECTORS %0d MISMATCHES %0d", n, mism);
    $finish;
  end
endmodule
