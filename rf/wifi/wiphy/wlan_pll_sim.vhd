-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- wlan_pll_sim: a behavioural stand-in for the PLL of bladeRF-wiphy's receiver (component wlan_pll in
-- wlan_rx.vhd: a 40 MHz reference in, the receiver's 80 MHz clock out), so that the modem simulates
-- without the vendor's PLL model.  Compile into the modem's own library (wlan), where the component's
-- default binding finds it.
--
-- The output clock has twice the reference's frequency and is aligned to it.  The period is measured
-- from the reference; `locked` rises once it has been, and the output runs from then on.
--
-- ALIGNED means more here than equal times.  The modem passes signals between the two clocks without
-- a synchroniser (the receiver's controller, on the output clock, takes the acquisition's mark and
-- its estimates straight from the reference clock), which is sound for a PLL's two outputs: at an
-- edge the two clocks share, a register of either clock takes what the other clock's registers held
-- BEFORE the edge.  A simulator gives that only if the two edges fall in the same delta cycle.  So the
-- output's edges are scheduled by time alone, a reference period ahead, and never derived from the
-- reference's edge they coincide with (which would put them a delta cycle after it, and every
-- register of the output clock would then take the reference clock's NEW values).  The reference is
-- taken to have its edges in the first delta cycle of their time, as a clock made by an `after`
-- assignment has.
library ieee;
use ieee.std_logic_1164.all;

entity wlan_pll is
    port (
        refclk   : in  std_logic;
        rst      : in  std_logic;
        outclk_0 : out std_logic := '0';
        locked   : out std_logic);
end entity;

architecture sim of wlan_pll is
    signal known : boolean := false;
begin
    process (refclk)
        variable last_rise : time := -1 ns;
        variable period    : time;
    begin
        if rising_edge(refclk) then
            if last_rise >= 0 ns then
                period := now - last_rise;
                -- the next four edges; the last falls on the reference's next rising edge
                outclk_0 <= transport '0' after period / 4, '1' after period / 2,
                                      '0' after (3 * period) / 4, '1' after period;
                known <= true;
            end if;
            last_rise := now;
        end if;
    end process;

    locked <= '1' when known and rst /= '1' else '0';
end architecture;
