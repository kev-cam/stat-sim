-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
-- Test bench for ad9361_pkg: prints "AD9361 <name> <value>" lines that `ad9361_vhdl.py check` compares
-- with the Python model (ad9361.py).  Run by hand:
--   nvc --std=2008 --work=rf -a <nvc>/lib/rf/rf_signal_pkg.vhd <nvc>/lib/rf/iq_pkg.vhd <nvc>/lib/rf/ofdm_pkg.vhd
--   nvc --std=2008 -L . -a ad9361_pkg.vhd tb_ad9361.vhd -e tb_ad9361 -r
library ieee;
use ieee.math_real.all;
library rf;
use rf.rf_signal_pkg.all;
use rf.iq_pkg.all;
use rf.ofdm_pkg.all;
use work.ad9361_pkg.all;

entity tb_ad9361 is end entity;

architecture t of tb_ad9361 is
    constant N_MC : natural := 200000;
    type real_vec is array (natural range <>) of real;
    constant LOS : real_vec(0 to 2) := (800.0e6, 2.437e9, 5.2e9);

    procedure say(name : string; v : real) is
    begin
        report "AD9361 " & name & " " & to_string(v, "%.15e");
    end procedure;

    function mhz(f : real) return string is
    begin
        return integer'image(integer(round(f / 1.0e6)));
    end function;

    function cfg_at(f : real) return ad9361_config is
        variable c : ad9361_config := ad9361_default_config;
    begin
        c.rx_lo := f;
        c.tx_lo := f;
        c.sample_rate := 20.0e6;
        c.rx_gain_db := ad9361_rx_gain_max(f);
        c.tx_atten_db := 0.0;
        return c;
    end function;

    -- EVM in dB from running sums over (sent s, received y): the complex gain and a constant offset
    -- (carrier leakage) are fitted and removed, as an EVM measurement does
    function evm_db(n : real; s2, y2, c_re, c_im, ys_re, ys_im, ss_re, ss_im : real) return real is
        constant ms_re : real := ss_re / n;
        constant ms_im : real := ss_im / n;
        constant my_re : real := ys_re / n;
        constant my_im : real := ys_im / n;
        -- covariance fit: g = cov(s, y) / var(s)
        constant vs    : real := s2 / n - (ms_re * ms_re + ms_im * ms_im);
        constant cv_re : real := c_re / n - (ms_re * my_re + ms_im * my_im);
        constant cv_im : real := c_im / n - (ms_re * my_im - ms_im * my_re);
        constant g_re  : real := cv_re / vs;
        constant g_im  : real := cv_im / vs;
        constant vy    : real := y2 / n - (my_re * my_re + my_im * my_im);
        constant err   : real := vy - (g_re * g_re + g_im * g_im) * vs;
    begin
        return 10.0 * log10(realmax(err, 1.0e-300) / ((g_re * g_re + g_im * g_im) * vs));
    end function;
begin
    process
        variable cfg : ad9361_config;
        variable pv : real_vector(0 to AD9361_ACCEL_N - 1);
        variable st : ad9361_state;
        variable s : rf_signal;
        variable c, w : iq_sample;
        variable a, fsw, u, acc, t : real;
        variable s2, y2, c_re, c_im, ys_re, ys_im, ss_re, ss_im, m_re, m_im : real;
        variable seed1 : positive := 11;
        variable seed2 : positive := 22;
        type tag3 is array (0 to 2) of string(1 to 5);
        constant ATT : real_vec(0 to 2) := (0.0, 10.0, 40.25);
        constant ATT_TAG : tag3 := ("0    ", "10   ", "40p25");
        constant BACK : real_vec(0 to 2) := (0.0, 20.0, 60.0);
        constant REL : real_vec(0 to 3) := (-60.0, -20.0, -3.0, 6.0);
        constant CODE_I : real_vec(0 to 3) := (32767.0, 8000.0, -20000.0, 7.0);
        constant CODE_Q : real_vec(0 to 3) := (0.0, -6000.0, 20000.0, 8.0);
        constant BAND_F : real_vec(0 to 4) := (800.0e6, 1.5e9, 2.437e9, 5.2e9, 6.0e9);
        constant AGC_P : real_vec(0 to 4) := (-3.0, -8.0, -11.0, -15.0, -25.0);
        variable data, rxd : iq_array(0 to OFDM_DATA_CARRIERS - 1);
        variable sym, rxs : iq_array(0 to OFDM_FFT_SIZE + OFDM_CP_LENGTH - 1);
        variable lam, path, rms : real;

        function trim(x : string) return string is
            variable n : natural := x'length;
        begin
            while n > 0 and x(x'low + n - 1) = ' ' loop
                n := n - 1;
            end loop;
            return x(x'low to x'low + n - 1);
        end function;
    begin
        -- band tables
        for i in BAND_F'range loop
            say("band_rx_gain_max_" & mhz(BAND_F(i)), ad9361_band(AD9361_T_RX_GAIN_MAX, BAND_F(i)));
            say("band_rx_nf_" & mhz(BAND_F(i)), ad9361_band(AD9361_T_RX_NF, BAND_F(i)));
            say("band_rx_iip3_" & mhz(BAND_F(i)), ad9361_band(AD9361_T_RX_IIP3, BAND_F(i)));
            say("band_tx_pmax_" & mhz(BAND_F(i)), ad9361_band(AD9361_T_TX_PMAX, BAND_F(i)));
            say("band_tx_oip3_" & mhz(BAND_F(i)), ad9361_band(AD9361_T_TX_OIP3, BAND_F(i)));
            say("band_tx_evm_" & mhz(BAND_F(i)), ad9361_band(AD9361_T_TX_EVM, BAND_F(i)));
            say("band_lo_pn_rms_" & mhz(BAND_F(i)), ad9361_band(AD9361_T_LO_PN_RMS, BAND_F(i)));
        end loop;

        -- noise-free transmit path
        for l in LOS'range loop
            for k in ATT'range loop
                cfg := cfg_at(LOS(l));
                cfg.tx_atten_db := ATT(k);
                for n in CODE_I'range loop
                    s := ad9361_tx_ideal(cfg, (i => CODE_I(n), q => CODE_Q(n)));
                    say("tx_" & mhz(LOS(l)) & "_" & trim(ATT_TAG(k)) & "_" & integer'image(n) & "_re", s.eh_re);
                    say("tx_" & mhz(LOS(l)) & "_" & trim(ATT_TAG(k)) & "_" & integer'image(n) & "_im", s.eh_im);
                end loop;
                say("txfs_" & mhz(LOS(l)) & "_" & trim(ATT_TAG(k)), ad9361_tx_full_scale_dbm(cfg));
            end loop;
        end loop;

        -- noise-free receive path: from far under to over full scale, at three gains
        for l in LOS'range loop
            for k in BACK'range loop
                cfg := cfg_at(LOS(l));
                cfg.rx_gain_db := ad9361_rx_gain_legal(LOS(l), ad9361_rx_gain_max(LOS(l)) - BACK(k));
                fsw := dbm_to_watts(ad9361_rx_full_scale_dbm(cfg));
                for n in REL'range loop
                    a := sqrt(fsw * 10.0 ** (REL(n) / 10.0));
                    s := (eh_re => a * cos(0.7), eh_im => a * sin(0.7), ev_re => 0.0, ev_im => 0.0, freq => LOS(l));
                    c := ad9361_rx_ideal(cfg, s);
                    say("rx_" & mhz(LOS(l)) & "_" & integer'image(integer(BACK(k))) & "_" & integer'image(n) & "_i", c.i);
                    say("rx_" & mhz(LOS(l)) & "_" & integer'image(integer(BACK(k))) & "_" & integer'image(n) & "_q", c.q);
                end loop;
            end loop;
        end loop;

        say("lo_actual_2437_1ppm", ad9361_lo_actual(2.437e9, 1.0));
        say("rx_gain_legal_2437_40p3", ad9361_rx_gain_legal(2.437e9, 40.3));
        say("rx_noise_floor_2437", ad9361_rx_noise_floor_dbm(cfg_at(2.437e9)));

        -- slow AGC decisions from 40 dB
        cfg := cfg_at(2.437e9);
        cfg.rx_gain_db := ad9361_rx_gain_legal(2.437e9, 40.0);
        for n in AGC_P'range loop
            say("agc_slow_" & integer'image(n), ad9361_agc_slow(cfg, AGC_P(n)));
        end loop;

        -- the chip's constants as the accelerator is given them, in two control states
        cfg := cfg_at(2.437e9);
        cfg.rx_rf_bw := 18.0e6;
        cfg.tx_rf_bw := 18.0e6;
        cfg.xo_ppm := 1.0;
        cfg.gain_mode := AGC_FAST_ATTACK;
        cfg.ensm := ENSM_TX;
        pv := ad9361_accel_params(cfg, 64);
        for i in pv'range loop
            say("accel_a_" & integer'image(i), pv(i));
        end loop;
        cfg := cfg_at(5.2e9);
        cfg.rx_rf_bw := 9.0e6;
        cfg.tx_rf_bw := 9.0e6;
        cfg.xo_ppm := -1.5;
        cfg.gain_mode := AGC_MANUAL;
        cfg.rx_gain_db := 40.0;
        cfg.tx_atten_db := 10.25;
        cfg.ensm := ENSM_FDD;
        pv := ad9361_accel_params(cfg, 64);
        for i in pv'range loop
            say("accel_b_" & integer'image(i), pv(i));
        end loop;

        -- Monte Carlo on the noisy procedures
        for l in LOS'range loop
            -- receiver noise figure: no input, maximum gain
            cfg := cfg_at(LOS(l));
            st := ad9361_init_state(100 + l);
            s := (0.0, 0.0, 0.0, 0.0, ad9361_lo_actual(cfg.rx_lo, 0.0));
            acc := 0.0;
            for n in 1 to N_MC loop
                ad9361_rx_sample(cfg, st, s, 0.0, c);
                acc := acc + c.i * c.i + c.q * c.q;
            end loop;
            a := acc / real(N_MC) / 2048.0 ** 2 * dbm_to_watts(AD9361_ADC_FS_AT_0DB) / 10.0 ** (cfg.rx_gain_db / 10.0);
            say("mc_rx_nf_" & mhz(LOS(l)), 10.0 * log10(a / (1.380649e-23 * 290.0 * cfg.sample_rate)));

            -- transmitter with nothing to send: carrier leakage (the mean) and noise (what is left)
            st := ad9361_init_state(200 + l);
            m_re := 0.0; m_im := 0.0; acc := 0.0;
            for n in 1 to N_MC loop
                ad9361_tx_sample(cfg, st, IQ_ZERO, s);
                m_re := m_re + s.eh_re;
                m_im := m_im + s.eh_im;
                acc := acc + s.eh_re * s.eh_re + s.eh_im * s.eh_im;
            end loop;
            m_re := m_re / real(N_MC);
            m_im := m_im / real(N_MC);
            say("mc_tx_leak_" & mhz(LOS(l)),
                10.0 * log10((m_re * m_re + m_im * m_im) / dbm_to_watts(ad9361_tx_full_scale_dbm(cfg))));
            say("mc_tx_noise_" & mhz(LOS(l)),
                watts_to_dbm((acc / real(N_MC) - (m_re * m_re + m_im * m_im)) / cfg.sample_rate));

            -- transmitter EVM: four-level words on each rail (multiples of 2048: exact in the DAC word)
            st := ad9361_init_state(300 + l);
            s2 := 0.0; y2 := 0.0; c_re := 0.0; c_im := 0.0; ys_re := 0.0; ys_im := 0.0; ss_re := 0.0; ss_im := 0.0;
            for n in 1 to N_MC loop
                uniform(seed1, seed2, u);
                w.i := (2.0 * floor(u * 4.0) - 3.0) * 2048.0;
                uniform(seed1, seed2, u);
                w.q := (2.0 * floor(u * 4.0) - 3.0) * 2048.0;
                ad9361_tx_sample(cfg, st, w, s);
                s2 := s2 + w.i * w.i + w.q * w.q;
                y2 := y2 + s.eh_re * s.eh_re + s.eh_im * s.eh_im;
                c_re := c_re + w.i * s.eh_re + w.q * s.eh_im;          -- conj(w) * y
                c_im := c_im + w.i * s.eh_im - w.q * s.eh_re;
                ys_re := ys_re + s.eh_re; ys_im := ys_im + s.eh_im;
                ss_re := ss_re + w.i; ss_im := ss_im + w.q;
            end loop;
            say("mc_tx_evm_" & mhz(LOS(l)), evm_db(real(N_MC), s2, y2, c_re, c_im, ys_re, ys_im, ss_re, ss_im));

            -- receiver EVM: the same kind of signal, 12 dB under full scale, gain 40 dB under maximum
            cfg.rx_gain_db := ad9361_rx_gain_legal(LOS(l), ad9361_rx_gain_max(LOS(l)) - 40.0);
            a := sqrt(dbm_to_watts(ad9361_rx_full_scale_dbm(cfg) - 12.0) / 10.0);
            st := ad9361_init_state(400 + l);
            s2 := 0.0; y2 := 0.0; c_re := 0.0; c_im := 0.0; ys_re := 0.0; ys_im := 0.0; ss_re := 0.0; ss_im := 0.0;
            for n in 1 to N_MC loop
                uniform(seed1, seed2, u);
                w.i := (2.0 * floor(u * 4.0) - 3.0) * a;
                uniform(seed1, seed2, u);
                w.q := (2.0 * floor(u * 4.0) - 3.0) * a;
                s := (eh_re => w.i, eh_im => w.q, ev_re => 0.0, ev_im => 0.0, freq => ad9361_lo_actual(cfg.rx_lo, 0.0));
                ad9361_rx_sample(cfg, st, s, 0.0, c);
                s2 := s2 + w.i * w.i + w.q * w.q;
                y2 := y2 + c.i * c.i + c.q * c.q;
                c_re := c_re + w.i * c.i + w.q * c.q;
                c_im := c_im + w.i * c.q - w.q * c.i;
                ys_re := ys_re + c.i; ys_im := ys_im + c.q;
                ss_re := ss_re + w.i; ss_im := ss_im + w.q;
            end loop;
            say("mc_rx_evm_" & mhz(LOS(l)), evm_db(real(N_MC), s2, y2, c_re, c_im, ys_re, ys_im, ss_re, ss_im));
        end loop;

        -- One OFDM symbol from rf.ofdm_pkg through transmitter, 10 m of free space (0 dBi) and receiver.
        -- The symbol is sent 12 dB under DAC full scale (rms); the receiver gain puts it 12 dB under ADC
        -- full scale.  EVM over the 48 data carriers after fitting one complex gain.
        cfg := cfg_at(2.437e9);
        for k in data'range loop
            uniform(seed1, seed2, u);
            data(k).i := (2.0 * floor(u * 2.0) - 1.0) / sqrt(2.0);
            uniform(seed1, seed2, u);
            data(k).q := (2.0 * floor(u * 2.0) - 1.0) / sqrt(2.0);
        end loop;
        sym := ofdm_modulate(data);
        rms := 0.0;
        for k in sym'range loop
            rms := rms + iq_power(sym(k));
        end loop;
        rms := sqrt(rms / real(sym'length));
        lam := SPEED_OF_LIGHT / cfg.tx_lo;
        path := lam / (4.0 * MATH_PI * 10.0);
        -- received power: packet power at the TX port times the path loss
        a := ad9361_tx_full_scale_dbm(cfg) - 12.0 + 20.0 * log10(path);
        cfg.rx_gain_db := ad9361_rx_gain_legal(cfg.rx_lo, AD9361_ADC_FS_AT_0DB - 12.0 - a);
        say("ofdm_prx_dbm", a);
        say("ofdm_rx_gain_db", cfg.rx_gain_db);
        st := ad9361_init_state(500);
        for k in sym'range loop
            w := (i => sym(k).i / rms * 32768.0 * 10.0 ** (-12.0 / 20.0), q => sym(k).q / rms * 32768.0 * 10.0 ** (-12.0 / 20.0));
            ad9361_tx_sample(cfg, st, w, s);
            s := scale_rf(s, path);
            ad9361_rx_sample(cfg, st, s, real(k) / cfg.sample_rate, rxs(k));
        end loop;
        rxd := ofdm_demodulate(rxs);
        s2 := 0.0; y2 := 0.0; c_re := 0.0; c_im := 0.0; ys_re := 0.0; ys_im := 0.0; ss_re := 0.0; ss_im := 0.0;
        for k in data'range loop
            s2 := s2 + iq_power(data(k));
            y2 := y2 + iq_power(rxd(k));
            c_re := c_re + data(k).i * rxd(k).i + data(k).q * rxd(k).q;
            c_im := c_im + data(k).i * rxd(k).q - data(k).q * rxd(k).i;
        end loop;
        -- gain fitted through the origin (48 points: no offset term)
        a := (c_re * c_re + c_im * c_im) / s2;                       -- |g|^2 * s2
        say("ofdm_evm_db", 10.0 * log10(realmax(y2 - a, 1.0e-300) / a));
        assert 10.0 * log10(realmax(y2 - a, 1.0e-300) / a) < -28.0
            report "OFDM symbol through the AD9361 pair: EVM worse than -28 dB" severity error;
        report "AD9361 done 1.0";
        wait;
    end process;
end architecture;
