#!/usr/bin/env python3
"""PHASE 2 (c) -- FORMAL EQUIVALENCE + VECTORS against the committed behavioural
qal/synth/threeway/sha_slice.v.

Acceptance standard adopted from the sibling run's qal/sha256/verify.py (read-only
input to this run) so the two runs are comparable:

  E5 ports    gate module port list and widths identical to the RTL, read back
              from yosys write_json -- not a regex: the RTL declares six names in
              one `input [7:0] a, b, c, ...` and a hand parser gets that wrong.
  E1 SAT      miter -equiv -flatten -make_assert; sat -verify -prove-asserts.
              A proof over all 2^48 input combinations, not a sample.
  E2 equiv_*  equiv_make / equiv_simple / equiv_induct / equiv_status -assert.
              A structurally different engine -- one green light from one engine
              on a netlist I generated myself is not evidence.
  E3 vectors  iverilog, >= 151,584 vectors, 0 mismatches -- the standard the
              committed QDI form met.  All 65,536 (a,b) pairs are covered
              EXHAUSTIVELY, so the 8-bit CPA is complete, not sampled.

ANCHOR G0B: the COMMITTED netlist sha_slice.cmos.v is put through this same flow.
It must pass.  If it does not, my minicells.v models are wrong and every other
result in this file is void -- that is the point of running it.

DECLARED SCOPE.  E1/E2/E3 validate the BOOLEAN remap only.  They run on
functional cell models and say nothing about level loss, settling, rail draw or
chain behaviour.  The electrical verdict is Phase 1's (qal/pgcell/RESULTS.json)
and is inherited here, never re-derived from these models.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = "/usr/local/src/stat-sim/qal/synth/threeway/sha_slice.v"
VLOG = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/"
PDK_CELLS = VLOG + "sg13g2_stdcell.v"      # the REAL PDK models, for iverilog
PDK_UDP = VLOG + "sg13g2_udp.v"
YCELLS = [os.path.join(HERE, "minicells.v"), os.path.join(HERE, "pgcells.v")]
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def ports(path, extra):
    js = os.path.join(OUT, "p_%s.json" % re.sub(r"\W+", "_", os.path.basename(path)))
    sc = js.replace(".json", ".ys")
    open(sc, "w").write("\n".join(
        ["read_verilog %s" % p for p in extra] +
        ["read_verilog %s" % path, "hierarchy -top sha_slice",
         "write_json %s" % js]) + "\n")
    r = sh(["yosys", "-q", "-s", sc])
    if r.returncode:
        raise SystemExit("port dump failed for %s:\n%s" % (path, (r.stderr or r.stdout)[-1500:]))
    d = json.load(open(js))["modules"]["sha_slice"]["ports"]
    return sorted((n, v["direction"], len(v["bits"])) for n, v in d.items())


PRE = (["read_verilog %s" % RTL, "rename sha_slice gold", "prep -flatten -top gold",
        "design -stash gold"] +
       ["read_verilog %s" % c for c in YCELLS])


def formal(gate):
    tag = re.sub(r"\W+", "_", os.path.basename(gate).replace(".v", ""))
    res = {"netlist": gate}

    gp, rp = ports(gate, YCELLS), ports(RTL, [])
    res["E5_ports_gate"] = [list(x) for x in gp]
    res["E5_ports_rtl"] = [list(x) for x in rp]
    res["E5_PORT_FIDELITY"] = gp == rp

    common = PRE + ["read_verilog %s" % gate, "rename sha_slice gate",
                    "prep -flatten -top gate", "design -stash gate",
                    "design -copy-from gold -as gold gold",
                    "design -copy-from gate -as gate gate"]

    s1 = common + ["miter -equiv -flatten -make_assert gold gate miter",
                   "hierarchy -top miter", "flatten", "opt -full",
                   "sat -verify -prove-asserts -show-ports miter"]
    p1, l1 = os.path.join(OUT, "e1_%s.ys" % tag), os.path.join(OUT, "e1_%s.log" % tag)
    open(p1, "w").write("\n".join(s1) + "\n")
    r1 = sh(["yosys", "-s", p1, "-l", l1])
    t1 = open(l1).read() + r1.stderr
    res["E1_rc"] = r1.returncode
    res["E1_SAT_MITER"] = (r1.returncode == 0 and
                           "SAT proof finished - no model found: SUCCESS!" in t1)
    res["E1_tail"] = [x for x in t1.splitlines()
                      if "SAT proof" in x or "ERROR" in x][-4:]

    s2 = common + ["equiv_make gold gate equiv", "hierarchy -top equiv",
                   "equiv_simple -short", "equiv_induct", "equiv_status -assert"]
    p2, l2 = os.path.join(OUT, "e2_%s.ys" % tag), os.path.join(OUT, "e2_%s.log" % tag)
    open(p2, "w").write("\n".join(s2) + "\n")
    r2 = sh(["yosys", "-s", p2, "-l", l2])
    t2 = open(l2).read() + r2.stderr
    res["E2_rc"] = r2.returncode
    res["E2_EQUIV"] = (r2.returncode == 0 and "Equivalence successfully proven" in t2)
    res["E2_tail"] = [x for x in t2.splitlines() if "quivalen" in x or "ERROR" in x][-5:]
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
  task check; begin
    maj_r = (a & b) ^ (a & c) ^ (b & c);
    ch_r  = (e & f) ^ (~e & g);
    sum_r = a + b;
    #1; n = n + 1;
    if (maj_g !== maj_r || ch_g !== ch_r || sum_g !== sum_r) begin
      mism = mism + 1;
      if (mism < 10)
        $display("MISMATCH a=%h b=%h c=%h e=%h f=%h g=%h | maj %h/%h ch %h/%h sum %h/%h",
                 a,b,c,e,f,g,maj_g,maj_r,ch_g,ch_r,sum_g,sum_r);
    end
  end endtask
  initial begin
    n = 0; mism = 0; lfsr = 32'hACE1_2345;
    // PART 1: EXHAUSTIVE over all 65,536 (a,b) pairs -> the 8-bit CPA is COMPLETE.
    for (i = 0; i < 256; i = i + 1)
      for (k = 0; k < 256; k = k + 1) begin
        a = i[7:0]; b = k[7:0];
        c = k[7:0] ^ i[7:0]; e = i[7:0]; f = ~k[7:0]; g = i[7:0] + k[7:0];
        check;
      end
    // PART 2: EXHAUSTIVE per-bit cover of maj and ch -- every (a_i,b_i,c_i) and
    // every (e_i,f_i,g_i) triple on every bit slice.
    for (i = 0; i < 8; i = i + 1)
      for (k = 0; k < 8; k = k + 1) begin
        a = {8{i[2]}}; b = {8{i[1]}}; c = {8{i[0]}};
        e = {8{k[2]}}; f = {8{k[1]}}; g = {8{k[0]}};
        check;
      end
    // PART 3: pseudo-random, to carry the total past the committed 151,584.
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
    tag = re.sub(r"\W+", "_", os.path.basename(gate).replace(".v", ""))
    tbp = os.path.join(OUT, "tb_%s.v" % tag)
    open(tbp, "w").write(TB)
    exe = os.path.join(OUT, "sim_%s" % tag)
    # the REAL PDK verilog + UDPs for the library cells; pgcells.v for the TG cells
    r = sh(["iverilog", "-g2005", "-o", exe, tbp, gate,
            os.path.join(HERE, "pgcells.v"), PDK_CELLS, PDK_UDP])
    if r.returncode:
        raise SystemExit("iverilog failed for %s:\n%s" % (gate, (r.stdout + r.stderr)[-2000:]))
    r = sh(["vvp", exe])
    open(os.path.join(OUT, "vec_%s.log" % tag), "w").write(r.stdout + r.stderr)
    m = re.search(r"VECTORS (\d+) MISMATCHES (\d+)", r.stdout)
    if not m:
        raise SystemExit("no result line for %s:\n%s" % (gate, r.stdout[-1500:]))
    n, mm = int(m.group(1)), int(m.group(2))
    return {"vectors": n, "mismatches": mm,
            "E3_VECTORS": bool(n >= 151584 and mm == 0),
            "standard": "committed QDI form: 151,584 vectors / 0 mismatches",
            "first_mismatches": [l for l in r.stdout.splitlines()
                                 if l.startswith("MISMATCH")][:5]}


if __name__ == "__main__":
    allres = {}
    for gate in sys.argv[1:]:
        r = formal(gate)
        r.update(vectors(gate))
        r["ALL_PASS"] = all(r[k] for k in ("E5_PORT_FIDELITY", "E1_SAT_MITER",
                                           "E2_EQUIV", "E3_VECTORS"))
        allres[os.path.basename(gate)] = r
        print("%-28s E5 %-5s E1 %-5s E2 %-5s E3 %-5s (%d vec, %d mism)  ALL %s"
              % (os.path.basename(gate), r["E5_PORT_FIDELITY"], r["E1_SAT_MITER"],
                 r["E2_EQUIV"], r["E3_VECTORS"], r["vectors"], r["mismatches"],
                 r["ALL_PASS"]))
        if not r["ALL_PASS"]:
            print("   E1:", " | ".join(r["E1_tail"]))
            print("   E2:", " | ".join(r["E2_tail"]))
            print("   MM:", " | ".join(r["first_mismatches"]))
    p = os.path.join(OUT, "VERIFY.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    old.update(allres)
    json.dump(old, open(p, "w"), indent=1)
