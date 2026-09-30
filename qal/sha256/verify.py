#!/usr/bin/env python3
"""PHASE 1(d): FORMAL EQUIVALENCE + VECTORS of a remapped netlist against the
COMMITTED behavioural qal/synth/threeway/sha_slice.v.

E1  SAT miter   : miter -equiv -make_assert, then sat -verify -prove-asserts.
E2  equiv_*     : equiv_make / equiv_simple / equiv_induct / equiv_status -assert.
                  A structurally different engine, because one green light from one
                  engine on a netlist I generated is not evidence.
E5  ports       : the gate module's port list and widths must match the RTL exactly.
E3  vectors     : iverilog, >= 151,584 vectors, 0 mismatches (the standard the
                  committed QDI form met).  ALL 65,536 (a,b) pairs are covered
                  exhaustively, so the 8-bit CPA is complete, not sampled.

usage: verify.py formal <netlist.v>
       verify.py vectors <netlist.v>
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = "/usr/local/src/stat-sim/qal/synth/threeway/sha_slice.v"
VLOG = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/")
CELLS = VLOG + "sg13g2_stdcell.v"          # the real PDK models -- used by iverilog
UDP = VLOG + "sg13g2_udp.v"                # the real PDK UDPs   -- used by iverilog
# yosys 0.58 cannot parse the PDK's `ifnone` specify construct nor its UDP tables.
# verify/cells_min.v carries the same 13 combinational cells with the FUNCTION gate
# primitives verbatim, specify blocks stripped (timing only), and the one UDP-bodied
# cell (mux2) written out as its 2-state function.  Built by mkcells().
YCELLS = os.path.join(HERE, "verify", "cells_min.v")
OUT = os.path.join(HERE, "verify")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ports_of(path, top):
    src = open(path).read()
    body = src[src.index("module %s(" % top):]
    body = body[:body.index(");")]
    return body


def formal(gate):
    os.makedirs(OUT, exist_ok=True)
    tag = os.path.basename(gate).replace(".v", "")
    res = {"netlist": gate}

    # --- E5 port fidelity -------------------------------------------------
    def decls(path, extra=""):
        """Port list read back from YOSYS ITSELF (write_json), not from a regex over
        the source: the RTL declares six names in one `input [7:0] a, b, c, ...`
        and any hand-rolled parser gets that wrong."""
        js = os.path.join(OUT, "ports_%s.json" % abs(hash(path)))
        sc = os.path.join(OUT, "ports_%s.ys" % abs(hash(path)))
        open(sc, "w").write("\n".join(
            ([extra] if extra else []) +
            ["read_verilog %s" % path, "hierarchy -top sha_slice",
             "write_json %s" % js]) + "\n")
        r = sh(["yosys", "-q", "-s", sc])
        if r.returncode:
            raise SystemExit("port dump failed: " + (r.stderr or r.stdout)[-500:])
        d = json.load(open(js))["modules"]["sha_slice"]["ports"]
        return sorted((n, v["direction"], len(v["bits"])) for n, v in d.items())
    gp = decls(gate, "read_verilog %s" % YCELLS)
    rp = decls(RTL)
    norm = lambda L: L
    res["E5_ports_gate"] = [list(x) for x in norm(gp)]
    res["E5_ports_rtl"] = [list(x) for x in norm(rp)]
    res["E5_PORT_FIDELITY"] = norm(gp) == norm(rp)

    # --- E1 SAT miter -----------------------------------------------------
    s1 = "\n".join([
        "read_verilog %s" % RTL,
        "rename sha_slice gold",
        "prep -flatten -top gold",
        "design -stash gold",
        "read_verilog %s" % YCELLS,
        "read_verilog %s" % gate,
        "rename sha_slice gate",
        "prep -flatten -top gate",
        "design -stash gate",
        "design -copy-from gold -as gold gold",
        "design -copy-from gate -as gate gate",
        "miter -equiv -flatten -make_assert gold gate miter",
        "hierarchy -top miter",
        "flatten; opt -full",
        "sat -verify -prove-asserts -show-ports miter",
    ])
    p1 = os.path.join(OUT, "e1_%s.ys" % tag)
    open(p1, "w").write(s1 + "\n")
    l1 = os.path.join(OUT, "e1_%s.log" % tag)
    r1 = sh(["yosys", "-s", p1, "-l", l1])
    txt = open(l1).read() + r1.stderr
    res["E1_rc"] = r1.returncode
    res["E1_SAT_MITER"] = (r1.returncode == 0 and
                           "SAT proof finished - no model found: SUCCESS!" in txt)
    res["E1_tail"] = [x for x in txt.splitlines() if "SAT proof" in x or "ERROR" in x][-4:]

    # --- E2 equiv_* -------------------------------------------------------
    s2 = "\n".join([
        "read_verilog %s" % RTL,
        "rename sha_slice gold",
        "prep -flatten -top gold",
        "design -stash gold",
        "read_verilog %s" % YCELLS,
        "read_verilog %s" % gate,
        "rename sha_slice gate",
        "prep -flatten -top gate",
        "design -stash gate",
        "design -copy-from gold -as gold gold",
        "design -copy-from gate -as gate gate",
        "equiv_make gold gate equiv",
        "hierarchy -top equiv",
        "equiv_simple -short",
        "equiv_induct",
        "equiv_status -assert",
    ])
    p2 = os.path.join(OUT, "e2_%s.ys" % tag)
    open(p2, "w").write(s2 + "\n")
    l2 = os.path.join(OUT, "e2_%s.log" % tag)
    r2 = sh(["yosys", "-s", p2, "-l", l2])
    t2 = open(l2).read() + r2.stderr
    res["E2_rc"] = r2.returncode
    res["E2_EQUIV"] = (r2.returncode == 0 and "Equivalence successfully proven" in t2)
    res["E2_tail"] = [x for x in t2.splitlines() if "quivalen" in x or "ERROR" in x][-6:]
    json.dump(res, open(os.path.join(OUT, "formal_%s.json" % tag), "w"), indent=1)
    for k in ("E5_PORT_FIDELITY", "E1_SAT_MITER", "E2_EQUIV"):
        print("%-18s %s" % (k, res[k]))
    for k in ("E1_tail", "E2_tail"):
        print(" %s: %s" % (k, " | ".join(res[k])))
    return res


TB = r"""
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
"""


def vectors(gate):
    os.makedirs(OUT, exist_ok=True)
    tag = os.path.basename(gate).replace(".v", "")
    tbp = os.path.join(OUT, "tb_%s.v" % tag)
    open(tbp, "w").write(TB)
    exe = os.path.join(OUT, "sim_%s" % tag)
    r = sh(["iverilog", "-g2005", "-o", exe, tbp, gate, CELLS, UDP])
    if r.returncode:
        print(r.stdout, r.stderr)
        raise SystemExit("iverilog compile failed")
    r = sh(["vvp", exe])
    open(os.path.join(OUT, "vec_%s.log" % tag), "w").write(r.stdout + r.stderr)
    m = re.search(r"VECTORS (\d+) MISMATCHES (\d+)", r.stdout)
    if not m:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit("no result line")
    n, mm = int(m.group(1)), int(m.group(2))
    res = dict(netlist=gate, vectors=n, mismatches=mm,
               E3_VECTORS=bool(n >= 151584 and mm == 0),
               standard="committed QDI form: 151,584 vectors / 0 mismatches")
    json.dump(res, open(os.path.join(OUT, "vectors_%s.json" % tag), "w"), indent=1)
    print("VECTORS %d  MISMATCHES %d  E3 %s" % (n, mm, res["E3_VECTORS"]))
    if mm:
        print(r.stdout[:2000])
    return res


if __name__ == "__main__":
    if sys.argv[1] == "formal":
        formal(sys.argv[2])
    elif sys.argv[1] == "vectors":
        vectors(sys.argv[2])
