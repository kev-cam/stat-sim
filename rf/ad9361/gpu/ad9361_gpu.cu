// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
// ad9361_gpu -- the spectral event model of AD9361 radios in an arena, on a GPU.
//
// M radios, B OFDM-symbol events per window, 64 lines per event.  Per window, on the device:
//   transmit   one thread per (radio, symbol): data-port lines -> spectrum at the TX pin     (tx_symbol)
//   receive 1  one thread per (radio, symbol): arena sum over the transmitters it hears,
//              carrier offsets, noise; samples before the gain and per-sub-block statistics   (rx_front)
//   AGC        the gain state machine over those statistics: sequential per radio, on the host
//   receive 2  one thread per (radio, symbol): gain, ADC, data-port lines                     (rx_back)
// The same functions (ad9361_kernels.h) run on the CPU as the reference and the baseline.
//
//   ad9361_gpu scenario.bin out.bin [--windows N] [--cpu-windows N] [--seed S]
// scenario.bin is written by an2597_gpu.py (radios' constants per control state, coupling per pair, the
// symbols to send); out.bin gets the first window's gains and received lines; timings go to stdout as
// "RESULT key=value" lines.
#include "ad9361_kernels.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cuda_runtime.h>
#include <omp.h>
#include <vector>

#define CK(e) do { cudaError_t _e = (e); if (_e != cudaSuccess) { \
    fprintf(stderr, "CUDA error %s at %s:%d\n", cudaGetErrorString(_e), __FILE__, __LINE__); exit(1); } } while (0)

struct AgcState { float gain; int fast; int settle; int lost; };          // fast: 0 search, 1 settle, 2 locked

__global__ void k_tx(const RadioTx *rt, const float *bins, float *lines, int M, int B, uint64_t seed, uint64_t b0) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= (long)M * B) return;
    int j = (int)(idx / B);
    long b = idx % B;
    tx_symbol(rt + j, bins + idx * 2 * NK, lines + idx * 2 * NK, rng_key(seed, j, 0, b0 + b));
}

__global__ void k_rx1(const RadioRx *rr, const Pair *pairs, const float *lines, float *pre, float *stats, int M, int B,
                      uint64_t seed, uint64_t b0) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= (long)M * B) return;
    int i = (int)(idx / B);
    long b = idx % B;
    rx_front(rr + i, pairs + (long)i * M, M, lines + b * 2 * NK, (long)B * 2 * NK, pre + idx * 2 * NK,
             stats + idx * 2 * NSB, rng_key(seed, i, 1, b0 + b), b0 + b);
}

__global__ void k_rx2(const RadioRx *rr, const float *pre, const float *gains, float *out, int M, int B) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= (long)M * B) return;
    int i = (int)(idx / B);
    rx_back(rr + i, pre + idx * 2 * NK, gains + idx * NSB, out + idx * 2 * NK);
}

static float legal_gain(const AgcCfg &c, float g) {
    float k = floorf((c.gmax_db - g) + 0.5f), kmax = floorf(c.gmax_db - c.gmin_db);
    k = fminf(fmaxf(k, 0.0f), kmax);
    return c.gmax_db - k;
}

// The AGC of one radio over a window: the gain used in each sub-block, from the statistics of the signal
// before the gain (mean power in W, largest |I| or |Q| in sqrt(W)).  The same state machine as the VHDL;
// the comparisons are made on power ratios, so a sub-block that changes nothing costs no log or pow.
static void agc_scan(const AgcCfg &c, const RadioRx &r, AgcState &st, const float *stats, float *gains, int B) {
    const long n = (long)B * NSB;
    if (c.mode == 0 || !r.on) {
        if (c.mode == 0)
            st.gain = legal_gain(c, c.manual_db);
        for (long sb = 0; sb < n; sb++) gains[sb] = st.gain;
        return;
    }
    const float detect = powf(10.0f, 0.1f * c.detect), strong = powf(10.0f, 0.1f * (c.target + c.stronger));
    const float lost = powf(10.0f, 0.1f * (c.target - c.lost)), rail = 2046.5f / 2048.0f;
    float gain = st.gain - 1.0f, g2 = 0.0f, g1 = 0.0f;                   // forces the first evaluation
    for (long sb = 0; sb < n; sb++) {
        if (st.gain != gain) {
            gain = st.gain;
            g2 = powf(10.0f, 0.1f * gain) / r.fs0_w;                     // power gain to ADC full scale
            g1 = sqrtf(g2);
        }
        gains[sb] = gain;
        const float pw = stats[2 * sb] * g2;                             // ADC power against a full-scale tone
        const bool clip = stats[2 * sb + 1] * g1 >= rail;
        auto adjust = [&]() {
            if (clip) {
                st.gain = legal_gain(c, st.gain - c.clip_step);
                return false;
            }
            float p = 10.0f * log10f(fmaxf(pw, 1e-12f));
            st.gain = legal_gain(c, st.gain - (p - c.target));
            return fabsf(p - c.target) < 1.0f;
        };
        if (st.fast == 0) {
            if (pw > detect || clip) {
                st.fast = 1;
                st.settle = 0;
                if (adjust()) { st.fast = 2; st.lost = 0; }
            }
        }
        else if (st.fast == 1) {
            st.settle++;
            bool done = adjust();
            if (done || st.settle >= c.settle_iterations) { st.fast = 2; st.lost = 0; }
        }
        else if (clip || pw > strong) {
            st.fast = 1;
            st.settle = 0;
            st.lost = 0;
            if (adjust()) st.fast = 2;
        }
        else if (pw < lost) {
            if (++st.lost >= c.lost_blocks) {
                st.fast = 0;
                st.lost = 0;
                st.gain = c.gmax_db;
            }
        }
        else
            st.lost = 0;
    }
}

static double now_s() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s scenario.bin out.bin [--windows N] [--cpu-windows N] [--seed S]\n", argv[0]);
        return 2;
    }
    int windows = 50, cpu_windows = 3;
    uint64_t seed = 1;
    for (int a = 3; a + 1 < argc; a += 2) {
        if (!strcmp(argv[a], "--windows")) windows = atoi(argv[a + 1]);
        else if (!strcmp(argv[a], "--cpu-windows")) cpu_windows = atoi(argv[a + 1]);
        else if (!strcmp(argv[a], "--seed")) seed = strtoull(argv[a + 1], NULL, 10);
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    int hdr[8];
    double t_sym;
    if (fread(hdr, sizeof(int), 8, f) != 8 || hdr[0] != 0x41393336 || fread(&t_sym, sizeof(double), 1, f) != 1) {
        fprintf(stderr, "%s: not a scenario file\n", argv[1]);
        return 1;
    }
    if (hdr[4] != (int)sizeof(RadioTx) || hdr[5] != (int)sizeof(RadioRx) || hdr[6] != (int)sizeof(Pair)
        || hdr[7] != (int)sizeof(AgcCfg)) {
        fprintf(stderr, "%s: record sizes %d %d %d %d, this program has %zu %zu %zu %zu\n", argv[1], hdr[4], hdr[5],
                hdr[6], hdr[7], sizeof(RadioTx), sizeof(RadioRx), sizeof(Pair), sizeof(AgcCfg));
        return 1;
    }
    const int M = hdr[1], B = hdr[2];
    const long MB = (long)M * B;
    std::vector<RadioTx> rt(M);
    std::vector<RadioRx> rr(M);
    std::vector<Pair> pairs((size_t)M * M);
    std::vector<AgcCfg> agc(M);
    std::vector<float> bins(MB * 2 * NK);
    bool ok = fread(rt.data(), sizeof(RadioTx), M, f) == (size_t)M && fread(rr.data(), sizeof(RadioRx), M, f) == (size_t)M
        && fread(pairs.data(), sizeof(Pair), (size_t)M * M, f) == (size_t)M * M
        && fread(agc.data(), sizeof(AgcCfg), M, f) == (size_t)M
        && fread(bins.data(), sizeof(float), bins.size(), f) == bins.size();
    fclose(f);
    if (!ok) { fprintf(stderr, "%s: short scenario file\n", argv[1]); return 1; }
    bool any_agc = false;
    for (int i = 0; i < M; i++) any_agc = any_agc || (agc[i].mode != 0 && rr[i].on);

    // ---- CPU reference -------------------------------------------------------------------------
    std::vector<float> c_lines(MB * 2 * NK), c_pre(MB * 2 * NK), c_stats(MB * 2 * NSB), c_gains(MB * NSB), c_out(MB * 2 * NK);
    auto agc_init = [&](std::vector<AgcState> &st) {
        st.assign(M, AgcState{0, 0, 0, 0});
        for (int i = 0; i < M; i++) st[i].gain = agc[i].mode == 0 ? legal_gain(agc[i], agc[i].manual_db) : agc[i].gmax_db;
    };
    auto cpu_window = [&](uint64_t b0, std::vector<AgcState> &st, int threads) {
        #pragma omp parallel for num_threads(threads) schedule(static)
        for (long idx = 0; idx < MB; idx++)
            tx_symbol(&rt[idx / B], &bins[idx * 2 * NK], &c_lines[idx * 2 * NK], rng_key(seed, (int)(idx / B), 0, b0 + idx % B));
        #pragma omp parallel for num_threads(threads) schedule(static)
        for (long idx = 0; idx < MB; idx++) {
            int i = (int)(idx / B);
            long b = idx % B;
            rx_front(&rr[i], &pairs[(size_t)i * M], M, &c_lines[b * 2 * NK], (long)B * 2 * NK, &c_pre[idx * 2 * NK],
                     &c_stats[idx * 2 * NSB], rng_key(seed, i, 1, b0 + b), b0 + b);
        }
        for (int i = 0; i < M; i++)
            agc_scan(agc[i], rr[i], st[i], &c_stats[(long)i * B * 2 * NSB], &c_gains[(long)i * B * NSB], B);
        #pragma omp parallel for num_threads(threads) schedule(static)
        for (long idx = 0; idx < MB; idx++)
            rx_back(&rr[idx / B], &c_pre[idx * 2 * NK], &c_gains[idx * NSB], &c_out[idx * 2 * NK]);
    };

    // ---- GPU -----------------------------------------------------------------------------------
    RadioTx *d_rt; RadioRx *d_rr; Pair *d_pairs;
    float *d_bins, *d_lines, *d_pre, *d_stats, *d_gains, *d_out;
    CK(cudaMalloc(&d_rt, M * sizeof(RadioTx)));
    CK(cudaMalloc(&d_rr, M * sizeof(RadioRx)));
    CK(cudaMalloc(&d_pairs, (size_t)M * M * sizeof(Pair)));
    CK(cudaMalloc(&d_bins, bins.size() * sizeof(float)));
    CK(cudaMalloc(&d_lines, bins.size() * sizeof(float)));
    CK(cudaMalloc(&d_pre, bins.size() * sizeof(float)));
    CK(cudaMalloc(&d_stats, MB * 2 * NSB * sizeof(float)));
    CK(cudaMalloc(&d_gains, MB * NSB * sizeof(float)));
    CK(cudaMalloc(&d_out, bins.size() * sizeof(float)));
    CK(cudaMemcpy(d_rt, rt.data(), M * sizeof(RadioTx), cudaMemcpyHostToDevice));
    CK(cudaMemcpy(d_rr, rr.data(), M * sizeof(RadioRx), cudaMemcpyHostToDevice));
    CK(cudaMemcpy(d_pairs, pairs.data(), (size_t)M * M * sizeof(Pair), cudaMemcpyHostToDevice));
    CK(cudaMemcpy(d_bins, bins.data(), bins.size() * sizeof(float), cudaMemcpyHostToDevice));
    std::vector<float> g_stats(MB * 2 * NSB), g_gains(MB * NSB), g_out(MB * 2 * NK);
    const int TPB = 128;
    const unsigned blocks = (unsigned)((MB + TPB - 1) / TPB);
    // host_agc: download the statistics, run the state machines, upload the gains (one extra sync per window)
    auto gpu_window = [&](uint64_t b0, std::vector<AgcState> &st, bool host_agc) {
        k_tx<<<blocks, TPB>>>(d_rt, d_bins, d_lines, M, B, seed, b0);
        k_rx1<<<blocks, TPB>>>(d_rr, d_pairs, d_lines, d_pre, d_stats, M, B, seed, b0);
        if (host_agc) {
            CK(cudaMemcpy(g_stats.data(), d_stats, g_stats.size() * sizeof(float), cudaMemcpyDeviceToHost));
            #pragma omp parallel for schedule(static) if (M > 1)
            for (int i = 0; i < M; i++)
                agc_scan(agc[i], rr[i], st[i], &g_stats[(long)i * B * 2 * NSB], &g_gains[(long)i * B * NSB], B);
            CK(cudaMemcpy(d_gains, g_gains.data(), g_gains.size() * sizeof(float), cudaMemcpyHostToDevice));
        }
        k_rx2<<<blocks, TPB>>>(d_rr, d_pre, d_gains, d_out, M, B);
        CK(cudaDeviceSynchronize());
    };

    // first window on both, same random numbers: compare, and keep the GPU's for the caller
    std::vector<AgcState> st_c, st_g;
    agc_init(st_c);
    agc_init(st_g);
    cpu_window(0, st_c, omp_get_max_threads());
    gpu_window(0, st_g, true);
    CK(cudaMemcpy(g_out.data(), d_out, g_out.size() * sizeof(float), cudaMemcpyDeviceToHost));
    long gain_diff = 0;
    for (size_t k = 0; k < g_gains.size(); k++) gain_diff += g_gains[k] != c_gains[k];
    double max_diff = 0, rms = 0;
    for (size_t k = 0; k < g_out.size(); k++) {
        max_diff = fmax(max_diff, fabs((double)g_out[k] - c_out[k]));
        rms += (double)c_out[k] * c_out[k];
    }
    rms = sqrt(rms / g_out.size());
    printf("RESULT M=%d B=%d t_sym=%.9g agc=%d\n", M, B, t_sym, (int)any_agc);
    printf("RESULT gpu_cpu_gain_mismatches=%ld of %zu\n", gain_diff, g_gains.size());
    printf("RESULT gpu_cpu_max_line_diff=%.6g line_rms=%.6g\n", max_diff, rms);
    f = fopen(argv[2], "wb");
    if (!f) { perror(argv[2]); return 1; }
    int oh[2] = {M, B};
    fwrite(oh, sizeof(int), 2, f);
    fwrite(g_gains.data(), sizeof(float), g_gains.size(), f);
    fwrite(g_out.data(), sizeof(float), g_out.size(), f);
    fclose(f);

    // timing: GPU with the AGC round trip (if any radio has an AGC), GPU with the gains held, CPU
    const double air = B * t_sym;
    for (int pass = 0; pass < 2; pass++) {
        bool host_agc = pass == 0;
        if (host_agc && !any_agc) continue;
        agc_init(st_g);
        for (int w = 0; w < 3; w++) gpu_window((uint64_t)w * B, st_g, host_agc);
        double t0 = now_s();
        for (int w = 0; w < windows; w++) gpu_window((uint64_t)(w + 3) * B, st_g, host_agc);
        double per = (now_s() - t0) / windows;
        printf("RESULT %s_window_ms=%.4f %s_rtf=%.3f\n", host_agc ? "gpu_agc" : "gpu_held", per * 1e3,
               host_agc ? "gpu_agc" : "gpu_held", air / per);
    }
    for (int threads : {1, omp_get_max_threads()}) {
        agc_init(st_c);
        cpu_window(0, st_c, threads);
        double t0 = now_s();
        for (int w = 0; w < cpu_windows; w++) cpu_window((uint64_t)(w + 1) * B, st_c, threads);
        double per = (now_s() - t0) / cpu_windows;
        printf("RESULT cpu%d_window_ms=%.4f cpu%d_rtf=%.4f\n", threads, per * 1e3, threads, air / per);
    }
    return 0;
}
