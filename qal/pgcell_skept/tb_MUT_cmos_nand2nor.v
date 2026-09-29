
`timescale 1ns/1ps
module tb;
  reg [7:0] a,b,c,e,f,g;
  wire [7:0] maj,ch,sum;
  integer i, mism, n;
  reg [31:0] lf;
  reg [7:0] emaj, ech, esum;
  sha_slice U(.a(a),.b(b),.c(c),.e(e),.f(f),.g(g),.maj(maj),.ch(ch),.sum(sum));
  task chk; begin
    emaj = (a&b)^(a&c)^(b&c); ech = (e&f)^((~e)&g); esum = a+b; n = n+1;
    #1;
    if (maj!==emaj || ch!==ech || sum!==esum) begin
      mism = mism+1;
      if (mism < 6) $display("MISM a=%h b=%h c=%h e=%h f=%h g=%h  maj=%h/%h ch=%h/%h sum=%h/%h",
                              a,b,c,e,f,g,maj,emaj,ch,ech,sum,esum);
    end
  end endtask
  function [31:0] nxt; input [31:0] s; begin
    nxt = {s[30:0], s[31]^s[21]^s[1]^s[0]};
  end endfunction
  initial begin
    mism=0; n=0; lf=32'hACE1_2345;
    // 1. EXHAUSTIVE over all 65536 (a,b) pairs -> the 8-bit CPA is COMPLETE
    for (i=0;i<65536;i=i+1) begin
      a = i[15:8]; b = i[7:0];
      c = lf[7:0]; e = lf[15:8]; f = lf[23:16]; g = lf[31:24];
      chk; lf = nxt(lf);
    end
    // 2. EXHAUSTIVE per-bit maj: all 8 (a,b,c) bit patterns on every bit at once,
    //    walked so every bit sees all 8
    for (i=0;i<256;i=i+1) begin
      a = {8{i[0]}}; b = {8{i[1]}}; c = {8{i[2]}};
      e = i[7:0]; f = ~i[7:0]; g = i[7:0] ^ 8'h5A; chk;
      a = i[7:0]; b = ~i[7:0]; c = i[7:0]^8'h3C;
      e = {8{i[0]}}; f = {8{i[1]}}; g = {8{i[2]}}; chk;
    end
    // 3. EXHAUSTIVE per-bit ch: all 8 (e,f,g) patterns
    for (i=0;i<8;i=i+1) begin
      e={8{i[0]}}; f={8{i[1]}}; g={8{i[2]}};
      a=8'h5A; b=8'hA5; c=8'h3C; chk;
    end
    // 4. random
    for (i=0;i<90000;i=i+1) begin
      a=lf[7:0]; lf=nxt(lf); b=lf[7:0]; lf=nxt(lf); c=lf[7:0]; lf=nxt(lf);
      e=lf[7:0]; lf=nxt(lf); f=lf[7:0]; lf=nxt(lf); g=lf[7:0]; lf=nxt(lf);
      chk;
    end
    $display("VECTORS %0d MISMATCH %0d", n, mism);
    $finish;
  end
endmodule
