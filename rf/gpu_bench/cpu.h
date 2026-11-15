// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
// CPU reference kernels for spectral-signal operations (interleaved complex).
#pragma once
template <class T> void cpu_linear(const T *x, const T *h, T *y, int K, int B);
template <class T> void cpu_arena(const T *x, const T *dist, T *y, int M, int K, T f0, T df);
template <class T> struct CpuNonlin {
    void *plan_f = nullptr, *plan_b = nullptr;
    T *tmp = nullptr;
    int K, B;
    CpuNonlin(int K, int B);
    ~CpuNonlin();
    void run(const T *x, T *y, const T *a);   // a = {a1re,a1im,a3re,a3im,a5re,a5im}
};
