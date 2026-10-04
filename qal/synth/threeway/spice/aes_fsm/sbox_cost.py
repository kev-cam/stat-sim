#!/usr/bin/env python3
"""AES-128 S-box COST CHARACTERIZATION for the self-timed static-CMOS FSM campaign.

The S-box is what makes AES *different* from SHA-256: SHA's round was arithmetic
(adders + rotations); AES's round is SUBSTITUTION. 16 S-boxes/round x 10 rounds =
160 data S-box evals (+ 40 in key expansion), and the round critical path and per-op
energy are S-box-DOMINATED. This script characterizes that distinctive element two
ways and feeds per-S-box / per-round / per-encrypt fJ to the energy-composition agent.

WHAT IT DOES (all synthesis is REAL; nothing is hand-waved):
  (a) 256x8 LUT/ROM form  -- reads the RTL agent's aes_sbox.v (module aes_sbox), the
      FIPS-197 case table. "fast/big": a decoder/mux tree.
  (b) Canright composite-field GF((2^4)^2) tower S-box -- GENERATED here and verified
      bit-exact. "compact/deeper": map GF(2^8)->GF((2^4)^2)->GF((2^2)^2), invert,
      remap+affine, all static XOR/AND. The classic ~110-130 gate low-power form.
  + aes_mixcolumns / aes_addroundkey, synthesized too, so the per-round number is
    grounded (not guessed).

VERIFICATION (never self-asserted):
  * the reference S-box table is built from first principles -- multiplicative inverse
    in GF(2^8) mod 0x11b + the AES affine transform -- and cross-checked byte-for-byte
    against the canonical published FIPS-197 table (independent oracle, 256/256).
  * BOTH Verilog forms are simulated with iverilog over all 256 inputs and must match
    that reference (256/256) before any cell count is reported.
  * MixColumns is checked against a Python GF reference.

ENERGY: composed from the MEASURED anchor sha_slice = 232 fJ / 63 cells = 3.683
fJ/cell/op (same per-cell basis the SHA compose used), tagged [MEAS-anchor]/[COMPOSED]/
[EST]. No SPICE is launched (USER DIRECTIVE 2026-10-02: stat-sim modeling over SPICE).

TOOLS: yosys /usr/local/src/yosys-build/yosys ; iverilog/vvp /usr/local/bin ;
OpenSTA /home/claude/.local/bin/sta ; liberty = IHP SG13G2 typ 1.20V 25C.
Intermediate .v / logs go to a TEMP workdir (keeps aes_fsm/ to the two owned files);
pass --workdir DIR to keep them. Run:  python3 sbox_cost.py
"""
import os, sys, re, subprocess, tempfile, shutil

# NOTE: /usr/local/src/yosys-build/yosys in this image was built WITHOUT the `abc`
# command; the /home/claude/.local release yosys (0.58) carries abc + its bundled
# yosys-abc, so we drive synthesis with it. Same liberty, same recipe as the SHA anchor.
YOSYS = "/home/claude/.local/bin/yosys"
STA   = "/home/claude/.local/bin/sta"
IVERILOG = "/usr/local/bin/iverilog"
VVP   = "/usr/local/bin/vvp"
LIB   = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
HERE  = os.path.dirname(os.path.abspath(__file__))
RTL_SBOX = os.path.join(HERE, "aes_sbox.v")   # the RTL agent's LUT form

# ---- MEASURED anchor (shared with the SHA compose) --------------------------
E_SHA_SLICE = 232.0      # fJ/op, measured static-CMOS sha_slice            [MEAS]
N_SHA_SLICE = 63         # cells, same-recipe re-synth (calibration basis)  [MEAS/COMPOSED]
E_CELL      = E_SHA_SLICE / N_SHA_SLICE          # 3.683 fJ/cell/op         [MEAS-anchor]

# ============================================================================
# 1. GF(2^8) AES field, reference S-box, canonical oracle
# ============================================================================
def gf_mul(a, b, poly=0x11B):
    r = 0
    for _ in range(8):
        if b & 1: r ^= a
        b >>= 1; a <<= 1
        if a & 0x100: a ^= poly
    return r

def gf_inv(a):
    if a == 0: return 0
    r = 1
    for _ in range(254): r = gf_mul(r, a)
    return r

def aes_affine(y):
    s = 0
    for i in range(8):
        bit = ((y >> i) ^ (y >> ((i+4) % 8)) ^ (y >> ((i+5) % 8)) ^
               (y >> ((i+6) % 8)) ^ (y >> ((i+7) % 8))) & 1
        s |= (bit << i)
    return s ^ 0x63

REF_SBOX = [aes_affine(gf_inv(x)) for x in range(256)]

# canonical published AES S-box (FIPS-197 Fig. 7) -- independent oracle
CANON = [
0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]

# ============================================================================
# 2. Composite tower GF((2^4)^2), isomorphism, verified S-box, linear matrices
# ============================================================================
def g2_mul(a, b):
    a1=(a>>1)&1; a0=a&1; b1=(b>>1)&1; b0=b&1
    return (((a1&b1)^(a1&b0)^(a0&b1))<<1) | ((a1&b1)^(a0&b0))
def g2_sq(a):   return g2_mul(a, a)
def g2_inv(a):  return g2_sq(a) if a else 0

def mk_g4(PHI):
    def mul(a, b):
        a1=(a>>2)&3; a0=a&3; b1=(b>>2)&3; b0=b&3
        t=g2_mul(a1,b1)
        return ((t ^ g2_mul(a1,b0) ^ g2_mul(a0,b1))<<2) | (g2_mul(t,PHI) ^ g2_mul(a0,b0))
    def sq(a): return mul(a, a)
    def inv(a):
        if a==0: return 0
        a1=(a>>2)&3; a0=a&3
        d = g2_mul(PHI, g2_sq(a1)) ^ g2_mul(a0,a1) ^ g2_sq(a0)
        di = g2_inv(d)
        return ((g2_mul(a1,di))<<2) | g2_mul(a1^a0, di)
    return mul, sq, inv

def mk_g8(g4_mul, g4_sq, g4_inv, LAM):
    def mul(a, b):
        a1=(a>>4)&0xF; a0=a&0xF; b1=(b>>4)&0xF; b0=b&0xF
        t=g4_mul(a1,b1)
        return ((t ^ g4_mul(a1,b0) ^ g4_mul(a0,b1))<<4) | (g4_mul(t,LAM) ^ g4_mul(a0,b0))
    def inv(a):
        if a==0: return 0
        a1=(a>>4)&0xF; a0=a&0xF
        d = g4_mul(LAM, g4_sq(a1)) ^ g4_mul(a0,a1) ^ g4_sq(a0)
        di = g4_inv(d)
        return ((g4_mul(a1,di))<<4) | g4_mul(a1^a0, di)
    return mul, inv

def find_tower():
    """Return (PHI, LAM, beta, g8_mul, g8_inv) for a tower whose composite S-box == REF."""
    for PHI in range(1, 4):
        g4_mul, g4_sq, g4_inv = mk_g4(PHI)
        if any(g4_mul(a, g4_inv(a)) != 1 for a in range(1, 16)):
            continue
        for LAM in range(1, 16):
            g8_mul, g8_inv = mk_g8(g4_mul, g4_sq, g4_inv, LAM)
            if any(g8_mul(a, g8_inv(a)) != 1 for a in range(1, 256)):
                continue
            # beta = root of AES poly x^8+x^4+x^3+x+1 in the composite field
            def paes(b):
                b2=g8_mul(b,b); b4=g8_mul(b2,b2); b8=g8_mul(b4,b4); b3=g8_mul(b2,b)
                return b8 ^ b4 ^ b3 ^ b ^ 1
            for beta in (b for b in range(256) if paes(b)==0):
                cols=[1]*8
                acc=1
                for i in range(8):
                    cols[i]=acc; acc=g8_mul(acc,beta)
                def T(x, cols=cols):
                    o=0
                    for i in range(8):
                        if (x>>i)&1: o^=cols[i]
                    return o
                Tf=[T(x) for x in range(256)]
                if len(set(Tf))!=256: continue
                Ti=[0]*256
                for x in range(256): Ti[Tf[x]]=x
                sbox=[aes_affine(Ti[g8_inv(Tf[x])]) for x in range(256)]
                if sbox==REF_SBOX:
                    return PHI, LAM, beta, Tf, Ti
    raise RuntimeError("no tower reproduced the reference S-box")

def lin_matrix_from_values(apply_to_unit):
    """8x8 bit matrix M with M[j][i] = bit j of apply_to_unit(1<<i)."""
    return [[(apply_to_unit(1<<i) >> j) & 1 for i in range(8)] for j in range(8)]

# ============================================================================
# 3. Verilog emission (composite form + MixColumns + AddRoundKey)
# ============================================================================
def xor_assign(dst, srcbus, srcbits, const=0):
    terms = [f"{srcbus}[{i}]" for i in srcbits]
    body = " ^ ".join(terms) if terms else "1'b0"
    if const: body = (f"{body} ^ 1'b1") if terms else "1'b1"
    return f"  assign {dst} = {body};"

def emit_composite(PHI, LAM, Tf, Ti):
    # M_in = T  (rows j -> input bits i); columns of T are T applied to unit vectors
    Min = lin_matrix_from_values(lambda v: Tf[v])          # w = Min . in
    # affine linear part A (no const): bit i = y_i ^ y_{i+4} ^ y_{i+5} ^ y_{i+6} ^ y_{i+7}
    def A_lin(y):
        s=0
        for i in range(8):
            b=((y>>i)^(y>>((i+4)%8))^(y>>((i+5)%8))^(y>>((i+6)%8))^(y>>((i+7)%8)))&1
            s|=b<<i
        return s
    # M_out = A_lin . Tinv  (apply Tinv to u, then affine linear part); const 0x63 added after
    Mout = lin_matrix_from_values(lambda v: A_lin(Ti[v]))  # o = Mout . u ^ 0x63
    assert PHI == 2 and LAM == 8, "emitter specialized for PHI=2, LAM=8"
    v = []
    v.append("// GENERATED by sbox_cost.py -- Canright-style composite-field S-box")
    v.append(f"// tower GF((2^4)^2)/GF(2^2): PHI={PHI}, LAM={LAM}; verified == FIPS-197 table")
    v.append("module g2mul(input [1:0] a, input [1:0] b, output [1:0] o);")
    v.append("  assign o[1]=(a[1]&b[1])^(a[1]&b[0])^(a[0]&b[1]);")
    v.append("  assign o[0]=(a[1]&b[1])^(a[0]&b[0]);")
    v.append("endmodule")
    v.append("module g4mul(input [3:0] a, input [3:0] b, output [3:0] o);")
    v.append("  wire [1:0] t,p,q,r; wire [1:0] sc;")
    v.append("  g2mul u0(a[3:2],b[3:2],t);")
    v.append("  g2mul u1(a[3:2],b[1:0],p);")
    v.append("  g2mul u2(a[1:0],b[3:2],q);")
    v.append("  g2mul u3(a[1:0],b[1:0],r);")
    v.append("  assign sc={t[1]^t[0],t[1]};           // scale by PHI=2")
    v.append("  assign o[3:2]=t^p^q;")
    v.append("  assign o[1:0]=sc^r;")
    v.append("endmodule")
    v.append("module g4sq(input [3:0] a, output [3:0] o);")
    v.append("  wire [1:0] a1s={a[3],a[3]^a[2]};        // g2sq(a_hi)")
    v.append("  wire [1:0] a0s={a[1],a[1]^a[0]};        // g2sq(a_lo)")
    v.append("  wire [1:0] sc ={a1s[1]^a1s[0],a1s[1]};  // scalePHI(a_hi^2)")
    v.append("  assign o[3:2]=a1s;")
    v.append("  assign o[1:0]=sc^a0s;")
    v.append("endmodule")
    v.append("module g4inv(input [3:0] a, output [3:0] o);")
    v.append("  wire [1:0] a1sq={a[3],a[3]^a[2]};")
    v.append("  wire [1:0] scp ={a1sq[1]^a1sq[0],a1sq[1]}; // PHI*a_hi^2")
    v.append("  wire [1:0] a0a1; g2mul m1(a[1:0],a[3:2],a0a1);")
    v.append("  wire [1:0] a0sq={a[1],a[1]^a[0]};")
    v.append("  wire [1:0] delta=scp^a0a1^a0sq;")
    v.append("  wire [1:0] di={delta[1],delta[1]^delta[0]}; // g2inv=g2sq")
    v.append("  wire [1:0] hi; g2mul m2(a[3:2],di,hi);")
    v.append("  wire [1:0] lo; g2mul m3(a[3:2]^a[1:0],di,lo);")
    v.append("  assign o={hi,lo};")
    v.append("endmodule")
    v.append("module g8inv(input [7:0] x, output [7:0] o);")
    v.append("  wire [3:0] a1=x[7:4], a0=x[3:0];")
    v.append("  wire [3:0] a1sq; g4sq s1(a1,a1sq);")
    v.append("  wire [3:0] a0sq; g4sq s2(a0,a0sq);")
    v.append("  wire [3:0] lamsq; g4mul ml(a1sq,4'd8,lamsq);   // scale by LAM=8")
    v.append("  wire [3:0] a0a1; g4mul m1(a0,a1,a0a1);")
    v.append("  wire [3:0] delta=lamsq^a0a1^a0sq;")
    v.append("  wire [3:0] di; g4inv iv(delta,di);")
    v.append("  wire [3:0] hi; g4mul m2(a1,di,hi);")
    v.append("  wire [3:0] lo; g4mul m3(a1^a0,di,lo);")
    v.append("  assign o={hi,lo};")
    v.append("endmodule")
    v.append("module aes_sbox_comp(input [7:0] in, output [7:0] o);")
    v.append("  wire [7:0] w;")
    for j in range(8):
        v.append(xor_assign(f"w[{j}]", "in", [i for i in range(8) if Min[j][i]], 0))
    v.append("  wire [7:0] u; g8inv gi(w,u);")
    for j in range(8):
        cst = (0x63 >> j) & 1
        v.append(xor_assign(f"o[{j}]", "u", [i for i in range(8) if Mout[j][i]], cst))
    v.append("endmodule")
    return "\n".join(v) + "\n"

MIXCOL_V = r"""
module aes_mixcol32(input [31:0] in, output [31:0] o);
  function [7:0] xt; input [7:0] a; xt=(a<<1)^(a[7]?8'h1b:8'h00); endfunction
  wire [7:0] a0=in[31:24], a1=in[23:16], a2=in[15:8], a3=in[7:0];
  assign o[31:24]= xt(a0) ^ (xt(a1)^a1) ^ a2 ^ a3;
  assign o[23:16]= a0 ^ xt(a1) ^ (xt(a2)^a2) ^ a3;
  assign o[15:8] = a0 ^ a1 ^ xt(a2) ^ (xt(a3)^a3);
  assign o[7:0]  = (xt(a0)^a0) ^ a1 ^ a2 ^ xt(a3);
endmodule
module aes_mixcolumns(input [127:0] s, output [127:0] o);
  aes_mixcol32 c0(s[127:96],o[127:96]);
  aes_mixcol32 c1(s[95:64], o[95:64]);
  aes_mixcol32 c2(s[63:32], o[63:32]);
  aes_mixcol32 c3(s[31:0],  o[31:0]);
endmodule
"""

ADDRK_V = r"""
module aes_addroundkey(input [127:0] s, input [127:0] k, output [127:0] o);
  assign o = s ^ k;
endmodule
"""

# Python MixColumns reference (for checking the Verilog)
def py_xt(a): return ((a << 1) ^ (0x1b if a & 0x80 else 0)) & 0xFF
def py_mixcol(col):  # col = [a0,a1,a2,a3]
    a0,a1,a2,a3 = col
    return [py_xt(a0)^(py_xt(a1)^a1)^a2^a3,
            a0^py_xt(a1)^(py_xt(a2)^a2)^a3,
            a0^a1^py_xt(a2)^(py_xt(a3)^a3),
            (py_xt(a0)^a0)^a1^a2^py_xt(a3)]

# ============================================================================
# 4. Tool drivers
# ============================================================================
def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def iverilog_check_sbox(wd, src_v, top):
    """Simulate `top`(in->o) over all 256 inputs; return list of 256 outputs."""
    tb = os.path.join(wd, f"tb_{top}.v")
    vvpf = os.path.join(wd, f"tb_{top}.vvp")
    with open(tb, "w") as f:
        f.write(f"""module tb; reg [7:0] in; wire [7:0] o; integer i;
{top} dut(.in(in), .o(o));
initial begin for(i=0;i<256;i=i+1) begin in=i[7:0]; #1 $display("%0d %0d", i, o); end $finish; end
endmodule
""")
    r = run([IVERILOG, "-o", vvpf, "-g2012", src_v, tb])
    if r.returncode != 0:
        raise RuntimeError("iverilog compile failed:\n" + r.stderr)
    r = run([VVP, vvpf])
    out = [None]*256
    for line in r.stdout.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s*$", line)
        if m: out[int(m.group(1))] = int(m.group(2)) & 0xFF
    return out

def iverilog_check_mixcol(wd, src_v):
    tb = os.path.join(wd, "tb_mix.v"); vvpf = os.path.join(wd, "tb_mix.vvp")
    with open(tb, "w") as f:
        f.write("""module tb; reg [31:0] in; wire [31:0] o; integer i;
aes_mixcol32 dut(.in(in),.o(o));
initial begin
  in=32'hdb135345; #1 $display("%h",o);
  in=32'hf20a225c; #1 $display("%h",o);
  in=32'h01010101; #1 $display("%h",o);
  in=32'hc6c6c6c6; #1 $display("%h",o);
  in=32'h2d26314c; #1 $display("%h",o);
  $finish; end endmodule
""")
    r = run([IVERILOG, "-o", vvpf, "-g2012", src_v, tb])
    if r.returncode != 0:
        raise RuntimeError("iverilog mixcol compile failed:\n" + r.stderr)
    r = run([VVP, vvpf])
    vals = [int(x, 16) for x in r.stdout.split()
            if re.fullmatch(r"[0-9a-fA-F]{8}", x)]
    return vals

def yosys_synth(wd, src_v, top, tag):
    """Map `top` to SG13G2 and return physical cell count (sg13g2_* only), chip area
    (um^2), combinational logic depth (ltp levels), the mapped netlist, and a cell-type
    histogram. ltp runs after `read_liberty -lib` so it knows the mapped cells' pins."""
    mapped = os.path.join(wd, f"{tag}.mapped.v")
    ys = os.path.join(wd, f"{tag}.ys")
    with open(ys, "w") as f:
        f.write(f"""read_verilog -sv {src_v}
hierarchy -top {top}
synth -flatten -top {top}
abc -liberty {LIB}
opt_clean
write_verilog -noattr {mapped}
stat -liberty {LIB}
read_liberty -lib {LIB}
ltp
""")
    r = run([YOSYS, "-s", ys])
    log = r.stdout + r.stderr
    # physical cell count = sum of mapped sg13g2_* cells (excludes $scopeinfo pseudo-cells)
    types = {}
    for mm in re.finditer(r"^\s*(\d+)\s+[\d.eE+\-]+\s+(sg13g2_\S+)\s*$", log, re.M):
        types[mm.group(2)] = int(mm.group(1))
    cells = sum(types.values()) or None
    area = None
    m = re.search(r"Chip area for module.*?:\s+([\d.]+)", log)
    if m: area = float(m.group(1))
    depth = None
    m = re.search(r"Longest topological path.*?length=(\d+)", log, re.S)
    if m: depth = int(m.group(1))
    return dict(cells=cells, area=area, depth=depth, mapped=mapped, types=types, log=log)

def opensta_path_ns(wd, mapped_v, top):
    tcl = os.path.join(wd, f"sta_{top}.tcl")
    with open(tcl, "w") as f:
        f.write(f"""read_liberty {LIB}
read_verilog {mapped_v}
link_design {top}
set_max_delay -from [all_inputs] -to [all_outputs] 0
report_checks -path_delay max -group_count 1 -digits 4
exit
""")
    r = run([STA, "-no_init", "-exit", tcl])
    log = r.stdout + r.stderr
    m = re.search(r"([\d.]+)\s+data arrival time", log)
    return (float(m.group(1)) if m else None), log

# ============================================================================
# 5. Main
# ============================================================================
def banner(s): print("\n" + "=" * 78 + "\n" + s + "\n" + "=" * 78)

def main():
    keep = None
    if "--workdir" in sys.argv:
        keep = sys.argv[sys.argv.index("--workdir") + 1]
        os.makedirs(keep, exist_ok=True); wd = keep
    else:
        wd = tempfile.mkdtemp(prefix="sbox_")

    banner("AES-128 S-BOX COST  --  self-timed static-CMOS FSM campaign (SG13G2 130nm)")
    print("workdir:", wd, "(temp)" if keep is None else "(kept)")

    # -- verification layer 1: reference table vs canonical oracle --
    assert REF_SBOX == CANON, "GF-derived S-box != canonical FIPS-197 table"
    print("[VERIFY] GF(2^8)-derived S-box == canonical FIPS-197 table: 256/256 PASS")

    PHI, LAM, beta, Tf, Ti = find_tower()
    print("[VERIFY] composite tower GF((2^4)^2) PHI=%d LAM=%d beta=0x%02x : "
          "Python composite S-box == reference 256/256 PASS" % (PHI, LAM, beta))

    # -- emit Verilog --
    comp_v = os.path.join(wd, "aes_sbox_comp.v")
    with open(comp_v, "w") as f: f.write(emit_composite(PHI, LAM, Tf, Ti))
    mix_v = os.path.join(wd, "aes_mix.v")
    with open(mix_v, "w") as f: f.write(MIXCOL_V)
    ark_v = os.path.join(wd, "aes_ark.v")
    with open(ark_v, "w") as f: f.write(ADDRK_V)

    # LUT form: prefer the RTL agent's aes_sbox.v; else emit a local copy
    if os.path.exists(RTL_SBOX):
        lut_v, lut_top = RTL_SBOX, "aes_sbox"
        print("[INPUT ] LUT form = RTL agent's aes_sbox.v (module aes_sbox)")
    else:
        lut_v = os.path.join(wd, "aes_sbox_lut.v"); lut_top = "aes_sbox_lut"
        with open(lut_v, "w") as f:
            f.write("module aes_sbox_lut(input [7:0] in, output reg [7:0] o);\n always @(*) case(in)\n")
            for i in range(256): f.write(f"  8'd{i}:o=8'd{REF_SBOX[i]};\n")
            f.write("  default:o=8'h00; endcase\nendmodule\n")
        print("[INPUT ] LUT form = locally emitted aes_sbox_lut.v (RTL file absent)")

    # -- verification layer 2: both Verilog forms vs reference (iverilog, 256) --
    lut_out = iverilog_check_sbox(wd, lut_v, lut_top)
    comp_out = iverilog_check_sbox(wd, comp_v, "aes_sbox_comp")
    lut_ok = (lut_out == REF_SBOX); comp_ok = (comp_out == REF_SBOX)
    print("[VERIFY] iverilog LUT  form  vs reference: %s" %
          ("256/256 PASS" if lut_ok else "FAIL %d mismatches" % sum(a!=b for a,b in zip(lut_out,REF_SBOX))))
    print("[VERIFY] iverilog comp form  vs reference: %s" %
          ("256/256 PASS" if comp_ok else "FAIL %d mismatches" % sum(a!=b for a,b in zip(comp_out,REF_SBOX))))
    assert lut_ok and comp_ok, "a Verilog S-box form does not match the reference"

    mix_chk = iverilog_check_mixcol(wd, mix_v)
    mix_ref = [int.from_bytes(bytes(py_mixcol(list(v.to_bytes(4, "big")))), "big")
               for v in (0xdb135345, 0xf20a225c, 0x01010101, 0xc6c6c6c6, 0x2d26314c)]
    mix_ok = (mix_chk == mix_ref)
    print("[VERIFY] iverilog MixColumns vs GF reference: %s" % ("PASS" if mix_ok else "FAIL %r vs %r" % (mix_chk, mix_ref)))
    assert mix_ok

    # -- synthesis --
    banner("SYNTHESIS  (yosys: synth -flatten; abc -liberty SG13G2; opt_clean; stat; ltp)")
    S_lut  = yosys_synth(wd, lut_v, lut_top, "lut")
    S_comp = yosys_synth(wd, comp_v, "aes_sbox_comp", "comp")
    S_mix  = yosys_synth(wd, mix_v, "aes_mixcolumns", "mix")
    S_ark  = yosys_synth(wd, ark_v, "aes_addroundkey", "ark")

    for name, S in (("S-box LUT/ROM (256x8)", S_lut), ("S-box composite (Canright)", S_comp),
                    ("MixColumns (128b, 4 col)", S_mix), ("AddRoundKey (128b XOR)", S_ark)):
        print("%-30s cells=%-5s area=%-10s depth(levels)=%-4s" %
              (name, S["cells"], ("%.2f" % S["area"]) if S["area"] else "n/a", S["depth"]))

    # -- OpenSTA critical path (ns) --
    t_lut,_  = opensta_path_ns(wd, S_lut["mapped"],  lut_top)
    t_comp,_ = opensta_path_ns(wd, S_comp["mapped"], "aes_sbox_comp")
    t_mix,_  = opensta_path_ns(wd, S_mix["mapped"],  "aes_mixcolumns")
    print("\nOpenSTA max comb path [COMPOSED/STA]:  LUT=%.3f ns  comp=%.3f ns  MixCol=%.3f ns"
          % (t_lut or 0, t_comp or 0, t_mix or 0))

    # ========================================================================
    # 6. ENERGY COMPOSITION from the MEASURED anchor
    # ========================================================================
    banner("ENERGY  [MEAS-anchor sha_slice 232 fJ / 63 cells = %.3f fJ/cell/op]" % E_CELL)
    e_lut  = S_lut["cells"]  * E_CELL
    e_comp = S_comp["cells"] * E_CELL
    e_mix  = S_mix["cells"]  * E_CELL
    e_ark  = S_ark["cells"]  * E_CELL
    print("per S-box eval [COMPOSED]:  LUT = %.1f fJ (%d cells)   composite = %.1f fJ (%d cells)"
          % (e_lut, S_lut["cells"], e_comp, S_comp["cells"]))
    print("  (same per-cell basis & ~alpha as the SHA compose; activity sensitivity below)")

    # per round: 16 S-boxes (SubBytes) + ShiftRows(0) + MixColumns + AddRoundKey
    def round_energy(e_sbox, with_mix=True):
        return 16*e_sbox + (e_mix if with_mix else 0.0) + e_ark
    r_lut  = round_energy(e_lut);  r_comp = round_energy(e_comp)
    r_lut_f = round_energy(e_lut, False); r_comp_f = round_energy(e_comp, False)
    print("\nper ROUND combinational [COMPOSED]  (16 S-box + ShiftRows 0 + MixCol %d c + AddRK %d c):"
          % (S_mix["cells"], S_ark["cells"]))
    print("  rounds 1-9 (with MixColumns):  LUT = %.1f fJ   composite = %.1f fJ" % (r_lut, r_comp))
    print("  round 10   (no MixColumns)  :  LUT = %.1f fJ   composite = %.1f fJ" % (r_lut_f, r_comp_f))

    # per AES-128 encrypt:
    #   data S-boxes: 16/round x 10 = 160 ; key-expansion SubWord: 4/round x 10 = 40 -> 200
    #   MixColumns: rounds 1-9 (9x) ; AddRoundKey: initial + 10 rounds = 11x
    N_SBOX_DATA = 160; N_SBOX_KEY = 40; N_SBOX_TOT = N_SBOX_DATA + N_SBOX_KEY
    def encrypt_energy(e_sbox):
        return N_SBOX_TOT*e_sbox + 9*e_mix + 11*e_ark
    enc_lut  = encrypt_energy(e_lut);  enc_comp = encrypt_energy(e_comp)
    print("\nper AES-128 ENCRYPT combinational [COMPOSED]  (%d S-box evals = %d data +%d key,"
          % (N_SBOX_TOT, N_SBOX_DATA, N_SBOX_KEY))
    print("   9x MixColumns, 11x AddRoundKey):")
    print("  LUT form       = %.2f pJ   (S-box share %.0f%%)"
          % (enc_lut/1e3, 100*N_SBOX_TOT*e_lut/enc_lut))
    print("  composite form = %.2f pJ   (S-box share %.0f%%)"
          % (enc_comp/1e3, 100*N_SBOX_TOT*e_comp/enc_comp))
    print("  --> the S-box DOMINATES the round/encrypt combinational energy either way.")

    # activity sensitivity bracket [EST]
    print("\nactivity sensitivity [EST] (per-cell scales ~linearly with alpha; anchor ~0.48):")
    for a in (0.25, 0.5, 1.0):
        sc = a/0.476
        print("  alpha=%.2f -> per-S-box: LUT %.1f fJ  composite %.1f fJ"
              % (a, e_lut*sc, e_comp*sc))

    # ========================================================================
    # 7. ROUND CRITICAL-PATH DEPTH -> replica-done sharpness
    # ========================================================================
    banner("ROUND CRITICAL-PATH DEPTH  -> self-timed replica-done delay")
    print("round path = S-box depth + MixColumns depth (SubBytes -> MixColumns series).")
    print("  LUT  S-box : %s levels / %.3f ns" % (S_lut["depth"], t_lut or 0))
    print("  comp S-box : %s levels / %.3f ns   (composite is DEEPER -> the area/depth trade)"
          % (S_comp["depth"], t_comp or 0))
    print("  MixColumns : %s levels / %.3f ns" % (S_mix["depth"], t_mix or 0))
    print("  round path (comp S-box + MixCol) ~ %s levels / %.3f ns [COMPOSED]"
          % ((S_comp["depth"] + S_mix["depth"]) if S_comp["depth"] and S_mix["depth"] else "n/a",
             (t_comp or 0)+(t_mix or 0)))
    print("  round path (LUT  S-box + MixCol) ~ %s levels / %.3f ns [COMPOSED]"
          % ((S_lut["depth"] + S_mix["depth"]) if S_lut["depth"] and S_mix["depth"] else "n/a",
             (t_lut or 0)+(t_mix or 0)))
    print("CONTRAST vs SHA-256: SHA's round was a 32b 5-operand ADDER ripple (5.64 ns,")
    print("deep carry chain). AES's round is substitution + XOR-shallow MixColumns -> a")
    print("SHORTER, more uniform settle -> a SHARPER power-settle edge for current-sense /")
    print("in-kind replica completion (the 'done' is easier to place and tighter).")

    if keep is None:
        shutil.rmtree(wd, ignore_errors=True)

if __name__ == "__main__":
    main()
