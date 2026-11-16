// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
// ad9361_kernels.h -- the AD9361 spectral event model, one OFDM-symbol event per call, for GPU and CPU.
//
// The same maths as ad9361_spectral_pkg.vhd / ad9361_pkg.vhd (and ad9361.py): an event is 64 spectral lines;
// the chip filters on the lines and does everything non-linear on the 64 samples of the event.  Every
// function here is compiled for the device (one thread per radio and symbol) and for the host (the CPU
// reference), with the same counter-based random numbers, so the two can be compared event by event.
//
// Differences from the VHDL, both forced by running the symbols of a window in parallel:
//  - LO phase noise starts each event from a fresh stationary value instead of continuing from the last
//    event (same rms and corner within the event; no correlation from one symbol to the next);
//  - the AGC is three steps: per-sub-block power and peak of the signal before the gain (parallel), the
//    gain state machine over those numbers (sequential, cheap, on the host), gain and ADC (parallel).
//    The state machine sees the power the ADC would measure without compression, which differs from the
//    VHDL's measurement only when a sub-block clips (and then both step down by the same amount).
#pragma once
#include <math.h>
#include <stdint.h>

#ifdef __CUDACC__
#define HD __host__ __device__
#else
#define HD
#endif

#define NK 64                 // lines per event
#define NSB 4                 // AGC sub-blocks per event
#define SBLEN 16              // samples per sub-block

struct RadioTx {              // one transmitter in one control state
    int on;
    float amp;                // envelope of a full-scale DAC value before compression, sqrt(W)
    float ip3;                // output intercept, W
    float res_sigma;          // EVM residual, per component
    float pn_sigma;           // LO phase noise rms, rad
    float pn_a, pn_w;         // first-order process: theta = a theta + w N
    float leak_re, leak_im;   // carrier leakage, sqrt(W)
    float noise_sigma;        // TX noise per component per sample, sqrt(W)
    float h_re[NK], h_im[NK]; // analog baseband response per line
};

struct RadioRx {              // one receiver in one control state
    int on;
    float res_sigma, pn_sigma, pn_a, pn_w;
    float noise_sigma;        // thermal noise per component per sample, sqrt(W)
    float iq_g, iq_c, iq_s;   // quadrature error: Q' = g (Q c + I s)
    float iip3_max_dbm, gmax_db, iip3_ceil_dbm;   // input intercept at maximum gain; it rises as gain falls, to the ceiling
    float fs0_w;              // CW power reaching ADC full scale at 0 dB gain, W
};

struct Pair {                 // receiver i from transmitter j (index i * M + j)
    int on;
    float eps;                // carrier of j minus LO of i, in line spacings
    double dphi;              // the same offset in cycles per symbol period
    float c_re[NK], c_im[NK]; // antennas, free space and the receiver's baseband filter, per line of j's grid
};

struct AgcCfg {               // host side
    int mode;                 // 0 manual, 1 fast attack
    float manual_db, gmax_db, gmin_db;
    float detect, target, clip_step, stronger, lost;
    int settle_iterations, lost_blocks;
};


// 64-point FFT in place; sign -1: forward (exp(-j ...)), +1: inverse without the 1/N
HD static inline void fft64(float *re, float *im, int sign) {
    // twiddles and bit reversal as local constants: usable in device and host code alike
    const float FFT_RE[32] = {1.000000000e+00f, 9.951847267e-01f, 9.807852804e-01f, 9.569403357e-01f, 9.238795325e-01f, 8.819212643e-01f, 8.314696123e-01f, 7.730104534e-01f, 7.071067812e-01f, 6.343932842e-01f, 5.555702330e-01f, 4.713967368e-01f, 3.826834324e-01f, 2.902846773e-01f, 1.950903220e-01f, 9.801714033e-02f, 6.123233996e-17f, -9.801714033e-02f, -1.950903220e-01f, -2.902846773e-01f, -3.826834324e-01f, -4.713967368e-01f, -5.555702330e-01f, -6.343932842e-01f, -7.071067812e-01f, -7.730104534e-01f, -8.314696123e-01f, -8.819212643e-01f, -9.238795325e-01f, -9.569403357e-01f, -9.807852804e-01f, -9.951847267e-01f};
    const float FFT_IM[32] = {0.000000000e+00f, 9.801714033e-02f, 1.950903220e-01f, 2.902846773e-01f, 3.826834324e-01f, 4.713967368e-01f, 5.555702330e-01f, 6.343932842e-01f, 7.071067812e-01f, 7.730104534e-01f, 8.314696123e-01f, 8.819212643e-01f, 9.238795325e-01f, 9.569403357e-01f, 9.807852804e-01f, 9.951847267e-01f, 1.000000000e+00f, 9.951847267e-01f, 9.807852804e-01f, 9.569403357e-01f, 9.238795325e-01f, 8.819212643e-01f, 8.314696123e-01f, 7.730104534e-01f, 7.071067812e-01f, 6.343932842e-01f, 5.555702330e-01f, 4.713967368e-01f, 3.826834324e-01f, 2.902846773e-01f, 1.950903220e-01f, 9.801714033e-02f};
    const unsigned char FFT_REV[64] = {0, 32, 16, 48, 8, 40, 24, 56, 4, 36, 20, 52, 12, 44, 28, 60, 2, 34, 18, 50, 10, 42, 26, 58, 6, 38, 22, 54, 14, 46, 30, 62, 1, 33, 17, 49, 9, 41, 25, 57, 5, 37, 21, 53, 13, 45, 29, 61, 3, 35, 19, 51, 11, 43, 27, 59, 7, 39, 23, 55, 15, 47, 31, 63};
    for (int i = 0; i < NK; i++) {
        int j = FFT_REV[i];
        if (j > i) {
            float t = re[i]; re[i] = re[j]; re[j] = t;
            t = im[i]; im[i] = im[j]; im[j] = t;
        }
    }
    for (int len = 2, step = NK / 2; len <= NK; len <<= 1, step >>= 1) {
        for (int i = 0; i < NK; i += len) {
            for (int k = 0; k < len / 2; k++) {
                float wr = FFT_RE[k * step], wi = sign * FFT_IM[k * step];
                int a = i + k, b = a + len / 2;
                float xr = re[b] * wr - im[b] * wi, xi = re[b] * wi + im[b] * wr;
                re[b] = re[a] - xr; im[b] = im[a] - xi;
                re[a] += xr; im[a] += xi;
            }
        }
    }
}

// counter-based random numbers: a key per (seed, radio, side, symbol), a counter per draw
HD static inline uint64_t mix64(uint64_t z) {
    z += 0x9e3779b97f4a7c15ULL;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}
HD static inline uint64_t rng_key(uint64_t seed, int radio, int side, uint64_t symbol) {
    return mix64(mix64(seed ^ ((uint64_t)radio << 40) ^ ((uint64_t)side << 56)) ^ symbol);
}
// two independent unit Gaussians for draw c of a key
HD static inline void gauss2(uint64_t key, uint32_t c, float *g1, float *g2) {
    uint64_t r = mix64(key + (uint64_t)c * 0x632be59bd9b4e019ULL);
    float u1 = ((float)(uint32_t)(r >> 32) + 1.0f) * 2.3283064365386963e-10f;      // (0, 1]
    float u2 = (float)(uint32_t)r * 2.3283064365386963e-10f;
    float m = sqrtf(-2.0f * logf(u1)), a = 6.283185307179586f * u2;
    *g1 = m * cosf(a);
    *g2 = m * sinf(a);
}

HD static inline float dac_word(float x) {
    return fminf(2047.0f, fmaxf(-2048.0f, floorf(x * 0.0625f + 0.5f))) * (1.0f / 2048.0f);
}
HD static inline float adc_word(float v) {
    return fminf(2047.0f, fmaxf(-2048.0f, floorf(v * 2048.0f + 0.5f)));
}

// One event through a transmitter.  bins: 64 complex data-port lines (full scale 2**15); lines: 64 complex
// lines at the TX pin, sqrt(W).
HD static inline void tx_symbol(const RadioTx *t, const float *bins, float *lines, uint64_t key) {
    float re[NK], im[NK];
    if (!t->on) {
        for (int k = 0; k < 2 * NK; k++) lines[k] = 0.0f;
        return;
    }
    for (int k = 0; k < NK; k++) {                              // baseband filter on the lines
        float br = bins[2 * k], bi = bins[2 * k + 1];
        re[k] = br * t->h_re[k] - bi * t->h_im[k];
        im[k] = br * t->h_im[k] + bi * t->h_re[k];
    }
    fft64(re, im, +1);                                          // the samples of the event
    float g1, g2;
    gauss2(key, 0, &g1, &g2);
    float theta = t->pn_sigma * g1;                             // phase noise: a stationary start
    for (int n = 0; n < NK; n++) {
        uint32_t c = 1 + 3 * (uint32_t)n;
        gauss2(key, c, &g1, &g2);
        theta = t->pn_a * theta + t->pn_w * g1;
        float qi = dac_word(re[n]), qq = dac_word(im[n]);
        gauss2(key, c + 1, &g1, &g2);                           // (1 + e): the EVM residual
        float er = 1.0f + t->res_sigma * g1, ei = t->res_sigma * g2;
        float ti = qi * er - qq * ei, tq = qi * ei + qq * er;
        float cs = cosf(theta), sn = sinf(theta);
        float xi = (ti * cs - tq * sn) * t->amp, xq = (ti * sn + tq * cs) * t->amp;
        float k = 1.0f / sqrtf(1.0f + 2.0f * (xi * xi + xq * xq) / t->ip3);     // compression
        gauss2(key, c + 2, &g1, &g2);
        re[n] = xi * k + t->leak_re + t->noise_sigma * g1;
        im[n] = xq * k + t->leak_im + t->noise_sigma * g2;
    }
    fft64(re, im, -1);
    for (int k = 0; k < NK; k++) {
        lines[2 * k] = re[k] * (1.0f / NK);
        lines[2 * k + 1] = im[k] * (1.0f / NK);
    }
}

// Receiver, first part: everything before the gain.  lines: all transmitters' events for this symbol
// (M x 64 complex, stride `stride` floats between transmitters); pre: 64 complex samples before the gain;
// stats: per sub-block the mean power and the largest |I| or |Q|.  symbol: the global symbol index.
HD static inline void rx_front(const RadioRx *r, const Pair *pairs, int M, const float *lines, long stride,
                               float *pre, float *stats, uint64_t key, uint64_t symbol) {
    float ar[NK], ai[NK], re[NK], im[NK];
    if (!r->on) {
        for (int n = 0; n < 2 * NK; n++) pre[n] = 0.0f;
        for (int s = 0; s < 2 * NSB; s++) stats[s] = 0.0f;
        return;
    }
    for (int n = 0; n < NK; n++) ar[n] = ai[n] = 0.0f;
    for (int j = 0; j < M; j++) {                               // the arena: every transmitter this receiver hears
        const Pair *p = pairs + j;
        if (!p->on) continue;
        const float *x = lines + j * stride;
        for (int k = 0; k < NK; k++) {
            re[k] = x[2 * k] * p->c_re[k] - x[2 * k + 1] * p->c_im[k];
            im[k] = x[2 * k] * p->c_im[k] + x[2 * k + 1] * p->c_re[k];
        }
        fft64(re, im, +1);
        // the carrier offset: its phase at the start of the event, and its ramp through the event
        double cyc = p->dphi * (double)symbol;
        float ph0 = 6.283185307179586f * (float)(cyc - floor(cyc));
        float dph = 6.283185307179586f * p->eps * (1.0f / NK);
        for (int n = 0; n < NK; n++) {
            float cs = cosf(ph0 + dph * n), sn = sinf(ph0 + dph * n);
            ar[n] += re[n] * cs - im[n] * sn;
            ai[n] += re[n] * sn + im[n] * cs;
        }
    }
    float g1, g2;
    gauss2(key, 0, &g1, &g2);
    float theta = r->pn_sigma * g1;
    for (int n = 0; n < NK; n++) {
        uint32_t c = 1 + 3 * (uint32_t)n;
        gauss2(key, c, &g1, &g2);
        theta = r->pn_a * theta + r->pn_w * g1;
        float cs = cosf(theta), sn = sinf(theta);
        float xi = ar[n] * cs - ai[n] * sn, xq = ar[n] * sn + ai[n] * cs;
        gauss2(key, c + 1, &g1, &g2);
        float er = 1.0f + r->res_sigma * g1, ei = r->res_sigma * g2;
        float ti = xi * er - xq * ei, tq = xi * ei + xq * er;
        gauss2(key, c + 2, &g1, &g2);
        ti += r->noise_sigma * g1;
        tq += r->noise_sigma * g2;
        pre[2 * n] = ti;                                        // quadrature errors: gain and phase on Q
        pre[2 * n + 1] = r->iq_g * (tq * r->iq_c + ti * r->iq_s);
    }
    for (int s = 0; s < NSB; s++) {
        float acc = 0.0f, peak = 0.0f;
        for (int n = s * SBLEN; n < (s + 1) * SBLEN; n++) {
            acc += pre[2 * n] * pre[2 * n] + pre[2 * n + 1] * pre[2 * n + 1];
            peak = fmaxf(peak, fmaxf(fabsf(pre[2 * n]), fabsf(pre[2 * n + 1])));
        }
        stats[2 * s] = acc * (1.0f / SBLEN);
        stats[2 * s + 1] = peak;
    }
}

// Receiver, second part: compression, gain (dB, one per sub-block) and the ADC; out: 64 complex data-port lines.
HD static inline void rx_back(const RadioRx *r, const float *pre, const float *gain_db, float *out) {
    float re[NK], im[NK];
    if (!r->on) {
        for (int k = 0; k < 2 * NK; k++) out[k] = 0.0f;
        return;
    }
    for (int s = 0; s < NSB; s++) {
        float g_db = gain_db[s];
        float iip3 = 1e-3f * powf(10.0f, 0.1f * fminf(r->iip3_max_dbm + (r->gmax_db - g_db), r->iip3_ceil_dbm));
        float g = sqrtf(powf(10.0f, 0.1f * g_db) / r->fs0_w);
        for (int n = s * SBLEN; n < (s + 1) * SBLEN; n++) {
            float xi = pre[2 * n], xq = pre[2 * n + 1];
            float k = g / sqrtf(1.0f + 2.0f * (xi * xi + xq * xq) / iip3);
            re[n] = adc_word(xi * k);
            im[n] = adc_word(xq * k);
        }
    }
    fft64(re, im, -1);
    for (int k = 0; k < NK; k++) {
        out[2 * k] = re[k] * (1.0f / NK);
        out[2 * k + 1] = im[k] * (1.0f / NK);
    }
}
