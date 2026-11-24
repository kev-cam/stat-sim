-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- cc2652r_spectral_pkg: what the software of a CC2652R (entity cc2652r, cc2652r.vhd) sees of it.
--
-- The chip has no sample port: its software sets a frequency, a PHY and a power, hands it packets to
-- send and is handed the packets it receives.  cc2652r_config is the first, cc2652r_packet the other
-- two.  On the RF pin the chip is an rf_spectrum like the AD9361 model's, with one difference in how
-- an event is read: a GFSK transmission is a run of consecutive events, each the 64 samples (2 us at
-- CC_FS) that follow the event before, not one periodic symbol each.
library ieee;
use ieee.math_real.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;

package cc2652r_spectral_pkg is
    constant CC_T_EVENT : time := 2 us;                 -- SPEC_N samples at CC_FS

    type cc2652r_config is record
        rx_on          : boolean;                       -- the receiver listens (when the chip is not sending)
        frequency      : real;                          -- Hz
        phy            : ble_phy;
        tx_power       : real;                          -- dBm; the chip sends the nearest setting it has
        xo_ppm         : real;                          -- crystal error: moves the carrier
        access_address : bit_vector(0 to 31);           -- transmission order
        crc_init       : natural;
        whiten         : integer;                       -- channel index that whitens the packets, -1: none
    end record;
    function cc2652r_default_config return cc2652r_config;

    type cc2652r_packet is record
        pdu    : ble_octets(0 to BLE_MAX_PDU - 1);
        len    : natural;                               -- octets of pdu in use (header and payload)
        crc_ok : boolean;                               -- received packets
        rssi   : real;                                  -- dBm, received packets
        t_end  : time;                                  -- received packets: when the packet ended at the pin
        seq    : natural;                               -- changes with every packet; 0: none yet
    end record;
    constant CC2652R_NO_PACKET : cc2652r_packet;
    function cc2652r_packet_of(pdu : ble_octets; seq : positive) return cc2652r_packet;

    -- Wait until simulation time t.  Used in place of `wait for`: in the nvc this was written with
    -- (1.19-devel r624) a `wait for` is cut short by an event on a signal that an earlier wait of the
    -- same process named.
    procedure cc_wait_until(t : time);

    function cc2652r_tx_power_legal(dbm : real) return real;
    function cc_dbm_w(dbm : real) return real;
    function cc_w_dbm(w : real) return real;
    -- free-space level at a receiver, dBm (for score boards)
    function cc_link_budget(tx_dbm, distance, freq, gains_dbi : real) return real;
end package;

package body cc2652r_spectral_pkg is
    constant CC2652R_NO_PACKET : cc2652r_packet := (pdu => (others => 0), len => 0, crc_ok => false, rssi => 0.0,
                                                    t_end => 0 fs, seq => 0);

    function cc2652r_default_config return cc2652r_config is
    begin
        return (rx_on => false, frequency => 2440.0e6, phy => PHY_1M, tx_power => 0.0, xo_ppm => 0.0,
                access_address => BLE_ADV_AA, crc_init => BLE_CRC_INIT_ADV, whiten => -1);
    end function;

    function cc2652r_packet_of(pdu : ble_octets; seq : positive) return cc2652r_packet is
        variable p : cc2652r_packet := CC2652R_NO_PACKET;
    begin
        p.pdu(0 to pdu'length - 1) := pdu;
        p.len := pdu'length;
        p.seq := seq;
        return p;
    end function;

    procedure cc_wait_until(t : time) is
    begin
        while now < t loop
            wait for t - now;
        end loop;
    end procedure;

    function cc2652r_tx_power_legal(dbm : real) return real is
    begin
        return realmin(realmax(round(dbm / CC_TX_STEP) * CC_TX_STEP, CC_TX_PMAX - CC_TX_RANGE), CC_TX_PMAX);
    end function;

    function cc_dbm_w(dbm : real) return real is
    begin
        return 1.0e-3 * 10.0 ** (dbm / 10.0);
    end function;

    function cc_w_dbm(w : real) return real is
    begin
        return 10.0 * log10(realmax(w, 1.0e-300) / 1.0e-3);
    end function;

    function cc_link_budget(tx_dbm, distance, freq, gains_dbi : real) return real is
    begin
        return tx_dbm + gains_dbi + 20.0 * log10(299792458.0 / freq / (4.0 * MATH_PI * distance));
    end function;
end package body;
