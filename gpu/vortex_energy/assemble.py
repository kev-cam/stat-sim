#!/usr/bin/env python3
"""Assemble the per-module dataset for the Vortex whole-design event-driven
energy composition: join the STATIC half (yosys-flattened netlist islands,
/home/claude/vortex_static_char + regenerated vortex_flat.json) with the
DYNAMIC half (whole-design VCD activity, /home/claude/vortex_activity/
{hello,saxpy,sgemm}.tsv, D2 threshold columns) into ONE JSON:

    /home/claude/vortex_energy/permodule.json

Everything static is re-derived from the flat netlist JSON here (not copied
from text reports) and then CHECKED against the numbers in
consolidated_vector.txt / flat_islands.txt; everything dynamic is parsed from
the TSVs and CHECKED against the known chip-level facts. Join failures are
reported, never silently dropped.

Provenance labels used in the output: MEASURED / DERIVED / ASSUMED.
"""
import json, sys, collections, importlib.util, os, math, hashlib

SP = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad"
FLAT_JSON = SP + "/vxstat/vortex_flat.json"      # regenerated today, md5-identical to this morning's
ACT_DIR = "/home/claude/vortex_activity"
OUT = "/home/claude/vortex_energy/permodule.json"

# ---------------------------------------------------------------- static half
spec = importlib.util.spec_from_file_location(
    "flat_islands", "/home/claude/vortex_static_char/flat_islands.py")
fi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fi)          # gives us norm, cell_path, profile

CO = "tb.dut.clusters[0].cluster.sockets[0].socket.cores[0].core"
E = CO + ".execute"
S = "tb.dut.clusters[0].cluster.sockets[0].socket"
P = "clusters.cluster.sockets.socket."

# name, static prefix (normalized flatten path), VCD scope (None = untraced), parent
ISLANDS = [
    ("whole_chip",   "",                                   "tb.dut",                          None),
    ("core",         P + "cores.core",                     CO,                                "whole_chip"),
    ("execute",      P + "cores.core.execute",             E,                                 "core"),
    ("alu_unit",     P + "cores.core.execute.alu_unit",    E + ".alu_unit",                   "execute"),
    ("alu_int",      P + "cores.core.execute.alu_unit.alu_int", E + ".alu_unit.genblk1[0].alu_int", "alu_unit"),
    ("muldiv",       P + "cores.core.execute.alu_unit.muldiv",  E + ".alu_unit.genblk1[0].muldiv_unit", "alu_unit"),
    ("fpu_unit",     P + "cores.core.execute.fpu_unit",    E + ".fpu_unit",                   "execute"),
    ("lsu_unit",     P + "cores.core.execute.lsu_unit",    E + ".lsu_unit",                   "execute"),
    ("sfu_unit",     P + "cores.core.execute.sfu_unit",    E + ".sfu_unit",                   "execute"),
    ("issue",        P + "cores.core.issue",               CO + ".issue",                     "core"),
    ("schedule",     P + "cores.core.schedule",            CO + ".schedule",                  "core"),
    ("fetch",        P + "cores.core.fetch",               CO + ".fetch",                     "core"),
    ("decode",       P + "cores.core.decode",              CO + ".decode",                    "core"),
    ("commit",       P + "cores.core.commit",              CO + ".commit",                    "core"),
    ("lmem_unit",    P + "cores.core.lmem_unit",           CO + ".lmem_unit",                 "core"),
    ("mem_coalescer",P + "cores.core.mem_coalescer",       None,                              "core"),
    ("dcache",       P + "dcache",                         S + ".dcache",                     "whole_chip"),
    ("icache",       P + "icache",                         S + ".icache",                     "whole_chip"),
    ("mem_arb",      P + "mem_arb",                        S + ".mem_arb",                    "whole_chip"),
    ("l2",           "clusters.cluster.l2cache",           "tb.dut.clusters[0].cluster.l2cache", "whole_chip"),
    ("l3",           "l3cache",                            "tb.dut.l3cache",                  "whole_chip"),
]

# cut_bits at each island's own hierarchy depth, MEASURED by boundary.py on
# vortex_hier.json (values as consolidated in consolidate.py ROWS; '-' = not computed)
CUT_BITS = {"whole_chip": 1183, "core": 1928, "execute": 3764, "issue": 2997,
            "commit": 1091, "lmem_unit": 948, "mem_coalescer": 739,
            "dcache": 1924, "icache": 1254, "mem_arb": 1845, "l2": 1241, "l3": 1241}

def scc_regs(cells, sel_names):
    """Deterministic replacement for profile()'s regs-in-cycles count.

    flat_islands.py marks cycle members during a DFS whose visit order iterates
    Python sets -> the count varies with PYTHONHASHSEED (2694 vs 2668 for the
    whole chip). The well-defined quantity is: registers lying on some
    register-to-register dependency cycle = members of non-trivial SCCs (plus
    self-loops) of the reg graph. Computed here with iterative Tarjan.
    Graph construction is identical to profile(): edges r -> regs feeding r's D
    through combinational cells only (register Q outputs are boundaries)."""
    sel = {cn: cells[cn] for cn in sel_names}
    drv, seq = {}, {}
    for cn, c in sel.items():
        t = c["type"]
        if t.startswith(fi.SEQ_PREFIXES):
            seq[cn] = c
        elif not t.startswith(fi.MEM_PREFIXES):
            for b in c["connections"].get("Y", []):
                if isinstance(b, int): drv[b] = cn
    reg_of_q = {}
    for cn, c in seq.items():
        for b in c["connections"].get("Q", []):
            if isinstance(b, int): reg_of_q[b] = cn
    def deps(dn):
        seen, st, rs = set(), list(dn), set()
        while st:
            n = st.pop()
            if not isinstance(n, int): continue
            if n in reg_of_q: rs.add(reg_of_q[n]); continue
            if n in seen: continue
            seen.add(n)
            cn = drv.get(n)
            if cn is None: continue
            for pin, cc in sel[cn]["connections"].items():
                if pin not in fi.OUT_PINS: st.extend(cc)
        return rs
    D = {r: sorted(deps([b for b in c["connections"].get("D", []) if isinstance(b, int)]))
         for r, c in seq.items()}
    # iterative Tarjan
    index, low, onstk, stk, idx, out = {}, {}, set(), [], [0], []
    for root in sorted(D):
        if root in index: continue
        work = [(root, iter(D[root]))]
        index[root] = low[root] = idx[0]; idx[0] += 1
        stk.append(root); onstk.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = idx[0]; idx[0] += 1
                    stk.append(w); onstk.add(w)
                    work.append((w, iter(D[w]))); advanced = True; break
                elif w in onstk:
                    low[v] = min(low[v], index[w])
            if advanced: continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stk.pop(); onstk.discard(w); comp.append(w)
                    if w == v: break
                out.append(comp)
    incyc = set()
    for comp in out:
        if len(comp) > 1: incyc.update(comp)
    for r in D:
        if r in D[r]: incyc.add(r)
    return len(incyc)


# expected static vector (consolidated_vector.txt / flat_islands.txt) for the
# assembly-bug check: (comb, seq, mem, mux, D, regs_in_cycles)
EXPECT_STATIC = {
    "whole_chip": (291608, 35004, 90, 126649, 148, 2694),
    "core":       (227335, 22161, 60,  72293, 148, 2149),
    "execute":    (182473, 14862, 28,  44597, 148,  776),
    "alu_unit":   ( 45704,  2408,  0,   4485,  46,  144),
    "alu_int":    (  4145,   247,  0,   1544,  19,    0),
    "muldiv":     ( 40421,  1809,  0,   1826,  46,  141),
    "fpu_unit":   (126333,  8732, 25,  33623, 148,  521),
    "lsu_unit":   (  5259,  2051,  1,   2874,  28,   25),
    "sfu_unit":   (  5167,  1667,  2,   3612,  24,   82),
    "issue":      ( 16777,  4240,  6,   8839,  21,  742),
    "schedule":   (  5740,   189,  5,   3544,  32,   73),
    "fetch":      (  1700,    68,  0,   1156,  21,    1),
    "decode":     (  1021,     0,  1,     92,  21,    0),
    "commit":     (  3196,   160,  1,   2751,  13,    3),
    "lmem_unit":  (  6917,  2042,  4,   6274,  17,   42),
    "mem_coalescer": (4371,   232,  0,   2475,  21,  196),
    "dcache":     ( 38516,  8233, 24,  30429,  27,  411),
    "icache":     (  2706,  1290,  6,   1011,  27,  101),
    "mem_arb":    ( 18058,  3315,  0,  17997,  10,    9),
    "l2":         (  4909,     0,  0,   4906,  10,    0),
    "l3":         (     7,     0,  0,      6,   2,    0),
}

print("### loading flat netlist %s" % FLAT_JSON)
mods = json.load(open(FLAT_JSON))["modules"]
m = mods["Vortex"]
allcells = m["cells"]
nscopeinfo = sum(1 for v in allcells.values() if v["type"] == "$scopeinfo")
cells = {k: v for k, v in allcells.items() if v["type"] != "$scopeinfo"}
print("### cells: %d real + %d $scopeinfo = %d raw" % (len(cells), nscopeinfo, len(allcells)))

# --- attribution, exactly as flat_islands.main() ---
paths = {cn: fi.cell_path(cn) for cn in cells}
named = sum(1 for p in paths.values() if p)
bitpath = {}
for nname, nn in m.get("netnames", {}).items():
    if nname.startswith("$") or "." not in nname:
        continue
    p = fi.norm(nname.rsplit(".", 1)[0])
    if p:
        for b in nn["bits"]:
            if isinstance(b, int) and b not in bitpath:
                bitpath[b] = p

def lcp(ps):
    if not ps: return None
    sp = [q.split(".") for q in ps]; out = []
    for i in range(min(len(s) for s in sp)):
        t = sp[0][i]
        if all(s[i] == t for s in sp): out.append(t)
        else: break
    return ".".join(out) if out else None

todo = [cn for cn, p in paths.items() if not p]
for cn in todo:
    ps = {bitpath[b] for pin, cc in cells[cn]["connections"].items() for b in cc
          if isinstance(b, int) and b in bitpath}
    a = lcp(ps)
    if a: paths[cn] = a
netcells = collections.defaultdict(list)
for cn, c in cells.items():
    for pin, cc in c["connections"].items():
        for b in cc:
            if isinstance(b, int): netcells[b].append(cn)
for _ in range(10):
    rest, prog = [], 0
    for cn in [c for c in todo if not paths[c]]:
        v = collections.Counter()
        for pin, cc in cells[cn]["connections"].items():
            for b in cc:
                if isinstance(b, int):
                    for o in netcells[b]:
                        if paths.get(o): v[paths[o]] += 1
        if v: paths[cn] = v.most_common(1)[0][0]; prog += 1
        else: rest.append(cn)
    if not prog: break
unattr = sum(1 for p in paths.values() if not p)
print("### attribution: %d flatten-named, %d fallback, %d unattributed" %
      (named, len(cells) - named, unattr))

byprefix = collections.defaultdict(list)
for cn, p in paths.items():
    byprefix[p or "<UNATTRIBUTED>"].append(cn)

static = {}
for name, pref, scope, parent in ISLANDS:
    sel = [cn for p, lst in byprefix.items() if p.startswith(pref) for cn in lst] if pref \
          else list(cells)
    r = fi.profile(cells, sel)
    r["ncyc_scc"] = scc_regs(cells, sel)
    h = r["hist"]; tot = sum(h.values())
    small = sum(n for n in h.values() if n <= 4)
    mid = sum(n for n in h.values() if 4 < n < 32)
    big = sum(n for n in h.values() if n >= 32)
    static[name] = dict(
        comb=r["ncomb"], seq=r["nseq"], mem=r["nmem"], mux=r["mux"],
        mux_pct=round(100.0 * r["mux"] / r["ncomb"], 2) if r["ncomb"] else 0.0,
        depth_D=r["D"],
        W_eff=round(r["ncomb"] / r["D"], 1) if r["D"] else 0.0,
        seq_frac_pct=round(100.0 * r["nseq"] / (r["ncomb"] + r["nseq"]), 2) if r["ncomb"] + r["nseq"] else 0.0,
        reg_graph=("CYCLIC" if r["cyclic"] else "FEED_FORWARD"),
        regs_in_cycles=r["ncyc_scc"],   # deterministic SCC count (see check below)
        regs_in_cycles_dfsmark=r["ncyc"],  # flat_islands.py's order-dependent marker count
        cyc_frac_pct=round(100.0 * r["ncyc_scc"] / r["nseq"], 2) if r["nseq"] else 0.0,
        max_reg_stage=r["maxstage"],
        comb_loop_cells=r["loops"],
        bank_profile=[h.get(i, 0) for i in range(r["D"])],
        qal_fill=dict(n_le4=small, n_5_31=mid, n_ge32=big),
        mix=r["mix"],
        cut_bits=CUT_BITS.get(name),
    )

# --- assembly-bug check: re-derived static vs consolidated_vector.txt ---
# comb/seq/mem/mux/D must match EXACTLY. regs_in_cycles is compared informationally:
# consolidated_vector's numbers came from flat_islands.py's DFS cycle-marking, whose
# count depends on set-iteration order (PYTHONHASHSEED) -- the SCC count emitted here
# is the well-defined version and must be >= within a few % of the DFS-marker number.
fail, cycnote = [], []
for name, exp in EXPECT_STATIC.items():
    s = static[name]
    got = (s["comb"], s["seq"], s["mem"], s["mux"], s["depth_D"])
    if got != exp[:5]: fail.append((name, exp[:5], got))
    if s["regs_in_cycles"] != exp[5]:
        cycnote.append("%s scc=%d vs dfs-mark=%d (consolidated) / %d (this run)"
                       % (name, s["regs_in_cycles"], exp[5], s["regs_in_cycles_dfsmark"]))
print("### static re-derivation vs consolidated_vector.txt (comb/seq/mem/mux/D): %s" %
      ("ALL %d ISLANDS MATCH EXACTLY" % len(EXPECT_STATIC) if not fail else "MISMATCH %r" % fail))
for n in cycnote:
    print("### [note] regs_in_cycles: " + n)
if fail: sys.exit("static mismatch -- refusing to emit")

# bank_profile must sum to comb
for name, s in static.items():
    assert sum(s["bank_profile"]) == s["comb"], name

# ---------------------------------------------------------------- dynamic half
def load_act(path):
    rows = {}; nc = None
    for line in open(path):
        if line.startswith("# ncycles"): nc = int(line.split("\t")[1]); continue
        if line.startswith("path\t"): continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 23: continue
        rows[f[0]] = f
    return nc, rows

def load_w(path):
    w = {}
    for line in open(path):
        if line.startswith("path\t"): continue
        f = line.rstrip("\n").split("\t")
        w[f[0]] = dict(nvars=int(f[1]), sumw=int(f[2]), maxw=int(f[3]),
                       mean_w=float(f[4]), bw_mean_w=float(f[5]))
    return w

def edges(b):
    if b < 16: return b + 1, b + 1
    lo, hi = 17, 32; k = 16
    while k < b: lo, hi = hi + 1, hi * 2; k += 1
    return lo, hi

def ww_burst(bhist, maxburst):
    """Work-weighted mean burst length: sum(l^2 n)/sum(l n) over the log-binned
    histogram, bin representative = (lo + min(hi, maxburst))/2. DERIVED -- a
    binning convention; reproduces the campaign chip numbers 10.3/13.4/31.0 as
    10.25/13.46/31.59 (sgemm 2% high vs quoted; raw hist is in the JSON)."""
    num = den = 0.0
    for b, n in enumerate(bhist):
        if not n: continue
        lo, hi = edges(b)
        r = (lo + min(hi, maxburst)) / 2.0
        num += r * r * n; den += r * n
    return round(num / den, 2) if den else 0.0

BASE_KERNELS = ["hello", "saxpy", "sgemm"]          # the original 3 (checks pinned)
NEW_KERNELS = ["fpsat_fma", "fpsat_div"]            # 2026-09-25 FP-saturation runs
KERNELS = BASE_KERNELS + NEW_KERNELS
ACT, NC = {}, {}
for k in KERNELS:
    NC[k], ACT[k] = load_act(os.path.join(ACT_DIR, k + ".tsv"))
W = load_w(os.path.join(ACT_DIR, "widths.tsv"))

def dyn(scope, k):
    f = ACT[k].get(scope)
    if f is None: return None
    nc = NC[k]
    nbits = int(f[2]); tog = int(f[3]); busy1 = int(f[4])
    thresh = int(f[13]); busy2 = int(f[14]); nb2 = int(f[15]); bsum2 = int(f[16])
    mxb2 = int(f[17]); nidle2 = int(f[18]); isum2 = int(f[19]); mxi2 = int(f[20])
    bh2 = [int(x) for x in f[21].split(",")]
    ih2 = [int(x) for x in f[22].split(",")]
    assert sum(bh2) == nb2 and sum(ih2) == nidle2, scope
    return dict(
        nbits=nbits,                       # traced bits in subtree = alpha denominator (MEASURED)
        toggles=tog,                       # MEASURED (per-bit toggles summed over subtree)
        alpha=round(tog / (nbits * nc), 6) if nbits else 0.0,
        alpha_on_busy2=round(tog / (nbits * busy2), 6) if nbits and busy2 else 0.0,
        duty2=round(busy2 / nc, 4), busy2_cycles=busy2, thresh2=thresh,
        duty1=round(busy1 / nc, 4),        # D1 kept for reference only (unusable for duty)
        nbursts2=nb2, mean_burst2=round(bsum2 / nb2, 2) if nb2 else 0.0,
        work_weighted_burst2=ww_burst(bh2, mxb2), max_burst2=mxb2,
        burst_hist2=bh2,
        nidle2=nidle2, mean_idle2=round(isum2 / nidle2, 2) if nidle2 else 0.0,
        max_idle2=mxi2, idle_hist2=ih2, idle_cycles2=nc - busy2,
    )

# nbits must be identical across kernels (same traced design)
for name, pref, scope, parent in ISLANDS:
    if scope is None: continue
    nb = {k: int(ACT[k][scope][2]) for k in KERNELS}
    assert len(set(nb.values())) == 1, (name, nb)

# ---------------------------------------------------------------- join + emit
children = collections.defaultdict(list)
for name, pref, scope, parent in ISLANDS:
    if parent: children[parent].append(name)

modules = {}
join_failures = []
for name, pref, scope, parent in ISLANDS:
    entry = dict(
        hierarchy=dict(parent=parent, children=children.get(name, [])),
        static=dict(static[name],
                    source="MEASURED: yosys-flattened netlist of "
                           "/usr/local/src/rtlmeter/designs/Vortex/src (regenerated+md5-verified today)"),
        vcd_scope=scope,
    )
    if scope is None:
        entry["dynamic"] = None
        join_failures.append(dict(
            module=name, kind="STATIC_ONLY",
            reason="VX_mem_coalescer.sv is wrapped in `TRACING_OFF (VX_platform.vh:54) -> "
                   "its module scope is absent from the whole-design VCD; only its boundary "
                   "nets are traced, and they live under core.genblk1[0] (not a coalescer scope). "
                   "Static island = 4371 comb / 232 seq is real; dynamic must be bounded from "
                   "the lsu_unit/dcache interface activity around it."))
    else:
        entry["dynamic"] = {k: dyn(scope, k) for k in KERNELS}
        entry["widths"] = W.get(scope)
    modules[name] = entry

# glue pseudo-modules (parent minus children), static exact, dynamic by
# subtraction of additive fields only (toggles, nbits); duty/burst NOT additive
for parent in ("whole_chip", "core", "execute", "alu_unit"):
    ch = children[parent]
    g = dict(comb=static[parent]["comb"] - sum(static[c]["comb"] for c in ch),
             seq=static[parent]["seq"] - sum(static[c]["seq"] for c in ch),
             mem=static[parent]["mem"] - sum(static[c]["mem"] for c in ch))
    dynsub = {}
    for k in KERNELS:
        pd = modules[parent]["dynamic"][k]
        cds = [modules[c]["dynamic"][k] for c in ch if modules[c]["dynamic"]]
        dynsub[k] = dict(
            nbits=pd["nbits"] - sum(d["nbits"] for d in cds),
            toggles=pd["toggles"] - sum(d["toggles"] for d in cds),
            note="DERIVED by subtraction; includes untraced-module boundary nets and "
                 "interface scopes at this level; duty/burst not derivable")
        dynsub[k]["alpha"] = round(dynsub[k]["toggles"] / (dynsub[k]["nbits"] * NC[k]), 6) \
            if dynsub[k]["nbits"] > 0 else None
    modules[parent + "__glue"] = dict(
        hierarchy=dict(parent=parent, children=[]),
        static=dict(g, source="DERIVED: parent minus named children (exact at cell level)"),
        vcd_scope=None, dynamic=dynsub)

# dynamic-only scopes worth flagging (in report.py's SEL but no static island)
join_failures.append(dict(
    module="dcr_data", kind="DYNAMIC_ONLY",
    vcd_scope=CO + ".dcr_data",
    reason="traced scope (190 bits) with no static island of its own; its cells are inside "
           "the CORE island (core glue). Not emitted as a module."))

# ---------------------------------------------------------------- sanity checks
print()
print("=" * 100)
print("SANITY CHECKS")
print("=" * 100)
ok_all = True

# (1) chip totals reproduce known duty/alpha (BASE pinned to campaign facts;
#     NEW pinned to the kernel agent's independently-computed rep_fpsat.txt)
EXP = dict(hello=(0.307, 0.0042), saxpy=(0.643, 0.0080), sgemm=(0.793, 0.0094),
           fpsat_fma=(0.979, 0.01245), fpsat_div=(0.783, 0.01841))
for k in KERNELS:
    d = modules["whole_chip"]["dynamic"][k]
    duty, alpha = d["duty2"], d["alpha"]
    e = EXP[k]
    ok = abs(duty - e[0]) < 0.0006 and abs(alpha - e[1]) < 0.00006
    ok_all &= ok
    print("[%s] chip %-9s: duty2=%.4f (expect %.3f)  alpha=%.5f (expect %.5f)  ncycles=%d"
          % ("OK" if ok else "FAIL", k, duty, e[0], alpha, e[1], NC[k]))

# (2) work-weighted burst vs quoted 10.3/13.4/31.0 (BASE only; NEW informational)
EXP_WW = dict(hello=10.3, saxpy=13.4, sgemm=31.0)
for k in KERNELS:
    ww = modules["whole_chip"]["dynamic"][k]["work_weighted_burst2"]
    q = ("(campaign quote %.1f)" % EXP_WW[k]) if k in EXP_WW else "(new kernel, no prior quote)"
    print("[note] chip %-9s work-weighted burst (capped-midpoint bins) = %.2f  %s" % (k, ww, q))

# (3) cell totals
s = static["whole_chip"]
ok = (s["comb"], s["seq"], s["mem"]) == (291608, 35004, 90) and \
     s["comb"] + s["seq"] + s["mem"] == 326702
ok_all &= ok
print("[%s] whole chip cells: comb=%d seq=%d mem=%d  total=%d (+%d $scopeinfo)"
      % ("OK" if ok else "FAIL", s["comb"], s["seq"], s["mem"],
         s["comb"] + s["seq"] + s["mem"], nscopeinfo))

# (4) disjoint partition covers the chip
top = ["core", "dcache", "icache", "mem_arb", "l2", "l3"]
for cls in ("comb", "seq", "mem"):
    tot = sum(static[t][cls] for t in top) + modules["whole_chip__glue"]["static"][cls]
    ok = tot == static["whole_chip"][cls]
    ok_all &= ok
    print("[%s] partition sum %-4s: %d == chip %d (glue %d)"
          % ("OK" if ok else "FAIL", cls, tot, static["whole_chip"][cls],
             modules["whole_chip__glue"]["static"][cls]))

# (5) FPU duty by kernel (the headline block); NEW kernels pinned to rep_fpsat.txt
fd = [modules["fpu_unit"]["dynamic"][k]["duty2"] for k in BASE_KERNELS]
ok = abs(fd[0] - 0.000) < 0.001 and abs(fd[1] - 0.032) < 0.001 and abs(fd[2] - 0.235) < 0.001
ok_all &= ok
print("[%s] fpu_unit duty2 h/s/g = %.3f/%.3f/%.3f (expect .000/.032/.235)"
      % ("OK" if ok else "FAIL", *fd))
fn = [modules["fpu_unit"]["dynamic"][k]["duty2"] for k in NEW_KERNELS]
ok = abs(fn[0] - 0.9781) < 0.001 and abs(fn[1] - 0.7806) < 0.001
ok_all &= ok
print("[%s] fpu_unit duty2 fpsat_fma/fpsat_div = %.4f/%.4f (expect .9781/.7806 per rep_fpsat.txt)"
      % ("OK" if ok else "FAIL", *fn))

# (6) the 63-of-431 dark-silicon fact (pinned over the BASE 3 kernels, as quoted)
big_scopes = [p for p in ACT["hello"] if int(ACT["hello"][p][2]) >= 500]
never = [p for p in big_scopes
         if all(int(ACT[k][p][14]) / NC[k] < 0.001 for k in BASE_KERNELS if p in ACT[k])]
print("[%s] scopes >=500 bits: %d, never duty2>=0.001 in base 3 kernels: %d (expect 431 / 63)"
      % ("OK" if (len(big_scopes) == 431 and len(never) == 63) else "FAIL",
         len(big_scopes), len(never)))
ok_all &= (len(big_scopes) == 431 and len(never) == 63)
never5 = [p for p in big_scopes
          if all(int(ACT[k][p][14]) / NC[k] < 0.001 for k in KERNELS if p in ACT[k])]
print("[note] with fpsat_fma+fpsat_div added, never-active >=500-bit scopes: %d (was 63)"
      % len(never5))

# (7) join failures
print("[note] join failures: %d" % len(join_failures))
for jf in join_failures:
    print("       - %s (%s)" % (jf["module"], jf["kind"]))

# ---------------------------------------------------------------- write
meta = dict(
    generated="2026-09-25 by vortex_energy/assemble.py",
    design="Vortex 'mini' (1 cluster / 1 core / 4 warps / 4 threads), rtlmeter configurations.mini",
    provenance=dict(
        rtl_source="/usr/local/src/rtlmeter/designs/Vortex/src (rtlmeter git e528dc208d2701b4"
                    "ba7881dd1ef89748ba714d3b, clean; descriptor.yaml pins vortex "
                    "e80ee2c81909ecf118fa1b8842613af4b26ab4a1, fpnew 79e4531390)",
        static_half="yosys 0.58 flat netlist, regenerated today from that source by "
                    "reproduce.sh; stat_flat.txt and vortex_flat.json byte/md5-identical "
                    "to the originals behind consolidated_vector.txt "
                    "(md5 2d5326cc902490e463c1fe5db88cb4e4)",
        dynamic_half="whole-design VCD from the SAME source tree: Verilator build "
                     "work_qal_vortex_tr/Vortex/mini/compile-0 whose verilogSourceFiles/ are "
                     "symlinks into designs/Vortex/src (tb.sv = tb.sv.patched, md5 "
                     "64d05869f9cc158267fe3cce8034dce4); parsed by vcdact.c (validated 3 ways)",
        same_tree=True,
    ),
    kernels={k: dict(ncycles=NC[k], tsv=os.path.join(ACT_DIR, k + ".tsv")) for k in KERNELS},
    conventions=dict(
        busy_definition="D2: cycle is busy if >= max(2, 0.5% of subtree traced bits) toggle "
                        "(TSV *2 columns). D1 kept as duty1 for reference only.",
        alpha="toggles / (nbits * ncycles); nbits = traced bits in the VCD subtree "
              "(interface scopes included; Verilator also traces parameters as constant "
              "vars, so nbits slightly overstates togglable bits -> alpha is a lower bound "
              "at RTL-net level; chip facts .0042/.0080/.0094 use this same denominator)",
        hist_bins="bins 0..15 = run length 1..16 exactly; bin b>=16 covers "
                  "[2^(b-12)+1 .. 2^(b-11)] i.e. 17-32, 33-64, ... (vcdact.c lg2bin)",
        work_weighted_burst="sum(l^2 n)/sum(l n), bin rep=(lo+min(hi,max_burst))/2 -- DERIVED "
                            "convention; full hist carried so composer may re-derive",
        bank_profile="comb cells per topological logic level (bank_profile[i] = level i), "
                     "sums to comb; QAL banks may SPAN levels -- use partition DP, never "
                     "per-level population directly",
        rtl_to_gate_alpha="ASSUMED/UNRESOLVED: RTL-net alpha is a subset proxy for gate-output "
                          "alpha. 35 utility modules (VX_stream_arb, VX_fifo_queue, VX_multiplier, "
                          "VX_serial_div, VX_dp_ram, arbiters, ...) are `TRACING_OFF -> their "
                          "internal nets are NOT in the VCD at all; their activity is only seen at "
                          "boundaries. Composer MUST carry a multiplier band (calibrate on nulex "
                          "ALU where both RTL VCD and gate-level power exist).",
    ),
    hierarchy_note="Module entries are NESTED (whole_chip > core > execute > alu_unit > "
                   "{alu_int,muldiv}); use the disjoint partitions + __glue entries to "
                   "compose without double counting.",
    disjoint_partitions=dict(
        whole_chip=["core", "dcache", "icache", "mem_arb", "l2", "l3", "whole_chip__glue"],
        core=["execute", "issue", "schedule", "fetch", "decode", "commit", "lmem_unit",
              "mem_coalescer", "core__glue"],
        execute=["alu_unit", "fpu_unit", "lsu_unit", "sfu_unit", "execute__glue"],
        alu_unit=["alu_int", "muldiv", "alu_unit__glue"],
    ),
)

out = dict(_meta=meta, _join_failures=join_failures, modules=modules)
with open(OUT, "w") as f:
    json.dump(out, f, indent=1)
print()
print("### wrote %s (%.1f KB), %d module entries" %
      (OUT, os.path.getsize(OUT) / 1024.0, len(modules)))
print("### OVERALL: %s" % ("ALL CHECKS PASS" if ok_all else "SOME CHECKS FAILED"))
sys.exit(0 if ok_all else 1)
