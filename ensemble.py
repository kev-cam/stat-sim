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
