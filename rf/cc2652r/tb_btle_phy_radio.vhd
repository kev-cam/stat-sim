-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- tb_btle_phy_radio: a CC2652R (a) and btle_phy_radio (b) pin to pin through 70 dB: packets each way
-- on an advertising and on a data channel, and the timing of b against a's (which is exact).  The third
-- packet is one that shows the baseband's cut-off last symbol (btle_phy_radio.vhd): without tx_tail
-- the CC2652R takes its CRC as wrong.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;
use work.cc2652r_spectral_pkg.all;
use work.ble_ll_pkg.all;
use work.btle_phy_radio_pkg.all;

entity tb_btle_phy_radio_dut is
    generic (rx_hit_delay : time := 1625 ns; start_parity : natural := 0; tx_tail : boolean := false);
end entity;

architecture sim of tb_btle_phy_radio_dut is
    signal pin_a, pin_b : std_logic;
    signal cfg_a, cfg_b : cc2652r_config := cc2652r_default_config;
    signal tx_a, tx_b, rx_a, rx_b : cc2652r_packet := CC2652R_NO_PACKET;
    signal busy_a, busy_b : boolean;
begin
    a: entity work.cc2652r generic map (seed => 5)
        port map (ant => pin_a, cfg => cfg_a, tx => tx_a, tx_busy => busy_a, rx => rx_a);
    b: entity work.btle_phy_radio generic map (seed => 9, rx_hit_delay => rx_hit_delay, start_parity => start_parity, tx_tail => tx_tail, debug => false)
        port map (ant => pin_b, cfg => cfg_b, tx => tx_b, tx_busy => busy_b, rx => rx_b);

    process
        variable failures : natural := 0;
        variable c : cc2652r_config;
        variable seq : natural := 0;
        variable t0 : time;
        constant ADV : ble_octets := (16#42#, 9, 16#C1#, 16#A2#, 16#A3#, 16#A4#, 16#A5#, 16#A6#, 2, 1, 6);
        constant DATA : ble_octets := (16#0E#, 7, 3, 0, 4, 0, 16#02#, 23, 0);
        constant LONG : ble_octets := (16#40#, 17, 16#55#, 16#44#, 16#33#, 16#22#, 16#11#, 16#C0#, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10);

        procedure check(what : string; ok : boolean) is
        begin
            if ok then
                report "TB " & what & " ok";
            else
                report "TB " & what & " DIFFERS";
                failures := failures + 1;
            end if;
        end procedure;

        procedure both_ways(name : string; pdu : ble_octets; ch : natural; aa : bit_vector(0 to 31); crc : natural;
                            cut : boolean := false) is
        begin
            c := cc2652r_default_config;
            c.frequency := ble_channel_frequency(ch);
            c.whiten := ch;
            c.access_address := aa;
            c.crc_init := crc;
            c.xo_ppm := 10.0;
            cfg_a <= c;
            c.xo_ppm := -10.0;
            c.rx_on := true;
            cfg_b <= c;
            wait for 100 us;
            seq := seq + 1;
            t0 := now;
            tx_a <= cc2652r_packet_of(pdu, seq);
            wait on rx_b for 5 ms;
            check(name & " to the baseband", rx_b'event and rx_b.crc_ok and rx_b.len = pdu'length and rx_b.pdu(0 to pdu'length - 1) = pdu);
            report "TB " & name & " baseband t_end error " & to_string(real((rx_b.t_end - t0 - ble_packet_time(PHY_1M, pdu'length)) / 1 ns) / 1000.0, "%.3f")
                & " us, RSSI " & to_string(rx_b.rssi, "%.0f") & " dBm";
            wait for 1 ms;
            c.rx_on := false;
            cfg_b <= c;
            c.xo_ppm := 10.0;
            c.rx_on := true;
            cfg_a <= c;
            wait for 100 us;
            seq := seq + 1;
            t0 := now;
            tx_b <= cc2652r_packet_of(pdu, seq);
            wait on rx_a for 5 ms;
            if cut and not tx_tail then
                -- a packet whose last CRC bit the modulator's cut-off last symbol loses
                check(name & " from the baseband, CRC " & boolean'image(rx_a.crc_ok) & " (its modulator cuts the last symbol off)",
                      rx_a'event and rx_a.len = pdu'length and rx_a.pdu(0 to pdu'length - 1) = pdu);
            else
                check(name & " from the baseband", rx_a'event and rx_a.crc_ok and rx_a.len = pdu'length and rx_a.pdu(0 to pdu'length - 1) = pdu);
            end if;
            report "TB " & name & " baseband tx delay " & to_string(real((rx_a.t_end - t0 - ble_packet_time(PHY_1M, pdu'length)) / 1 ns) / 1000.0, "%.3f")
                & " us (BTLE_TX_DELAY " & to_string(real(BTLE_TX_DELAY / 1 ns) / 1000.0, "%.3f") & "), RSSI " & to_string(rx_a.rssi, "%.0f") & " dBm";
            check(name & " tx delay within 0.25 us of BTLE_TX_DELAY", abs(rx_a.t_end - t0 - ble_packet_time(PHY_1M, pdu'length) - BTLE_TX_DELAY) <= 250 ns);
            wait for 1 ms;
        end procedure;
    begin
        both_ways("advertisement", ADV, 37, BLE_ADV_AA, BLE_CRC_INIT_ADV);
        both_ways("data packet", DATA, 9, ble_bits_of((16#B7#, 16#4A#, 16#65#, 16#50#)), 16#17B2C5#);
        both_ways("ADV_IND of 19 octets", LONG, 37, BLE_ADV_AA, BLE_CRC_INIT_ADV, cut => true);
        report "TB done failures=" & integer'image(failures);
        std.env.finish;
    end process;
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use work.rf_spectrum_pkg.all;

entity tb_btle_phy_radio_pad is
end entity;

architecture sim of tb_btle_phy_radio_pad is
    alias a_drv is << signal .tb_btle_phy_radio.dut.a.ant.driver : rf_spectrum >>;
    alias a_oth is << signal .tb_btle_phy_radio.dut.a.ant.other : rf_spectrum >>;
    alias b_drv is << signal .tb_btle_phy_radio.dut.b.ant.driver : rf_spectrum >>;
    alias b_oth is << signal .tb_btle_phy_radio.dut.b.ant.other : rf_spectrum >>;
begin
    process (a_drv, b_drv)
    begin
        b_oth := spec_scale(a_drv, 3.1622776601683794e-4);
        a_oth := spec_scale(b_drv, 3.1622776601683794e-4);
    end process;
end architecture;

entity tb_btle_phy_radio is
    generic (rx_hit_delay : time := 1625 ns; start_parity : natural := 0; tx_tail : boolean := false);
end entity;

architecture wrapper of tb_btle_phy_radio is
begin
    dut: entity work.tb_btle_phy_radio_dut generic map (rx_hit_delay => rx_hit_delay, start_parity => start_parity, tx_tail => tx_tail);
    pad: entity work.tb_btle_phy_radio_pad;
end architecture;
