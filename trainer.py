#!/usr/bin/env python3
"""Live behavioral-model trainer — runs a cycle behind the simulation.

Tails an XYCE_ORACLE_RECORD file while Xyce is still writing it (the
recorder flushes every 64 rows), maintains a trailing window of accepted
steps, and continuously fits per-node models on that PRIOR data using a
spare core. Each fit is published as an atomic snapshot the consumer side
can pick up whenever it likes — pure fire-and-forget in both directions,
per the continuous-learning contract: the trainer never blocks the solver,
the solver never waits for the trainer, and a stale/absent model only
costs its consumer accuracy, never correctness.

v0 model per node: least-squares AR(2) over the trailing window, i.e.
x[k] ~ a*x[k-1] + b*x[k-2] + c. That is deliberately the same family as
the solver's own polynomial predictor so the published quality numbers
(one-step-ahead error vs the live trajectory) are directly comparable.
The fit() seat is the slot for richer families later — per-regime table
models, bfit analytic templates, generative producers — without changing
the transport or the snapshot contract.

Snapshot: OUTDIR/model.json.tmp -> rename model.json
  {epoch, t_head, rows_seen, lag_rows, fit_ms, nodes: N,
   coeffs: [[a,b,c]...], q_rms: one-step-ahead RMS over holdout}

Transports, cheapest first:
  --shm : SOURCE is an XYCE_ORACLE_SHM ring (tmpfs, e.g. /dev/shm/xyce_live).
          The data never leaves memory — the solver's per-step cost is one
          in-cache row copy + a release-store; this side mmaps the same
          pages and samples rows in place at its own pace. Ring overrun
          just means training on a sampled window.
  (default) : SOURCE is an XYCE_ORACLE_RECORD file being written (recorder
          flushes every 64 rows). Portable across hosts/containers, but
          pays stdio + filesystem on both sides.

Usage: trainer.py SOURCE OUTDIR [--shm] [--window 512] [--interval 0.2]
       [--holdout 32] [--stop-idle 10]
"""

import argparse
import json
import mmap
import os
import struct
import sys
import time

try:
    import numpy as np
except ImportError:
    sys.exit('trainer.py needs numpy')

MAGIC = 0x584C495645


def file_rows(path, interval, stop_idle):
    """Yield arrays of new rows from a growing recording file."""
    while not (os.path.exists(path) and os.path.getsize(path) >= 8):
        time.sleep(0.05)
    f = open(path, 'rb')
    n = struct.unpack('<q', f.read(8))[0]
    rowbytes = 8 * (1 + n)
    seen, last_new = 0, time.time()
    yield n
    while True:
        k = (os.path.getsize(path) - 8 - seen * rowbytes) // rowbytes
        if k > 0:
            buf = f.read(k * rowbytes)
            got = len(buf) // rowbytes
            seen += got
            last_new = time.time()
            yield np.frombuffer(buf[:got * rowbytes],
                                dtype='<f8').reshape(got, 1 + n), None, seen
        elif time.time() - last_new > stop_idle:
            return
        else:
            time.sleep(interval / 4)


def ring_open(path):
    """Wait for a live ring's magic, return (mmap, n, R, ring_view)."""
    while True:
        try:
            with open(path, 'rb') as f:
                hdr = f.read(32)
            if len(hdr) >= 32 and struct.unpack('<q', hdr[:8])[0] == MAGIC:
                break
        except OSError:
            pass
        time.sleep(0.05)
    f = open(path, 'r+b')
    mm = mmap.mmap(f.fileno(), 0)
    n, R = struct.unpack('<qq', mm[8:24])
    ring = np.frombuffer(mm, dtype='<f8', offset=4096,
                         count=R * (1 + n)).reshape(R, 1 + n)
    return mm, n, R, ring


def ring_seq(mm):
    return struct.unpack('<q', mm[24:32])[0]


def ring_read(mm, ring, R, margin, lo, hi):
    """Copy rows [lo, hi) out of the ring; returns (rows, safe_count)."""
    idx = np.arange(lo, hi) % R
    rows = ring[idx].copy()              # trainer-side copy, its own core
    seq2 = ring_seq(mm)
    keep = len(rows) - max(0, seq2 - lo - (R - margin))
    return rows, keep


def shm_rows(path, interval, stop_idle, regime_path=None):
    """Yield (rows, keys_or_None, head) sampled in place from the live
    ring(s). With regime_path, rows and regime keys are read in seq
    lockstep (both rings are pushed once per accepted step)."""
    mm, n, R, ring = ring_open(path)
    rmm = rring = None
    rm = 0
    margin = max(4, R // 8)
    seen, last_new = 0, time.time()
    yield n
    while True:
        if regime_path and rmm is None:
            try:
                if os.path.getsize(regime_path) >= 32:
                    hdr = open(regime_path, 'rb').read(8)
                    if struct.unpack('<q', hdr)[0] == MAGIC:
                        rmm, rm, _, rring = ring_open(regime_path)
            except OSError:
                pass
        seq = ring_seq(mm)
        if rmm is not None:
            seq = min(seq, ring_seq(rmm))
        if seq > seen:
            lo = max(seen, seq - (R - margin))
            rows, keep = ring_read(mm, ring, R, margin, lo, seq)
            keys = None
            if rmm is not None:
                krows, kkeep = ring_read(rmm, rring, R, margin, lo, seq)
                keep = min(keep, kkeep)
                keys = krows
            if keep > 0:
                if keep < len(rows):
                    rows = rows[-keep:]
                    keys = keys[-keep:] if keys is not None else None
                last_new = time.time()
                yield rows, keys, seq
                seen = seq
                continue
            seen = seq
        elif time.time() - last_new > stop_idle:
            return
        time.sleep(interval / 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('outdir')
    ap.add_argument('--shm', action='store_true',
                    help='SOURCE is a live XYCE_ORACLE_SHM ring, not a file')
    ap.add_argument('--regime-ring',
                    help='XYCE_ORACLE_SHM_STORE ring: bucket samples by '
                         'regime key and fit per regime (requires --shm)')
    ap.add_argument('--regime-col', type=int, default=0,
                    help='store-vector column holding the regime key')
    ap.add_argument('--dwell', type=int, default=8,
                    help='steps a regime must persist before its samples '
                         'count as an operating point; earlier samples are '
                         'transit (passing through) and are never fitted')
    ap.add_argument('--merge-tol', type=float, default=0.05,
                    help='relative model distance below which two regime '
                         'keys are reported as merge candidates (the '
                         'Verilog-A branch structure is a hint, not truth)')
    ap.add_argument('--promote-tol', type=float,
                    help='promotion protocol: a regime model becomes '
                         'substitution-eligible after its held-out q_rms '
                         'stays <= this for --promote-epochs consecutive '
                         'fits; one breach demotes it (revocable trust)')
    ap.add_argument('--promote-epochs', type=int, default=5)
    ap.add_argument('--window', type=int, default=512)
    ap.add_argument('--interval', type=float, default=0.2,
                    help='seconds between fit cycles')
    ap.add_argument('--holdout', type=int, default=32,
                    help='newest rows held out of the fit for quality eval')
    ap.add_argument('--stop-idle', type=float, default=10.0,
                    help='exit after this many seconds with no new rows')
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    src = (shm_rows(a.source, a.interval, a.stop_idle, a.regime_ring)
           if a.shm else file_rows(a.source, a.interval, a.stop_idle))
    n = next(src)

    def fit_bucket(w):
        """AR(2) per node over rows w; newest holdout rows held out.
        Returns (coeffs, q_rms)."""
        fitw = w[:-a.holdout]
        x2, x1, x0 = fitw[:-2], fitw[1:-1], fitw[2:]
        coeffs = np.empty((n, 3))
        for j in range(n):
            A = np.column_stack([x1[:, j], x2[:, j], np.ones(len(x0))])
            coeffs[j], *_ = np.linalg.lstsq(A, x0[:, j], rcond=None)
        h = w[-a.holdout:]
        pred = h[1:-1] * coeffs[:, 0] + h[:-2] * coeffs[:, 1] + coeffs[:, 2]
        return coeffs, float(np.sqrt(np.mean((pred - h[2:]) ** 2)))

    win = []                      # global window (no-regime mode)
    buckets = {}                  # regime -> settled rows (no time col)
    models = {}                   # regime -> (coeffs, q_rms)
    trans = {}                    # "a>b" -> transition count
    stable = {}                   # regime -> consecutive fits with q<=tol
    promoted = set()              # substitution-eligible regimes
    promo_log = []                # promotion/demotion events
    cur_reg, runlen = None, 0
    settled_ct = transit_ct = 0
    rows_seen = produced = epoch = 0
    t_train = 0.0
    snap = {}

    for arr, keys, head in src:
        rows_seen += len(arr)
        produced = head
        t0 = time.time()

        if keys is None:
            win.extend(arr.tolist())
            del win[:-a.window]
            if len(win) < 3 * a.holdout:
                continue
            coeffs, q_rms = fit_bucket(np.asarray(win)[:, 1:])
            t_train += time.time() - t0
            epoch += 1
            snap = {'epoch': epoch, 't_head': win[-1][0],
                    'rows_seen': rows_seen, 'rows_produced': produced,
                    'coverage': round(rows_seen / max(1, produced), 4),
                    'fit_ms': round(1000 * (time.time() - t0), 2),
                    'nodes': n, 'coeffs': coeffs.tolist(), 'q_rms': q_rms}
        else:
            # dwell/transit split: a sample joins its regime's bucket only
            # after the key has persisted --dwell steps. A regime you are
            # merely passing through never contributes to its model.
            kk = keys[:, 1 + a.regime_col].astype(np.int64)
            for row, k in zip(arr[:, 1:], kk):
                k = int(k)
                if k == cur_reg:
                    runlen += 1
                else:
                    if cur_reg is not None:
                        tk = '%d>%d' % (cur_reg, k)
                        trans[tk] = trans.get(tk, 0) + 1
                    cur_reg, runlen = k, 1
                if runlen >= a.dwell:
                    b = buckets.setdefault(k, [])
                    b.append(row)
                    del b[:-a.window]
                    settled_ct += 1
                else:
                    transit_ct += 1
            reginfo = {}
            for r, b in sorted(buckets.items()):
                if len(b) >= 3 * a.holdout:
                    coeffs, q = fit_bucket(np.asarray(b))
                    models[r] = (coeffs, q)
                    # promotion protocol: substitution eligibility is earned
                    # by demonstrated agreement and revoked by one breach
                    if a.promote_tol is not None:
                        if q <= a.promote_tol:
                            stable[r] = stable.get(r, 0) + 1
                            if stable[r] >= a.promote_epochs \
                               and r not in promoted:
                                promoted.add(r)
                                promo_log.append('epoch %d: regime %d '
                                                 'PROMOTED (q=%.3e)'
                                                 % (epoch + 1, r, q))
                        else:
                            stable[r] = 0
                            if r in promoted:
                                promoted.discard(r)
                                promo_log.append('epoch %d: regime %d '
                                                 'DEMOTED (q=%.3e)'
                                                 % (epoch + 1, r, q))
                if r in models:
                    c, q = models[r]
                    reginfo[str(r)] = {'settled': len(b), 'q_rms': q,
                                       'stable': stable.get(r, 0),
                                       'promoted': r in promoted,
                                       'coeffs': c.tolist()}
            # merge hints: regime keys whose fitted models coincide are
            # syntactic distinctions, not behavioral ones
            merge = []
            rs = sorted(models)
            for i in range(len(rs)):
                for j in range(i + 1, len(rs)):
                    ca, cb = models[rs[i]][0], models[rs[j]][0]
                    d = float(np.mean(np.abs(ca - cb)) /
                              (0.5 * np.mean(np.abs(ca) + np.abs(cb)) + 1e-12))
                    if d < a.merge_tol:
                        merge.append([rs[i], rs[j], round(d, 4)])
            t_train += time.time() - t0
            if not reginfo:
                continue
            epoch += 1
            snap = {'epoch': epoch, 'rows_seen': rows_seen,
                    'rows_produced': produced, 'nodes': n,
                    'transit_frac': round(transit_ct /
                                          max(1, settled_ct + transit_ct), 4),
                    'transitions': trans, 'regimes': reginfo,
                    'merge_candidates': merge,
                    'promotions': promo_log,
                    'fit_ms': round(1000 * (time.time() - t0), 2)}
        tmp = os.path.join(a.outdir, 'model.json.tmp')
        json.dump(snap, open(tmp, 'w'))
        os.replace(tmp, os.path.join(a.outdir, 'model.json'))
        time.sleep(a.interval)

    if 'regimes' in snap:
        print('[trainer] done: %d rows, %d epochs, %.2fs cpu, transit %.1f%%'
              % (rows_seen, epoch, t_train, 100 * snap['transit_frac']))
        for r, info in sorted(snap['regimes'].items(), key=lambda x: int(x[0])):
            print('  regime %s: settled %d  q_rms %.3e%s'
                  % (r, info['settled'], info['q_rms'],
                     '  [PROMOTED]' if info.get('promoted') else ''))
        print('  transitions: %s' % snap['transitions'])
        print('  merge candidates: %s' % snap['merge_candidates'])
        for ev in snap.get('promotions', []):
            print('  ' + ev)
    else:
        print('[trainer] done: ingested %d of %d rows (%.0f%%), %d epochs, '
              '%.2fs training cpu, final q_rms=%.3e'
              % (rows_seen, produced,
                 100.0 * rows_seen / max(1, produced), epoch, t_train,
                 snap.get('q_rms', float('nan')) if epoch else float('nan')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
