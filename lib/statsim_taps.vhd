-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
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


-- statsim_pl_rc -- RC-in-path 2-port wire element. Straddles the driver (near)
-- node `a` and the receiver (far) node `b`: the receiver sees the RC-delayed
-- forward probability while the driver sees the wire+fan-out C as backward load.
-- Pulls the routing R-C into the driver->receiver path (vs a lumped load at the
-- driver). resolve_pl and the generated cells are unchanged.
library ieee;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_pl_rc is
    generic ( C     : real := 0.0;       -- routing wire capacitance (F)
              R     : real := 0.0;       -- routing wire series resistance (ohm)
              ALPHA : real := 0.5 );     -- far-cap fraction (0.5 pi/Elmore; 1.0 legacy anchor)
    port ( a : inout resolved_pl;                -- near / driver node
           b : inout resolved_pl := PL_FLOAT );  -- far / receiver node
end entity;

architecture pwl of statsim_pl_rc is
begin
    -- BACKWARD: reflect wire C + downstream receiver load onto the driver node.
    -- gdrv=0 (no forward vote, never tears net_a); rwire=0 (the wire R lives in the
    -- forward flight delay below, so the driver delay isn't double-counted).
    -- maximum(.,0): guard the startup-transient garbage read of an unresolved
    -- record (a capacitance is never negative).
    a <= PL_WIRE(C + maximum(b.cload, 0.0), 0.0);

    -- FORWARD: TRANSPORT-schedule an RC-delayed, series-R-degraded copy of a's
    -- simplex onto b. Sensitive to `a` ONLY (never self-retriggers on its own b
    -- write); reads the topology-static b.cload. px passes through verbatim.
    process(a)
        variable cfar, twr : real;
        variable td : time;
    begin
        cfar := ALPHA * C + maximum(b.cload, 0.0);   -- far cap charged through R (>=0 guard)
        twr  := LN2 * R * cfar;                      -- wire flight delay (s)
        td   := integer(maximum(twr, TPD_FLOOR) * 1.0e15) * 1 fs;   -- >= 1 fs => no zero-delay loop
        b <= transport (a.p0, a.p1, a.px, g_series(a.gdrv, R), 0.0, 0.0) after td;
    end process;
end architecture;
