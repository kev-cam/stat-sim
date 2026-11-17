-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ad9361_spectral_pkg: the AD9361 model one event at a time, for spectral event-driven simulation.
--
-- An event is one symbol period of signal: SPEC_N samples at the data port, handed over as their
-- spectrum (ad9361_frame), and an rf_spectrum at the RF pins.  Inside the chip the linear parts work
-- on the lines (the analog baseband filters), and everything that is not linear (DAC and ADC words,
-- compression, the AGC changing gain part-way through) works on the samples of the event, through
-- ad9361_pkg's per-sample procedures: the same model as ad9361.py, 64 samples at a time.
library ieee;
use ieee.math_real.all;
library rf;
use rf.rf_signal_pkg.all;
use rf.iq_pkg.all;
use work.rf_spectrum_pkg.all;
use work.ad9361_pkg.all;

package ad9361_spectral_pkg is
    -- One event at the data port: the samples x[n], n = 0 .. SPEC_N - 1, as lines,
    -- x[n] = sum_k lines(k) exp(j 2 pi k n / SPEC_N).  Units are the data port's: transmit samples have
    -- full scale 2**15 (the 12-bit DAC word in the upper bits), receive samples are -2048 .. 2047.
    type ad9361_frame is record
        lines : spec_lines;
        seq   : natural;             -- changes with every event; 0: no frame
    end record;
    constant AD9361_NO_FRAME : ad9361_frame := (lines => LINES_ZERO, seq => 0);

    type ad9361_fast_state is (FAST_SEARCH, FAST_SETTLE, FAST_LOCKED);
    type ad9361_agc_state is record
        gain_db : real;              -- RX gain in use
        fast    : ad9361_fast_state;
        settle  : natural;           -- settling steps taken
        lost    : natural;           -- sub-blocks in a row under the lost level
        acc     : real;              -- slow attack: sum of |code|^2 ...
        acc_n   : natural;           -- ... over this many samples
    end record;
    function ad9361_agc_init(cfg : ad9361_config) return ad9361_agc_state;

    -- the analog baseband filters (third-order Butterworth and one real pole) at offset f from the carrier
    function ad9361_bb_response(rx : boolean; rf_bw : real; f : real) return iq_sample;

    -- one event through the transmitter: data-port frame -> spectrum at the TX pin
    procedure ad9361_tx_symbol(cfg : in ad9361_config; st : inout ad9361_state; frame : in ad9361_frame;
                               s : out rf_spectrum);
    -- one event through the receiver: spectrum at the RX pin (the event starts at t0 seconds) -> frame.
    -- frame.seq = 0 when the receiver is off.
    procedure ad9361_rx_symbol(cfg : in ad9361_config; st : inout ad9361_state; agc : inout ad9361_agc_state;
                               s : in rf_spectrum; t0 : in real; frame : out ad9361_frame);
    -- what the receiver sends out of its own RX pin: its LO leakage, one line at the carrier
    function ad9361_rx_emission(cfg : ad9361_config; seq : positive) return rf_spectrum;
end package;

package body ad9361_spectral_pkg is
    function ad9361_agc_init(cfg : ad9361_config) return ad9361_agc_state is
        variable a : ad9361_agc_state := (gain_db => ad9361_rx_gain_max(cfg.rx_lo), fast => FAST_SEARCH, settle => 0,
                                          lost => 0, acc => 0.0, acc_n => 0);
    begin
        if cfg.gain_mode = AGC_MANUAL then
            a.gain_db := ad9361_rx_gain_legal(cfg.rx_lo, cfg.rx_gain_db);
        end if;
        return a;
    end function;

    function ad9361_bb_response(rx : boolean; rf_bw : real; f : real) return iq_sample is
        constant bbbw : real := rf_bw / 2.0;
        variable fc3, fc1, x, dr, di, m, pr, pi, pm : real;
    begin
        if rx then
            fc3 := AD9361_RX_BBLPF_CORNER * bbbw;
            fc1 := AD9361_RX_TIA_CORNER * bbbw;
        else
            fc3 := AD9361_TX_BBLPF_CORNER * bbbw;
            fc1 := AD9361_TX_SECONDARY_CORNER * bbbw;
        end if;
        -- 1 / ((jx)^3 + 2 (jx)^2 + 2 jx + 1), x = f / fc3
        x := f / fc3;
        dr := 1.0 - 2.0 * x * x;
        di := 2.0 * x - x * x * x;
        m := dr * dr + di * di;
        -- 1 / (1 + j f / fc1)
        pr := 1.0;
        pi := f / fc1;
        pm := pr * pr + pi * pi;
        -- (dr - j di) / m * (pr - j pi) / pm
        return (i => (dr * pr - di * pi) / (m * pm), q => -(dr * pi + di * pr) / (m * pm));
    end function;

    -- The baseband filters on the lines of an event; f_shift is where line 0 sits against the carrier the
    -- filter belongs to.  A filter is applied on the grid the signal is periodic on (the transmitter's):
    -- each line is then a tone through the event and its guard, and the filter only scales it.  Filtering
    -- after a carrier offset has been applied would wrap the filter's transient round a block whose two
    -- ends differ by the offset's phase, an error that grows with the square of the offset.
    function filtered(x : spec_lines; rx : boolean; rf_bw : real; df : real; f_shift : real := 0.0) return spec_lines is
        variable r : spec_lines;
        variable h : iq_sample;
    begin
        for k in x'range loop
            h := ad9361_bb_response(rx, rf_bw, spec_line_offset(k, df) + f_shift);
            r(k) := iq_mul(x(k), h);
        end loop;
        return r;
    end function;

    procedure ad9361_tx_symbol(cfg : in ad9361_config; st : inout ad9361_state; frame : in ad9361_frame;
                               s : out rf_spectrum) is
        constant df : real := cfg.sample_rate / real(SPEC_N);
        variable t : spec_lines;
        variable y : rf_signal;
        variable r : rf_spectrum;
    begin
        if (cfg.ensm /= ENSM_TX and cfg.ensm /= ENSM_FDD) or frame.seq = 0 then
            s := spec_silent(frame.seq + 1);
            return;
        end if;
        t := lines_to_time(filtered(frame.lines, false, cfg.tx_rf_bw, df));
        for n in t'range loop
            ad9361_tx_sample(cfg, st, t(n), y);
            t(n) := (i => y.eh_re, q => y.eh_im);
        end loop;
        r.h := time_to_lines(t);
        r.v := LINES_ZERO;
        r.freq := ad9361_lo_actual(cfg.tx_lo, cfg.xo_ppm);
        r.df := df;
        r.seq := frame.seq;
        s := r;
    end procedure;

    procedure ad9361_rx_symbol(cfg : in ad9361_config; st : inout ad9361_state; agc : inout ad9361_agc_state;
                               s : in rf_spectrum; t0 : in real; frame : out ad9361_frame) is
        constant df  : real := cfg.sample_rate / real(SPEC_N);
        constant lo  : real := ad9361_lo_actual(cfg.rx_lo, cfg.xo_ppm);
        constant blk : natural := AD9361_FAST_BLOCK;
        constant period : natural := integer(round(AD9361_AGC_PERIOD * cfg.sample_rate));
        variable r : rf_spectrum;
        variable t : spec_lines := LINES_ZERO;
        variable c : iq_sample;
        variable cfgv : ad9361_config := cfg;
        variable acc, p : real;
        variable clip, done : boolean;

        -- one settling step from a measured sub-block; true when it needed no more than 1 dB
        impure function adjust(p : real; clipped : boolean) return boolean is
        begin
            if clipped then
                agc.gain_db := ad9361_rx_gain_legal(cfg.rx_lo, agc.gain_db - AD9361_FAST_CLIP_STEP);
                return false;
            end if;
            agc.gain_db := ad9361_rx_gain_legal(cfg.rx_lo, agc.gain_db - (p - AD9361_FAST_TARGET));
            return abs(p - AD9361_FAST_TARGET) < 1.0;
        end function;
    begin
        if cfg.ensm /= ENSM_RX and cfg.ensm /= ENSM_FDD then
            frame := AD9361_NO_FRAME;
            return;
        end if;
        if not spec_is_silent(s) then
            assert abs(s.df - df) < 1.0e-6 * df
                report "ad9361: the signal's line spacing is not this receiver's sample rate / " & integer'image(SPEC_N)
                severity failure;
            r := s;
            r.h := filtered(s.h, true, cfg.rx_rf_bw, df, s.freq - lo);     -- on the sender's grid, then the offset
            r := spec_regrid(r, lo, t0);
            t := lines_to_time(r.h);
        end if;
        if cfg.gain_mode = AGC_MANUAL then
            agc.gain_db := ad9361_rx_gain_legal(cfg.rx_lo, cfg.rx_gain_db);
        end if;
        for n in t'range loop
            cfgv.rx_gain_db := agc.gain_db;
            ad9361_rx_sample(cfgv, st, (eh_re => t(n).i, eh_im => t(n).q, ev_re => 0.0, ev_im => 0.0, freq => lo), 0.0, c);
            t(n) := c;
            if n mod blk = 0 then
                acc := 0.0;
                clip := false;
            end if;
            acc := acc + c.i * c.i + c.q * c.q;
            clip := clip or abs(c.i) >= 2047.0 or abs(c.q) >= 2047.0;
            if cfg.gain_mode = AGC_SLOW_ATTACK then
                agc.acc := agc.acc + c.i * c.i + c.q * c.q;
                agc.acc_n := agc.acc_n + 1;
                if agc.acc_n >= period then
                    cfgv.rx_gain_db := agc.gain_db;
                    agc.gain_db := ad9361_agc_slow(cfgv, 10.0 * log10(realmax(agc.acc / real(period) / 2048.0 ** 2, 1.0e-12)));
                    agc.acc := 0.0;
                    agc.acc_n := 0;
                end if;
            elsif cfg.gain_mode = AGC_FAST_ATTACK and n mod blk = blk - 1 then
                p := 10.0 * log10(realmax(acc / real(blk) / 2048.0 ** 2, 1.0e-12));
                case agc.fast is
                    when FAST_SEARCH =>
                        if p > AD9361_FAST_DETECT or clip then
                            agc.fast := FAST_SETTLE;
                            agc.settle := 0;
                            if adjust(p, clip) then
                                agc.fast := FAST_LOCKED;
                                agc.lost := 0;
                            end if;
                        end if;
                    when FAST_SETTLE =>
                        agc.settle := agc.settle + 1;
                        done := adjust(p, clip);
                        if done or agc.settle >= AD9361_FAST_SETTLE_ITERATIONS then
                            agc.fast := FAST_LOCKED;
                            agc.lost := 0;
                        end if;
                    when FAST_LOCKED =>
                        if clip or p > AD9361_FAST_TARGET + AD9361_FAST_STRONGER then
                            agc.fast := FAST_SETTLE;
                            agc.settle := 0;
                            agc.lost := 0;
                            if adjust(p, clip) then
                                agc.fast := FAST_LOCKED;
                            end if;
                        elsif p < AD9361_FAST_TARGET - AD9361_FAST_LOST then
                            agc.lost := agc.lost + 1;
                            if agc.lost >= AD9361_FAST_LOST_BLOCKS then
                                agc.fast := FAST_SEARCH;
                                agc.lost := 0;
                                agc.gain_db := ad9361_rx_gain_max(cfg.rx_lo);
                            end if;
                        else
                            agc.lost := 0;
                        end if;
                end case;
            end if;
        end loop;
        frame.lines := time_to_lines(t);
        if s.seq = 0 then
            frame.seq := 1;
        else
            frame.seq := s.seq;
        end if;
    end procedure;

    function ad9361_rx_emission(cfg : ad9361_config; seq : positive) return rf_spectrum is
        variable r : rf_spectrum := (h => LINES_ZERO, v => LINES_ZERO, freq => ad9361_lo_actual(cfg.rx_lo, cfg.xo_ppm),
                                     df => cfg.sample_rate / real(SPEC_N), seq => seq);
    begin
        if cfg.ensm /= ENSM_RX and cfg.ensm /= ENSM_FDD then
            return spec_silent(seq);
        end if;
        r.h(0) := (i => sqrt(dbm_to_watts(ad9361_band(AD9361_T_RX_LO_LEAK, cfg.rx_lo))), q => 0.0);
        return r;
    end function;
end package body;
