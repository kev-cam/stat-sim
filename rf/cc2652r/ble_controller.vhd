-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ble_controller: the part of a Bluetooth LE controller's link layer that `kind` asks for, as the
-- software of a CC2652R (entity cc2652r: it drives the chip's cfg and tx and reads its rx); the VHDL of
-- ble_host.py's Controller.  Times and packets are the Bluetooth Core Specification's (Vol 6 Parts B, F):
--
--   NODE_TEST_TX     Direct Test Mode transmitter: in each of `windows` windows of `window`, `packets`
--                    PRBS9 packets of `length` octets, one every test interval, from 1 ms into the window
--   NODE_TEST_RX     Direct Test Mode receiver; reports at the end of each window
--                       BLE test node=<name> window=<k> received=<n> crc_errors=<n> rssi=<mean dBm>
--   NODE_ADVERTISER  legacy advertising every adv_interval + advDelay (0 - 10 ms) on channels 37, 38, 39:
--                    ADV_IND (scannable: answers a SCAN_REQ with a SCAN_RSP) or ADV_NONCONN_IND
--   NODE_SCANNER     scanning, scan_window of every scan_interval, the channel stepping 37, 38, 39;
--                    active: sends a SCAN_REQ to what can be scanned and waits for the SCAN_RSP
--
-- Advertisers and scanners report when run_time is over:
--   BLE adv node=<name> events=<n> scan_requests=<n> scan_responses=<n>
--   BLE scan node=<name> from=<last octet of the advertiser's address> adv_ind=<n> adv_nonconn_ind=<n> scan_rsp=<n> rssi=<mean dBm>
--   BLE scan node=<name> scan_requests=<n> crc_errors=<n>
-- Not modelled: connections, extended advertising, the scanner's backoff, filter policies.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;
use work.cc2652r_spectral_pkg.all;

package ble_controller_pkg is
    type ble_controller_kind is (NODE_TEST_TX, NODE_TEST_RX, NODE_ADVERTISER, NODE_SCANNER);
    constant BLE_ADV_SPACING : time := 1500 us;         -- between the PDUs of one advertising event (limit: 10 ms)
    -- Direct Test Mode: one packet every this long (the packet and 249 us, rounded up to 625 us)
    function ble_test_interval(phy : ble_phy; length : natural) return time;
end package;

package body ble_controller_pkg is
    function ble_test_interval(phy : ble_phy; length : natural) return time is
        constant d : real := real(ble_packet_symbol_count(phy, length + 2)) / ble_symbol_rate(phy);
    begin
        return integer(ceil((d + 249.0e-6) / 625.0e-6)) * 625 us;
    end function;
end package body;

library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;
use work.cc2652r_spectral_pkg.all;
use work.ble_controller_pkg.all;

entity ble_controller is
    generic (
        name      : string := "node";
        kind      : ble_controller_kind := NODE_TEST_RX;
        seed      : positive := 1;
        address   : ble_octets(0 to 5) := (1, 0, 0, 0, 0, 16#C0#);     -- as on the air: least significant octet first
        tx_dbm    : real := 0.0;
        xo_ppm    : real := 0.0;
        run_time  : time := 1 sec;
        -- test modes
        phy       : ble_phy := PHY_1M;
        rf_channel : natural := 19;
        length    : natural := 37;
        packets   : natural := 40;
        window    : time := 100 ms;
        windows   : natural := 1;
        -- advertiser
        adv_interval : time := 100 ms;
        scannable : boolean := true;
        adv_data_len : natural := 11;                   -- octets of advertising data (a counting pattern)
        rsp_data_len : natural := 6;
        -- scanner
        scan_interval : time := 60 ms;
        scan_window : time := 30 ms;
        active    : boolean := true
    );
    port (
        cfg     : out cc2652r_config := cc2652r_default_config;
        tx      : out cc2652r_packet := CC2652R_NO_PACKET;
        tx_busy : in boolean;
        rx      : in cc2652r_packet
    );
end entity;

architecture sim of ble_controller is
    function base_cfg return cc2652r_config is
        variable c : cc2652r_config := cc2652r_default_config;
    begin
        c.tx_power := tx_dbm;
        c.xo_ppm := xo_ppm;
        return c;
    end function;

    function on_channel(c : cc2652r_config; index : natural; rx_on : boolean) return cc2652r_config is
        variable r : cc2652r_config := c;
    begin
        r.frequency := ble_channel_frequency(index);
        r.whiten := index;
        r.rx_on := rx_on;
        return r;
    end function;

    function pattern(n : natural) return ble_octets is
        variable r : ble_octets(0 to n - 1);
    begin
        for i in r'range loop
            r(i) := i;
        end loop;
        return r;
    end function;
begin
    test_tx: if kind = NODE_TEST_TX generate
        process
            constant step : time := ble_test_interval(phy, length);
            variable c : cc2652r_config := base_cfg;
            variable seq : natural := 0;
        begin
            assert 1 ms + packets * step <= window report "ble_controller: the window is too short for the packets" severity failure;
            c.frequency := ble_rf_channel_frequency(rf_channel);
            c.phy := phy;
            c.access_address := BLE_TEST_AA;
            cfg <= c;
            for k in 0 to windows - 1 loop
                cc_wait_until(k * window + 1 ms);
                for p in 0 to packets - 1 loop
                    seq := seq + 1;
                    tx <= cc2652r_packet_of(ble_test_pdu(length), seq);
                    cc_wait_until(k * window + 1 ms + (p + 1) * step);
                end loop;
            end loop;
            wait;
        end process;
    end generate;

    test_rx: if kind = NODE_TEST_RX generate
        process
            variable c : cc2652r_config := base_cfg;
            variable got, bad : natural;
            variable rssi : real;
            variable t_end : time;
        begin
            c.frequency := ble_rf_channel_frequency(rf_channel);
            c.phy := phy;
            c.access_address := BLE_TEST_AA;
            c.rx_on := true;
            cfg <= c;
            for k in 0 to windows - 1 loop
                got := 0;
                bad := 0;
                rssi := 0.0;
                t_end := (k + 1) * window - 100 us;
                while now < t_end loop
                    wait on rx for t_end - now;
                    if rx'event then
                        if rx.crc_ok then
                            got := got + 1;
                            rssi := rssi + rx.rssi;
                        else
                            bad := bad + 1;
                        end if;
                    end if;
                end loop;
                if got > 0 then
                    rssi := rssi / real(got);
                end if;
                report "BLE test node=" & name & " window=" & integer'image(k) & " received=" & integer'image(got)
                    & " crc_errors=" & integer'image(bad) & " rssi=" & to_string(rssi, "%.2f");
            end loop;
            c.rx_on := false;
            cfg <= c;
            wait;
        end process;
    end generate;

    advertiser: if kind = NODE_ADVERTISER generate
        process
            variable c : cc2652r_config := base_cfg;
            variable s1 : positive := seed + 77;
            variable s2 : positive := 2 * seed + 1;
            variable u : real;
            variable seq, events, requests, responses : natural := 0;
            variable t_ev, t_listen : time;
            variable adv : ble_octets(0 to 7 + adv_data_len);
            variable rsp : ble_octets(0 to 7 + rsp_data_len);

            procedure send(pdu : ble_octets) is
            begin
                seq := seq + 1;
                tx <= cc2652r_packet_of(pdu, seq);
                wait until tx_busy;
                wait until not tx_busy;
            end procedure;
        begin
            if scannable then
                adv := ble_adv_pdu(BLE_ADV_IND, address & pattern(adv_data_len), tx_add => 1);
            else
                adv := ble_adv_pdu(BLE_ADV_NONCONN_IND, address & pattern(adv_data_len), tx_add => 1);
            end if;
            rsp := ble_adv_pdu(BLE_SCAN_RSP, address & pattern(rsp_data_len), tx_add => 1);
            cfg <= c;
            uniform(s1, s2, u);
            cc_wait_until(u * adv_interval);
            while now < run_time loop
                t_ev := now;
                events := events + 1;
                for ch in 37 to 39 loop
                    cfg <= on_channel(c, ch, false);
                    send(adv);
                    if scannable then
                        -- a SCAN_REQ starts T_IFS after the advertisement and is 176 us long
                        cfg <= on_channel(c, ch, true);
                        t_listen := now + BLE_T_IFS + 176 us + 60 us;
                        while now < t_listen loop
                            wait on rx for t_listen - now;
                            if rx'event and rx.crc_ok and rx.len = 14 and rx.pdu(0) mod 16 = BLE_SCAN_REQ
                               and rx.pdu(8 to 13) = address then
                                requests := requests + 1;
                                cc_wait_until(rx.t_end + BLE_T_IFS);
                                cfg <= on_channel(c, ch, false);
                                send(rsp);
                                responses := responses + 1;
                                exit;
                            end if;
                        end loop;
                        cfg <= on_channel(c, ch, false);
                    end if;
                    if now < t_ev + (ch - 36) * BLE_ADV_SPACING then
                        cc_wait_until(t_ev + (ch - 36) * BLE_ADV_SPACING);
                    end if;
                end loop;
                uniform(s1, s2, u);
                cc_wait_until(t_ev + adv_interval + u * 10 ms);
            end loop;
            report "BLE adv node=" & name & " events=" & integer'image(events) & " scan_requests=" & integer'image(requests)
                & " scan_responses=" & integer'image(responses);
            wait;
        end process;
    end generate;

    scanner: if kind = NODE_SCANNER generate
        process
            variable c : cc2652r_config := base_cfg;
            type count_t is array (0 to 255) of natural;
            variable n_ind, n_non, n_rsp, n_all : count_t := (others => 0);
            type sum_t is array (0 to 255) of real;
            variable rssi : sum_t := (others => 0.0);
            variable seq, requests, bad, k, ch, typ, who : natural := 0;
            variable t_i, t_w, t_listen : time;
            variable req : ble_octets(0 to 13);
            variable adva : ble_octets(0 to 5);

            procedure send(pdu : ble_octets) is
            begin
                seq := seq + 1;
                tx <= cc2652r_packet_of(pdu, seq);
                wait until tx_busy;
                wait until not tx_busy;
            end procedure;
        begin
            while k * scan_interval < run_time loop
                t_i := k * scan_interval;
                t_w := t_i + scan_window;
                ch := 37 + k mod 3;
                cfg <= on_channel(c, ch, true);
                while now < t_w loop
                    wait on rx for t_w - now;
                    if rx'event then
                        if not rx.crc_ok or rx.len < 8 then
                            bad := bad + 1;
                        else
                            typ := rx.pdu(0) mod 16;
                            who := rx.pdu(2);
                            adva := rx.pdu(2 to 7);
                            if typ = BLE_ADV_NONCONN_IND then
                                n_non(who) := n_non(who) + 1;
                                n_all(who) := n_all(who) + 1;
                                rssi(who) := rssi(who) + rx.rssi;
                            elsif typ = BLE_ADV_IND or typ = BLE_ADV_SCAN_IND then
                                n_ind(who) := n_ind(who) + 1;
                                n_all(who) := n_all(who) + 1;
                                rssi(who) := rssi(who) + rx.rssi;
                                if active then
                                    req := ble_adv_pdu(BLE_SCAN_REQ, address & adva, tx_add => 1, rx_add => (rx.pdu(0) / 64) mod 2);
                                    cc_wait_until(rx.t_end + BLE_T_IFS);
                                    cfg <= on_channel(c, ch, false);
                                    send(req);
                                    requests := requests + 1;
                                    -- the SCAN_RSP starts T_IFS later and is at most 376 us long
                                    cfg <= on_channel(c, ch, true);
                                    t_listen := now + BLE_T_IFS + 376 us + 60 us;
                                    while now < t_listen loop
                                        wait on rx for t_listen - now;
                                        if rx'event then
                                            if rx.crc_ok and rx.len >= 8 and rx.pdu(0) mod 16 = BLE_SCAN_RSP and rx.pdu(2 to 7) = adva then
                                                n_rsp(who) := n_rsp(who) + 1;
                                                n_all(who) := n_all(who) + 1;
                                                rssi(who) := rssi(who) + rx.rssi;
                                            elsif not rx.crc_ok then
                                                bad := bad + 1;
                                            end if;
                                            exit;
                                        end if;
                                    end loop;
                                end if;
                            end if;
                        end if;
                    end if;
                end loop;
                cfg <= on_channel(c, ch, false);
                k := k + 1;
                if now < k * scan_interval then
                    cc_wait_until(k * scan_interval);
                end if;
            end loop;
            for a in 0 to 255 loop
                if n_all(a) > 0 then
                    report "BLE scan node=" & name & " from=" & integer'image(a) & " adv_ind=" & integer'image(n_ind(a))
                        & " adv_nonconn_ind=" & integer'image(n_non(a)) & " scan_rsp=" & integer'image(n_rsp(a))
                        & " rssi=" & to_string(rssi(a) / real(n_all(a)), "%.2f");
                end if;
            end loop;
            report "BLE scan node=" & name & " scan_requests=" & integer'image(requests) & " crc_errors=" & integer'image(bad);
            wait;
        end process;
    end generate;
end architecture;
