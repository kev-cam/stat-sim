#!/usr/bin/env python3
"""Event-driven energy composition of the WHOLE Vortex (mini) over three real
kernels (hello/saxpy/sgemm), stat-sim style: characterize once on the measured
physical ALU anchor, compose per module from measured per-scope activity.

  E(module,kernel) = events x per-event energy            (comb dynamic)
                   + flop clock floor + flop data term    (seq)
                   + clock tree                           (clock)
                   + leakage x wall time                  (comb+DFF+SRAM proxy)
   with UNGATED and IDEALLY-GATED clock variants, liberty-basis and
   transistor-corrected columns, and the RTL->gate alpha band carried through.

INPUTS (all verified on disk):
  /home/claude/vortex_energy/permodule.json   static census + per-kernel D2 activity
  /home/claude/vortex_energy/mem_arrays.json  90 $mem_v2 geometries (471,900 bits)
  /home/claude/vortex_energy/calib/*.json     anchor activity (RTL/synth/phys VCDs)
  /usr/local/src/mylex/probes/layopt/evidence/alu_cmos/work/inst_power.json
      per-instance liberty power of the placed+CTS ALU at measured VCD activity
      (5164 instances, 4.75 ns; groups verified: comb 4.425379 mW / seq 2.966603
       / clk 1.754673 -> total 9.146656 mW = alu_cmos_results.log:34)

CALIBRATION ANCHOR (MEASURED, alu_cmos_results.log):
  Combinational 21.021 pJ/cycle, Sequential 14.091, Clock tree 8.335 (lines 48-51)
  flop CLK-pin floor = 78.856% of Sequential (line 56); cycles/op 1.0742 (line 42)
  transistor corrections per class (lines 8-27, 60-63): small logic x1.87-2.31,
  buffers x1.26-1.40, flop x0.782 (floor x0.549 / data x1.654), clock tree x1.384
  physical overhead +40.3% over synth-only (line 76) -- ALREADY INSIDE the
  coefficients here, because they are calibrated on the PHYSICAL netlist.

The nulex alu_top is a DIFFERENT Vortex revision (no FPU): COEFFICIENT SOURCE
ONLY, never composed as a module of the design.
"""
import json, os, sys, collections, math

D = "/home/claude/vortex_energy"
AL = "/usr/local/src/mylex/probes/layopt/evidence/alu_cmos/work"
T_CLK = 4.75e-9          # s -- ASSUMED for the whole chip (ALU closed at 4.75 ns)
NOPS_ANCHOR = 2001.0

# ----------------------------------------------------------------- anchor load
pm = json.load(open(D + "/permodule.json"))
MODS = pm["modules"]
NC = {k: v["ncycles"] for k, v in pm["_meta"]["kernels"].items()}
KERNELS = ["hello", "saxpy", "sgemm"]

pw = {d["name"].lstrip("\\"): d for d in json.load(open(AL + "/inst_power.json"))}
typ = json.load(open(D + "/calib/netclass_phys.json"))["typ"]

def grp(n, t):
    if "dfrbpq" in t: return "seq"
    if n.startswith("clkbuf") or n.startswith("clkload") or "clkinv" in n: return "clk"
    if "tie" in t.lower(): return "tie"
    return "comb"

P = collections.Counter(); NG = collections.Counter()
for n, d in pw.items():
    g = grp(n, typ[n]); P[g] += d["total"]; NG[g] += 1
assert abs(P["comb"] - 4.425379e-3) < 1e-8 and abs(P["seq"] - 2.966603e-3) < 1e-8 \
   and abs(P["clk"] - 1.754673e-3) < 1e-8, "inst_power group decomposition drifted"
E_COMB_CYC = P["comb"] * T_CLK * 1e15   # fJ/cycle, MEASURED (liberty, physical)
E_SEQ_CYC  = P["seq"]  * T_CLK * 1e15
E_CLK_CYC  = P["clk"]  * T_CLK * 1e15
N_FF_A = NG["seq"]                       # 188
FLOP_CLKFRAC = 0.78856                   # liberty at measured alpha_ff (log line 56)
ALPHA_FF_A = 0.4116                      # MEASURED flop Q toggle rate (type_census)

# anchor activity (MEASURED: this campaign's RTL/synth/phys VCD analyses)
rtl = json.load(open(D + "/calib/rtl_act.json"))
phy = json.load(open(D + "/calib/phys_act.json"))
syn = json.load(open(D + "/calib/synth_act.json"))
N_GEN_COMB_A = 4533                      # generic comb cells of alu_top (alu.json)
N_GEN_A = 4721                           # + 188 DFF
ALPHA_RTL_A = rtl["tot"]["rtl"] / (rtl["nbits"] * rtl["cycles"])       # 0.2286
TOG_COMB_PHYS = phy["tot"]["comb"] / phy["cycles"]                     # 1741.2/cyc
TOG_COMB_SYN  = syn["tot"]["comb"] / syn["cycles"]

# (a) coefficients ------------------------------------------------------------
e_tog_comb = E_COMB_CYC / TOG_COMB_PHYS                    # fJ / gate-output toggle
e_ff = E_SEQ_CYC / N_FF_A                                  # fJ/flop/cycle @ alpha_ff
E0_FF = FLOP_CLKFRAC * e_ff                                # clock-pin floor fJ/f/cyc
S_FF = (e_ff - E0_FF) / ALPHA_FF_A                         # data slope fJ per unit a
E_TREE = E_CLK_CYC / N_FF_A                                # fJ/flop/cycle
PHYS_OVH = 9.146656 / 6.518550                             # 1.403 (log lines 74-76)

# (b) RTL-net-alpha -> gate-activity multiplier band --------------------------
# central: measured phys gate toggles per GENERIC comb cell per unit RTL alpha
K_C  = (TOG_COMB_PHYS / N_GEN_COMB_A) / ALPHA_RTL_A        # 1.680
K_LO = (TOG_COMB_SYN  / N_GEN_COMB_A) / ALPHA_RTL_A        # 1.351 (synth basis)
# window spread (16 windows, both VCDs): +-0.02 on K_C -- MEASURED, tiny
kw = []
for i in range(phy["nwin"]):
    rt = rtl["win"][i].get("rtl", 0); pc = phy["win"][i].get("comb", 0)
    if rt: kw.append((pc / N_GEN_COMB_A) / (rt / rtl["nbits"]))
K_WIN = (min(kw), max(kw))
# boundary-visibility bias, measured ON THE ANCHOR: alpha over top-scope nets
# only (the `TRACING_OFF analog) reads x1.569 LOW vs full tracing
F_BOUNDARY = 0.22855 / 0.14570                              # 1.569 MEASURED
D0 = rtl["nbits"] / N_GEN_A                                 # anchor traced density 1.713
K_FF = ALPHA_FF_A / ALPHA_RTL_A                             # 1.801 flop-alpha mapping
K_FF_WIN = (1.774, 1.844)

def f_mod(nbits, cells):
    """Per-module upper-band factor for boundary-biased tracing: interpolate
    1 -> F_BOUNDARY as traced-bit density falls below the anchor's. DERIVED
    heuristic (density is the only measurable proxy for untraced fraction)."""
    if not nbits or not cells: return F_BOUNDARY
    d = nbits / cells
    return 1.0 + (F_BOUNDARY - 1.0) * min(1.0, max(0.0, 1.0 - d / D0))

# transistor correction per class (MEASURED, alu_cmos_results.log:8-27,60-63)
R_TYPE = {"sg13g2_inv_1": 1.380, "sg13g2_buf_1": 1.262, "sg13g2_buf_8": 1.331,
          "sg13g2_buf_16": 1.402, "sg13g2_nand2_1": 1.948, "sg13g2_nor2_1": 2.163,
          "sg13g2_o21ai_1": 2.313, "sg13g2_a21oi_1": 2.179, "sg13g2_mux2_1": 1.8685}
R_BUF_X, R_LOG_X = 1.330, 2.062          # extrapolation means (log line 32)
def r_of(t):
    if t in R_TYPE: return R_TYPE[t]
    return R_BUF_X if ("buf" in t or "dlygate" in t) else R_LOG_X
num = den = 0.0
for n, d in pw.items():
    if grp(n, typ[n]) == "comb":
        num += d["total"] * r_of(typ[n]); den += d["total"]
C_COMB_ALU = num / den                    # power-weighted comb correction on anchor
R_GEN = {"$_MUX_": 1.8685, "$_NOT_": 1.380, "$_AND_": 2.0555, "$_OR_": 2.0555,
         "$_XOR_": 2.062}
MIX_ALU = {"$_MUX_": 1957, "$_NOT_": 122, "$_AND_": 1298, "$_XOR_": 358, "$_OR_": 798}
def mixr(mix):
    n = sum(v for k, v in mix.items() if k in R_GEN)
    if not n: return sum(R_GEN.values()) / len(R_GEN)
    return sum(v * R_GEN[k] for k, v in mix.items() if k in R_GEN) / n
MIXR_ALU = mixr(MIX_ALU)
def c_comb(mix):
    """Module comb correction: anchor's power-weighted correction, shifted by the
    module's generic-mix ratio vs the anchor's (count-weighted -- ASSUMED)."""
    return C_COMB_ALU * mixr(mix) / MIXR_ALU
C_FLOOR, C_DATA, C_TREE = 0.549, 1.654, 1.384   # MEASURED (log lines 60-63,25-27)

# leakage coefficients (MEASURED, campaign; see threeway_gals_campaign.md)
LEAK_COMB = (117e-12, 124.25e-12, 131.5e-12)    # W/cell (lo, mid, hi band)
LEAK_DFF = 526.5e-12
LEAK_SRAM_BIT = 12.09e-12                        # SG13G2 macro 24.7519nW/2048b
PHYS_CELL_INFL = NG["comb"] / N_GEN_COMB_A       # 4921/4533=1.086 phys cells/gen cell
SRAM_EDGE = (0.2958, 0.9849)                     # pJ/edge partial-deselect band

# SRAM bits per module (name-path attribution; totals == census 90 arrays)
mems = json.load(open(D + "/mem_arrays.json"))
P_ = "clusters.cluster.sockets.socket."
ISL_PREF = [("alu_int", P_ + "cores.core.execute.alu_unit.alu_int"),
    ("muldiv", P_ + "cores.core.execute.alu_unit.muldiv"),
    ("alu_unit__glue", P_ + "cores.core.execute.alu_unit"),
    ("fpu_unit", P_ + "cores.core.execute.fpu_unit"),
    ("lsu_unit", P_ + "cores.core.execute.lsu_unit"),
    ("sfu_unit", P_ + "cores.core.execute.sfu_unit"),
    ("execute__glue", P_ + "cores.core.execute"),
    ("issue", P_ + "cores.core.issue"), ("schedule", P_ + "cores.core.schedule"),
    ("fetch", P_ + "cores.core.fetch"), ("decode", P_ + "cores.core.decode"),
    ("commit", P_ + "cores.core.commit"), ("lmem_unit", P_ + "cores.core.lmem_unit"),
    ("mem_coalescer", P_ + "cores.core.mem_coalescer"),
    ("core__glue", P_ + "cores.core"),
    ("dcache", P_ + "dcache"), ("icache", P_ + "icache"),
    ("mem_arb", P_ + "mem_arb"), ("l2", "clusters.cluster.l2cache"),
    ("l3", "l3cache"), ("whole_chip__glue", "")]
SRAM_BITS = collections.Counter(); SRAM_N = collections.Counter()
for x in mems:
    p = x["path"] or ""
    if not p:            # the lone 24-bit $auto ROM: census puts decode mem=1
        tgt = "decode"
    else:
        tgt = next(nm for nm, pref in ISL_PREF if p.startswith(pref))
    SRAM_BITS[tgt] += x["bits"]; SRAM_N[tgt] += 1
assert sum(SRAM_N.values()) == 90 and sum(SRAM_BITS.values()) == 471900

# ------------------------------------------------------------------- composer
LEAVES = ["alu_int", "muldiv", "alu_unit__glue", "fpu_unit", "lsu_unit", "sfu_unit",
          "execute__glue", "issue", "schedule", "fetch", "decode", "commit",
          "lmem_unit", "mem_coalescer", "core__glue", "dcache", "icache",
          "mem_arb", "l2", "l3", "whole_chip__glue"]
PARENT_DUTY = {"alu_unit__glue": "alu_unit", "execute__glue": "execute",
               "core__glue": "core", "whole_chip__glue": "whole_chip",
               "mem_coalescer": "core"}

def mod_inputs(name, k):
    """(alpha, busy2, nbits, provenance-note) for a leaf module."""
    m = MODS[name]
    dyn = m["dynamic"]
    if name == "mem_coalescer":
        g = MODS["core__glue"]["dynamic"][k]
        a = g["alpha"]
        note = "ASSUMED alpha := core__glue alpha (module `TRACING_OFF; its " \
               "boundary toggles live in core__glue)"
    elif dyn and dyn.get(k) and "duty2" in dyn[k]:
        a = dyn[k]["alpha"]; note = "MEASURED"
    else:  # glue: subtraction alpha, no duty
        a = dyn[k]["alpha"] if dyn and dyn.get(k) else 0.0
        note = "DERIVED (subtraction)"
    if a is None: a = 0.0
    if name in PARENT_DUTY:
        busy = MODS[PARENT_DUTY[name]]["dynamic"][k]["busy2_cycles"]
        note += "; duty := parent %s duty2 (ASSUMED)" % PARENT_DUTY[name]
    else:
        busy = dyn[k]["busy2_cycles"]
    nbits = (dyn[k]["nbits"] if dyn and dyn.get(k) else None)
    return a, busy, nbits, note

def compose(name, k, static=None, alpha=None, busy=None, nbits=None, ncyc=None,
            alpha_ff=None, mix=None):
    """Energy of one module for one kernel. Returns dict of fJ totals."""
    s = static if static is not None else MODS[name]["static"]
    ncyc = ncyc if ncyc is not None else NC[k]
    if alpha is None:
        alpha, busy, nbits, note = mod_inputs(name, k)
    else:
        note = "explicit"
    mix = mix if mix is not None else s.get("mix", MIX_ALU)
    ncomb, nseq = s["comb"], s["seq"]
    fm = f_mod(nbits, ncomb + nseq)
    aff = alpha_ff if alpha_ff is not None else min(0.5, K_FF * alpha)
    aff_hi = alpha_ff if alpha_ff is not None else min(0.5, K_FF * alpha * fm)
    cc = c_comb(mix)
    # events x per-event energy (gate toggles estimated from measured RTL toggles)
    tog_c = ncomb * alpha * K_C * ncyc
    e_comb = tog_c * e_tog_comb
    e_comb_lo = ncomb * alpha * K_LO * ncyc * e_tog_comb
    e_comb_hi = ncomb * alpha * K_C * fm * ncyc * e_tog_comb
    e_data = nseq * aff * S_FF * ncyc
    e_data_hi = nseq * aff_hi * S_FF * ncyc
    e_floor_ug = nseq * E0_FF * ncyc
    e_floor_g  = nseq * E0_FF * busy
    e_tree_ug = nseq * E_TREE * ncyc
    e_tree_g  = nseq * E_TREE * busy
    tw = ncyc * T_CLK
    e_leak = (ncomb * PHYS_CELL_INFL * LEAK_COMB[1] + nseq * LEAK_DFF
              + SRAM_BITS.get(name, 0) * LEAK_SRAM_BIT) * tw * 1e15
    e_sram_lo = SRAM_N.get(name, 0) * busy * SRAM_EDGE[0] * 1e3   # fJ
    e_sram_hi = SRAM_N.get(name, 0) * busy * SRAM_EDGE[1] * 1e3
    def tot(gated, corr):
        c = e_comb * (cc if corr else 1.0)
        d = e_data * (C_DATA if corr else 1.0)
        f = (e_floor_g if gated else e_floor_ug) * (C_FLOOR if corr else 1.0)
        t = (e_tree_g if gated else e_tree_ug) * (C_TREE if corr else 1.0)
        return c + d + f + t + e_leak
    return dict(
        comb=e_comb, comb_lo=e_comb_lo, comb_hi=e_comb_hi, comb_corr=e_comb * cc,
        data=e_data, data_hi=e_data_hi, floor_ug=e_floor_ug, floor_g=e_floor_g,
        tree_ug=e_tree_ug, tree_g=e_tree_g, leak=e_leak,
        sram_lo=e_sram_lo, sram_hi=e_sram_hi,
        lib_ungated=tot(False, False), lib_gated=tot(True, False),
        cor_ungated=tot(False, True), cor_gated=tot(True, True),
        cor_gated_lo=tot(True, True) - e_comb * c_comb(mix) + e_comb_lo * c_comb(mix),
        cor_gated_hi=tot(True, True) - e_comb * c_comb(mix) + e_comb_hi * c_comb(mix)
                     + (e_data_hi - e_data) * C_DATA,
        alpha=alpha, busy=busy, fm=fm, cc=cc, note=note)

# --------------------------------------------------------- selection verdicts
def verdict(name):
    if name.endswith("__glue"): return "(glue)"
    s = MODS[name]["static"]
    d = MODS[name].get("dynamic")
    tags = []
    scc = s.get("regs_in_cycles", 0)
    if scc: tags.append("reg-CYCLES(%d)->no pure QDI" % scc)
    elif s.get("seq"): tags.append("FF-reg-graph->QDI-composable")
    if s.get("mem"): tags.append("SRAM(%d)->sync interface" % s["mem"])
    if "arb" in name: tags.append("arbitration->sync")
    if not s.get("seq") and not s.get("mem"):
        tags.append("comb-only (no clock terms; MUX fabric)")
    if d and all((d[k] or {}).get("duty2", 1) < 0.05 for k in KERNELS):
        tags.append("dark->power-gate+sync")
    elif d and d.get("sgemm") and "duty2" in d["sgemm"]:
        du = [d[k]["duty2"] for k in KERNELS]
        if max(du) - min(du) > 0.3: tags.append("kernel-swing duty %.2f-%.2f" % (min(du), max(du)))
    q = s.get("qal_fill")
    if q:
        big = q["n_ge32"] / max(1, s["comb"])
        if big > 0.9 and s["comb"] > 20000: tags.append("QAL-bank-rich(%.0f%%>=32)" % (100 * big))
    return "; ".join(tags) if tags else "-"

# ------------------------------------------------------------------ reporting
OUTTXT = []
def say(s=""):
    print(s); OUTTXT.append(s)

say("=" * 108)
say("EVENT-DRIVEN ENERGY COMPOSITION -- whole Vortex (mini), kernels hello/saxpy/sgemm")
say("=" * 108)
say("""
(a) CALIBRATED COEFFICIENTS (anchor = placed+CTS nulex alu_top, SG13G2, 4.75 ns, real VCD;
    liberty-basis power groups verified against inst_power.json to 1e-8:
    comb 4.425379 / seq 2.966603 / clktree 1.754673 mW = alu_cmos_results.log:34,48-51)""")
say("  e_tog_comb  = %7.3f fJ / comb gate-output toggle    MEASURED/DERIVED: 21.021 pJ/cyc over"
    % e_tog_comb)
say("                %.1f measured comb-net toggles/cycle (phys VCD, 4921 comb cells incl. 894 repair bufs)"
    % TOG_COMB_PHYS)
say("  E0_ff       = %7.3f fJ / flop / cycle  (clock-pin floor, %.3f%% of seq @ alpha_ff=%.4f)"
    % (E0_FF, 100 * FLOP_CLKFRAC, ALPHA_FF_A))
say("  S_ff        = %7.3f fJ / flop / unit-alpha (data term slope)" % S_FF)
say("  E_tree      = %7.3f fJ / flop / cycle  (53 CTS cells / 188 flops; ASSUMED linear in flops)"
    % E_TREE)
say("  phys ovh    = x%.3f over synth-only -- INCLUDED (coefficients are physical-netlist)"
    % PHYS_OVH)
say("  C_comb_ALU  = x%.3f transistor/liberty comb correction (power-weighted, anchor mix)"
    % C_COMB_ALU)
say("  per-class corr: floor x%.3f, data x%.3f, tree x%.3f; module comb corr scaled by generic mix"
    % (C_FLOOR, C_DATA, C_TREE))
say("  leakage: comb %.1f-%.1f pW/cell (x%.3f phys-cell inflation), DFF %.1f pW, SRAM %.2f pW/bit"
    % (LEAK_COMB[0] * 1e12, LEAK_COMB[2] * 1e12, PHYS_CELL_INFL, LEAK_DFF * 1e12,
       LEAK_SRAM_BIT * 1e12))
say("  CROSS-CHECK vs old add8 anchors: E_clk 0.0282 pJ/DFF/cyc vs (tree+floor)=%.1f fJ -> x%.2f"
    % (E_TREE + E0_FF, (E_TREE + E0_FF) / 28.2))
say("     (tree only %.1f fJ -> x%.2f); E_cell 0.0076 pJ vs per-toggle %.2f fJ -> x%.2f"
    % (E_TREE, E_TREE / 28.2, e_tog_comb, e_tog_comb / 7.6))
say("     (vs per-comb-cell-per-cycle at anchor activity %.2f fJ -> x%.2f). PREFER the physical-ALU"
    % (E_COMB_CYC / NG["comb"], (E_COMB_CYC / NG["comb"]) / 7.6))
say("     coefficients; add8 was synth-only + tiny CTS.")

say("""
(b) RTL-NET-ALPHA -> GATE-ACTIVITY BAND (the flagged weak link, bounded not hidden)""")
say("  anchor RTL alpha (iverilog VCD, vcdact conventions, 8086 bits) = %.5f" % ALPHA_RTL_A)
say("  gate comb toggles / GENERIC comb cell / cycle: phys %.4f, synth %.4f"
    % (TOG_COMB_PHYS / N_GEN_COMB_A, TOG_COMB_SYN / N_GEN_COMB_A))
say("  K central = %.3f (phys)   K_lo = %.3f (synth basis)   window spread %.3f-%.3f (16 windows)"
    % (K_C, K_LO, K_WIN[0], K_WIN[1]))
say("  boundary-visibility bias measured ON the anchor: full/top-only alpha = x%.3f" % F_BOUNDARY)
say("  -> per-module upper factor f_mod in [1, %.3f] by traced-bit density vs anchor d0=%.3f (DERIVED)"
    % (F_BOUNDARY, D0))
say("  flop mapping K_ff = %.3f (windows %.3f-%.3f), alpha_ff capped at 0.5" % (K_FF, *K_FF_WIN))
say("  RESIDUAL (flagged, unprobeable here): linearity of gate-alpha in RTL-alpha from the anchor's")
say("  regime (0.23) down to Vortex regimes (0.001-0.04); the stimulus has no low-alpha windows.")

# (e) instrument check ---------------------------------------------------------
say("""
(e) INSTRUMENT CHECK -- composer over the ALU's OWN census + OWN measured activity""")
chk = compose("ANCHOR", "hello", static=dict(comb=N_GEN_COMB_A, seq=188, mix=MIX_ALU),
              alpha=ALPHA_RTL_A, busy=int(rtl["cycles"]), nbits=rtl["nbits"],
              ncyc=rtl["cycles"], alpha_ff=ALPHA_FF_A, mix=MIX_ALU)
pj_cyc = chk["lib_ungated"] / rtl["cycles"] / 1e3
pj_op = pj_cyc * (2149.5 / NOPS_ANCHOR)
say("  composed (liberty, ungated): %.3f pJ/cycle -> %.3f pJ/op   TARGET 43.447 / 46.671"
    % (pj_cyc, pj_op))
say("     split fJ/cyc: comb %.0f (target 21021) seq %.0f (floor+data, target 14091) tree %.0f (8335) leak %.1f"
    % (chk["comb"] / rtl["cycles"], (chk["data"] + chk["floor_ug"]) / rtl["cycles"],
       chk["tree_ug"] / rtl["cycles"], chk["leak"] / rtl["cycles"]))
err = 100 * (pj_op / 46.671 - 1)
say("  ERROR vs measured 46.671 pJ/op: %+.2f%%  (tolerance +-2%%: %s)"
    % (err, "PASS" if abs(err) < 2 else "FAIL"))
cor_cyc = chk["cor_ungated"] / rtl["cycles"] / 1e3
say("  corrected column: %.3f pJ/cycle -> %.3f pJ/op vs transistor-measured 59.45-60.25 pJ/op range"
    % (cor_cyc, cor_cyc * 2149.5 / NOPS_ANCHOR))
say("  NOTE this check validates the composer's plumbing/units against the anchor it was")
say("  calibrated on -- it does NOT validate transfer to other modules (that is the (b) band).")
if abs(err) >= 2:
    say("  INSTRUMENT CHECK FAILED -- composer wrong, aborting"); sys.exit(1)

# (c)(d) compose all leaves ----------------------------------------------------
RES = {k: {} for k in KERNELS}
for k in KERNELS:
    for name in LEAVES:
        RES[k][name] = compose(name, k)

say("""
(c)(d) PER-KERNEL WHOLE-CHIP TOTALS (sum of 21 disjoint leaves; SRAM access band separate)
  'gated' = IDEALLY clock-gated: flop CLK-pin floor + clock tree charged only on the module's
  busy2 cycles (D2 threshold); ICG cell overhead and gating granularity IGNORED (ASSUMED best
  case). 'ungated' = clock everywhere every cycle. Data term follows alpha in both variants.
  SRAM access energy is a BOUND, not composed (arrays are `TRACING_OFF -> toggles invisible):
  n_arrays x busy2 x 0.2958-0.9849 pJ/edge (the measured partial-deselect band; a real access
  >= this). SRAM bits attributed by instance path (differs from the census cell attribution
  for 25 plain-named arrays the census left in core__glue; both total 90 arrays/471,900 bits).""")
say("%-7s %10s | %12s %12s %12s %12s | %18s | %11s" % (
    "kernel", "cycles", "lib-ungated", "lib-gated", "corr-ungated", "corr-gated",
    "corr-gated band", "Wh/kernel"))
CHIP = {}
for k in KERNELS:
    t = {f: sum(RES[k][m][f] for m in LEAVES) for f in
         ("lib_ungated", "lib_gated", "cor_ungated", "cor_gated", "cor_gated_lo",
          "cor_gated_hi", "comb", "comb_corr", "data", "floor_ug", "floor_g",
          "tree_ug", "tree_g", "leak", "sram_lo", "sram_hi")}
    CHIP[k] = t
    uJ = 1e-9  # fJ -> uJ factor applied inline below
    say("%-7s %10d | %9.2f uJ %9.2f uJ %9.2f uJ %9.2f uJ | %7.2f-%8.2f uJ | %11.3e" % (
        k, NC[k], t["lib_ungated"] * uJ, t["lib_gated"] * uJ, t["cor_ungated"] * uJ,
        t["cor_gated"] * uJ, t["cor_gated_lo"] * uJ, t["cor_gated_hi"] * uJ,
        t["cor_gated"] * 1e-15 / 3600))
say("")
for k in KERNELS:
    t = CHIP[k]
    tot = t["cor_gated"]
    say("%-7s corrected-gated split: comb %5.1f%%  seq-data %4.1f%%  clk-floor %5.1f%%  tree %5.1f%%"
        "  leak %4.1f%%   (+SRAM access bound %.2f-%.2f uJ)" % (
        k, 100 * t["comb_corr"] / tot, 100 * t["data"] * C_DATA / tot,
        100 * t["floor_g"] * C_FLOOR / tot, 100 * t["tree_g"] * C_TREE / tot,
        100 * t["leak"] / tot, t["sram_lo"] * 1e-9, t["sram_hi"] * 1e-9))
    say("%-7s ungated->gated saves %.1f%% of corrected total; avg power (corr-gated) %.1f mW @ %.0f MHz"
        % (k, 100 * (1 - t["cor_gated"] / t["cor_ungated"]),
           t["cor_gated"] * 1e-15 / (NC[k] * T_CLK) * 1e3, 1e-6 / T_CLK))

say("""
PER-MODULE TABLE, per kernel: top 15 leaves by corrected-gated energy
(E in nJ; split %% of module corr-gated: C=comb S=seq-data F=clk-floor T=tree L=leak;
 pJ/busycyc = module energy per ACTIVE (busy2) cycle -- the per-'op' figure)""")
for k in KERNELS:
    rows = sorted(LEAVES, key=lambda m: -RES[k][m]["cor_gated"])[:15]
    say("--- %s (%d cycles) %s" % (k, NC[k], "-" * 70))
    say("%-16s %9s %6s | %8s %18s | %2s/%2s/%2s/%2s/%2s | %8s %7s | %s" % (
        "module", "corrE nJ", "share", "lib nJ", "band nJ", "C", "S", "F", "T", "L",
        "pJ/busycyc", "duty2", "alpha"))
    for m in rows:
        r = RES[k][m]
        tot = r["cor_gated"]
        chip = CHIP[k]["cor_gated"]
        d = MODS[m].get("dynamic")
        duty = (d[k]["duty2"] if d and d.get(k) and "duty2" in d[k] else
                MODS[PARENT_DUTY[m]]["dynamic"][k]["duty2"] if m in PARENT_DUTY else None)
        say("%-16s %9.1f %5.1f%% | %8.1f %8.1f-%8.1f | %2.0f/%2.0f/%2.0f/%2.0f/%2.0f | %8.2f %7s | %.4f" % (
            m, tot * 1e-6, 100 * tot / chip, r["lib_gated"] * 1e-6,
            r["cor_gated_lo"] * 1e-6, r["cor_gated_hi"] * 1e-6,
            100 * r["comb_corr"] / tot, 100 * r["data"] * C_DATA / tot,
            100 * r["floor_g"] * C_FLOOR / tot, 100 * r["tree_g"] * C_TREE / tot,
            100 * r["leak"] / tot,
            (tot / r["busy"] * 1e-3) if r["busy"] else float("nan"),
            ("%.3f" % duty) if duty is not None else "n/a", r["alpha"]))

say("""
SELECTION-RULE DISCRIMINANTS per leaf (MEASURED static + dynamic evidence -> favoured binding)""")
say("%-16s %7s %6s %5s | %6s %7s %7s | %s" % ("module", "comb", "seq", "SCC",
    "duty2*", "wwburst", "meanidl", "verdict tags (hard gates first)"))
for m in LEAVES:
    if m.endswith("__glue"): continue
    s = MODS[m]["static"]; d = MODS[m].get("dynamic")
    dg = d.get("sgemm") if d else None
    say("%-16s %7d %6d %5s | %6s %7s %7s | %s" % (
        m, s["comb"], s["seq"], s.get("regs_in_cycles", "-"),
        ("%.3f" % dg["duty2"]) if dg and "duty2" in dg else "n/a",
        ("%.1f" % dg["work_weighted_burst2"]) if dg and dg.get("work_weighted_burst2") else "-",
        ("%.1f" % dg["mean_idle2"]) if dg and dg.get("mean_idle2") else "-",
        verdict(m)))
say("  (*duty2 shown for sgemm; SCC = regs on reg-to-reg cycles, the QDI hard gate)")

# JSON dump
outj = dict(
    _meta=dict(generated="compose_energy.py", T_clk_ns=4.75,
               coefficients=dict(e_tog_comb_fJ=e_tog_comb, E0_ff_fJ=E0_FF,
                                 S_ff_fJ_per_alpha=S_FF, E_tree_fJ=E_TREE,
                                 C_comb_ALU=C_COMB_ALU, C_floor=C_FLOOR,
                                 C_data=C_DATA, C_tree=C_TREE,
                                 K_central=K_C, K_lo=K_LO, K_window=K_WIN,
                                 F_boundary=F_BOUNDARY, K_ff=K_FF,
                                 leak_comb_W=LEAK_COMB, leak_dff_W=LEAK_DFF,
                                 leak_sram_W_bit=LEAK_SRAM_BIT,
                                 phys_overhead=PHYS_OVH, anchor_alpha_rtl=ALPHA_RTL_A),
               instrument_check=dict(pJ_op=pj_op, target=46.671, err_pct=err),
               units="fJ per kernel run unless noted"),
    chip=CHIP, modules={k: RES[k] for k in KERNELS},
    sram_bits=dict(SRAM_BITS), sram_arrays=dict(SRAM_N))
json.dump(outj, open(D + "/energy_composed.json", "w"), indent=1)
open(D + "/energy_report.txt", "w").write("\n".join(OUTTXT) + "\n")
say("")
say("wrote %s/energy_composed.json + energy_report.txt" % D)
