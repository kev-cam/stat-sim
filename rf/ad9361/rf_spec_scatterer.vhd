-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- rf_spec_scatterer: a point target in the arena (--std=2040 spectral signals).
--
-- It has no net: the arena resolver (arena_resolver.py, rf_spectrum_pkg.arena_resolve) reads where it is
-- and its radar cross-section, and gives every antenna the echo of every antenna's signal off it.  The
-- position is a port, so a target can move from event to event (the phase of its echo then turns: Doppler).
library ieee;
use ieee.std_logic_1164.all;
use work.rf_spectrum_pkg.all;
use work.spectral_accel_pkg.all;

entity rf_spec_scatterer is
    generic (
        rcs_m2 : real := 1.0                  -- radar cross-section, m2
    );
    port (
        position : in rf_position
    );
end entity;

architecture behavioral of rf_spec_scatterer is
    signal pos : rf_position := (0.0, 0.0, 0.0);
    signal rcs : real := rcs_m2;              -- for the resolver to read
    signal accel_id : real := -1.0;           -- this scatterer in the spectral accelerator (-1.0: none)
begin
    pos <= position;

    track: process (position)
        variable id : real := -1.0;
        variable asked : boolean := false;
    begin
        if not asked then
            asked := true;
            if sa_available then
                id := sa_scatterer_new(rcs_m2);
                accel_id <= id;
            end if;
        end if;
        if id >= 0.0 then
            sa_scatterer_position(id, position.x, position.y, position.z);
        end if;
    end process;
end architecture;
