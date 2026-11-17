// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
// GPU vs CPU for event-driven spectral RF signals (arrays of complex bins).
//
// Three operations, each on B signals of K complex bins:
//   linear  y = H .* x                      (filter / amplifier / channel)
//   nonlin  IFFT -> polynomial -> FFT       (PA / mixer nonlinearity, HB style)
//   arena   Friis-coupled sum over M antennas per bin (antenna arena resolution)
//
// Modes: cpu1 (one thread), cpuN (all threads), gpu_res (data lives on the GPU,
// one launch + sync per event), gpu_rt (data lives in host memory: copy in,
// compute, copy out -- what an nvc signal update would cost today).
#include "cpu.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cuda_runtime.h>
#include <cufft.h>
#include <functional>
#include <omp.h>
#include <string>
#include <vector>

#define CK(e) do { cudaError_t _e = (e); if (_e != cudaSuccess) { \
    fprintf(stderr, "CUDA error %s at %s:%d\n", cudaGetErrorString(_e), __FILE__, __LINE__); exit(1); } } while (0)
#define FK(e) do { cufftResult _e = (e); if (_e != CUFFT_SUCCESS) { \
    fprintf(stderr, "cuFFT error %d at %s:%d\n", (int)_e, __FILE__, __LINE__); exit(1); } } while (0)

static const double C0 = 299792458.0;

template <class T> __global__ void k_linear(const T *x, const T *h, T *y, long n, int Kmask) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    int k = (int)(i & Kmask);
    T xr = x[2 * i], xi = x[2 * i + 1], hr = h[2 * k], hi = h[2 * k + 1];
    y[2 * i] = xr * hr - xi * hi;
    y[2 * i + 1] = xr * hi + xi * hr;
}

template <class T> __global__ void k_poly(T *t, long n, T a0, T a1, T a2, T a3, T a4, T a5, T scale) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    T xr = t[2 * i] * scale, xi = t[2 * i + 1] * scale;
    T p = xr * xr + xi * xi;
    T gr = a0 + p * (a2 + p * a4), gi = a1 + p * (a3 + p * a5);
    t[2 * i] = xr * gr - xi * gi;
    t[2 * i + 1] = xr * gi + xi * gr;
}

template <class T> __global__ void k_arena(const T *x, const T *dist, T *y, int M, int K, T f0, T df) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= (long)M * K) return;
    int j = (int)(idx / K), k = (int)(idx % K);
    T f = f0 + df * k;
    T amp = (T)(C0 / (4 * M_PI)) / f;
    T w = (T)(-2 * M_PI / C0) * f;
    T sr = 0, si = 0;
    for (int i = 0; i < M; i++) {
        if (i == j) continue;
        T d = dist[i * M + j];
        T a = amp / d, s, c;
        sincos(w * d, &s, &c);
        T xr = x[2 * ((long)i * K + k)], xi = x[2 * ((long)i * K + k) + 1];
        sr += a * (xr * c - xi * s);
        si += a * (xr * s + xi * c);
    }
    y[2 * idx] = sr;
    y[2 * idx + 1] = si;
}

// float data, but the propagation phase is formed and range-reduced in double
// (2 pi f d / c is thousands of radians: float loses ~4 digits of phase there).
__global__ void k_arena_mix(const float *x, const double *dist, float *y, int M, int K, double f0, double df) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= (long)M * K) return;
    int j = (int)(idx / K), k = (int)(idx % K);
    double f = f0 + df * k;
    float amp = (float)((C0 / (4 * M_PI)) / f);
    double w = f / C0;                     // cycles per metre
    float sr = 0, si = 0;
    for (int i = 0; i < M; i++) {
        if (i == j) continue;
        double d = dist[i * M + j];
        double cyc = w * d;
        float ph = (float)(-2 * M_PI * (cyc - rint(cyc)));
        float a = amp / (float)d, s, c;
        sincosf(ph, &s, &c);
        float xr = x[2 * ((long)i * K + k)], xi = x[2 * ((long)i * K + k) + 1];
        sr += a * (xr * c - xi * s);
        si += a * (xr * s + xi * c);
    }
    y[2 * idx] = sr;
    y[2 * idx + 1] = si;
}

static double now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
// median wall time of f() in seconds
static double timeit(const std::function<void()> &f, double budget = 0.25) {
    for (int i = 0; i < 3; i++) f();
    std::vector<double> t;
    double t0 = now();
    while ((now() - t0 < budget || t.size() < 5) && t.size() < 20000) {
        double a = now(); f(); t.push_back(now() - a);
    }
    std::sort(t.begin(), t.end());
    return t[t.size() / 2];
}
template <class T> static double relerr(const T *a, const T *ref, long n) {
    double num = 0, den = 0;
    for (long i = 0; i < n; i++) { double d = (double)a[i] - ref[i]; num += d * d; den += (double)ref[i] * ref[i]; }
    return den > 0 ? sqrt(num / den) : sqrt(num);
}
static void fill(float *p, long n) { for (long i = 0; i < n; i++) p[i] = (float)(rand() / (double)RAND_MAX - 0.5); }
static void fill(double *p, long n) { for (long i = 0; i < n; i++) p[i] = rand() / (double)RAND_MAX - 0.5; }

static int g_threads;
static void row(const char *op, const char *ty, int M, int K, int B, double c1, double cn, double gres, double grt, double err) {
    printf("%s,%s,%d,%d,%d,%.3f,%.3f,%.3f,%.3f,%.2f,%.2f,%.2f,%.2f,%.1e\n", op, ty, M, K, B,
           c1 * 1e6, cn * 1e6, gres * 1e6, grt * 1e6, c1 / gres, c1 / grt, cn / gres, cn / grt, err);
    fflush(stdout);
}
template <class T> static const char *tyname();
template <> const char *tyname<float>() { return "f32"; }
template <> const char *tyname<double>() { return "f64"; }

template <class T> static void alloc(T **host, T **dev, long n) {
    CK(cudaMallocHost(host, sizeof(T) * n));
    CK(cudaMalloc(dev, sizeof(T) * n));
}
static inline int blocks(long n) { return (int)((n + 255) / 256); }

template <class T> static void bench_linear(int K, int B) {
    long n = (long)K * B;
    T *hx, *hy, *hh, *href, *dx, *dy, *dh;
    alloc(&hx, &dx, 2 * n); alloc(&hy, &dy, 2 * n); alloc(&hh, &dh, 2L * K);
    href = (T *)malloc(sizeof(T) * 2 * n);
    fill(hx, 2 * n); fill(hh, 2L * K);
    CK(cudaMemcpy(dx, hx, sizeof(T) * 2 * n, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dh, hh, sizeof(T) * 2 * K, cudaMemcpyHostToDevice));
    omp_set_num_threads(1);
    double c1 = timeit([&] { cpu_linear(hx, hh, href, K, B); });
    omp_set_num_threads(g_threads);
    double cn = timeit([&] { cpu_linear(hx, hh, href, K, B); });
    double gres = timeit([&] { k_linear<T><<<blocks(n), 256>>>(dx, dh, dy, n, K - 1); CK(cudaDeviceSynchronize()); });
    double grt = timeit([&] {
        CK(cudaMemcpy(dx, hx, sizeof(T) * 2 * n, cudaMemcpyHostToDevice));
        k_linear<T><<<blocks(n), 256>>>(dx, dh, dy, n, K - 1);
        CK(cudaMemcpy(hy, dy, sizeof(T) * 2 * n, cudaMemcpyDeviceToHost));
    });
    row("linear", tyname<T>(), 1, K, B, c1, cn, gres, grt, relerr(hy, href, 2 * n));
    cudaFreeHost(hx); cudaFreeHost(hy); cudaFreeHost(hh); cudaFree(dx); cudaFree(dy); cudaFree(dh); free(href);
}

static void fft_exec(cufftHandle p, float *in, float *out, int dir) { FK(cufftExecC2C(p, (cufftComplex *)in, (cufftComplex *)out, dir)); }
static void fft_exec(cufftHandle p, double *in, double *out, int dir) { FK(cufftExecZ2Z(p, (cufftDoubleComplex *)in, (cufftDoubleComplex *)out, dir)); }

template <class T> static void bench_nonlin(int K, int B) {
    long n = (long)K * B;
    T *hx, *hy, *href, *dx, *dy;
    alloc(&hx, &dx, 2 * n); alloc(&hy, &dy, 2 * n);
    href = (T *)malloc(sizeof(T) * 2 * n);
    fill(hx, 2 * n);
    T a[6] = {(T)10, (T)0.5, (T)-3, (T)0.8, (T)0.4, (T)-0.2};
    CK(cudaMemcpy(dx, hx, sizeof(T) * 2 * n, cudaMemcpyHostToDevice));
    cufftHandle plan;
    int kk = K;
    FK(cufftPlanMany(&plan, 1, &kk, nullptr, 1, K, nullptr, 1, K, sizeof(T) == 4 ? CUFFT_C2C : CUFFT_Z2Z, B));
    CpuNonlin<T> cpu(K, B);
    omp_set_num_threads(1);
    double c1 = timeit([&] { cpu.run(hx, href, a); });
    omp_set_num_threads(g_threads);
    double cn = timeit([&] { cpu.run(hx, href, a); });
    auto gpu = [&] {
        fft_exec(plan, dx, dy, CUFFT_INVERSE);
        k_poly<T><<<blocks(n), 256>>>(dy, n, a[0], a[1], a[2], a[3], a[4], a[5], (T)1 / K);
        fft_exec(plan, dy, dy, CUFFT_FORWARD);
    };
    double gres = timeit([&] { gpu(); CK(cudaDeviceSynchronize()); });
    double grt = timeit([&] {
        CK(cudaMemcpy(dx, hx, sizeof(T) * 2 * n, cudaMemcpyHostToDevice));
        gpu();
        CK(cudaMemcpy(hy, dy, sizeof(T) * 2 * n, cudaMemcpyDeviceToHost));
    });
    row("nonlin", tyname<T>(), 1, K, B, c1, cn, gres, grt, relerr(hy, href, 2 * n));
    FK(cufftDestroy(plan));
    cudaFreeHost(hx); cudaFreeHost(hy); cudaFree(dx); cudaFree(dy); free(href);
}

template <class T> static void bench_arena(int M, int K) {
    long n = (long)M * K;
    T *hx, *hy, *hd, *href, *dx, *dy, *dd;
    alloc(&hx, &dx, 2 * n); alloc(&hy, &dy, 2 * n); alloc(&hd, &dd, (long)M * M);
    href = (T *)malloc(sizeof(T) * 2 * n);
    fill(hx, 2 * n);
    // antennas scattered in a 100 m x 100 m x 10 m volume
    std::vector<double> px(M), py(M), pz(M);
    for (int i = 0; i < M; i++) { px[i] = 100.0 * rand() / RAND_MAX; py[i] = 100.0 * rand() / RAND_MAX; pz[i] = 10.0 * rand() / RAND_MAX; }
    for (int i = 0; i < M; i++)
        for (int j = 0; j < M; j++)
            hd[i * M + j] = (T)std::max(0.1, sqrt((px[i] - px[j]) * (px[i] - px[j]) + (py[i] - py[j]) * (py[i] - py[j]) + (pz[i] - pz[j]) * (pz[i] - pz[j])));
    T f0 = (T)2.4e9, df = (T)(20e6 / K);
    CK(cudaMemcpy(dx, hx, sizeof(T) * 2 * n, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dd, hd, sizeof(T) * M * M, cudaMemcpyHostToDevice));
    double budget = (double)M * M * K > 3e8 ? 0.0 : 0.25;
    omp_set_num_threads(1);
    double c1 = timeit([&] { cpu_arena(hx, hd, href, M, K, f0, df); }, budget);
    omp_set_num_threads(g_threads);
    double cn = timeit([&] { cpu_arena(hx, hd, href, M, K, f0, df); }, budget);
    double gres = timeit([&] { k_arena<T><<<blocks(n), 256>>>(dx, dd, dy, M, K, f0, df); CK(cudaDeviceSynchronize()); });
    double grt = timeit([&] {
        CK(cudaMemcpy(dx, hx, sizeof(T) * 2 * n, cudaMemcpyHostToDevice));
        k_arena<T><<<blocks(n), 256>>>(dx, dd, dy, M, K, f0, df);
        CK(cudaMemcpy(hy, dy, sizeof(T) * 2 * n, cudaMemcpyDeviceToHost));
    });
    row("arena", tyname<T>(), M, K, 1, c1, cn, gres, grt, relerr(hy, href, 2 * n));
    cudaFreeHost(hx); cudaFreeHost(hy); cudaFreeHost(hd); cudaFree(dx); cudaFree(dy); cudaFree(dd); free(href);
}

// GPU: float data + double phase.  CPU reference: all double.  Reported speedups are
// therefore against the double-precision CPU kernel, the precision nvc uses today.
static void bench_arena_mix(int M, int K) {
    long n = (long)M * K;
    float *hx, *hy, *dx, *dy; double *hd, *dd;
    alloc(&hx, &dx, 2 * n); alloc(&hy, &dy, 2 * n); alloc(&hd, &dd, (long)M * M);
    std::vector<double> x64(2 * n), ref(2 * n);
    fill(hx, 2 * n);
    for (long i = 0; i < 2 * n; i++) x64[i] = hx[i];
    std::vector<double> px(M), py(M), pz(M);
    for (int i = 0; i < M; i++) { px[i] = 100.0 * rand() / RAND_MAX; py[i] = 100.0 * rand() / RAND_MAX; pz[i] = 10.0 * rand() / RAND_MAX; }
    for (int i = 0; i < M; i++)
        for (int j = 0; j < M; j++)
            hd[i * M + j] = std::max(0.1, sqrt((px[i] - px[j]) * (px[i] - px[j]) + (py[i] - py[j]) * (py[i] - py[j]) + (pz[i] - pz[j]) * (pz[i] - pz[j])));
    double f0 = 2.4e9, df = 20e6 / K;
    CK(cudaMemcpy(dx, hx, sizeof(float) * 2 * n, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dd, hd, sizeof(double) * M * M, cudaMemcpyHostToDevice));
    double budget = (double)M * M * K > 3e8 ? 0.0 : 0.25;
    omp_set_num_threads(1);
    double c1 = timeit([&] { cpu_arena(x64.data(), hd, ref.data(), M, K, f0, df); }, budget);
    omp_set_num_threads(g_threads);
    double cn = timeit([&] { cpu_arena(x64.data(), hd, ref.data(), M, K, f0, df); }, budget);
    double gres = timeit([&] { k_arena_mix<<<blocks(n), 256>>>(dx, dd, dy, M, K, f0, df); CK(cudaDeviceSynchronize()); });
    double grt = timeit([&] {
        CK(cudaMemcpy(dx, hx, sizeof(float) * 2 * n, cudaMemcpyHostToDevice));
        k_arena_mix<<<blocks(n), 256>>>(dx, dd, dy, M, K, f0, df);
        CK(cudaMemcpy(hy, dy, sizeof(float) * 2 * n, cudaMemcpyDeviceToHost));
    });
    double num = 0, den = 0;
    for (long i = 0; i < 2 * n; i++) { double d = hy[i] - ref[i]; num += d * d; den += ref[i] * ref[i]; }
    row("arena", "f32+p64", M, K, 1, c1, cn, gres, grt, sqrt(num / den));
    cudaFreeHost(hx); cudaFreeHost(hy); cudaFreeHost(hd); cudaFree(dx); cudaFree(dy); cudaFree(dd);
}

template <class T> static void suite(const std::string &which) {
    if (which == "all" || which == "linear") {
        for (int K = 64; K <= (1 << 22); K *= 4) bench_linear<T>(K, 1);
        for (int B = 16; B <= 65536; B *= 16) bench_linear<T>(64, B);
    }
    if (which == "all" || which == "nonlin") {
        for (int K = 64; K <= (1 << 22); K *= 4) bench_nonlin<T>(K, 1);
        for (int B = 16; B <= 65536; B *= 16) bench_nonlin<T>(64, B);
        for (int B = 16; B <= 4096; B *= 16) bench_nonlin<T>(1024, B);
    }
    if (which == "all" || which == "arena") {
        for (int M = 2; M <= 1024; M *= 2) bench_arena<T>(M, 64);
        for (int M = 2; M <= 1024; M *= 4) bench_arena<T>(M, 1024);
    }
}

int main(int argc, char **argv) {
    std::string which = argc > 1 ? argv[1] : "all";
    g_threads = omp_get_max_threads();
    cudaDeviceProp p;
    CK(cudaGetDeviceProperties(&p, 0));
    fprintf(stderr, "GPU: %s  CPU threads: %d\n", p.name, g_threads);
    printf("op,type,M,K,B,cpu1_us,cpuN_us,gpu_res_us,gpu_rt_us,x_cpu1_res,x_cpu1_rt,x_cpuN_res,x_cpuN_rt,relerr\n");
    suite<float>(which);
    suite<double>(which);
    if (which == "all" || which == "arena") {
        for (int M = 2; M <= 1024; M *= 2) bench_arena_mix(M, 64);
        for (int M = 2; M <= 1024; M *= 4) bench_arena_mix(M, 1024);
    }
    return 0;
}
