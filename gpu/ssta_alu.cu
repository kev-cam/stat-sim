// Design-scale SSTA on the Vortex ALU — the GPU kernel (step 1).
// One thread = one lane = one whole-design COHERENT Monte-Carlo sample: each cell draws its
// delay ONCE (curand), arrival propagates through the levelized DAG reusing that value, so
// reconvergent paths sharing an upstream cone automatically share its realization. Arrival
// array is net-major [net*L + lane] so a warp (consecutive lanes) reads/writes consecutive
// addresses -> fully coalesced. Cells are pre-levelized on the host, so within a lane every
// input was written at an earlier cell index; no __syncthreads needed (lanes are independent).
//
// Build: gpu-cc.sh -O2 -arch=sm_75 -o ssta_alu ssta_alu.cu ; Run: ./ssta_alu [n_lanes]
// Reproduces ssta_alu_ref.py (numpy) mean/sd/p99.9, baked into ssta_alu_data.h.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <curand_kernel.h>
#include "ssta_alu_data.h"

#define CUDA_CHECK(call) do { cudaError_t _e=(call); if(_e!=cudaSuccess){ \
  fprintf(stderr,"CUDA ERR %s @%s:%d: %s\n",#call,__FILE__,__LINE__,cudaGetErrorString(_e)); exit(2);} } while(0)

#define NB 512
__constant__ float HLO, HBIN;

// prefill every net's noise with fresh iid N(0,1); start nets keep this as the "virtual
// predecessor" for level-1 cells, combinational nets get overwritten in ssta().
__global__ void prefill_z(unsigned long long seed, long long L, unsigned long long loff, float *znet) {
    long long lane = blockIdx.x * (long long)blockDim.x + threadIdx.x;
    if (lane >= L) return;
    curandStatePhilox4_32_10_t st; curand_init(seed, (unsigned long long)lane + loff, 0, &st);
    for (int n = 0; n < N_NETS; n++) znet[(size_t)n * L + lane] = (float)curand_normal_double(&st);
}

__global__ void ssta(unsigned long long seed, long long L, unsigned long long loff, float *arr, float *znet,
                     const int *out, const int *nin, const int *in0, const int *in1, const int *in2,
                     const float *mu, const float *sd,
                     const int *endi, double *g_sum, double *g_sq, unsigned int *g_hist) {
    long long lane = blockIdx.x * (long long)blockDim.x + threadIdx.x;
    // Every thread must reach the block reduction (no early return) or the last partial
    // block sums uninitialized shared memory -> corrupts sumsq -> nan variance. Threads
    // with lane>=L contribute 0 and skip the (out-of-bounds) arr work + histogram.
    double my_sum = 0.0, my_sq = 0.0;
    if (lane < L) {
        curandStatePhilox4_32_10_t st; curand_init(seed, (unsigned long long)lane + loff, 0, &st);
        for (int c = 0; c < N_CELLS; c++) {
            int k = nin[c]; float base = 0.f; int crit = out[c];  // nin==0 -> own prefill noise
            if (k > 0) { int i0 = in0[c]; base = arr[(size_t)i0 * L + lane]; crit = i0;
                if (k > 1) { float v = arr[(size_t)in1[c] * L + lane]; if (v > base) { base = v; crit = in1[c]; } }
                if (k > 2) { float v = arr[(size_t)in2[c] * L + lane]; if (v > base) { base = v; crit = in2[c]; } } }
            float zpred = znet[(size_t)crit * L + lane];          // critical predecessor's noise
            float s = sd[c];
            if (s > 0.f) {                                        // correlated draw: MA(1) with crit pred
                float zc = (float)curand_normal_double(&st);
                float x = MA_A * zc + MA_B * zpred;               // unit-var, nn-corr rho0
                arr[(size_t)out[c] * L + lane] = base + mu[c] + s * x;
                znet[(size_t)out[c] * L + lane] = zc;             // store own noise for successors
            } else {                                             // zero-delay buffer: pass noise through
                arr[(size_t)out[c] * L + lane] = base;
                znet[(size_t)out[c] * L + lane] = zpred;
            }
        }
        float crit = 0.f;
        for (int e = 0; e < N_END; e++) crit = fmaxf(crit, arr[(size_t)endi[e] * L + lane]);
        my_sum = crit; my_sq = (double)crit * crit;
        int b = (int)((crit - HLO) / HBIN); if (b < 0) b = 0; if (b >= NB) b = NB - 1;
        atomicAdd(&g_hist[b], 1u);
    }
    // block reduction for sum/sumsq (ALL threads participate)
    extern __shared__ double sh[]; double *ss = sh, *sq = sh + blockDim.x;
    ss[threadIdx.x] = my_sum; sq[threadIdx.x] = my_sq; __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) { ss[threadIdx.x] += ss[threadIdx.x + s]; sq[threadIdx.x] += sq[threadIdx.x + s]; }
        __syncthreads();
    }
    if (threadIdx.x == 0) { atomicAdd(g_sum, ss[0]); atomicAdd(g_sq, sq[0]); }
}

static float mu_k[N_CELLS], sd_k[N_CELLS];   // per-corner cell mean/sd (static: too big for stack)

static float pctile(const unsigned int *hist, long long total, double q, float hlo, float hbin) {
    long long target = (long long)(q * total), cum = 0;
    for (int b = 0; b < NB; b++) { cum += hist[b]; if (cum >= target) return hlo + (b + 0.5f) * hbin; }
    return hlo + NB * hbin;
}

int main(int argc, char **argv) {
    long long L = (argc > 1) ? atoll(argv[1]) : 8000LL;   // lanes per batch (arr+znet each N_NETS*L*4B)
    int nbatch = (argc > 2) ? atoi(argv[2]) : 1;          // independent MC batches per corner
    float sfrac_scale = (argc > 3) ? atof(argv[3]) : 1.0f;// amplify sigma_frac (low-Vdd near-threshold)
    int block = 256; long long grid = (L + block - 1) / block;
    if (block & (block - 1)) { fprintf(stderr, "block not pow2\n"); return 2; }
    int *d_out,*d_nin,*d_in0,*d_in1,*d_in2,*d_end; float *d_mu,*d_sd,*d_arr,*d_znet; double *d_sum,*d_sq; unsigned int *d_hist;
    size_t nc = N_CELLS * sizeof(int);
    #define CP_I(dp, src) CUDA_CHECK(cudaMalloc(&dp, nc)); CUDA_CHECK(cudaMemcpy(dp, src, nc, cudaMemcpyHostToDevice))
    CP_I(d_out, CELL_OUT); CP_I(d_nin, CELL_NIN); CP_I(d_in0, CELL_IN0); CP_I(d_in1, CELL_IN1); CP_I(d_in2, CELL_IN2);
    CUDA_CHECK(cudaMalloc(&d_end, N_END*sizeof(int))); CUDA_CHECK(cudaMemcpy(d_end, END_IDX, N_END*sizeof(int), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMalloc(&d_mu, N_CELLS*sizeof(float))); CUDA_CHECK(cudaMalloc(&d_sd, N_CELLS*sizeof(float)));
    size_t arrbytes = (size_t)N_NETS * L * sizeof(float);
    CUDA_CHECK(cudaMalloc(&d_arr, arrbytes)); CUDA_CHECK(cudaMalloc(&d_znet, arrbytes));
    CUDA_CHECK(cudaMalloc(&d_sum, sizeof(double))); CUDA_CHECK(cudaMalloc(&d_sq, sizeof(double)));
    CUDA_CHECK(cudaMalloc(&d_hist, NB*sizeof(unsigned int)));
    long long total = L * (long long)nbatch;
    printf("Vortex SSTA on GPU (INSTANCES x CORNERS): %d cells, %d nets, %d endpoints, rho0=%.2f, sigma_frac x%.2f | %lld lanes x %d batches = %lld inst/corner, %d corners (arr+znet %.2f GB)\n",
           N_CELLS, N_NETS, N_END, RHO0, sfrac_scale, L, nbatch, total, NKVT, 2 * arrbytes / 1e9);
    printf("\n  kvt | eff sigma_frac | GPU mean |  GPU sd | clk@99.9%% | (p99.9-mean)/mean | vs numpy@x1\n");
    bool allpass = true; float p999_worst = 0; int kvt_worst = 0;
    for (int ki = 0; ki < NKVT; ki++) {
        for (int c = 0; c < N_CELLS; c++) { mu_k[c] = GATE_MU[CELL_TID[c]*NKVT + ki]; sd_k[c] = SIGMA_FRAC[ki]*sfrac_scale*mu_k[c]; }
        CUDA_CHECK(cudaMemcpy(d_mu, mu_k, N_CELLS*sizeof(float), cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaMemcpy(d_sd, sd_k, N_CELLS*sizeof(float), cudaMemcpyHostToDevice));
        float w = REF_SD[ki] * (sfrac_scale > 1.f ? sfrac_scale : 1.f);
        float hlo = REF_MEAN[ki] - 5.f*w, hhi = REF_MEAN[ki] + 10.f*w, hbin = (hhi - hlo) / NB;
        CUDA_CHECK(cudaMemcpyToSymbol(HLO, &hlo, sizeof(float))); CUDA_CHECK(cudaMemcpyToSymbol(HBIN, &hbin, sizeof(float)));
        CUDA_CHECK(cudaMemset(d_sum, 0, sizeof(double))); CUDA_CHECK(cudaMemset(d_sq, 0, sizeof(double)));
        CUDA_CHECK(cudaMemset(d_hist, 0, NB*sizeof(unsigned int)));
        for (int b = 0; b < nbatch; b++) {
            unsigned long long loff = (unsigned long long)b * L;
            CUDA_CHECK(cudaMemset(d_arr, 0, arrbytes));
            prefill_z<<<grid, block>>>(0x5A18ULL, L, loff, d_znet);
            CUDA_CHECK(cudaGetLastError()); CUDA_CHECK(cudaDeviceSynchronize());
            ssta<<<grid, block, 2*block*sizeof(double)>>>(0x5A17ULL, L, loff, d_arr, d_znet, d_out, d_nin, d_in0, d_in1, d_in2,
                                                          d_mu, d_sd, d_end, d_sum, d_sq, d_hist);
            CUDA_CHECK(cudaGetLastError()); CUDA_CHECK(cudaDeviceSynchronize());
        }
        double sum, sq; unsigned int hist[NB];
        CUDA_CHECK(cudaMemcpy(&sum, d_sum, sizeof(double), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaMemcpy(&sq, d_sq, sizeof(double), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaMemcpy(hist, d_hist, sizeof(hist), cudaMemcpyDeviceToHost));
        double mean = sum / total, sd = sqrt(sq / total - mean * mean);
        float p99 = pctile(hist, total, 0.99, hlo, hbin), p999 = pctile(hist, total, 0.999, hlo, hbin);
        double e_mean = fabs(mean - REF_MEAN[ki]) / REF_MEAN[ki] * 100, e_sd = fabs(sd - REF_SD[ki]) / REF_SD[ki] * 100;
        if (sfrac_scale == 1.0f && (e_mean > 0.5 || e_sd > 5.0)) allpass = false;   // numpy ref is scale=1
        double ymargin = (p999 - mean) / mean * 100;                                // yield tail (relative)
        if (p999 > p999_worst) { p999_worst = p999; kvt_worst = KVT_LIST[ki]; }
        char vsn[32]; if (sfrac_scale == 1.0f) snprintf(vsn, 32, "%.2f%%/%.1f%%", e_mean, e_sd); else snprintf(vsn, 32, "(proj)");
        printf("   %d  |     %5.2f%%     | %8.1f | %6.1f | %8.1f  |     %5.2f%%       | %s\n",
               KVT_LIST[ki], SIGMA_FRAC[ki]*sfrac_scale*100, mean, sd, p999, ymargin, vsn);
    }
    printf("\n  SIGN-OFF across all %d corners (sigma_frac x%.2f): worst = kvt %d, clk@99.9%% yield = %.1f ps -> fmax = %.3f GHz\n",
           NKVT, sfrac_scale, kvt_worst, p999_worst, 1000.0/p999_worst);
    if (sfrac_scale == 1.0f)
        printf("  -> %s\n", allpass ? "PROVEN on GPU: reproduces the numpy reference at every corner (scale=1 baseline)."
                                    : "CHECK: a corner disagrees with the numpy reference.");
    else
        printf("  -> LOW-Vdd PROJECTION: sigma_frac amplified x%.2f (near-threshold); watch the yield-margin growth.\n", sfrac_scale);
    return 0;
}
