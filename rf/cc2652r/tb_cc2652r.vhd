-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- tb_cc2652r: ble_phy_pkg against ble_phy.py (the reference packets cc2652r_vhdl.py wrote into
-- cc2652r_pkg), and a packet of each PHY from one CC2652R to another through 70 dB of loss, the two
-- crystals 20 ppm apart.  Prints "TB <what> ok" lines and "TB done failures=<n>".
-- The bench resolves its own two pins (tb_cc2652r_pad, the attenuator between them): no generated network.
--     nvc --std=2040 -a ... tb_cc2652r.vhd -e tb_cc2652r -r        (ble_nvc.py --selftest does it)
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;
use work.cc2652r_spectral_pkg.all;

entity tb_cc2652r_dut is
end entity;

architecture sim of tb_cc2652r_dut is
    signal pin_a, pin_b : std_logic;
    signal cfg_a, cfg_b : cc2652r_config := cc2652r_default_config;
    signal tx_a, tx_b, rx_a, rx_b : cc2652r_packet := CC2652R_NO_PACKET;
    signal busy_a, busy_b : boolean;
begin
    a: entity work.cc2652r generic map (seed => 5)
        port map (ant => pin_a, cfg => cfg_a, tx => tx_a, tx_busy => busy_a, rx => rx_a);
    b: entity work.cc2652r generic map (seed => 9)
        port map (ant => pin_b, cfg => cfg_b, tx => tx_b, tx_busy => busy_b, rx => rx_b);

    process
        variable failures : natural := 0;
        variable c : cc2652r_config;
        variable seq : natural := 0;

        procedure check(what : string; ok : boolean) is
        begin
            if ok then
                report "TB " & what & " ok";
            else
                report "TB " & what & " DIFFERS";
                failures := failures + 1;
            end if;
        end procedure;
    begin
        check("packet symbols LE 1M", ble_packet_symbols(PHY_1M, CC_REF_PDU, CC_REF_CHANNEL, BLE_ADV_AA, BLE_CRC_INIT_ADV) = CC_REF_SYMBOLS_1M);
        check("packet symbols LE 2M", ble_packet_symbols(PHY_2M, CC_REF_PDU, CC_REF_CHANNEL, BLE_ADV_AA, BLE_CRC_INIT_ADV) = CC_REF_SYMBOLS_2M);
        check("packet symbols LE Coded S=2", ble_packet_symbols(PHY_S2, CC_REF_PDU, CC_REF_CHANNEL, BLE_ADV_AA, BLE_CRC_INIT_ADV) = CC_REF_SYMBOLS_S2);
        check("packet symbols LE Coded S=8", ble_packet_symbols(PHY_S8, CC_REF_PDU, CC_REF_CHANNEL, BLE_ADV_AA, BLE_CRC_INIT_ADV) = CC_REF_SYMBOLS_S8);
        check("test packet PDU (PRBS9)", ble_test_pdu(37) = CC_REF_TEST_PDU);
        for p in ble_phy loop
            c := cc2652r_default_config;
            c.phy := p;
            c.frequency := ble_channel_frequency(CC_REF_CHANNEL);
            c.whiten := CC_REF_CHANNEL;
            c.xo_ppm := 10.0;
            cfg_a <= c;
            c.xo_ppm := -10.0;
            c.rx_on := true;
            cfg_b <= c;
            wait for 100 us;
            seq := seq + 1;
            tx_a <= cc2652r_packet_of(CC_REF_PDU, seq);
            wait on rx_b for 20 ms;
            check("packet " & ble_phy'image(p) & " received", rx_b'event and rx_b.crc_ok and rx_b.len = CC_REF_PDU'length
                  and rx_b.pdu(0 to CC_REF_PDU'length - 1) = CC_REF_PDU);
            check("packet " & ble_phy'image(p) & " RSSI " & to_string(rx_b.rssi, "%.0f") & " dBm", abs(rx_b.rssi + 70.0) <= 1.0);
            wait for 1 ms;
        end loop;
        report "TB done failures=" & integer'image(failures);
        wait;
    end process;
end architecture;

-- the attenuator between the two pins: each hears the other 70 dB down
library ieee;
use ieee.std_logic_1164.all;
use work.rf_spectrum_pkg.all;

entity tb_cc2652r_pad is
end entity;

architecture sim of tb_cc2652r_pad is
    alias a_drv is << signal .tb_cc2652r.dut.a.ant.driver : rf_spectrum >>;
    alias a_oth is << signal .tb_cc2652r.dut.a.ant.other : rf_spectrum >>;
    alias b_drv is << signal .tb_cc2652r.dut.b.ant.driver : rf_spectrum >>;
    alias b_oth is << signal .tb_cc2652r.dut.b.ant.other : rf_spectrum >>;
begin
    process (a_drv, b_drv)
    begin
        b_oth := spec_scale(a_drv, 3.1622776601683794e-4);
        a_oth := spec_scale(b_drv, 3.1622776601683794e-4);
    end process;
end architecture;

entity tb_cc2652r is
end entity;

architecture wrapper of tb_cc2652r is
begin
    dut: entity work.tb_cc2652r_dut;
    pad: entity work.tb_cc2652r_pad;
end architecture;
