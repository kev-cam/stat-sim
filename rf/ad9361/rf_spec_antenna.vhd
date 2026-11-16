-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- rf_spec_antenna: an antenna for spectral signals (--std=2040), a driver and a receiver in the arena.
--
-- feed is the wire to the radio; air is the antenna's place in the arena.  The antenna radiates
-- air'driver and receives air'other; the arena resolver (arena_resolver.py, rf_spectrum_pkg.arena_resolve)
-- gives every antenna the sum of what the others radiate, through free space between their positions.
-- The position is a port, so an antenna can move during the run; the resolver reads `pos`.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library rf;
use rf.rf_signal_pkg.all;
use work.rf_spectrum_pkg.all;

entity rf_spec_antenna is
    generic (
        gain_dbi  : real := 0.0;
        pol_angle : real := 0.0               -- polarisation, rad (0: horizontal)
    );
    port (
        feed     : inout std_logic;
        air      : inout std_logic;
        position : in rf_position
    );
end entity;

architecture behavioral of rf_spec_antenna is
    signal pos : rf_position := (0.0, 0.0, 0.0);
begin
    pos <= position;

    process (feed'other, air'other)
        constant g : real := sqrt(db_to_linear(gain_dbi));
        variable from_feed, from_air : rf_spectrum;
    begin
        from_feed := feed'other;
        from_air := air'other;
        air'driver := spec_scale(spec_rotate(from_feed, pol_angle), g);
        feed'driver := spec_scale(spec_rotate(from_air, -pol_angle), g);
    end process;
end architecture;
