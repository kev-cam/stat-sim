#!/usr/bin/env python3
"""SHA-256 round-core SLICE recast as a self-timed static-CMOS FSM — the
per-round ENERGY anchor (transistor level), analogous to ../fsm/gen_fsm.py.

WHY THIS EXISTS
---------------
The full 32b x 64-round SHA-256 is far too big for a Xyce transient. But the
energy-vs-duty claim for the self-timed approach only needs a REPRESENTATIVE
round-core transition cost in real transistors; composition (analyze) scales it
to the whole hash. This generator emits that anchor: sha_slice.v
(maj = ab^ac^bc, ch = ef^(~e)g, add = CPA) recast as a precharge-free static
round core feeding an edge-triggered dfrbp DFF, with the SAME two capture modes
proven on the 4-bit accumulator:
  golden    : DFF CLK = free-running clock  -> clocks EVERY cycle incl. idle
  selftimed : DFF CLK = in-kind replica-done pulse, fired only on an op (round)
Same stimulus + same op times -> the captured state sequence MUST match
(functional differential). Energy = supply-current integral over a window of
N round-ops at duty d; the clocked deck pays its clock floor on idle cycles.

ROUND-CORE NEXT-STATE CONE (static CMOS, NOT domino), 8-bit slice:
  a = q                      (state fed back)        -- the working word
  b = ROL1(q), e = q, g = ROR1(q)                    -- in-kind operand variety
  c, f = fixed data bytes (device sources)
  maj_i = (a&b) ^ (a&c) ^ (b&c)                      -- majority (TH23-natural)
  ch_i  = (e&f) ^ (~e&g)                             -- choice
  cmb   = maj + ch           (CPA #1, carry chain)   -- round primitive combine
  nxt   = q + cmb + 1        (CPA #2, carry-in=1)     -- guarantees per-op switch
  q <- nxt  (dfrbp, edge-triggered master-slave, active-low reset)
This reproduces a SHA round's dominant activity+depth (3-input majority, choice,
and TWO chained carry-propagate adders ~ the multi-operand T1/T2 add) so the
measured per-op energy is a faithful round anchor. (q ramps like the accumulator
-> every op toggles; the trajectory is not a SHA digest -- logic correctness is
proven separately at RTL in tb_sha256.v. Here only per-round ENERGY is wanted.)

SELF-TIMED COMPLETION: the done is an IN-KIND REPLICA delay (a static buffer
chain sized to the round-core's worst-case settle = maj depth + the two ripple
carry chains), NOT a per-op analog comparator -- it stays embedded/sparse so it
never re-dominates the duty crossover (the QAL-cliff). REPLICA_STAGES is a first
guess; the orchestrator TUNES it to the measured round-core critical path (read
V(cmb*/nxt*) settle in the .prn) exactly as the accumulator replica was tuned.

ONE Xyce at a time, orchestrator-only (dfrbp decks are slow ~600-900 s; a
background reaper kills >~20 min). This script only WRITES decks + meta.
"""
import sys, json

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.include "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
"""
VDD = 1.2
NB  = 8                 # round-core slice width (sha_slice is 8-bit)
REPLICA_STAGES = 7      # in-kind done delay; orchestrator tunes to measured settle
CBYTE = 0x5A            # fixed data byte c
FBYTE = 0x3C            # fixed data byte f


def rol1(i):  # bit index feeding b_i = q[(i+1) mod NB]  (rotate-left-by-1 of q)
    return (i + 1) % NB


def ror1(i):  # bit index feeding g_i = q[(i-1) mod NB]  (rotate-right-by-1 of q)
    return (i - 1) % NB


def cpa(sumpfx, ain, bin, cin0):
    """Static ripple CPA: sum_i = a^b^cin ; cout = maj(a,b,cin). a/b are lists of
    node names (len NB), cin0 the carry-in node. Returns (lines, sum_nodes)."""
    s = []
    cin = cin0
    sm = []
    for i in range(NB):
        a = ain[i]; b = bin[i]
        axb = f"{sumpfx}axb{i}"; m = f"{sumpfx}s{i}"
        s.append(f"Xxab_{sumpfx}{i} {axb} {a} {b} VDD VSS sg13g2_xor2_1")
        s.append(f"Xsum_{sumpfx}{i} {m} {axb} {cin} VDD VSS sg13g2_xor2_1")
        sm.append(m)
        if i < NB - 1:
            ab = f"{sumpfx}ab{i}"; acb = f"{sumpfx}acb{i}"; co = f"{sumpfx}c{i+1}"
            s.append(f"Xab_{sumpfx}{i} {ab} {a} {b} VDD VSS sg13g2_and2_1")
            s.append(f"Xacb_{sumpfx}{i} {acb} {axb} {cin} VDD VSS sg13g2_and2_1")
            s.append(f"Xco_{sumpfx}{i} {co} {ab} {acb} VDD VSS sg13g2_or2_1")
            cin = co
    return s, sm


def round_subckt():
    """Self-timed SHA round-core slice. Ports: c0..c7 f0..f7 clk rstb q0..q7 VDD VSS."""
    s = [".subckt sharound " +
         " ".join(f"c{i}" for i in range(NB)) + " " +
         " ".join(f"f{i}" for i in range(NB)) +
         " clk rstb " + " ".join(f"q{i}" for i in range(NB)) + " VDD VSS"]
    a = [f"q{i}" for i in range(NB)]              # a = q
    b = [f"q{rol1(i)}" for i in range(NB)]        # b = ROL1(q)
    e = [f"q{i}" for i in range(NB)]              # e = q
    g = [f"q{ror1(i)}" for i in range(NB)]        # g = ROR1(q)
    c = [f"c{i}" for i in range(NB)]
    f = [f"f{i}" for i in range(NB)]
    maj = []; ch = []
    for i in range(NB):
        # maj_i = (a&b) ^ (a&c) ^ (b&c)
        ab = f"m_ab{i}"; ac = f"m_ac{i}"; bc = f"m_bc{i}"; t = f"m_t{i}"; mj = f"maj{i}"
        s.append(f"Xmab{i} {ab} {a[i]} {b[i]} VDD VSS sg13g2_and2_1")
        s.append(f"Xmac{i} {ac} {a[i]} {c[i]} VDD VSS sg13g2_and2_1")
        s.append(f"Xmbc{i} {bc} {b[i]} {c[i]} VDD VSS sg13g2_and2_1")
        s.append(f"Xmt{i} {t} {ab} {ac} VDD VSS sg13g2_xor2_1")
        s.append(f"Xmaj{i} {mj} {t} {bc} VDD VSS sg13g2_xor2_1")
        maj.append(mj)
        # ch_i = (e&f) ^ (~e & g)
        ef = f"c_ef{i}"; ne = f"c_ne{i}"; neg = f"c_neg{i}"; chn = f"ch{i}"
        s.append(f"Xcef{i} {ef} {e[i]} {f[i]} VDD VSS sg13g2_and2_1")
        s.append(f"Xcne{i} {ne} {e[i]} VDD VSS sg13g2_inv_1")
        s.append(f"Xcng{i} {neg} {ne} {g[i]} VDD VSS sg13g2_and2_1")
        s.append(f"Xch{i} {chn} {ef} {neg} VDD VSS sg13g2_xor2_1")
        ch.append(chn)
    # cmb = maj + ch  (CPA #1, carry-in 0)
    l1, cmb = cpa("A", maj, ch, "VSS")
    s += l1
    # nxt = q + cmb + 1  (CPA #2, carry-in VDD -> +1 guarantees per-op switching)
    l2, nxt = cpa("B", a, cmb, "VDD")
    s += l2
    # dfrbp state register: Q=q_i, Q_N=qn_i, CLK=clk, D=nxt_i, RESET_B=rstb
    for i in range(NB):
        s.append(f"Xff{i} q{i} qn{i} clk {nxt[i]} rstb VDD VSS sg13g2_dfrbp_1")
    s.append(".ends sharound")
    return "\n".join(s)


def replica_done():
    """In-kind replica delay -> capture pulse. Buffer chain sized to the round-core
    settle (maj depth + two ripple carry chains); REPLICA_STAGES buffers. The DFF
    is edge-triggered, so cap = done rises once per req. Ports: req cap VDD VSS."""
    s = [".subckt capgen req cap VDD VSS"]
    prev = "req"
    for k in range(REPLICA_STAGES):
        nd = "done" if k == REPLICA_STAGES - 1 else f"d{k}"
        s.append(f"Xd{k} {nd} {prev} VDD VSS sg13g2_buf_4")
        prev = nd
    s.append("Xcb cap done VDD VSS sg13g2_buf_2")
    s.append(".ends capgen")
    return "\n".join(s)


def pwl(points):
    dd = []
    for t, v in points:
        if dd and abs(t - dd[-1][0]) < 1e-15:
            dd[-1] = (t, v)
        else:
            dd.append((t, v))
    return "PWL(" + " ".join("%.5gn %.4g" % (t * 1e9, v) for t, v in dd) + ")"


def byte_sources(prefix, val):
    """Static device sources tying byte `prefix` to constant `val` (LSB=bit0)."""
    out = []
    for i in range(NB):
        out.append(f"V{prefix}{i} {prefix}{i} 0 {VDD if (val >> i) & 1 else 0}")
    return out


def build(mode, duty_cycles, nops, name):
    """mode: 'golden' (free clock) | 'selftimed' (req-pulsed). duty_cycles = clock
    periods per op (round). nops = number of round-ops in the window."""
    Tc = 1.5e-9
    tr = 0.08e-9
    Ttot = (nops * duty_cycles + 1) * Tc
    s = [f"* {name}: {mode} SHA round-core slice ({NB}b), {nops} ops, duty 1/{duty_cycles} cyc",
         HDR, round_subckt(), replica_done(),
         f"VDDs VDD 0 {VDD}", "VSSs VSS 0 0"]
    # fixed data bytes c, f (constant device sources)
    s += byte_sources("c", CBYTE)
    s += byte_sources("f", FBYTE)
    # reset low 0.3 ns then high (clears q to 0; warm-up cycle 0, first op at cycle 1)
    s.append(f"Vrst rstb 0 PWL(0 0 0.3n 0 0.33n {VDD} {Ttot*1e9}n {VDD})")
    # round-core instance (q fed back internally)
    ports = (" ".join(f"c{i}" for i in range(NB)) + " " +
             " ".join(f"f{i}" for i in range(NB)) +
             " capnet rstb " + " ".join(f"q{i}" for i in range(NB)) + " VDD VSS")
    s.append(f"Xrc {ports} sharound")
    if mode == "golden":
        # free-running clock: rises every Tc across the WHOLE window (idle too)
        pts = [(0, 0)]; t = 0.5e-9
        while t < Ttot - Tc * 0.5:
            pts += [(t, 0), (t + tr, VDD), (t + Tc * 0.5, VDD), (t + Tc * 0.5 + tr, 0)]
            t += Tc
        s.append("Vclk capnet 0 " + pwl(pts))
    else:
        # self-timed: req pulses ONLY on ops (every duty_cycles cycles); replica->cap
        pts = [(0, 0)]
        for k in range(nops):
            t = 0.5e-9 + (1 + k * duty_cycles) * Tc
            pts += [(t, 0), (t + tr, VDD), (t + Tc * 0.5, VDD), (t + Tc * 0.5 + tr, 0)]
        s.append("Vreq reqnet 0 " + pwl(pts))
        s.append("Xcap reqnet capnet VDD VSS capgen")
    # energy over the window + state + capture trace
    qprint = " ".join(f"V(q{i})" for i in range(NB))
    s += [f".tran 2p {Ttot*1e9:.4g}n",
          ".options device gmin=1e-13",
          ".options timeint reltol=1e-6 abstol=1e-12 delmax=5e-12",
          ".options nonlin-tran abstol=1e-12 reltol=1e-6",
          f".measure tran QVDD INTEG I(VDDs) from=0.4n to={Ttot*1e9:.4g}n",
          ".measure tran EVDD PARAM {-1.2*QVDD}",
          f".print tran format=noindex I(VDDs) {qprint} V(capnet)",
          ".end", ""]
    meta = {"mode": mode, "duty_cycles": duty_cycles, "nops": nops, "Tc_ns": Tc * 1e9,
            "Ttot_ns": Ttot * 1e9, "nb": NB, "replica_stages": REPLICA_STAGES,
            "cbyte": CBYTE, "fbyte": FBYTE, "anchor": "sha256_round_core_slice"}
    return "\n".join(s), meta


if __name__ == "__main__":
    # functional differential: golden & self-timed at duty 2, 4 ops
    specs = [("golden", 2, 4, "sr_g_d2"), ("selftimed", 2, 4, "sr_st_d2")]
    # energy vs duty: 4 ops at duties 2,4,10
    for d in (2, 4, 10):
        specs += [("golden", d, 4, f"sr_g_d{d}"), ("selftimed", d, 4, f"sr_st_d{d}")]
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for mode, d, n, nm in specs:
        if which != "all" and which != nm:
            continue
        txt, meta = build(mode, d, n, nm)
        bad = [i + 1 for i, l in enumerate(txt.splitlines()) if l[:1] in (' ', '\t')]
        if bad:
            print("WS LINT FAIL", nm, bad[:4]); sys.exit(2)
        open(nm + ".cir", "w").write(txt)
        json.dump(meta, open(nm + ".meta.json", "w"))
        print(f"wrote {nm}.cir ({mode}, duty 1/{d}, {n} ops, replica={REPLICA_STAGES})")
