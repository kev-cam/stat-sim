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

Usage: trainer.py RECORDING OUTDIR [--window 512] [--interval 0.2]
       [--holdout 32] [--stop-idle 10]
"""

import argparse
import json
import os
import struct
import sys
import time

try:
    import numpy as np
except ImportError:
    sys.exit('trainer.py needs numpy')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('recording')
    ap.add_argument('outdir')
    ap.add_argument('--window', type=int, default=512)
    ap.add_argument('--interval', type=float, default=0.2,
                    help='seconds between fit cycles')
    ap.add_argument('--holdout', type=int, default=32,
                    help='newest rows held out of the fit for quality eval')
    ap.add_argument('--stop-idle', type=float, default=10.0,
                    help='exit after this many seconds with no new rows')
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    # wait for the header
    while not (os.path.exists(a.recording)
               and os.path.getsize(a.recording) >= 8):
        time.sleep(0.05)
    f = open(a.recording, 'rb')
    n = struct.unpack('<q', f.read(8))[0]
    rowbytes = 8 * (1 + n)

    win = []                      # trailing window of rows (t + n values)
    rows_seen = 0
    epoch = 0
    last_new = time.time()
    t_train = 0.0

    while True:
        avail = os.path.getsize(a.recording) - 8 - rows_seen * rowbytes
        k = avail // rowbytes
        if k > 0:
            buf = f.read(k * rowbytes)
            got = len(buf) // rowbytes
            arr = np.frombuffer(buf[:got * rowbytes],
                                dtype='<f8').reshape(got, 1 + n)
            rows_seen += got
            win.extend(arr.tolist())
            del win[:-a.window]
            last_new = time.time()
        elif time.time() - last_new > a.stop_idle:
            break
        else:
            time.sleep(a.interval / 4)
            continue

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
        lag = int((os.path.getsize(a.recording) - 8) // rowbytes - rows_seen)
        snap = {'epoch': epoch, 't_head': win[-1][0], 'rows_seen': rows_seen,
                'lag_rows': lag, 'fit_ms': round(1000 * (time.time() - t0), 2),
                'nodes': n, 'coeffs': coeffs.tolist(), 'q_rms': q_rms}
        tmp = os.path.join(a.outdir, 'model.json.tmp')
        json.dump(snap, open(tmp, 'w'))
        os.replace(tmp, os.path.join(a.outdir, 'model.json'))
        time.sleep(a.interval)

    print('[trainer] done: %d rows, %d epochs, %.2fs training cpu, '
          'final q_rms=%.3e'
          % (rows_seen, epoch, t_train,
             snap['q_rms'] if epoch else float('nan')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
