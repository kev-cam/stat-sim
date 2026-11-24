-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ble_tester: a Bluetooth LE central (master) and the little of a host above it that tests a peripheral
-- over the air.  It is the software of a CC2652R (entity cc2652r), like ble_controller; the device
-- under test is anything that advertises in the same arena, in this simulation or in another one of
-- the federation.  One pass, each step reporting a line
--
--     BLE tester test=<step> verdict=PASS|FAIL <what was measured>
--
--   adv        `adv_observe` ADV_INDs of the device on channel 37: the advertising interval (20 ms or
--              more, advDelay within 10 ms)
--   adv_chan   it is heard on channels 38 and 39 too
--   scan       `scan_count` SCAN_REQs: each answered by a SCAN_RSP, T_IFS (150 us) later within 2 us
--   connect    CONNECT_IND; the device answers the first packets of the connection
--   version    LL_VERSION_IND exchange
--   features   LL_FEATURE_REQ / LL_FEATURE_RSP
--   mtu        ATT Exchange MTU                          } host_tests: the device has a host
--   services   GATT primary service discovery            } (BLE tester service ... for each)
--   per        `per_events` connection events of empty packets: those not answered, or with a bad CRC
--   t_ifs      the device's T_IFS over the whole connection
--   terminate  LL_TERMINATE_IND is acknowledged
--   summary    the count of the steps
--
-- Times are those at the tester's antenna pin; path_delay (the set-up knows it) is taken out of a
-- measured T_IFS twice, which leaves the device's own.
-- LE 1M only; one packet each way in a connection event; channel selection algorithm #1.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.ble_phy_pkg.all;
use work.ble_ll_pkg.all;
use work.cc2652r_spectral_pkg.all;

entity ble_tester is
    generic (
        name       : string := "tester";
        address    : ble_octets(0 to 5) := (16#01#, 16#E5#, 16#7E#, 16#57#, 16#E5#, 16#C0#);
        any_target : boolean := true;                   -- test the first device heard advertising connectably
        target     : ble_octets(0 to 5) := (others => 0);
        tx_dbm     : real := 0.0;
        xo_ppm     : real := 0.0;
        path_delay : time := 0 ns;                      -- to the device, one way: taken out of the T_IFS measured
        run_time   : time := 2 sec;                     -- give up then
        adv_observe : positive := 4;
        scan_count : natural := 3;
        host_tests : boolean := true;
        per_events : natural := 40;
        -- the connection it makes
        access_address : ble_octets(0 to 3) := (16#B7#, 16#4A#, 16#65#, 16#50#);       -- 0x50654AB7
        crc_init   : natural := 16#17B2C5#;
        conn_interval : positive := 8;                  -- 1.25 ms
        supervision : positive := 50;                   -- 10 ms
        hop        : positive := 7;
        channel_map : bit_vector(0 to 36) := (others => '1');
        rsp_events : positive := 20                     -- connection events to wait for a response
    );
    port (
        cfg     : out cc2652r_config := cc2652r_default_config;
        tx      : out cc2652r_packet := CC2652R_NO_PACKET;
        tx_busy : in boolean;
        rx      : in cc2652r_packet
    );
end entity;

architecture sim of ble_tester is
    constant PHY : ble_phy := PHY_1M;
    constant INTERVAL : time := conn_interval * 1250 us;
    constant PARAMS : ble_conn_params := (aa => access_address, crc_init => crc_init, win_size => 1, win_offset => 0,
                                          interval => conn_interval, latency => 0, timeout => supervision,
                                          chm => channel_map, hop => hop, sca => 0);
begin
    assert ble_aa_valid(access_address) report "ble_tester: the access address breaks the specification's rules" severity failure;
    assert hop >= 5 and hop <= 16 report "ble_tester: hop is 5 to 16" severity failure;

    process
        variable c : cc2652r_config := cc2652r_default_config;
        variable seq, passed, failed : natural := 0;
        variable t_tx_end : time := 0 fs;               -- the end of the packet last sent
        variable dut : ble_octets(0 to 5) := target;
        variable dut_add : natural := 0;                -- its TxAdd
        variable have_dut : boolean := not any_target;
        variable got : boolean;
        -- advertising
        variable t_start, t_prev, t_listen, t_limit : time;
        variable n_adv, n_rsp, n_req : natural := 0;
        variable iv, iv_min, iv_max, rssi_sum : real := 0.0;
        variable heard : bit_vector(37 to 39) := (others => '0');
        variable ifs, ifs_min, ifs_max : real := 0.0;
        variable n_ifs : natural := 0;
        -- connection
        variable l : ble_link_state;
        variable anchor : time;
        variable unmapped, ev, ev_missed, ev_bad, ev_first : natural := 0;
        variable in_valid : boolean := false;           -- a new payload arrived: in_llid, in_len, in_data
        variable in_llid, in_len : natural := 0;
        variable in_data : ble_octets(0 to BLE_DATA_MAX - 1);
        variable pdu : ble_octets(0 to BLE_DATA_MAX + 1);
        variable n, start_h, end_h, n_services, k, m0, b0 : natural := 0;
        variable ok, done : boolean;

        function flag(b : bit) return string is
        begin
            if b = '1' then
                return "1";
            end if;
            return "0";
        end function;

        function us(t : time) return real is
        begin
            return real(t / 1 ns) / 1000.0;
        end function;

        function ms(t : time) return real is
        begin
            return real(t / 1 us) / 1000.0;
        end function;

        impure function on_adv(ch : natural; rx_on : boolean) return cc2652r_config is
            variable r : cc2652r_config := c;
        begin
            r.frequency := ble_channel_frequency(ch);
            r.whiten := ch;
            r.rx_on := rx_on;
            r.access_address := BLE_ADV_AA;
            r.crc_init := BLE_CRC_INIT_ADV;
            return r;
        end function;

        impure function on_data(ch : natural; rx_on : boolean) return cc2652r_config is
            variable r : cc2652r_config := c;
        begin
            r.frequency := ble_channel_frequency(ch);
            r.whiten := ch;
            r.rx_on := rx_on;
            r.access_address := ble_bits_of(access_address);
            r.crc_init := crc_init;
            return r;
        end function;

        procedure send(p : ble_octets) is
        begin
            seq := seq + 1;
            t_tx_end := now + ble_packet_time(PHY, p'length);
            tx <= cc2652r_packet_of(p, seq);
            wait until tx_busy;
            wait until not tx_busy;
        end procedure;

        procedure verdict(test : string; pass : boolean; detail : string) is
        begin
            if pass then
                passed := passed + 1;
                report "BLE tester test=" & test & " verdict=PASS " & detail;
            else
                failed := failed + 1;
                report "BLE tester test=" & test & " verdict=FAIL " & detail;
            end if;
        end procedure;

        procedure summary is
        begin
            cfg <= on_adv(37, false);
            if failed = 0 then
                report "BLE tester test=summary verdict=PASS passed=" & integer'image(passed) & " failed=0";
            else
                report "BLE tester test=summary verdict=FAIL passed=" & integer'image(passed) & " failed=" & integer'image(failed);
            end if;
        end procedure;

        -- Listen on advertising channel ch until t_stop for an advertisement of the device under test
        -- (the first connectable one heard becomes it); found: it is in rx.
        procedure hear_adv(ch : natural; t_stop : time; found : out boolean) is
        begin
            found := false;
            cfg <= on_adv(ch, true);
            while now < t_stop loop
                wait on rx for t_stop - now;
                if rx'event and rx.crc_ok and rx.len >= 8 and rx.pdu(0) mod 16 = BLE_ADV_IND
                   and (not have_dut or rx.pdu(2 to 7) = dut) then
                    if not have_dut then
                        dut := rx.pdu(2 to 7);
                        have_dut := true;
                    end if;
                    dut_add := (rx.pdu(0) / 64) mod 2;
                    found := true;
                    exit;
                end if;
            end loop;
        end procedure;

        procedure note_ifs(t_pkt_start : time) is
        begin
            ifs := us(t_pkt_start - t_tx_end - 2 * path_delay);
            if n_ifs = 0 or ifs < ifs_min then
                ifs_min := ifs;
            end if;
            if n_ifs = 0 or ifs > ifs_max then
                ifs_max := ifs;
            end if;
            n_ifs := n_ifs + 1;
        end procedure;

        -- One connection event: the current PDU at the anchor point, then the device's answer.
        procedure conn_event is
            variable ch : natural;
            variable fresh : boolean;
        begin
            cc_wait_until(anchor);
            unmapped := (unmapped + hop) mod 37;
            ch := ble_data_channel(unmapped, channel_map);
            cfg <= on_data(ch, false);
            ble_link_transmit(l, pdu, n);
            send(pdu(0 to n - 1));
            cfg <= on_data(ch, true);
            t_listen := t_tx_end + BLE_T_IFS + ble_packet_time(PHY, BLE_DATA_MAX + 2) + 60 us;
            got := false;
            while now < t_listen loop
                wait on rx for t_listen - now;
                if rx'event then
                    got := true;
                    if rx.crc_ok then
                        note_ifs(rx.t_end - ble_packet_time(PHY, rx.len));
                        rssi_sum := rssi_sum + rx.rssi;
                        ble_link_receive(l, rx.pdu(0), fresh);
                        if fresh and rx.len > 2 and rx.len <= BLE_DATA_MAX + 2 then
                            in_valid := true;
                            in_llid := rx.pdu(0) mod 4;
                            in_len := rx.len - 2;
                            in_data(0 to in_len - 1) := rx.pdu(2 to rx.len - 1);
                        end if;
                    else
                        ev_bad := ev_bad + 1;
                    end if;
                    exit;
                end if;
            end loop;
            if not got then
                ev_missed := ev_missed + 1;
            end if;
            cfg <= on_data(ch, false);
            ev := ev + 1;
            anchor := anchor + INTERVAL;
        end procedure;

        -- Send a payload and run connection events until a new one comes back (in_*), or rsp_events pass.
        procedure exchange(llid : natural; payload : ble_octets; answered : out boolean) is
        begin
            in_valid := false;
            ble_link_push(l, llid, payload);
            for i in 1 to rsp_events loop
                conn_event;
                exit when in_valid;
            end loop;
            answered := in_valid;
        end procedure;

        impure function is_att(op : natural) return boolean is
        begin
            return in_valid and in_llid = BLE_LLID_START and in_len >= 5 and in_data(2) = BLE_CID_ATT and in_data(3) = 0
                and in_data(4) = op;
        end function;

        impure function is_ctrl(op : natural) return boolean is
        begin
            return in_valid and in_llid = BLE_LLID_CTRL and in_len >= 1 and in_data(0) = op;
        end function;

        impure function got_what return string is
        begin
            if not in_valid then
                return "response=none";
            end if;
            return "response=" & ble_hex(in_data(0 to in_len - 1)) & " llid=" & integer'image(in_llid);
        end function;
    begin
        c.tx_power := tx_dbm;
        c.xo_ppm := xo_ppm;
        c.phy := PHY;
        cfg <= on_adv(37, false);

        ---------------------------------------------------------------- advertising, channel 37
        t_prev := 0 fs;
        while n_adv < adv_observe loop
            hear_adv(37, run_time, got);
            exit when not got;
            t_start := rx.t_end - ble_packet_time(PHY, rx.len);
            rssi_sum := rssi_sum + rx.rssi;
            if n_adv > 0 then
                iv := ms(t_start - t_prev);
                if n_adv = 1 or iv < iv_min then
                    iv_min := iv;
                end if;
                if n_adv = 1 or iv > iv_max then
                    iv_max := iv;
                end if;
            end if;
            t_prev := t_start;
            n_adv := n_adv + 1;
        end loop;
        if n_adv = 0 then
            verdict("adv", false, "seen=0");
            summary;
            wait;
        end if;
        verdict("adv", n_adv = adv_observe and (n_adv < 2 or (iv_min >= 20.0 and iv_max - iv_min <= 10.0)),
                "address=" & ble_hex((dut(5), dut(4), dut(3), dut(2), dut(1), dut(0))) & " seen=" & integer'image(n_adv) & " interval_min_ms=" & to_string(iv_min, "%.3f")
                & " interval_max_ms=" & to_string(iv_max, "%.3f") & " rssi=" & to_string(rssi_sum / real(n_adv), "%.1f"));
        rssi_sum := 0.0;

        ---------------------------------------------------------------- the other advertising channels
        heard(37) := '1';
        for ch in 38 to 39 loop
            t_limit := now + integer(3.0 * iv_max + 40.0) * 1 ms;
            if t_limit > run_time then
                t_limit := run_time;
            end if;
            hear_adv(ch, t_limit, got);
            if got then
                heard(ch) := '1';
            end if;
        end loop;
        verdict("adv_chan", heard = "111", "ch37=1 ch38=" & flag(heard(38)) & " ch39=" & flag(heard(39)));

        ---------------------------------------------------------------- active scanning
        n_ifs := 0;
        for i in 1 to scan_count loop
            hear_adv(37, run_time, got);
            exit when not got;
            cc_wait_until(rx.t_end + BLE_T_IFS);
            cfg <= on_adv(37, false);
            send(ble_adv_pdu(BLE_SCAN_REQ, address & dut, tx_add => 1, rx_add => dut_add));
            n_req := n_req + 1;
            cfg <= on_adv(37, true);
            t_listen := now + BLE_T_IFS + ble_packet_time(PHY, 39) + 60 us;
            while now < t_listen loop
                wait on rx for t_listen - now;
                if rx'event then
                    if rx.crc_ok and rx.len >= 8 and rx.pdu(0) mod 16 = BLE_SCAN_RSP and rx.pdu(2 to 7) = dut then
                        n_rsp := n_rsp + 1;
                        note_ifs(rx.t_end - ble_packet_time(PHY, rx.len));
                    end if;
                    exit;
                end if;
            end loop;
        end loop;
        if scan_count > 0 then
            verdict("scan", n_rsp = scan_count and abs(ifs_min - 150.0) <= 2.0 and abs(ifs_max - 150.0) <= 2.0,
                    "requests=" & integer'image(n_req) & " responses=" & integer'image(n_rsp)
                    & " t_ifs_min_us=" & to_string(ifs_min, "%.2f") & " t_ifs_max_us=" & to_string(ifs_max, "%.2f"));
        end if;

        ---------------------------------------------------------------- connect
        hear_adv(37, run_time, got);
        if not got then
            verdict("connect", false, "advertising=none");
            summary;
            wait;
        end if;
        cc_wait_until(rx.t_end + BLE_T_IFS);
        cfg <= on_adv(37, false);
        send(ble_connect_pdu(address, dut, PARAMS, tx_add => 1, rx_add => dut_add));
        -- the transmit window opens 1.25 ms after the CONNECT_IND and is 1.25 ms long
        anchor := t_tx_end + 1250 us + 300 us;
        ble_link_reset(l);
        n_ifs := 0;
        ifs_min := 0.0;
        ifs_max := 0.0;
        got := false;
        for i in 1 to 6 loop                            -- the specification's limit to establish it
            conn_event;
            exit when got;
        end loop;
        ev_first := ev;
        verdict("connect", got, "answered_in_event=" & integer'image(ev - 1) & " interval_ms=" & to_string(ms(INTERVAL), "%.2f")
                & " access_address=" & ble_hex((access_address(3), access_address(2), access_address(1), access_address(0))));
        if not got then
            summary;
            wait;
        end if;

        ---------------------------------------------------------------- link layer control
        exchange(BLE_LLID_CTRL, (BLE_LL_VERSION_IND, 16#0F#, 16#FF#, 16#FF#, 0, 0), ok);
        if is_ctrl(BLE_LL_VERSION_IND) and in_len = 6 then
            verdict("version", true, "version=" & integer'image(in_data(1)) & " company=" & ble_hex((in_data(3), in_data(2)))
                    & " subversion=" & ble_hex((in_data(5), in_data(4))));
        else
            verdict("version", false, got_what);
        end if;
        exchange(BLE_LLID_CTRL, (BLE_LL_FEATURE_REQ, 0, 0, 0, 0, 0, 0, 0, 0), ok);
        if is_ctrl(BLE_LL_FEATURE_RSP) and in_len = 9 then
            verdict("features", true, "features=" & ble_hex((in_data(8), in_data(7), in_data(6), in_data(5), in_data(4), in_data(3),
                                                               in_data(2), in_data(1))));
        else
            verdict("features", false, got_what);
        end if;

        ---------------------------------------------------------------- the device's host
        if host_tests then
            exchange(BLE_LLID_START, ble_l2cap(BLE_CID_ATT, (BLE_ATT_MTU_REQ, 23, 0)), ok);
            if is_att(BLE_ATT_MTU_RSP) and in_len = 7 then
                verdict("mtu", in_data(5) + 256 * in_data(6) >= 23, "mtu=" & integer'image(in_data(5) + 256 * in_data(6)));
            else
                verdict("mtu", false, got_what);
            end if;
            start_h := 1;
            done := false;
            ok := true;
            while not done and n_services < 16 loop
                exchange(BLE_LLID_START, ble_l2cap(BLE_CID_ATT, (BLE_ATT_READ_BY_GROUP_REQ, start_h mod 256, start_h / 256,
                                                                 16#FF#, 16#FF#, 16#00#, 16#28#)), got);
                if is_att(BLE_ATT_READ_BY_GROUP_RSP) and in_len >= 12 and in_data(5) = 6 then
                    k := 6;
                    while k + 6 <= in_len loop
                        end_h := in_data(k + 2) + 256 * in_data(k + 3);
                        report "BLE tester service start=" & integer'image(in_data(k) + 256 * in_data(k + 1)) & " end="
                            & integer'image(end_h) & " uuid=" & ble_hex((in_data(k + 5), in_data(k + 4)));
                        n_services := n_services + 1;
                        k := k + 6;
                    end loop;
                    done := end_h = 16#FFFF#;
                    start_h := end_h + 1;
                elsif is_att(BLE_ATT_ERROR_RSP) and in_len = 9 and in_data(8) = 16#0A# then
                    done := true;                       -- Attribute Not Found: no more
                else
                    ok := false;
                    done := true;
                end if;
            end loop;
            if ok then
                verdict("services", n_services > 0, "found=" & integer'image(n_services));
            else
                verdict("services", false, "found=" & integer'image(n_services) & " " & got_what);
            end if;
        end if;

        ---------------------------------------------------------------- packet errors
        m0 := ev_missed;
        b0 := ev_bad;
        for i in 1 to per_events loop
            conn_event;
        end loop;
        if per_events > 0 then
            verdict("per", real(ev_missed - m0 + ev_bad - b0) < 0.308 * real(per_events),
                    "events=" & integer'image(per_events) & " not_answered=" & integer'image(ev_missed - m0)
                    & " crc_errors=" & integer'image(ev_bad - b0));
        end if;
        if n_ifs > 0 then
            verdict("t_ifs", abs(ifs_min - 150.0) <= 2.0 and abs(ifs_max - 150.0) <= 2.0,
                    "packets=" & integer'image(n_ifs) & " t_ifs_min_us=" & to_string(ifs_min, "%.2f") & " t_ifs_max_us="
                    & to_string(ifs_max, "%.2f") & " rssi=" & to_string(rssi_sum / real(n_ifs), "%.1f"));
        end if;

        ---------------------------------------------------------------- terminate
        ble_link_push(l, BLE_LLID_CTRL, (BLE_LL_TERMINATE_IND, 16#13#));       -- Remote User Terminated Connection
        for i in 1 to rsp_events loop
            conn_event;
            exit when ble_link_idle(l);
        end loop;
        verdict("terminate", ble_link_idle(l), "events=" & integer'image(ev) & " not_answered=" & integer'image(ev_missed)
                & " crc_errors=" & integer'image(ev_bad));
        summary;
        wait;
    end process;
end architecture;
