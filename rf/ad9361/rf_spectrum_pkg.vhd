-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- rf_spectrum_pkg: a wideband RF signal as a spectrum, for event-driven simulation in nvc (--std=2040).
--
-- One value of rf_spectrum is what is on a net for one event: SPEC_N spectral lines (complex amplitude
-- and phase of each, both polarisations) on a grid of spacing df around the carrier `freq`.  An OFDM
-- radio makes one event per symbol period; a linear block multiplies each line, a non-linear one goes
-- through the time domain of the symbol (lines_to_time / time_to_lines), and the air between antennas
-- is resolved in an arena (arena_resolve: every antenna hears every other one through Friis coupling).
--
-- Conventions.  Amplitudes are in sqrt(W): the power of a line is |h|^2 + |v|^2, as in rf.rf_signal_pkg.
-- Lines are in FFT order: line k is at freq + k df for k < SPEC_N / 2 and at freq + (k - SPEC_N) df above.
-- Over the event the signal is  x(t) = sum_k X_k exp(j 2 pi (k df) t),  t from the start of the event.
-- `seq` must change with every event (two equal spectra in a row are otherwise no event); seq = 0 is a
-- net nothing was ever written to, whose other fields are not to be read.
library ieee;
use ieee.math_real.all;
library rf;
use rf.rf_signal_pkg.all;
use rf.iq_pkg.all;
use rf.ofdm_pkg.all;

package rf_spectrum_pkg is
    constant SPEC_N : positive := 64;
    subtype spec_lines is iq_array(0 to SPEC_N - 1);
    constant LINES_ZERO : spec_lines := (others => IQ_ZERO);

    type rf_spectrum is record
        h    : spec_lines;      -- H-polarised lines, sqrt(W)
        v    : spec_lines;      -- V-polarised lines
        freq : real;            -- carrier (line 0), Hz; < 0.0: nothing on the net
        df   : real;            -- line spacing, Hz
        seq  : natural;         -- event marker; 0: never written
    end record;
    type rf_spectrum_vector is array (natural range <>) of rf_spectrum;

    type rf_position is record
        x, y, z : real;         -- metres
    end record;
    type rf_position_vector is array (natural range <>) of rf_position;

    function spec_silent(seq : positive) return rf_spectrum;
    function spec_is_silent(s : rf_spectrum) return boolean;
    function spec_power(s : rf_spectrum) return real;                      -- W, all lines
    function spec_line_offset(k : natural; df : real) return real;         -- frequency of line k against the carrier
    function spec_scale(s : rf_spectrum; a : real) return rf_spectrum;
    function spec_rotate(s : rf_spectrum; angle : real) return rf_spectrum; -- polarisation rotation
    -- free space over `distance` metres: lambda / (4 pi d) and the carrier phase, line by line
    function spec_friis(s : rf_spectrum; distance : real) return rf_spectrum;
    -- the same signal on a grid around another carrier, for the event that starts at t0 (seconds)
    function spec_regrid(s : rf_spectrum; freq : real; t0 : real) return rf_spectrum;
    function spec_add(a, b : rf_spectrum; t0 : real) return rf_spectrum;
    function rf_distance(a, b : rf_position) return real;
    -- arena: what each antenna receives from all the others (drv(i) is what antenna i radiates)
    function arena_resolve(drv : rf_spectrum_vector; pos : rf_position_vector; t0 : real) return rf_spectrum_vector;
    -- the same with platforms and scatterers.  plat(i): antennas on the same platform (not 0) do not hear
    -- each other directly (an array's elements, shielded from each other by construction).  A scatterer
    -- is a point target of radar cross-section srcs (m2) at spos: every antenna hears every antenna's
    -- signal (its own too) off every scatterer; scatterers do not light each other (single bounce).
    function arena_resolve(drv : rf_spectrum_vector; pos : rf_position_vector; plat : integer_vector;
                           spos : rf_position_vector; srcs : real_vector; t0 : real) return rf_spectrum_vector;
    -- a field arriving at a scatterer of cross-section rcs, re-radiated over `distance` metres: per line
    -- sqrt(4 pi rcs) / lambda, times free space
    function spec_echo(s : rf_spectrum; distance : real; rcs : real) return rf_spectrum;
    -- wire: what each end of a wire receives from all the others
    function wire_resolve(drv : rf_spectrum_vector; t0 : real) return rf_spectrum_vector;

    -- samples of the event: x[n] = sum_k X_k exp(j 2 pi k n / SPEC_N), and back
    function lines_to_time(x : spec_lines) return spec_lines;
    function time_to_lines(x : spec_lines) return spec_lines;
    -- the lines of the same samples seen from a carrier `eps` line spacings lower
    function lines_shift(x : spec_lines; eps : real) return spec_lines;
    function lines_power(x : spec_lines) return real;
    function lines_rotate(x : spec_lines; phase : real) return spec_lines;
    impure function sim_time return real;                                   -- now, in seconds
    -- lines as (re, im) pairs in a real_vector, and back: how spectra cross to foreign code
    function lines_to_reals(x : spec_lines) return real_vector;
    function reals_to_lines(v : real_vector) return spec_lines;
end package;

package body rf_spectrum_pkg is
    impure function sim_time return real is
    begin
        return real(now / 1 ns) * 1.0e-9;
    end function;

    function lines_to_reals(x : spec_lines) return real_vector is
        variable v : real_vector(0 to 2 * SPEC_N - 1);
    begin
        for k in x'range loop
            v(2 * k) := x(k).i;
            v(2 * k + 1) := x(k).q;
        end loop;
        return v;
    end function;

    function reals_to_lines(v : real_vector) return spec_lines is
        variable x : spec_lines;
    begin
        for k in x'range loop
            x(k) := (i => v(v'low + 2 * k), q => v(v'low + 2 * k + 1));
        end loop;
        return x;
    end function;

    function spec_silent(seq : positive) return rf_spectrum is
    begin
        return (h => LINES_ZERO, v => LINES_ZERO, freq => -1.0, df => 0.0, seq => seq);
    end function;

    function spec_is_silent(s : rf_spectrum) return boolean is
    begin
        if s.seq = 0 then
            return true;
        end if;
        return s.freq < 0.0;
    end function;

    function lines_power(x : spec_lines) return real is
        variable p : real := 0.0;
    begin
        for k in x'range loop
            p := p + x(k).i * x(k).i + x(k).q * x(k).q;
        end loop;
        return p;
    end function;

    function spec_power(s : rf_spectrum) return real is
    begin
        if spec_is_silent(s) then
            return 0.0;
        end if;
        return lines_power(s.h) + lines_power(s.v);
    end function;

    function spec_line_offset(k : natural; df : real) return real is
    begin
        if k < SPEC_N / 2 then
            return real(k) * df;
        end if;
        return real(k - SPEC_N) * df;
    end function;

    function spec_scale(s : rf_spectrum; a : real) return rf_spectrum is
        variable r : rf_spectrum := s;
    begin
        if spec_is_silent(s) then
            return spec_silent(s.seq + 1);
        end if;
        for k in r.h'range loop
            r.h(k) := (s.h(k).i * a, s.h(k).q * a);
            r.v(k) := (s.v(k).i * a, s.v(k).q * a);
        end loop;
        return r;
    end function;

    function spec_rotate(s : rf_spectrum; angle : real) return rf_spectrum is
        constant c : real := cos(angle);
        constant sn : real := sin(angle);
        variable r : rf_spectrum := s;
    begin
        if spec_is_silent(s) then
            return spec_silent(s.seq + 1);
        end if;
        if angle = 0.0 then
            return s;
        end if;
        for k in r.h'range loop
            r.h(k) := (s.h(k).i * c - s.v(k).i * sn, s.h(k).q * c - s.v(k).q * sn);
            r.v(k) := (s.h(k).i * sn + s.v(k).i * c, s.h(k).q * sn + s.v(k).q * c);
        end loop;
        return r;
    end function;

    function lines_rotate(x : spec_lines; phase : real) return spec_lines is
        constant c : real := cos(phase);
        constant s : real := sin(phase);
        variable r : spec_lines;
    begin
        for k in x'range loop
            r(k) := (x(k).i * c - x(k).q * s, x(k).i * s + x(k).q * c);
        end loop;
        return r;
    end function;

    function spec_friis(s : rf_spectrum; distance : real) return rf_spectrum is
        variable r : rf_spectrum := s;
        variable f, a, ph, c, sn : real;
    begin
        if spec_is_silent(s) or distance <= 0.0 then          -- two things in one place do not hear each other
            return spec_silent(s.seq + 1);
        end if;
        for k in r.h'range loop
            f := s.freq + spec_line_offset(k, s.df);
            a := SPEED_OF_LIGHT / (4.0 * MATH_PI * distance * f);
            ph := -2.0 * MATH_PI * (f * distance / SPEED_OF_LIGHT mod 1.0);
            c := a * cos(ph);
            sn := a * sin(ph);
            r.h(k) := (s.h(k).i * c - s.h(k).q * sn, s.h(k).i * sn + s.h(k).q * c);
            r.v(k) := (s.v(k).i * c - s.v(k).q * sn, s.v(k).i * sn + s.v(k).q * c);
        end loop;
        return r;
    end function;

    function lines_to_time(x : spec_lines) return spec_lines is
        variable t : spec_lines := ifft(x);                 -- rf.ofdm_pkg's ifft carries 1 / N
    begin
        for n in t'range loop
            t(n) := (t(n).i * real(SPEC_N), t(n).q * real(SPEC_N));
        end loop;
        return t;
    end function;

    function time_to_lines(x : spec_lines) return spec_lines is
        variable f : spec_lines := fft(x);
    begin
        for k in f'range loop
            f(k) := (f(k).i / real(SPEC_N), f(k).q / real(SPEC_N));
        end loop;
        return f;
    end function;

    function lines_shift(x : spec_lines; eps : real) return spec_lines is
        variable t : spec_lines;
        variable ph, c, s : real;
    begin
        if eps = 0.0 then
            return x;
        end if;
        if abs(eps) >= real(SPEC_N / 2) then
            return LINES_ZERO;                              -- another channel: outside this grid
        end if;
        t := lines_to_time(x);
        for n in t'range loop
            ph := 2.0 * MATH_PI * eps * real(n) / real(SPEC_N);
            c := cos(ph);
            s := sin(ph);
            t(n) := (t(n).i * c - t(n).q * s, t(n).i * s + t(n).q * c);
        end loop;
        return time_to_lines(t);
    end function;

    function spec_regrid(s : rf_spectrum; freq : real; t0 : real) return rf_spectrum is
        variable r : rf_spectrum := s;
        variable eps, ph : real;
    begin
        if spec_is_silent(s) then
            return spec_silent(s.seq + 1);
        end if;
        if s.freq = freq then
            return s;
        end if;
        eps := (s.freq - freq) / s.df;
        ph := 2.0 * MATH_PI * ((s.freq - freq) * t0 mod 1.0);         -- the offset's phase at the start of the event
        r.h := lines_rotate(lines_shift(s.h, eps), ph);
        r.v := lines_rotate(lines_shift(s.v, eps), ph);
        r.freq := freq;
        return r;
    end function;

    function spec_add(a, b : rf_spectrum; t0 : real) return rf_spectrum is
        variable r : rf_spectrum := a;
        variable o : rf_spectrum;
    begin
        if spec_is_silent(b) then
            if spec_is_silent(a) then
                return spec_silent((a.seq + b.seq) mod 1000000000 + 1);
            end if;
            r.seq := (a.seq + b.seq) mod 1000000000 + 1;
            return r;
        end if;
        if spec_is_silent(a) then
            r := b;
            r.seq := (a.seq + b.seq) mod 1000000000 + 1;
            return r;
        end if;
        assert a.df = b.df report "spec_add: the two signals have different line spacings" severity failure;
        o := spec_regrid(b, a.freq, t0);
        for k in r.h'range loop
            r.h(k) := (a.h(k).i + o.h(k).i, a.h(k).q + o.h(k).q);
            r.v(k) := (a.v(k).i + o.v(k).i, a.v(k).q + o.v(k).q);
        end loop;
        r.seq := (a.seq + b.seq) mod 1000000000 + 1;
        return r;
    end function;

    function rf_distance(a, b : rf_position) return real is
    begin
        return sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2);
    end function;

    function arena_resolve(drv : rf_spectrum_vector; pos : rf_position_vector; t0 : real) return rf_spectrum_vector is
        variable r : rf_spectrum_vector(drv'range);
        variable acc : rf_spectrum;
    begin
        for i in drv'range loop
            acc := spec_silent(1);
            for j in drv'range loop
                if j /= i then
                    acc := spec_add(acc, spec_friis(drv(j), rf_distance(pos(i), pos(j))), t0);
                end if;
            end loop;
            r(i) := acc;
        end loop;
        return r;
    end function;

    function spec_echo(s : rf_spectrum; distance : real; rcs : real) return rf_spectrum is
        variable r : rf_spectrum := s;
        variable a, f, ph, c, sn : real;
    begin
        if spec_is_silent(s) or distance <= 0.0 then
            return spec_silent(s.seq + 1);
        end if;
        a := sqrt(4.0 * MATH_PI * rcs) / (4.0 * MATH_PI * distance);     -- the same at every line
        for k in r.h'range loop
            f := s.freq + spec_line_offset(k, s.df);
            ph := -2.0 * MATH_PI * (f * distance / SPEED_OF_LIGHT mod 1.0);
            c := a * cos(ph);
            sn := a * sin(ph);
            r.h(k) := (s.h(k).i * c - s.h(k).q * sn, s.h(k).i * sn + s.h(k).q * c);
            r.v(k) := (s.v(k).i * c - s.v(k).q * sn, s.v(k).i * sn + s.v(k).q * c);
        end loop;
        return r;
    end function;

    function arena_resolve(drv : rf_spectrum_vector; pos : rf_position_vector; plat : integer_vector;
                           spos : rf_position_vector; srcs : real_vector; t0 : real) return rf_spectrum_vector is
        variable r : rf_spectrum_vector(drv'range);
        variable field : rf_spectrum_vector(spos'range);
        variable acc : rf_spectrum;
    begin
        for s in spos'range loop                       -- what arrives at each scatterer
            acc := spec_silent(1);
            for j in drv'range loop
                acc := spec_add(acc, spec_friis(drv(j), rf_distance(spos(s), pos(j))), t0);
            end loop;
            field(s) := acc;
        end loop;
        for i in drv'range loop
            acc := spec_silent(1);
            for j in drv'range loop
                if j /= i and not (plat(i) /= 0 and plat(i) = plat(j)) then
                    acc := spec_add(acc, spec_friis(drv(j), rf_distance(pos(i), pos(j))), t0);
                end if;
            end loop;
            for s in spos'range loop
                acc := spec_add(acc, spec_echo(field(s), rf_distance(pos(i), spos(s)), srcs(s)), t0);
            end loop;
            r(i) := acc;
        end loop;
        return r;
    end function;

    function wire_resolve(drv : rf_spectrum_vector; t0 : real) return rf_spectrum_vector is
        variable r : rf_spectrum_vector(drv'range);
        variable acc : rf_spectrum;
    begin
        for i in drv'range loop
            acc := spec_silent(1);
            for j in drv'range loop
                if j /= i then
                    acc := spec_add(acc, drv(j), t0);
                end if;
            end loop;
            r(i) := acc;
        end loop;
        return r;
    end function;
end package body;
