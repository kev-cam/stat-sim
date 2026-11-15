// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
#include "cpu_pipe.h"
#include "tables.h"
#include <cmath>
#include <cstring>
#include <fftw3.h>
#include <omp.h>

static inline void mulbins(const float *x, const float *h, float *y, int K) {
#pragma omp simd
    for (int k = 0; k < K; k++) {
        float xr = x[2 * k], xi = x[2 * k + 1], hr = h[2 * k], hi = h[2 * k + 1];
        y[2 * k] = xr * hr - xi * hi;
        y[2 * k + 1] = xr * hi + xi * hr;
    }
}
// y = x * G(|x|), G from a uniform table over |x| in [0, amax]
static inline void tab(float *t, int K, const float *T, float amax, float scale) {
    const float s = (TAB_N - 1) / amax;
    for (int k = 0; k < K; k++) {
        float xr = t[2 * k] * scale, xi = t[2 * k + 1] * scale;
        float u = std::sqrt(xr * xr + xi * xi) * s;
        if (u > TAB_N - 1.001f) u = TAB_N - 1.001f;
        int i = (int)u;
        float f = u - i;
        float gr = T[2 * i] + f * (T[2 * i + 2] - T[2 * i]), gi = T[2 * i + 1] + f * (T[2 * i + 3] - T[2 * i + 1]);
        t[2 * k] = xr * gr - xi * gi;
        t[2 * k + 1] = xr * gi + xi * gr;
    }
}
CpuPipe::CpuPipe(int M_, int B_, int K_) : M(M_), B(B_), K(K_) {
    t = (float *)fftwf_malloc(sizeof(float) * 2 * (size_t)M * B * K);
    float *a = (float *)fftwf_malloc(sizeof(float) * 2 * K), *b = (float *)fftwf_malloc(sizeof(float) * 2 * K);
    pb = fftwf_plan_dft_1d(K, (fftwf_complex *)a, (fftwf_complex *)b, FFTW_BACKWARD, FFTW_MEASURE);
    pf = fftwf_plan_dft_1d(K, (fftwf_complex *)a, (fftwf_complex *)b, FFTW_FORWARD, FFTW_MEASURE);
    fftwf_free(a); fftwf_free(b);
}
CpuPipe::~CpuPipe() { fftwf_destroy_plan((fftwf_plan)pb); fftwf_destroy_plan((fftwf_plan)pf); fftwf_free(t); }

void CpuPipe::run(const float *x, float *y, const float *htx, const float *hrx, const float *G) {
    const long MB = (long)M * B;
    // TX chain: channel filter -> PA -> spectrum at the antenna feed (into t)
#pragma omp parallel
    {
        float *u = (float *)fftwf_malloc(sizeof(float) * 2 * K), *v = (float *)fftwf_malloc(sizeof(float) * 2 * K);
#pragma omp for schedule(static)
        for (long s = 0; s < MB; s++) {
            mulbins(x + 2 * s * K, htx, u, K);
            fftwf_execute_dft((fftwf_plan)pb, (fftwf_complex *)u, (fftwf_complex *)v);
            tab(v, K, PA_TAB, PA_AMAX, 1.0f / K);
            fftwf_execute_dft((fftwf_plan)pf, (fftwf_complex *)v, (fftwf_complex *)(t + 2 * s * K));
        }
        // free space: every antenna hears every other one
#pragma omp for schedule(static)
        for (int j = 0; j < M; j++) {
            float *yj = y + 2L * j * B * K;
            memset(yj, 0, sizeof(float) * 2 * B * K);
            for (int i = 0; i < M; i++) {
                const float *g = G + 2L * ((long)j * M + i) * K;
                for (int b = 0; b < B; b++) {
                    const float *xi_ = t + 2L * ((long)i * B + b) * K;
                    float *o = yj + 2L * b * K;
#pragma omp simd
                    for (int k = 0; k < K; k++) {
                        float xr = xi_[2 * k], xi = xi_[2 * k + 1], gr = g[2 * k], gi = g[2 * k + 1];
                        o[2 * k] += xr * gr - xi * gi;
                        o[2 * k + 1] += xr * gi + xi * gr;
                    }
                }
            }
        }
        // RX chain: LNA -> mixer + channel filter (per-bin complex gain)
#pragma omp for schedule(static)
        for (long s = 0; s < MB; s++) {
            fftwf_execute_dft((fftwf_plan)pb, (fftwf_complex *)(y + 2 * s * K), (fftwf_complex *)v);
            tab(v, K, LNA_TAB, LNA_AMAX, 1.0f / K);
            fftwf_execute_dft((fftwf_plan)pf, (fftwf_complex *)v, (fftwf_complex *)u);
            mulbins(u, hrx, y + 2 * s * K, K);
        }
        fftwf_free(u); fftwf_free(v);
    }
}
