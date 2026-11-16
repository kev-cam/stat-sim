// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
// spectral_stages.inc -- what happens to one element's spectrum in one event.  Included twice by
// spectral_accel.cu: once as device code, where a block of K threads is one element and thread k is
// frequency line k (or sample k), and once as host code, where the same sections are loops.
//
//   PAR(k) ... END_PAR   the body runs once for every k in 0 .. K-1.  Device: thread k runs it, then all
//                        threads of the block meet at a barrier.  Host: a loop.
//   SEQ ... END_SEQ      the body runs once (device: thread 0, then a barrier).
//
// Rule that makes the two the same program: whatever a later section needs from an earlier one is in the
// block's arrays (B.*) or in the engine's tables -- never in a local, unless the local has the same value
// in every thread (loop counters, constants read from the tables).  A body only writes entry k of an
// array, or entries no other k writes.
//
// The maths is ad9361_spectral_pkg.vhd / ad9361_pkg.vhd / rf_spectrum_pkg.vhd, line for line where it
// can be; the random numbers are the accelerator's own (counter-based, one key per element and event).

// In-place transform of (B.a_re, B.a_im).  sign +1: lines -> samples, x[n] = sum_k X_k exp(+j 2 pi k n / K);
// sign -1: samples -> K times the lines.
STAGE void NAME(fft)(const Tab &T, Blk &B, const float sign)
{
    const int K = T.K;
    PAR(k)
        const int j = bitrev(k, T.logK);
        if (j > k) {                                   // each pair is swapped by its lower index only
            float t = B.a_re[k]; B.a_re[k] = B.a_re[j]; B.a_re[j] = t;
            t = B.a_im[k]; B.a_im[k] = B.a_im[j]; B.a_im[j] = t;
        }
    END_PAR
    float *sr = B.a_re, *si = B.a_im, *dr = B.b_re, *di = B.b_im;
    for (int len = 2; len <= K; len <<= 1) {
        const int half = len >> 1, step = K / len;
        PAR(k)
            const int pos = k & (len - 1);
            const int lo = pos < half ? k : k - half, hi = lo + half;
            const int tw = (pos & (half - 1)) * step;
            const float wr = T.tw[2 * tw], wi = sign * T.tw[2 * tw + 1];
            const float xr = sr[hi] * wr - si[hi] * wi, xi = sr[hi] * wi + si[hi] * wr;
            if (pos < half) { dr[k] = sr[lo] + xr; di[k] = si[lo] + xi; }
            else            { dr[k] = sr[lo] - xr; di[k] = si[lo] - xi; }
        END_PAR
        float *t = sr; sr = dr; dr = t;
        t = si; si = di; di = t;
    }
    if (sr != B.a_re) {
        PAR(k)
            B.a_re[k] = B.b_re[k];
            B.a_im[k] = B.b_im[k];
        END_PAR
    }
}

// LO phase noise through the event: B.w0[n] = theta[n], the first-order process
// theta[n] = a theta[n-1] + w N(0,1) continued from theta_prev (ad9361_pkg.phase_step).  The recurrence
// is unrolled as a prefix sum in log2(K) doubling steps, so every sample is its own thread.
STAGE void NAME(phase_noise)(const Tab &T, Blk &B, const float a, const float w, const float theta_prev,
                             const uint64_t key)
{
    const int K = T.K;
    PAR(n)
        float g1, g2;
        gauss2(key, 3u * (uint32_t)n, &g1, &g2);
        B.w0[n] = w * g1;
    END_PAR
    float *s = B.w0, *d = B.w1;
    float as = a;                                      // a ** stride
    for (int stride = 1; stride < K; stride <<= 1) {
        PAR(n)
            d[n] = s[n] + (n >= stride ? as * s[n - stride] : 0.0f);
        END_PAR
        float *t = s; s = d; d = t;
        as *= as;
    }
    PAR(n)
        B.w0[n] = s[n] + powf(a, (float)(n + 1)) * theta_prev;
    END_PAR
}

// One event through a transmitter (ad9361_tx_symbol) and its antenna: the frame at the data port ->
// the spectrum on the TX pin (T.pin) and what the antenna radiates (T.air).
STAGE void NAME(tx_stage)(const Tab &T, Blk &B, const int e)
{
    const int K = T.K;
    const TxP &p = T.txp[e];
    TxS &st = T.txs[e];
    if (!T.fresh[e])
        return;                                        // no new frame: what is on the net stays there
    float *pin = T.pin + (size_t)e * 2 * K, *air = T.air + (size_t)e * 2 * K;
    if (!p.on) {                                       // not in a transmit state: the pin goes silent
        PAR(k)
            pin[2 * k] = pin[2 * k + 1] = air[2 * k] = air[2 * k + 1] = 0.0f;
        END_PAR
        SEQ
            st.on = 0;
        END_SEQ
        return;
    }
    const float *frame = T.frame + (size_t)e * 2 * K;
    PAR(k)                                             // the analog baseband filter, on the lines
        const int koff = k < K / 2 ? k : k - K;
        float hr, hi;
        bb_response(p.fc3, p.fc1, koff * T.df, &hr, &hi);
        B.a_re[k] = frame[2 * k] * hr - frame[2 * k + 1] * hi;
        B.a_im[k] = frame[2 * k] * hi + frame[2 * k + 1] * hr;
    END_PAR
    NAME(fft)(T, B, +1.0f);                            // the samples of the event
    const uint64_t key = rng_key(T.seed, p.seed, 0, T.event);
    NAME(phase_noise)(T, B, p.pn_a, p.pn_w, st.theta, key);
    const float lr = p.leak_amp * cosf(st.leak_phase), li = p.leak_amp * sinf(st.leak_phase);
    PAR(n)                                             // ad9361_tx_sample
        float g1, g2, sn, cs;
        const float qi = dac_word(B.a_re[n]), qq = dac_word(B.a_im[n]);
        gauss2(key, 3u * (uint32_t)n + 1u, &g1, &g2);  // (1 + e): the EVM residual
        const float er = 1.0f + p.res_sigma * g1, ei = p.res_sigma * g2;
        const float ti = qi * er - qq * ei, tq = qi * ei + qq * er;
        sincosf(B.w0[n], &sn, &cs);
        const float xi = (ti * cs - tq * sn) * p.amp, xq = (ti * sn + tq * cs) * p.amp;
        const float c = 1.0f / sqrtf(1.0f + 2.0f * (xi * xi + xq * xq) / p.ip3);   // the output stage compresses
        gauss2(key, 3u * (uint32_t)n + 2u, &g1, &g2);
        B.a_re[n] = xi * c + lr + p.noise_sigma * g1;
        B.a_im[n] = xq * c + li + p.noise_sigma * g2;
    END_PAR
    SEQ
        st.theta = B.w0[K - 1];
        st.on = 1;
    END_SEQ
    NAME(fft)(T, B, -1.0f);
    PAR(k)
        const float xr = B.a_re[k] * T.inv_k, xi = B.a_im[k] * T.inv_k;
        pin[2 * k] = xr;
        pin[2 * k + 1] = xi;
        air[2 * k] = xr * p.g_ant;
        air[2 * k + 1] = xi * p.g_ant;
    END_PAR
}

// What reaches one scatterer in the arena from every transmitting antenna, per group of transmitters
// that share a carrier (T.scat): free space, line by line.
STAGE void NAME(scat_stage)(const Tab &T, Blk &B, const int s)
{
    const int K = T.K;
    (void)B;
    for (int g = 0; g < T.G; g++) {
        const int *list = T.grp_list + T.grp_start[g];
        const int nf = T.grp_nfull[g];
        const float dff = T.df / (float)T.grp_f[g];
        float *o = T.scat + ((size_t)s * T.G + g) * 2 * K;
        PAR(k)
            const int koff = k < K / 2 ? k : k - K;
            float sr = 0.0f, si = 0.0f;
            for (int i = 0; i < nf; i++) {
                const int t = list[i];
                if (!T.txs[t].on)
                    continue;
                const PairT q = T.sp_t[(size_t)s * T.n_tx + t];
                float ph = q.phi0 + koff * q.dphi, sn, cs;
                ph -= floorf(ph);
                sa_sincospi(2.0f * ph, &sn, &cs);
                const float xr = T.air[((size_t)t * K + k) * 2], xi = T.air[((size_t)t * K + k) * 2 + 1];
                sr += q.amp * (xr * cs - xi * sn);
                si += q.amp * (xr * sn + xi * cs);
            }
            const float fi = 1.0f / (1.0f + koff * dff);        // free space loss follows the line's own frequency
            o[2 * k] = sr * fi;
            o[2 * k + 1] = si * fi;
        END_PAR
    }
}

// One event at a receiver: the arena (every antenna and scatterer it hears, rf_spectrum_pkg.arena_resolve),
// its antenna, and the chip's receive path (ad9361_rx_symbol) -> the frame at the data port (T.out).
STAGE void NAME(rx_stage)(const Tab &T, Blk &B, const int r)
{
    const int K = T.K;
    const RxP &p = T.rxp[r];
    RxS &st = T.rxs[r];
    float *out = T.out + (size_t)r * (2 * K + 2);
    if (!p.on)
        return;                                        // not in a receive state: no frame
    PAR(k)
        B.t_re[k] = B.t_im[k] = B.l_re[k] = B.l_im[k] = 0.0f;
    END_PAR
    int lines_used = 0;
    const PairT *pr = T.pair + (size_t)r * T.R;
    for (int g = 0; g < T.G; g++) {
        const int *list = T.grp_list + T.grp_start[g];
        const int nf = T.grp_nfull[g], nl = T.grp_nleak[g];
        const double dfreq = T.grp_f[g] - p.lo;        // the group's carrier against this receiver's LO
        const float eps = (float)(dfreq / T.df);
        if (fabsf(eps) >= 0.5f * K)
            continue;                                  // another channel: outside this receiver's grid
        SEQ
            int n = 0;
            for (int i = 0; i < nf; i++)
                n += T.txs[list[i]].on;
            for (int i = 0; i < nl; i++)
                n += (list[nf + i] != r && T.rxp[list[nf + i]].on);
            B.scal[0] = (float)n;
        END_SEQ
        if (B.scal[0] == 0.0f)
            continue;                                  // nothing of this group is on the air
        const int direct = T.heard[(size_t)r * T.G + g];        // some antenna of the group reaches this one directly
        if (!direct && T.S == 0)
            continue;
        const float dff = T.df / (float)T.grp_f[g];
        PAR(k)                                         // the arena: each line on its own
            const int koff = k < K / 2 ? k : k - K;
            float sr = 0.0f, si = 0.0f, sn, cs;
            for (int i = 0; direct && i < nf; i++) {   // transmitting antennas
                const int t = list[i];
                if (!T.txs[t].on)
                    continue;
                const PairT q = pr[t];
                if (q.amp == 0.0f)
                    continue;
                float ph = q.phi0 + koff * q.dphi;
                ph -= floorf(ph);
                sa_sincospi(2.0f * ph, &sn, &cs);
                const float xr = T.air[((size_t)t * K + k) * 2], xi = T.air[((size_t)t * K + k) * 2 + 1];
                sr += q.amp * (xr * cs - xi * sn);
                si += q.amp * (xr * sn + xi * cs);
            }
            if (k == 0 && direct)                      // other receivers' LO leakage: one line at their carrier
                for (int i = 0; i < nl; i++) {
                    const int j = list[nf + i];
                    if (j == r || !T.rxp[j].on)
                        continue;
                    const PairT q = pr[T.n_tx + j];
                    sa_sincospi(2.0f * q.phi0, &sn, &cs);
                    const float a = q.amp * T.rxp[j].leak_amp * T.rxp[j].g_ant;
                    sr += a * cs;
                    si += a * sn;
                }
            const float fi = 1.0f / (1.0f + koff * dff);
            sr *= fi;
            si *= fi;
            for (int s = 0; s < T.S; s++) {            // echoes off the scatterers
                const float *q = T.sp_r + ((size_t)r * T.S + s) * 2;
                float ph = T.sp_rphi[((size_t)r * T.S + s) * T.G + g] + koff * q[1];
                ph -= floorf(ph);
                sa_sincospi(2.0f * ph, &sn, &cs);
                const float *x = T.scat + (((size_t)s * T.G + g) * K + k) * 2;
                sr += q[0] * (x[0] * cs - x[1] * sn);
                si += q[0] * (x[0] * sn + x[1] * cs);
            }
            // the receiver's baseband filter, on the sender's grid at the frequencies the receiver sees
            float hr, hi;
            bb_response(p.fc3, p.fc1, koff * T.df + (float)dfreq, &hr, &hi);
            B.a_re[k] = sr * hr - si * hi;
            B.a_im[k] = sr * hi + si * hr;
        END_PAR
        if (dfreq == 0.0) {                            // on this receiver's own grid: stays lines
            PAR(k)
                B.l_re[k] += B.a_re[k];
                B.l_im[k] += B.a_im[k];
            END_PAR
            lines_used = 1;
        }
        else {                                         // a carrier offset: a ramp through the event's samples
            NAME(fft)(T, B, +1.0f);
            const double cyc = dfreq * T.t0;           // and the offset's phase at the start of the event
            const float ph0 = (float)(cyc - floor(cyc));
            PAR(n)
                float ph = ph0 + eps * (float)n * T.inv_k, sn, cs;
                ph -= floorf(ph);
                sa_sincospi(2.0f * ph, &sn, &cs);
                B.t_re[n] += B.a_re[n] * cs - B.a_im[n] * sn;
                B.t_im[n] += B.a_re[n] * sn + B.a_im[n] * cs;
            END_PAR
        }
    }
    if (lines_used) {
        PAR(k)
            B.a_re[k] = B.l_re[k];
            B.a_im[k] = B.l_im[k];
        END_PAR
        NAME(fft)(T, B, +1.0f);
        PAR(n)
            B.t_re[n] += B.a_re[n];
            B.t_im[n] += B.a_im[n];
        END_PAR
    }
    const uint64_t key = rng_key(T.seed, p.seed, 1, T.event);
    NAME(phase_noise)(T, B, p.pn_a, p.pn_w, st.theta, key);
    PAR(n)                                             // ad9361_rx_sample, up to the gain
        float g1, g2, sn, cs;
        sincosf(B.w0[n], &sn, &cs);
        const float ai = B.t_re[n] * cs - B.t_im[n] * sn, aq = B.t_re[n] * sn + B.t_im[n] * cs;
        gauss2(key, 3u * (uint32_t)n + 1u, &g1, &g2);
        const float er = 1.0f + p.res_sigma * g1, ei = p.res_sigma * g2;
        float ti = ai * er - aq * ei, tq = ai * ei + aq * er;
        gauss2(key, 3u * (uint32_t)n + 2u, &g1, &g2);
        ti += p.noise_sigma * g1;
        tq += p.noise_sigma * g2;
        B.t_re[n] = ti;                                // quadrature errors: gain and phase on Q
        B.t_im[n] = p.iq_g * (tq * p.iq_c + ti * p.iq_s);
    END_PAR
    SEQ
        st.theta = B.w0[K - 1];
        if (p.mode == 0)
            st.gain_db = legal_gain(p, p.manual_db);
        set_gain(p, st.gain_db, B.scal);
    END_SEQ
    // Compression, gain and the ADC, one AGC sub-block at a time: the samples of a sub-block in parallel
    // with the gain in force, then the AGC's decision from their ADC words, which sets the next gain.
    for (int sb = 0; sb < K / p.sb; sb++) {
        PAR(n)
            if (n / p.sb == sb)
                adc_sample(B.t_re[n], B.t_im[n], B.scal, &B.a_re[n], &B.a_im[n]);
        END_PAR
        SEQ
            float acc = 0.0f;
            bool clip = false;
            for (int n = sb * p.sb; n < (sb + 1) * p.sb; n++) {
                const float ci = B.a_re[n], cq = B.a_im[n];
                acc += ci * ci + cq * cq;
                clip = clip || fabsf(ci) >= 2047.0f || fabsf(cq) >= 2047.0f;
                if (p.mode == 1) {                     // slow attack: a decision once per period, at any sample
                    st.acc += ci * ci + cq * cq;
                    if (++st.acc_n >= p.slow_period) {
                        const float g = agc_slow(p, st.gain_db,
                                                 10.0f * log10f(fmaxf(st.acc / p.slow_period / 4194304.0f, 1e-12f)));
                        st.acc = 0.0f;
                        st.acc_n = 0;
                        if (g != st.gain_db) {         // the rest of this sub-block again, at the new gain
                            st.gain_db = g;
                            set_gain(p, g, B.scal);
                            for (int m = n + 1; m < (sb + 1) * p.sb; m++)
                                adc_sample(B.t_re[m], B.t_im[m], B.scal, &B.a_re[m], &B.a_im[m]);
                        }
                    }
                }
            }
            if (p.mode == 2) {
                const float before = st.gain_db;
                agc_fast(p, st, 10.0f * log10f(fmaxf(acc / p.sb / 4194304.0f, 1e-12f)), clip);
                if (st.gain_db != before)
                    set_gain(p, st.gain_db, B.scal);
            }
        END_SEQ
    }
    NAME(fft)(T, B, -1.0f);
    PAR(k)
        out[2 * k] = B.a_re[k] * T.inv_k;
        out[2 * k + 1] = B.a_im[k] * T.inv_k;
    END_PAR
    SEQ
        out[2 * K] = st.gain_db;
    END_SEQ
}
