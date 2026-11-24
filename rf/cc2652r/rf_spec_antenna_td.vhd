-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- rf_spec_antenna_td: rf_spec_antenna (rf/ad9361) for an arena whose path delays are in time: its air
-- pin is an rf_air_td (rf_spectrum_pkg), for radios whose events are consecutive blocks of samples.
-- feed is the wire to the radio; the antenna radiates air'driver and receives air'other.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library rf;
use rf.rf_signal_pkg.all;
use work.rf_spectrum_pkg.all;

entity rf_spec_antenna_td is
    generic (
        gain_dbi  : real := 0.0;
        pol_angle : real := 0.0;              -- polarisation, rad (0: horizontal)
        platform  : natural := 0;             -- antennas on the same platform (not 0) do not hear each other
        tx_lead   : time := 0 ns              -- transmit latency (> 0: scheduled ahead, see rf_spec_antenna)
    );
    port (
        feed     : inout std_logic;
        air      : inout std_logic;
        position : in rf_position
    );
end entity;

architecture behavioral of rf_spec_antenna_td is
    signal pos : rf_position := (0.0, 0.0, 0.0);
    signal plat : integer := platform;        -- for the resolver to read
begin
    pos <= position;

    process (feed'other, air'other)
        constant g : real := sqrt(db_to_linear(gain_dbi));
        variable from_feed : rf_spectrum;
        variable from_air, to_air : rf_air_td;
    begin
        from_feed := feed'other;
        from_air := air'other;
        to_air := spec_scale(spec_rotate(from_feed, pol_angle), g);
        if tx_lead > 0 ns then
            air'driver <= transport to_air after tx_lead;
        else
            air'driver := to_air;
        end if;
        feed'driver := spec_scale(spec_rotate(from_air, -pol_angle), g);
    end process;
end architecture;
