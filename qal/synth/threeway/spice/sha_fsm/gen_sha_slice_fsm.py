#!/usr/bin/env python3
"""Self-timed static-CMOS SHA-256 ROUND-SLICE FSM vs clocked golden — the per-round
energy anchor (SG13G2 130nm transistors).

Deliverable #3 of the SHA-256 self-timed campaign. Recasts the sha_slice round CORE
(../../sha_slice.v: maj=(a&b)^(a&c)^(b&c), ch=(e&f)^(~e&g), 8-bit CPA) as a SELF-TIMED
ROUND-SLICE state machine so per-round energy can be anchored in real transistors,
analogous to gen_fsm.py (the proven 4-bit-accumulator fixture). SAME proven patterns:
precharge-free static next-state logic + edge-triggered dfrbp DFF state register +
done-pulsed capture (in-kind replica delay, capgen) vs a free-running clocked golden.
ONE Xyce at a time. Transient-only, gmin op-point init (no uic).

WHAT THE SLICE COMPUTES (8-bit, iterated like SHA's 64-round a..h recurrence):
  state register a (8b) = round working register, fed back each round
  constants b,c,e,f,g (8b)  driven to the VDD/VSS rails (genuine constant inputs)
  maj = (a & b) ^ (a & c) ^ (b & c)          <- sha_slice majority (TH23-natural)
  ch  = (e & f) ^ (~e & g)                   <- sha_slice choice (constant: no a)
  T   = maj ^ ch                             round combine
  Tg  = T & en                               addend gate (en=0 -> hold; the fair
                                             data-gate, exactly like gen_fsm's x0)
  a'  = a + Tg   (8-bit ripple CPA, cin=0)   <- the sha_slice "sum" carry chain, the
                                             round critical path; result captured
  register: a <- a' on the capture edge (dfrbp, master-slave, no feedback race)

All three sha_slice primitives (maj, ch, 8-bit sum/CPA) feed the captured round
result, and the state feeds back -> a genuine iterating round FSM, not a toy. The
recurrence a_{k+1} = (a_k + ((maj(a_k,b,c) ^ ch(e,f,g)) & en)) mod 256 is checkable
against an independent reference (analyze_sha_slice_fsm.py computes it from the
sha_slice.v maj/ch/sum definitions; cross-validated against the RTL via iverilog).

TWO decks share the datapath, differ only in capture:
  golden     : DFF CLK = free-running clock -> clocks EVERY cycle incl. idle; idle
               cycles are data-gated (en=0 -> Tg=0 -> a'=a hold) so it does the SAME
               N round updates as self-timed while its clock still burns the floor.
  selftimed  : DFF CLK = replica-delayed done pulse, fired only on a req (round) edge;
               en=1 always (every captured edge is a real round).
Energy by supply-current integral over a window holding K rounds at duty d; the
clocked deck pays its clock floor on idle cycles, the self-timed deck does not ->
the duty-shaped lower-power win, exactly as the 4-bit accumulator measured.

HARD RULE: this script only WRITES decks and LINTS them. It does NOT run Xyce. The
orchestrator runs them ONE at a time (the dfrbp-DFF decks are SLOW; see runtimes at
the bottom).
"""
import sys, json

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.include "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
"""
VDD = 1.2
NB  = 8                      # round-slice datapath width (8-bit anchor)
Tc  = 1.5e-9                 # base cycle / round spacing (same as gen_fsm run2)
TR  = 0.08e-9                # edge rise/fall
REPLICA_STAGES = 10          # in-kind replica delay (buf_4 chain). The 8-bit CPA +
                             # maj/ch front is ~2.5-3x deeper than the 4-bit adder,
                             # so the replica is longer than capgen's 4. MUST exceed
                             # the logic settle and stay < the round spacing (>=1.5ns)
                             # -> tune from the first .prn (done must rise AFTER a'
                             # settles). Op spacing >=1.5ns gives wide margin.

# Fixed round constants (arbitrary but pinned; the reference recomputes from these).
# Chosen so the 4-round trajectory moves in several bits each round (a real exercise,
# not stuck-at). b,c,e,f,g are driven to the rails bit-by-bit in the top deck.
BCEFG = dict(b=0x5A, c=0x3C, e=0x6A, f=0x99, g=0xC3)


def round_subckt():
    """8-bit self-timed round slice: maj + ch + gated 8-bit CPA feeding a dfrbp
    state register. Ports: a0..a7 (state Q, fed back), b*/c*/e*/f*/g* (constants),
    en (addend gate), clk (capture), rstb (async reset), VDD, VSS."""
    ports = []
    for nm in ("a", "b", "c", "e", "f", "g"):
        ports += [f"{nm}{i}" for i in range(NB)]
    ports += ["en", "clk", "rstb", "VDD", "VSS"]
    s = [".subckt round8 " + " ".join(ports)]
    cin = "VSS"                                 # CPA carry-in = 0
    for i in range(NB):
        a = f"a{i}"; b = f"b{i}"; c = f"c{i}"
        e = f"e{i}"; fnet = f"f{i}"; g = f"g{i}"
        # --- maj = (a&b) ^ (a&c) ^ (b&c) : sha_slice majority (TH23-natural) ---
        s.append(f"Xmab{i} mab{i} {a} {b} VDD VSS sg13g2_and2_1")       # a&b
        s.append(f"Xmac{i} mac{i} {a} {c} VDD VSS sg13g2_and2_1")       # a&c
        s.append(f"Xmbc{i} mbc{i} {b} {c} VDD VSS sg13g2_and2_1")       # b&c
        s.append(f"Xm1{i} m1{i} mab{i} mac{i} VDD VSS sg13g2_xor2_1")   # (a&b)^(a&c)
        s.append(f"Xmaj{i} maj{i} m1{i} mbc{i} VDD VSS sg13g2_xor2_1")  # ^(b&c)
        # --- ch = (e&f) ^ (~e & g) : sha_slice choice ---
        s.append(f"Xef{i} ef{i} {e} {fnet} VDD VSS sg13g2_and2_1")      # e&f
        s.append(f"Xne{i} ne{i} {e} VDD VSS sg13g2_inv_1")             # ~e
        s.append(f"Xneg{i} neg{i} ne{i} {g} VDD VSS sg13g2_and2_1")     # ~e & g
        s.append(f"Xch{i} ch{i} ef{i} neg{i} VDD VSS sg13g2_xor2_1")    # ^
        # --- round combine + addend gate: T=maj^ch ; Tg=T&en ---
        s.append(f"XT{i} tcomb{i} maj{i} ch{i} VDD VSS sg13g2_xor2_1")  # maj^ch
        s.append(f"XTg{i} tg{i} tcomb{i} en VDD VSS sg13g2_and2_1")     # gate addend
        # --- 8-bit ripple CPA: a' = a + Tg (the sha_slice carry chain) ---
        s.append(f"Xaxb{i} axb{i} {a} tg{i} VDD VSS sg13g2_xor2_1")     # a^Tg
        s.append(f"Xsum{i} nsum{i} axb{i} {cin} VDD VSS sg13g2_xor2_1") # a^Tg^cin
        if i < NB - 1:
            co = f"cry{i+1}"
            s.append(f"Xcab{i} cab{i} {a} tg{i} VDD VSS sg13g2_and2_1") # generate a&Tg
            # carry = (a^Tg)&cin | (a&Tg)  -> one a21o compound (X=(A1&A2)|B1)
            s.append(f"Xco{i} {co} axb{i} {cin} cab{i} VDD VSS sg13g2_a21o_1")
            cin = co
        # --- state register bit: a_i <- a'_i on capture edge (async reset -> 0) ---
        s.append(f"Xff{i} {a} an{i} clk nsum{i} rstb VDD VSS sg13g2_dfrbp_1")
    s.append(".ends round8")
    return "\n".join(s)


def replica_done():
    """In-kind replica delay = a static buf chain matching the round slice's
    worst-case settle (maj/ch front + 8-bit carry chain), driving the capture pulse.
    Longer than capgen's 4 (deeper datapath). Ports: req -> cap (one pulse per req).
    Sized by measurement; tune REPLICA_STAGES from the first .prn (done must rise
    after a' settles, and before the next round, which is >=1.5ns away)."""
    s = [".subckt capgen req cap VDD VSS"]
    prev = "req"
    for k in range(REPLICA_STAGES):
        nxt = "done" if k == REPLICA_STAGES - 1 else f"d{k}"
        s.append(f"Xd{k} {nxt} {prev} VDD VSS sg13g2_buf_4")
        prev = nxt
    # capture = done; the dfrbp is edge-triggered -> done rises once per req
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


def ref_traj(nops):
    """Independent golden of the slice, from the sha_slice.v maj/ch/sum definitions.
    a_{k+1} = (a_k + (maj(a_k,b,c) ^ ch(e,f,g))) mod 256, en=1 on every round."""
    b, c, e, f, g = (BCEFG[k] for k in ("b", "c", "e", "f", "g"))
    a = 0
    traj = []
    for _ in range(nops):
        maj = (a & b) ^ (a & c) ^ (b & c)
        ch = (e & f) ^ ((~e & 0xFF) & g)
        T = (maj ^ ch) & 0xFF
        a = (a + T) & 0xFF
        traj.append(a)
    return traj


def railbits(name):
    """The 8 rail nets for a constant byte, LSB..MSB, as VDD/VSS (genuine inputs)."""
    v = BCEFG[name]
    return [("VDD" if (v >> i) & 1 else "VSS") for i in range(NB)]


def build(mode, duty_cycles, nops, name):
    """mode: 'golden' (free clock) or 'selftimed' (req-pulsed). duty_cycles = clock
    periods per round (1 = every cycle). nops = actual round updates."""
    Ttot = (nops * duty_cycles + 1) * Tc
    s = [f"* {name}: {mode} SHA-256 round-slice FSM, {nops} rounds, duty 1/{duty_cycles} cyc",
         HDR, round_subckt(), replica_done(),
         f"VDDs VDD 0 {VDD}", "VSSs VSS 0 0"]
    # en: the addend gate (plays gen_fsm's x0 role). golden idle -> en=0 (hold);
    # golden full-duty / self-timed -> en=1 (every cycle is a round).
    if mode == "golden" and duty_cycles > 1:
        # en high for a FULL cycle before the capture edge (>=Tc setup so the maj/ch
        # + 8-bit CPA settle) through just after it; 0 on idle cycles.
        pts = [(0, 0)]
        for k in range(nops):
            t = 0.5e-9 + (1 + k * duty_cycles) * Tc      # round capture edge (warm-up cyc 0)
            r = max(0.0, t - Tc)                         # rise a full cycle early
            pts += [(r, 0), (r + TR, VDD), (t + 0.4e-9, VDD), (t + 0.4e-9 + TR, 0)]
        pts.append((Ttot, 0))
        s.append("Ven en 0 " + pwl(pts))
    else:
        s.append(f"Ven en 0 {VDD}")                      # every edge is a round
    # constant round inputs b,c,e,f,g wired to the rails bit-by-bit in the instance
    rails = {nm: railbits(nm) for nm in ("b", "c", "e", "f", "g")}
    # reset low 0.3 ns then high (async clear -> a=0)
    s.append(f"Vrst rstb 0 PWL(0 0 0.3n 0 0.33n {VDD} {Ttot*1e9:.4g}n {VDD})")
    # the round-slice instance: a0..a7 (state), b/c/e/f/g rails, en, capnet, rstb
    inst = ["Xr"] + [f"s{i}" for i in range(NB)]         # state nets named s0..s7
    for nm in ("b", "c", "e", "f", "g"):
        inst += rails[nm]
    inst += ["en", "capnet", "rstb", "VDD", "VSS", "round8"]
    s.append(" ".join(inst))
    if mode == "golden":
        # free-running clock: rises every Tc for the WHOLE window (idle cycles too)
        pts = [(0, 0)]
        t = 0.5e-9
        while t < Ttot - Tc * 0.5:
            pts += [(t, 0), (t + TR, VDD), (t + Tc * 0.5, VDD), (t + Tc * 0.5 + TR, 0)]
            t += Tc
        s.append("Vclk capnet 0 " + pwl(pts))
    else:
        # self-timed: req pulses ONLY on rounds (every duty_cycles cyc); replica->cap
        pts = [(0, 0)]
        for k in range(nops):
            t = 0.5e-9 + (1 + k * duty_cycles) * Tc
            pts += [(t, 0), (t + TR, VDD), (t + Tc * 0.5, VDD), (t + Tc * 0.5 + TR, 0)]
        s.append("Vreq reqnet 0 " + pwl(pts))
        s.append("Xcap reqnet capnet VDD VSS capgen")
    # energy over the window + print 8-bit state + capture
    prints = " ".join("V(s%d)" % i for i in range(NB))
    s += [f".tran 2p {Ttot*1e9:.4g}n",
          ".options device gmin=1e-13",
          ".options timeint reltol=1e-6 abstol=1e-12 delmax=5e-12",
          ".options nonlin-tran abstol=1e-12 reltol=1e-6",
          f".measure tran QVDD INTEG I(VDDs) from=0.4n to={Ttot*1e9:.4g}n",
          ".measure tran EVDD PARAM {-1.2*QVDD}",
          f".print tran format=noindex I(VDDs) {prints} V(capnet)",
          ".end", ""]
    meta = {"mode": mode, "duty_cycles": duty_cycles, "nops": nops, "Tc_ns": Tc * 1e9,
            "Ttot_ns": Ttot * 1e9, "nb": NB, "bcefg": BCEFG,
            "ref_traj": ref_traj(nops), "replica_stages": REPLICA_STAGES}
    return "\n".join(s), meta


if __name__ == "__main__":
    # duties per the task: 1 (every cycle), 4, 10; golden + self-timed each; 4 rounds.
    specs = []
    for d in (1, 4, 10):
        specs += [("golden", d, 4, f"g_sha_d{d}"), ("selftimed", d, 4, f"st_sha_d{d}")]
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    print("reference round trajectory (a0=0 -> a4), b/c/e/f/g = "
          + " ".join("%s=0x%02X" % (k.upper(), BCEFG[k]) for k in ("b", "c", "e", "f", "g")))
    print("  ref_traj =", ["0x%02X" % v for v in ref_traj(4)])
    for mode, d, n, nm in specs:
        if which != "all" and which != nm:
            continue
        txt, meta = build(mode, d, n, nm)
        # flush-left lint: no leading whitespace on any card
        bad = [i + 1 for i, l in enumerate(txt.splitlines()) if l[:1] in (" ", "\t")]
        if bad:
            print("WS LINT FAIL", nm, bad[:4]); sys.exit(2)
        # node-name lint: no vt/gmin/node-name leakage into net names
        banned = ("vt", "gmin")
        toks = set()
        for l in txt.splitlines():
            if l.startswith(("X", "V", "R", "C")):
                toks.update(l.split()[1:])
        hits = [t for t in toks if t.lower() in banned]
        if hits:
            print("NODE LINT FAIL", nm, hits); sys.exit(2)
        open(nm + ".cir", "w").write(txt)
        json.dump(meta, open(nm + ".meta.json", "w"))
        print(f"wrote {nm}.cir  ({mode}, duty 1/{d}, {n} rounds, window {meta['Ttot_ns']:.4g} ns)")
