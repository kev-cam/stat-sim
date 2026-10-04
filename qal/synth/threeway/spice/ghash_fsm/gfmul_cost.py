#!/usr/bin/env python3
"""GHASH GF(2^128) carry-less MULTIPLIER cost characterization -- self-timed static-CMOS
FSM campaign (IHP SG13G2 130 nm). This is GHASH's *distinctive* element, the analog of the
AES S-box and the SHA-256 adder: in GHASH the whole datapath is one GF(2^128) carry-less
(clmul) multiply-reduce. NO S-box (substitution), NO carry chain (carry-LESS) -> the purest
XOR/AND datapath of the three ciphers. This script characterizes that multiply THREE ways
and feeds per-multiply / per-block / per-frame fJ to the energy-composition agent.

WHAT IT DOES (all synthesis is REAL; nothing hand-waved):
  (a) BIT-SERIAL  -- the classic 128-step shift + conditional-XOR (NIST SP 800-38D Alg 1).
      ONE step's combinational logic is synthesized; the iterative multiplier reuses it for
      128 cycles, so per-multiply cost = step_cells x 128. (A fully-spatial 128-stage unroll
      is also synthesized, as a cross-check and to show the serial-chain depth/latency.)
  (b) FULLY PARALLEL schoolbook -- 128x128 carry-less partial products (shift-and-XOR) +
      mod-P reduction, as a single combinational cone (one "round" / block).
  (c) KARATSUBA parallel -- 2-way recursive split (3 subproducts/level: the "3-way
      recursion"), down to 1-bit base, + the same reduction. The low-AREA parallel form.

GF(2^128) field = the GCM field: P = x^128 + x^7 + x^2 + x + 1, with GCM's REFLECTED bit
order (bit 0 = MSB of byte 0 = the x^0 coefficient; "multiply by x" is a RIGHT shift).

VERIFICATION (never self-asserted -- GCM's #1 bug is the bit reflection):
  * Python reference GF(2^128) multiply implemented THREE independent ways and cross-checked:
      (1) NIST SP 800-38D Alg 1 directly (R=0xe1<<120, right-shift) -- THE definition;
      (2) reflect -> standard clmul mod P -> reflect;
      (3) reflect -> clmul -> x^k-mod-P reduction matrix -> reflect  (== the RTL structure).
    All three must agree on 2000 random pairs.
  * The python ref is anchored to KNOWN-GOOD crypto: H = AES_{k=0}(0) == 66e94bd4...342b2e,
    the empty-message GCM tag (k=iv=0) == 58e2fcce...e7455a (NIST SP 800-38D), and a random
    full GCM (AAD+PT) tag+ciphertext == pycryptodome. (No RTL number is reported until this
    passes.)
  * EACH of the three Verilog multiplier forms is simulated with iverilog over the anchor
    vectors + 300 random pairs and must match the validated python ref BEFORE it is costed.

ENERGY: composed from the MEASURED anchor sha_slice = 232 fJ / 63 cells = 3.683 fJ/cell/op,
tagged [MEAS-anchor]/[COMPOSED]/[EST]. No SPICE (USER DIRECTIVE 2026-10-02: stat-sim over SPICE).

TOOLS: yosys /home/claude/.local/bin/yosys (carries abc; the /usr/local/src/yosys-build
binary was built without the `abc` command) ; iverilog/vvp /usr/local/bin ; OpenSTA
/home/claude/.local/bin/sta ; liberty = IHP SG13G2 typ 1.20V 25C ; pycryptodome present.
Generated .v / logs go to a TEMP workdir (keeps ghash_fsm/ to the two owned files);
pass --workdir DIR to keep them. Run:  python3 gfmul_cost.py
"""
import os, sys, re, subprocess, tempfile, shutil, random

YOSYS = "/home/claude/.local/bin/yosys"
STA   = "/home/claude/.local/bin/sta"
IVERILOG = "/usr/local/bin/iverilog"
VVP   = "/usr/local/bin/vvp"
LIB   = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
HERE  = os.path.dirname(os.path.abspath(__file__))

# ---- MEASURED anchor (shared with the SHA + AES composes) -------------------
E_SHA_SLICE = 232.0      # fJ/op, measured static-CMOS sha_slice            [MEAS]
N_SHA_SLICE = 63         # cells, same-recipe re-synth (calibration basis)  [MEAS/COMPOSED]
E_CELL      = E_SHA_SLICE / N_SHA_SLICE          # 3.683 fJ/cell/op         [MEAS-anchor]

MASK128 = (1 << 128) - 1
R_GCM   = 0xe1 << 120          # 11100001 || 0^120  (NIST SP 800-38D reduction constant)

# ============================================================================
# 1. GF(2^128) reference -- three independent implementations
# ============================================================================
def gcm_mult_nist(X, Y):
    """NIST SP 800-38D Algorithm 1. X,Y = 128-bit ints (int.from_bytes(block,'big'))."""
    Z, V = 0, Y
    for i in range(128):
        if (X >> (127 - i)) & 1:          # X bit i from the LEFT = int bit (127-i)
            Z ^= V
        if V & 1:                         # LSB (GCM) = rightmost = int bit 0
            V = (V >> 1) ^ R_GCM
        else:
            V >>= 1
    return Z & MASK128

def bitrev128(x):
    r = 0
    for i in range(128):
        if (x >> i) & 1:
            r |= 1 << (127 - i)
    return r

def clmul(a, b):
    """carry-less product, STANDARD convention (bit i = x^i); returns up to 255-bit int."""
    p = 0
    for i in range(128):
        if (a >> i) & 1:
            p ^= b << i
    return p

def xk_mod_p(k):
    """x^k mod P in standard convention, as a 128-bit int. Drives the RTL reduction net."""
    if k < 128:
        return 1 << k
    cur = (1 << 7) ^ (1 << 2) ^ (1 << 1) ^ 1     # x^128 mod P
    for _ in range(128, k):
        cur <<= 1
        if (cur >> 128) & 1:
            cur ^= (1 << 128)
            cur ^= (1 << 7) ^ (1 << 2) ^ (1 << 1) ^ 1
    return cur & MASK128

# precompute reduction columns once
XK = [xk_mod_p(k) for k in range(255)]

def reduce_matrix(p):
    r = 0
    for k in range(255):
        if (p >> k) & 1:
            r ^= XK[k]
    return r

def gcm_mult_reflect(X, Y):
    return bitrev128(reduce_matrix(clmul(bitrev128(X), bitrev128(Y))))

def gcm_mult_reflect_poly(X, Y):
    """same, but reduction by explicit fold (independent of XK) -- third witness."""
    p = clmul(bitrev128(X), bitrev128(Y))
    for k in range(254, 127, -1):
        if (p >> k) & 1:
            p ^= (1 << k)
            p ^= (1 << (k-121)) ^ (1 << (k-126)) ^ (1 << (k-127)) ^ (1 << (k-128))
    return bitrev128(p & MASK128)

# ============================================================================
# 2. Crypto anchors (pycryptodome) -- the python ref is validated against KNOWN good
# ============================================================================
def crypto_anchor_checks():
    from Crypto.Cipher import AES
    out = []
    H = int.from_bytes(AES.new(b'\x00'*16, AES.MODE_ECB).encrypt(b'\x00'*16), 'big')
    h_ok = format(H, '032x') == "66e94bd4ef8a2c3b884cfa59ca342b2e"
    out.append(("H = AES_{k=0}(0) == 66e94bd4...342b2e", h_ok, format(H, '032x')))

    def ghash(Hk, A, C):
        def blocks(x):
            x = x + b'\x00'*((-len(x)) % 16)
            return [int.from_bytes(x[i:i+16], 'big') for i in range(0, len(x), 16)]
        Y = 0
        for blk in blocks(A): Y = gcm_mult_nist(Y ^ blk, Hk)
        for blk in blocks(C): Y = gcm_mult_nist(Y ^ blk, Hk)
        return gcm_mult_nist(Y ^ (((len(A)*8) << 64) | (len(C)*8)), Hk)

    def my_tag(key, nonce, aad, pt):
        ecb = AES.new(key, AES.MODE_ECB)
        Hk = int.from_bytes(ecb.encrypt(b'\x00'*16), 'big')
        J0 = nonce + b'\x00\x00\x00\x01'
        def inc32(b):
            n = (int.from_bytes(b[12:], 'big') + 1) & 0xffffffff
            return b[:12] + n.to_bytes(4, 'big')
        ct, ctr = b'', J0
        for i in range(0, len(pt), 16):
            ctr = inc32(ctr)
            ks = ecb.encrypt(ctr)
            ct += bytes(a ^ b for a, b in zip(pt[i:i+16], ks))
        S = ghash(Hk, aad, ct)
        return ct, (S ^ int.from_bytes(ecb.encrypt(J0), 'big')).to_bytes(16, 'big')

    # empty-message vector
    ct, tag = my_tag(b'\x00'*16, b'\x00'*12, b'', b'')
    pc = AES.new(b'\x00'*16, AES.MODE_GCM, nonce=b'\x00'*12)
    _, ptag = pc.encrypt_and_digest(b'')
    e_ok = tag == ptag == bytes.fromhex("58e2fccefa7e3061367f1d57a4e7455a")
    out.append(("empty-msg GCM tag (k=iv=0) == 58e2fcce...e7455a", e_ok, tag.hex()))

    # random full GCM
    key, nonce, aad, pt = os.urandom(16), os.urandom(12), os.urandom(53), os.urandom(96)
    ct, tag = my_tag(key, nonce, aad, pt)
    c = AES.new(key, AES.MODE_GCM, nonce=nonce); c.update(aad)
    pct, ptag = c.encrypt_and_digest(pt)
    r_ok = (ct == pct) and (tag == ptag)
    out.append(("random full GCM (53B AAD + 96B PT) ct+tag == pycryptodome", r_ok,
                "ct %s tag %s" % ("OK" if ct == pct else "BAD", "OK" if tag == ptag else "BAD")))
    return out, H

# ============================================================================
# 3. Verilog emission
# ============================================================================
def emit_reduce():
    """gf128_reduce: input [254:0] p (standard-conv clmul product), output [127:0] r = p mod P.
    r[j] = XOR of p[k] for all k with bit j set in (x^k mod P)."""
    cols = [[] for _ in range(128)]
    for k in range(255):
        v = XK[k]
        for j in range(128):
            if (v >> j) & 1:
                cols[j].append(k)
    L = ["module gf128_reduce(input [254:0] p, output [127:0] r);"]
    for j in range(128):
        terms = " ^ ".join("p[%d]" % k for k in cols[j])
        L.append("  assign r[%d] = %s;" % (j, terms))
    L.append("endmodule")
    return "\n".join(L) + "\n"

REFLECT_WRAP = r"""
// bit reflection (GCM order <-> standard x^i order) is pure wiring (0 cells)
module gfmul_{name}(input [127:0] a, input [127:0] b, output [127:0] o);
  wire [127:0] as, bs, rs;
  wire [254:0] p;
  genvar gi;
  generate for (gi=0; gi<128; gi=gi+1) begin: refl
    assign as[gi] = a[127-gi];
    assign bs[gi] = b[127-gi];
    assign o[gi]  = rs[127-gi];
  end endgenerate
  {core}
  gf128_reduce rd(p, rs);
endmodule
"""

CLMUL_SCHOOL = r"""
module clmul_school(input [127:0] a, input [127:0] b, output [254:0] p);
  integer i; reg [254:0] acc;
  always @(*) begin
    acc = 255'b0;
    for (i=0; i<128; i=i+1)
      if (a[i]) acc = acc ^ ({127'b0, b} << i);
  end
  assign p = acc;
endmodule
"""

CLMUL_KARA = r"""
module clmul_kara #(parameter N=128) (input [N-1:0] a, input [N-1:0] b, output [2*N-2:0] p);
  generate
    if (N == 1) begin: base
      assign p = a & b;
    end else begin: rec
      localparam H = N/2;
      wire [2*H-2:0] p0, p2, pm;
      wire [H-1:0] al = a[H-1:0],   ah = a[N-1:H];
      wire [H-1:0] bl = b[H-1:0],   bh = b[N-1:H];
      clmul_kara #(H) u0 (al, bl, p0);
      clmul_kara #(H) u2 (ah, bh, p2);
      clmul_kara #(H) um ((al^ah), (bl^bh), pm);
      wire [2*H-2:0] mid = pm ^ p0 ^ p2;
      wire [2*N-2:0] t0 = { {(2*N-1-(2*H-1)){1'b0}}, p0 };
      wire [2*N-2:0] tm = { {(2*N-1-(2*H-1)-H){1'b0}}, mid, {H{1'b0}} };
      wire [2*N-2:0] t2 = { p2, {(2*H){1'b0}} };
      assign p = t0 ^ tm ^ t2;
    end
  endgenerate
endmodule
"""

# bit-serial: ONE step (costed x128) + full 128-stage unroll (verified / depth cross-check)
SERIAL_STEP = r"""
module gfmul_serial_step(input [127:0] Zin, input [127:0] Vin, input xbit,
                         output [127:0] Zout, output [127:0] Vout);
  assign Zout = xbit ? (Zin ^ Vin) : Zin;
  wire [127:0] vsh = Vin >> 1;                 // multiply by x = RIGHT shift (GCM order)
  wire [127:0] Rc  = {8'he1, 120'b0};          // R = 0xe1 || 0^120
  assign Vout = Vin[0] ? (vsh ^ Rc) : vsh;
endmodule
"""

SERIAL_FULL = r"""
module gfmul_serial(input [127:0] a, input [127:0] b, output [127:0] o);
  // a = X (operand whose bits select), b = Y = V0
  wire [127:0] Z [0:128];
  wire [127:0] V [0:128];
  assign Z[0] = 128'b0;
  assign V[0] = b;
  genvar i;
  generate for (i=0; i<128; i=i+1) begin: step
    gfmul_serial_step s(Z[i], V[i], a[127-i], Z[i+1], V[i+1]);
  end endgenerate
  assign o = Z[128];
endmodule
"""

def emit_all(wd):
    red = emit_reduce()
    files = {}
    files["gf128_reduce.v"] = red
    files["clmul_school.v"] = CLMUL_SCHOOL
    files["clmul_kara.v"]   = CLMUL_KARA
    files["serial_step.v"]  = SERIAL_STEP
    files["serial_full.v"]  = SERIAL_FULL
    files["gfmul_parallel.v"] = red + CLMUL_SCHOOL + REFLECT_WRAP.format(
        name="parallel", core="clmul_school cm(as, bs, p);")
    files["gfmul_karatsuba.v"] = red + CLMUL_KARA + REFLECT_WRAP.format(
        name="karatsuba", core="clmul_kara #(128) cm(as, bs, p);")
    paths = {}
    for n, s in files.items():
        p = os.path.join(wd, n)
        with open(p, "w") as f:
            f.write(s)
        paths[n] = p
    return paths

# ============================================================================
# 4. Tool drivers (same recipe as the SHA anchor / AES S-box lane)
# ============================================================================
def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def iverilog_check_mul(wd, src_list, top, vectors, ref):
    """Simulate `top`(a,b->o) over vectors; compare to ref[(a,b)]. Return (#pass,#tot,mism)."""
    tb = os.path.join(wd, "tb_%s.v" % top)
    vvpf = os.path.join(wd, "tb_%s.vvp" % top)
    lines = ["module tb; reg [127:0] a,b; wire [127:0] o;",
             "%s dut(.a(a), .b(b), .o(o));" % top, "initial begin"]
    for (a, b) in vectors:
        lines.append("  a=128'h%032x; b=128'h%032x; #1 $display(\"%%032x\", o);" % (a, b))
    lines.append("  $finish; end endmodule")
    with open(tb, "w") as f:
        f.write("\n".join(lines) + "\n")
    r = run([IVERILOG, "-o", vvpf, "-g2012"] + src_list + [tb])
    if r.returncode != 0:
        raise RuntimeError("iverilog compile failed (%s):\n%s" % (top, r.stderr))
    r = run([VVP, vvpf])
    outs = [int(x, 16) for x in re.findall(r"^[0-9a-fA-F]{32}$", r.stdout, re.M)]
    npass = 0; mism = None
    for (a, b), got in zip(vectors, outs):
        exp = ref[(a, b)]
        if got == exp:
            npass += 1
        elif mism is None:
            mism = (a, b, got, exp)
    return npass, len(vectors), mism

def yosys_synth(wd, src_list, top, tag):
    mapped = os.path.join(wd, "%s.mapped.v" % tag)
    ys = os.path.join(wd, "%s.ys" % tag)
    reads = "\n".join("read_verilog -sv %s" % s for s in src_list)
    with open(ys, "w") as f:
        f.write("""%s
hierarchy -top %s
synth -flatten -top %s
abc -liberty %s
opt_clean
write_verilog -noattr %s
stat -liberty %s
read_liberty -lib %s
ltp
""" % (reads, top, top, LIB, mapped, LIB, LIB))
    r = run([YOSYS, "-s", ys])
    log = r.stdout + r.stderr
    types = {}
    for mm in re.finditer(r"^\s*(\d+)\s+[\d.eE+\-]+\s+(sg13g2_\S+)\s*$", log, re.M):
        types[mm.group(2)] = int(mm.group(1))
    cells = sum(types.values()) or None
    area = None
    m = re.search(r"Chip area for (?:top )?module.*?:\s+([\d.]+)", log)
    if m: area = float(m.group(1))
    depth = None
    m = re.search(r"Longest topological path.*?length=(\d+)", log, re.S)
    if m: depth = int(m.group(1))
    return dict(cells=cells, area=area, depth=depth, mapped=mapped, types=types, log=log)

def opensta_path_ns(wd, mapped_v, top):
    tcl = os.path.join(wd, "sta_%s.tcl" % top)
    with open(tcl, "w") as f:
        f.write("""read_liberty %s
read_verilog %s
link_design %s
set_max_delay -from [all_inputs] -to [all_outputs] 0
report_checks -path_delay max -group_count 1 -digits 4
exit
""" % (LIB, mapped_v, top))
    r = run([STA, "-no_init", "-exit", tcl])
    log = r.stdout + r.stderr
    m = re.search(r"([\d.]+)\s+data arrival time", log)
    return (float(m.group(1)) if m else None), log

def top_cellmix(types, n=6):
    return ", ".join("%s x%d" % (k.replace("sg13g2_", ""), v)
                     for k, v in sorted(types.items(), key=lambda kv: -kv[1])[:n])

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
        wd = tempfile.mkdtemp(prefix="gfmul_")

    banner("GHASH GF(2^128) MULTIPLIER COST -- self-timed static-CMOS FSM (SG13G2 130nm)")
    print("workdir:", wd, "(temp)" if keep is None else "(kept)")

    # -- verification layer 1: three python refs agree --
    random.seed(12345)
    pairs = [(random.getrandbits(128), random.getrandbits(128)) for _ in range(2000)]
    agree = all(gcm_mult_nist(a, b) == gcm_mult_reflect(a, b) == gcm_mult_reflect_poly(a, b)
                for a, b in pairs)
    print("[VERIFY] python GF(2^128) mult: NIST-alg == reflect+clmul+matrix == "
          "reflect+clmul+fold on 2000 random: %s" % ("PASS" if agree else "FAIL"))
    assert agree, "python GF multiply implementations disagree"

    # -- verification layer 2: python ref vs KNOWN crypto (pycryptodome + NIST vectors) --
    checks, H = crypto_anchor_checks()
    for name, ok, val in checks:
        print("[VERIFY] %-55s %s  (%s)" % (name, "PASS" if ok else "FAIL", val))
    assert all(ok for _, ok, _ in checks), "crypto anchor failed -- python ref not trusted"
    print("        -> python GF(2^128) multiply is the validated reference (NEVER self-asserted).")

    # -- emit Verilog --
    P = emit_all(wd)

    # -- verification layer 3: each RTL form vs the validated python ref (iverilog) --
    banner("RTL FUNCTIONAL VERIFICATION  (iverilog vs validated python ref)")
    GHASH_BLOCKS = [0x66e94bd4ef8a2c3b884cfa59ca342b2e,  # H
                    0xffffffffffffffffffffffffffffffff, 0x1, 1 << 127, 0xdeadbeef00000000cafe]
    vt = [(x, H) for x in GHASH_BLOCKS] + [(H, x) for x in GHASH_BLOCKS]
    random.seed(7)
    vt += [(random.getrandbits(128), random.getrandbits(128)) for _ in range(300)]
    ref = {(a, b): gcm_mult_nist(a, b) for (a, b) in vt}

    forms = [
        ("bit-serial (128-stage unroll)", [P["serial_step.v"], P["serial_full.v"]], "gfmul_serial"),
        ("parallel schoolbook",           [P["gfmul_parallel.v"]],                  "gfmul_parallel"),
        ("Karatsuba (recursive)",         [P["gfmul_karatsuba.v"]],                 "gfmul_karatsuba"),
    ]
    for label, srcs, top in forms:
        npass, ntot, mism = iverilog_check_mul(wd, srcs, top, vt, ref)
        status = "%d/%d PASS" % (npass, ntot) if npass == ntot else \
                 "FAIL %d/%d  first mism a=%032x b=%032x got=%032x exp=%032x" % \
                 ((npass, ntot) + mism)
        print("[VERIFY] %-32s vs python ref: %s" % (label, status))
        assert npass == ntot, "%s does not match the reference" % label

    # -- synthesis --
    banner("SYNTHESIS  (yosys: synth -flatten; abc -liberty SG13G2; opt_clean; stat; ltp)")
    S_step = yosys_synth(wd, [P["serial_step.v"]], "gfmul_serial_step", "step")
    S_ser  = yosys_synth(wd, [P["serial_step.v"], P["serial_full.v"]], "gfmul_serial", "serial")
    S_par  = yosys_synth(wd, [P["gfmul_parallel.v"]],  "gfmul_parallel",  "par")
    S_kar  = yosys_synth(wd, [P["gfmul_karatsuba.v"]], "gfmul_karatsuba", "kar")

    N_STEPS = 128
    rows = [
        ("bit-serial STEP (1 of 128)", S_step),
        ("bit-serial x128 (iterative)", None),   # computed below
        ("bit-serial unroll (spatial)", S_ser),
        ("parallel schoolbook",         S_par),
        ("Karatsuba parallel",          S_kar),
    ]
    print("%-30s %-7s %-11s %-9s" % ("form", "cells", "area um^2", "depth(lvls)"))
    for name, S in rows:
        if S is None:
            c = S_step["cells"] * N_STEPS
            print("%-30s %-7s %-11s %-9s  (= step x 128 cycles)" % (name, c, "-", "-"))
        else:
            print("%-30s %-7s %-11s %-9s" %
                  (name, S["cells"], ("%.1f" % S["area"]) if S["area"] else "n/a", S["depth"]))
    print("\ncell mix (top types):")
    print("  step     :", top_cellmix(S_step["types"]))
    print("  parallel :", top_cellmix(S_par["types"]))
    print("  karatsuba:", top_cellmix(S_kar["types"]))

    # -- OpenSTA critical path --
    t_step, _ = opensta_path_ns(wd, S_step["mapped"], "gfmul_serial_step")
    t_par,  _ = opensta_path_ns(wd, S_par["mapped"],  "gfmul_parallel")
    t_kar,  _ = opensta_path_ns(wd, S_kar["mapped"],  "gfmul_karatsuba")
    print("\nOpenSTA max comb path [COMPOSED/STA]: step=%.3f ns  parallel=%.3f ns  karatsuba=%.3f ns"
          % (t_step or 0, t_par or 0, t_kar or 0))

    # ========================================================================
    # 6. ENERGY COMPOSITION from the MEASURED anchor
    # ========================================================================
    banner("ENERGY  [MEAS-anchor sha_slice 232 fJ / 63 cells = %.3f fJ/cell/op]" % E_CELL)
    e_step = S_step["cells"] * E_CELL
    e_ser  = e_step * N_STEPS                     # iterative bit-serial reuses the step x128
    e_par  = S_par["cells"] * E_CELL
    e_kar  = S_kar["cells"] * E_CELL
    print("per-STEP (bit-serial)  [COMPOSED]: %7.1f fJ  (%d cells)" % (e_step, S_step["cells"]))
    print("per-MULTIPLY           [COMPOSED]:")
    print("  bit-serial (step x128): %8.1f fJ  (%d cells x 128 cyc)" % (e_ser, S_step["cells"]))
    print("  parallel schoolbook   : %8.1f fJ  (%d cells, one shot)" % (e_par, S_par["cells"]))
    print("  Karatsuba parallel    : %8.1f fJ  (%d cells, one shot)" % (e_kar, S_kar["cells"]))
    print("  --> bit-serial per-STEP x128 vs the one-shot parallel: same algebra, different")
    print("      spatial/temporal unfolding; compare the totals above.")

    # per GHASH block = one (Y XOR C_i) then one multiply. XOR = 128 cells.
    e_xor128 = 128 * E_CELL
    b_ser = e_ser + e_xor128
    b_par = e_par + e_xor128
    b_kar = e_kar + e_xor128
    print("\nper GHASH BLOCK [COMPOSED] (Y_i = (Y_{i-1} XOR C_i) . H ; +128b XOR = %.1f fJ):" % e_xor128)
    print("  bit-serial %.1f fJ   parallel %.1f fJ   Karatsuba %.1f fJ" % (b_ser, b_par, b_kar))

    # per MACsec frame: 1500-byte Ethernet frame. GHASH processes AAD(SecTAG ~1 blk) +
    # ciphertext(ceil(1500/16)=94 blk) + 1 length block -> 96 multiplies. Headline = 94 data.
    NB_DATA = (1500 + 15) // 16      # 94
    NB_TOT  = NB_DATA + 1 + 1        # + 1 AAD (SecTAG) + 1 length block
    print("\nper MACsec FRAME [COMPOSED] (1500B = %d cipher blocks + 1 AAD + 1 len = %d multiplies):"
          % (NB_DATA, NB_TOT))
    for label, eb in (("bit-serial", b_ser), ("parallel", b_par), ("Karatsuba", b_kar)):
        print("  %-11s %7.2f pJ / frame   (%.3f pJ / 94-block headline)"
              % (label, NB_TOT * eb / 1e3, NB_DATA * eb / 1e3))

    print("\nactivity sensitivity [EST] (per-cell ~ alpha; anchor ~0.48):")
    for a in (0.25, 0.5, 1.0):
        sc = a / 0.476
        print("  alpha=%.2f -> per-multiply: serial %8.1f fJ  parallel %7.1f fJ  karatsuba %7.1f fJ"
              % (a, e_ser*sc, e_par*sc, e_kar*sc))

    # ========================================================================
    # 7. DEPTH -> replica-done sharpness; the three-cipher contrast
    # ========================================================================
    banner("DEPTH -> self-timed replica-done; GHASH is the SHARPEST of the three ciphers")
    print("per-form combinational depth (yosys ltp levels / OpenSTA ns):")
    print("  bit-serial STEP : %s levels / %.3f ns  (per cycle; x128 cycles total latency)"
          % (S_step["depth"], t_step or 0))
    print("  parallel        : %s levels / %.3f ns  (one-shot cone)" % (S_par["depth"], t_par or 0))
    print("  Karatsuba       : %s levels / %.3f ns  (deeper: recursive XOR)" % (S_kar["depth"], t_kar or 0))
    print("\nCONTRAST across the campaign:")
    print("  SHA-256 round : ~5.64 ns  DEEP carry-ripple adder -> data-dependent, BLURRED done")
    print("  AES-128 round : ~1.08-3.42 ns  substitution cone  -> shallow, SHARP done")
    print("  GHASH mult    : the above  carry-LESS XOR/AND tree -> O(log) regular -> SHARPEST")
    print("GHASH has NO carry chain and NO substitution LUT: every output is a balanced XOR")
    print("reduction of AND partial products. The settle is monotone and data-INdependent in")
    print("shape -> the in-kind replica delay is a fixed short buffer and the current-sense")
    print("'done' is the tightest/sharpest of the three. (Bit-serial trades this for 128 tiny,")
    print("even-sharper per-step settles at the cost of 128 cycles + register toggling.)")

    # ========================================================================
    # 8. FEED-FORWARD block
    # ========================================================================
    banner("FEED TO THE ENERGY-COMPOSITION AGENT (explicit, labeled)")
    print("per_cell_fJ              = %.3f            [MEAS-anchor] (232 fJ / 63 cells, sha_slice)" % E_CELL)
    print("cells_serial_step       = %-6d           [COMPOSED]    (one bit-serial step)" % S_step["cells"])
    print("cells_parallel          = %-6d           [COMPOSED]    (schoolbook clmul+reduce)" % S_par["cells"])
    print("cells_karatsuba         = %-6d           [COMPOSED]    (recursive clmul+reduce)" % S_kar["cells"])
    print("E_mul_serial_fJ         = %-10.1f       [COMPOSED]    (step x128 cycles)" % e_ser)
    print("E_mul_parallel_fJ       = %-10.1f       [COMPOSED]    (one shot)" % e_par)
    print("E_mul_karatsuba_fJ      = %-10.1f       [COMPOSED]    (one shot)" % e_kar)
    print("E_block_parallel_fJ     = %-10.1f       [COMPOSED]    ((Y XOR C).H, parallel)" % b_par)
    print("E_frame_parallel_pJ     = %-10.2f       [COMPOSED]    (%d multiplies, 1500B frame)"
          % (NB_TOT * b_par / 1e3, NB_TOT))
    print("depth_parallel_levels   = %-6s           [COMPOSED]    (ltp; %.3f ns STA)" % (S_par["depth"], t_par or 0))
    print("GHASH_state_flops       ~ 256              [EST]  128b Y acc + 128b H held (parallel)")
    print("GHASH_state_flops_serial~ 512              [EST]  +128b V + 128b X-shift (+ctr) bit-serial")
    print("                          (register-LIGHT like AES, NOT SHA's 774 -> duty win is")
    print("                           AES-class, and the carry-less settle is the sharpest done.)")

    if keep is None:
        shutil.rmtree(wd, ignore_errors=True)

if __name__ == "__main__":
    main()
