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
                                dtype='<f8').reshape(got, 1 + n), seen, seen
        elif time.time() - last_new > stop_idle:
            return
        else:
            time.sleep(interval / 4)


def shm_rows(path, interval, stop_idle):
    """Yield arrays of new rows sampled in place from the live ring."""
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
    margin = max(4, R // 8)
    seen, last_new = 0, time.time()
    yield n
    while True:
        seq = struct.unpack('<q', mm[24:32])[0]
        if seq > seen:
            lo = max(seen, seq - (R - margin))
            idx = np.arange(lo, seq) % R
            rows = ring[idx].copy()          # trainer-side copy, its own core
            seq2 = struct.unpack('<q', mm[24:32])[0]
            keep = len(rows) - max(0, seq2 - lo - (R - margin))
            if keep > 0:
                last_new = time.time()
                yield rows[-keep:] if keep < len(rows) else rows, seq, seen
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
    ap.add_argument('--window', type=int, default=512)
    ap.add_argument('--interval', type=float, default=0.2,
                    help='seconds between fit cycles')
    ap.add_argument('--holdout', type=int, default=32,
                    help='newest rows held out of the fit for quality eval')
    ap.add_argument('--stop-idle', type=float, default=10.0,
                    help='exit after this many seconds with no new rows')
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    src = (shm_rows if a.shm else file_rows)(a.source, a.interval, a.stop_idle)
    n = next(src)

    win = []                      # trailing window of rows (t + n values)
    rows_seen = 0                 # rows actually ingested (sampled, for shm)
    produced = 0                  # rows the solver has produced
    epoch = 0
    t_train = 0.0

    for arr, head, _prev in src:
        rows_seen += len(arr)
        produced = head
        win.extend(arr.tolist())
        del win[:-a.window]

        if len(win) < 3 * a.holdout:
            continue

        # fit on prior data only; newest rows are the holdout
        t0 = time.time()
        w = np.asarray(win)[:, 1:]          # drop time column
        fitw = w[:-a.holdout]
        x2, x1, x0 = fitw[:-2], fitw[1:-1], fitw[2:]
        coeffs = np.empty((n, 3))
        for j in range(n):
            A = np.column_stack([x1[:, j], x2[:, j],
                                 np.ones(len(x0))])
            coeffs[j], *_ = np.linalg.lstsq(A, x0[:, j], rcond=None)
        # one-step-ahead quality on the held-out (unseen) rows
        h = w[-a.holdout:]
        pred = h[1:-1] * coeffs[:, 0] + h[:-2] * coeffs[:, 1] + coeffs[:, 2]
        q_rms = float(np.sqrt(np.mean((pred - h[2:]) ** 2)))
        t_train += time.time() - t0

        epoch += 1
        snap = {'epoch': epoch, 't_head': win[-1][0], 'rows_seen': rows_seen,
                'rows_produced': produced,
                'coverage': round(rows_seen / max(1, produced), 4),
                'fit_ms': round(1000 * (time.time() - t0), 2),
                'nodes': n, 'coeffs': coeffs.tolist(), 'q_rms': q_rms}
        tmp = os.path.join(a.outdir, 'model.json.tmp')
        json.dump(snap, open(tmp, 'w'))
        os.replace(tmp, os.path.join(a.outdir, 'model.json'))
        time.sleep(a.interval)

    print('[trainer] done: ingested %d of %d rows (%.0f%%), %d epochs, '
          '%.2fs training cpu, final q_rms=%.3e'
          % (rows_seen, produced,
             100.0 * rows_seen / max(1, produced), epoch, t_train,
             snap['q_rms'] if epoch else float('nan')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
