#!/usr/bin/env python3
"""(a)/(d) NETLIST CONNECTIVITY AUDIT of the committed rail-draw decks.

Before re-running anything: is the meter on a node that HAS a load?  A rail
source whose node carries no circuit element at all reads exactly 0 A by
construction, and 'exactly 0.0000 fC' would then be a TAUTOLOGY of the deck
rather than a measurement of a device.

This parses the decks the run actually simulated and, for every rail source,
lists every element that touches its node -- excluding the metering B-sources
and their 1 F integrator caps, which sense but do not load."""
import json, os, re, sys, collections

DECKS = {
    "D_raildraw.cir": "/usr/local/src/stat-sim/qal/pgcell/D_raildraw.cir",
    "D2_raildraw_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell/D2_raildraw_vhi.cir",
}

# element -> node positions (1-indexed into the split token list)
NODE_POS = {
    "V": [1, 2], "I": [1, 2], "R": [1, 2], "C": [1, 2], "L": [1, 2],
    "B": [1, 2], "E": [1, 2, 3, 4], "G": [1, 2, 3, 4],
    "X": None,   # subckt / model-card device: all tokens up to the model name
}


def elements(path):
    out = []
    for raw in open(path):
        s = raw.strip()
        if not s or s.startswith("*") or s.startswith(".") or s.startswith("+"):
            continue
        t = s.split()
        k = t[0][0].upper()
        if k == "X":
            # Xname n1 n2 ... model [params]  -- nodes are every token before the
            # first token that is a known model/subckt name or contains '='
            nodes = []
            for tok in t[1:]:
                if "=" in tok or tok.startswith("sg13"):
                    break
                nodes.append(tok)
            out.append((t[0], k, nodes, s))
        elif k in NODE_POS and NODE_POS[k]:
            nodes = [t[i] for i in NODE_POS[k] if i < len(t)]
            out.append((t[0], k, nodes, s))
    return out


def audit(path):
    els = elements(path)
    # every rail source VS<tag>
    rails = {}
    for nm, k, nodes, s in els:
        if k == "V" and nm.upper().startswith("VS") and not nm.upper().startswith("VSEL"):
            rails[nm] = nodes[0]
    rep = {}
    for src, node in rails.items():
        touch = []
        for nm, k, nodes, s in els:
            if nm == src:
                continue
            if node in nodes:
                # metering: B-sources named BX*, integrator caps CX*, res RX*
                meter = bool(re.match(r"^(BX|CX|RX)", nm, re.I))
                touch.append(dict(el=nm, kind=k, meter=meter, line=s[:110]))
        real = [t for t in touch if not t["meter"]]
        rep[src] = dict(node=node, n_touching=len(touch),
                        n_real_circuit_elements=len(real),
                        real=real,
                        VERDICT=("RAIL NODE CARRIES NO CIRCUIT ELEMENT -- "
                                 "I(%s) == 0 BY CONSTRUCTION" % src) if not real
                                else "loaded")
    return rep


if __name__ == "__main__":
    R = {}
    for name, p in DECKS.items():
        if not os.path.exists(p):
            R[name] = dict(error="missing")
            continue
        a = audit(p)
        R[name] = a
        dangling = [s for s, d in a.items() if d["n_real_circuit_elements"] == 0]
        print("%-22s %3d rail sources, %3d with a DANGLING rail node: %s"
              % (name, len(a), len(dangling), sorted(dangling)))
        for s in sorted(dangling)[:4]:
            print("    %s -> node %s : %s" % (s, a[s]["node"], a[s]["VERDICT"]))
    json.dump(R, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "CONNAUDIT.json"), "w"), indent=1)
    print("wrote CONNAUDIT.json")
