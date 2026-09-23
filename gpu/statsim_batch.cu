// stat-sim GPU-batching PROTOTYPE — the SIMT kernel behind "share the driver across warps".
//
// One thread = one LANE = one whole-chain coherent Monte-Carlo draw of an N-stage NCL carry
// chain. The DRIVER (per-stage in-context means + per-stage sigma) is broadcast read-only from
// __constant__ memory — identical across all lanes, exactly the "share the driver" shape. Lanes
// differ only in their per-lane Philox RNG stream. The rho0 nearest-neighbor correlation is
// carried IN-LANE by an MA(1) draw x_i = alpha*w_i + beta*w_{i+1} (alpha*beta=rho0,
// alpha^2+beta^2=1), giving chain variance sum sigma_i^2 + 2*rho0*sum sigma_i*sigma_{i+1} ==
// statsim_delay.predict_ctx. This is the numpy reference gpu_statsim_ref.py, mapped to CUDA.
//
// Build (no GPU needed):  ../.. /sv2ghdl/gpubuild/gpu-cc.sh -O2 -arch=sm_75 -o statsim_batch statsim_batch.cu
// Run (on any GPU host):  ./statsim_batch [n_lanes]
//
// Validation criteria mirror the numpy ref: (a) MC-with-rho0 vs analytic golden < 1%,
// (b) vs transistor-MC ground truth < 6%, (c) rho0-induced sigma shift > 4%.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <curand_kernel.h>
#include "statsim_model.h"

// Never trust a GPU that silently didn't run: abort on any CUDA error so a
// failed launch/copy can't print fabricated moments under the PROVEN banner.
#define CUDA_CHECK(call) do { cudaError_t _e = (call); if (_e != cudaSuccess) { \
    fprintf(stderr, "CUDA ERROR %s at %s:%d -> %s\n", #call, __FILE__, __LINE__, \
            cudaGetErrorString(_e)); exit(2); } } while (0)

#define MAXN 64
__constant__ double c_mu[MAXN];   // per-stage in-context mean (ps)
__constant__ double c_sd[MAXN];   // per-stage sd = sigma_frac*mu (ps)
__constant__ int    c_N;
__constant__ double c_alpha;      // MA(1) coeffs (set per rho0)
__constant__ double c_beta;

// double atomicAdd is native on sm_60+ (we target sm_75+).
__global__ void batch(unsigned long long seed, long long n_lanes,
                      double *g_sum, double *g_sumsq) {
    long long tid = blockIdx.x * (long long)blockDim.x + threadIdx.x;
    long long stride = (long long)gridDim.x * blockDim.x;
    double local_sum = 0.0, local_sumsq = 0.0;
    curandStatePhilox4_32_10_t st;
    for (long long lane = tid; lane < n_lanes; lane += stride) {
        curand_init(seed, (unsigned long long)lane, 0, &st);   // per-lane counter-based stream
        double w_prev = curand_normal_double(&st);             // w_0
        double S = 0.0;
        for (int i = 0; i < c_N; i++) {
            double w_next = curand_normal_double(&st);          // w_{i+1}
            double x = c_alpha * w_prev + c_beta * w_next;      // unit-var, nearest-neighbor corr
            S += c_mu[i] + c_sd[i] * x;
            w_prev = w_next;
        }
        local_sum += S;
        local_sumsq += S * S;
    }
    // block reduction in shared memory, then one atomicAdd per block
    extern __shared__ double sh[];               // 2*blockDim.x doubles
    double *ssum = sh, *ssq = sh + blockDim.x;
    ssum[threadIdx.x] = local_sum; ssq[threadIdx.x] = local_sumsq;
    __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) { ssum[threadIdx.x] += ssum[threadIdx.x + s];
                               ssq[threadIdx.x]  += ssq[threadIdx.x + s]; }
        __syncthreads();
    }
    if (threadIdx.x == 0) { atomicAdd(g_sum, ssum[0]); atomicAdd(g_sumsq, ssq[0]); }
}

static void ma1(double rho0, double *a, double *b) {
    if (rho0 == 0.0) { *a = 1.0; *b = 0.0; return; }
    *a = (sqrt(1 + 2*rho0) + sqrt(1 - 2*rho0)) / 2.0;
    *b = (sqrt(1 + 2*rho0) - sqrt(1 - 2*rho0)) / 2.0;
}

// build the per-(N,kvt) stage mean/sd arrays (in-context tiling) and push to constant mem
static void load_driver(int N, int kvt_idx, double rho0) {
    double mu[MAXN], sd[MAXN];
    for (int i = 0; i < N; i++) {
        double m = (i == 0) ? T_FIRST : (i == N - 1 ? T_LAST : T_CTX);
        mu[i] = m; sd[i] = SIGMA_FRAC[kvt_idx] * m;
    }
    double a, b; ma1(rho0, &a, &b);
    CUDA_CHECK(cudaMemcpyToSymbol(c_mu, mu, N * sizeof(double)));
    CUDA_CHECK(cudaMemcpyToSymbol(c_sd, sd, N * sizeof(double)));
    CUDA_CHECK(cudaMemcpyToSymbol(c_N, &N, sizeof(int)));
    CUDA_CHECK(cudaMemcpyToSymbol(c_alpha, &a, sizeof(double)));
    CUDA_CHECK(cudaMemcpyToSymbol(c_beta, &b, sizeof(double)));
}

static void run(int N, int kvt_idx, double rho0, long long n_lanes,
                double *mu_out, double *sd_out) {
    load_driver(N, kvt_idx, rho0);
    double *d_sum, *d_sq;
    CUDA_CHECK(cudaMalloc(&d_sum, sizeof(double))); CUDA_CHECK(cudaMalloc(&d_sq, sizeof(double)));
    CUDA_CHECK(cudaMemset(d_sum, 0, sizeof(double))); CUDA_CHECK(cudaMemset(d_sq, 0, sizeof(double)));
    int block = 256, grid = 1024;
    if (block & (block - 1)) { fprintf(stderr, "block %d not power of 2\n", block); exit(2); }
    batch<<<grid, block, 2 * block * sizeof(double)>>>(0x5A17ULL, n_lanes, d_sum, d_sq);
    CUDA_CHECK(cudaGetLastError());          // launch config / arch mismatch
    CUDA_CHECK(cudaDeviceSynchronize());     // async execution faults
    double sum, sq;
    CUDA_CHECK(cudaMemcpy(&sum, d_sum, sizeof(double), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(&sq, d_sq, sizeof(double), cudaMemcpyDeviceToHost));
    double mean = sum / n_lanes, var = sq / n_lanes - mean * mean;
    *mu_out = mean; *sd_out = sqrt(var > 0 ? var : 0);
    CUDA_CHECK(cudaFree(d_sum)); CUDA_CHECK(cudaFree(d_sq));
}

int main(int argc, char **argv) {
    long long n_lanes = (argc > 1) ? atoll(argv[1]) : 1000000LL;
    printf("stat-sim GPU batched-MC — %lld lanes/launch, shared driver + MA(1) rho0=%.2f\n", n_lanes, RHO0);
    double worst_gt = 0, worst_an = 0, min_shift = 1e9;
    const int Ns[2] = {4, 8};
    for (int ni = 0; ni < 2; ni++) {
        int N = Ns[ni];
        const double *gmu = (N == 4) ? GT4_MU : GT8_MU;
        const double *gsd = (N == 4) ? GT4_SD : GT8_SD;
        const double *amu = (N == 4) ? AN4_MU : AN8_MU;   // analytic golden predict_ctx
        const double *asd = (N == 4) ? AN4_SD : AN8_SD;
        printf("\n--- N=%d ripple carry chain ---\n", N);
        printf("  kvt |  MC rho0=on (mu,sd) | analytic(mu,sd) | real MC (mu,sd) | vs golden | vs gt | sd-shift\n");
        for (int k = 0; k < NKVT; k++) {
            double mon, son, moff, soff;
            run(N, k, RHO0, n_lanes, &mon, &son);
            run(N, k, 0.0,  n_lanes, &moff, &soff);
            double e_an = (son - asd[k]) / asd[k] * 100.0;   // (a) tight faithfulness check
            double e_gt = (son - gsd[k]) / gsd[k] * 100.0;   // (b) vs transistor MC
            double shift = (son - soff) / son * 100.0;       // (c) rho0 effect
            if (fabs(e_an) > worst_an) worst_an = fabs(e_an);
            if (fabs(e_gt) > worst_gt) worst_gt = fabs(e_gt);
            if (shift < min_shift) min_shift = shift;
            printf("   %d  | (%7.1f,%5.1f)   | (%7.1f,%5.1f) | (%6.1f,%4.1f) |  %+5.2f%%  | %+5.1f%%|  +%4.1f%%\n",
                   KVT[k], mon, son, amu[k], asd[k], gmu[k], gsd[k], e_an, e_gt, shift);
        }
    }
    printf("\nDECISION\n");
    printf("  (a) vs ANALYTIC golden predict_ctx : worst |sd err| = %.2f%%  (< 1%% : faithful reduction)\n", worst_an);
    printf("  (b) vs TRANSISTOR-MC ground truth  : worst |sd err| = %.1f%%   (< 6%% : reproduces physics)\n", worst_gt);
    printf("  (c) rho0-induced sd shift          : >= %.1f%%          (> 4%% : reduction carries correlation)\n", min_shift);
    printf("  -> %s\n", (worst_an < 1.0 && worst_gt < 6.0 && min_shift > 4.0)
           ? "PROVEN on GPU (matches the numpy reference, the analytic golden, and the transistor-MC ground truth)."
           : "CHECK: does not meet criteria — compare against gpu_statsim_ref.py.");
    return 0;
}
