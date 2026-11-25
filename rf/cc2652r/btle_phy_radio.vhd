-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- btle_phy_radio: an open Bluetooth LE baseband as a radio in the arena, with the ports of entity
-- cc2652r, so that the same link layer (ble_controller) drives it and the same tester (ble_tester)
-- tests it.
--
-- The baseband is btle_phy of github.com/JiaoXianjun/BTLE (Verilog, Apache-2.0; not part of stat-sim),
-- translated to VHDL by sv2ghdl (iverilog -tvhdl over nvc's sv2vhdl library): LE 1M only, a GFSK
-- modulator that puts out 8-bit I/Q at 8 samples a symbol, and a receiver that takes 16-bit I/Q at the
-- same rate, searches for the access address and decodes in eight sampling phases.  It has no RF part;
-- this entity is the rest of a radio around it:
--
--   sending    the baseband's samples, interpolated to CC_FS (linearly, by 4) and scaled to the power
--              asked for, go to the pin as spectral events of 64 samples, as the CC2652R's do
--   receiving  the pin's events, with the receiver's carrier error and thermal noise (nf_db), go
--              through a channel filter (rx_bw), are decimated by 4 and scaled by an ideal AGC to the
--              baseband's input
--   clock      16 MHz, running only while a packet is sent or the receiver has a signal at the pin
--              (as the CC2652R model's receiver sleeps until something arrives); the baseband is reset
--              when the clock starts.  Its host clock (clkb: the PDU memories) is pulsed as needed.
--
-- All of the radio process's waits are in its body, none in a procedure: nvc (1.19-devel r626) loses
-- the state of a procedure suspended in a wait once its code is compiled.  It also needs that nvc's
-- waits (30bf1386c): a `wait for` here must not be cut short by the signals the idle wait names.
--
-- The time between a packet handed over on tx and its first sample at the pin is BTLE_TX_DELAY
-- (the baseband's pipeline and one event); a link layer that keeps T_IFS hands the packet over that
-- much early (ble_controller: radio_tx_delay).
--
-- The baseband's modulator stops a symbol early: its Gaussian filter delays the waveform by one symbol
-- (8 samples) and it puts out exactly 8 samples a bit, so the last bit of the CRC is not sent (no
-- phase advance is left in the last symbol; its own receiver decides on what leaks of it into the
-- symbol before).  That is how it is sent here.  With tx_tail the front end completes the packet: 8
-- more samples that turn the way of the last bit (tx_phy_bit), which is what the modulator would
-- send if it ran its filter out.
--
-- Not there in the baseband, so not here: LE 2M and Coded, unwhitened packets (cfg.whiten < 0).  A
-- packet whose CRC fails comes out of the baseband without a length: it is handed on as two octets,
-- its end taken as when the baseband gave up.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library rf;
use rf.iq_pkg.all;
library sv2vhdl;
use sv2vhdl.logic3d_types_pkg.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;
use work.cc2652r_spectral_pkg.all;
use work.btle_phy_radio_pkg.all;

entity btle_phy_radio is
    generic (
        seed  : positive := 1;
        nf_db : real := 6.0;                -- noise figure of the front end
        rx_bw : real := 1.0e6;              -- cutoff of the channel filter, Hz from the carrier
        -- the receiver's latency: from the end of the access address at the pin to the baseband's hit
        rx_hit_delay : time := 1625 ns;
        start_parity : natural := 0;        -- clock (after reset) on which tx_start is given, modulo 2
        tx_tail : boolean := false;         -- complete the last symbol, which the modulator cuts off
        debug : boolean := false
    );
    port (
        ant     : inout std_logic;
        cfg     : in cc2652r_config;
        tx      : in cc2652r_packet;
        tx_busy : out boolean;
        rx      : out cc2652r_packet
    );
end entity;

architecture wrapped of btle_phy_radio is
    constant HALF : time := 31250 ps;       -- of the 16 MHz clock
    constant NT : positive := 33;           -- taps of the channel filter
    constant TARGET : real := 4000.0;       -- RMS at the baseband's input, of 32768
    constant FLUSH : positive := 8;         -- silent events after which the receiver sleeps

    function l3v(n : integer; w : positive) return logic3d_vector is
        variable r : logic3d_vector(w - 1 downto 0);
        variable v : integer := n;
    begin
        for i in 0 to w - 1 loop
            if v mod 2 = 1 then
                r(i) := L3D_1;
            else
                r(i) := L3D_0;
            end if;
            v := (v - v mod 2) / 2;
        end loop;
        return r;
    end function;

    function int_of(v : logic3d_vector; signed : boolean := false) return integer is
        alias a : logic3d_vector(v'length - 1 downto 0) is v;
        variable r : integer := 0;
    begin
        for i in a'high downto 0 loop
            r := r * 2;
            if is_one(a(i)) then
                r := r + 1;
            end if;
        end loop;
        if signed and is_one(a(a'high)) then
            r := r - 2 ** a'length;
        end if;
        return r;
    end function;

    -- the baseband takes the access address as a number whose least significant bit goes first
    function aa_of(b : bit_vector(0 to 31)) return logic3d_vector is
        variable r : logic3d_vector(31 downto 0);
    begin
        for i in 0 to 31 loop
            if b(i) = '1' then
                r(i) := L3D_1;
            else
                r(i) := L3D_0;
            end if;
        end loop;
        return r;
    end function;

    -- ... and the CRC's initial value with its first and third octets exchanged (crc24_core.v)
    function crc_of(init : natural) return logic3d_vector is
    begin
        return l3v((init mod 256) * 65536 + ((init / 256) mod 256) * 256 + init / 65536, 24);
    end function;

    type real_taps is array (0 to NT - 1) of real;
    function channel_filter return real_taps is
        constant M : real := real(NT - 1) / 2.0;
        constant W : real := 2.0 * rx_bw / CC_FS;
        variable h : real_taps;
        variable x, sum : real := 0.0;
    begin
        for n in h'range loop
            x := MATH_PI * W * (real(n) - M);
            if abs x < 1.0e-9 then
                h(n) := W;
            else
                h(n) := W * sin(x) / x;
            end if;
            h(n) := h(n) * (0.54 - 0.46 * cos(2.0 * MATH_PI * real(n) / real(NT - 1)));
            sum := sum + h(n);
        end loop;
        for n in h'range loop
            h(n) := h(n) / sum;
        end loop;
        return h;
    end function;
    constant FIR : real_taps := channel_filter;

    -- the taps of the modulator's Gaussian filter (BT 0.5 over two symbols, as the project's btlelib.py
    -- makes them): the first nine, the rest mirror them
    type int_taps is array (0 to 8) of integer;
    function gauss_taps_of return int_taps is
        constant SIGMA : real := sqrt(log(2.0)) / (2.0 * MATH_PI * 0.5);
        variable r : int_taps;
        variable t : real;
    begin
        for k in r'range loop
            t := real(k - 8) / 8.0;
            r(k) := integer(round(128.0 / 8.0 * exp(-t * t / (2.0 * SIGMA * SIGMA)) / (SIGMA * sqrt(2.0 * MATH_PI))));
        end loop;
        return r;
    end function;
    constant GAUSS_TAPS : int_taps := gauss_taps_of;

    signal sending : boolean := false;
    signal pin_in, pin_out : rf_spectrum := spec_silent(1);

    -- the baseband's pins
    signal clk, clkb, rst : logic3d := L3D_0;
    signal tap_i : logic3d_vector(3 downto 0) := (others => L3D_0);
    signal tap_v : logic3d_vector(15 downto 0) := (others => L3D_0);
    signal tab_a : logic3d_vector(10 downto 0) := (others => L3D_0);
    signal cos_d, sin_d : logic3d_vector(7 downto 0) := (others => L3D_0);
    signal preamble : logic3d_vector(7 downto 0) := l3v(16#AA#, 8);
    signal tx_aa, rx_aa : logic3d_vector(31 downto 0) := aa_of(BLE_ADV_AA);
    signal tx_crc, rx_crc : logic3d_vector(23 downto 0) := crc_of(BLE_CRC_INIT_ADV);
    signal tx_chan, rx_chan : logic3d_vector(5 downto 0) := l3v(37, 6);
    signal tx_start, zero : logic3d := L3D_0;
    signal tx_d : logic3d_vector(7 downto 0) := (others => L3D_0);
    signal tx_a, rx_a : logic3d_vector(8 downto 0) := (others => L3D_0);
    signal tx_i, tx_q : logic3d_vector(7 downto 0);
    signal tx_v, tx_last, phy_b, phy_v : logic3d;
    signal rx_i, rx_q : logic3d_vector(15 downto 0) := (others => L3D_0);
    signal rx_v : logic3d := L3D_0;
    signal hit, run, done, ok : logic3d;
    signal phase : logic3d_vector(2 downto 0);
    signal len, rx_d : logic3d_vector(7 downto 0);
begin
    pin_watch: process (ant'other)
        variable s : rf_spectrum;
    begin
        s := ant'other;
        pin_in <= s;
    end process;

    -- (ant'driver cannot be assigned in a subprogram)
    pin_drive: process (pin_out)
        variable s : rf_spectrum;
    begin
        s := pin_out;
        ant'driver := s;
    end process;

    tx_busy <= sending;

    baseband: entity work.btle_phy
        port map (clk => clk, rst => rst, clkb => clkb,
                  tx_gauss_filter_tap_index => tap_i, tx_gauss_filter_tap_value => tap_v,
                  tx_cos_table_write_address => tab_a, tx_cos_table_write_data => cos_d,
                  tx_sin_table_write_address => tab_a, tx_sin_table_write_data => sin_d,
                  tx_preamble => preamble, tx_access_address => tx_aa, tx_crc_state_init_bit => tx_crc,
                  tx_crc_state_init_bit_load => zero, tx_channel_number => tx_chan, tx_channel_number_load => zero,
                  tx_pdu_octet_mem_data => tx_d, tx_pdu_octet_mem_addr => tx_a, tx_start => tx_start,
                  tx_i_signal => tx_i, tx_q_signal => tx_q, tx_iq_valid => tx_v, tx_iq_valid_last => tx_last,
                  tx_phy_bit => phy_b, tx_phy_bit_valid => phy_v, tx_phy_bit_valid_last => open,
                  tx_bit_upsample => open, tx_bit_upsample_valid => open, tx_bit_upsample_valid_last => open,
                  tx_bit_upsample_gauss_filter => open, tx_bit_upsample_gauss_filter_valid => open,
                  tx_bit_upsample_gauss_filter_valid_last => open,
                  rx_unique_bit_sequence => rx_aa, rx_channel_number => rx_chan, rx_crc_state_init_bit => rx_crc,
                  rx_i_signal => rx_i, rx_q_signal => rx_q, rx_iq_valid => rx_v,
                  rx_hit_flag => hit, rx_decode_run => run, rx_decode_end => done, rx_crc_ok => ok,
                  rx_best_phase => phase, rx_payload_length => len,
                  rx_pdu_octet_mem_addr => rx_a, rx_pdu_octet_mem_data => rx_d);

    radio: process
        constant SGM : real := sqrt(CC_K_BOLTZ * CC_T0 * 10.0 ** (nf_db / 10.0) * CC_FS / 2.0);
        variable s1, s2 : positive := seed;
        variable nclk : natural := 0;                       -- clocks since the baseband's reset
        variable last_seq, out_seq, pin_seq : natural := 0;
        variable c : cc2652r_config;
        variable p : cc2652r_packet;
        variable t_ev, t_hit : time;
        variable stop : boolean;
        -- sending
        variable t : spec_lines := (others => IQ_ZERO);
        variable prev, cur : iq_sample := IQ_ZERO;
        variable n, ns, nc, limit, tail : natural := 0;
        variable last_bit : boolean;
        variable turn : real;
        variable amp, doff, off : real := 0.0;
        -- receiving
        variable sig : rf_spectrum;
        variable dl : iq_array(0 to NT - 1) := (others => IQ_ZERO);
        variable dpos, quiet, plen : natural := 0;
        variable dec : iq_array(0 to SPEC_N / 4 - 1);
        variable rxph, drx, pw, gain, pw_hit : real := 0.0;

        procedure gauss(g1, g2 : out real) is
            variable u1, u2, r : real;
        begin
            uniform(s1, s2, u1);
            uniform(s1, s2, u2);
            r := sqrt(-2.0 * log(realmax(u1, 1.0e-300)));
            g1 := r * cos(2.0 * MATH_PI * u2);
            g2 := r * sin(2.0 * MATH_PI * u2);
        end procedure;

        impure function tx_pending return boolean is
        begin
            return tx.seq /= last_seq and tx.seq /= 0 and tx.len >= 2;
        end function;

        -- a sample of the baseband (8 Msps) as four at the pin
        procedure interpolate is
            variable a, cs, sn, re, im : real;
        begin
            for j in 1 to 4 loop
                a := real(j) / 4.0;
                re := prev.i + (cur.i - prev.i) * a;
                im := prev.q + (cur.q - prev.q) * a;
                cs := cos(off);
                sn := sin(off);
                t(n) := (amp * (re * cs - im * sn), amp * (re * sn + im * cs));
                n := n + 1;
                off := off + doff;
                if off > MATH_PI then
                    off := off - 2.0 * MATH_PI;
                elsif off < -MATH_PI then
                    off := off + 2.0 * MATH_PI;
                end if;
            end loop;
            prev := cur;
        end procedure;

        -- the event gathered in t, to the pin
        procedure emit is
        begin
            pin_seq := pin_seq + 1;
            pin_out <= (h => time_to_lines(t), v => LINES_ZERO, freq => c.frequency, df => CC_FS / real(SPEC_N), seq => pin_seq);
            t := (others => IQ_ZERO);
            n := 0;
            t_ev := now;
        end procedure;

        -- front end: one event of the pin (sig) with the receiver's carrier error and noise, through
        -- the channel filter, decimated and scaled: dec.  pw: the signal's power in this event, W.
        procedure front_end is
            variable r : rf_spectrum;
            variable x : spec_lines := LINES_ZERO;
            variable pwf, g1, g2, cs, sn, re, im : real := 0.0;
            variable y : iq_sample;
            variable j : natural;
        begin
            pw := 0.0;
            if spec_is_silent(sig) then
                quiet := quiet + 1;
            else
                quiet := 0;
                r := spec_regrid(sig, c.frequency, 0.0);
                if not spec_is_silent(r) then
                    x := lines_to_time(r.h);
                end if;
            end if;
            for i in x'range loop
                pw := pw + x(i).i * x(i).i + x(i).q * x(i).q;
                cs := cos(rxph);
                sn := sin(rxph);
                gauss(g1, g2);
                re := x(i).i * cs - x(i).q * sn + g1 * SGM;
                im := x(i).i * sn + x(i).q * cs + g2 * SGM;
                rxph := rxph + drx;
                if rxph > MATH_PI then
                    rxph := rxph - 2.0 * MATH_PI;
                elsif rxph < -MATH_PI then
                    rxph := rxph + 2.0 * MATH_PI;
                end if;
                dpos := (dpos + 1) mod NT;
                dl(dpos) := (re, im);
                if i mod 4 = 3 then
                    y := IQ_ZERO;
                    j := dpos;
                    for k in 0 to NT - 1 loop
                        y.i := y.i + FIR(k) * dl(j).i;
                        y.q := y.q + FIR(k) * dl(j).q;
                        if j = 0 then
                            j := NT - 1;
                        else
                            j := j - 1;
                        end if;
                    end loop;
                    dec(i / 4) := y;
                    pwf := pwf + y.i * y.i + y.q * y.q;
                end if;
            end loop;
            pw := pw / real(SPEC_N);
            gain := TARGET / sqrt(realmax(pwf / real(dec'length), 1.0e-30));
        end procedure;

        function clip16(x : real) return integer is
        begin
            return integer(realmax(realmin(round(x), 32767.0), -32768.0));
        end function;
    begin
        -- the modulator's oscillator: one turn in 2048 steps
        for k in 0 to 2047 loop
            tab_a <= l3v(k, 11);
            cos_d <= l3v(integer(round(127.0 * cos(2.0 * MATH_PI * real(k) / 2048.0))), 8);
            sin_d <= l3v(integer(round(127.0 * sin(2.0 * MATH_PI * real(k) / 2048.0))), 8);
            wait for 1 ps; clk <= L3D_1; wait for 1 ps; clk <= L3D_0;
        end loop;

        loop
            if not tx_pending then
                wait on tx, pin_in, cfg;
            end if;
            stop := true;
            if tx_pending then
                stop := false;
            elsif cfg.rx_on and pin_in'event and not spec_is_silent(pin_in) and cfg.phy = PHY_1M and cfg.whiten >= 0 then
                stop := false;
            end if;

            if not stop then
                c := cfg;
                assert c.phy = PHY_1M and c.whiten >= 0
                    report "btle_phy_radio: the baseband sends LE 1M, whitened, only" severity failure;
                if tx_pending then
                    p := tx;
                    last_seq := p.seq;
                    sending <= true;
                    if c.access_address(0) = '1' then
                        preamble <= l3v(16#55#, 8);
                    else
                        preamble <= l3v(16#AA#, 8);
                    end if;
                    tx_aa <= aa_of(c.access_address);
                    tx_crc <= crc_of(c.crc_init);
                    tx_chan <= l3v(c.whiten, 6);
                    for k in 0 to p.len - 1 loop
                        tx_a <= l3v(k, 9);
                        tx_d <= l3v(p.pdu(k), 8);
                        wait for 1 ps; clkb <= L3D_1; wait for 1 ps; clkb <= L3D_0;
                    end loop;
                    stop := true;                           -- (here: a packet is to be sent)
                else
                    rx_aa <= aa_of(c.access_address);
                    rx_crc <= crc_of(c.crc_init);
                    rx_chan <= l3v(c.whiten, 6);
                end if;
                -- reset, and the taps of the modulator's Gaussian filter
                for k in -2 to 8 loop
                    if k < 0 then
                        rst <= L3D_1;
                    else
                        rst <= L3D_0;
                        tap_i <= l3v(k, 4);
                        tap_v <= l3v(GAUSS_TAPS(k), 16);
                    end if;
                    wait for 1 ps; clk <= L3D_1; wait for 1 ps; clk <= L3D_0;
                end loop;
                nclk := 0;

                if stop then
                    amp := sqrt(cc_dbm_w(c.tx_power)) / 127.0;
                    doff := 2.0 * MATH_PI * c.frequency * c.xo_ppm * 1.0e-6 / CC_FS;
                    limit := (p.len + 16) * 8 * 16;
                    prev := IQ_ZERO;
                    t := (others => IQ_ZERO);
                    n := 0;
                    ns := 0;
                    nc := 0;
                    tail := 0;
                    if nclk mod 2 /= start_parity then
                        wait for 1 ps; clk <= L3D_1; wait for 1 ps; clk <= L3D_0;
                        nclk := nclk + 1;
                    end if;
                    tx_start <= L3D_1;
                    wait for HALF; clk <= L3D_1; wait for HALF; clk <= L3D_0;
                    tx_start <= L3D_0;
                    loop
                        wait for HALF; clk <= L3D_1; wait for HALF; clk <= L3D_0;
                        nc := nc + 1;
                        if is_one(phy_v) then
                            last_bit := is_one(phy_b);
                        end if;
                        if tail > 0 then                    -- the symbol the modulator cuts off
                            if tail mod 2 = 0 then
                                turn := MATH_PI / 16.0;
                                if not last_bit then
                                    turn := -turn;
                                end if;
                                cur := (prev.i * cos(turn) - prev.q * sin(turn), prev.i * sin(turn) + prev.q * cos(turn));
                                interpolate;
                                ns := ns + 1;
                                if n = SPEC_N then
                                    emit;
                                end if;
                            end if;
                            tail := tail - 1;
                            exit when tail = 0;
                        elsif is_one(tx_v) then
                            cur := (real(int_of(tx_i, true)), real(int_of(tx_q, true)));
                            interpolate;
                            ns := ns + 1;
                            if n = SPEC_N then
                                emit;
                            end if;
                            if is_one(tx_last) then
                                exit when not tx_tail;
                                tail := 16;
                            end if;
                        end if;
                        if nc > limit then
                            report "btle_phy_radio: the baseband did not finish a packet of " & integer'image(p.len) & " octets" severity warning;
                            exit;
                        end if;
                    end loop;
                    if debug then
                        report "btle_phy_radio: sent " & integer'image(p.len) & " octets, " & integer'image(ns) & " samples";
                    end if;
                    if n > 0 then                           -- the last, part-filled event
                        wait for t_ev + CC_T_EVENT - now;
                        emit;
                    end if;
                    wait for t_ev + CC_T_EVENT - now;
                    pin_seq := pin_seq + 1;
                    pin_out <= spec_silent(pin_seq);
                    sending <= false;
                else
                    if debug then
                        report "btle_phy_radio: receiver wakes";
                    end if;
                    drx := -2.0 * MATH_PI * c.frequency * c.xo_ppm * 1.0e-6 / CC_FS;
                    dl := (others => IQ_ZERO);
                    quiet := 0;
                    t_ev := now + CC_T_EVENT / 2;
                    wait for t_ev - now;
                    loop
                        sig := pin_in;
                        front_end;
                        -- the baseband: a sample every other clock
                        for k in dec'range loop
                            rx_i <= l3v(clip16(dec(k).i * gain), 16);
                            rx_q <= l3v(clip16(dec(k).q * gain), 16);
                            rx_v <= L3D_1;
                            for edge in 0 to 1 loop
                                wait for HALF; clk <= L3D_1; wait for HALF; clk <= L3D_0;
                                rx_v <= L3D_0;
                                if is_one(hit) then
                                    t_hit := now;
                                    pw_hit := pw;
                                    if debug then
                                        report "btle_phy_radio: access address found";
                                    end if;
                                end if;
                                if is_one(done) then
                                    p := CC2652R_NO_PACKET;
                                    p.crc_ok := is_one(ok);
                                    p.rssi := round(cc_w_dbm(pw_hit));
                                    if p.crc_ok then
                                        plen := int_of(len);
                                        p.len := plen + 2;
                                        for a in 0 to p.len - 1 loop
                                            rx_a <= l3v(a, 9);
                                            wait for 1 ps; clkb <= L3D_1; wait for 1 ps; clkb <= L3D_0;
                                            wait for 1 ps;
                                            p.pdu(a) := int_of(rx_d);
                                        end loop;
                                        p.t_end := t_hit - rx_hit_delay + (16 + 8 * plen + 24) * 1 us;
                                    else
                                        p.len := 2;
                                        p.t_end := now;
                                    end if;
                                    out_seq := out_seq + 1;
                                    p.seq := out_seq;
                                    rx <= p;
                                    if debug then
                                        report "btle_phy_radio: packet of " & integer'image(p.len) & " octets, CRC " & boolean'image(p.crc_ok)
                                            & ", phase " & integer'image(int_of(phase));
                                    end if;
                                end if;
                            end loop;
                            stop := tx_pending or cfg /= c;
                            exit when stop;
                        end loop;
                        exit when stop or (quiet >= FLUSH and not is_one(run));
                        t_ev := t_ev + CC_T_EVENT;
                        if now < t_ev then
                            wait for t_ev - now;
                        end if;
                    end loop;
                end if;
            end if;
        end loop;
    end process;
end architecture;
