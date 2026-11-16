-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
-- Prints the gain of the generated table packages against drive level; compare with the fitted .json tables.
--   nvc --work=rf -a <nvc>/lib/rf/rf_signal_pkg.vhd
--   nvc -L . -a ../models/ft8_lna4_ext_fit_pkg.vhd ../models/ft8_lna4_states_fit_pkg.vhd tb.vhd -e tb -r
library ieee; use ieee.math_real.all;
library rf; use rf.rf_signal_pkg.all;
use work.ft8_lna4_ext_fit_pkg.all;
use work.ft8_lna4_states_fit_pkg.all;
entity tb is end entity;
architecture t of tb is
  function gain_db(r, s : rf_signal) return real is
  begin
    return 10.0 * log10(rf_power(r) / rf_power(s));
  end function;
begin
  process
    variable s, r : rf_signal;
    variable vin : real;
  begin
    for i in 0 to 7 loop
      vin := 0.05e-6 * 4.0 ** i;                      -- peak volts, from below to above the fitted range
      s := make_h_polarized(vin * vin / (2.0 * work.ft8_lna4_ext_fit_pkg.Z0), 0.0, 28.0e6);
      r := ft8_lna4_ext_apply(s);
      report "ext 28MHz vin=" & real'image(vin) & " gain=" & real'image(gain_db(r, s)) & " dB phase=" & real'image(phase_h(r) * 180.0 / MATH_PI) & " deg";
    end loop;
    s := make_h_polarized(1.0e-6 ** 2 / (2.0 * work.ft8_lna4_ext_fit_pkg.Z0), 0.0, 7.0e6);
    for st in ft8_lna4_states_state loop
      r := ft8_lna4_states_apply(s, st);
      report "states 7MHz 1uV " & ft8_lna4_states_state'image(st) & " gain=" & real'image(gain_db(r, s)) & " dB";
    end loop;
    wait;
  end process;
end architecture;
