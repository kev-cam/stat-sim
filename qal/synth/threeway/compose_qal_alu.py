#!/usr/bin/env python3
"""QAL COMPOSITION for the Vortex ALU (alu_top) on IHP SG13G2.  NO XYCE IS RUN HERE:
this composes the ALU's cost from the committed per-gate QAL measurements.

=== INPUT PROVENANCE (every number below is labelled where it is printed) ===
MEASURED (Xyce, SG13G2/PSP103 tt), at the co-designed iso-current operating point
dV = 1.0 V, L = 277.8 nH, N = 8 gates, C_eff = 35.979 fF, transfer switch nMOS w=20u +
pMOS w=40u, gate-drive rail VGH = 1.5 V:
  1.34269 fJ per gate-settle, 342.0 ps per hop, settling 100%
        -> qal_isocurrent.json rows[2]   (the only VALID row; 0.8 V settles 77.1%)
  transfer-switch gate-drive NET energy |EGT| = 5.882058 fJ per hop
        -> iso1000_h.cir.mt0  (see NOTE ON EGT below)
  bank replication scaling N = 8M -> C_A*M, L/M, Rs/M, SWITCH WIDTH *M, with per-gate
  transferred charge INVARIANT: 4.14050 / 4.14994 / 4.14736 fC at N = 8 / 32 / 128
  (0.23% span), t_zcs identical
        -> qal_bankN_sqrtN.json ; scaling rule stated at qal_bankN_sqrtN.py:31-36
  hop split at dV=1.0: delivery path = 23.18-24.76% of E_hop, gates the rest
        -> qal_split_differential.json
  matched CMOS inverter: 10.08 fJ/op, 34.81 ps at 1.2 V with a 2 fF load, wp=1.12u
  wn=0.74u -- WHICH IS EXACTLY sg13g2_inv_1 (nmos w=740n, pmos w=1.12u,
  sg13g2_stdcell.spice:619-622).  The QAL anchor bank is literally 8 sg13g2_inv_1.
  per-hop delivery loss vs switch Ron: 6.8% (w=40u) .. 13.6% (w=10u REAL) -> qal_trackC.py:12-17
  top-up rail energy per bank per fire 25.425 fJ (eta 0.12%) .. 112.181 fJ (eta 61.58%)
        -> qal_pulse_topup.json  (both at UNTUNED design points, dV=0.6)
MEASURED-BY-PEER (OpenSTA liberty power + real VCD, alu_cmos workflow; the campaign's
standing caveat that liberty power has never been transistor-cross-checked applies):
  CMOS alu_top, SG13G2 1.20 V, 4.75 ns: LOGIC 21.033 / DFF 14.091 / CLKTREE 8.323
  = 43.447 pJ per cycle over 5164 placed instances  -> alu_cmos/work/inst_power.json
  critical path ex_data[220] -> _8053_/D, arrival 4.6398 ns of which 0.4750 ns is the
  SDC input delay => 4.1648 ns in-block, 37 logic stages + 6 buffers
        -> alu_cmos/work/final_sta2.log:6-74
FROM THE PDK (on disk, not simulated here):
  sg13g2_stdcell.spice per-cell device widths (exact)
  sg13g2_stdcell_typ_1p20V_25C.lib per-cell area and input pin capacitance
  inductor PCell default estimates: 1 turn 33.303 pH / 2 turns 221.5 pH at minimum
  geometry -> libs.tech/klayout/.../ihp/inductors_code.py:40-47 ; the PDK's canonical
  xschem symbol default geometry is d=222 um, w=10 um, s=10 um, 2 turns
        -> libs.tech/xschem/sg13g2_pr/inductor3.sym:36-39
STRUCTURE (mine): levelize_alu.py over alu.json, levelize_mapped.py over alu.cmos.v.
ASSUMED (nothing on disk): zero-current detector 30-300 fJ per bank per hop (~35
  devices); no comparator has been simulated anywhere in this campaign.

NOTE ON EGT.  iso1000_h.cir.mt0 reports EGT = -5.882058e-15.  The integrand is
'Bpg pg 0 V={ -V(gt)*I(VGT) - V(gtp)*I(VGTP) }' (qal_hop_gates.py:189), already flipped
once for Xyce's source-current convention, so a negative result means it is flipped once
more than intended.  Magnitude used, sign recorded UNRESOLVED.  More important: this is
the net integral of an IDEAL PWL gate driver, which takes the gate charge back on the
falling edge.  A real CMOS gate driver does not.  Both bounds are carried.
"""
import collections
import json
import re

PDK = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2"
LIB = PDK + "/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
SPI = PDK + "/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
MAPPED = "/usr/local/src/mylex/probes/layopt/evidence/alu_cmos/work/alu.cmos.v"
LEVELS = "/usr/local/src/stat-sim/qal/synth/threeway/work/alu/alu_levels.json"
OUT = "/usr/local/src/stat-sim/qal/synth/threeway/work/alu/qal_alu_composition.json"

# ---- MEASURED constants -------------------------------------------------------------
E_GATE_SETTLE = 1.34269
T_HOP = 342.0
C_EFF_PER_GATE = 35.979 / 8.0
CLOAD_ANCHOR = 2.0
N_ANCHOR = 8
L_ANCHOR_NH = 277.8
EGT_HOP = 5.882058
WSW_TOT = 20.0 + 40.0        # um of transfer-switch device at N=8
VGH = 1.5
E_INV_OP, VDD_INV = 10.08, 1.2
PATH_PCT = (23.18, 24.76)
E_ZCD = (30.0, 300.0)                 # ASSUMED
ETA_TOPUP = (0.0012, 0.6158)          # MEASURED at two untuned points
L_PDK_1T_PH, L_PDK_2T_PH = 33.303, 221.5

CMOS_PJ = {"LOGIC": 21.0327, "DFF": 14.0914, "CLKTREE": 8.3226}
CMOS_TOTAL_PJ = sum(CMOS_PJ.values())
CMOS_PERIOD_NS = 4.75
CMOS_CRIT_NS = 4.6398 - 0.4750
CMOS_REG2REG_NS = 2.3261
CMOS_STAGES = 37


def liberty():
    lines = open(LIB).read().split("\n")
    cells, i = {}, 0
    while i < len(lines):
        m = re.match(r"\s*cell \((\w+)\) \{", lines[i])
        if not m:
            i += 1
            continue
        name, depth, j = m.group(1), 1, i + 1
        area, caps, pin, pdir, pcap = 0.0, {}, None, None, None
        while j < len(lines) and depth > 0:
            L = lines[j]
            depth += L.count("{") - L.count("}")
            a = re.match(r"\s*area\s*:\s*([\d.eE+-]+)", L)
            if a and depth == 1:
                area = float(a.group(1))
            pm = re.match(r"\s*pin \((\w+)\) \{", L)
            if pm:
                if pin and pdir == "input" and pcap is not None:
                    caps[pin] = pcap * 1000.0
                pin, pdir, pcap = pm.group(1), None, None
            if pin:
                if re.match(r'\s*direction\s*:\s*"?input"?', L):
                    pdir = "input"
                c = re.match(r"\s{6}capacitance\s*:\s*([\d.eE+-]+)", L)
                if c and pcap is None:
                    pcap = float(c.group(1))
            j += 1
        if pin and pdir == "input" and pcap is not None:
            caps[pin] = pcap * 1000.0
        cells[name] = {"area": area, "cin": caps, "sumcin": sum(caps.values())}
        i = j
    return cells


def widths():
    txt = open(SPI).read()
    out = {}
    for m in re.finditer(r"^\.subckt (\S+) (.*?)\n(.*?)^\.ends", txt, re.M | re.S):
        name, body = m.group(1), m.group(3)
        wp = wn = 0.0
        for dm in re.finditer(r"^X\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(sg13_lv_\w+)\s+w=([\d.]+)([un])",
                              body, re.M):
            dev, wv, unit = dm.groups()
            w = float(wv) * (1e-3 if unit == "n" else 1.0)
            if "pmos" in dev:
                wp += w
            else:
                wn += w
        out[name] = {"wp": wp, "wn": wn, "wtot": wp + wn}
    return out


def mapped_netlist():
    src = open(MAPPED).read()
    body = src[src.index("module alu_top("):]
    body = body[:body.index("endmodule")]
    cells = {}
    for m in re.finditer(r"^\s*(sg13g2_\w+)\s+(\\?\S+)\s*\((.*?)\);", body, re.M | re.S):
        ct, cn, conns = m.groups()
        pins = {k: v.strip() for k, v in re.findall(r"\.(\w+)\(([^)]*)\)", conns)}
        cells[cn] = (ct, pins)
    return cells


def sect(t):
    print("\n" + "-" * 94)
    print(t)
    print("-" * 94)


def main():
    lib, wid = liberty(), widths()
    inv_a = lib["sg13g2_inv_1"]["area"]
    inv_c = lib["sg13g2_inv_1"]["sumcin"]
    inv_wp = wid["sg13g2_inv_1"]["wp"]
    inv_wt = wid["sg13g2_inv_1"]["wtot"]
    lv = json.load(open(LEVELS))
    prof, D, NC = lv["profile"], lv["depth"], lv["n_comb"]
    c_self_inv = C_EFF_PER_GATE - 0.5 * CLOAD_ANCHOR
    cg_per_um = inv_c / inv_wt                      # fF/um, DERIVED from liberty
    res = {}

    print("=" * 94)
    print("QAL COMPOSITION -- Vortex ALU (alu_top), IHP SG13G2.")
    print("*** COMPOSED PROJECTION, NOT A MEASUREMENT. *** Every QAL number below is the")
    print("measured 8-inverter bank scaled by structure; no ALU circuit has been simulated.")
    print("=" * 94)

    sect("ANCHOR DECOMPOSITION [MEASURED]")
    print("  the QAL anchor bank is 8 x (wp=1.12u, wn=0.74u) = 8 x sg13g2_inv_1 EXACTLY")
    print("     (sg13g2_stdcell.spice:619-622) -- the anchor and the CMOS arm share a cell.")
    print("  bank-rail capacitance per anchor gate  C_eff/N = %.3f fF" % C_EFF_PER_GATE)
    print("     of which charged external load      0.5 x %.1f = %.1f fF" % (CLOAD_ANCHOR, 0.5 * CLOAD_ANCHOR))
    print("     => self term (pMOS junctions + nwell) %.3f fF  <- this is what scales with cell size"
          % c_self_inv)
    print("  hop energy split [MEASURED %.2f-%.2f%% path]:" % PATH_PCT)
    print("     delivery path %.3f-%.3f fJ/gate ; gate settling %.3f-%.3f fJ/gate"
          % (E_GATE_SETTLE * PATH_PCT[0] / 100, E_GATE_SETTLE * PATH_PCT[1] / 100,
             E_GATE_SETTLE * (1 - PATH_PCT[1] / 100), E_GATE_SETTLE * (1 - PATH_PCT[0] / 100)))

    # ======================================================= (a)
    sect("(a) LEVELIZATION  [structure, from alu.json; cross-checked two ways]")
    print("  generic alu.json  : %d comb + %d DFF, DEPTH %d" % (NC, lv["n_seq"], D))
    print("  SG13G2-mapped     : 4027 comb + 188 DFF, DEPTH 38  (levelize_mapped.py)")
    print("  Kahn longest-path reproduces the generic profile exactly and visits all %d" % NC)
    print("  cells => the combinational graph is ACYCLIC (no comb loops).")
    print("  profile: %s" % "/".join(map(str, prof)))
    print("\n  %4s %6s %7s %10s   %s" % ("lvl", "N", "cum%", "L_req_nH", "type mix (top 3)"))
    cum = 0
    for i, n in enumerate(prof, 1):
        cum += n
        mix = ", ".join("%s %d" % (k.strip("$_"), v)
                        for k, v in sorted(lv["typemix"][str(i)].items(), key=lambda kv: -kv[1])[:3])
        print("  %4d %6d %6.1f%% %10.1f   %s" % (i, n, 100.0 * cum / NC, L_ANCHOR_NH * N_ANCHOR / n, mix))
    head = sum(prof[:12])
    tail = sum(prof[24:])
    print("\n  head (levels 1-12) : %4d cells = %.1f%% of the logic in 32.4%% of the depth"
          % (head, 100.0 * head / NC))
    print("  tail (levels 25-37): %4d cells = %.1f%% of the logic in 35.1%% of the depth"
          % (tail, 100.0 * tail / NC))
    print("  sha_slice for contrast: 48/22/19/3/2/4/2/3/1/1 (D=10, 105 cells) -- same SHAPE,")
    print("  ~43x the cells.  The ALU is NOT wide-and-shallow; it is wide-then-a-long-thin-wire.")
    print("  levels 31-37 hold EXACTLY 2 cells each: two 1:1-paired copies of one serial")
    print("  control chain (reduceOR -> NOT -> AND -> MUX -> pmuxAND -> reduceOR -> pmuxMUX ->")
    print("  MUX -> clock-enable MUX), ending on two DFF enables.  Names pair 3566/3636,")
    print("  3568/3638, 3570/3640, 3943/4557, 54437/54501 -- the two-warp branch/trap valid")
    print("  chain, not an arithmetic carry.  Levels 29-37 are 9 levels = 24.3% of the")
    print("  total depth holding 22 cells = 0.49% of the logic.")
    res["profile"] = prof

    # ======================================================= (b)
    sect("(b) ENERGY  [COMPOSED PROJECTION from the measured 1.34269 fJ/gate-settle]")
    print("  *** THE ANCHOR IS AN INVERTER BANK; THE ALU IS 41% 2:1 MUX. ***")
    print("  A gate settling on a rail costs in proportion to the capacitance it hangs on")
    print("  that rail.  In the anchor deck the pMOS BULK is tied to the bank node")
    print("  (qal_bank_gates.py:'pMOS bulk is tied to the bank node'), so the rail carries the")
    print("  whole nwell plus every pMOS junction -- i.e. it scales with TOTAL pMOS WIDTH.")
    print("  Three proxies are carried; wp is the PDK-exact one and is taken as primary.")
    print("\n  %-20s %6s %8s %8s %8s %8s" % ("cell", "n", "wp_um", "wp/inv", "A/inv", "Cin/inv"))
    GEN2SG = {"$_NOT_": "sg13g2_inv_1", "$_AND_": "sg13g2_and2_1", "$_OR_": "sg13g2_or2_1",
              "$_XOR_": "sg13g2_xor2_1", "$_MUX_": "sg13g2_mux2_1"}
    gcount = collections.Counter()
    for i in range(1, D + 1):
        for t, n in lv["typemix"][str(i)].items():
            gcount[t] += n
    gw = ga = gc = 0.0
    for t, n in gcount.most_common():
        sg = GEN2SG[t]
        rw, ra, rc = (wid[sg]["wp"] / inv_wp, lib[sg]["area"] / inv_a, lib[sg]["sumcin"] / inv_c)
        gw += n * rw
        ga += n * ra
        gc += n * rc
        print("  %-20s %6d %8.2f %8.2f %8.2f %8.2f" % (t.strip("$_") + " -> " + sg.replace("sg13g2_", ""),
                                                       n, wid[sg]["wp"], rw, ra, rc))
    print("  %-20s %6d %8s %8.2f %8.2f %8.2f" % ("WEIGHTED MEAN", NC, "", gw / NC, ga / NC, gc / NC))
    print("  => THE MUX TAX.  In DIMS a 2:1 MUX is 10 threshold cells, the most expensive")
    print("     primitive there is.  In QAL a 2:1 MUX is ONE static cell that happens to be")
    print("     %.2fx an inverter in pMOS width (PDK-exact).  So MUX-domination costs QAL"
          % (wid["sg13g2_mux2_1"]["wp"] / inv_wp))
    print("     ~5x-per-MUX, not ~10-cells-per-MUX: the 41%% MUX mix is a real tax on QAL but")
    print("     it is the one place QAL is structurally better off than the async DIMS arm.")

    mn = mapped_netlist()
    sinks = collections.defaultdict(list)
    for cn, (ct, pins) in mn.items():
        for p, net in pins.items():
            if p in ("X", "Y", "Q"):
                continue
            sinks[net].append((ct, p))
    loads, fanouts = [], []
    for cn, (ct, pins) in mn.items():
        if "dfrbpq" in ct:
            continue
        out = pins.get("X") or pins.get("Y")
        sk = sinks.get(out, [])
        cl = sum(lib[st]["cin"].get(sp, 0.0) for st, sp in sk) if sk else 6.0
        loads.append((ct, cl))
        fanouts.append(len(sk))
    nmap = len(loads)
    print("\n  MAPPED netlist is the physically right vehicle: QAL settles single-rail static")
    print("  CMOS gates, so the SG13G2-mapped netlist IS the QAL netlist, and it is the same")
    print("  netlist the CMOS arm measures -- apples to apples.")
    print("  %d comb cells, mean fanout %.2f sinks, mean load %.2f fF (anchor assumed %.1f fF)"
          % (nmap, sum(fanouts) / len(fanouts), sum(c for _, c in loads) / nmap, CLOAD_ANCHOR))

    def compose(proxy):
        tot = 0.0
        for ct, cl in loads:
            if proxy == "wp":
                r = wid[ct]["wp"] / inv_wp
            elif proxy == "area":
                r = lib[ct]["area"] / inv_a
            else:
                r = lib[ct]["sumcin"] / inv_c
            tot += E_GATE_SETTLE * (c_self_inv * r + 0.5 * cl) / C_EFF_PER_GATE
        return tot

    e_naive = nmap * E_GATE_SETTLE
    e_wp, e_ar, e_cp = compose("wp"), compose("area"), compose("cin")
    print("\n  E_logic per op, mapped netlist with its real fanout loads:")
    for lbl, v in (("naive 'every cell = 1.34269 fJ'", e_naive),
                   ("wp proxy   (PDK-exact, PRIMARY)", e_wp),
                   ("area proxy (liberty)", e_ar),
                   ("Cin proxy  (liberty)", e_cp)):
        print("    %-34s %8.0f fJ = %6.3f pJ   vs CMOS LOGIC %.3f pJ -> %.2fx"
              % (lbl, v, v / 1000, CMOS_PJ["LOGIC"], CMOS_PJ["LOGIC"] * 1000 / v))
    print("    generic alu.json, wp proxy, 2 fF loads: %6.3f pJ"
          % (gw * E_GATE_SETTLE * (c_self_inv / C_EFF_PER_GATE) / 1000
             + NC * E_GATE_SETTLE * (0.5 * CLOAD_ANCHOR / C_EFF_PER_GATE) / 1000))
    print("\n  *** CHASE: QAL %.2f fJ/cell/op vs CMOS %.2f fJ/cell/op -- a 0.5%% agreement"
          % (e_wp / nmap, CMOS_PJ["LOGIC"] * 1000 / 4927))
    print("      between two numbers from completely independent chains (mine: Xyce 8-gate")
    print("      anchor x liberty widths; theirs: OpenSTA liberty power x a real VCD).  Chased:")
    print("      it is a COINCIDENCE of two opposing factors, and the factors are worth naming")
    print("      because they are the whole story of why QAL barely wins the logic term:")
    print("        ACTIVITY.  CMOS pays only for nodes that toggle.  alu_phys.vcd gives %.4f"
          % 0.4524)
    print("        value changes per identifier per clock cycle over %d identifiers and %d" % (13034, 2154))
    print("        cycles [MEASURED, my count] -- ~%.3f 0->1 events/node/cycle.  QAL pays the" % (0.4524 / 2))
    print("        rail self term (nwell + pMOS junctions) at alpha = 1.000 BY CONSTRUCTION --")
    print("        the rail ramps through every gate in the bank whether its data changed or")
    print("        not -- and the load term at the measured a = 0.5.  So QAL charges ~2-4x")
    print("        more node-events per op than CMOS does.")
    print("        SWING AND RECOVERY.  QAL runs at dV = 1.0 V not 1.2 V and gives charge back.")
    print("      The two cancel to within 0.5% on this netlist.  That is luck, not physics, and")
    print("      it should be re-checked the moment a real bank is measured.")
    print("\n  WHAT WOULD MAKE THIS A MEASUREMENT: simulate one real ALU bank -- e.g. the 240")
    print("  cells of level 1 in their actual type mix with their actual fanout loads -- on a")
    print("  pulsed inductor at dV=1.0, the way the 8-inverter anchor was done.  That is one")
    print("  Xyce run of ~240 cells, which is inside the ~4-minute budget, and it would")
    print("  replace the proxy weighting with a measured bank energy.")
    res["E_logic_fJ"] = {"naive": e_naive, "wp": e_wp, "area": e_ar, "cin": e_cp}

    # ======================================================= (c)
    sect("(c) LATENCY  [COMPOSED: depth x measured 342.0 ps/hop]")
    print("  QAL generic depth %d x 342.0 ps = %6.3f ns" % (D, D * T_HOP / 1000))
    print("  QAL mapped  depth 38 x 342.0 ps = %6.3f ns" % (38 * T_HOP / 1000))
    print("  CMOS [MEASURED-BY-PEER, OpenSTA at 1.2 V, placed + estimated parasitics]:")
    print("    in-block combinational worst path  %.4f ns over %d logic stages + 6 buffers"
          % (CMOS_CRIT_NS, CMOS_STAGES))
    print("    worst reg-to-reg arrival           %.4f ns" % CMOS_REG2REG_NS)
    print("    shipped period                     %.2f ns (slack +0.0091 ns, MET)" % CMOS_PERIOD_NS)
    print("  NOTE the depth agreement is real, not a coincidence: my generic depth is %d and" % D)
    print("  the mapped depth is 38, and the STA critical path independently walks %d logic"
          % CMOS_STAGES)
    print("  stages.  ABC's complex cells (a21oi/o21ai absorbing 2 generic levels) are exactly")
    print("  offset by 2:1 MUXes expanding into a21oi+o21ai pairs -- visible in final_sta2.log,")
    print("  where the path alternates a21oi/o21ai for 14 stages.  So generic depth is a fair")
    print("  proxy for CMOS logic depth on this design.")
    print("\n  per stage: CMOS %.1f ps/stage   QAL %.1f ps/hop  -> QAL is %.2fx SLOWER per level"
          % (CMOS_CRIT_NS * 1000 / CMOS_STAGES, T_HOP, T_HOP / (CMOS_CRIT_NS * 1000 / CMOS_STAGES)))
    print("  single-op latency: QAL %.3f ns = %.2fx the CMOS comb path, %.2fx the shipped cycle."
          % (D * T_HOP / 1000, D * T_HOP / 1000 / CMOS_CRIT_NS, D * T_HOP / 1000 / CMOS_PERIOD_NS))
    print("  THROUGHPUT reading (pipeline full, one op per beat, %d in flight):" % D)
    print("    %.3f Gop/s vs CMOS %.3f Gop/s = %.2fx, after a %.3f ns fill."
          % (1000.0 / T_HOP, 1.0 / CMOS_PERIOD_NS, (1000.0 / T_HOP) * CMOS_PERIOD_NS, D * T_HOP / 1000))
    print("    That %.1fx is the north-star-relevant number (GPU lanes are streaming), but it"
          % ((1000.0 / T_HOP) * CMOS_PERIOD_NS))
    print("    compares a %d-deep QAL pipeline against an UNPIPELINED 37-stage CMOS block." % D)
    print("    Pipelining the CMOS block to ~1 stage/cycle would give it ~%.2f Gop/s too; the"
          % (1000.0 / (CMOS_CRIT_NS * 1000 / CMOS_STAGES)))
    print("    honest QAL speed claim is 'no worse per stage than a 342 ps clock', not 13.9x.")

    # ======================================================= (d)
    sect("(d) PER-BANK OVERHEAD -- switch, inductor, zero-current detector")
    print("  1. THE TRANSFER SWITCH DOES NOT AMORTIZE.")
    print("     qal_bankN_sqrtN.py:31-36 builds an N=8M bank as M parallel copies: C_A*M,")
    print("     L/M, Rs/M, SWITCH WIDTH *M -- and the MEASURED per-gate transferred charge is")
    print("     then invariant (4.1405 / 4.1499 / 4.1474 fC at N=8/32/128, 0.23% span).")
    print("     Holding the transfer loss fixed therefore REQUIRES the switch to grow with the")
    print("     bank.  Switch cost is PER GATE, not per bank.  The 'amortize the switch over")
    print("     the bank' framing in qal_pulse_topup.json's _doc is wrong for a fixed-loss bank.")
    print("     anchor switch at N=8: %.0f um total device = %.2f um/gate"
          % (WSW_TOT, WSW_TOT / N_ANCHOR))
    print("     MEASURED net gate drive, IDEAL PWL driver (charge returned on the falling")
    print("       edge): |EGT| = %.3f fJ/hop = %.3f fJ/gate" % (EGT_HOP, EGT_HOP / N_ANCHOR))
    cg = WSW_TOT * cg_per_um
    e_full = cg * VGH ** 2
    print("     DERIVED if that gate is driven by an ordinary CMOS buffer (no recovery):")
    print("       c_g = %.4f fF/um from liberty sg13g2_inv_1 (Cin %.4f fF over %.2f um of"
          % (cg_per_um, inv_c, inv_wt))
    print("       device) -> C_g = %.1f fF, E = C_g*VGH^2 = %.1f fJ/hop = %.2f fJ/gate"
          % (cg, e_full, e_full / N_ANCHOR))
    print("     => switch tax band %.3f - %.2f fJ/gate against %.3f fJ/gate of logic:"
          % (EGT_HOP / N_ANCHOR, e_full / N_ANCHOR, E_GATE_SETTLE))
    print("        %.2fx to %.1fx the thing it powers.  THIS IS THE DOMINANT UNCERTAINTY IN"
          % (EGT_HOP / N_ANCHOR / E_GATE_SETTLE, e_full / N_ANCHOR / E_GATE_SETTLE))
    print("        THE WHOLE QAL ARM, and it is larger than the ZCD uncertainty the campaign")
    print("        has been worrying about.  It collapses only if the switch gate drive is")
    print("        ITSELF resonant/recovered -- never built or simulated here.")

    print("\n  2. THE INDUCTOR IS THE HARD STRUCTURAL WALL.  L_required = %.1f nH x 8/N."
          % L_ANCHOR_NH)
    print("     PDK anchors: inductor PCell default estimates are %.3f pH (1 turn) and %.1f pH"
          % (L_PDK_1T_PH, L_PDK_2T_PH))
    print("     (2 turns) at minimum geometry; the canonical xschem default geometry is a")
    print("     2-turn, 222 um diameter, 10 um wide spiral.  Planar spirals in this BEOL are a")
    print("     sub-nH to low-nH device.")
    print("     The QAL anchor's own L = %.1f nH is %.0fx the PDK 2-turn estimate.  NO ONE IN"
          % (L_ANCHOR_NH, L_ANCHOR_NH * 1000 / L_PDK_2T_PH))
    print("     THE ON-DISK RECORD HAS CHECKED THE OPERATING POINT AGAINST THE PDK's INDUCTORS.")
    print("     %5s %8s %10s %12s" % ("L_tgt", "N_min", "banks ok", "gates covered"))
    for thr in (0.5, 1.0, 5.0, 10.0, 30.0):
        nmin = L_ANCHOR_NH * N_ANCHOR / thr
        ok = [n for n in prof if n >= nmin]
        print("     %4.1f nH %8.0f %7d/%-3d %11.1f%%" % (thr, nmin, len(ok), D, 100.0 * sum(ok) / NC))
    print("     => at ANY plausible on-chip L the ALU's tail banks are unbuildable: level 37")
    print("        (N=2) would need %.0f nH.  Bank-per-level DOES NOT SURVIVE on this design."
          % (L_ANCHOR_NH * N_ANCHOR / 2))

    print("\n  3. THE ZCD IS THE ONLY OVERHEAD THAT TRULY AMORTIZES (fixed per bank).")
    zl, zh = D * E_ZCD[0], D * E_ZCD[1]
    print("     %4s %6s %13s %13s" % ("lvl", "N", "ZCD/gate lo", "ZCD/gate hi"))
    for i, n in enumerate(prof, 1):
        if i <= 2 or n <= 4 or i in (13, 27, 28):
            print("     %4d %6d %13.3f %13.3f" % (i, n, E_ZCD[0] / n, E_ZCD[1] / n))
    print("     37 banks x ZCD = %.2f - %.2f pJ/op (ASSUMED 30-300 fJ), vs %.3f pJ of logic."
          % (zl / 1000, zh / 1000, e_wp / 1000))
    thin = [n for n in prof if n <= 32]
    print("     the %d banks of N<=32 carry %.1f%% of the ZCD cost for %.2f%% of the gates."
          % (len(thin), 100.0 * len(thin) / D, 100.0 * sum(thin) / NC))

    print("\n  4. DOES THE BANK-PER-LEVEL MODEL SURVIVE?  NO -- and the fix is forced.")
    slow = ((1.2 - 0.4) / (0.5826 - 0.4)) ** 1.3
    t_set = 34.81 * slow
    print("     The hop is LC-limited at %.0f ps [MEASURED]; gate settling is RC-limited, so" % T_HOP)
    print("     several levels can in principle ripple inside one hop.  The matched inverter")
    print("     is %.2f ps [MEASURED] but at 1.2 V; a QAL gate settles at the MEASURED mean" % 34.81)
    print("     rail 0.5826 V with Vt_est 0.400 V [ASSUMED, the project's own].  Alpha-power")
    print("     with alpha=1.3 gives ((1.2-0.4)/(0.5826-0.4))^1.3 = %.1fx -> t_settle ~ %.0f ps"
          % (slow, t_set))
    print("     per level [DERIVED; no multi-level settling chain has ever been simulated].")
    print("     Because %.0f ps < %.0f ps, EVERY merged level is CHEAPER IN TIME than its own"
          % (t_set, T_HOP))
    print("     hop.  Merging is free speed as well as saved overhead.  A bank spanning k")
    print("     levels beats at max(%.0f, k x %.0f) ps." % (T_HOP, t_set))
    print("\n     PARETO, exhaustive DP over every contiguous level partition, minimising the")
    print("     pipeline beat subject to an inductor ceiling (L_bank = 2222.4/N_bank nH):")
    print("     %9s %7s %6s %8s %8s %8s   %s"
          % ("L_cap_nH", "N_min", "banks", "beat_ns", "Gop/s", "fill_ns", "vs CMOS 0.211 Gop/s"))
    pre = [0]
    for n in prof:
        pre.append(pre[-1] + n)

    def dp_best(lcap):
        nmin = L_ANCHOR_NH * N_ANCHOR / lcap
        INF = float("inf")
        dp = [(INF, None)] * (D + 1)
        dp[0] = (0.0, ())
        for j in range(1, D + 1):
            bv, bp = INF, None
            for i in range(j):
                if dp[i][0] == INF:
                    continue
                N, k = pre[j] - pre[i], j - i
                if N < nmin:
                    continue
                v = max(dp[i][0], max(T_HOP, k * t_set))
                if v < bv:
                    bv, bp = v, dp[i][1] + ((k, N),)
            dp[j] = (bv, bp)
        return dp[D]

    pareto = {}
    for lcap in (1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0, 100.0, L_ANCHOR_NH * N_ANCHOR / 2):
        v, p = dp_best(lcap)
        if p is None:
            continue
        fill = sum(max(T_HOP, k * t_set) for k, _ in p) / 1000.0
        pareto[lcap] = (v, p, fill)
        print("     %9.1f %7.0f %6d %8.3f %8.3f %8.2f   %.2fx"
              % (lcap, L_ANCHOR_NH * N_ANCHOR / lcap, len(p), v / 1000, 1000 / v, fill,
                 (1000 / v) * CMOS_PERIOD_NS))
    print("     THE TAIL SETS EVERY ROW.  At any buildable L the last bank has to swallow the")
    print("     whole thin tail, and its ripple time IS the beat: at L<=10 nH the partition is")
    print("     8 single-level head banks + ... + one 15-level/250-gate tail bank beating at")
    print("     %.2f ns.  The ALU's 13.9x throughput headline is an artefact of assuming 37"
          % (pareto[10.0][0] / 1000 if 10.0 in pareto else 0))
    print("     inductors of 4.8-1111 nH.  With PDK-plausible inductors QAL's throughput on")
    print("     this block is %.2fx-%.2fx CMOS, i.e. a WASH, not a win."
          % ((1000 / pareto[2.0][0]) * CMOS_PERIOD_NS if 2.0 in pareto else 0,
             (1000 / pareto[10.0][0]) * CMOS_PERIOD_NS if 10.0 in pareto else 0))
    print("     ENERGY does improve with merging: ZCD cost falls from %.2f-%.2f pJ (37 banks)"
          % (zl / 1000, zh / 1000))
    if 10.0 in pareto:
        b10 = len(pareto[10.0][1])
        print("     to %.2f-%.2f pJ (%d banks at L<=10 nH).  The switch tax does NOT fall: total"
              % (b10 * E_ZCD[0] / 1000, b10 * E_ZCD[1] / 1000, b10))
    print("     switch width tracks total bank capacitance, which is the whole netlist either way.")
    res["pareto"] = {str(k): {"beat_ps": v[0], "banks": len(v[1]), "fill_ns": v[2]}
                     for k, v in pareto.items()}

    # totals
    print("\n  COMPOSED TOTAL, bank-per-level, 37 banks:")
    print("  %-48s %10s %10s" % ("term", "lo pJ/op", "hi pJ/op"))
    rows = [("logic settle (Cin proxy / wp proxy)", min(e_wp, e_cp) / 1000, max(e_wp, e_cp) / 1000),
            ("transfer-switch gate drive (ideal / CMOS buf)",
             nmap * EGT_HOP / N_ANCHOR / 1000, nmap * e_full / N_ANCHOR / 1000),
            ("ZCD x 37 banks (ASSUMED 30 / 300 fJ)", zl / 1000, zh / 1000)]
    lo = hi = 0.0
    for lbl, a, b in rows:
        lo += a
        hi += b
        print("  %-48s %10.3f %10.3f" % (lbl, a, b))
    print("  %-48s %10.3f %10.3f" % ("SUBTOTAL (before top-up conversion)", lo, hi))
    print("  top-up: the rail must REPLACE all of the above through a converter whose only")
    print("    two MEASURED efficiency points are %.2f%% and %.2f%% (qal_pulse_topup.json,"
          % (100 * ETA_TOPUP[0], 100 * ETA_TOPUP[1]))
    print("    both UNTUNED and at dV=0.6).  At %.2f%% the subtotal becomes %.2f - %.2f pJ/op;"
          % (100 * ETA_TOPUP[1], lo / ETA_TOPUP[1], hi / ETA_TOPUP[1]))
    print("    at anything near %.2f%% QAL is not a power technology.  NOT KNOWABLE from disk."
          % (100 * ETA_TOPUP[0]))
    print("  CMOS reference [MEASURED-BY-PEER]: %.3f pJ/cycle = %.3f logic + %.3f DFF + %.3f clk"
          % (CMOS_TOTAL_PJ, CMOS_PJ["LOGIC"], CMOS_PJ["DFF"], CMOS_PJ["CLKTREE"]))
    print("  => QAL %.2fx BETTER (lo, and only if the switch drive is recovered) .. %.2fx WORSE"
          % (CMOS_TOTAL_PJ / lo, hi / CMOS_TOTAL_PJ))
    print("     (hi), before any top-up conversion loss.  The sign of the answer is set by one")
    print("     unmeasured quantity: whether the power-switch gate drive is recovered.")
    res["totals_pJ"] = {"lo": lo, "hi": hi, "cmos": CMOS_TOTAL_PJ}

    # ======================================================= (e)
    sect("(e) THE 188 REGISTERS -- what holds state between waves")
    ff = {int(k): v for k, v in lv["ff_input_levels"].items()}
    print("  D-pin arrival levels: %s" % sorted(ff.items()))
    print("  55 of 188 FFs close at level 3 and 31 at level 7; only 2 close at level 37.")
    print("  sg13g2_dfrbpq_1: area %.4f um^2 = %.1f inverter-equivalents, wp %.2f um = %.1fx"
          % (lib["sg13g2_dfrbpq_1"]["area"], lib["sg13g2_dfrbpq_1"]["area"] / inv_a,
             wid["sg13g2_dfrbpq_1"]["wp"], wid["sg13g2_dfrbpq_1"]["wp"] / inv_wp))
    print("  188 of them = %.1f um^2 = 18.68%% of the 49310.856 um^2 block (cmos_stat.txt)."
          % (188 * lib["sg13g2_dfrbpq_1"]["area"]))
    print("\n  THE PROBLEM, stated precisely: a QAL bank rail RETURNS its charge.  That is the")
    print("  mechanism.  When the rail recycles, every gate powered from it loses its output")
    print("  level -- the bank is volatile BY CONSTRUCTION, and 'energy recovered' and 'state")
    print("  retained' are the same charge.  So nothing inside the recovered domain can hold")
    print("  state, and the registers must sit OUTSIDE it.")
    print("\n  Options and what each costs:")
    print("   (i) DC-powered DFF at the wave boundary, rail ramp used as the timing reference.")
    print("       Cost: the full CMOS DFF cell energy, %.3f pJ/cycle for 188 DFF"
          % CMOS_PJ["DFF"])
    print("       [MEASURED-BY-PEER], of which the data-dependent part is small: switching is")
    print("       only %.4f mW of the %.4f mW DFF total, i.e. %.1f%% -- the rest is clock-pin"
          % (0.000138852 * 1000, 0.0029666 * 1000, 100 * 0.000138852 / 0.0029666))
    print("       internal power that a QAL wave would still have to pay in some form.")
    print("       SAVED: the 49-buffer clock tree, %.3f pJ/cycle [MEASURED-BY-PEER], because"
          % CMOS_PJ["CLKTREE"])
    print("       the bank rail IS the timing reference and it is already being distributed.")
    print("       NOT SAVED: the DFF internal power, unless the latch itself is adiabatic.")
    print("   (ii) adiabatic/charge-recovering latch. NOT MEASURED, NOT DESIGNED, and the")
    print("       campaign's own A2 result (qal_a2, 'single-rail source-follower cannot")
    print("       cascade, Vt clamp') is the nearest thing to evidence -- and it is negative.")
    print("   (iii) bounce the state through a second bank held at its level. Forbidden by the")
    print("       same measured droop that forces K=1 top-up: the level walks off the 0.50 V")
    print("       settling cliff within ~2 hops (qal_burst_model.py mechanism 2).")
    print("\n  VERDICT: (i) is the only binding with any measured backing.  It is honest and it")
    print("  is NOT clockless -- it keeps 188 statically-powered flip-flops and deletes the")
    print("  clock TREE, not the clock.  Accounted that way:")
    print("    QAL ALU = [composed logic+overheads %.2f-%.2f pJ] + [188 DC DFF %.3f pJ MEASURED]"
          % (lo, hi, CMOS_PJ["DFF"]))
    print("            = %.2f - %.2f pJ/op   vs CMOS %.3f pJ/cycle"
          % (lo + CMOS_PJ["DFF"], hi + CMOS_PJ["DFF"], CMOS_TOTAL_PJ))
    print("    -> %.2fx better .. %.2fx worse.  The clock-tree deletion alone is %.3f pJ ="
          % (CMOS_TOTAL_PJ / (lo + CMOS_PJ["DFF"]), (hi + CMOS_PJ["DFF"]) / CMOS_TOTAL_PJ,
             CMOS_PJ["CLKTREE"]))
    print("       %.1f%% of the CMOS block and it is the ONE QAL win on this rung that is"
          % (100 * CMOS_PJ["CLKTREE"] / CMOS_TOTAL_PJ))
    print("       backed end-to-end by measurement on both sides.")
    print("\n  UNSOLVED, stated as such: what holds state between waves in a TRUE clockless QAL")
    print("  is unsolved.  No charge-recovering storage element exists in this campaign, the")
    print("  one cascading experiment that bears on it (A2) failed on a Vt clamp, and the")
    print("  measured level-droop budget forbids holding a level across hops.")

    json.dump(res, open(OUT, "w"), indent=1)
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
