library ieee; use ieee.math_real.all;
library rf; use rf.rf_signal_pkg.all;
use work.ft8_lna4_ext_fit_pkg.all;
entity tb is end entity;
architecture t of tb is begin
  process
    variable s, r : rf_signal;
    variable vin : real;
  begin
    for i in 0 to 4 loop
      vin := 1.0e-6 * 4.0 ** i;                       -- peak volts
      s := make_h_polarized(vin * vin / (2.0 * Z0), 0.0, 28.0e6);
      r := ft8_lna4_ext_apply(s);
      report "vin=" & real'image(vin) & " V  gain=" & real'image(10.0 * log10(rf_power(r) / rf_power(s))) & " dB  phase=" & real'image(phase_h(r) * 180.0 / MATH_PI) & " deg";
    end loop;
    wait;
  end process;
end architecture;
