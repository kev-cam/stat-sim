#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
ad9361.py -- behavioural model of the Analog Devices AD9361 RF transceiver, driven from software.

The chip is modelled at its data port: complex baseband samples in, RF complex envelope out
(transmit), and RF complex envelope in, complex baseband samples out (receive), one sample per
data-port sample.  There is no SPI register map and no LVDS/CMOS port timing: the controls are
the ones software sets through the Linux IIO driver (the names follow pyadi-iio's ad9361 class:
rx_lo, tx_lo, sample_rate, rx_rf_bandwidth, tx_rf_bandwidth, gain_control_mode_chan0,
rx_hardwaregain_chan0, tx_hardwaregain_chan0, tx(), rx()).

Signal convention (the one of nvc's rf.rf_signal_pkg): an RF signal is its complex envelope x
around a centre frequency, in sqrt(W), so |x|^2 is the power of the RF signal in watts.

    radio.transmit(codes)        -> envelope at the TX port, centred on radio.tx_lo_actual
    radio.receive(env, f_centre) -> codes at the RX data port (I, Q in -2048 .. 2047)

Numbers: SPEC holds the data sheet's typical values per band with where each was read; MODEL
holds what the data sheet does not give and this model assumes.  `ad9361.py check` measures
the model the way the data sheet measures the chip and prints both; `ad9361.py spec` prints
the tables.

This file is the reference.  The model that runs in nvc is VHDL: ad9361_vhdl.py writes
ad9361_pkg.vhd from the same tables and checks it against this file, and ad9361.vhd /
ad9361_spectral_pkg.vhd wrap it for --std=2040 spectral event-driven simulation
(an2597_nvc.py runs the AN-2597 link that way and compares it with an2597_link.py here).
"""
import argparse
import math
import sys

import numpy as np
from scipy import signal

K_BOLTZ = 1.380649e-23
T0 = 290.0
C0 = 299792458.0

# ---------------------------------------------------------------------------------------------
# Data sheet values (AD9361 data sheet, Table 1, typical).
#
# status "ds":  read on 2026-11-16 from published text of the table (Rev. F and Rev. G copies
#               returned by a web search; the PDF itself could not be opened from the machine
#               this was written on, so nothing here was read off the PDF page).
# status "rec": written from recollection of the data sheet or of the reference manual UG-570
#               and NOT checked; treat as a placeholder until someone reads the document.
# status "ez":  an Analog Devices staff reply on EngineerZone, not a data sheet value.
# ---------------------------------------------------------------------------------------------
BANDS = (800e6, 2.4e9, 5.5e9)

SPEC = {
    # name: ((800 MHz, 2.4 GHz, 5.5 GHz), unit, status, what it is)
    "rx_gain_max": ((74.5, 73.0, 65.5), "dB", "ds",
                    "maximum RX gain (given at 800 MHz; 2300 MHz RX1A/RX2A; 5500 MHz RX1A/RX2A)"),
    "rx_nf": ((2.0, 3.0, 3.8), "dB", "ds", "noise figure at maximum RX gain"),
    "rx_iip3": ((-18.0, -14.0, -17.0), "dBm", "ds", "third-order input intercept at maximum RX gain"),
    "rx_evm": ((-42.0, -42.0, -37.0), "dB", "ds",
               "RX modulation accuracy (19.2 MHz reference at 800 MHz, 40 MHz at 2.4 and 5.5 GHz)"),
    "rx_lo_leak": ((-122.0, -110.0, -95.0), "dBm", "ds", "LO leakage at the RX front-end input"),
    "tx_pmax": ((8.0, 7.5, 6.5), "dBm", "ds",
                "maximum output power, 1 MHz tone (7 MHz at 5.5 GHz) into 50 ohm"),
    "tx_oip3": ((23.0, 19.0, 17.0), "dBm", "ds", "third-order output intercept, 0 dB attenuation"),
    "tx_evm": ((-40.0, -40.0, -36.0), "dB", "ds",
               "TX modulation accuracy; -40 dB at 800 MHz and 2.4 GHz were read, -36 dB at 5.5 GHz is 'rec'"),
    "tx_noise": ((-157.0, -156.0, -151.5), "dBm/Hz", "ds", "TX noise floor at 90 MHz offset"),
    "tx_leak_0db": ((-50.0, -50.0, -50.0), "dBc", "ds", "carrier leakage at 0 dB attenuation"),
    "tx_leak_40db": ((-32.0, -32.0, -30.0), "dBc", "ds",
                     "carrier leakage at 40 dB attenuation; -32 dBc was read, -30 dBc at 5.5 GHz is 'rec'"),
    "lo_pn_rms": ((0.13, 0.37, 0.59), "deg", "rec",
                  "integrated LO phase noise; the data sheet has it as plots only, these three numbers are 'rec'"),
}

SCALARS = {
    # name: (value, unit, status, what it is)
    "rx_lo_min": (70e6, "Hz", "ds", "RX band"),
    "rx_lo_max": (6.0e9, "Hz", "ds", "RX band"),
    "tx_lo_min": (47e6, "Hz", "ds", "TX band"),
    "tx_lo_max": (6.0e9, "Hz", "ds", "TX band"),
    "rx_gain_min": (0.0, "dB", "ds", "minimum RX gain"),
    "rx_gain_step": (1.0, "dB", "ds", "RX gain step"),
    "tx_atten_max": (89.75, "dB", "ds", "TX power control range (90 dB) in 0.25 dB steps"),
    "tx_atten_step": (0.25, "dB", "ds", "TX power control resolution"),
    "rx_quad_gain_err": (0.2, "%", "ds", "RX quadrature gain error"),
    "rx_quad_phase_err": (0.2, "deg", "ds", "RX quadrature phase error"),
    "rssi_range": (100.0, "dB", "ds", "RSSI range"),
    "rssi_accuracy": (2.0, "dB", "ds", "RSSI accuracy (+/-)"),
    "lo_step": (2.4, "Hz", "ds", "maximum LO step size"),
    "bw_min": (200e3, "Hz", "ds", "tunable channel bandwidth, lower end (given as '<200 kHz')"),
    "bw_max": (56e6, "Hz", "ds", "tunable channel bandwidth, upper end"),
    "adc_bits": (12, "bit", "ds", "ADC and DAC word length at the data port"),
    "rate_max": (61.44e6, "Hz", "rec", "maximum data-port sample rate"),
    "rate_min": (25e6 / 48, "Hz", "rec", "minimum data-port sample rate (25 MSPS ADC, decimation 12 x 4)"),
    "rx_isolation": (65.0, "dB", "ds", "RX1 to RX2 isolation (RX1A to RX2A; read from a Rev. F copy)"),
    "tx_isolation": (50.0, "dB", "ds", "TX1 to TX2 isolation"),
    "adc_fs_at_0db": (5.9, "dBm", "ez",
                      "CW power at the 50 ohm input that reaches ADC full scale at 0 dB gain: 0.625 V peak"),
}

# ---------------------------------------------------------------------------------------------
# What the data sheet does not give: this model's own assumptions.  Every one can be overridden
# per instance (AD9361(name, **overrides)).
# ---------------------------------------------------------------------------------------------
MODEL = {
    # Analog baseband filters, as multiples of the baseband bandwidth BBBW = rf_bandwidth / 2
    # (the corner settings the reference manual describes; 'rec').  Order 3 Butterworth plus a
    # single real pole on each side.
    "rx_bblpf_corner": 1.4, "rx_tia_corner": 2.5, "tx_bblpf_corner": 1.6, "tx_secondary_corner": 5.0,
    "fir_taps": 33,                 # length of the FIR that carries those responses at the data rate
    # RX intercept against gain: the limiting stage is taken to be after the gain, so the input
    # intercept rises 1 dB per dB of gain reduction, up to this ceiling (dBm).  The data sheet has
    # the intercept against gain index only as plots; the rule and the ceiling are 'rec' of them.
    "rx_iip3_ceiling": 20.0,
    # RX noise against gain: front-end noise stays at the data sheet figure, the 12-bit output
    # word adds its quantisation noise; nothing else changes with gain.
    # TX: the attenuator is taken to be before the stage that sets OIP3, so IM3 in dBc falls
    # 2 dB per dB of attenuation; the noise floor follows the attenuator down to kT.
    "tx_atten_before_output_stage": True,
    # LO phase noise as a first-order process with this corner (Hz) and the rms of SPEC.
    "pn_corner": 100e3,
    # Slow attack AGC: mean power over one period against two pairs of thresholds (dBFS).
    "agc_period": 1e-3, "agc_inner_high": -10.0, "agc_inner_low": -12.0,
    "agc_outer_high": -5.0, "agc_outer_low": -18.0, "agc_step_inner": 1.0, "agc_step_outer": 4.0,
    # Fast attack AGC: power in sub-blocks of `fast_block` samples; at maximum gain a sub-block
    # above `fast_detect` (dBFS; thermal noise in 20 MHz sits near -31 dBFS there, and anything
    # weaker than this needs no gain change) starts a burst and the gain is set for `fast_target`.
    # Locked, a sub-block that clips or is `fast_stronger` dB over the target settles again, and
    # `fast_lost_blocks` sub-blocks `fast_lost` dB under the target end the burst.  The chip's fast
    # AGC has these three elements (acquire, stronger signal, energy lost); the numbers are mine.
    "fast_block": 16, "fast_detect": -18.0, "fast_target": -12.0, "fast_clip_step": 12.0,
    "fast_settle_iterations": 4, "fast_stronger": 9.0, "fast_lost": 15.0, "fast_lost_blocks": 8,
}


def band(name, f):
    """SPEC value at LO frequency f: linear in log10(f) between the three bands, held outside them."""
    v = SPEC[name][0]
    x = math.log10(min(max(f, BANDS[0]), BANDS[-1]))
    xs = [math.log10(b) for b in BANDS]
    if x <= xs[1]:
        return v[0] + (v[1] - v[0]) * (x - xs[0]) / (xs[1] - xs[0])
    return v[1] + (v[2] - v[1]) * (x - xs[1]) / (xs[2] - xs[1])


def scalar(name):
    return SCALARS[name][0]


def dbm_to_w(dbm):
    return 1e-3 * 10.0 ** (dbm / 10.0)


def w_to_dbm(w):
    return 10.0 * math.log10(max(w, 1e-300) / 1e-3)


def soft_compress(x, ip3_w):
    """Memoryless third-order compression of an envelope: y = x / sqrt(1 + 2 |x|^2 / IP3).
    To first order y = x (1 - |x|^2 / IP3): two tones of power P each give IM3 = P^3 / IP3^2.
    Saturates at IP3 / 2 instead of folding over as the bare cubic does."""
    return x / np.sqrt(1.0 + 2.0 * (x.real ** 2 + x.imag ** 2) / ip3_w)


class _PhaseNoise:
    """First-order Gaussian phase process with a given rms (rad) and corner frequency."""

    def __init__(self, rng):
        self.rng = rng
        self.theta = 0.0

    def run(self, n, rms, corner, fs):
        if rms <= 0.0 or n == 0:
            return np.zeros(n)
        a = math.exp(-2.0 * math.pi * corner / fs)
        w = self.rng.standard_normal(n) * (rms * math.sqrt(1.0 - a * a))
        th, zf = signal.lfilter([1.0], [1.0, -a], w, zi=[a * self.theta])
        self.theta = float(th[-1])
        return th


class AD9361:
    """One AD9361, `channels` (1 or 2) transmitters and receivers on one pair of LOs."""

    def __init__(self, name="ad9361", seed=0, channels=1, **overrides):
        if channels not in (1, 2):
            raise ValueError("the AD9361 has two transmitters and two receivers")
        unknown = set(overrides) - set(MODEL)
        if unknown:
            raise ValueError("unknown model parameter(s): %s" % ", ".join(sorted(unknown)))
        self.name = name
        self.nch = channels
        self.m = dict(MODEL)
        self.m.update(overrides)
        self.rng = np.random.default_rng(seed)
        # what the model includes; switch entries off for a noise-free reference
        self.enable = {"noise": True, "phase_noise": True, "evm_residual": True, "filters": True,
                       "leak": True, "iq_imbalance": True, "quantise": True, "crosstalk": True}
        self._rx_lo = 2.4e9
        self._tx_lo = 2.4e9
        self._fs = 30.72e6
        self._rx_bw = 18e6
        self._tx_bw = 18e6
        self.xo_ppm = 0.0                    # reference clock error; moves both LOs (not the sample clock)
        self.ensm_mode = "fdd"               # "fdd", "rx", "tx", "alert", "sleep"
        self._gain_mode = ["slow_attack"] * channels
        self._rx_gain_set = [self.rx_gain_max] * channels      # manual setting, dB
        self._rx_gain = [self.rx_gain_max] * channels          # gain in use, dB
        self._tx_gain = [-10.0] * channels                     # dB, 0 = full power
        self._tx_leak_phase = self.rng.uniform(0.0, 2.0 * math.pi, channels)
        self._pn_rx = _PhaseNoise(self.rng)                    # one RX LO and one TX LO, shared by the channels
        self._pn_tx = _PhaseNoise(self.rng)
        self._n_rx = 0
        self._n_tx = 0
        self._fir = {}
        self._zi = {}
        self._agc = [dict(acc=0.0, n=0, state="search", lost=0, level=None, settle=0) for _ in range(channels)]
        self.rx_gain_log = [[] for _ in range(channels)]       # (sample index, gain) at every change
        # software side
        self.rx_buffer_size = 1024
        self.tx_cyclic_buffer = False
        self.arena = None
        self._tx_queue = []
        self._tx_cyclic = None
        self._rx_fifo = [np.zeros(0, complex) for _ in range(channels)]

    # ---- controls (pyadi-iio names) ---------------------------------------------------------
    @property
    def rx_lo(self):
        return self._rx_lo

    @rx_lo.setter
    def rx_lo(self, f):
        if not scalar("rx_lo_min") <= f <= scalar("rx_lo_max"):
            raise ValueError("rx_lo %g Hz is outside 70 MHz .. 6 GHz" % f)
        self._rx_lo = float(f)
        for ch in range(self.nch):
            self._rx_gain_set[ch] = min(self._rx_gain_set[ch], self.rx_gain_max)
            self._rx_gain[ch] = min(self._rx_gain[ch], self.rx_gain_max)

    @property
    def tx_lo(self):
        return self._tx_lo

    @tx_lo.setter
    def tx_lo(self, f):
        if not scalar("tx_lo_min") <= f <= scalar("tx_lo_max"):
            raise ValueError("tx_lo %g Hz is outside 47 MHz .. 6 GHz" % f)
        self._tx_lo = float(f)

    def _lo_actual(self, f):
        step = scalar("lo_step")
        return round(f * (1.0 + self.xo_ppm * 1e-6) / step) * step

    @property
    def rx_lo_actual(self):
        """The RX LO with the reference error applied, on the 2.4 Hz grid."""
        return self._lo_actual(self._rx_lo)

    @property
    def tx_lo_actual(self):
        return self._lo_actual(self._tx_lo)

    @property
    def sample_rate(self):
        return self._fs

    @sample_rate.setter
    def sample_rate(self, fs):
        if not scalar("rate_min") <= fs <= scalar("rate_max"):
            raise ValueError("sample_rate %g Hz is outside %.0f .. %.0f" % (fs, scalar("rate_min"), scalar("rate_max")))
        self._fs = float(fs)
        self._fir.clear()
        self._zi.clear()

    def _set_bw(self, attr, bw):
        if not scalar("bw_min") <= bw <= scalar("bw_max"):
            raise ValueError("rf bandwidth %g Hz is outside 200 kHz .. 56 MHz" % bw)
        setattr(self, attr, float(bw))
        self._fir.clear()
        self._zi.clear()

    rx_rf_bandwidth = property(lambda self: self._rx_bw, lambda self, bw: self._set_bw("_rx_bw", bw))
    tx_rf_bandwidth = property(lambda self: self._tx_bw, lambda self, bw: self._set_bw("_tx_bw", bw))

    @property
    def rx_gain_max(self):
        return band("rx_gain_max", self._rx_lo)

    def rx_gain_legal(self, g):
        """The nearest gain the 1 dB table has: maximum gain minus a whole number of steps, not below 0 dB."""
        gmax = self.rx_gain_max
        step = scalar("rx_gain_step")
        k = round((gmax - g) / step)
        k = max(0, min(k, math.floor((gmax - scalar("rx_gain_min")) / step)))
        return gmax - k * step

    def set_gain_control_mode(self, ch, mode):
        if mode not in ("manual", "slow_attack", "fast_attack"):
            raise ValueError("gain control mode is manual, slow_attack or fast_attack")
        self._gain_mode[ch] = mode
        self._agc[ch].update(acc=0.0, n=0, state="search", lost=0, level=None, settle=0)
        if mode == "manual":
            self._set_gain(ch, self._rx_gain_set[ch])
        elif mode == "fast_attack":
            self._set_gain(ch, self.rx_gain_max)

    def set_rx_hardwaregain(self, ch, g):
        self._rx_gain_set[ch] = self.rx_gain_legal(g)
        if self._gain_mode[ch] == "manual":
            self._set_gain(ch, self._rx_gain_set[ch])

    def set_tx_hardwaregain(self, ch, g):
        step = scalar("tx_atten_step")
        if not -scalar("tx_atten_max") <= g <= 0.0:
            raise ValueError("tx hardwaregain %g dB is outside -89.75 .. 0" % g)
        self._tx_gain[ch] = round(g / step) * step

    gain_control_mode_chan0 = property(lambda s: s._gain_mode[0], lambda s, v: s.set_gain_control_mode(0, v))
    gain_control_mode_chan1 = property(lambda s: s._gain_mode[1], lambda s, v: s.set_gain_control_mode(1, v))
    rx_hardwaregain_chan0 = property(lambda s: s._rx_gain[0], lambda s, v: s.set_rx_hardwaregain(0, v))
    rx_hardwaregain_chan1 = property(lambda s: s._rx_gain[1], lambda s, v: s.set_rx_hardwaregain(1, v))
    tx_hardwaregain_chan0 = property(lambda s: s._tx_gain[0], lambda s, v: s.set_tx_hardwaregain(0, v))
    tx_hardwaregain_chan1 = property(lambda s: s._tx_gain[1], lambda s, v: s.set_tx_hardwaregain(1, v))

    def _set_gain(self, ch, g):
        g = self.rx_gain_legal(g)
        if g != self._rx_gain[ch] or not self.rx_gain_log[ch]:
            self.rx_gain_log[ch].append((self._n_rx, g))
        self._rx_gain[ch] = g

    # ---- derived quantities ------------------------------------------------------------------
    def rx_full_scale_dbm(self, ch=0):
        """CW power at the RX port that reaches ADC full scale at the gain in use."""
        return scalar("adc_fs_at_0db") - self._rx_gain[ch]

    def rx_noise_floor_dbm(self):
        """Thermal noise referred to the RX port in the simulated band (the sample rate)."""
        return w_to_dbm(K_BOLTZ * T0 * self._fs) + band("rx_nf", self._rx_lo)

    def rx_lo_leak_w(self):
        """LO power the receiver sends out of its own RX port (a CW at rx_lo_actual)."""
        return dbm_to_w(band("rx_lo_leak", self._rx_lo))

    def tx_full_scale_dbm(self, ch=0):
        """Output power of a full-scale tone at the present attenuation (compression included)."""
        return w_to_dbm(self._tx_carrier_w(10.0 ** (self._tx_gain[ch] / 10.0)))

    def _tx_lin_w(self):
        # linear (uncompressed) power of a full-scale tone at 0 dB attenuation, chosen so that the
        # compressed output is the data sheet's maximum output power
        pmax = dbm_to_w(band("tx_pmax", self._tx_lo))
        ip3 = dbm_to_w(band("tx_oip3", self._tx_lo))
        return pmax / (1.0 - 2.0 * pmax / ip3)

    def _tx_carrier_w(self, att):
        """Output power of a full-scale tone at power attenuation ratio att (<= 1)."""
        ip3 = dbm_to_w(band("tx_oip3", self._tx_lo))
        if self.m["tx_atten_before_output_stage"]:
            p = self._tx_lin_w() * att
            return p / (1.0 + 2.0 * p / ip3)
        return dbm_to_w(band("tx_pmax", self._tx_lo)) * att

    def _tx_leak_w(self, att):
        """Carrier leakage power: one part that follows the attenuator and one that does not, set
        by the data sheet's two points (dBc of a full-scale carrier at 0 and at 40 dB attenuation)."""
        lo = self._tx_lo
        p0 = self._tx_carrier_w(1.0) * 10.0 ** (band("tx_leak_0db", lo) / 10.0)
        p40 = self._tx_carrier_w(1e-4) * 10.0 ** (band("tx_leak_40db", lo) / 10.0)
        la = (p0 - p40) / (1.0 - 1e-4)
        return la * att + (p0 - la)

    def _residual(self, which):
        """Signal-proportional error left over to reach the data sheet EVM once the phase noise
        (and for RX the quadrature errors) the model has explicitly are counted; a power ratio."""
        lo = self._rx_lo if which == "rx" else self._tx_lo
        total = 10.0 ** (band(which + "_evm", lo) / 10.0)
        explicit = 0.0
        if self.enable["phase_noise"]:
            explicit += math.radians(band("lo_pn_rms", lo)) ** 2
        if which == "rx" and self.enable["iq_imbalance"]:
            explicit += self._image_ratio()
        return max(total - explicit, 0.0)

    def _image_ratio(self):
        e = scalar("rx_quad_gain_err") / 100.0
        p = math.radians(scalar("rx_quad_phase_err"))
        return (e * e + p * p) / 4.0

    # ---- filters -----------------------------------------------------------------------------
    def _analog_response(self, which, f):
        bbbw = (self._rx_bw if which == "rx" else self._tx_bw) / 2.0
        if which == "rx":
            fc3, fc1 = self.m["rx_bblpf_corner"] * bbbw, self.m["rx_tia_corner"] * bbbw
        else:
            fc3, fc1 = self.m["tx_bblpf_corner"] * bbbw, self.m["tx_secondary_corner"] * bbbw
        b, a = signal.butter(3, 2.0 * math.pi * fc3, analog=True)
        _, h3 = signal.freqs(b, a, 2.0 * math.pi * np.abs(f))
        h3 = np.where(f < 0, np.conj(h3), h3)
        return h3 / (1.0 + 1j * f / fc1)

    def _get_fir(self, which):
        """FIR at the data rate with the analog baseband response of one side over |f| < fs/2."""
        if which not in self._fir:
            ntaps = int(self.m["fir_taps"])
            n = 1 << int(math.ceil(math.log2(16 * ntaps)))
            f = np.fft.fftfreq(n, 1.0 / self._fs)
            delay = (ntaps - 1) / 2.0
            h = np.fft.ifft(self._analog_response(which, f) * np.exp(-2j * np.pi * f * delay / self._fs))
            h = np.real(h[:ntaps]) * np.kaiser(ntaps, 6.0)
            self._fir[which] = h / np.sum(h)
        return self._fir[which]

    def filter_delay(self):
        """Delay each side's filter adds, in samples."""
        return (int(self.m["fir_taps"]) - 1) // 2 if self.enable["filters"] else 0

    def _filter(self, which, ch, x):
        if not self.enable["filters"]:
            return x
        h = self._get_fir(which)
        key = (which, ch)
        if key not in self._zi:
            self._zi[key] = np.zeros(len(h) - 1, complex)
        y, self._zi[key] = signal.lfilter(h, [1.0], x, zi=self._zi[key])
        return y

    def _cnormal(self, n, power):
        """n complex Gaussian samples of mean power `power`."""
        s = math.sqrt(power / 2.0)
        return (self.rng.standard_normal(n) + 1j * self.rng.standard_normal(n)) * s

    # ---- transmit ----------------------------------------------------------------------------
    def transmit(self, codes):
        """Data-port samples -> RF envelope at the TX port(s), centred on tx_lo_actual.

        codes: complex, shape (n,) or (channels, n); I and Q in 16-bit units with full scale
        2**15, the 12-bit DAC word in the upper bits (as the IIO buffer carries it)."""
        codes = np.asarray(codes, complex)
        one = codes.ndim == 1
        codes = np.atleast_2d(codes)
        if codes.shape[0] != self.nch:
            raise ValueError("%d transmit channel(s), got data for %d" % (self.nch, codes.shape[0]))
        n = codes.shape[1]
        out = np.zeros((self.nch, n), complex)
        if self.ensm_mode in ("fdd", "tx") and n:
            fs = self._fs
            lo = self._tx_lo
            ip3 = dbm_to_w(band("tx_oip3", lo))
            theta = self._pn_tx.run(n, math.radians(band("lo_pn_rms", lo)) if self.enable["phase_noise"] else 0.0,
                                    self.m["pn_corner"], fs)
            rot = np.exp(1j * theta)
            res = self._residual("tx") if self.enable["evm_residual"] else 0.0
            for ch in range(self.nch):
                if self.enable["quantise"]:
                    q = (np.clip(np.floor(codes[ch].real / 16.0 + 0.5), -2048, 2047)
                         + 1j * np.clip(np.floor(codes[ch].imag / 16.0 + 0.5), -2048, 2047)) / 2048.0
                else:
                    q = codes[ch] / 32768.0
                if res > 0.0:
                    q = q * (1.0 + self._cnormal(n, res))
                q = self._filter("tx", ch, q * rot)
                att = 10.0 ** (self._tx_gain[ch] / 10.0)                 # power ratio, <= 1
                if self.m["tx_atten_before_output_stage"]:
                    y = soft_compress(q * math.sqrt(self._tx_lin_w() * att), ip3)
                else:
                    y = soft_compress(q * math.sqrt(self._tx_lin_w()), ip3) * math.sqrt(att)
                if self.enable["leak"]:
                    y = y + math.sqrt(self._tx_leak_w(att)) * np.exp(1j * self._tx_leak_phase[ch])
                if self.enable["noise"]:
                    y = y + self._cnormal(n, max(dbm_to_w(band("tx_noise", lo)) * att, K_BOLTZ * T0) * fs)
                out[ch] = y
            if self.nch == 2 and self.enable["crosstalk"]:
                k = 10.0 ** (-scalar("tx_isolation") / 20.0)
                out = out + k * out[::-1]
        self._n_tx += n
        return out[0] if one else out

    # ---- receive -----------------------------------------------------------------------------
    def receive(self, env, f_centre=None):
        """RF envelope at the RX port(s) -> data-port samples (complex, I and Q in -2048 .. 2047).

        env: complex, shape (n,) or (channels, n), in sqrt(W), centred on f_centre (default: this
        receiver's own LO)."""
        env = np.asarray(env, complex)
        one = env.ndim == 1
        env = np.atleast_2d(env)
        if env.shape[0] != self.nch:
            raise ValueError("%d receive channel(s), got signals for %d" % (self.nch, env.shape[0]))
        n = env.shape[1]
        out = np.zeros((self.nch, n), complex)
        if self.ensm_mode in ("fdd", "rx") and n:
            fs = self._fs
            lo = self._rx_lo
            x = env
            if self.nch == 2 and self.enable["crosstalk"]:
                x = x + 10.0 ** (-scalar("rx_isolation") / 20.0) * x[::-1]
            df = (self.rx_lo_actual if f_centre is None else f_centre) - self.rx_lo_actual
            theta = self._pn_rx.run(n, math.radians(band("lo_pn_rms", lo)) if self.enable["phase_noise"] else 0.0,
                                    self.m["pn_corner"], fs)
            if df != 0.0:
                theta = theta + 2.0 * math.pi * df * ((self._n_rx + np.arange(n)) / fs)
            rot = np.exp(1j * theta)
            res = self._residual("rx") if self.enable["evm_residual"] else 0.0
            noise_w = K_BOLTZ * T0 * fs * 10.0 ** (band("rx_nf", lo) / 10.0)
            for ch in range(self.nch):
                a = x[ch] * rot
                if res > 0.0:
                    a = a * (1.0 + self._cnormal(n, res))
                if self.enable["noise"]:
                    a = a + self._cnormal(n, noise_w)
                a = self._filter("rx", ch, a)
                if self.enable["iq_imbalance"]:
                    e = scalar("rx_quad_gain_err") / 100.0
                    p = math.radians(scalar("rx_quad_phase_err"))
                    a = a.real + 1j * (1.0 + e) * (a.imag * math.cos(p) + a.real * math.sin(p))
                out[ch] = self._agc_run(ch, a)
        self._n_rx += n
        return out[0] if one else out

    def _adc(self, ch, a, gain):
        """The gain-dependent, memoryless end of the receiver: compression, gain, ADC."""
        lo = self._rx_lo
        iip3 = min(band("rx_iip3", lo) + (self.rx_gain_max - gain), self.m["rx_iip3_ceiling"])
        v = soft_compress(a, dbm_to_w(iip3)) * math.sqrt(10.0 ** (gain / 10.0) / dbm_to_w(scalar("adc_fs_at_0db")))
        if not self.enable["quantise"]:
            return v * 2048.0
        return (np.clip(np.floor(v.real * 2048.0 + 0.5), -2048, 2047)
                + 1j * np.clip(np.floor(v.imag * 2048.0 + 0.5), -2048, 2047))

    @staticmethod
    def _dbfs(codes):
        """Mean power of ADC codes against a full-scale tone, dB."""
        p = np.mean(codes.real ** 2 + codes.imag ** 2) / 2048.0 ** 2
        return 10.0 * math.log10(max(p, 1e-12))

    def _agc_run(self, ch, a):
        mode = self._gain_mode[ch]
        if mode == "manual":
            return self._adc(ch, a, self._rx_gain[ch])
        if mode == "slow_attack":
            return self._agc_slow(ch, a)
        return self._agc_fast(ch, a)

    def _agc_slow(self, ch, a):
        m, st = self.m, self._agc[ch]
        period = max(1, int(round(m["agc_period"] * self._fs)))
        out = np.empty(len(a), complex)
        pos = 0
        while pos < len(a):
            take = min(period - st["n"], len(a) - pos)
            seg = self._adc(ch, a[pos:pos + take], self._rx_gain[ch])
            out[pos:pos + take] = seg
            st["acc"] += float(np.sum(seg.real ** 2 + seg.imag ** 2))
            st["n"] += take
            pos += take
            if st["n"] == period:
                p = 10.0 * math.log10(max(st["acc"] / period / 2048.0 ** 2, 1e-12))
                g = self._rx_gain[ch]
                if p > m["agc_outer_high"]:
                    g -= m["agc_step_outer"]
                elif p > m["agc_inner_high"]:
                    g -= m["agc_step_inner"]
                elif p < m["agc_outer_low"]:
                    g += m["agc_step_outer"]
                elif p < m["agc_inner_low"]:
                    g += m["agc_step_inner"]
                st["acc"], st["n"] = 0.0, 0
                self._n_rx += pos                    # so the log carries the sample the change takes effect at
                self._set_gain(ch, g)
                self._n_rx -= pos
        return out

    def _agc_fast(self, ch, a):
        """Burst AGC, in sub-blocks of `fast_block` samples.
        search:  maximum gain, until a sub-block is above `fast_detect`;
        settle:  each sub-block sets the gain for `fast_target` from the power just measured (a
                 clipped sub-block cannot be measured: step down `fast_clip_step`), until one lands
                 within 1 dB or `fast_settle_iterations` have gone;
        locked:  gain held.  A sub-block that clips or is `fast_stronger` dB over the target is a
                 stronger signal: settle again.  `fast_lost_blocks` sub-blocks in a row `fast_lost`
                 dB under the target: the burst is over, back to search at maximum gain."""
        m, st = self.m, self._agc[ch]
        blk = int(m["fast_block"])
        out = np.empty(len(a), complex)
        pos = 0

        def measure(seg):
            """Per sub-block: power in dBFS and whether a rail was hit."""
            k = len(seg) // blk
            re, im = seg.real[:k * blk].reshape(k, blk), seg.imag[:k * blk].reshape(k, blk)
            p = 10.0 * np.log10(np.maximum((re ** 2 + im ** 2).mean(axis=1) / 2048.0 ** 2, 1e-12))
            clip = ((np.abs(re) >= 2047) | (np.abs(im) >= 2047)).any(axis=1)
            return p, clip

        def set_gain(g, at):
            self._n_rx += at                     # the log carries the sample the change takes effect at
            self._set_gain(ch, g)
            self._n_rx -= at

        def adjust(p, clipped, at):
            """One settling step from a measured sub-block; True when it needed no more than 1 dB."""
            set_gain(self._rx_gain[ch] - (m["fast_clip_step"] if clipped else p - m["fast_target"]), at)
            return (not clipped) and abs(p - m["fast_target"]) < 1.0

        while pos < len(a):
            rest = len(a) - pos
            if rest < blk:                       # a tail shorter than a sub-block: no decision on it
                out[pos:] = self._adc(ch, a[pos:], self._rx_gain[ch])
                break
            if st["state"] == "settle":
                seg = self._adc(ch, a[pos:pos + blk], self._rx_gain[ch])
                out[pos:pos + blk] = seg
                pos += blk
                p, clip = measure(seg)
                st["settle"] += 1
                if adjust(float(p[0]), bool(clip[0]), pos) or st["settle"] >= m["fast_settle_iterations"]:
                    st.update(state="locked", lost=0)
                continue
            rest = min(rest - rest % blk, 256 * blk)      # look ahead in bounded chunks
            seg = self._adc(ch, a[pos:pos + rest], self._rx_gain[ch])
            p, clip = measure(seg)
            if st["state"] == "search":
                hit = np.nonzero((p > m["fast_detect"]) | clip)[0]
                if len(hit) == 0:
                    k = len(p) * blk
                    out[pos:pos + k] = seg[:k]
                    pos += k
                    continue
                i = int(hit[0])
                out[pos:pos + (i + 1) * blk] = seg[:(i + 1) * blk]
                pos += (i + 1) * blk
                st.update(state="settle", settle=0)
                if adjust(float(p[i]), bool(clip[i]), pos):
                    st.update(state="locked", lost=0)
            else:                                # locked
                strong = clip | (p > m["fast_target"] + m["fast_stronger"])
                low = p < m["fast_target"] - m["fast_lost"]
                run, event, i = st["lost"], None, 0
                for i in range(len(p)):
                    if strong[i]:
                        event = "stronger"
                        break
                    run = run + 1 if low[i] else 0
                    if run >= m["fast_lost_blocks"]:
                        event = "lost"
                        break
                if event is None:
                    st["lost"] = run
                    k = len(p) * blk
                    out[pos:pos + k] = seg[:k]
                    pos += k
                    continue
                out[pos:pos + (i + 1) * blk] = seg[:(i + 1) * blk]
                pos += (i + 1) * blk
                if event == "lost":
                    st.update(state="search", lost=0)
                    set_gain(self.rx_gain_max, pos)
                else:
                    st.update(state="settle", settle=0, lost=0)
                    if adjust(float(p[i]), bool(clip[i]), pos):
                        st.update(state="locked", lost=0)
        return out

    def rx_gain_at(self, sample, ch=0):
        """The gain that was in use at an RX sample index (counted from the first sample received)."""
        g = self.rx_gain_max
        for at, gain in self.rx_gain_log[ch]:
            if at > sample:
                break
            g = gain
        return g

    @property
    def rx_sample_count(self):
        """Samples the receiver has produced so far."""
        return self._n_rx

    # ---- software side: buffers, as pyadi-iio has them ---------------------------------------
    def tx(self, data):
        """Queue samples for transmission (16-bit units, full scale 2**15).  With
        tx_cyclic_buffer the buffer repeats until tx_destroy_buffer()."""
        data = np.atleast_2d(np.asarray(data, complex))
        if data.shape[0] != self.nch:
            raise ValueError("%d transmit channel(s), got data for %d" % (self.nch, data.shape[0]))
        if self.tx_cyclic_buffer:
            self._tx_cyclic = [data, 0]
        else:
            self._tx_queue.append(data)

    def tx_destroy_buffer(self):
        self._tx_cyclic = None
        self._tx_queue = []

    def _pull_tx(self, n):
        out = np.zeros((self.nch, n), complex)
        if self._tx_cyclic is not None:
            data, at = self._tx_cyclic
            idx = (at + np.arange(n)) % data.shape[1]
            self._tx_cyclic[1] = (at + n) % data.shape[1]
            return data[:, idx]
        pos = 0
        while pos < n and self._tx_queue:
            head = self._tx_queue[0]
            take = min(n - pos, head.shape[1])
            out[:, pos:pos + take] = head[:, :take]
            pos += take
            if take == head.shape[1]:
                self._tx_queue.pop(0)
            else:
                self._tx_queue[0] = head[:, take:]
        return out

    def tx_pending(self):
        """Samples queued and not yet sent."""
        return sum(b.shape[1] for b in self._tx_queue)

    def rx(self):
        """rx_buffer_size samples from the RX data port; runs the arena until they exist."""
        if self.arena is None:
            raise RuntimeError("%s is not in an Arena: nothing reaches its RX port" % self.name)
        while len(self._rx_fifo[0]) < self.rx_buffer_size:
            self.arena.run(max(self.rx_buffer_size - len(self._rx_fifo[0]), 1))
        out = np.array([f[:self.rx_buffer_size] for f in self._rx_fifo])
        self._rx_fifo = [f[self.rx_buffer_size:] for f in self._rx_fifo]
        return out[0] if self.nch == 1 else out

    def rx_flush(self):
        self._rx_fifo = [np.zeros(0, complex) for _ in range(self.nch)]


class Arena:
    """Radios in free space: every transmitter reaches every other radio's receiver through
    Friis coupling (antenna gains, lambda / (4 pi d), carrier phase, delay to the nearest
    sample).  A radio does not hear its own transmitter unless self_isolation_db is given."""

    def __init__(self):
        self.nodes = []
        self.time = 0                # samples

    def add(self, radio, position, antenna_gain_dbi=0.0, self_isolation_db=None, pa_gain_db=0.0, lna_gain_db=0.0,
            lna_nf_db=None):
        """position in metres (x, y, z).  pa_gain_db / lna_gain_db: ideal external gain between the
        chip and the antenna; lna_nf_db: that LNA's noise figure (None: noiseless)."""
        if self.nodes and radio.sample_rate != self.nodes[0]["radio"].sample_rate:
            raise ValueError("all radios in one Arena run at one sample rate")
        if radio.nch != 1:
            raise ValueError("the Arena couples single-channel radios")
        radio.arena = self
        self.nodes.append(dict(radio=radio, pos=np.asarray(position, float), g=antenna_gain_dbi,
                               iso=self_isolation_db, pa=pa_gain_db, lna=lna_gain_db, lna_nf=lna_nf_db,
                               hist=np.zeros(0, complex)))

    def coupling(self, i, j):
        """(amplitude ratio, delay in samples) from node i's antenna feed to node j's."""
        a, b = self.nodes[i], self.nodes[j]
        d = float(np.linalg.norm(a["pos"] - b["pos"]))
        lam = C0 / a["radio"].tx_lo_actual
        amp = 10.0 ** ((a["g"] + b["g"]) / 20.0) * lam / (4.0 * math.pi * d)
        return amp * np.exp(-2j * math.pi * d / lam), int(round(d / C0 * a["radio"].sample_rate))

    def run(self, n):
        """Advance every radio by n samples."""
        fs = self.nodes[0]["radio"].sample_rate
        tx = []
        for nd in self.nodes:
            y = nd["radio"].transmit(nd["radio"]._pull_tx(n))[0] * 10.0 ** (nd["pa"] / 20.0)
            tx.append(np.concatenate([nd["hist"], y]))
        maxdelay = 0
        for j, rxn in enumerate(self.nodes):
            r = rxn["radio"]
            total = np.zeros(n, complex)
            t = (self.time + np.arange(n)) / fs
            for i, txn in enumerate(self.nodes):
                if i == j:
                    if rxn["iso"] is None:
                        continue
                    h, delay = 10.0 ** (-rxn["iso"] / 20.0) / 10.0 ** ((rxn["pa"] + rxn["lna"]) / 20.0), 0
                else:
                    h, delay = self.coupling(i, j)
                maxdelay = max(maxdelay, delay)
                src = tx[i]
                past = len(src) - n - delay              # index in src of the sample arriving now
                seg = src[max(past, 0):past + n] if past + n > 0 else src[:0]
                if len(seg) < n:
                    seg = np.concatenate([np.zeros(n - len(seg), complex), seg])
                # the transmitter's carrier against this receiver's LO
                df = txn["radio"].tx_lo_actual - r.rx_lo_actual
                total += h * seg * (np.exp(2j * math.pi * df * t) if df else 1.0)
            if rxn["lna"] != 0.0:
                # the chip's own noise figure already counts the source's kT once; with gain G in front
                # the chain is kT F_lna + kT (F_chip - 1) / G, so the LNA adds kT (F_lna - 1 / G) here
                f_lna = 10.0 ** ((rxn["lna_nf"] or 0.0) / 10.0)
                total = total + r._cnormal(n, K_BOLTZ * T0 * fs * (f_lna - 10.0 ** (-rxn["lna"] / 10.0)))
            codes = r.receive(total * 10.0 ** (rxn["lna"] / 20.0))
            r._rx_fifo[0] = np.concatenate([r._rx_fifo[0], codes])
        for nd, y in zip(self.nodes, tx):
            nd["hist"] = y[len(y) - maxdelay:] if maxdelay else np.zeros(0, complex)
        self.time += n


# ---------------------------------------------------------------------------------------------
# check: measure the model as the data sheet measures the chip
# ---------------------------------------------------------------------------------------------
def _tone(n, f, fs, amp=1.0):
    return amp * np.exp(2j * np.pi * f * np.arange(n) / fs)


def _bin_power(x, f, fs):
    """Power of the component of x at frequency f (f on an FFT bin of len(x))."""
    k = int(round(f * len(x) / fs))
    return abs(np.fft.fft(x)[k] / len(x)) ** 2


def measure(lo, fs=30.72e6, bw=18e6, seed=1):
    """Model figures at one LO frequency, each measured from signals; returns a dict."""
    out = {}
    n = 1 << 16

    def radio(**kw):
        r = AD9361(seed=seed)
        r.rx_lo = r.tx_lo = lo
        r.sample_rate = fs
        r.rx_rf_bandwidth = r.tx_rf_bandwidth = bw
        r.gain_control_mode_chan0 = "manual"
        r.rx_hardwaregain_chan0 = r.rx_gain_max
        r.tx_hardwaregain_chan0 = 0.0
        r.enable.update(kw)
        return r

    quiet = dict(noise=False, phase_noise=False, evm_residual=False, leak=False, iq_imbalance=False)
    half = n // 2                       # the second half of each record is analysed (filters settled)
    f1 = round(1e6 * half / fs) * fs / half                             # 1 MHz, moved onto an FFT bin
    f2 = round(1.5e6 * half / fs) * fs / half

    # TX: full-scale tone, maximum output power
    r = radio(**quiet)
    y = r.transmit(_tone(n, f1, fs, 32767.0))
    out["tx_pmax"] = w_to_dbm(np.mean(np.abs(y[n // 2:]) ** 2))
    # TX: two tones, OIP3 = P_tone + (P_tone - P_im3) / 2
    r = radio(**quiet)
    y = r.transmit(_tone(n, f1, fs, 8000.0) + _tone(n, f2, fs, 8000.0))[n // 2:]
    pt, pim = _bin_power(y, f1, fs), _bin_power(y, 2 * f1 - f2, fs)
    out["tx_oip3"] = w_to_dbm(pt) + (w_to_dbm(pt) - w_to_dbm(pim)) / 2.0
    # TX: carrier leakage against the full-scale carrier at 0 and 40 dB attenuation
    for att, key in ((0.0, "tx_leak_0db"), (-40.0, "tx_leak_40db")):
        r = radio(noise=False, phase_noise=False, evm_residual=False, iq_imbalance=False)
        r.tx_hardwaregain_chan0 = att
        y = r.transmit(_tone(n, f1, fs, 32767.0))[n // 2:]
        out[key] = w_to_dbm(_bin_power(y, 0.0, fs)) - w_to_dbm(_bin_power(y, f1, fs))
    # TX: noise floor with no signal
    r = radio(leak=False)
    y = r.transmit(np.zeros(n))
    out["tx_noise"] = w_to_dbm(np.mean(np.abs(y) ** 2) / fs)
    # TX: EVM of a full-scale-backed-off 16-QAM-like random signal against what was sent
    r = radio(noise=False, leak=False, filters=False)
    rng = np.random.default_rng(seed)
    sym = (rng.integers(0, 4, n) * 2 - 3 + 1j * (rng.integers(0, 4, n) * 2 - 3)) * 2048.0   # multiples of 16: exact in 12 bits
    y = r.transmit(sym)
    g = np.vdot(sym, y) / np.vdot(sym, sym)
    out["tx_evm"] = 10.0 * math.log10(np.mean(np.abs(y - g * sym) ** 2) / np.mean(np.abs(g * sym) ** 2))

    # RX: gain and full scale: a tone 20 dB under full scale at maximum gain
    r = radio(**quiet)
    pin = dbm_to_w(r.rx_full_scale_dbm() - 20.0)
    c = r.receive(_tone(n, f1, fs, math.sqrt(pin)))[n // 2:]
    out["rx_gain_max"] = 10.0 * math.log10(_bin_power(c, f1, fs) / 2048.0 ** 2 * dbm_to_w(scalar("adc_fs_at_0db")) / pin)
    # RX: noise figure = output noise referred to the input, against kT0 (Y-factor would give the same)
    r = radio(phase_noise=False, evm_residual=False, iq_imbalance=False, filters=False)
    c = r.receive(np.zeros(n))
    pn_in = np.mean(np.abs(c) ** 2) / 2048.0 ** 2 * dbm_to_w(scalar("adc_fs_at_0db")) / 10.0 ** (r.rx_gain_max / 10.0)
    out["rx_nf"] = 10.0 * math.log10(pn_in / (K_BOLTZ * T0 * fs))
    # RX: two tones 50 dB under full scale... the intercept is far above full scale at maximum gain,
    # so measure it with the ADC left unquantised: IIP3 = P_tone + (P_tone - P_im3) / 2 at the input
    r = radio(**quiet, quantise=False)
    pin = dbm_to_w(-70.0)
    c = r.receive(_tone(n, f1, fs, math.sqrt(pin)) + _tone(n, f2, fs, math.sqrt(pin)))[n // 2:]
    pt, pim = _bin_power(c, f1, fs), _bin_power(c, 2 * f1 - f2, fs)
    out["rx_iip3"] = -70.0 + (10.0 * math.log10(pt / pim)) / 2.0
    # RX: EVM of a clean modulated input 12 dB under full scale (rms), against what was sent, with the
    # gain 40 dB under maximum so that thermal noise is 55 dB under the signal (at maximum gain a
    # signal 12 dB under full scale is only 16 dB over the noise of a 30 MHz band)
    r = radio(filters=False)
    r.rx_hardwaregain_chan0 = r.rx_gain_max - 40.0
    sym = (rng.integers(0, 4, n) * 2 - 3 + 1j * (rng.integers(0, 4, n) * 2 - 3)) / math.sqrt(10.0)
    x = sym * math.sqrt(dbm_to_w(r.rx_full_scale_dbm() - 12.0))
    c = r.receive(x)
    g = np.vdot(x, c) / np.vdot(x, x)
    out["rx_evm"] = 10.0 * math.log10(np.mean(np.abs(c - g * x) ** 2) / np.mean(np.abs(g * x) ** 2))
    # RX: image of a tone (quadrature errors)
    r = radio(noise=False, phase_noise=False, evm_residual=False)
    c = r.receive(_tone(n, f1, fs, math.sqrt(dbm_to_w(r.rx_full_scale_dbm() - 6.0))))[n // 2:]
    out["rx_image"] = 10.0 * math.log10(_bin_power(c, -f1, fs) / _bin_power(c, f1, fs))
    # filters: droop at the edge of the rf bandwidth
    r = radio(**quiet, quantise=False)
    fe = round(bw / 2.0 * 0.9 * half / fs) * fs / half
    for which in ("tx", "rx"):
        h = r._get_fir(which)
        resp = abs(np.sum(h * np.exp(-2j * np.pi * fe / fs * np.arange(len(h)))))
        out[which + "_droop_at_0.45bw"] = 20.0 * math.log10(resp)
        out[which + "_analog_at_0.45bw"] = 20.0 * math.log10(abs(r._analog_response(which, np.array([fe]))[0]))
    return out


def cmd_check(args):
    worst = 0.0
    print("AD9361 model against the data sheet (typ.), fs %.2f MSPS, rf bandwidth %.1f MHz" % (args.fs / 1e6, args.bw / 1e6))
    for lo in BANDS:
        got = measure(lo, args.fs, args.bw)
        print("\nLO %.1f MHz" % (lo / 1e6))
        print("  %-16s %10s %10s %8s  %s" % ("quantity", "model", "data sheet", "diff", "unit / status"))
        for key in ("rx_gain_max", "rx_nf", "rx_iip3", "rx_evm", "tx_pmax", "tx_oip3", "tx_evm", "tx_noise",
                    "tx_leak_0db", "tx_leak_40db"):
            want = band(key, lo)
            d = got[key] - want
            worst = max(worst, abs(d))
            print("  %-16s %10.2f %10.2f %+8.2f  %s (%s)" % (key, got[key], want, d, SPEC[key][1], SPEC[key][2]))
        ir = 10.0 * math.log10((0.002 ** 2 + math.radians(0.2) ** 2) / 4.0)
        print("  %-16s %10.2f %10.2f %+8.2f  dBc (from 0.2 %% and 0.2 deg)" % ("rx_image", got["rx_image"], ir, got["rx_image"] - ir))
        for which in ("tx", "rx"):
            print("  %-16s %10.3f %10.3f %+8.3f  dB (FIR against the analog response)"
                  % (which + " at 0.45 bw", got[which + "_droop_at_0.45bw"], got[which + "_analog_at_0.45bw"],
                     got[which + "_droop_at_0.45bw"] - got[which + "_analog_at_0.45bw"]))
    print("\nlargest difference from a data sheet value: %.2f dB" % worst)
    return 0 if worst < 0.5 else 1


def cmd_spec(args):
    print("%-18s %-28s %-7s %-4s %s" % ("name", "800 MHz / 2.4 GHz / 5.5 GHz", "unit", "from", "what"))
    for k, (v, unit, status, what) in SPEC.items():
        print("%-18s %-28s %-7s %-4s %s" % (k, " / ".join("%g" % x for x in v), unit, status, what))
    for k, (v, unit, status, what) in SCALARS.items():
        print("%-18s %-28s %-7s %-4s %s" % (k, "%g" % v, unit, status, what))
    print("\nmodel assumptions (not from the data sheet):")
    for k, v in MODEL.items():
        print("  %-30s %s" % (k, v))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="measure the model and compare with the data sheet")
    p.add_argument("--fs", type=float, default=30.72e6)
    p.add_argument("--bw", type=float, default=18e6)
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("spec", help="print the data sheet table and the model assumptions")
    p.set_defaults(fn=cmd_spec)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
