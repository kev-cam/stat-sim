-- statsim_taps.vhd -- passive prob_load taps for the binder (stat-sim).
-- These carry only the BACKWARD channel (gdrv=0, so they never move the
-- probability vote): a fan-out receiver pin presents its input capacitance, a
-- SPEF wire segment presents its C and series R. The binder drops one pl_wire
-- per net plus one pl_load per fan-out receiver onto the multi-UDN node; the
-- resolver sums their cload/rwire so each driving cell reads the real load back.

library ieee;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_pl_load is
    generic ( CIN : real := 2.0e-15 );     -- receiver input capacitance (F)
    port ( n : inout resolved_pl );
end entity;

architecture pwl of statsim_pl_load is
begin
    n <= PL_LOAD(CIN);                      -- pure load (gdrv=0): votes nothing
end architecture;


library ieee;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_pl_wire is
    generic ( C : real := 0.0;             -- SPEF wire capacitance (F)
              R : real := 0.0 );           -- SPEF wire series resistance (ohm)
    port ( n : inout resolved_pl );
end entity;

architecture pwl of statsim_pl_wire is
begin
    n <= PL_WIRE(C, R);
end architecture;
