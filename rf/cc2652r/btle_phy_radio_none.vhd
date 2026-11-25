-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- btle_phy_radio, when the BTLE baseband is not there (ble_nvc.py without --dut btle): the entity of
-- btle_phy_radio.vhd with nothing in it, so that ble_link can be compiled.
library ieee;
use ieee.std_logic_1164.all;
use work.cc2652r_spectral_pkg.all;

entity btle_phy_radio is
    generic (
        seed  : positive := 1;
        nf_db : real := 6.0;
        rx_bw : real := 1.0e6;
        rx_hit_delay : time := 1625 ns;
        start_parity : natural := 0;
        tx_tail : boolean := false;
        debug : boolean := false
    );
    port (
        ant     : inout std_logic;
        cfg     : in cc2652r_config;
        tx      : in cc2652r_packet;
        tx_busy : out boolean;
        rx      : out cc2652r_packet
    );
end entity;

architecture none of btle_phy_radio is
begin
    assert false report "btle_phy_radio: compiled without the BTLE baseband (ble_nvc.py --dut btle)" severity failure;
end architecture;
