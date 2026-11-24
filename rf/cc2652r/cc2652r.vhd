-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- cc2652r: the TI CC2652R's Bluetooth LE radio for nvc's --std=2040 spectral event-driven mode; the
-- VHDL of cc2652r.py (numbers: cc2652r_pkg.vhd, written by cc2652r_vhdl.py from the same tables).
--
-- ant is the RF pin (one, for both directions): the chip drives ant'driver with what it sends and reads
-- ant'other.  Its software sets cfg, puts a packet on tx to send it (when tx_busy is false) and is
-- handed received packets on rx.
--
-- Sending.  The packet's symbols (ble_phy_pkg) are GFSK-modulated at CC_FS; every CC_T_EVENT the pin is
-- driven with the spectrum of the next 64 samples, and with silence after the last.  The spectrum's
-- carrier is the channel's nominal frequency; the crystal's error is in the samples.
--
-- Receiving.  The receiver is idle until something arrives.  It then reads the pin once every CC_T_EVENT,
-- half an event after the first arrival (so each read is in the middle of an event of that signal; the
-- events of a second signal with another path delay are taken as they stand at the reads, an error in
-- its timing of under one event), and puts the 64 samples through noise, compression, the channel
-- filter and the discriminator.  A packet search runs on the discriminator's output: correlation with
-- preamble and access address, then the header, then the packet (ble_phy_pkg's detectors).  It goes
-- idle again when the pin has been silent long enough for the filters to empty and no packet is open.
-- The AGC is ideal: the gain follows each event's power (cc2652r.py: one setting per capture).
-- Signals more than CC_FS / 2 from the receiver's frequency are not seen at all (no blocking by them).
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library rf;
use rf.iq_pkg.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;
use work.cc2652r_spectral_pkg.all;

entity cc2652r is
    generic (
        seed : positive := 1;
        -- 2 ** ring_log2 discriminator samples are kept (32 a symbol, 16 on LE 2M), which is the longest
        -- packet that can be received: 17 holds any uncoded packet, a Coded S=2 packet of up to 229 octets
        -- and an S=8 one of up to 51; 20 holds everything (and wants nvc -H 64m or more per chip)
        ring_log2 : positive := 17;
        debug : boolean := false            -- report what the receiver does
    );
    port (
        ant     : inout std_logic;
        cfg     : in cc2652r_config;
        tx      : in cc2652r_packet;
        tx_busy : out boolean;
        rx      : out cc2652r_packet
    );
end entity;

architecture spectral of cc2652r is
    constant MAX_SYMBOLS : natural := ble_packet_symbol_count(PHY_S8, BLE_MAX_PDU);
    constant RING : natural := 2 ** ring_log2;
    signal sending : boolean := false;
    -- What the pin hears, as an ordinary signal: the receiver reads the pin at times of its own, and a
    -- process that reads ant'other itself is woken by every event on it, whatever it is waiting for.
    signal pin_in : rf_spectrum := spec_silent(1);
begin
    pin_watch: process (ant'other)
        variable s : rf_spectrum;
    begin
        s := ant'other;
        pin_in <= s;
    end process;

    assert SPEC_N = 64 and CC_T_EVENT = integer(round(real(SPEC_N) / CC_FS * 1.0e9)) * 1 ns
        report "cc2652r: CC_T_EVENT is not SPEC_N samples at CC_FS" severity failure;
    tx_busy <= sending;

    transmitter: process
        variable last_seq, seq : natural := 0;
        variable syms : bit_vector(0 to MAX_SYMBOLS - 1);
        variable nsym, sps, total, n, idx, c, glen : natural;
        variable phase, off, doff, amp, f : real := 0.0;
        variable t : spec_lines;
        variable c_cfg : cc2652r_config;
        variable pin : rf_spectrum;
        variable t_next : time;
    begin
        wait on tx;
        if tx.seq /= last_seq and tx.seq /= 0 and tx.len >= 2 then
            last_seq := tx.seq;
            c_cfg := cfg;
            assert c_cfg.frequency >= CC_F_MIN and c_cfg.frequency <= CC_F_MAX
                report "cc2652r: " & real'image(c_cfg.frequency) & " Hz is outside the radio's band" severity failure;
            nsym := ble_packet_symbol_count(c_cfg.phy, tx.len);
            syms(0 to nsym - 1) := ble_packet_symbols(c_cfg.phy, tx.pdu(0 to tx.len - 1), c_cfg.whiten,
                                                      c_cfg.access_address, c_cfg.crc_init);
            sps := CC_SPS(c_cfg.phy);
            glen := 5 * sps;
            c := (glen - 1) / 2;
            total := nsym * sps;
            amp := sqrt(cc_dbm_w(cc2652r_tx_power_legal(c_cfg.tx_power)));
            doff := 2.0 * MATH_PI * c_cfg.frequency * c_cfg.xo_ppm * 1.0e-6 / CC_FS;
            off := 0.0;
            sending <= true;
            n := 0;
            t_next := now;
            while n < total loop
                for i in 0 to SPEC_N - 1 loop
                    if n + i < total then
                        f := 0.0;                           -- the frequency pulses of the symbols around this sample
                        for j in 0 to glen - 1 loop
                            idx := n + i + c;
                            if idx >= j and idx - j < total then
                                if sps = 16 then
                                    if syms((idx - j) / sps) = '1' then
                                        f := f + CC_GAUSS_16(j);
                                    else
                                        f := f - CC_GAUSS_16(j);
                                    end if;
                                else
                                    if syms((idx - j) / sps) = '1' then
                                        f := f + CC_GAUSS_32(j);
                                    else
                                        f := f - CC_GAUSS_32(j);
                                    end if;
                                end if;
                            end if;
                        end loop;
                        phase := phase + f * MATH_PI * CC_MOD_INDEX / real(sps);
                        if phase > MATH_PI then
                            phase := phase - 2.0 * MATH_PI;
                        elsif phase < -MATH_PI then
                            phase := phase + 2.0 * MATH_PI;
                        end if;
                        t(i) := (amp * cos(phase + off), amp * sin(phase + off));
                        off := off + doff;
                        if off > MATH_PI then
                            off := off - 2.0 * MATH_PI;
                        elsif off < -MATH_PI then
                            off := off + 2.0 * MATH_PI;
                        end if;
                    else
                        t(i) := IQ_ZERO;
                    end if;
                end loop;
                seq := seq + 1;
                pin := (h => time_to_lines(t), v => LINES_ZERO, freq => c_cfg.frequency,
                        df => CC_FS / real(SPEC_N), seq => seq);
                ant'driver := pin;
                n := n + SPEC_N;
                t_next := t_next + CC_T_EVENT;
                cc_wait_until(t_next);
            end loop;
            seq := seq + 1;
            pin := spec_silent(seq);
            ant'driver := pin;
            sending <= false;
        end if;
    end process;

    receiver: process
        type state_t is (SEARCH, HEADER, PAYLOAD);
        variable state : state_t;
        variable c_cfg : cc2652r_config;
        variable s1, s2 : positive := seed;
        -- per activation
        variable phy : ble_phy;
        variable sps, ntaps, t0s, coding : natural;
        variable t_first : time;
        variable dl : iq_array(0 to CC_MAX_TAPS - 1);       -- the filter's input, newest at dpos
        variable dpos : natural;
        variable yh : iq_array(0 to 31);                    -- the filter's output one symbol back
        variable ypos : natural;
        variable softr, pwrr : real_vector(0 to RING - 1);
        variable nsamp, wr : natural;                       -- samples through the filter; discriminator samples kept
        variable rxph, drx : real;
        variable quiet, flush : natural;
        variable pat : bit_vector(0 to 335);
        variable p0 : real_vector(0 to 335);
        variable ln : natural;
        variable p0sq, thr, patmean : real;
        -- the search
        variable n, n0, nbits, s_found, out_seq : natural := 0;
        variable cpk, dc : real;
        variable sig : rf_spectrum;
        variable progress : boolean;
        variable cmax : real := -1.0e9;       -- debug: the largest correlation of this activation

        procedure gauss(g1, g2 : out real) is
            variable u1, u2, r : real;
        begin
            uniform(s1, s2, u1);
            uniform(s1, s2, u2);
            r := sqrt(-2.0 * log(realmax(u1, 1.0e-300)));
            g1 := r * cos(2.0 * MATH_PI * u2);
            g2 := r * sin(2.0 * MATH_PI * u2);
        end procedure;

        procedure activate is
            variable m : real := 0.0;
        begin
            phy := c_cfg.phy;
            sps := CC_SPS(phy);
            ntaps := CC_NTAPS(phy);
            t0s := CC_T0_SAMPLES(phy);
            coding := ble_coding(phy);
            dl := (others => IQ_ZERO);
            dpos := 0;
            yh := (others => IQ_ZERO);
            ypos := 0;
            nsamp := 0;
            wr := 0;
            rxph := 0.0;
            drx := -2.0 * MATH_PI * c_cfg.frequency * c_cfg.xo_ppm * 1.0e-6 / CC_FS;
            quiet := 0;
            flush := (ntaps + t0s + 2 * sps) / SPEC_N + 2;
            if coding = 1 and phy = PHY_1M then
                ln := 40;
            elsif coding = 1 then
                ln := 48;
            else
                ln := 336;
            end if;
            pat(0 to ln - 1) := ble_sync_pattern(phy, c_cfg.access_address);
            for k in 0 to ln - 1 loop
                if pat(k) = '1' then
                    m := m + 1.0;
                else
                    m := m - 1.0;
                end if;
            end loop;
            patmean := m / real(ln);
            p0sq := 0.0;
            thr := 0.0;
            for k in 0 to ln - 1 loop
                if pat(k) = '1' then
                    p0(k) := 1.0 - patmean;
                    thr := thr + p0(k);
                else
                    p0(k) := -1.0 - patmean;
                    thr := thr - p0(k);
                end if;
                p0sq := p0sq + p0(k) * p0(k);
            end loop;
            if coding = 1 then
                thr := CC_SYNC_THRESHOLD * CC_AMP(phy) * thr;
            else
                thr := CC_SYNC_THRESHOLD_CODED * CC_AMP(phy) * thr;
            end if;
            state := SEARCH;
            n := 0;
        end procedure;

        -- one event of the pin through the front end, into the rings
        procedure front_end(s : in rf_spectrum) is
            variable r : rf_spectrum;
            variable x : spec_lines := LINES_ZERO;
            variable pw, gr, sgm, ip3, g1, g2, k, cs, sn, re, im, a : real := 0.0;
            variable y, z, tp, d : iq_sample;
            variable j : natural;
        begin
            if not spec_is_silent(s) then
                r := spec_regrid(s, c_cfg.frequency, 0.0);
                if not spec_is_silent(r) then
                    x := lines_to_time(r.h);
                    for i in x'range loop
                        pw := pw + x(i).i * x(i).i + x(i).q * x(i).q;
                    end loop;
                    pw := pw / real(SPEC_N);
                end if;
            end if;
            if pw > 0.0 then
                gr := realmin(realmax(cc_w_dbm(pw) - CC_AGC_THRESHOLD, 0.0), CC_AGC_RANGE);
            end if;
            sgm := sqrt((CC_K_BOLTZ * CC_T0 * 10.0 ** (CC_NF(phy) / 10.0) * CC_FS + pw / 10.0 ** (CC_DYNAMIC_RANGE / 10.0)) / 2.0);
            ip3 := cc_dbm_w(CC_IIP3(phy) + gr);
            for i in x'range loop
                -- the receiver's own carrier error
                if drx /= 0.0 then
                    cs := cos(rxph);
                    sn := sin(rxph);
                    x(i) := (x(i).i * cs - x(i).q * sn, x(i).i * sn + x(i).q * cs);
                    rxph := rxph + drx;
                    if rxph > MATH_PI then
                        rxph := rxph - 2.0 * MATH_PI;
                    elsif rxph < -MATH_PI then
                        rxph := rxph + 2.0 * MATH_PI;
                    end if;
                end if;
                gauss(g1, g2);
                re := x(i).i + g1 * sgm;
                im := x(i).q + g2 * sgm;
                k := 1.0 / sqrt(1.0 + 2.0 * (re * re + im * im) / ip3);
                -- channel filter
                dpos := (dpos + 1) mod CC_MAX_TAPS;
                dl(dpos) := (re * k, im * k);
                y := IQ_ZERO;
                j := dpos;
                for t in 0 to ntaps - 1 loop
                    tp := CC_FIR(phy)(t);
                    d := dl(j);
                    y.i := y.i + tp.i * d.i - tp.q * d.q;
                    y.q := y.q + tp.i * d.q + tp.q * d.i;
                    if j = 0 then
                        j := CC_MAX_TAPS - 1;
                    else
                        j := j - 1;
                    end if;
                end loop;
                -- phase advance over one symbol
                z := yh(ypos);
                yh(ypos) := y;
                ypos := (ypos + 1) mod sps;
                re := y.i * z.i + y.q * z.q;
                im := y.q * z.i - y.i * z.q;
                a := 0.0;
                if re /= 0.0 or im /= 0.0 then
                    a := arctan(im, re);
                end if;
                if nsamp >= t0s then
                    softr(wr mod RING) := a;
                    pwrr(wr mod RING) := y.i * y.i + y.q * y.q;
                    wr := wr + 1;
                end if;
                nsamp := nsamp + 1;
            end loop;
        end procedure;

        impure function corr(at : natural) return real is
            variable c : real := 0.0;
        begin
            for k in 0 to ln - 1 loop
                c := c + p0(k) * softr((at + k * sps) mod RING);
            end loop;
            return c;
        end function;

        -- cnt symbols from symbol `first` of the candidate at n0, less the offset the carrier error gives
        impure function symbols(first, cnt : natural) return real_vector is
            variable r : real_vector(0 to cnt - 1);
        begin
            for k in r'range loop
                r(k) := softr((n0 + (first + k) * sps) mod RING) - dc;
            end loop;
            return r;
        end function;

        -- The header of the candidate at n0.  ok: it is a packet; then nbits is the length of PDU and CRC
        -- and s_found the coding of what follows the access address.
        procedure header(ok : out boolean) is
            variable got : bit_vector(0 to ln + 23);
            variable b1 : bit_vector(0 to 36);
            variable hdr : bit_vector(0 to 15);
            variable errs : natural := 0;
            variable o : ble_octets(0 to 0);
            variable span : natural;
        begin
            ok := false;
            if coding = 1 then
                got := ble_sequence_detect(symbols(0, ln + 24), CC_ISI0(phy), CC_ISI1(phy), CC_ISI2(phy));
                for k in 0 to ln - 1 loop
                    if got(k) /= pat(k) then
                        errs := errs + 1;
                    end if;
                end loop;
                if errs > CC_SYNC_ERRORS then
                    return;
                end if;
                hdr := got(ln to ln + 15);
                s_found := 1;
            else
                b1 := ble_viterbi(ble_pattern_llr(symbols(80, 296), 8));
                if b1(0 to 31) /= c_cfg.access_address or b1(33) = '1' then
                    return;
                end if;
                s_found := 8;
                if b1(32) = '1' then
                    s_found := 2;
                end if;
                hdr := ble_viterbi(ble_pattern_llr(symbols(376, 32 * s_found), s_found), false)(0 to 15);
            end if;
            if c_cfg.whiten >= 0 then
                hdr := hdr xor ble_whitening(c_cfg.whiten, 16);
            end if;
            o := ble_octets_of(hdr(8 to 15));
            nbits := 16 + 8 * o(0) + 24;
            if coding = 1 then
                span := (ln + nbits + 3) * sps;
            else
                span := (376 + (nbits + 3) * s_found + 1) * sps;
            end if;
            if span > RING then
                report "cc2652r: a packet of " & integer'image(o(0) + 2) & " octets is longer than the receiver keeps (ring_log2)"
                    severity warning;
                return;
            end if;
            ok := true;
        end procedure;

        procedure deliver(bits : bit_vector; nsym : natural) is
            variable p : cc2652r_packet := CC2652R_NO_PACKET;
            variable w : bit_vector(0 to bits'length - 1);
            variable pw : real := 0.0;
        begin
            w := bits;
            if c_cfg.whiten >= 0 then
                w := w xor ble_whitening(c_cfg.whiten, w'length);
            end if;
            p.len := (w'length - 24) / 8;
            p.pdu(0 to p.len - 1) := ble_octets_of(w(0 to w'length - 25));
            p.crc_ok := ble_crc24(w(0 to w'length - 25), c_cfg.crc_init) = w(w'length - 24 to w'length - 1);
            for k in 0 to ln * sps - 1 loop
                pw := pw + pwrr((n0 + k) mod RING);
            end loop;
            p.rssi := realmin(realmax(round(cc_w_dbm(pw / real(ln * sps))), CC_RSSI_FLOOR), CC_RSSI_FLOOR + CC_RSSI_RANGE);
            p.t_end := t_first + (n0 + nsym * sps) * (CC_T_EVENT / SPEC_N);
            out_seq := out_seq + 1;
            p.seq := out_seq;
            rx <= p;
        end procedure;

        -- one step of the packet search, if the samples in the rings allow one (progress)
        procedure search is
            variable c2 : real;
            variable ok : boolean;
            variable need, nsym : natural;
        begin
            progress := false;
            case state is
                when SEARCH =>
                    if n + ln * sps <= wr then
                        progress := true;
                        cpk := corr(n);
                        if cpk > cmax then
                            cmax := cpk;
                        end if;
                        if cpk > thr then
                            n0 := n;
                            for d in 1 to sps - 1 loop
                                c2 := corr(n + d);
                                if c2 > cpk then
                                    cpk := c2;
                                    n0 := n + d;
                                end if;
                            end loop;
                            dc := 0.0;
                            for k in 0 to ln - 1 loop
                                dc := dc + softr((n0 + k * sps) mod RING);
                            end loop;
                            dc := dc / real(ln) - cpk / p0sq * patmean;
                            state := HEADER;
                            if debug then
                                report "cc2652r: candidate at sample " & integer'image(n0) & " corr " & to_string(cpk, "%.2f") & " threshold " & to_string(thr, "%.2f");
                            end if;
                        else
                            n := n + 1;
                        end if;
                    end if;
                when HEADER =>
                    need := ln + 24;
                    if coding /= 1 then
                        need := 376 + 32 * 8;
                    end if;
                    if n0 + (need - 1) * sps < wr then
                        progress := true;
                        header(ok);
                        if debug then
                            report "cc2652r: header " & boolean'image(ok) & " bits " & integer'image(nbits);
                        end if;
                        if ok then
                            state := PAYLOAD;
                        else
                            n := n0 + 1;
                            state := SEARCH;
                        end if;
                    end if;
                when PAYLOAD =>
                    if coding = 1 then
                        nsym := ln + nbits;
                        need := nsym + 2;
                    else
                        nsym := 376 + (nbits + 3) * s_found;
                        need := nsym;
                    end if;
                    if n0 + (need - 1) * sps < wr then
                        progress := true;
                        if coding = 1 then
                            deliver(ble_sequence_detect(symbols(0, need), CC_ISI0(phy), CC_ISI1(phy), CC_ISI2(phy))(ln to ln + nbits - 1), nsym);
                        else
                            deliver(ble_viterbi(ble_pattern_llr(symbols(376, (nbits + 3) * s_found), s_found))(0 to nbits - 1), nsym);
                        end if;
                        n := n0 + nsym * sps;
                        state := SEARCH;
                    end if;
            end case;
        end procedure;

        variable t_tick : time;
    begin
        -- idle until something new arrives while the receiver is on
        loop
            wait on pin_in, cfg, sending;
            sig := pin_in;
            exit when cfg.rx_on and not sending and pin_in'event and not spec_is_silent(sig);
        end loop;
        c_cfg := cfg;
        activate;
        cmax := -1.0e9;
        t_first := now;
        if debug then
            report "cc2652r: receiver wakes, pin at " & to_string(cc_w_dbm(spec_power(sig)), "%.1f") & " dBm, carrier " & to_string(sig.freq, "%.0f");
        end if;
        t_tick := now + CC_T_EVENT / 2;
        cc_wait_until(t_tick);
        loop
            exit when sending or cfg /= c_cfg;
            sig := pin_in;
            front_end(sig);
            if spec_is_silent(sig) then
                quiet := quiet + 1;
            else
                quiet := 0;
            end if;
            loop
                search;
                exit when not progress;
            end loop;
            exit when quiet >= flush and state = SEARCH;
            t_tick := t_tick + CC_T_EVENT;
            cc_wait_until(t_tick);
        end loop;
        if debug then
            report "cc2652r: receiver idle after " & integer'image(nsamp) & " samples, search at " & integer'image(n) & " of " & integer'image(wr)
                & ", largest correlation " & to_string(cmax, "%.2f") & " of " & to_string(thr, "%.2f") & " seq " & integer'image(sig.seq);
        end if;
    end process;
end architecture;
