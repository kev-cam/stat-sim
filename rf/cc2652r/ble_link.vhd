-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ble_link: Bluetooth LE devices (each a CC2652R, its antenna and a link layer, ble_controller) in an
-- arena, in nvc's
-- --std=2040 spectral event-driven mode.  Two scenarios, the ones of ble_host.py:
--
--   scenario 0  range in Direct Test Mode: a tester at the origin sends `packets` test packets in each
--               window, the device under test stands at d0, d1, ... metres in turn (it moves between
--               windows) and reports what it received in each
--   scenario 1  a beacon (ADV_IND every 100 ms, answers scan requests) at the origin, a neighbour
--               (ADV_NONCONN_IND every 20 ms) and an active scanner (30 ms of every 60 ms) `dist` away
--
-- role: 0 everything in one simulation; federated across the arena, 1 is the transmitting side only
-- (tester; beacon and neighbour) and 2 the other (device under test; scanner).
-- Run through ble_nvc.py (it generates the resolver network with nvc's plugin and tabulates).
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_spectral_pkg.all;
use work.ble_controller_pkg.all;

entity ble_link is
    generic (
        scenario   : natural := 0;
        role       : natural := 0;
        phy_code   : natural := 1;              -- HCI test PHY: 1 LE 1M, 2 LE 2M, 3 Coded S=8, 4 Coded S=2
        rf_channel : natural := 19;
        length     : natural := 37;
        tx_dbm     : real := 0.0;
        packets    : positive := 40;
        d0, d1, d2, d3, d4, d5, d6, d7 : real := -1.0;      -- scenario 0: distances, m (negative: not used)
        dist       : real := 10.0;              -- scenario 1
        run_time   : time := 2 sec;             -- scenario 1
        ppm_a      : real := 0.0;               -- crystal errors of the two sides
        ppm_b      : real := 0.0;
        tx_lead    : time := 0 ns
    );
end entity;

architecture sim of ble_link is
    type phy_table is array (1 to 4) of ble_phy;
    constant PHY_OF : phy_table := (PHY_1M, PHY_2M, PHY_S8, PHY_S2);
    constant phy : ble_phy := PHY_OF(phy_code);
    constant DIST_M : real_vector(0 to 7) := (d0, d1, d2, d3, d4, d5, d6, d7);
    function count_used return natural is
        variable n : natural := 0;
    begin
        for i in DIST_M'range loop
            exit when DIST_M(i) <= 0.0;
            n := n + 1;
        end loop;
        return n;
    end function;
    constant NDIST : natural := count_used;
    constant WINDOW : time := 2 ms + packets * ble_test_interval(phy, length);
    function pick(first, second : ble_controller_kind) return ble_controller_kind is
    begin
        if scenario = 0 then
            return first;
        end if;
        return second;
    end function;
    -- RF nets: the payload is on each pin's 'driver / 'other; the generated resolver network joins them
    signal air, feed_a, feed_b, feed_c : std_logic;
    signal pos_a : rf_position := (0.0, 0.0, 0.0);
    signal pos_b : rf_position := (1.0, 0.0, 0.0);
    signal pos_c : rf_position := (1.0, 2.0, 0.0);
    -- between each chip and its software
    signal cfg_a, cfg_b, cfg_c : cc2652r_config := cc2652r_default_config;
    signal tx_a, tx_b, tx_c, rx_a, rx_b, rx_c : cc2652r_packet := CC2652R_NO_PACKET;
    signal busy_a, busy_b, busy_c : boolean := false;
begin
    assert scenario /= 0 or NDIST > 0 report "ble_link: no distance given (d0, d1, ...)" severity failure;

    -- where the second device is: scenario 0, at each distance in turn (it moves between windows; both
    -- sides of a federation know where it is)
    move: process
    begin
        if scenario = 0 then
            for k in 0 to NDIST - 1 loop
                pos_b <= (DIST_M(k), 0.0, 0.0);
                wait for WINDOW;
            end loop;
        else
            pos_b <= (dist, 0.0, 0.0);
            pos_c <= (dist, 2.0, 0.0);
        end if;
        wait;
    end process;

  -- the tester (scenario 0) or the beacon (scenario 1), at the origin
  side_a: if role /= 2 generate
    chip_a: entity work.cc2652r
        generic map (seed => 11)
        port map (ant => feed_a, cfg => cfg_a, tx => tx_a, tx_busy => busy_a, rx => rx_a);
    ant_a: entity work.rf_spec_antenna_td
        generic map (tx_lead => tx_lead)
        port map (feed => feed_a, air => air, position => pos_a);
    host_a: entity work.ble_controller
        generic map (name => "a", kind => pick(NODE_TEST_TX, NODE_ADVERTISER), seed => 11,
                     address => (16#A6#, 16#A5#, 16#A4#, 16#A3#, 16#A2#, 16#C1#), tx_dbm => tx_dbm, xo_ppm => ppm_a,
                     run_time => run_time, phy => phy, rf_channel => rf_channel, length => length, packets => packets,
                     window => WINDOW, windows => NDIST,
                     adv_interval => 100 ms, scannable => true, adv_data_len => 11, rsp_data_len => 6)
        port map (cfg => cfg_a, tx => tx_a, tx_busy => busy_a, rx => rx_a);
  end generate;

  -- the neighbour (scenario 1), next to the second device
  side_c: if role /= 2 and scenario = 1 generate
    chip_c: entity work.cc2652r
        generic map (seed => 37)
        port map (ant => feed_c, cfg => cfg_c, tx => tx_c, tx_busy => busy_c, rx => rx_c);
    ant_c: entity work.rf_spec_antenna_td
        generic map (tx_lead => tx_lead)
        port map (feed => feed_c, air => air, position => pos_c);
    host_c: entity work.ble_controller
        generic map (name => "c", kind => NODE_ADVERTISER, seed => 37, address => (16#99#, 0, 0, 0, 0, 16#C1#),
                     tx_dbm => tx_dbm, xo_ppm => ppm_a, run_time => run_time,
                     adv_interval => 20 ms, scannable => false, adv_data_len => 31)
        port map (cfg => cfg_c, tx => tx_c, tx_busy => busy_c, rx => rx_c);
  end generate;

  -- the device under test (scenario 0) or the scanner (scenario 1)
  side_b: if role /= 1 generate
    chip_b: entity work.cc2652r
        generic map (seed => 23)
        port map (ant => feed_b, cfg => cfg_b, tx => tx_b, tx_busy => busy_b, rx => rx_b);
    ant_b: entity work.rf_spec_antenna_td
        generic map (tx_lead => tx_lead)
        port map (feed => feed_b, air => air, position => pos_b);
    host_b: entity work.ble_controller
        generic map (name => "b", kind => pick(NODE_TEST_RX, NODE_SCANNER), seed => 23,
                     address => (16#55#, 16#44#, 16#33#, 16#22#, 16#11#, 16#C0#), tx_dbm => tx_dbm, xo_ppm => ppm_b,
                     run_time => run_time, phy => phy, rf_channel => rf_channel, length => length, packets => packets,
                     window => WINDOW, windows => NDIST,
                     scan_interval => 60 ms, scan_window => 30 ms, active => true)
        port map (cfg => cfg_b, tx => tx_b, tx_busy => busy_b, rx => rx_b);
  end generate;
end architecture;
