-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ofdm_soft_pkg: a software OFDM modem on spectra, for driving a radio model from a process (no RTL).
--
-- The 802.11a/g numerology of ofdm.py: 64 lines, 52 used (48 data, pilots at -21, -7, 7, 21), one event
-- per symbol period (80 samples of air time, of which the 64 of the symbol body are modelled).  A packet
-- is two short-training events, two long-training events and the data events.  No SIGNAL field, coding
-- or scrambling: the measures are EVM and uncoded bit errors.
library ieee;
use ieee.math_real.all;
library rf;
use rf.iq_pkg.all;
use work.rf_spectrum_pkg.all;

package ofdm_soft_pkg is
    constant SOFT_CARRIERS : positive := 48;
    constant SOFT_SYMBOL_SAMPLES : positive := 80;            -- symbol period in samples (64 + 16 guard)
    subtype soft_symbols is iq_array(0 to SOFT_CARRIERS - 1);
    type soft_indices is array (0 to SOFT_CARRIERS - 1) of natural;
    type soft_modulation is (MOD_BPSK, MOD_QPSK, MOD_16QAM, MOD_64QAM);

    function soft_points(m : soft_modulation) return positive;                 -- constellation size
    function soft_bits(m : soft_modulation) return positive;                   -- bits per symbol
    function soft_point(m : soft_modulation; index : natural) return iq_sample; -- unit mean power
    function soft_decide(m : soft_modulation; p : iq_sample) return natural;   -- index of the nearest point
    function soft_bit_errors(m : soft_modulation; a, b : natural) return natural; -- Gray-coded bits that differ

    -- one event's lines, total power 1
    function soft_stf return spec_lines;
    function soft_ltf return spec_lines;
    function soft_data(m : soft_modulation; idx : soft_indices) return spec_lines;

    -- receive side
    function soft_is_stf(x : spec_lines) return boolean;
    -- carrier offset in line spacings, from the phase between two long-training events one symbol apart
    function soft_cfo(ltf1, ltf2 : spec_lines) return real;
    -- remove a carrier offset of eps line spacings from the event `symbol` periods after the reference event
    function soft_correct(x : spec_lines; eps : real; symbol : integer) return spec_lines;
    function soft_channel(ltf1, ltf2 : spec_lines) return spec_lines;          -- per line; unused lines zero
    function soft_equalise(x : spec_lines; h : spec_lines) return soft_symbols; -- data lines, pilot phase removed
end package;

package body ofdm_soft_pkg is
    type int_vec is array (natural range <>) of integer;
    -- long training symbol on subcarriers -26 .. 26
    constant LTF_SEQ : int_vec(0 to 52) := (1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1,
                                            1, 1, 1, 0, 1, -1, -1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, -1, 1, 1, -1, -1,
                                            1, -1, 1, -1, 1, 1, 1, 1);
    -- short training symbol: signs of (1 + j) on subcarriers -24, -20, .. , 24 (not 0)
    constant STF_K : int_vec(0 to 11) := (-24, -20, -16, -12, -8, -4, 4, 8, 12, 16, 20, 24);
    constant STF_S : int_vec(0 to 11) := (1, -1, 1, -1, -1, 1, -1, -1, 1, 1, 1, 1);
    constant PILOT_K : int_vec(0 to 3) := (-21, -7, 7, 21);
    constant PILOT_V : int_vec(0 to 3) := (1, 1, 1, -1);

    function line(k : integer) return natural is              -- subcarrier -32 .. 31 -> FFT-order line
    begin
        return k mod SPEC_N;
    end function;

    function is_pilot(k : integer) return boolean is
    begin
        return k = -21 or k = -7 or k = 7 or k = 21;
    end function;

    function soft_points(m : soft_modulation) return positive is
    begin
        case m is
            when MOD_BPSK => return 2;
            when MOD_QPSK => return 4;
            when MOD_16QAM => return 16;
            when MOD_64QAM => return 64;
        end case;
    end function;

    function soft_bits(m : soft_modulation) return positive is
    begin
        case m is
            when MOD_BPSK => return 1;
            when MOD_QPSK => return 2;
            when MOD_16QAM => return 4;
            when MOD_64QAM => return 6;
        end case;
    end function;

    function levels(m : soft_modulation) return positive is   -- levels per axis
    begin
        case m is
            when MOD_BPSK | MOD_QPSK => return 2;
            when MOD_16QAM => return 4;
            when MOD_64QAM => return 8;
        end case;
    end function;

    function norm(m : soft_modulation) return real is         -- rms of the unscaled points
    begin
        case m is
            when MOD_BPSK => return 1.0;
            when MOD_QPSK => return sqrt(2.0);
            when MOD_16QAM => return sqrt(10.0);
            when MOD_64QAM => return sqrt(42.0);
        end case;
    end function;

    -- index = (level position on I) * levels + (level position on Q); BPSK: the position on I
    function soft_point(m : soft_modulation; index : natural) return iq_sample is
        constant l : positive := levels(m);
    begin
        if m = MOD_BPSK then
            return (i => real(2 * index - 1), q => 0.0);
        end if;
        return (i => real(2 * (index / l) - (l - 1)) / norm(m), q => real(2 * (index mod l) - (l - 1)) / norm(m));
    end function;

    function level_of(x : real; l : positive) return natural is
        variable i : integer := integer(round((x + real(l - 1)) / 2.0));
    begin
        if i < 0 then
            return 0;
        elsif i > l - 1 then
            return l - 1;
        end if;
        return i;
    end function;

    function soft_decide(m : soft_modulation; p : iq_sample) return natural is
        constant l : positive := levels(m);
    begin
        if m = MOD_BPSK then
            return level_of(p.i, 2);
        end if;
        return level_of(p.i * norm(m), l) * l + level_of(p.q * norm(m), l);
    end function;

    function gray_diff(a, b : natural) return natural is       -- bits differing between the Gray codes of a and b
        variable x : natural := 0;
        variable ga : natural := a;
        variable gb : natural := b;
        variable n : natural := 0;
    begin
        -- Gray code g = i xor (i / 2), bit by bit
        for bit in 0 to 5 loop
            if ((ga / 2 ** bit) mod 2 + (ga / 2 ** (bit + 1)) mod 2) mod 2 /= ((gb / 2 ** bit) mod 2 + (gb / 2 ** (bit + 1)) mod 2) mod 2 then
                n := n + 1;
            end if;
        end loop;
        return n;
    end function;

    function soft_bit_errors(m : soft_modulation; a, b : natural) return natural is
        constant l : positive := levels(m);
    begin
        if m = MOD_BPSK then
            return gray_diff(a, b);
        end if;
        return gray_diff(a / l, b / l) + gray_diff(a mod l, b mod l);
    end function;

    function soft_stf return spec_lines is
        variable x : spec_lines := LINES_ZERO;
        constant a : real := 1.0 / sqrt(24.0);                 -- 12 lines of power 2 a^2: total 1
    begin
        for n in STF_K'range loop
            x(line(STF_K(n))) := (i => a * real(STF_S(n)), q => a * real(STF_S(n)));
        end loop;
        return x;
    end function;

    function soft_ltf return spec_lines is
        variable x : spec_lines := LINES_ZERO;
    begin
        for k in -26 to 26 loop
            x(line(k)) := (i => real(LTF_SEQ(k + 26)) / sqrt(52.0), q => 0.0);
        end loop;
        return x;
    end function;

    function soft_data(m : soft_modulation; idx : soft_indices) return spec_lines is
        variable x : spec_lines := LINES_ZERO;
        variable n : natural := 0;
        variable p : iq_sample;
    begin
        for k in -26 to 26 loop
            if k = 0 then
                null;
            elsif is_pilot(k) then
                for q in PILOT_K'range loop
                    if PILOT_K(q) = k then
                        x(line(k)) := (i => real(PILOT_V(q)) / sqrt(52.0), q => 0.0);
                    end if;
                end loop;
            else
                p := soft_point(m, idx(n));
                x(line(k)) := (i => p.i / sqrt(52.0), q => p.q / sqrt(52.0));
                n := n + 1;
            end if;
        end loop;
        return x;
    end function;

    function soft_is_stf(x : spec_lines) return boolean is
        variable on_stf : real := 0.0;
        constant total : real := lines_power(x);
    begin
        for n in STF_K'range loop
            on_stf := on_stf + iq_power(x(line(STF_K(n))));
        end loop;
        return total > 0.0 and on_stf > 0.5 * total;
    end function;

    function soft_cfo(ltf1, ltf2 : spec_lines) return real is
        variable re, im : real := 0.0;
    begin
        for k in -26 to 26 loop
            if k /= 0 then                                     -- sum of conj(first) * second
                re := re + ltf1(line(k)).i * ltf2(line(k)).i + ltf1(line(k)).q * ltf2(line(k)).q;
                im := im + ltf1(line(k)).i * ltf2(line(k)).q - ltf1(line(k)).q * ltf2(line(k)).i;
            end if;
        end loop;
        -- the phase advances 2 pi eps (symbol period / body) per symbol
        return arctan(im, re) / (2.0 * MATH_PI) * real(SPEC_N) / real(SOFT_SYMBOL_SAMPLES);
    end function;

    function soft_correct(x : spec_lines; eps : real; symbol : integer) return spec_lines is
    begin
        return lines_rotate(lines_shift(x, -eps),
                            -2.0 * MATH_PI * eps * real(SOFT_SYMBOL_SAMPLES) / real(SPEC_N) * real(symbol));
    end function;

    function soft_channel(ltf1, ltf2 : spec_lines) return spec_lines is
        variable h : spec_lines := LINES_ZERO;
        variable s : real;
    begin
        for k in -26 to 26 loop
            if k /= 0 then
                s := real(LTF_SEQ(k + 26)) / sqrt(52.0);
                h(line(k)) := (i => (ltf1(line(k)).i + ltf2(line(k)).i) / (2.0 * s),
                               q => (ltf1(line(k)).q + ltf2(line(k)).q) / (2.0 * s));
            end if;
        end loop;
        return h;
    end function;

    function soft_equalise(x : spec_lines; h : spec_lines) return soft_symbols is
        variable r : soft_symbols;
        variable n : natural := 0;
        variable re, im, m, c, s : real := 0.0;
        variable y, hk : iq_sample;
    begin
        -- common phase of this event from the pilots: sum of y conj(h p)
        for q in PILOT_K'range loop
            y := x(line(PILOT_K(q)));
            hk := h(line(PILOT_K(q)));
            re := re + real(PILOT_V(q)) * (y.i * hk.i + y.q * hk.q);
            im := im + real(PILOT_V(q)) * (y.q * hk.i - y.i * hk.q);
        end loop;
        m := sqrt(re * re + im * im);
        if m > 0.0 then
            c := re / m;
            s := im / m;
        else
            c := 1.0;
            s := 0.0;
        end if;
        for k in -26 to 26 loop
            if k /= 0 and not is_pilot(k) then
                y := x(line(k));
                hk := h(line(k));
                m := hk.i * hk.i + hk.q * hk.q;
                if m > 0.0 then
                    -- y / h, then times exp(-j phase): multiply by (c - j s)
                    re := (y.i * hk.i + y.q * hk.q) / m;
                    im := (y.q * hk.i - y.i * hk.q) / m;
                    r(n) := (i => (re * c + im * s) * sqrt(52.0), q => (im * c - re * s) * sqrt(52.0));
                else
                    r(n) := IQ_ZERO;
                end if;
                n := n + 1;
            end if;
        end loop;
        return r;
    end function;
end package body;
