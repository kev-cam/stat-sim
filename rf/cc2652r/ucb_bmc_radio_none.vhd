-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ucb_bmc_radio, when the Berkeley baseband-modem is not there (ble_nvc.py without --dut bmc): the
-- entity of ucb_bmc_radio.vhd with nothing in it, so that ble_link has something to name.
library ieee;
use ieee.std_logic_1164.all;
use work.cc2652r_spectral_pkg.all;

entity ucb_bmc_radio is
    generic (
        seed  : positive := 1;
        nf_db : real := 6.0;
        rx_bw : real := 1.0e6;
        rx_hit_delay : time := 4250 ns;
        adc_level : real := 0.4;
        tx_end : boolean := false;
        trace : string := "";
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

architecture none of ucb_bmc_radio is
begin
    assert false report "ucb_bmc_radio: compiled without the baseband-modem (ble_nvc.py --dut bmc)" severity failure;
end architecture;
