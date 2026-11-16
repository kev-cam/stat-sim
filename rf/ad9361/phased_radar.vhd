-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- phased_radar: a phased-array radar in nvc's --std=2040 spectral event-driven mode.
--
-- n AD9361 channels on one LO, each with a transmit element (a line along y, half a wavelength apart) and
-- a receive element (the same line `sep` metres higher), three point targets in the arena, and the radar
-- itself as software: one process that, for each target in turn, focuses the transmit beam on the
-- target's cell, sends `pulses` OFDM pulses `pri` apart from every element (one spectral event per
-- element and pulse), forms the receive beam from the echoes, and finds the target's range (lines ->
-- delay), radial speed (pulse to pulse) and bearing (across the elements).  The targets move.
--
-- One report line per look:
--   RADAR target=<n> range=<m> bearing=<deg> speed=<m/s> margin_db=<peak over everything outside its main lobe>
--
-- Run through radar_nvc.py (it writes the resolver network and the wrapper, and sets the generics); with
-- --accel the chips, antennas and arena are processed on the spectral accelerator, one thread per line.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library rf;
use rf.rf_signal_pkg.all;
use rf.iq_pkg.all;
use work.rf_spectrum_pkg.all;
use work.ad9361_pkg.all;
use work.ad9361_spectral_pkg.all;
use work.ofdm_soft_pkg.all;

entity phased_radar is
    generic (
        n          : positive := 8;         -- elements per array
        lo         : real := 2.437e9;       -- carrier, Hz
        fs         : real := 20.0e6;        -- sample rate = pulse bandwidth, Hz
        ant_dbi    : real := 2.0;           -- gain of every element
        sep        : real := 3.0;           -- height of the receive array over the transmit array, m
        isolate    : boolean := false;      -- the two arrays are one platform: they do not hear each other directly
        pri        : real := 100.0e-6;      -- pulse repetition interval, s
        pulses     : positive := 64;        -- per look
        looks      : positive := 3;         -- one target after the other, round and round
        backoff_db : real := 12.0;          -- pulse rms under DAC full scale
        blank      : real := 45.0;          -- shortest range searched, m
        -- the targets: range m and bearing deg (from broadside, in the x-y plane) at time 0, radar
        -- cross-section m2, radial speed m/s (positive: receding)
        r0 : real := 120.0; b0 : real := 12.0;  c0 : real := 10.0;  v0 : real := -40.0;
        r1 : real := 210.0; b1 : real := -25.0; c1 : real := 30.0;  v1 : real := 75.0;
        r2 : real := 160.0; b2 : real := 45.0;  c2 : real := 100.0; v2 : real := 120.0
    );
end entity;

architecture sim of phased_radar is
    constant LAMBDA : real := SPEED_OF_LIGHT / lo;
    constant T_PRI : time := pri * 1 sec;
    constant OS : positive := 4;                              -- range cells per sample of delay
    constant NR : positive := SPEC_N * OS;
    type frame_vector is array (natural range <>) of ad9361_frame;
    type target_t is record
        r, b, c, v : real;
    end record;
    type target_vector is array (0 to 2) of target_t;
    constant TARGETS : target_vector := ((r0, b0, c0, v0), (r1, b1, c1, v1), (r2, b2, c2, v2));

    function platform_of(iso : boolean) return natural is
    begin
        if iso then
            return 1;
        end if;
        return 0;
    end function;

    function element_y(i : natural) return real is
    begin
        return (real(i) - real(n - 1) / 2.0) * LAMBDA / 2.0;
    end function;

    function array_positions(z : real) return rf_position_vector is
        variable p : rf_position_vector(0 to n - 1);
    begin
        for i in p'range loop
            p(i) := (0.0, element_y(i), z);
        end loop;
        return p;
    end function;

    function target_position(t : target_t; at : real) return rf_position is
        constant rr : real := t.r + t.v * at;
        constant b  : real := t.b * MATH_PI / 180.0;
    begin
        return (rr * cos(b), rr * sin(b), sep / 2.0);
    end function;

    function target_positions(at : real) return rf_position_vector is
        variable p : rf_position_vector(0 to 2);
    begin
        for s in p'range loop
            p(s) := target_position(TARGETS(s), at);
        end loop;
        return p;
    end function;

    function radar_cfg return ad9361_config is
        variable c : ad9361_config := ad9361_default_config;
    begin
        c.rx_lo := lo;
        c.tx_lo := lo;
        c.sample_rate := fs;
        c.rx_rf_bw := 0.9 * fs;
        c.tx_rf_bw := 0.9 * fs;
        c.gain_mode := AGC_FAST_ATTACK;
        c.tx_atten_db := 0.0;
        c.xo_ppm := 0.0;
        c.ensm := ENSM_FDD;
        return c;
    end function;

    signal n_tx, n_rx : std_logic_vector(0 to n - 1);
    signal air : std_logic;
    signal cfg : ad9361_config := radar_cfg;
    signal tx, rx : frame_vector(0 to n - 1) := (others => AD9361_NO_FRAME);
    signal gain : real_vector(0 to n - 1) := (others => 0.0);
    signal tx_pos : rf_position_vector(0 to n - 1) := array_positions(0.0);
    signal rx_pos : rf_position_vector(0 to n - 1) := array_positions(sep);
    signal tgt_pos : rf_position_vector(0 to 2) := target_positions(0.0);
begin
    g: for i in 0 to n - 1 generate
        chip: entity work.ad9361
            generic map (seed => 100 + i)
            port map (tx1 => n_tx(i), rx1 => n_rx(i), cfg => cfg, tx_data => tx(i), rx_data => rx(i), rx_gain_db => gain(i));
        ant_tx: entity work.rf_spec_antenna
            generic map (gain_dbi => ant_dbi, platform => platform_of(isolate))
            port map (feed => n_tx(i), air => air, position => tx_pos(i));
        ant_rx: entity work.rf_spec_antenna
            generic map (gain_dbi => ant_dbi, platform => platform_of(isolate))
            port map (feed => n_rx(i), air => air, position => rx_pos(i));
    end generate;

    tgt0: entity work.rf_spec_scatterer generic map (rcs_m2 => c0) port map (position => tgt_pos(0));
    tgt1: entity work.rf_spec_scatterer generic map (rcs_m2 => c1) port map (position => tgt_pos(1));
    tgt2: entity work.rf_spec_scatterer generic map (rcs_m2 => c2) port map (position => tgt_pos(2));

    -- The radar's software.
    radar_sw: process
        constant amp : real := 32768.0 * 10.0 ** (-backoff_db / 20.0);
        constant sym : spec_lines := soft_ltf;                -- the pulse: 52 lines of +-1
        type look_t is array (0 to pulses - 1, 0 to n - 1) of spec_lines;
        type pulse_lines is array (0 to pulses - 1) of spec_lines;
        type range_row is array (0 to NR - 1) of iq_sample;
        type range_rows is array (0 to pulses - 1) of range_row;
        type map_t is array (0 to pulses - 1, 0 to NR - 1) of real;
        variable h : look_t;                                  -- echoes, per pulse and element, over the pulse and the gain
        variable y : pulse_lines;
        variable rows : range_rows;
        variable power : map_t;
        variable w, wscan : iq_array(0 to n - 1);             -- element weights of the look, and of the bearing scan
        variable frames : frame_vector(0 to n - 1);
        variable seqno : natural := 0;
        variable gl, best, rest, found_range, found_speed, found_bearing, v, pr, pq : real;
        variable acc, e : iq_sample;
        variable pb, nb, near, kk, db, ti : integer;
        variable cr, sr : real_vector(0 to NR - 1);           -- exp(j 2 pi n / NR)
        variable cd, sd : real_vector(0 to pulses - 1);       -- exp(j 2 pi p / pulses)
        variable win : real_vector(0 to pulses - 1);          -- pulse to pulse: Blackman
        variable wr : real_vector(0 to SPEC_N - 1);           -- across the lines: raised cosine over the used ones
        variable gcell : iq_array(0 to n - 1);
        variable cal : spec_lines;                            -- 1 / (the chips' baseband filters), line by line

        function koff(k : natural) return integer is
        begin
            if k < SPEC_N / 2 then
                return k;
            end if;
            return k - SPEC_N;
        end function;

        -- Element weights that focus the array on a point at a range and bearing: each element's own
        -- distance to it.  (A long array is in its own near field out to 2 D^2 / lambda -- 4 km for 256
        -- elements here -- so pointing with a plane wave's weights would blur.)
        function steer(bearing_deg : real; range_m : real) return iq_array is
            constant b : real := bearing_deg * MATH_PI / 180.0;
            variable r : iq_array(0 to n - 1);
            variable d, a : real;
        begin
            for i in r'range loop
                d := sqrt((range_m * cos(b)) ** 2 + (range_m * sin(b) - element_y(i)) ** 2 + (sep / 2.0) ** 2);
                a := 2.0 * MATH_PI * ((lo * (d - range_m) / SPEED_OF_LIGHT) mod 1.0);
                r(i) := (cos(a), sin(a));
            end loop;
            return r;
        end function;
    begin
        for i in cr'range loop
            cr(i) := cos(2.0 * MATH_PI * real(i) / real(NR));
            sr(i) := sin(2.0 * MATH_PI * real(i) / real(NR));
        end loop;
        for p in cd'range loop
            cd(p) := cos(2.0 * MATH_PI * real(p) / real(pulses));
            sd(p) := sin(2.0 * MATH_PI * real(p) / real(pulses));
            win(p) := 0.42 - 0.5 * cos(2.0 * MATH_PI * real(p + 1) / real(pulses + 1))
                      + 0.08 * cos(4.0 * MATH_PI * real(p + 1) / real(pulses + 1));
        end loop;
        for k in wr'range loop
            wr(k) := 0.0;
            if sym(k).i /= 0.0 then
                wr(k) := 0.5 + 0.5 * cos(2.0 * MATH_PI * real(koff(k)) / 54.0);
            end if;
        end loop;
        -- what the radar knows about its own hardware: the two baseband filters every echo went through
        -- (they delay it by some tens of ns, metres of range); the echoes are divided by them
        for k in cal'range loop
            e := iq_mul(ad9361_bb_response(false, cfg.tx_rf_bw, real(koff(k)) * fs / real(SPEC_N)),
                        ad9361_bb_response(true, cfg.rx_rf_bw, real(koff(k)) * fs / real(SPEC_N)));
            cal(k) := (e.i / (e.i * e.i + e.q * e.q), -e.q / (e.i * e.i + e.q * e.q));
        end loop;
        near := integer(blank * 2.0 * fs * real(OS) / SPEED_OF_LIGHT);
        wait for T_PRI;

        for look in 0 to looks - 1 loop
            ti := look mod 3;
            w := steer(TARGETS(ti).b, TARGETS(ti).r);
            for i in 0 to n - 1 loop
                for k in sym'range loop
                    frames(i).lines(k) := iq_scale(iq_mul(sym(k), w(i)), amp);
                end loop;
            end loop;
            -- the look: pulses out, echoes in
            for p in 0 to pulses - 1 loop
                tgt_pos <= target_positions(sim_time);
                seqno := seqno + 1;
                for i in 0 to n - 1 loop
                    frames(i).seq := seqno;
                    tx(i) <= frames(i);
                end loop;
                wait for T_PRI / 2;
                for i in 0 to n - 1 loop
                    gl := 10.0 ** (-gain(i) / 20.0);
                    for k in sym'range loop
                        if sym(k).i /= 0.0 then
                            h(p, i)(k) := iq_scale(iq_mul(rx(i).lines(k), cal(k)), gl / sym(k).i);
                        else
                            h(p, i)(k) := IQ_ZERO;
                        end if;
                    end loop;
                end loop;
                wait for T_PRI - T_PRI / 2;
            end loop;

            -- receive beam at the look's bearing, line by line
            for p in 0 to pulses - 1 loop
                for k in sym'range loop
                    acc := IQ_ZERO;
                    if wr(k) /= 0.0 then
                        for i in 0 to n - 1 loop
                            acc := iq_add(acc, iq_mul(h(p, i)(k), w(i)));
                        end loop;
                    end if;
                    y(p)(k) := iq_scale(acc, wr(k));
                end loop;
            end loop;
            -- range: lines -> delay
            for p in 0 to pulses - 1 loop
                for nn in 0 to NR - 1 loop
                    pr := 0.0;
                    pq := 0.0;
                    for k in sym'range loop
                        if wr(k) /= 0.0 then
                            kk := (koff(k) * nn) mod NR;
                            pr := pr + y(p)(k).i * cr(kk) - y(p)(k).q * sr(kk);
                            pq := pq + y(p)(k).i * sr(kk) + y(p)(k).q * cr(kk);
                        end if;
                    end loop;
                    rows(p)(nn) := (pr * win(p), pq * win(p));
                end loop;
            end loop;
            -- Doppler: pulse to pulse, per range cell
            for b in 0 to pulses - 1 loop
                for nn in 0 to NR - 1 loop
                    pr := 0.0;
                    pq := 0.0;
                    for p in 0 to pulses - 1 loop
                        kk := (p * b) mod pulses;
                        pr := pr + rows(p)(nn).i * cd(kk) + rows(p)(nn).q * sd(kk);
                        pq := pq - rows(p)(nn).i * sd(kk) + rows(p)(nn).q * cd(kk);
                    end loop;
                    power(b, nn) := pr * pr + pq * pq;
                end loop;
            end loop;
            -- The direct path between the arrays does not move; it is left out of the search (the slowest
            -- Doppler cells), with the short ranges its phase noise reaches.
            best := -1.0;
            pb := 3;
            nb := near;
            for b in 3 to pulses - 3 loop
                for nn in near to NR - near - 1 loop
                    if power(b, nn) > best then
                        best := power(b, nn);
                        pb := b;
                        nb := nn;
                    end if;
                end loop;
            end loop;
            rest := 0.0;
            for b in 3 to pulses - 3 loop
                for nn in near to NR - near - 1 loop
                    db := abs(b - pb);
                    if (db > 4 and db < pulses - 4) or abs(nn - nb) > 4 * OS then
                        rest := realmax(rest, power(b, nn));
                    end if;
                end loop;
            end loop;
            found_range := SPEED_OF_LIGHT * real(nb) / (2.0 * fs * real(OS));
            if pb < pulses / 2 then
                found_speed := -real(pb) / (real(pulses) * pri) * LAMBDA / 2.0;
            else
                found_speed := -real(pb - pulses) / (real(pulses) * pri) * LAMBDA / 2.0;
            end if;
            -- bearing: the peak's cell at each element, then the angle that lines the elements up
            for i in 0 to n - 1 loop
                acc := IQ_ZERO;
                for p in 0 to pulses - 1 loop
                    pr := 0.0;
                    pq := 0.0;
                    for k in sym'range loop
                        if wr(k) /= 0.0 then
                            kk := (koff(k) * nb) mod NR;
                            pr := pr + wr(k) * (h(p, i)(k).i * cr(kk) - h(p, i)(k).q * sr(kk));
                            pq := pq + wr(k) * (h(p, i)(k).i * sr(kk) + h(p, i)(k).q * cr(kk));
                        end if;
                    end loop;
                    kk := (p * pb) mod pulses;
                    acc := iq_add(acc, (win(p) * (pr * cd(kk) + pq * sd(kk)), win(p) * (-pr * sd(kk) + pq * cd(kk))));
                end loop;
                gcell(i) := acc;
            end loop;
            v := -1.0;
            found_bearing := 0.0;
            for a in -600 to 600 loop
                acc := IQ_ZERO;
                wscan := steer(real(a) * 0.1, found_range);
                for i in 0 to n - 1 loop
                    acc := iq_add(acc, iq_mul(gcell(i), wscan(i)));
                end loop;
                if acc.i * acc.i + acc.q * acc.q > v then
                    v := acc.i * acc.i + acc.q * acc.q;
                    found_bearing := real(a) * 0.1;
                end if;
            end loop;
            report "RADAR target=" & integer'image(ti) & " range=" & to_string(found_range, "%.2f")
                & " bearing=" & to_string(found_bearing, "%.2f") & " speed=" & to_string(found_speed, "%.2f")
                & " margin_db=" & to_string(10.0 * log10(best / realmax(rest, 1.0e-300)), "%.2f")
                & " look_end=" & to_string(sim_time, "%.9f");
        end loop;
        report "RADAR done";
        wait;
    end process;
end architecture;
