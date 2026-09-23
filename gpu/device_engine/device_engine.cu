// Analytic device engine on GPU — batched closed-form LTI/NLDM propagator (no ODE integrator).
// One thread = one device instance = one 40-stage inverter chain; per stage draws a mismatch
// factor g (Vt->drive strength) and propagates (delay, slew) with the 2-param alternating model.
// Grid-stride so every thread reaches the block reduction (partial-block trap avoided).
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <curand_kernel.h>
#define CUDA_CHECK(c) do{cudaError_t e=(c); if(e!=cudaSuccess){fprintf(stderr,"CUDA %s:%d %s\n",__FILE__,__LINE__,cudaGetErrorString(e));exit(2);} }while(0)

#define NSTAGE 40
__constant__ float DLY0[2] = {16.78f, 40.87f};   // delay intercept (fall,rise)
__constant__ float DLYc[2] = {0.3523f, 0.0791f}; // delay slew-sensitivity
__constant__ float SLW0[2] = {26.23f, 56.99f};   // out-slew intercept
__constant__ float SLWb[2] = {0.1535f, 0.0396f}; // out-slew slew-sensitivity

__global__ void de(unsigned long long seed, long long Ninst, float sigma_g, float Tin0,
                   double *g_sum, double *g_sq) {
    long long tid = blockIdx.x * (long long)blockDim.x + threadIdx.x;
    long long stride = (long long)gridDim.x * blockDim.x;
    double lsum = 0.0, lsq = 0.0;
    curandStatePhilox4_32_10_t st;
    for (long long inst = tid; inst < Ninst; inst += stride) {
        curand_init(seed, (unsigned long long)inst, 0, &st);
        float T = Tin0, tot = 0.f;
        for (int i = 0; i < NSTAGE; i++) {
            int pol = i & 1;
            float g = 1.f + sigma_g * (float)curand_normal_double(&st);
            float d = (DLY0[pol] + DLYc[pol] * T) * g;
            T = (SLW0[pol] + SLWb[pol] * T) * g;
            tot += d;
        }
        lsum += tot; lsq += (double)tot * tot;
    }
    extern __shared__ double sh[]; double *ss = sh, *sq = sh + blockDim.x;
    ss[threadIdx.x] = lsum; sq[threadIdx.x] = lsq; __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) { ss[threadIdx.x] += ss[threadIdx.x + s]; sq[threadIdx.x] += sq[threadIdx.x + s]; }
        __syncthreads();
    }
    if (threadIdx.x == 0) { atomicAdd(g_sum, ss[0]); atomicAdd(g_sq, sq[0]); }
}

int main(int argc, char **argv) {
    long long N = (argc > 1) ? atoll(argv[1]) : 200000LL;
    float sigma_g = (argc > 2) ? atof(argv[2]) : 0.08f, Tin0 = 80.f;
    const float REF_MEAN = 1628.05f, REF_SD = 27.27f;   // numpy oracle
    int block = 256, grid = 512;
    double *d_sum, *d_sq;
    CUDA_CHECK(cudaMalloc(&d_sum, sizeof(double))); CUDA_CHECK(cudaMemset(d_sum, 0, sizeof(double)));
    CUDA_CHECK(cudaMalloc(&d_sq, sizeof(double)));  CUDA_CHECK(cudaMemset(d_sq, 0, sizeof(double)));
    de<<<grid, block, 2*block*sizeof(double)>>>(0x5A17ULL, N, sigma_g, Tin0, d_sum, d_sq);
    CUDA_CHECK(cudaGetLastError()); CUDA_CHECK(cudaDeviceSynchronize());
    double sum, sq; CUDA_CHECK(cudaMemcpy(&sum, d_sum, sizeof(double), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(&sq, d_sq, sizeof(double), cudaMemcpyDeviceToHost));
    double mean = sum / N, sd = sqrt(sq / N - mean * mean);
    printf("Device engine on GPU: %lld inst x %d stages, sigma_g=%.2f\n", N, NSTAGE, sigma_g);
    printf("  GPU   chain delay: mean=%.3f sd=%.3f ps\n", mean, sd);
    printf("  numpy reference  : mean=%.3f sd=%.3f ps\n", REF_MEAN, REF_SD);
    double em = fabs(mean - REF_MEAN) / REF_MEAN * 100, es = fabs(sd - REF_SD) / REF_SD * 100;
    printf("  GPU vs numpy: |mean|=%.3f%% |sd|=%.1f%%  -> %s\n", em, es,
           (em < 0.5 && es < 5.0) ? "PROVEN on GPU: analytic device engine batches + matches numpy."
                                  : "CHECK");
    return 0;
}
