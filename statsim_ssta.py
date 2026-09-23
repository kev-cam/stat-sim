#!/usr/bin/env python3
"""stat-sim SSTA — cell-level statistical static timing of a composed NCL design,
from a yosys gate netlist (JSON) + the delay-tier cell probability models.

Each logical gate is realized as a dual-rail NCL composite (ncl_logic.sp): its
delay is the critical sub-path through its TH cells (AND/OR=1 TH cell, XOR=th22->
th12, MUX=DIMS th33->collector, INV=free). The register-to-register critical path
is the longest-arrival path through the combinational cones between flip-flops;
its mean is the sum of gate delays and its sigma composes the per-gate mismatch
(sigma_frac) with the validated nearest-neighbor correlation. This gives the
design's clock-period distribution and timing yield under Vt mismatch WITHOUT any
transistor MC -- the point of the delay tier (see DELAY.md), now at ALU scale.

Usage: statsim_ssta.py <netlist.json>
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models", "ncl_th_delay.json")


def gate_delays(models_json, kvt):
    """Per-logical-gate NCL-implementation delay mu (ps) and its constituent-TH
    critical sub-path (for sigma). Uses in-context TH-cell delays where known;
    single-cell mu otherwise (absolute mu is approximate, ~20-40% per-context;
    sigma_frac and the relative reliability are the robust outputs)."""
    C = models_json["cells"]
    def mu(cell): return C[cell]["mu_ps"][kvt - 1]
    # NCL composite critical sub-paths (from ncl_logic.sp / nulex gate lib):
    #  AND2 = th22(H)|th12(L)  -> slower rail th22
    #  OR2  = th12(H)|th22(L)  -> th22
    #  XOR2 = (th22 -> th12) per rail -> th22 + th12 in series
    #  MUX2 = 3-in DIMS: th33 minterm -> OR-collector (~th14-class) in series
    #  NOT  = ncl_inv = rail swap, free
    return {
        "$_AND_": [ "th22" ],
        "$_OR_":  [ "th22" ],
        "$_XOR_": [ "th22", "th12" ],
        "$_MUX_": [ "th33", "th14" ],
        "$_NOT_": [ ],
    }, mu


def build(netpath):
    d = json.load(open(netpath))
    mod = list(d["modules"].values())[0]
    cells = {n: c for n, c in mod["cells"].items() if c["type"] != "$scopeinfo"}
    # net -> driving cell (via that cell's output ports); net -> is a register/PI start
    driver = {}          # net -> cellname (combinational driver)
    start_nets = set()   # nets launched by DFF.Q or primary inputs (arrival 0)
    end_nets = set()     # nets captured by DFF.D or primary outputs
    for n, c in cells.items():
        pd = c["port_directions"]; conn = c["connections"]
        for port, nets in conn.items():
            for net in nets:
                if pd[port] == "output":
                    if c["type"] == "$_DFF_P_":
                        start_nets.add(net)
                    else:
                        driver[net] = n
                elif c["type"] == "$_DFF_P_" and port == "D":
                    end_nets.add(net)
    for pname, p in mod["ports"].items():
        for net in p["bits"]:
            if not isinstance(net, int):  # constants like "0"/"1"
                continue
            if p["direction"] == "input":
                start_nets.add(net)
            else:
                end_nets.add(net)
    return cells, driver, start_nets, end_nets


def critical_path(cells, driver, start_nets, kvt, models_json):
    submap, mu = gate_delays(models_json, kvt)
    def gate_mu(cell):
        return sum(mu(c) for c in submap.get(cells[cell]["type"], []))
    # arrival(net) memoized longest path; returns (delay, path-of-cells)
    arr = {}
    instack = set()
    def arrival(net):
        if net in start_nets or net not in driver:
            return 0.0, []
        if net in arr:
            return arr[net]
        if net in instack:      # combinational loop guard (shouldn't happen R2R)
            return 0.0, []
        instack.add(net)
        cell = driver[net]; conn = cells[cell]["connections"]; pd = cells[cell]["port_directions"]
        best_in, best_path = 0.0, []
        for port, nets in conn.items():
            if pd[port] != "input":
                continue
            for inet in nets:
                if not isinstance(inet, int):
                    continue
                din, dpath = arrival(inet)
                if din >= best_in:
                    best_in, best_path = din, dpath
        gm = gate_mu(cell)
        res = (best_in + gm, best_path + [(cell, cells[cell]["type"], gm)])
        arr[net] = res; instack.discard(net)
        return res
    return arrival


def sigma_of_path(path, kvt, models_json):
    """sigma along a critical path: per-gate sigma = sigma_frac(kvt)*gate_mu, with
    nearest-neighbor correlation rho0 (validated). Skips zero-delay (INV) gates."""
    sf = models_json["cells"]["th23"]["sd_ps"][kvt - 1] / models_json["cells"]["th23"]["mu_ps"][kvt - 1]
    rho0 = models_json.get("inter_stage_correlation", {}).get("rho0", 0.0)
    sig = [sf * gm for (_c, _t, gm) in path if gm > 0]
    var = sum(x * x for x in sig) + 2 * rho0 * sum(sig[i] * sig[i + 1] for i in range(len(sig) - 1))
    return math.sqrt(var), len(sig)


def main(netpath):
    mj = json.load(open(MODELS))
    cells, driver, start_nets, end_nets = build(netpath)
    from collections import Counter
    print("Netlist: %s" % os.path.basename(netpath))
    print("  cells: %s" % dict(Counter(c["type"] for c in cells.values())))
    print("  start points (DFF.Q + PI): %d ; end points (DFF.D + PO): %d\n"
          % (len(start_nets), len(end_nets)))
    print("=== ALU register-to-register critical path (cell-level SSTA) ===")
    print(" kvt |  crit mu (ns) | logic depth | crit sd (ps) | sigma_frac | worst mu+3sd (ns)")
    depth1 = None
    for kvt in mj["kvt"]:
        arrival = critical_path(cells, driver, start_nets, kvt, mj)
        best = (0.0, [])
        for net in end_nets:
            dl, pth = arrival(net)
            if dl > best[0]:
                best = (dl, pth)
        mu_ps, path = best
        sd_ps, depth = sigma_of_path(path, kvt, mj)
        depth1 = depth
        print("  %d  |    %6.3f     |    %4d     |   %6.1f    |   %5.2f%%   |    %6.3f"
              % (kvt, mu_ps / 1000, depth, sd_ps, sd_ps / mu_ps * 100, (mu_ps + 3 * sd_ps) / 1000))
    print("\n  critical path is %d gate-stages deep. mu is approximate (per-gate in-context" % depth1)
    print("  timing not fully characterized); sigma_frac + relative timing yield are the robust")
    print("  outputs. This is a cell-level SSTA of a ~24k-TH-cell Vortex ALU with NO SPICE.")


if __name__ == "__main__":
    main(sys.argv[1])
