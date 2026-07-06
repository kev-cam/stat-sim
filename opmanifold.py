#!/usr/bin/env python3
"""Operating-point manifold: the first continuously-learned behavioral model
in the statsim flow.

Each ensemble member contributes its converged DC operating point, keyed by
its parameter sample. New members get a startup seed interpolated over the
manifold (inverse-distance weighting over normalized parameter space) and
applied through Xyce .NODESET — the advisory-only mechanism: the seed places
Newton inside the convergence basin, then the real solve converges freely,
so a poor model costs iterations and never correctness. Measured on the
2000-node ladder: DC Newton 38 -> 2 iterations (19x), downstream transient
-11% as well.

Subcommands:
  ingest  MANIFOLD_DIR ID ORC --params k=v[,k=v...]
          Extract the op point (first record) from an oracle recording
          (XYCE_ORACLE_RECORD format) into the manifold.
  seed    MANIFOLD_DIR NAMESFILE OUT_INC --params k=v[,...] [--knn K]
          Interpolate a seed for the given parameter point and write a
          .NODESET include file (node names via Xyce -namesfile output;
          branch/current variables are skipped).

Storage: MANIFOLD_DIR/manifest.jsonl (one JSON object per member) +
<id>.opb (binary: int64 n, n float64). Pure stdlib.
"""

import argparse
import json
import math
import os
import re
import struct
import sys


def driven_nodes(deckpath):
    """Nodes pinned by ideal voltage-defining elements (V/E/H, B with V=).
    A .NODESET clamp on such a node collides with the source constraint and
    Amesos sees a singular matrix. Top-level elements only — sources inside
    .INCLUDEd subckts are not scanned yet."""
    out = set()
    for ln in open(deckpath, errors='replace'):
        t = ln.split()
        if len(t) < 3 or not t[0]:
            continue
        if t[0][0] in 'VvEeHh' or \
           (t[0][0] in 'Bb' and re.search(r'(?i)\bV\s*=', ln)):
            out.update((t[1].lower(), t[2].lower()))
    return out


def read_orc_first_row(path):
    with open(path, 'rb') as f:
        n = struct.unpack('<q', f.read(8))[0]
        row = struct.unpack('<%dd' % (1 + n), f.read(8 * (1 + n)))
    return list(row[1:])  # drop time


def read_opb(path):
    with open(path, 'rb') as f:
        n = struct.unpack('<q', f.read(8))[0]
        return list(struct.unpack('<%dd' % n, f.read(8 * n)))


def write_opb(path, vals):
    with open(path, 'wb') as f:
        f.write(struct.pack('<q', len(vals)))
        f.write(struct.pack('<%dd' % len(vals), *vals))


def parse_params(s):
    out = {}
    for kv in s.split(','):
        k, v = kv.split('=')
        out[k.strip()] = float(v)
    return out


def load_manifest(mdir):
    path = os.path.join(mdir, 'manifest.jsonl')
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def read_namesfile(path):
    """Xyce -namesfile output: index -> solution variable name."""
    names = {}
    for ln in open(path):
        p = ln.split()
        if len(p) == 2 and p[0].isdigit():
            names[int(p[0])] = p[1]
    return names


def cmd_ingest(a):
    os.makedirs(a.manifold, exist_ok=True)
    op = read_orc_first_row(a.orc)
    write_opb(os.path.join(a.manifold, a.id + '.opb'), op)
    with open(os.path.join(a.manifold, 'manifest.jsonl'), 'a') as f:
        f.write(json.dumps({'id': a.id, 'params': parse_params(a.params),
                            'op': a.id + '.opb'}) + '\n')
    print('[opmanifold] ingested %s (%d vars)' % (a.id, len(op)))


def cmd_seed(a):
    members = load_manifest(a.manifold)
    if not members:
        print('[opmanifold] empty manifold — no seed emitted')
        return 1
    q = parse_params(a.params)
    dims = sorted(q.keys())

    # Normalize each parameter dimension by its spread across the manifold
    # (a dimension nobody varies contributes nothing to distance).
    scale = {}
    for d in dims:
        vals = [m['params'].get(d, 0.0) for m in members]
        lo, hi = min(vals), max(vals)
        scale[d] = (hi - lo) if hi > lo else 1.0

    def dist(m):
        return math.sqrt(sum(((q[d] - m['params'].get(d, 0.0)) / scale[d]) ** 2
                             for d in dims))

    ranked = sorted(members, key=dist)[:max(1, a.knn)]
    eps = 1e-9
    weights = [1.0 / (dist(m) + eps) for m in ranked]
    wsum = sum(weights)

    ops = [read_opb(os.path.join(a.manifold, m['op'])) for m in ranked]
    n = len(ops[0])
    seed = [sum(w * op[i] for w, op in zip(weights, ops)) / wsum
            for i in range(n)]

    names = read_namesfile(a.namesfile)
    pinned = driven_nodes(a.deck) if a.deck else set()
    cnt = 0
    with open(a.out, 'w') as f:
        f.write('* op-manifold seed: %d members (ids %s), IDW k=%d\n'
                % (len(members), ','.join(m['id'] for m in ranked), a.knn))
        if a.voltlim_off:
            # A good seed makes the DCOP voltage limiter pure drag (it walks
            # ~1000 iterations even from the exact answer on high-gain
            # feedback decks; measured 1054 -> 6 with it off). Only safe
            # WITH a seed — the caller must retry limiter-on if DCOP fails.
            # CAUTION: VOLTLIM=0 rides the WHOLE run, not just the DCOP.
            # Fine when DC dominates or the transient tolerates it (MOS
            # opamp: tran -2%), harmful on stiff switching/BJT transients
            # (amp300 cascade: tran Jacobians +72%, wall +62%). Use only
            # when the DC share of the run justifies it.
            f.write('.options DEVICE VOLTLIM=0\n')
        for i in range(n):
            nm = names.get(i)
            if nm and nm[0].isalpha() and '#' not in nm \
               and 'branch' not in nm.lower() and nm.lower() not in pinned:
                f.write('.NODESET V(%s)=%.12e\n' % (nm, seed[i]))
                cnt += 1
    print('[opmanifold] seed %s: %d nodesets from %d neighbors'
          % (a.out, cnt, len(ranked)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('ingest')
    p.add_argument('manifold')
    p.add_argument('id')
    p.add_argument('orc')
    p.add_argument('--params', required=True)
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser('seed')
    p.add_argument('manifold')
    p.add_argument('namesfile')
    p.add_argument('out')
    p.add_argument('--params', required=True)
    p.add_argument('--knn', type=int, default=3)
    p.add_argument('--deck', help='netlist to scan for source-pinned nodes '
                                  '(excluded from the .NODESET)')
    p.add_argument('--voltlim-off', action='store_true',
                   help='emit .options DEVICE VOLTLIM=0 alongside the seed')
    p.set_defaults(fn=cmd_seed)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == '__main__':
    main()
