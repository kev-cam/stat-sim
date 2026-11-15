// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
#pragma once
// CPU reference of the radio pipeline.  Layout: x[m][b][k], interleaved complex float.
struct CpuPipe {
    int M, B, K;
    void *pb, *pf;
    float *t;
    CpuPipe(int M, int B, int K);
    ~CpuPipe();
    // x: in (M*B*K), y: out, htx/hrx: K bins, G: [j][i][k] coupling
    void run(const float *x, float *y, const float *htx, const float *hrx, const float *G);
};
