#!/usr/bin/env python3
"""Statsim ensemble driver with op-manifold startup seeding.

Runs N Monte-Carlo members of a deck template, each with gaussian-sampled
parameters. With seeding enabled, every member after the first starts from a
.NODESET interpolated over the op manifold of the members already run
(opmanifold.py), and contributes its own op back — continuous learning; the
final solve is always the authoritative transistor-level Newton (a bad seed
costs iterations, never correctness).

Deck template: plain netlist with @NAME@ placeholders for parameters and an
optional @SEED@ placeholder (replaced by ".INCLUDE <seedfile>" or blank).

Member execution is a pluggable command (XYCE_CMD env, default local
mpirun); in the container-pool architecture the same driver dispatches
members to pool containers instead — nothing else changes.

Usage:
  ensemble.py TEMPLATE WORKDIR --n 8 --param AMP=5.0:0.25 --param RVAL=100:3
              [--no-seed] [--rng 1234]

Reports per-member and aggregate DC-op/transient Newton counts and wall
times, plus a CSV in WORKDIR.
"""

import argparse
import os
import random
import re
import struct
import subprocess
import sys
import time

TOOLDIR = os.path.dirname(os.path.abspath(__file__))


def parse_param(spec):
    name, rest = spec.split('=')
    nominal, sigma = rest.split(':')
    return name, float(nominal), float(sigma)


def xyce_counters(outpath):
    """(dc_jacobians, tran_jacobians, dc_steps, tran_steps) from a Xyce log;
    the summary block appears once for the DC op and once for the transient."""
    jac, steps = [], []
    for ln in open(outpath, errors='replace'):
        m = re.search(r'Number Jacobians Evaluated:\s+(\d+)', ln)
        if m:
            jac.append(int(m.group(1)))
        m = re.search(r'Number Successful Steps Taken:\s+(\d+)', ln)
        if m:
            steps.append(int(m.group(1)))
    dcj = jac[0] if jac else -1
    trj = jac[-1] if len(jac) > 1 else -1
    return dcj, trj, steps[0] if steps else -1, steps[-1] if len(steps) > 1 else -1


SEED_CACHE = ('{"ce_stage": {"params": {"gain": 9.82, "Vlo": 0.45, '
              '"Vhi": 9.53, "Rout": 1321.0, "Rin": 100000.0, "fp": 6000.0}, '
              '"sim": "neutral"}}\n')


def bfit_front(bfit, cache, src, out):
    """Substitute recognized blocks and coarsen the transient (the same
    recipe as the benchmark harness). Returns True on success."""
    t = out + '.t'
    env = dict(os.environ, XYCE_USE_BFIT='auto')
    r = subprocess.run([sys.executable, bfit, 'front', src, '--sim', 'xyce',
                        '--cache', cache, '-o', t],
                       env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    if r.returncode != 0 or not os.path.exists(t):
        return False
    txt = re.sub(r'(?m)^\.tran .*$', '.tran 1u 2m', open(t).read())
    open(out, 'w').write(txt)
    os.remove(t)
    return True


def read_orc(path):
    import numpy as np
    with open(path, 'rb') as f:
        n = struct.unpack('<q', f.read(8))[0]
        data = np.fromfile(f, dtype='<f8')
    rows = data[:len(data) - len(data) % (1 + n)].reshape(-1, 1 + n)
    return rows[:, 0], rows[:, 1:]


def audit_err(orc_full, names_full, orc_sub, names_sub, only=None):
    """Mean rel-L2 over the nodes both decks share (the macromodel deck
    eliminates internal nodes), substituted waveform interpolated onto the
    full solve's timegrid. `only` restricts to named observables."""
    import numpy as np
    from opmanifold import read_namesfile
    tf, F = read_orc(orc_full)
    ts, S = read_orc(orc_sub)
    def usable(m):
        return {v.lower(): k for k, v in m.items()
                if v and v[0].isalpha() and '#' not in v
                and 'branch' not in v.lower()}
    nf = usable(read_namesfile(names_full))
    ns = usable(read_namesfile(names_sub))
    shared = sorted(set(nf) & set(ns))
    if only:
        want = {w.strip().lower() for w in only.split(',') if w.strip()}
        shared = [n for n in shared if n in want]
    errs = []
    for nm in shared:
        a = F[:, nf[nm]]
        b = np.interp(tf, ts, S[:, ns[nm]])
        errs.append(float(np.linalg.norm(a - b) /
                          (np.linalg.norm(a) + 1e-30)))
    return (float(np.mean(errs)) if errs else float('inf')), len(shared)


def run_substitution(a, xyce_cmd, tpl, params, rng, csv):
    """Promotion-gated ensemble: the full solve stays authoritative on
    audits, promoted stretches ride the macromodel."""
    cache = a.bfit_cache
    if not cache:
        cache = os.path.join(a.workdir, 'bfit_cache.json')
        open(cache, 'w').write(SEED_CACHE)
    names_f = os.path.join(a.workdir, 'names_full.txt')
    names_s = os.path.join(a.workdir, 'names_sub.txt')
    promoted, err0 = False, None
    full_walls, audits = [], []
    t_all = time.time()

    for i in range(a.n):
        mid = 'm%03d' % i
        sample = {n: rng.gauss(nom, sig) for n, nom, sig in params}
        deck = tpl.replace('@SEED@', '* cold start')
        for k, v in sample.items():
            deck = deck.replace('@%s@' % k, '%.9g' % v)
        fdeck = os.path.join(a.workdir, mid + '.cir')
        open(fdeck, 'w').write(deck)
        sdeck = os.path.join(a.workdir, mid + '_sub.cir')
        audit = (i % a.audit_every == 0)

        def run(deckpath, orc, outp):
            env = dict(os.environ, XYCE_ORACLE_RECORD=orc)
            t0 = time.time()
            r = subprocess.run(list(xyce_cmd) + [deckpath],
                               stdout=open(outp, 'w'),
                               stderr=subprocess.STDOUT, env=env,
                               cwd=a.workdir)
            return r.returncode, time.time() - t0

        if audit or not promoted:
            rc, wf = run(fdeck, os.path.join(a.workdir, mid + '.orc'),
                         os.path.join(a.workdir, mid + '.out'))
            if rc != 0:
                print('[ensemble] %s full run FAILED rc=%d' % (mid, rc))
                continue
            full_walls.append(wf)
            mode = 'full'
            if audit and bfit_front(a.bfit, cache, fdeck, sdeck):
                if i == 0:
                    subprocess.run(list(xyce_cmd) + ['-namesfile', names_f,
                                                     fdeck],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.STDOUT, cwd=a.workdir)
                    subprocess.run(list(xyce_cmd) + ['-namesfile', names_s,
                                                     sdeck],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.STDOUT, cwd=a.workdir)
                src, ws = run(sdeck, os.path.join(a.workdir,
                                                  mid + '_sub.orc'),
                              os.path.join(a.workdir, mid + '_sub.out'))
                if src == 0:
                    err, shared = audit_err(
                        os.path.join(a.workdir, mid + '.orc'), names_f,
                        os.path.join(a.workdir, mid + '_sub.orc'), names_s,
                        only=a.audit_nodes)
                    audits.append((mid, err))
                    ok = (err <= a.audit_accept if err0 is None
                          else err <= a.audit_drift * err0)
                    if ok and not promoted:
                        promoted = True
                        err0 = err if err0 is None else err0
                        mode = 'audit PROMOTE (err %.3f, %d nodes)' \
                               % (err, shared)
                    elif ok:
                        mode = 'audit ok (err %.3f)' % err
                    else:
                        promoted = False
                        mode = 'audit DEMOTE (err %.3f > %.3f)' \
                               % (err, a.audit_drift * (err0 or 0))
                else:
                    mode = 'audit (sub run failed rc=%d)' % src
            wall = wf
        else:
            if not bfit_front(a.bfit, cache, fdeck, sdeck):
                print('[ensemble] %s bfit front failed — running full'
                      % mid)
                rc, wall = run(fdeck, os.path.join(a.workdir, mid + '.orc'),
                               os.path.join(a.workdir, mid + '.out'))
                full_walls.append(wall)
                mode = 'full (fallback)'
            else:
                rc, wall = run(sdeck, os.path.join(a.workdir,
                                                   mid + '_sub.orc'),
                               os.path.join(a.workdir, mid + '_sub.out'))
                mode = 'sub' if rc == 0 else 'sub FAILED rc=%d' % rc
        csv.write('%s,%s,%.2f\n' % (mid, mode.split()[0], wall))
        print('[ensemble] %s %-28s wall=%6.2fs' % (mid, mode, wall))

    flow = time.time() - t_all
    est_full = (sum(full_walls) / max(1, len(full_walls))) * a.n
    print('[ensemble] SUBSTITUTION TOTAL: %.1fs vs est all-full %.1fs '
          '(%.1fx); audits: %s'
          % (flow, est_full, est_full / max(flow, 1e-9),
             ', '.join('%s=%.3f' % x for x in audits)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('template')
    ap.add_argument('workdir')
    ap.add_argument('--n', type=int, default=8)
    ap.add_argument('--param', action='append', required=True,
                    help='NAME=nominal:sigma (gaussian)')
    ap.add_argument('--no-seed', action='store_true')
    ap.add_argument('--seed-voltlim-off', action='store_true',
                    help='disable voltage limiting for seeded members '
                         '(auto-retries limiter-on if the member fails). '
                         'VOLTLIM=0 applies to the whole run: big DCOP win '
                         'on high-gain feedback decks, but can slow stiff '
                         'transients — only use when DC dominates')
    ap.add_argument('--jobs', type=int, default=1,
                    help='run up to N members concurrently (parallel '
                         'evaluation on spare cores). The watcher ingests '
                         'each member\'s DC op as soon as its first '
                         'recording row lands — a cycle behind the live '
                         'runs — so later launches seed from members that '
                         'are still simulating.')
    ap.add_argument('--substitute-bfit', action='store_true',
                    help='promotion-gated behavioral substitution: audit '
                         'members run BOTH full-accuracy and bfit-'
                         'substituted decks and compare shared nodes; a '
                         'passing audit promotes the macromodel and later '
                         'members run substituted only; drift beyond '
                         '--audit-drift x the anchored error demotes. The '
                         'full solve stays authoritative on every audit.')
    ap.add_argument('--bfit', default='/usr/local/src/sv2ghdl/bfit/bfit.py')
    ap.add_argument('--bfit-cache',
                    help='bfit model cache (default: ce_stage seed cache '
                         'written into WORKDIR)')
    ap.add_argument('--audit-every', type=int, default=4,
                    help='every Kth member audits (runs both, compares)')
    ap.add_argument('--audit-accept', type=float, default=2.0,
                    help='absolute mean rel-L2 gate for the FIRST '
                         'promotion (phase-dominated signals read high)')
    ap.add_argument('--audit-drift', type=float, default=1.5,
                    help='demote when audit error exceeds this factor of '
                         'the promotion-anchor error')
    ap.add_argument('--audit-nodes',
                    help='comma-separated node names the audit compares '
                         '(default: every node both decks share — on deep '
                         'cascades that averages in the macromodel\'s '
                         'internal ports where per-stage phase error '
                         'compounds; judge the observable instead)')
    ap.add_argument('--knn', type=int, default=3)
    ap.add_argument('--rng', type=int, default=1234)
    a = ap.parse_args()

    xyce_cmd = os.environ.get('XYCE_CMD', '').split() or None
    if not xyce_cmd:
        print('ensemble.py: set XYCE_CMD (e.g. "mpirun -np 1 -x LD_LIBRARY_PATH=... /path/Xyce")',
              file=sys.stderr)
        return 2

    params = [parse_param(p) for p in a.param]
    tpl = open(a.template).read()
    os.makedirs(a.workdir, exist_ok=True)
    manifold = os.path.join(a.workdir, 'manifold')
    namesfile = os.path.join(a.workdir, 'names.txt')
    rng = random.Random(a.rng)
    seeding = not a.no_seed

    if a.substitute_bfit:
        csv = open(os.path.join(a.workdir, 'ensemble.csv'), 'w')
        csv.write('member,mode,wall_s\n')
        return run_substitution(a, xyce_cmd, tpl, params, rng, csv)

    csv = open(os.path.join(a.workdir, 'ensemble.csv'), 'w')
    csv.write('member,seeded,' + ','.join(n for n, _, _ in params) +
              ',dc_jac,tran_jac,tran_steps,wall_s\n')

    tot_dc = tot_tr = 0
    t_all = time.time()

    def prepare(i):
        """Sample params, decide seeding from the manifold as it exists NOW
        (launch time), write the member deck."""
        mid = 'm%03d' % i
        sample = {n: rng.gauss(nom, sig) for n, nom, sig in params}
        deck = tpl
        for k, v in sample.items():
            deck = deck.replace('@%s@' % k, '%.9g' % v)
        seeded = False
        seedinc = os.path.join(a.workdir, mid + '_seed.inc')
        if seeding and os.path.exists(os.path.join(manifold, 'manifest.jsonl')) \
           and os.path.exists(namesfile):
            pstr = ','.join('%s=%.9g' % (k, v) for k, v in sample.items())
            cmd = [sys.executable, os.path.join(TOOLDIR, 'opmanifold.py'),
                   'seed', manifold, namesfile, seedinc,
                   '--params', pstr, '--knn', str(a.knn),
                   '--deck', a.template]
            if a.seed_voltlim_off:
                cmd.append('--voltlim-off')
            seeded = subprocess.run(cmd).returncode == 0
        deck = deck.replace('@SEED@',
                            '.INCLUDE %s' % seedinc if seeded else '* cold start')
        deckpath = os.path.join(a.workdir, mid + '.cir')
        open(deckpath, 'w').write(deck)
        return {'mid': mid, 'sample': sample, 'deck': deck, 'seeded': seeded,
                'seedinc': seedinc, 'deckpath': deckpath,
                'orc': os.path.join(a.workdir, mid + '.orc'),
                'outp': os.path.join(a.workdir, mid + '.out'),
                'ingested': False, 'retried': False, 'wall': 0.0}

    def launch(st):
        env = dict(os.environ, XYCE_ORACLE_RECORD=st['orc'])
        st['t0'] = time.time()
        st['proc'] = subprocess.Popen(list(xyce_cmd) + [st['deckpath']],
                                      stdout=open(st['outp'], 'w'),
                                      stderr=subprocess.STDOUT, env=env,
                                      cwd=a.workdir)

    def op_ready(st):
        """Header plus one full row (the flushed DC op) on disk yet?"""
        try:
            sz = os.path.getsize(st['orc'])
        except OSError:
            return False
        if sz < 16:
            return False
        with open(st['orc'], 'rb') as f:
            nvar = struct.unpack('<q', f.read(8))[0]
        return sz >= 8 + 8 * (1 + nvar)

    def ingest(st):
        pstr = ','.join('%s=%.9g' % (k, v) for k, v in st['sample'].items())
        subprocess.run([sys.executable, os.path.join(TOOLDIR, 'opmanifold.py'),
                        'ingest', manifold, st['mid'], st['orc'],
                        '--params', pstr], stdout=subprocess.DEVNULL)
        st['ingested'] = True

    running, next_i = [], 0
    while next_i < a.n or running:
        while len(running) < max(1, a.jobs) and next_i < a.n:
            if seeding and running and \
               not os.path.exists(os.path.join(manifold, 'manifest.jsonl')):
                break   # hold the fleet until the bootstrap op lands
            st = prepare(next_i)
            if next_i == 0:
                # -namesfile is an introspection mode: Xyce dumps the
                # solution variable names and exits without solving — run
                # it as a blocking pre-flight before the first member.
                subprocess.run(list(xyce_cmd) + ['-namesfile', namesfile,
                                                 st['deckpath']],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.STDOUT, cwd=a.workdir)
            launch(st)
            running.append(st)
            next_i += 1
        time.sleep(0.05)
        for st in running[:]:
            # the trainer runs a cycle behind the live members: ingest each
            # DC op as soon as its (flushed) first recording row appears,
            # while that member's transient is still in progress.
            if not st['ingested'] and op_ready(st):
                ingest(st)
            rc = st['proc'].poll()
            if rc is None:
                continue
            st['wall'] += time.time() - st['t0']
            running.remove(st)
            if rc != 0 and st['seeded'] and not st['retried']:
                # Advisory contract: a bad seed may only cost a retry.
                print('[ensemble] %s seeded run failed (rc=%d) — retrying cold'
                      % (st['mid'], rc))
                open(st['deckpath'], 'w').write(
                    st['deck'].replace('.INCLUDE %s' % st['seedinc'],
                                       '* seed retried cold'))
                st['seeded'] = False
                st['retried'] = True
                launch(st)
                running.append(st)
                continue
            if rc != 0:
                print('[ensemble] %s FAILED (rc=%d) — see %s'
                      % (st['mid'], rc, st['outp']))
                continue
            if not st['ingested'] and op_ready(st):
                ingest(st)
            dcj, trj, _, trs = xyce_counters(st['outp'])
            tot_dc += max(dcj, 0)
            tot_tr += max(trj, 0)
            csv.write('%s,%d,%s,%d,%d,%d,%.2f\n' %
                      (st['mid'], int(st['seeded']),
                       ','.join('%.9g' % st['sample'][n] for n, _, _ in params),
                       dcj, trj, trs, st['wall']))
            print('[ensemble] %s seeded=%d dc_jac=%d tran_jac=%d wall=%.2fs'
                  % (st['mid'], int(st['seeded']), dcj, trj, st['wall']))

    csv.close()
    print('[ensemble] TOTAL: dc_jac=%d tran_jac=%d wall=%.1fs (%d members, seeding=%s)'
          % (tot_dc, tot_tr, time.time() - t_all, a.n, seeding))
    return 0


if __name__ == '__main__':
    sys.exit(main())
