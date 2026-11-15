// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
// Real-time factor of a time-windowed spectral radio pipeline on a GPU.
//
// M radios each transmit B OFDM symbols (K bins, one time-tagged spectral event
// per symbol) in a window.  Per window, entirely on the device:
//   TX:    channel filter -> PA (fitted class-E table, IFFT/table/FFT)
//   air:   arena resolution, y_j = sum_i G_ij(f) x_i   (precomputed Friis coupling)
//   RX:    LNA (fitted sky130 table) -> mixer + channel filter
// Nothing is synchronised between stages; one sync per window.
// Real-time factor = simulated air time of the window / wall time.
#include "cpu_pipe.h"
#include "tables.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cuda_runtime.h>
#include <cufft.h>
#include <functional>
#include <omp.h>
#include <vector>

#define CK(e) do { cudaError_t _e = (e); if (_e != cudaSuccess) { \
    fprintf(stderr, "CUDA error %s at %s:%d\n", cudaGetErrorString(_e), __FILE__, __LINE__); exit(1); } } while (0)
#define FK(e) do { cufftResult _e = (e); if (_e != CUFFT_SUCCESS) { \
    fprintf(stderr, "cuFFT error %d at %s:%d\n", (int)_e, __FILE__, __LINE__); exit(1); } } while (0)

static const double C0 = 299792458.0, T_SYM = 4e-6;   // 802.11 OFDM symbol

__global__ void k_mul(const float *x, const float *h, float *y, long n, int K) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    int k = (int)(i % K);
    float xr = x[2 * i], xi = x[2 * i + 1], hr = h[2 * k], hi = h[2 * k + 1];
    y[2 * i] = xr * hr - xi * hi;
    y[2 * i + 1] = xr * hi + xi * hr;
}
__global__ void k_tab(float *t, long n, const float *T, float amax, float scale) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    float xr = t[2 * i] * scale, xi = t[2 * i + 1] * scale;
    float u = sqrtf(xr * xr + xi * xi) * ((TAB_N - 1) / amax);
    if (u > TAB_N - 1.001f) u = TAB_N - 1.001f;
    int j = (int)u;
    float f = u - j;
    float gr = T[2 * j] + f * (T[2 * j + 2] - T[2 * j]), gi = T[2 * j + 1] + f * (T[2 * j + 3] - T[2 * j + 1]);
    t[2 * i] = xr * gr - xi * gi;
    t[2 * i + 1] = xr * gi + xi * gr;
}
// one thread per (j, b, k): sum over transmitting antennas i
__global__ void k_arena(const float *x, const float *G, float *y, int M, int B, int K) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long BK = (long)B * K;
    if (idx >= M * BK) return;
    int j = (int)(idx / BK);
    long bk = idx % BK;
    int k = (int)(bk % K);
    float sr = 0, si = 0;
    const float *g = G + 2 * ((long)j * M * K + k);
    for (int i = 0; i < M; i++) {
        float xr = x[2 * (i * BK + bk)], xi = x[2 * (i * BK + bk) + 1];
        float gr = g[2L * i * K], gi = g[2L * i * K + 1];
        sr += xr * gr - xi * gi;
        si += xr * gi + xi * gr;
    }
    y[2 * idx] = sr;
    y[2 * idx + 1] = si;
}

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
static double timeit(const std::function<void()> &f, double budget = 0.3) {
    for (int i = 0; i < 2; i++) f();
    std::vector<double> t;
    double t0 = now();
    while ((now() - t0 < budget || t.size() < 3) && t.size() < 5000) { double a = now(); f(); t.push_back(now() - a); }
    std::sort(t.begin(), t.end());
    return t[t.size() / 2];
}
static inline int blocks(long n) { return (int)((n + 255) / 256); }

static void bench(int M, int B, int K, bool do_cpu) {
    long n = (long)M * B * K;
    float *hx, *hy, *dx, *dt, *dy, *dhtx, *dhrx, *dG, *dpa, *dlna;
    CK(cudaMallocHost(&hx, 8 * n)); CK(cudaMallocHost(&hy, 8 * n));
    CK(cudaMalloc(&dx, 8 * n)); CK(cudaMalloc(&dt, 8 * n)); CK(cudaMalloc(&dy, 8 * n));
    CK(cudaMalloc(&dhtx, 8L * K)); CK(cudaMalloc(&dhrx, 8L * K)); CK(cudaMalloc(&dG, 8L * M * M * K));
    CK(cudaMalloc(&dpa, sizeof(PA_TAB))); CK(cudaMalloc(&dlna, sizeof(LNA_TAB)));
    std::vector<float> htx(2 * K), hrx(2 * K), G(2L * M * M * K);
    srand(1);
    // QPSK-like unit bins scaled so the PA runs into compression
    for (long i = 0; i < 2 * n; i++) hx[i] = (rand() & 1 ? 1.0f : -1.0f) * 0.035f;
    for (int k = 0; k < K; k++) {
        double w = 0.5 - 0.5 * cos(2 * M_PI * (k + 0.5) / K);           // band-shaping
        htx[2 * k] = (float)(0.5 + 0.5 * w); htx[2 * k + 1] = 0;
        hrx[2 * k] = (float)(cos(0.3 * k) * (0.5 + 0.5 * w)); hrx[2 * k + 1] = (float)(sin(0.3 * k) * (0.5 + 0.5 * w));
    }
    std::vector<double> px(M), py(M), pz(M);
    for (int i = 0; i < M; i++) { px[i] = 100.0 * rand() / RAND_MAX; py[i] = 100.0 * rand() / RAND_MAX; pz[i] = 10.0 * rand() / RAND_MAX; }
    for (int j = 0; j < M; j++)
        for (int i = 0; i < M; i++)
            for (int k = 0; k < K; k++) {
                double re = 0, im = 0;
                if (i != j) {
                    double d = std::max(0.1, sqrt((px[i] - px[j]) * (px[i] - px[j]) + (py[i] - py[j]) * (py[i] - py[j]) + (pz[i] - pz[j]) * (pz[i] - pz[j])));
                    double f = 2.4e9 + 20e6 * (k - K / 2) / K, a = C0 / (4 * M_PI * f * d), ph = -2 * M_PI * f * d / C0;
                    re = a * cos(ph); im = a * sin(ph);                 // phase formed in double, stored as float
                }
                G[2 * (((long)j * M + i) * K + k)] = (float)re; G[2 * (((long)j * M + i) * K + k) + 1] = (float)im;
            }
    CK(cudaMemcpy(dx, hx, 8 * n, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dhtx, htx.data(), 8L * K, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dhrx, hrx.data(), 8L * K, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dG, G.data(), 8L * M * M * K, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dpa, PA_TAB, sizeof(PA_TAB), cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dlna, LNA_TAB, sizeof(LNA_TAB), cudaMemcpyHostToDevice));
    cufftHandle plan;
    int kk = K;
    FK(cufftPlanMany(&plan, 1, &kk, nullptr, 1, K, nullptr, 1, K, CUFFT_C2C, M * B));

    double t_stage[3] = {0, 0, 0};
    auto tx = [&] {
        k_mul<<<blocks(n), 256>>>(dx, dhtx, dt, n, K);
        FK(cufftExecC2C(plan, (cufftComplex *)dt, (cufftComplex *)dt, CUFFT_INVERSE));
        k_tab<<<blocks(n), 256>>>(dt, n, dpa, PA_AMAX, 1.0f / K);
        FK(cufftExecC2C(plan, (cufftComplex *)dt, (cufftComplex *)dt, CUFFT_FORWARD));
    };
    auto air = [&] { k_arena<<<blocks(n), 256>>>(dt, dG, dy, M, B, K); };
    auto rx = [&] {
        FK(cufftExecC2C(plan, (cufftComplex *)dy, (cufftComplex *)dy, CUFFT_INVERSE));
        k_tab<<<blocks(n), 256>>>(dy, n, dlna, LNA_AMAX, 1.0f / K);
        FK(cufftExecC2C(plan, (cufftComplex *)dy, (cufftComplex *)dy, CUFFT_FORWARD));
        k_mul<<<blocks(n), 256>>>(dy, dhrx, dy, n, K);
    };
    double g = timeit([&] { tx(); air(); rx(); CK(cudaDeviceSynchronize()); });
    t_stage[0] = timeit([&] { tx(); CK(cudaDeviceSynchronize()); }, 0.1);
    t_stage[1] = timeit([&] { air(); CK(cudaDeviceSynchronize()); }, 0.1);
    tx(); air(); rx();
    CK(cudaMemcpy(hy, dy, 8 * n, cudaMemcpyDeviceToHost));

    double c = NAN, err = NAN;
    if (do_cpu) {
        CpuPipe cpu(M, B, K);
        std::vector<float> ref(2 * n);
        c = timeit([&] { cpu.run(hx, ref.data(), htx.data(), hrx.data(), G.data()); }, 0.3);
        double num = 0, den = 0;
        for (long i = 0; i < 2 * n; i++) { double d = (double)hy[i] - ref[i]; num += d * d; den += (double)ref[i] * ref[i]; }
        err = sqrt(num / den);
    }
    double sim = B * T_SYM;
    printf("%d,%d,%d,%.1f,%.1f,%.1f,%.1f,%.1f,%.3f,%.3f,%.1f,%.1e\n", M, B, K, sim * 1e6, g * 1e6, t_stage[0] * 1e6, t_stage[1] * 1e6,
           c * 1e6, sim / g, sim / c, c / g, err);
    fflush(stdout);
    FK(cufftDestroy(plan));
    cudaFreeHost(hx); cudaFreeHost(hy); cudaFree(dx); cudaFree(dt); cudaFree(dy); cudaFree(dhtx); cudaFree(dhrx); cudaFree(dG); cudaFree(dpa); cudaFree(dlna);
}

int main(int argc, char **argv) {
    int K = argc > 1 ? atoi(argv[1]) : 64;
    cudaDeviceProp p;
    CK(cudaGetDeviceProperties(&p, 0));
    fprintf(stderr, "GPU: %s  CPU threads: %d  K=%d\n", p.name, omp_get_max_threads(), K);
    printf("M,B,K,window_us,gpu_us,gpu_tx_us,gpu_air_us,cpuN_us,rtf_gpu,rtf_cpuN,gpu_vs_cpuN,relerr\n");
    for (int M : {2, 8, 32, 128, 512})
        for (int B : {1, 4, 16, 64, 256, 1024, 4096}) {
            if ((long)M * B > (1 << 18)) continue;
            bench(M, B, K, (double)M * M * B * K < 3e10);
        }
    return 0;
}
