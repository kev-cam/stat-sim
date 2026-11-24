-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ble_ll_pkg: what a Bluetooth LE connection needs of the link layer (Core Specification 6.1, Vol 6
-- Part B): the CONNECT_IND PDU and its parameters, data channel selection algorithm #1, data physical
-- channel PDUs, their acknowledgement scheme (SN / NESN) with a short transmit queue, and the framing
-- of L2CAP.  Used by both ends: ble_tester (central) and ble_controller's NODE_PERIPHERAL.
library ieee;
use ieee.math_real.all;
use work.ble_phy_pkg.all;

package ble_ll_pkg is
    constant BLE_LLID_CONT  : natural := 1;             -- continuation of an L2CAP message, or an empty PDU
    constant BLE_LLID_START : natural := 2;             -- start of an L2CAP message
    constant BLE_LLID_CTRL  : natural := 3;             -- LL Control PDU
    constant BLE_DATA_MAX   : natural := 27;            -- octets of payload (no data length extension)

    -- LL Control PDU opcodes
    constant BLE_LL_TERMINATE_IND : natural := 16#02#;
    constant BLE_LL_UNKNOWN_RSP   : natural := 16#07#;
    constant BLE_LL_FEATURE_REQ   : natural := 16#08#;
    constant BLE_LL_FEATURE_RSP   : natural := 16#09#;
    constant BLE_LL_VERSION_IND   : natural := 16#0C#;
    constant BLE_LL_PING_REQ      : natural := 16#12#;
    constant BLE_LL_PING_RSP      : natural := 16#13#;

    -- L2CAP channel of the Attribute Protocol, and the ATT opcodes used here
    constant BLE_CID_ATT : natural := 4;
    constant BLE_ATT_ERROR_RSP         : natural := 16#01#;
    constant BLE_ATT_MTU_REQ           : natural := 16#02#;
    constant BLE_ATT_MTU_RSP           : natural := 16#03#;
    constant BLE_ATT_READ_BY_GROUP_REQ : natural := 16#10#;
    constant BLE_ATT_READ_BY_GROUP_RSP : natural := 16#11#;

    -- LLData of a CONNECT_IND
    type ble_conn_params is record
        aa         : ble_octets(0 to 3);                -- access address, as on the air (least significant octet first)
        crc_init   : natural;
        win_size   : natural;                           -- transmitWindowSize, 1.25 ms
        win_offset : natural;                           -- transmitWindowOffset, 1.25 ms
        interval   : natural;                           -- connInterval, 1.25 ms
        latency    : natural;
        timeout    : natural;                           -- connSupervisionTimeout, 10 ms
        chm        : bit_vector(0 to 36);               -- '1': the data channel is used
        hop        : natural;                           -- hopIncrement, 5 - 16
        sca        : natural;
    end record;
    function ble_connect_pdu(inita, adva : ble_octets; p : ble_conn_params; tx_add, rx_add : natural := 0) return ble_octets;
    function ble_conn_params_of(pdu : ble_octets) return ble_conn_params;      -- of a whole CONNECT_IND PDU (36 octets)
    -- the rules for an access address (Vol 6 Part B 2.1.2)
    function ble_aa_valid(aa : ble_octets) return boolean;
    -- channel selection algorithm #1: the data channel of an unmapped channel
    function ble_data_channel(unmapped : natural; chm : bit_vector(0 to 36)) return natural;

    function ble_data_pdu(llid, nesn, sn : natural; payload : ble_octets) return ble_octets;
    function ble_l2cap(cid : natural; payload : ble_octets) return ble_octets;
    function ble_packet_time(phy : ble_phy; pdu_len : natural) return time;
    function ble_hex(o : ble_octets) return string;        -- in the order given

    -- One end of a connection's data channel: sequence numbers, the payload being sent (until it is
    -- acknowledged) and those waiting behind it.
    type ble_sdu is record
        llid : natural;
        len  : natural;
        data : ble_octets(0 to BLE_DATA_MAX - 1);
    end record;
    type ble_sdu_array is array (0 to 3) of ble_sdu;
    type ble_link_state is record
        sn, nesn : natural;
        cur      : ble_sdu;
        sent     : boolean;                             -- cur has been transmitted at least once
        q        : ble_sdu_array;
        qn       : natural;
    end record;
    procedure ble_link_reset(l : inout ble_link_state);
    procedure ble_link_push(l : inout ble_link_state; llid : natural; payload : ble_octets);
    -- the PDU to transmit now (n octets of pdu)
    procedure ble_link_transmit(l : inout ble_link_state; pdu : out ble_octets; n : out natural);
    -- a PDU with a good CRC arrived (hdr: its first octet); fresh: it is new data, not a repeat
    procedure ble_link_receive(l : inout ble_link_state; hdr : natural; fresh : out boolean);
    -- nothing left to send: everything pushed has been acknowledged
    function ble_link_idle(l : ble_link_state) return boolean;
end package;

package body ble_ll_pkg is
    constant EMPTY : ble_sdu := (llid => BLE_LLID_CONT, len => 0, data => (others => 0));

    function ble_connect_pdu(inita, adva : ble_octets; p : ble_conn_params; tx_add, rx_add : natural := 0) return ble_octets is
        variable d : ble_octets(0 to 21);
        constant chm : ble_octets := ble_octets_of(p.chm & "000");
    begin
        d(0 to 3) := p.aa;
        d(4) := p.crc_init mod 256;
        d(5) := (p.crc_init / 256) mod 256;
        d(6) := (p.crc_init / 65536) mod 256;
        d(7) := p.win_size;
        d(8) := p.win_offset mod 256;
        d(9) := p.win_offset / 256;
        d(10) := p.interval mod 256;
        d(11) := p.interval / 256;
        d(12) := p.latency mod 256;
        d(13) := p.latency / 256;
        d(14) := p.timeout mod 256;
        d(15) := p.timeout / 256;
        d(16 to 20) := chm;
        d(21) := p.hop + 32 * p.sca;
        return ble_adv_pdu(BLE_CONNECT_IND, inita & adva & d, tx_add, rx_add);
    end function;

    function ble_conn_params_of(pdu : ble_octets) return ble_conn_params is
        constant d : ble_octets(0 to pdu'length - 1) := pdu;
        constant chm : bit_vector(0 to 39) := ble_bits_of(d(30 to 34));
        variable p : ble_conn_params;
    begin
        p.aa := d(14 to 17);
        p.crc_init := d(18) + 256 * d(19) + 65536 * d(20);
        p.win_size := d(21);
        p.win_offset := d(22) + 256 * d(23);
        p.interval := d(24) + 256 * d(25);
        p.latency := d(26) + 256 * d(27);
        p.timeout := d(28) + 256 * d(29);
        p.chm := chm(0 to 36);
        p.hop := d(35) mod 32;
        p.sca := d(35) / 32;
        return p;
    end function;

    function ble_aa_valid(aa : ble_octets) return boolean is
        constant b : bit_vector(0 to 31) := ble_bits_of(aa);
        variable run, longest, transitions, top, differ : natural := 0;
    begin
        run := 1;
        longest := 1;
        for i in 1 to 31 loop
            if b(i) = b(i - 1) then
                run := run + 1;
            else
                run := 1;
                transitions := transitions + 1;
                if i >= 27 then
                    top := top + 1;
                end if;
            end if;
            if run > longest then
                longest := run;
            end if;
        end loop;
        for i in 0 to 31 loop
            if b(i) /= BLE_ADV_AA(i) then
                differ := differ + 1;
            end if;
        end loop;
        return longest <= 6 and transitions <= 24 and top >= 2 and differ > 1
            and not (aa(aa'low) = aa(aa'low + 1) and aa(aa'low) = aa(aa'low + 2) and aa(aa'low) = aa(aa'low + 3));
    end function;

    function ble_data_channel(unmapped : natural; chm : bit_vector(0 to 36)) return natural is
        variable used, k : natural := 0;
    begin
        if chm(unmapped) = '1' then
            return unmapped;
        end if;
        for i in chm'range loop
            if chm(i) = '1' then
                used := used + 1;
            end if;
        end loop;
        assert used > 0 report "ble_data_channel: no channel is used" severity failure;
        for i in chm'range loop
            if chm(i) = '1' then
                if k = unmapped mod used then
                    return i;
                end if;
                k := k + 1;
            end if;
        end loop;
        return 0;
    end function;

    function ble_data_pdu(llid, nesn, sn : natural; payload : ble_octets) return ble_octets is
        variable r : ble_octets(0 to payload'length + 1);
    begin
        r(0) := llid + 4 * nesn + 8 * sn;
        r(1) := payload'length;
        r(2 to r'high) := payload;
        return r;
    end function;

    function ble_l2cap(cid : natural; payload : ble_octets) return ble_octets is
        constant h : ble_octets(0 to 3) := (payload'length mod 256, payload'length / 256, cid mod 256, cid / 256);
    begin
        return h & payload;
    end function;

    function ble_packet_time(phy : ble_phy; pdu_len : natural) return time is
    begin
        return integer(round(real(ble_packet_symbol_count(phy, pdu_len)) / ble_symbol_rate(phy) * 1.0e9)) * 1 ns;
    end function;

    function ble_hex(o : ble_octets) return string is
        constant digits : string(1 to 16) := "0123456789ABCDEF";
        variable r : string(1 to 2 * o'length);
        variable k : positive := 1;
    begin
        for i in o'range loop
            r(k) := digits(o(i) / 16 + 1);
            r(k + 1) := digits(o(i) mod 16 + 1);
            k := k + 2;
        end loop;
        return r;
    end function;

    procedure ble_link_reset(l : inout ble_link_state) is
    begin
        l.sn := 0;
        l.nesn := 0;
        l.cur := EMPTY;
        l.sent := false;
        l.qn := 0;
    end procedure;

    procedure ble_link_push(l : inout ble_link_state; llid : natural; payload : ble_octets) is
        variable s : ble_sdu := EMPTY;
    begin
        assert payload'length <= BLE_DATA_MAX report "ble_link_push: the payload is too long" severity failure;
        s.llid := llid;
        s.len := payload'length;
        s.data(0 to payload'length - 1) := payload;
        if l.cur.len = 0 and not l.sent and l.qn = 0 then
            l.cur := s;                                 -- in place of the empty PDU that has not gone out
        else
            assert l.qn <= l.q'high report "ble_link_push: the transmit queue is full" severity failure;
            l.q(l.qn) := s;
            l.qn := l.qn + 1;
        end if;
    end procedure;

    procedure ble_link_transmit(l : inout ble_link_state; pdu : out ble_octets; n : out natural) is
    begin
        pdu(pdu'low to pdu'low + l.cur.len + 1) := ble_data_pdu(l.cur.llid, l.nesn, l.sn, l.cur.data(0 to l.cur.len - 1));
        n := l.cur.len + 2;
        l.sent := true;
    end procedure;

    procedure ble_link_receive(l : inout ble_link_state; hdr : natural; fresh : out boolean) is
        constant nesn : natural := (hdr / 4) mod 2;
        constant sn : natural := (hdr / 8) mod 2;
    begin
        if nesn /= l.sn then                            -- what was sent is acknowledged: the next one
            l.sn := 1 - l.sn;
            l.sent := false;
            if l.qn > 0 then
                l.cur := l.q(0);
                for i in 1 to l.qn - 1 loop
                    l.q(i - 1) := l.q(i);
                end loop;
                l.qn := l.qn - 1;
            else
                l.cur := EMPTY;
            end if;
        end if;
        fresh := sn = l.nesn;
        if sn = l.nesn then
            l.nesn := 1 - l.nesn;
        end if;
    end procedure;

    function ble_link_idle(l : ble_link_state) return boolean is
    begin
        return l.qn = 0 and l.cur.len = 0 and l.cur.llid = BLE_LLID_CONT;
    end function;
end package body;
