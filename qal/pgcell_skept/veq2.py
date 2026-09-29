#!/usr/bin/env python3
"""E4: the vector check re-run against the REAL PDK VERILOG + UDPs rather than my
liberty-derived models, so the result does not depend on my cell transcription at
all.  Only the three pg_* cells are mine (they have no PDK counterpart)."""
import json, os, re, subprocess, sys
import veq

PDKV = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/"
        "sg13g2_stdcell.v")
UDP = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/"
       "sg13g2_udp.v")
HERE = os.path.dirname(os.path.abspath(__file__))
PGONLY = os.path.join(HERE, "pgonly.v")
open(PGONLY, "w").write(
    "module pg_xor2 (A, B, X);  input A, B; output X; assign X = A ^ B; endmodule\n"
    "module pg_xnor2 (A, B, Y); input A, B; output Y; assign Y = ~(A ^ B); endmodule\n"
    "module pg_mux2 (A0, A1, S, X); input A0, A1, S; output X;\n"
    "  assign X = S ? A1 : A0;\nendmodule\n")

MODELS = "%s %s %s" % (UDP, PDKV, PGONLY)
nets = sys.argv[1:] or ["cmos", "pgp", "pgp1", "pgp1c", "pgr1c", "abc_nand_resyn2",
                        "abc_pg_resyn2"]
R = {"models": MODELS}
for n in nets:
    net = veq.CMOS if n == "cmos" else os.path.join(veq.OUT, "sha_slice.%s.v" % n)
    d = veq.vectors("PDKV_" + n, net, MODELS)
    R[n] = d
    print("%-18s compiled=%s vectors=%s mismatches=%s"
          % (n, d.get("compiled"), d.get("vectors"), d.get("mismatches")), flush=True)
R["ALL_PASS"] = all(v.get("pass_") for k, v in R.items() if isinstance(v, dict))
json.dump(R, open(os.path.join(HERE, "VEQ_PDKV.json"), "w"), indent=1)
print("ALL_PASS", R["ALL_PASS"])
