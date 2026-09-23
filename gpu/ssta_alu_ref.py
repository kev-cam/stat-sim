#!/usr/bin/env python3
"""Design-scale SSTA on the Vortex ALU — numpy reference of the GPU kernel (step 1).

The point of step 1: the reconvergent COHERENT draw. Each cell instance draws its delay
ONCE per lane; arrival propagates through the LEVELIZED DAG reusing that one value, so
reconvergent paths that share an upstream cone automatically share its realization (the
make-or-break rule the chain prototype quantified). One lane = one whole-design coherent
Monte-Carlo sample; the critical arrival = max over all endpoints.

Gate delays use the same NCL in-context model as statsim_ssta.py (AND/OR=th22, XOR=th22+th12,
MUX=th33+th14, NOT=0); per-cell sd = sigma_frac(th23,kvt)*mu. Compared to the analytic
single-critical-path SSTA (statsim_ssta) to expose the reconvergent max-inflation the closed
form cannot produce. This is the reference the CUDA kernel (ssta_alu.cu) must reproduce.
"""
import json, os, sys, math
import numpy as np
sys.path.insert(0, "/usr/local/src/stat-sim")
import statsim_ssta as S
from statsim_delay import DelayModels

sys.setrecursionlimit(400000)   # whole-Vortex critical paths are deep
ALU = "/usr/local/src/mylex/nulex/mapper/alu/work/alu.json"
MODELS = "/usr/local/src/stat-sim/models/ncl_th_delay.json"
NETLIST = sys.argv[sys.argv.index("--netlist") + 1] if "--netlist" in sys.argv else ALU


# gate type ids and per-(type,kvt) mean delay (NCL composite, same as statsim_ssta.gate_delays)
TYPE_ID = {"$_AND_": 0, "$_OR_": 0, "$_XOR_": 1, "$_MUX_": 2, "$_NOT_": 3}
TYPE_SUB = {0: ["th22"], 1: ["th22", "th12"], 2: ["th33", "th14"], 3: []}


def type_mu_table(mj):
    """TYPEMU[tid][k] = mean delay of gate type tid at corner index k (kvt)."""
    C = mj["cells"]; nk = len(mj["kvt"])
    return [[sum(C[c]["mu_ps"][k] for c in TYPE_SUB[tid]) for k in range(nk)] for tid in range(4)]


def build_levelized(mj):
    """Corner-AGNOSTIC graph: stores per-cell gate type; mu is computed per corner later."""
    cells, driver, start_nets, end_nets = S.build(NETLIST)
    comb = []  # (out, [ins], type_id)
    for cname, c in cells.items():
        if c["type"] == "$_DFF_P_":
            continue
        pd = c["port_directions"]; conn = c["connections"]
        outs = [n for p, nets in conn.items() if pd[p] == "output" for n in nets if isinstance(n, int)]
        ins = [n for p, nets in conn.items() if pd[p] == "input" for n in nets if isinstance(n, int)]
        if not outs:
            continue
        comb.append((outs[0], ins, TYPE_ID[c["type"]]))
    nets = set(start_nets) | set(end_nets)
    for o, ins, _ in comb:
        nets.add(o); nets.update(ins)
    nets = sorted(nets)
    idx = {n: i for i, n in enumerate(nets)}
    out_cell = {o: ins for (o, ins, _) in comb}
    level = {}; instk = set()
    def lvl(net):
        if net in start_nets or net not in out_cell:
            return 0
        if net in level: return level[net]
        if net in instk: return 0
        instk.add(net)
        L = 1 + max([lvl(i) for i in out_cell[net] if i in out_cell or i in start_nets] + [0])
        level[net] = L; instk.discard(net); return L
    for o, _, _ in comb: lvl(o)
    order = sorted(comb, key=lambda t: level.get(t[0], 0))
    return dict(cells=cells, driver=driver, start=start_nets, end=end_nets,
                comb=comb, order=order, idx=idx, nets=nets, level=level)


def analytic_critical(G, kvt, mj):
    """The deterministic single critical path + its sigma (statsim_ssta golden)."""
    arrival = S.critical_path(G["cells"], G["driver"], G["start"], kvt, mj)
    best = (0.0, [])
    for net in G["end"]:
        dl, pth = arrival(net)
        if dl > best[0]:
            best = (dl, pth)
    mu_ps, path = best
    sd_ps, depth = S.sigma_of_path(path, kvt, mj)
    return mu_ps, sd_ps, depth


def coherent_mc(G, kvt, mj, n_lanes, rng, rho0=0.0):
    """Coherent per-cell draw. rho0>0 adds nearest-neighbor correlation between a cell's delay
    and its CRITICAL PREDECESSOR (driver of the latest-arriving input) via the MA(1) construction
    x_C = alpha*z_C + beta*z_pred (alpha*beta=rho0, alpha^2+beta^2=1) -- the DAG generalization of
    the chain's predict_ctx correlation; reduces to it exactly on a chain. Zero-delay NOT buffers
    pass their predecessor's noise through so they don't break the coupling."""
    idx = G["idx"]; n_nets = len(G["nets"])
    m = DelayModels(); sf = m.sigma_frac("th23", kvt)
    ki = mj["kvt"].index(kvt); TYPEMU = type_mu_table(mj)
    a = math.sqrt(1 + 2*rho0)/2 + math.sqrt(1 - 2*rho0)/2 if rho0 > 0 else 1.0
    b = math.sqrt(1 + 2*rho0)/2 - math.sqrt(1 - 2*rho0)/2 if rho0 > 0 else 0.0
    arr = np.zeros((n_lanes, n_nets), dtype=np.float32)        # start nets stay 0
    # each net's driver's own iid noise; start nets get fresh noise = the "virtual predecessor"
    znet = rng.standard_normal((n_lanes, n_nets)).astype(np.float32)
    ar = np.arange(n_lanes)
    end_idx = np.array([idx[n] for n in G["end"] if n in idx], dtype=np.int64)
    for out, ins, tid in G["order"]:
        mu_cell = TYPEMU[tid][ki]
        oi = idx[out]
        ini = [idx[i] for i in ins if i in idx]
        if not ini:
            base = np.zeros(n_lanes, dtype=np.float32); zpred = znet[:, oi]  # no pred -> its own fresh
        elif len(ini) == 1:
            base = arr[:, ini[0]]; zpred = znet[:, ini[0]]
        else:
            ains = arr[:, ini]                                 # (L, k)
            am = ains.argmax(1)
            base = ains[ar, am]
            crit_net = np.asarray(ini)[am]                     # per-lane critical input net
            zpred = znet[ar, crit_net]                         # its driver's noise
        if mu_cell > 0.0:
            zc = rng.standard_normal(n_lanes).astype(np.float32)
            x = a * zc + b * zpred                             # unit-var, nn-corr with crit pred
            arr[:, oi] = base + (mu_cell + sf * mu_cell * x)
            znet[:, oi] = zc                                   # store C's own noise for successors
        else:                                                  # zero-delay buffer: pass noise through
            arr[:, oi] = base
            znet[:, oi] = zpred
    return arr[:, end_idx].max(axis=1)


def emit_header(G, mj, refs, rho0, a_mu, a_sd, path):
    """refs: {kvt: (mean, sd, p999)} per-corner numpy reference. Bakes a corner-parameterized
    graph: per-cell gate TYPE, the tiny per-(type,kvt) mean table, and sigma_frac per corner."""
    idx = G["idx"]; n_nets = len(G["nets"])
    a = math.sqrt(1 + 2*rho0)/2 + math.sqrt(1 - 2*rho0)/2 if rho0 > 0 else 1.0
    b = math.sqrt(1 + 2*rho0)/2 - math.sqrt(1 - 2*rho0)/2 if rho0 > 0 else 0.0
    kvts = mj["kvt"]; nk = len(kvts); m = DelayModels()
    TYPEMU = type_mu_table(mj)
    OUT, NIN, IN0, IN1, IN2, TID = [], [], [], [], [], []
    for out, ins, tid in G["order"]:
        ini = [idx[i] for i in ins if i in idx][:3]
        OUT.append(idx[out]); NIN.append(len(ini)); TID.append(tid)
        IN0.append(ini[0] if len(ini) > 0 else 0)
        IN1.append(ini[1] if len(ini) > 1 else 0)
        IN2.append(ini[2] if len(ini) > 2 else 0)
    END = [idx[n] for n in G["end"] if n in idx]
    gatemu = [TYPEMU[t][k] for t in range(4) for k in range(nk)]   # [type*nk + k]
    sfrac = [m.sigma_frac("th23", kv) for kv in kvts]
    rmean = [refs[kv][0] for kv in kvts]; rsd = [refs[kv][1] for kv in kvts]; rp999 = [refs[kv][2] for kv in kvts]
    def ia(name, xs): return "static const int %s[] = {%s};" % (name, ",".join(map(str, xs)))
    def fa(name, xs): return "static const float %s[] = {%s};" % (name, ",".join("%.5ff" % x for x in xs))
    H = ["// AUTO-GENERATED by ssta_alu_ref.py --emit-header -- levelized SSTA graph (corner-parameterized).",
         "#pragma once",
         "#define N_NETS %d" % n_nets, "#define N_CELLS %d" % len(OUT),
         "#define N_END %d" % len(END), "#define NKVT %d" % nk,
         ia("KVT_LIST", kvts),
         "static const float A_MU=%.4ff, A_SD=%.4ff; // analytic single crit path (worst corner)" % (a_mu, a_sd),
         "static const float RHO0=%.4ff, MA_A=%.6ff, MA_B=%.6ff;" % (rho0, a, b),
         ia("CELL_OUT", OUT), ia("CELL_NIN", NIN), ia("CELL_IN0", IN0), ia("CELL_IN1", IN1), ia("CELL_IN2", IN2),
         ia("CELL_TID", TID), fa("GATE_MU", gatemu), fa("SIGMA_FRAC", sfrac), ia("END_IDX", END),
         fa("REF_MEAN", rmean), fa("REF_SD", rsd), fa("REF_P999", rp999)]
    open(path, "w").write("\n".join(H) + "\n")
    print("  wrote %s (N_NETS=%d N_CELLS=%d N_END=%d NKVT=%d)" % (path, n_nets, len(OUT), len(END), nk))


def main():
    n_lanes = int(sys.argv[sys.argv.index("--lanes") + 1]) if "--lanes" in sys.argv else 6000
    mj = json.load(open(MODELS))
    kvts = mj["kvt"]; rho0 = mj.get("inter_stage_correlation", {}).get("rho0", 0.10)
    print("=" * 100)
    print("Design-scale SSTA — INSTANCES x CORNERS yield sweep (numpy reference)  netlist=%s"
          % os.path.basename(NETLIST))
    print("=" * 100)
    G = build_levelized(mj)
    print("  cells=%d comb (of %d), nets=%d, endpoints=%d, depth=%d | %d lanes x %d kvt corners, rho0=%.2f"
          % (len(G["comb"]), len(G["cells"]), len(G["nets"]), len(G["end"]),
             max(G["level"].values()), n_lanes, len(kvts), rho0))
    a_mu_worst, a_sd_worst, _ = analytic_critical(G, max(kvts), mj)
    print("\n  kvt | sigma_frac | analytic 1-path mu | MC mean |  MC sd | clk@50%% | clk@99%% | clk@99.9%% | fmax@99.9%%")
    refs = {}
    for kv in kvts:
        sf = DelayModels().sigma_frac("th23", kv)
        rng = np.random.default_rng(0x5A17)
        crit = coherent_mc(G, kv, mj, n_lanes, rng, rho0=rho0)
        mean, sd = float(crit.mean()), float(crit.std())
        p50, p99, p999 = [float(x) for x in np.percentile(crit, [50, 99, 99.9])]
        a_mu, _, _ = analytic_critical(G, kv, mj)
        refs[kv] = (mean, sd, p999)
        print("   %d  |   %5.2f%%   |     %8.1f ps    | %7.1f | %6.1f | %7.1f | %7.1f | %8.1f  |  %.3f GHz"
              % (kv, sf * 100, a_mu, mean, sd, p50, p99, p999, 1000.0 / p999))
    worst = kvts[-1]
    print("\n  SIGN-OFF (worst mismatch corner kvt=%d): clock @ 99.9%% timing yield = %.1f ps -> fmax = %.3f GHz"
          % (worst, refs[worst][2], 1000.0 / refs[worst][2]))
    print("  Across corners the mean is nearly flat (mismatch is zero-mean) but the yield TAIL widens")
    print("  with sigma_frac: p99.9 - mean grows %.0f -> %.0f ps from kvt=1 to kvt=%d. Each row = a full"
          % (refs[kvts[0]][2] - refs[kvts[0]][0], refs[worst][2] - refs[worst][0], worst))
    print("  MC over instances; the 4 corners run in one batched GPU sweep (the instances x corners regime).")
    json.dump(dict(n_lanes=n_lanes, rho0=rho0, kvts=kvts,
                   per_corner={kv: dict(mean=refs[kv][0], sd=refs[kv][1], p999=refs[kv][2]) for kv in kvts}),
              open("/home/claude/statsim_gpu_proto/alu_ref_result.json", "w"), indent=1)
    if "--emit-header" in sys.argv:
        emit_header(G, mj, refs, rho0, a_mu_worst, a_sd_worst,
                    "/home/claude/statsim_gpu_proto/ssta_alu_data.h")


if __name__ == "__main__":
    import threading
    threading.stack_size(512 * 1024 * 1024)   # deep recursion (whole-Vortex) needs a big C stack
    t = threading.Thread(target=main); t.start(); t.join()
