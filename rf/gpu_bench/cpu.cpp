// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
#include "cpu.h"
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fftw3.h>
#include <omp.h>

static const double C0 = 299792458.0;

// y = H .* x per bin, for B signals of K bins each
template <class T> void cpu_linear(const T *x, const T *h, T *y, int K, int B) {
#pragma omp parallel for schedule(static) if ((long)K * B > 16384)
    for (int b = 0; b < B; b++) {
        const T *xb = x + 2L * b * K;
        T *yb = y + 2L * b * K;
#pragma omp simd
        for (int k = 0; k < K; k++) {
            T xr = xb[2 * k], xi = xb[2 * k + 1], hr = h[2 * k], hi = h[2 * k + 1];
            yb[2 * k] = xr * hr - xi * hi;
            yb[2 * k + 1] = xr * hi + xi * hr;
        }
    }
}

// Arena resolution: every antenna j receives the Friis-coupled sum of all
// other antennas i, per frequency bin (amplitude lambda/(4 pi d), phase -2 pi f d / c).
template <class T> void cpu_arena(const T *x, const T *dist, T *y, int M, int K, T f0, T df) {
#pragma omp parallel for schedule(static) if ((long)M * M * K > 16384)
    for (int j = 0; j < M; j++) {
        T *yj = y + 2L * j * K;
        memset(yj, 0, sizeof(T) * 2 * K);
        for (int i = 0; i < M; i++) {
            if (i == j) continue;
            const T *xi_ = x + 2L * i * K;
            T d = dist[i * M + j];
#pragma omp simd
            for (int k = 0; k < K; k++) {
                T f = f0 + df * k;
                T a = (T)(C0 / (4 * M_PI)) / (f * d);
                T ph = (T)(-2 * M_PI / C0) * f * d;
                T c = std::cos(ph), s = std::sin(ph);
                T xr = xi_[2 * k], xi = xi_[2 * k + 1];
                yj[2 * k] += a * (xr * c - xi * s);
                yj[2 * k + 1] += a * (xr * s + xi * c);
            }
        }
    }
}

// Memoryless nonlinearity evaluated the harmonic-balance way:
// IFFT -> y = x (a1 + a3 |x|^2 + a5 |x|^4) -> FFT
template <class T> static inline void poly(T *t, int n, const T *a, T scale) {
#pragma omp simd
    for (int k = 0; k < n; k++) {
        T xr = t[2 * k] * scale, xi = t[2 * k + 1] * scale;
        T p = xr * xr + xi * xi;
        T gr = a[0] + p * (a[2] + p * a[4]);
        T gi = a[1] + p * (a[3] + p * a[5]);
        t[2 * k] = xr * gr - xi * gi;
        t[2 * k + 1] = xr * gi + xi * gr;
    }
}

template <> CpuNonlin<double>::CpuNonlin(int K_, int B_) : K(K_), B(B_) {
    tmp = (double *)fftw_malloc(sizeof(double) * 2 * (size_t)K * B);
    unsigned fl = K > (1 << 18) ? FFTW_ESTIMATE : FFTW_MEASURE;
    double *scr = (double *)fftw_malloc(sizeof(double) * 2 * (size_t)K);
    plan_b = fftw_plan_dft_1d(K, (fftw_complex *)scr, (fftw_complex *)tmp, FFTW_BACKWARD, fl);
    plan_f = fftw_plan_dft_1d(K, (fftw_complex *)tmp, (fftw_complex *)scr, FFTW_FORWARD, fl);
    fftw_free(scr);
}
template <> CpuNonlin<double>::~CpuNonlin() {
    fftw_destroy_plan((fftw_plan)plan_b); fftw_destroy_plan((fftw_plan)plan_f); fftw_free(tmp);
}
template <> void CpuNonlin<double>::run(const double *x, double *y, const double *a) {
#pragma omp parallel for schedule(static) if (B > 1)
    for (int b = 0; b < B; b++) {
        double *t = tmp + 2L * b * K, *yb = y + 2L * b * K;
        fftw_execute_dft((fftw_plan)plan_b, (fftw_complex *)(x + 2L * b * K), (fftw_complex *)t);
        poly(t, K, a, 1.0 / K);
        fftw_execute_dft((fftw_plan)plan_f, (fftw_complex *)t, (fftw_complex *)yb);
    }
}
template <> CpuNonlin<float>::CpuNonlin(int K_, int B_) : K(K_), B(B_) {
    tmp = (float *)fftwf_malloc(sizeof(float) * 2 * (size_t)K * B);
    unsigned fl = K > (1 << 18) ? FFTW_ESTIMATE : FFTW_MEASURE;
    float *scr = (float *)fftwf_malloc(sizeof(float) * 2 * (size_t)K);
    plan_b = fftwf_plan_dft_1d(K, (fftwf_complex *)scr, (fftwf_complex *)tmp, FFTW_BACKWARD, fl);
    plan_f = fftwf_plan_dft_1d(K, (fftwf_complex *)tmp, (fftwf_complex *)scr, FFTW_FORWARD, fl);
    fftwf_free(scr);
}
template <> CpuNonlin<float>::~CpuNonlin() {
    fftwf_destroy_plan((fftwf_plan)plan_b); fftwf_destroy_plan((fftwf_plan)plan_f); fftwf_free(tmp);
}
template <> void CpuNonlin<float>::run(const float *x, float *y, const float *a) {
#pragma omp parallel for schedule(static) if (B > 1)
    for (int b = 0; b < B; b++) {
        float *t = tmp + 2L * b * K, *yb = y + 2L * b * K;
        fftwf_execute_dft((fftwf_plan)plan_b, (fftwf_complex *)(x + 2L * b * K), (fftwf_complex *)t);
        poly(t, K, a, 1.0f / K);
        fftwf_execute_dft((fftwf_plan)plan_f, (fftwf_complex *)t, (fftwf_complex *)yb);
    }
}

template void cpu_linear<float>(const float *, const float *, float *, int, int);
template void cpu_linear<double>(const double *, const double *, double *, int, int);
template void cpu_arena<float>(const float *, const float *, float *, int, int, float, float);
template void cpu_arena<double>(const double *, const double *, double *, int, int, double, double);
