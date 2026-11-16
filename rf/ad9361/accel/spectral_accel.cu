// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
// spectral_accel.cu -- the spectral accelerator (see spectral_accel.h).
//
// The simulator's data, moved out: for every net of the RF signal path one spectrum of K complex lines
// (the frames at the chips' data ports, the TX pins, what the antennas radiate, what the receivers
// deliver), and the chips' state (LO phase noise, AGC).  The processing is SIMT, per frequency:
//
//   transmit   a block per transmitting chip, a thread per line: baseband filter on the lines, the
//              chip's non-linear parts on the event's samples (a thread per sample), back to lines
//   scatter    a block per scatterer, a thread per line: the field arriving from every transmitter
//   receive    a block per receiving chip, a thread per line: the arena (every antenna and scatterer it
//              hears, line by line), then the chip's receive path with its AGC, back to lines
//
// One event at a time, in the simulator's order, so the state carries from event to event exactly as
// the VHDL's does.  spectral_stages.inc holds the stages; it is compiled twice, for the device and as
// loops for the host (SPECTRAL_ACCEL_DEVICE=cpu, and the reference the device is checked against).
#include "spectral_accel.h"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cuda_runtime.h>
#include <map>
#include <mutex>
#include <omp.h>
#include <string>
#include <vector>

#define HD __host__ __device__
#define C0 299792458.0
#define PI_D 3.14159265358979323846

// ---- tables ----------------------------------------------------------------------------------------
struct TxP {                  // a transmitter in its control state (ad9361_pkg.ad9361_accel_params)
    int on;
    uint32_t seed;
    float amp, ip3, res_sigma, pn_a, pn_w, leak_amp, noise_sigma, fc3, fc1;
    float g_ant;              // its antenna, amplitude
};
struct RxP {                  // a receiver in its control state
    int on, mode;             // mode 0 manual, 1 slow attack, 2 fast attack
    uint32_t seed;
    int sb;                   // AGC sub-block, samples
    float res_sigma, pn_a, pn_w, noise_sigma, iq_g, iq_c, iq_s;
    float iip3_max_dbm, gmax_db, gmin_db, gstep_db, iip3_ceil_dbm, fs0_w, manual_db, fc3, fc1;
    float g_ant, leak_amp;
    float detect, target, clip_step, stronger, lost;
    int settle_iter, lost_blocks, slow_period;
    float in_hi, in_lo, out_hi, out_lo, step_in, step_out;
    double lo;                // the LO as it really is, Hz
};
struct TxS { float theta, leak_phase; int on; };                       // state that moves out and comes back
struct RxS { float theta, gain_db; int fast, settle, lost; float acc; int acc_n; };
struct PairT { float amp, phi0, dphi; };                               // free space between two points: amplitude,
                                                                      // phase at the carrier and per line, cycles
struct Tab {                  // everything a stage needs; the pointers are the device's or the host's
    int K, logK, n_tx, n_rx, R, G, S;
    float df, inv_k;
    double df_d, t0;
    uint64_t seed, event;
    const TxP *txp;
    const RxP *rxp;
    TxS *txs;
    RxS *rxs;
    const int *fresh;         // [n_tx] this event has a new frame
    const float *frame;       // [n_tx][K] complex: frames at the data ports
    float *pin, *air;         // [n_tx][K] complex: spectra on the TX pins, and radiated
    float *out;               // [n_rx][2K + 2]: frames the receivers deliver, the gain in use
    const float *tw;          // [K/2] complex: exp(j 2 pi i / K)
    PairT *pair;              // [n_rx][R]: receiver from radiator (transmitters, then receivers' LO leakage)
    PairT *sp_t;              // [S][n_tx]: scatterer from transmitter
    float *sp_r;              // [n_rx][S] (amplitude, phase per line): receiver from scatterer
    float *sp_rphi;           // [n_rx][S][G]: its phase at each group's carrier
    float *scat;              // [S][G][K] complex: field at the scatterers
    const double *grp_f;      // [G] carrier of each group of radiators
    const int *grp_start, *grp_nfull, *grp_nleak, *grp_list, *rad_grp;
    const int *rx_plat, *rad_plat;   // platform of each antenna: two on the same one (not 0) do not hear each other
    const int *heard;         // [n_rx][G]: the receiver hears some antenna of the group directly
    const double *rx_pos, *rad_pos, *sc_pos;
    const float *sc_rcs;
};
struct Blk {                  // one block's working arrays, K entries each
    float *a_re, *a_im, *b_re, *b_im, *t_re, *t_im, *l_re, *l_im, *w0, *w1, *scal;
};
#define BLK_FLOATS(K) (10 * (K) + 16)
HD static inline void blk_init(Blk &B, float *m, int K) {
    B.a_re = m; B.a_im = m + K; B.b_re = m + 2 * K; B.b_im = m + 3 * K; B.t_re = m + 4 * K; B.t_im = m + 5 * K;
    B.l_re = m + 6 * K; B.l_im = m + 7 * K; B.w0 = m + 8 * K; B.w1 = m + 9 * K; B.scal = m + 10 * K;
}

// ---- per-thread helpers (device and host) -------------------------------------------------------------
HD static inline int bitrev(int k, int bits) {
    int r = 0;
    for (int i = 0; i < bits; i++) { r = (r << 1) | (k & 1); k >>= 1; }
    return r;
}
HD static inline void sa_sincospi(float x, float *s, float *c) {
#ifdef __CUDA_ARCH__
    sincospif(x, s, c);
#else
    *s = sinf(3.14159265358979f * x);
    *c = cosf(3.14159265358979f * x);
#endif
}
// counter-based random numbers: a key per (seed, chip, side, event), a counter per draw
HD static inline uint64_t mix64(uint64_t z) {
    z += 0x9e3779b97f4a7c15ULL;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}
HD static inline uint64_t rng_key(uint64_t seed, uint32_t chip, int side, uint64_t event) {
    return mix64(mix64(seed ^ ((uint64_t)chip << 24) ^ ((uint64_t)side << 60)) ^ event);
}
HD static inline void gauss2(uint64_t key, uint32_t c, float *g1, float *g2) {
    uint64_t r = mix64(key + (uint64_t)c * 0x632be59bd9b4e019ULL);
    float u1 = ((float)(uint32_t)(r >> 32) + 1.0f) * 2.3283064365386963e-10f;      // (0, 1]
    float u2 = (float)(uint32_t)r * 2.3283064365386963e-10f;
    float m = sqrtf(-2.0f * logf(u1)), sn, cs;
    sa_sincospi(2.0f * u2, &sn, &cs);
    *g1 = m * cs;
    *g2 = m * sn;
}
HD static inline float dac_word(float x) {
    return fminf(2047.0f, fmaxf(-2048.0f, floorf(x * 0.0625f + 0.5f))) * (1.0f / 2048.0f);
}
HD static inline float adc_word(float v) {
    return fminf(2047.0f, fmaxf(-2048.0f, floorf(v * 2048.0f + 0.5f)));
}
// third-order Butterworth (corner fc3) and one real pole (fc1) at offset f: ad9361_bb_response
HD static inline void bb_response(float fc3, float fc1, float f, float *hr, float *hi) {
    const float x = f / fc3, dr = 1.0f - 2.0f * x * x, di = 2.0f * x - x * x * x, m = dr * dr + di * di;
    const float pi = f / fc1, pm = 1.0f + pi * pi;
    *hr = (dr - di * pi) / (m * pm);
    *hi = -(dr * pi + di) / (m * pm);
}
HD static inline float legal_gain(const RxP &p, float g) {
    float k = floorf((p.gmax_db - g) / p.gstep_db + 0.5f);
    const float kmax = floorf((p.gmax_db - p.gmin_db) / p.gstep_db);
    k = fmaxf(0.0f, fminf(k, kmax));
    return p.gmax_db - k * p.gstep_db;
}
// what the gain means for the samples: scal[1] the factor to ADC full scale, scal[2] the input intercept, W
HD static inline void set_gain(const RxP &p, float gain_db, float *scal) {
    scal[1] = sqrtf(powf(10.0f, 0.1f * gain_db) / p.fs0_w);
    scal[2] = 1e-3f * powf(10.0f, 0.1f * fminf(p.iip3_max_dbm + (p.gmax_db - gain_db), p.iip3_ceil_dbm));
}
HD static inline void adc_sample(float xi, float xq, const float *scal, float *ci, float *cq) {     // rx_core
    const float k = scal[1] / sqrtf(1.0f + 2.0f * (xi * xi + xq * xq) / scal[2]);
    *ci = adc_word(xi * k);
    *cq = adc_word(xq * k);
}
HD static inline float agc_slow(const RxP &p, float g, float pdb) {
    if (pdb > p.out_hi) g -= p.step_out;
    else if (pdb > p.in_hi) g -= p.step_in;
    else if (pdb < p.out_lo) g += p.step_out;
    else if (pdb < p.in_lo) g += p.step_in;
    return legal_gain(p, g);
}
HD static inline bool agc_adjust(const RxP &p, RxS &st, float pdb, bool clip) {
    if (clip) {
        st.gain_db = legal_gain(p, st.gain_db - p.clip_step);
        return false;
    }
    st.gain_db = legal_gain(p, st.gain_db - (pdb - p.target));
    return fabsf(pdb - p.target) < 1.0f;
}
// the fast-attack state machine at the end of a sub-block (ad9361_rx_symbol)
HD static inline void agc_fast(const RxP &p, RxS &st, float pdb, bool clip) {
    if (st.fast == 0) {
        if (pdb > p.detect || clip) {
            st.fast = 1;
            st.settle = 0;
            if (agc_adjust(p, st, pdb, clip)) { st.fast = 2; st.lost = 0; }
        }
    }
    else if (st.fast == 1) {
        st.settle++;
        const bool done = agc_adjust(p, st, pdb, clip);
        if (done || st.settle >= p.settle_iter) { st.fast = 2; st.lost = 0; }
    }
    else if (clip || pdb > p.target + p.stronger) {
        st.fast = 1;
        st.settle = 0;
        st.lost = 0;
        if (agc_adjust(p, st, pdb, clip)) st.fast = 2;
    }
    else if (pdb < p.target - p.lost) {
        if (++st.lost >= p.lost_blocks) {
            st.fast = 0;
            st.lost = 0;
            st.gain_db = p.gmax_db;
        }
    }
    else
        st.lost = 0;
}

// ---- geometry: free space between every pair of points that hear each other ---------------------------
HD static inline double dist3(const double *a, const double *b) {
    const double x = a[0] - b[0], y = a[1] - b[1], z = a[2] - b[2];
    return sqrt(x * x + y * y + z * z);
}
HD static inline float frac_neg(double cycles) {       // -cycles, mod 1
    const double a = -cycles;
    return (float)(a - floor(a));
}
HD static inline void geom_rx_rad(const Tab &T, long i) {      // receiver r from radiator j
    const int r = (int)(i / T.R), j = (int)(i % T.R), g = T.rad_grp[j];
    PairT q = {0.0f, 0.0f, 0.0f};
    if (g >= 0 && !(T.rx_plat[r] != 0 && T.rx_plat[r] == T.rad_plat[j])) {
        const double d = dist3(T.rx_pos + 3 * r, T.rad_pos + 3 * j);
        if (d > 1e-9) {                                // an antenna does not hear itself
            const double f = T.grp_f[g], tau = d / C0;
            q.amp = (float)(T.rxp[r].g_ant * C0 / (4.0 * PI_D * d * f));
            q.phi0 = frac_neg(f * tau);
            q.dphi = frac_neg(T.df_d * tau);
        }
    }
    T.pair[i] = q;
}
HD static inline void geom_sc_tx(const Tab &T, long i) {       // scatterer s from transmitter t
    const int s = (int)(i / T.n_tx), t = (int)(i % T.n_tx), g = T.rad_grp[t];
    PairT q = {0.0f, 0.0f, 0.0f};
    if (g >= 0) {
        const double d = dist3(T.sc_pos + 3 * s, T.rad_pos + 3 * t);
        if (d > 1e-9) {
            const double f = T.grp_f[g], tau = d / C0;
            q.amp = (float)(C0 / (4.0 * PI_D * d * f));
            q.phi0 = frac_neg(f * tau);
            q.dphi = frac_neg(T.df_d * tau);
        }
    }
    T.sp_t[i] = q;
}
HD static inline void geom_rx_sc(const Tab &T, long i) {       // receiver r from scatterer s
    const int r = (int)(i / T.S), s = (int)(i % T.S);
    const double d = dist3(T.rx_pos + 3 * r, T.sc_pos + 3 * s);
    const double tau = d / C0;
    // re-radiation: sqrt(4 pi rcs) / lambda, times free space lambda / (4 pi d): the same at every line
    T.sp_r[2 * i] = d > 1e-9 ? (float)(T.rxp[r].g_ant * sqrt(4.0 * PI_D * (double)T.sc_rcs[s]) / (4.0 * PI_D * d)) : 0.0f;
    T.sp_r[2 * i + 1] = frac_neg(T.df_d * tau);
    for (int g = 0; g < T.G; g++)
        T.sp_rphi[i * T.G + g] = frac_neg(T.grp_f[g] * tau);
}

// ---- the stages, twice ---------------------------------------------------------------------------------
#define STAGE __device__ static
#define NAME(f) f##_dev
#define PAR(k) { const int k = threadIdx.x; {
#define END_PAR } } __syncthreads();
#define SEQ if (threadIdx.x == 0) {
#define END_SEQ } __syncthreads();
#include "spectral_stages.inc"
#undef STAGE
#undef NAME
#undef PAR
#undef END_PAR
#undef SEQ
#undef END_SEQ

#define STAGE static
#define NAME(f) f##_host
#define PAR(k) for (int k = 0; k < K; k++) {
#define END_PAR }
#define SEQ {
#define END_SEQ }
#include "spectral_stages.inc"
#undef STAGE
#undef NAME
#undef PAR
#undef END_PAR
#undef SEQ
#undef END_SEQ

extern __shared__ float sa_shared[];
__global__ void k_tx(Tab T) { Blk B; blk_init(B, sa_shared, T.K); tx_stage_dev(T, B, blockIdx.x); }
__global__ void k_scat(Tab T) { Blk B; blk_init(B, sa_shared, T.K); scat_stage_dev(T, B, blockIdx.x); }
__global__ void k_rx(Tab T) { Blk B; blk_init(B, sa_shared, T.K); rx_stage_dev(T, B, blockIdx.x); }
__global__ void k_geom(Tab T, int what, long n) {
    const long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    if (what == 0) geom_rx_rad(T, i);
    else if (what == 1) geom_sc_tx(T, i);
    else geom_rx_sc(T, i);
}

// ---- the engine ----------------------------------------------------------------------------------------
#define CK(e) do { cudaError_t _e = (e); if (_e != cudaSuccess) { \
    fprintf(stderr, "spectral-accel: CUDA error %s at %s:%d\n", cudaGetErrorString(_e), __FILE__, __LINE__); exit(1); } } while (0)

namespace {

struct Chip {
    uint32_t seed = 1;
    bool has_params = false;
    double P[SA_P_COUNT] = {0};
    int tx_ant = -1, rx_ant = -1, tx_el = -1, rx_el = -1;
    uint64_t fetched = ~0ULL;
};
struct Ant { double gain_dbi = 0, pol = 0, pos[3] = {0, 0, 0}; bool arena = false; int chip = -1, pin = -1, platform = 0; };
struct Scat { double rcs = 1, pos[3] = {0, 0, 0}; };
struct Sched { double t; int mode; };

template <class T> struct Dev {                       // an array that lives on the host and, on a GPU, on the device
    std::vector<T> h;
    T *d = nullptr;
    size_t dn = 0;
    void size(size_t n, bool gpu) {
        h.assign(n, T());
        if (gpu && n > dn) {
            if (d) CK(cudaFree(d));
            CK(cudaMalloc(&d, n * sizeof(T)));
            dn = n;
        }
        if (gpu && n) CK(cudaMemset(d, 0, n * sizeof(T)));
    }
    void up(bool gpu, size_t first = 0, size_t n = (size_t)-1) {
        if (!gpu || h.empty()) return;
        if (n == (size_t)-1) n = h.size() - first;
        if (n) CK(cudaMemcpy(d + first, h.data() + first, n * sizeof(T), cudaMemcpyHostToDevice));
    }
    void down(bool gpu, size_t first = 0, size_t n = (size_t)-1) {
        if (!gpu || h.empty()) return;
        if (n == (size_t)-1) n = h.size() - first;
        if (n) CK(cudaMemcpy(h.data() + first, d + first, n * sizeof(T), cudaMemcpyDeviceToHost));
    }
    T *p(bool gpu) { return gpu ? d : h.data(); }
};

struct Engine {
    std::mutex mu;
    bool committed = false, declined = false, gpu = false, out = false, dirty = false;
    bool params_dirty = true, geom_dirty = true, verbose = false, env_read = false;
    int K = 0, logK = 0, n_tx = 0, n_rx = 0, R = 0, G = 0, S = 0;
    double fs = 0, df = 0;
    uint64_t seed = 1, event = 0;
    double seconds = 0, geom_seconds = 0, start_seconds = 0;
    uint64_t geom_runs = 0;
    std::vector<Chip> chips;
    std::vector<Ant> ants;
    std::vector<Scat> scats;
    std::vector<int> tx_chip, rx_chip;
    std::vector<Sched> sched;
    Dev<TxP> txp;
    Dev<RxP> rxp;
    Dev<TxS> txs;
    Dev<RxS> rxs;
    Dev<int> fresh, grp_start, grp_nfull, grp_nleak, grp_list, rad_grp, rx_plat, rad_plat, heard;
    Dev<float> frame, pin, air, outp, tw, sp_r, sp_rphi, scat, sc_rcs;
    Dev<PairT> pair, sp_t;
    Dev<double> grp_f, rx_pos, rad_pos, sc_pos;
    std::vector<float> scratch;                       // host path: one block's arrays per thread
    bool any_fresh = false;
};
Engine E;

double now_s() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

void read_env() {
    if (E.env_read) return;
    E.env_read = true;
    const char *v = getenv("SPECTRAL_ACCEL_VERBOSE");
    E.verbose = v && *v && strcmp(v, "0");
    v = getenv("SPECTRAL_ACCEL_SEED");
    if (v && *v) E.seed = strtoull(v, nullptr, 10);
    v = getenv("SPECTRAL_ACCEL_DEVICE");
    E.gpu = !(v && !strcmp(v, "cpu"));
    if (E.gpu) {
        int n = 0;
        const double t0 = now_s();
        const bool none = cudaGetDeviceCount(&n) != cudaSuccess || n == 0;
        if (!none) cudaFree(0);                        // brings the device up now, where it can be timed
        E.start_seconds += now_s() - t0;
        if (none) {
            fprintf(stderr, "spectral-accel: no CUDA device, running the same stages on the CPU\n");
            E.gpu = false;
        }
    }
    // SPECTRAL_ACCEL_SCHEDULE: "0:out,2ms:in,5ms:out" -- when the data and processing move out and come back
    v = getenv("SPECTRAL_ACCEL_SCHEDULE");
    std::string s = v && *v ? v : "0:out";
    size_t at = 0;
    while (at < s.size()) {
        size_t end = s.find(',', at);
        if (end == std::string::npos) end = s.size();
        std::string item = s.substr(at, end - at);
        at = end + 1;
        size_t colon = item.find(':');
        if (colon == std::string::npos) {
            fprintf(stderr, "spectral-accel: SPECTRAL_ACCEL_SCHEDULE item '%s' is not time:out or time:in\n", item.c_str());
            exit(1);
        }
        char *unit = nullptr;
        double t = strtod(item.c_str(), &unit);
        std::string u(unit, item.c_str() + colon - unit);
        if (u == "ms") t *= 1e-3;
        else if (u == "us") t *= 1e-6;
        else if (u == "ns") t *= 1e-9;
        else if (u != "" && u != "s") {
            fprintf(stderr, "spectral-accel: SPECTRAL_ACCEL_SCHEDULE: unit '%s' is not s, ms, us or ns\n", u.c_str());
            exit(1);
        }
        std::string m = item.substr(colon + 1);
        if (m != "out" && m != "in") {
            fprintf(stderr, "spectral-accel: SPECTRAL_ACCEL_SCHEDULE: '%s' is not out or in\n", m.c_str());
            exit(1);
        }
        E.sched.push_back({t, m == "out"});
    }
}

Chip *chip_at(double id, const char *who) {
    const long i = lround(id);
    if (i < 0 || i >= (long)E.chips.size()) {
        fprintf(stderr, "spectral-accel: %s: no chip %ld\n", who, i);
        exit(1);
    }
    return &E.chips[i];
}

Tab tab(bool gpu) {
    Tab T;
    T.K = E.K; T.logK = E.logK; T.n_tx = E.n_tx; T.n_rx = E.n_rx; T.R = E.R; T.G = E.G; T.S = E.S;
    T.df = (float)E.df; T.inv_k = 1.0f / E.K; T.df_d = E.df; T.t0 = 0; T.seed = E.seed; T.event = E.event;
    T.txp = E.txp.p(gpu); T.rxp = E.rxp.p(gpu); T.txs = E.txs.p(gpu); T.rxs = E.rxs.p(gpu);
    T.fresh = E.fresh.p(gpu); T.frame = E.frame.p(gpu); T.pin = E.pin.p(gpu); T.air = E.air.p(gpu);
    T.out = E.outp.p(gpu); T.tw = E.tw.p(gpu); T.pair = E.pair.p(gpu); T.sp_t = E.sp_t.p(gpu);
    T.sp_r = E.sp_r.p(gpu); T.sp_rphi = E.sp_rphi.p(gpu); T.scat = E.scat.p(gpu); T.grp_f = E.grp_f.p(gpu);
    T.grp_start = E.grp_start.p(gpu); T.grp_nfull = E.grp_nfull.p(gpu); T.grp_nleak = E.grp_nleak.p(gpu);
    T.grp_list = E.grp_list.p(gpu); T.rad_grp = E.rad_grp.p(gpu); T.rx_pos = E.rx_pos.p(gpu);
    T.rx_plat = E.rx_plat.p(gpu); T.rad_plat = E.rad_plat.p(gpu); T.heard = E.heard.p(gpu);
    T.rad_pos = E.rad_pos.p(gpu); T.sc_pos = E.sc_pos.p(gpu); T.sc_rcs = E.sc_rcs.p(gpu);
    return T;
}

// The chips' control states -> the tables: constants per element, and the groups of radiators that
// share a carrier (what one receiver can add up line by line before it leaves the lines).
void configure() {
    E.params_dirty = false;
    E.geom_dirty = true;
    std::map<double, int> groups;
    std::vector<double> gf;
    auto group_of = [&](double f) {
        auto it = groups.find(f);
        if (it != groups.end()) return it->second;
        const int g = (int)gf.size();
        groups[f] = g;
        gf.push_back(f);
        return g;
    };
    for (int e = 0; e < E.n_tx; e++) {
        const Chip &c = E.chips[E.tx_chip[e]];
        TxP &p = E.txp.h[e];
        p = TxP();
        p.seed = c.seed;
        p.g_ant = (float)pow(10.0, E.ants[c.tx_ant].gain_dbi / 20.0);
        E.rad_grp.h[e] = -1;
        if (!c.has_params) continue;
        const double *P = c.P;
        p.on = P[SA_P_TX_ON] != 0.0;
        p.amp = (float)P[SA_P_TX_AMP]; p.ip3 = (float)P[SA_P_TX_IP3]; p.res_sigma = (float)P[SA_P_TX_RES];
        p.pn_a = (float)P[SA_P_TX_PN_A]; p.pn_w = (float)P[SA_P_TX_PN_W]; p.leak_amp = (float)P[SA_P_TX_LEAK];
        p.noise_sigma = (float)P[SA_P_TX_NOISE]; p.fc3 = (float)P[SA_P_TX_FC3]; p.fc1 = (float)P[SA_P_TX_FC1];
        E.rad_grp.h[e] = group_of(P[SA_P_TX_FREQ]);
    }
    for (int e = 0; e < E.n_rx; e++) {
        const Chip &c = E.chips[E.rx_chip[e]];
        RxP &p = E.rxp.h[e];
        p = RxP();
        p.seed = c.seed;
        p.sb = 16;
        p.g_ant = (float)pow(10.0, E.ants[c.rx_ant].gain_dbi / 20.0);
        E.rad_grp.h[E.n_tx + e] = -1;
        if (!c.has_params) continue;
        const double *P = c.P;
        p.on = P[SA_P_RX_ON] != 0.0;
        p.mode = (int)lround(P[SA_P_AGC_MODE]);
        p.sb = (int)lround(P[SA_P_FAST_BLOCK]);
        p.res_sigma = (float)P[SA_P_RX_RES]; p.pn_a = (float)P[SA_P_RX_PN_A]; p.pn_w = (float)P[SA_P_RX_PN_W];
        p.noise_sigma = (float)P[SA_P_RX_NOISE]; p.iq_g = (float)P[SA_P_RX_IQ_G]; p.iq_c = (float)P[SA_P_RX_IQ_C];
        p.iq_s = (float)P[SA_P_RX_IQ_S]; p.iip3_max_dbm = (float)P[SA_P_RX_IIP3_MAX]; p.gmax_db = (float)P[SA_P_RX_GMAX];
        p.gmin_db = (float)P[SA_P_RX_GMIN]; p.gstep_db = (float)P[SA_P_RX_GSTEP]; p.iip3_ceil_dbm = (float)P[SA_P_RX_IIP3_CEIL];
        p.fs0_w = (float)P[SA_P_RX_FS0]; p.manual_db = (float)P[SA_P_AGC_MANUAL]; p.fc3 = (float)P[SA_P_RX_FC3];
        p.fc1 = (float)P[SA_P_RX_FC1]; p.leak_amp = (float)P[SA_P_RX_LEAK];
        p.detect = (float)P[SA_P_FAST_DETECT]; p.target = (float)P[SA_P_FAST_TARGET]; p.clip_step = (float)P[SA_P_FAST_CLIP_STEP];
        p.stronger = (float)P[SA_P_FAST_STRONGER]; p.lost = (float)P[SA_P_FAST_LOST];
        p.settle_iter = (int)lround(P[SA_P_FAST_SETTLE]); p.lost_blocks = (int)lround(P[SA_P_FAST_LOST_BLOCKS]);
        p.slow_period = (int)lround(P[SA_P_SLOW_PERIOD]);
        p.in_hi = (float)P[SA_P_SLOW_INNER_HIGH]; p.in_lo = (float)P[SA_P_SLOW_INNER_LOW];
        p.out_hi = (float)P[SA_P_SLOW_OUTER_HIGH]; p.out_lo = (float)P[SA_P_SLOW_OUTER_LOW];
        p.step_in = (float)P[SA_P_SLOW_STEP_INNER]; p.step_out = (float)P[SA_P_SLOW_STEP_OUTER];
        p.lo = P[SA_P_RX_FREQ];
        if (p.sb < 1 || E.K % p.sb) {
            fprintf(stderr, "spectral-accel: %d lines per event is not a whole number of AGC sub-blocks of %d\n", E.K, p.sb);
            exit(1);
        }
        E.rad_grp.h[E.n_tx + e] = group_of(P[SA_P_RX_FREQ]);
    }
    const int G = (int)gf.size();
    if (G != E.G || E.grp_f.h.size() != (size_t)G) {
        E.G = G;
        E.grp_f.size(G, E.gpu);
        E.grp_start.size(G, E.gpu);
        E.grp_nfull.size(G, E.gpu);
        E.grp_nleak.size(G, E.gpu);
        E.scat.size((size_t)E.S * G * 2 * E.K, E.gpu);
        E.sp_rphi.size((size_t)E.n_rx * E.S * G, E.gpu);
        E.heard.size((size_t)E.n_rx * G, E.gpu);
    }
    int at = 0;
    for (int g = 0; g < G; g++) {
        E.grp_f.h[g] = gf[g];
        E.grp_start.h[g] = at;
        int nf = 0, nl = 0;
        for (int e = 0; e < E.n_tx; e++)
            if (E.rad_grp.h[e] == g) { E.grp_list.h[at++] = e; nf++; }
        for (int e = 0; e < E.n_rx; e++)
            if (E.rad_grp.h[E.n_tx + e] == g) { E.grp_list.h[at++] = e; nl++; }
        E.grp_nfull.h[g] = nf;
        E.grp_nleak.h[g] = nl;
    }
    // which groups each receiver hears directly at all (platforms, and not itself)
    for (int e = 0; e < E.n_tx; e++) E.rad_plat.h[e] = E.ants[E.chips[E.tx_chip[e]].tx_ant].platform;
    for (int e = 0; e < E.n_rx; e++) E.rx_plat.h[e] = E.rad_plat.h[E.n_tx + e] = E.ants[E.chips[E.rx_chip[e]].rx_ant].platform;
    std::fill(E.heard.h.begin(), E.heard.h.end(), 0);
    for (int r = 0; r < E.n_rx; r++)
        for (int j = 0; j < E.R; j++) {
            const int g = E.rad_grp.h[j];
            if (g >= 0 && j != E.n_tx + r && !(E.rx_plat.h[r] != 0 && E.rx_plat.h[r] == E.rad_plat.h[j]))
                E.heard.h[(size_t)r * G + g] = 1;
        }
    E.rx_plat.up(E.gpu); E.rad_plat.up(E.gpu); E.heard.up(E.gpu);
    E.txp.up(E.gpu); E.rxp.up(E.gpu); E.rad_grp.up(E.gpu); E.grp_f.up(E.gpu); E.grp_start.up(E.gpu);
    E.grp_nfull.up(E.gpu); E.grp_nleak.up(E.gpu); E.grp_list.up(E.gpu);
}

void geometry() {
    E.geom_dirty = false;
    const double t0 = now_s();
    for (int e = 0; e < E.n_tx; e++)
        memcpy(&E.rad_pos.h[3 * e], E.ants[E.chips[E.tx_chip[e]].tx_ant].pos, 3 * sizeof(double));
    for (int e = 0; e < E.n_rx; e++) {
        memcpy(&E.rx_pos.h[3 * e], E.ants[E.chips[E.rx_chip[e]].rx_ant].pos, 3 * sizeof(double));
        memcpy(&E.rad_pos.h[3 * (E.n_tx + e)], &E.rx_pos.h[3 * e], 3 * sizeof(double));
    }
    for (int s = 0; s < E.S; s++) {
        memcpy(&E.sc_pos.h[3 * s], E.scats[s].pos, 3 * sizeof(double));
        E.sc_rcs.h[s] = (float)E.scats[s].rcs;
    }
    E.rad_pos.up(E.gpu); E.rx_pos.up(E.gpu); E.sc_pos.up(E.gpu); E.sc_rcs.up(E.gpu);
    const Tab T = tab(E.gpu);
    const long n0 = (long)E.n_rx * E.R, n1 = (long)E.S * E.n_tx, n2 = (long)E.n_rx * E.S;
    if (E.gpu) {
        if (n0) k_geom<<<(unsigned)((n0 + 255) / 256), 256>>>(T, 0, n0);
        if (n1) k_geom<<<(unsigned)((n1 + 255) / 256), 256>>>(T, 1, n1);
        if (n2) k_geom<<<(unsigned)((n2 + 255) / 256), 256>>>(T, 2, n2);
    }
    else {
        #pragma omp parallel for schedule(static) if (n0 > 4096)
        for (long i = 0; i < n0; i++) geom_rx_rad(T, i);
        for (long i = 0; i < n1; i++) geom_sc_tx(T, i);
        for (long i = 0; i < n2; i++) geom_rx_sc(T, i);
    }
    E.geom_seconds += now_s() - t0;
    E.geom_runs++;
}

// one event, with what is new at the data ports
void step(double now) {
    if (!E.committed) return;
    const double t_start = now_s();
    if (E.params_dirty) configure();
    if (E.geom_dirty) geometry();
    if (E.any_fresh) {
        E.fresh.up(E.gpu);
        E.frame.up(E.gpu);
    }
    Tab T = tab(E.gpu);
    T.t0 = now;
    const size_t sh = BLK_FLOATS(E.K) * sizeof(float);
    if (E.gpu) {
        if (E.any_fresh && E.n_tx) k_tx<<<E.n_tx, E.K, sh>>>(T);
        if (E.S && E.n_tx) k_scat<<<E.S, E.K, sh>>>(T);
        if (E.n_rx) k_rx<<<E.n_rx, E.K, sh>>>(T);
        E.outp.down(true);                             // waits for the kernels
        CK(cudaGetLastError());
    }
    else {
        const int nt = omp_get_max_threads();
        if (E.scratch.size() < (size_t)nt * BLK_FLOATS(E.K)) E.scratch.assign((size_t)nt * BLK_FLOATS(E.K), 0.0f);
        #pragma omp parallel
        {
            Blk B;
            blk_init(B, E.scratch.data() + (size_t)omp_get_thread_num() * BLK_FLOATS(E.K), E.K);
            if (E.any_fresh) {
                #pragma omp for schedule(static)
                for (int e = 0; e < E.n_tx; e++) tx_stage_host(T, B, e);
            }
            #pragma omp for schedule(static)
            for (int s = 0; s < E.S; s++) scat_stage_host(T, B, s);
            #pragma omp for schedule(static)
            for (int r = 0; r < E.n_rx; r++) rx_stage_host(T, B, r);
        }
    }
    if (E.any_fresh) {
        std::fill(E.fresh.h.begin(), E.fresh.h.end(), 0);
        E.any_fresh = false;
    }
    E.event++;
    E.dirty = false;
    E.seconds += now_s() - t_start;
}

void report() {
    if (E.event == 0) return;
    fprintf(stderr, "spectral-accel: %llu events on the %s (%d transmitters, %d receivers, %d scatterers, %d lines), "
            "%.3f ms each; geometry %llu times, %.3f ms each; start-up %.0f ms\n", (unsigned long long)E.event,
            E.gpu ? "GPU" : "CPU", E.n_tx, E.n_rx, E.S, E.K, E.seconds / E.event * 1e3, (unsigned long long)E.geom_runs,
            E.geom_runs ? E.geom_seconds / E.geom_runs * 1e3 : 0.0, E.start_seconds * 1e3);
}

} // namespace

// ---- the interface -------------------------------------------------------------------------------------
extern "C" {

void sa_reset(void) {
    std::lock_guard<std::mutex> lock(E.mu);
    report();
    E.chips.clear(); E.ants.clear(); E.scats.clear(); E.tx_chip.clear(); E.rx_chip.clear();
    E.committed = E.declined = E.out = E.dirty = E.any_fresh = false;
    E.params_dirty = E.geom_dirty = true;
    E.K = E.logK = E.n_tx = E.n_rx = E.R = E.G = E.S = 0;
    E.event = 0;
    E.seconds = E.geom_seconds = 0;
    E.geom_runs = 0;
}

double sa_chip_new(double seed) {
    std::lock_guard<std::mutex> lock(E.mu);
    read_env();
    Chip c;
    c.seed = (uint32_t)llround(seed);
    E.chips.push_back(c);
    return (double)(E.chips.size() - 1);
}

double sa_antenna_new(double gain_dbi, double pol_angle) {
    std::lock_guard<std::mutex> lock(E.mu);
    read_env();
    Ant a;
    a.gain_dbi = gain_dbi;
    a.pol = pol_angle;
    E.ants.push_back(a);
    return (double)(E.ants.size() - 1);
}

double sa_scatterer_new(double rcs_m2) {
    std::lock_guard<std::mutex> lock(E.mu);
    read_env();
    Scat s;
    s.rcs = rcs_m2;
    E.scats.push_back(s);
    return (double)(E.scats.size() - 1);
}

void sa_wire(double chip, double pin, double antenna) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_wire");
    const long a = lround(antenna), p = lround(pin);
    if (a < 0 || a >= (long)E.ants.size() || p < 0 || p > 1) {
        fprintf(stderr, "spectral-accel: sa_wire: no antenna %ld or pin %ld\n", a, p);
        exit(1);
    }
    int &slot = p == 0 ? c->tx_ant : c->rx_ant;
    if (slot >= 0 || E.ants[a].chip >= 0) {
        fprintf(stderr, "spectral-accel: declined: a chip pin or an antenna feed has more than one wire\n");
        E.declined = true;
        return;
    }
    slot = (int)a;
    E.ants[a].chip = (int)lround(chip);
    E.ants[a].pin = (int)p;
}

void sa_arena_antenna(double antenna) {
    std::lock_guard<std::mutex> lock(E.mu);
    const long a = lround(antenna);
    if (a >= 0 && a < (long)E.ants.size()) E.ants[a].arena = true;
}

void sa_antenna_platform(double antenna, double platform) {
    std::lock_guard<std::mutex> lock(E.mu);
    const long a = lround(antenna);
    if (a >= 0 && a < (long)E.ants.size()) E.ants[a].platform = (int)lround(platform);
    E.params_dirty = true;
}

double sa_commit(void) {
    std::lock_guard<std::mutex> lock(E.mu);
    read_env();
    if (E.committed) return 1.0;
    const char *why = nullptr;
    int K = 0;
    double fs = 0;
    for (const Chip &c : E.chips)
        if (c.has_params) {
            if (K && ((int)lround(c.P[SA_P_LINES]) != K || c.P[SA_P_FS] != fs))
                why = "the chips do not all have the same sample rate and lines per event";
            K = (int)lround(c.P[SA_P_LINES]);
            fs = c.P[SA_P_FS];
        }
    if (!K) why = "no chip has a configuration yet";
    else if (K < 16 || K > 1024 || (K & (K - 1))) why = "lines per event must be a power of two from 16 to 1024";
    for (const Ant &a : E.ants) {
        if (a.pol != 0.0) why = "an antenna has a polarisation angle (the accelerator carries one polarisation)";
        if (a.chip >= 0 && !a.arena) why = "an antenna wired to a chip is not in the arena";
        if (a.chip < 0 && a.arena) why = "an antenna in the arena is not wired to a chip pin";
    }
    if (E.declined) why = "the wiring is not one antenna per chip pin";
    if (why) {
        fprintf(stderr, "spectral-accel: declined: %s; the design stays in the simulator\n", why);
        E.declined = true;
        return 0.0;
    }
    E.K = K;
    E.logK = 0;
    while ((1 << E.logK) < K) E.logK++;
    E.fs = fs;
    E.df = fs / K;
    for (size_t i = 0; i < E.chips.size(); i++) {
        if (E.chips[i].tx_ant >= 0) { E.chips[i].tx_el = (int)E.tx_chip.size(); E.tx_chip.push_back((int)i); }
        if (E.chips[i].rx_ant >= 0) { E.chips[i].rx_el = (int)E.rx_chip.size(); E.rx_chip.push_back((int)i); }
    }
    E.n_tx = (int)E.tx_chip.size();
    E.n_rx = (int)E.rx_chip.size();
    E.R = E.n_tx + E.n_rx;
    E.S = (int)E.scats.size();
    E.G = -1;
    const bool g = E.gpu;
    const size_t K2 = 2 * (size_t)K;
    const double t_alloc = now_s();
    E.txp.size(E.n_tx, g); E.rxp.size(E.n_rx, g); E.txs.size(E.n_tx, g); E.rxs.size(E.n_rx, g);
    E.fresh.size(E.n_tx, g); E.frame.size(E.n_tx * K2, g); E.pin.size(E.n_tx * K2, g); E.air.size(E.n_tx * K2, g);
    E.outp.size((size_t)E.n_rx * (K2 + 2), g); E.tw.size(K, g);
    E.pair.size((size_t)E.n_rx * E.R, g); E.sp_t.size((size_t)E.S * E.n_tx, g); E.sp_r.size((size_t)E.n_rx * E.S * 2, g);
    E.grp_list.size(E.R, g); E.rad_grp.size(E.R, g); E.rx_plat.size(E.n_rx, g); E.rad_plat.size(E.R, g);
    E.rx_pos.size(3 * (size_t)E.n_rx, g); E.rad_pos.size(3 * (size_t)E.R, g); E.sc_pos.size(3 * (size_t)E.S, g);
    E.sc_rcs.size(E.S, g);
    for (int i = 0; i < K / 2; i++) {
        E.tw.h[2 * i] = (float)cos(2.0 * PI_D * i / K);
        E.tw.h[2 * i + 1] = (float)sin(2.0 * PI_D * i / K);
    }
    E.tw.up(g);
    for (int e = 0; e < E.n_rx; e++) {                 // until the simulator's state is pushed
        const Chip &c = E.chips[E.rx_chip[e]];
        E.rxs.h[e].gain_db = c.has_params ? (float)(c.P[SA_P_AGC_MODE] == 0.0 ? c.P[SA_P_AGC_MANUAL] : c.P[SA_P_RX_GMAX]) : 0.0f;
    }
    E.rxs.up(g);
    E.start_seconds += now_s() - t_alloc;
    E.committed = true;
    E.params_dirty = E.geom_dirty = true;
    if (E.verbose)
        fprintf(stderr, "spectral-accel: admitted: %d transmitters, %d receivers, %d scatterers, %d lines per event, on the %s\n",
                E.n_tx, E.n_rx, E.S, K, g ? "GPU" : "CPU");
    static bool registered = false;
    if (!registered) { registered = true; atexit(report); }
    return 1.0;
}

void sa_chip_params(double chip, const double *p, int64_t n) {
    std::lock_guard<std::mutex> lock(E.mu);
    read_env();
    Chip *c = chip_at(chip, "sa_chip_params");
    if (n != SA_P_COUNT || p[SA_P_VERSION] != SA_PARAMS_VERSION) {
        fprintf(stderr, "spectral-accel: sa_chip_params: %lld values of layout %g, this library takes %d of layout %g\n",
                (long long)n, n > 0 ? p[0] : 0.0, SA_P_COUNT, SA_PARAMS_VERSION);
        exit(1);
    }
    if (E.committed && ((int)lround(p[SA_P_LINES]) != E.K || p[SA_P_FS] != E.fs)) {
        fprintf(stderr, "spectral-accel: a chip changed its sample rate or lines per event while its design is admitted\n");
        exit(1);
    }
    memcpy(c->P, p, sizeof c->P);
    c->has_params = true;
    E.params_dirty = true;
}

void sa_antenna_position(double antenna, double x, double y, double z) {
    std::lock_guard<std::mutex> lock(E.mu);
    const long a = lround(antenna);
    if (a < 0 || a >= (long)E.ants.size()) return;
    E.ants[a].pos[0] = x; E.ants[a].pos[1] = y; E.ants[a].pos[2] = z;
    E.geom_dirty = true;
}

void sa_scatterer_position(double scatterer, double x, double y, double z) {
    std::lock_guard<std::mutex> lock(E.mu);
    const long s = lround(scatterer);
    if (s < 0 || s >= (long)E.scats.size()) return;
    E.scats[s].pos[0] = x; E.scats[s].pos[1] = y; E.scats[s].pos[2] = z;
    E.geom_dirty = true;
}

void sa_agc_init(double chip, double gain_db) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_agc_init");
    if (!E.committed || c->rx_el < 0) return;
    E.rxs.down(E.gpu, c->rx_el, 1);
    RxS &s = E.rxs.h[c->rx_el];
    s.gain_db = (float)gain_db;
    s.fast = s.settle = s.lost = s.acc_n = 0;
    s.acc = 0.0f;
    E.rxs.up(E.gpu, c->rx_el, 1);
}

double sa_schedule_count(void) { std::lock_guard<std::mutex> lock(E.mu); read_env(); return (double)E.sched.size(); }
double sa_schedule_time(double i) { return E.sched[(size_t)lround(i)].t; }
double sa_schedule_mode(double i) { return (double)E.sched[(size_t)lround(i)].mode; }

void sa_set_mode(double mode) {
    std::lock_guard<std::mutex> lock(E.mu);
    E.out = mode != 0.0;
    E.dirty = false;
    if (E.verbose) fprintf(stderr, "spectral-accel: data and processing %s\n", E.out ? "move out to the accelerator" : "come back to the simulator");
}

void sa_push_tx(double chip, const double *state, int64_t ns, const double *lines, int64_t n) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_push_tx");
    if (!E.committed || c->tx_el < 0 || ns < 3 || n < 2 * E.K) return;
    if (E.params_dirty) configure();
    const int e = c->tx_el;
    const size_t K2 = 2 * (size_t)E.K;
    E.txs.h[e].theta = (float)state[0];
    E.txs.h[e].leak_phase = (float)state[1];
    E.txs.h[e].on = state[2] != 0.0;
    for (size_t k = 0; k < K2; k++) {
        E.pin.h[e * K2 + k] = (float)lines[k];
        E.air.h[e * K2 + k] = (float)lines[k] * E.txp.h[e].g_ant;
    }
    E.txs.up(E.gpu, e, 1);
    E.pin.up(E.gpu, e * K2, K2);
    E.air.up(E.gpu, e * K2, K2);
}

void sa_pull_tx(double chip, double *state, int64_t ns, double *lines, int64_t n) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_pull_tx");
    if (!E.committed || c->tx_el < 0 || ns < 3 || n < 2 * E.K) return;
    const int e = c->tx_el;
    const size_t K2 = 2 * (size_t)E.K;
    E.txs.down(E.gpu, e, 1);
    E.pin.down(E.gpu, e * K2, K2);
    state[0] = E.txs.h[e].theta;
    state[1] = E.txs.h[e].leak_phase;
    state[2] = E.txs.h[e].on;
    for (size_t k = 0; k < K2; k++) lines[k] = E.pin.h[e * K2 + k];
}

void sa_push_rx(double chip, const double *state, int64_t ns) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_push_rx");
    if (!E.committed || c->rx_el < 0 || ns < 7) return;
    RxS &s = E.rxs.h[c->rx_el];
    s.theta = (float)state[0]; s.gain_db = (float)state[1]; s.fast = (int)lround(state[2]);
    s.settle = (int)lround(state[3]); s.lost = (int)lround(state[4]); s.acc = (float)state[5]; s.acc_n = (int)lround(state[6]);
    E.rxs.up(E.gpu, c->rx_el, 1);
}

void sa_pull_rx(double chip, double *state, int64_t ns) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_pull_rx");
    if (!E.committed || c->rx_el < 0 || ns < 7) return;
    E.rxs.down(E.gpu, c->rx_el, 1);
    const RxS &s = E.rxs.h[c->rx_el];
    state[0] = s.theta; state[1] = s.gain_db; state[2] = s.fast; state[3] = s.settle; state[4] = s.lost;
    state[5] = s.acc; state[6] = s.acc_n;
}

void sa_tx(double chip, double seq, const double *lines, int64_t n) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_tx");
    (void)seq;
    if (!E.committed || c->tx_el < 0 || n < 2 * E.K) return;
    const size_t K2 = 2 * (size_t)E.K;
    float *f = &E.frame.h[c->tx_el * K2];
    for (size_t k = 0; k < K2; k++) f[k] = (float)lines[k];
    E.fresh.h[c->tx_el] = 1;
    E.any_fresh = true;
    E.dirty = true;
}

void sa_tx_all(const float *frames, int64_t n) {
    std::lock_guard<std::mutex> lock(E.mu);
    if (!E.committed || n < (int64_t)E.frame.h.size()) return;
    memcpy(E.frame.h.data(), frames, E.frame.h.size() * sizeof(float));
    std::fill(E.fresh.h.begin(), E.fresh.h.end(), 1);
    E.any_fresh = true;
    E.dirty = true;
}

void sa_touch(void) {
    std::lock_guard<std::mutex> lock(E.mu);
    if (E.out) E.dirty = true;
}

void sa_step(double now) {
    std::lock_guard<std::mutex> lock(E.mu);
    step(now);
}

double sa_rx(double chip, double now, double *buf, int64_t n) {
    std::lock_guard<std::mutex> lock(E.mu);
    Chip *c = chip_at(chip, "sa_rx");
    if (!E.committed) return 0.0;
    if (E.dirty) step(now);
    if (c->rx_el < 0 || E.event == 0 || c->fetched == E.event || !E.rxp.h[c->rx_el].on || n < 2 * E.K + 1) return 0.0;
    c->fetched = E.event;
    const float *o = &E.outp.h[(size_t)c->rx_el * (2 * E.K + 2)];
    for (int k = 0; k < 2 * E.K + 1; k++) buf[k] = o[k];
    return (double)(E.event % 1000000000ULL + 1);
}

// VHDL's form (a procedure): buf[2K + 1] gets the sequence number
void sa_rx_buf(double chip, double now, double *buf, int64_t n) {
    if (n < 2 * E.K + 2) return;
    buf[2 * E.K + 1] = sa_rx(chip, now, buf, n);
}

double sa_lines(void) { return (double)E.K; }
double sa_events(void) { return (double)E.event; }
double sa_device_seconds(void) { return E.seconds; }
double sa_on_gpu(void) { return E.gpu ? 1.0 : 0.0; }

int64_t sa_read(double what, float *buf, int64_t n) {
    std::lock_guard<std::mutex> lock(E.mu);
    if (!E.committed) return 0;
    Dev<float> &a = what == 0.0 ? E.outp : E.air;
    if (what != 0.0) a.down(E.gpu);
    const int64_t m = (int64_t)a.h.size() < n ? (int64_t)a.h.size() : n;
    memcpy(buf, a.h.data(), m * sizeof(float));
    return m;
}

} // extern "C"
