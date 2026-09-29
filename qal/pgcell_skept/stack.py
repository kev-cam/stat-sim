#!/usr/bin/env python3
"""BINDING pull-up stack depth, computed from the PDK spice + the PDK liberty.

For every input vector that drives the cell output HIGH, find the SHORTEST
CONDUCTING pMOS path from VDD to the output node (pMOS conducts when its gate is
LOW).  The binding depth is the MAXIMUM of that over all such vectors -- i.e. the
worst case the cell is ever asked to pull up through.  Taking a plain shortest
path over all nodes (my first attempt) reports 1 for o21ai and is wrong: it finds
the B1 pMOS, which is OFF in exactly the vector that matters."""
import collections, itertools, json, re, sys
from libfun import cells, lib_to_verilog

PDK = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/"
       "sg13g2_stdcell.spice")


def netlist():
    cur, devs, ports = None, {}, {}
    for ln in open(PDK):
        s = ln.strip()
        if s.lower().startswith('.subckt'):
            cur = s.split()[1]; devs[cur] = []; ports[cur] = s.split()[2:]
        elif s.lower().startswith('.ends'):
            cur = None
        elif cur and s and s[0].upper() == 'X':
            p = s.split()
            devs[cur].append((p[0], p[1], p[2], p[3], 'p' if 'pmos' in s else 'n'))
    return devs, ports


def ev(expr, env):
    v = lib_to_verilog(expr)
    py = v.replace('~', ' not ').replace('&', ' and ').replace('|', ' or ')
    py = re.sub(r'\^', ' != ', py)
    return int(bool(eval(py, {}, {k: bool(x) for k, x in env.items()})))


def binding(cell, devs, C):
    order, pins = C[cell]
    ins = [p for p in order if pins[p][1] is None]
    outs = [p for p in order if pins[p][1] is not None]
    if not outs:
        return None
    out = outs[0]
    expr = pins[out][1]
    ps = [d for d in devs[cell] if d[4] == 'p']
    worst, worstvec = 0, None
    for bits in itertools.product((0, 1), repeat=len(ins)):
        env = dict(zip(ins, bits))
        if ev(expr, env) != 1:
            continue
        adj = collections.defaultdict(list)
        for nm, d, g, s, _ in ps:
            gv = env.get(g, None)
            if gv is None:                 # gate on an internal node
                gv = 'int'
            if gv == 0:                    # pMOS conducts on a LOW gate
                adj[d].append(s); adj[s].append(d)
            elif gv == 'int':
                # internal-node gate: unknown, treat as conducting (generous to
                # the cell, i.e. it can only UNDER-report depth)
                adj[d].append(s); adj[s].append(d)
        dist = {'VDD': 0}
        q = collections.deque(['VDD'])
        while q:
            n = q.popleft()
            for m in adj[n]:
                if m not in dist:
                    dist[m] = dist[n] + 1; q.append(m)
        d = dist.get(out)
        if d is None:
            continue                       # pulled up through an internal stage
        if d > worst:
            worst, worstvec = d, dict(env)
    return worst, worstvec


if __name__ == '__main__':
    devs, ports = netlist()
    C = cells()
    want = sys.argv[1:] or ['sg13g2_inv_1', 'sg13g2_nand2_1', 'sg13g2_nor2_1',
                            'sg13g2_and2_1', 'sg13g2_or2_1', 'sg13g2_xor2_1',
                            'sg13g2_xnor2_1', 'sg13g2_nor2b_1', 'sg13g2_mux2_1',
                            'sg13g2_a21oi_1', 'sg13g2_a21o_1', 'sg13g2_o21ai_1']
    R = {}
    print('%-18s %4s %6s  %s' % ('cell', 'dev', 'depth', 'worst vector'))
    for c in want:
        d, v = binding(c, devs, C)
        R[c] = dict(devices=len(devs[c]), binding_pmos_rise_depth=d, worst_vector=v)
        print('%-18s %4d %6d  %s' % (c, len(devs[c]), d, v))
    json.dump(R, open('STACKDEPTH_SKEPT.json', 'w'), indent=1)


def max_series(cell, devs):
    """STRUCTURAL: the longest simple series pMOS chain from VDD to any node --
    i.e. 'does a 2-high series pull-up stack exist anywhere in this cell'.
    Independent of gate states, so it cannot be flattered by the internal-node
    approximation in binding()."""
    ps = [d for d in devs[cell] if d[4] == 'p']
    adj = collections.defaultdict(list)
    for nm, d, g, s, _ in ps:
        adj[d].append((s, nm)); adj[s].append((d, nm))
    best = [0]

    # MY OWN BUG, caught because nand2 (two PARALLEL pull-up pMOS) came back 2:
    # tracking only the devices used lets the walk go VDD -> Y -> VDD through the
    # second parallel device and call it a 2-high stack.  NODES must be visited
    # at most once for a SERIES chain.
    def dfs(n, seen, dep):
        best[0] = max(best[0], dep)
        for m, nm in adj[n]:
            if m in seen or m == 'VSS':
                continue
            dfs(m, seen | {m}, dep + 1)
    dfs('VDD', frozenset({'VDD'}), 0)
    return best[0]
