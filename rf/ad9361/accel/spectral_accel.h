/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 */
/* SPDX-FileCopyrightText: 2026 D. Kevin Cameron */
/* Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md). */
/* spectral_accel.h -- the spectral accelerator: an nvc --std=2040 spectral design's RF signal path
 * (AD9361 chips, antennas, the arena) with its data and its processing moved out of the simulator.
 *
 * The data is the simulator's: one event is one spectrum per net, K complex lines.  The processing is
 * SIMT: one thread per frequency line (per sample, inside a chip's non-linear parts), one block of K
 * threads per element, on a GPU -- or the same code as plain loops on the CPU (SPECTRAL_ACCEL_DEVICE=cpu).
 *
 * Every function takes and returns doubles (and arrays of doubles with their length): that is what
 * nvc's VHPIDIRECT passes the same way in every VHDL standard, so the same library is called from
 * VHDL (spectral_accel_pkg.vhd) and from C or Python (ctypes).
 *
 * Life of a design:
 *   netlist     sa_chip_new / sa_antenna_new / sa_scatterer_new, sa_wire, sa_arena_antenna, sa_commit
 *   parameters  sa_chip_params (the chip's constants in its control state), positions
 *   move out    sa_set_mode(1), sa_push_tx / sa_push_rx: the simulator's state and net data
 *   events      sa_tx (a frame at a chip's data port), then sa_rx (what each receiver delivers;
 *               the first sa_rx after new frames processes the event on the accelerator)
 *   pull back   sa_set_mode(0), sa_pull_tx / sa_pull_rx: state and net data, for the simulator to go on
 */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* layout of the vector sa_chip_params takes (ad9361_pkg.ad9361_accel_params writes it in VHDL) */
enum {
    SA_P_VERSION, SA_P_LINES, SA_P_FS, SA_P_TX_ON, SA_P_RX_ON, SA_P_TX_FREQ, SA_P_RX_FREQ,
    SA_P_TX_AMP, SA_P_TX_IP3, SA_P_TX_RES, SA_P_TX_PN_A, SA_P_TX_PN_W, SA_P_TX_LEAK, SA_P_TX_NOISE,
    SA_P_TX_FC3, SA_P_TX_FC1,
    SA_P_RX_RES, SA_P_RX_PN_A, SA_P_RX_PN_W, SA_P_RX_NOISE, SA_P_RX_IQ_G, SA_P_RX_IQ_C, SA_P_RX_IQ_S,
    SA_P_RX_IIP3_MAX, SA_P_RX_GMAX, SA_P_RX_GMIN, SA_P_RX_GSTEP, SA_P_RX_IIP3_CEIL, SA_P_RX_FS0,
    SA_P_RX_FC3, SA_P_RX_FC1, SA_P_RX_LEAK,
    SA_P_AGC_MODE, SA_P_AGC_MANUAL, SA_P_FAST_DETECT, SA_P_FAST_TARGET, SA_P_FAST_CLIP_STEP,
    SA_P_FAST_STRONGER, SA_P_FAST_LOST, SA_P_FAST_BLOCK, SA_P_FAST_SETTLE, SA_P_FAST_LOST_BLOCKS,
    SA_P_SLOW_PERIOD, SA_P_SLOW_INNER_HIGH, SA_P_SLOW_INNER_LOW, SA_P_SLOW_OUTER_HIGH, SA_P_SLOW_OUTER_LOW,
    SA_P_SLOW_STEP_INNER, SA_P_SLOW_STEP_OUTER,
    SA_P_COUNT
};
#define SA_PARAMS_VERSION 1.0

/* ---- netlist (before sa_commit) ---- */
double sa_chip_new(double seed);                              /* -> chip id */
double sa_antenna_new(double gain_dbi, double pol_angle);     /* -> antenna id */
double sa_scatterer_new(double rcs_m2);                       /* -> scatterer id (a reflector in the arena) */
void   sa_wire(double chip, double pin, double antenna);      /* pin 0: TX1, 1: RX1 */
void   sa_arena_antenna(double antenna);
void   sa_antenna_platform(double antenna, double platform);  /* antennas on one platform (not 0) do not hear each other */
double sa_commit(void);                                       /* 1: the design is admitted; 0: declined (reason on stderr) */
void   sa_reset(void);                                        /* forget everything (a new design in the same process) */

/* ---- parameters (any time) ---- */
void   sa_chip_params(double chip, const double *p, int64_t n);
void   sa_antenna_position(double antenna, double x, double y, double z);
void   sa_scatterer_position(double scatterer, double x, double y, double z);
void   sa_agc_init(double chip, double gain_db);              /* the receiver's AGC starts over at this gain */

/* ---- where the data and the processing are ---- */
double sa_schedule_count(void);                               /* SPECTRAL_ACCEL_SCHEDULE: entries */
double sa_schedule_time(double i);                            /* seconds */
double sa_schedule_mode(double i);                            /* 1: out on the accelerator, 0: back in the simulator */
void   sa_set_mode(double mode);
/* state[0] theta (LO phase noise, rad), [1] carrier leakage phase, [2] 1: something is on the pin;
 * lines: the spectrum on the TX pin, K complex lines (re, im) */
void   sa_push_tx(double chip, const double *state, int64_t ns, const double *lines, int64_t n);
void   sa_pull_tx(double chip, double *state, int64_t ns, double *lines, int64_t n);
/* state[0] theta, [1] gain dB, [2] fast-AGC state (0 search, 1 settle, 2 locked), [3] settle count,
 * [4] lost count, [5] slow-AGC power sum, [6] slow-AGC sample count */
void   sa_push_rx(double chip, const double *state, int64_t ns);
void   sa_pull_rx(double chip, double *state, int64_t ns);

/* ---- events (while out) ---- */
void   sa_tx(double chip, double seq, const double *lines, int64_t n);   /* a frame at the data port: K (re, im) */
void   sa_touch(void);                                        /* something else changed what is radiated */
/* What the chip's receiver delivers for the event at `now` seconds: buf[0 .. 2K-1] the frame's lines,
 * buf[2K] the gain in use.  Returns the frame's sequence number, 0.0 when there is none (receiver off,
 * or this chip already took this event's frame). */
double sa_rx(double chip, double now, double *buf, int64_t n);
void   sa_rx_buf(double chip, double now, double *buf, int64_t n);     /* the same; the number goes to buf[2K+1] */

/* ---- for C and Python callers ---- */
void   sa_step(double now);                                   /* process the event now (sa_rx does it on demand) */
double sa_lines(void);                                        /* K */
double sa_events(void);                                       /* events processed on the accelerator */
double sa_device_seconds(void);                               /* time spent in them, s (frames in to frames out) */
double sa_on_gpu(void);
/* read a whole array at once: what 0: frames at the receivers' data ports [n_rx][2K+2] floats (lines, gain, pad),
 * 1: spectra radiated by the TX antennas [n_tx][2K] floats */
int64_t sa_read(double what, float *buf, int64_t n);
/* write every transmitter's frame at once: [n_tx][2K] floats (the same as n_tx calls of sa_tx) */
void   sa_tx_all(const float *frames, int64_t n);

#ifdef __cplusplus
}
#endif
