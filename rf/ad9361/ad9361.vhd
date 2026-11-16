-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ad9361: the AD9361 for nvc's --std=2040 spectral event-driven mode, driven from software.
--
-- RF pins tx1 and rx1 are std_logic nets whose payload is an rf_spectrum (work.rf_spectrum_pkg): the chip
-- writes tx1'driver and reads rx1'other, and a resolver network (arena_resolver.py) joins the pins to
-- antenna feeds and the antennas to each other.  There is no SPI port and no data-port timing: software
-- (a process, not RTL) sets `cfg`, the controls a program sets through the Linux IIO driver, and
-- exchanges samples one symbol period at a time: a new value on tx_data is transmitted as one event, and
-- every event at the RX pin gives a new value on rx_data.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.rf_spectrum_pkg.all;
use work.ad9361_pkg.all;
use work.ad9361_spectral_pkg.all;

entity ad9361 is
    generic (
        seed : positive := 1                 -- noise seed; give each chip its own
    );
    port (
        tx1        : inout std_logic;        -- TX1 pin
        rx1        : inout std_logic;        -- RX1 pin
        cfg        : in  ad9361_config;      -- controls
        tx_data    : in  ad9361_frame;       -- samples to send, one symbol period per event
        rx_data    : out ad9361_frame;       -- samples received, one symbol period per event
        rx_gain_db : out real                -- status: RX gain in use
    );
end entity;

architecture behavioral of ad9361 is
begin
    transmitter: process (tx_data)
        variable st : ad9361_state := ad9361_init_state(seed);
        variable s, reflected : rf_spectrum;
    begin
        reflected := tx1'other;              -- what comes back into the TX pin is ignored
        if tx_data.seq /= 0 and cfg.sample_rate > 0.0 then
            ad9361_tx_symbol(cfg, st, tx_data, s);
            tx1'driver := s;
        end if;
    end process;

    receiver: process (rx1'other, cfg)
        variable st : ad9361_state := ad9361_init_state(seed + 7919);
        variable agc : ad9361_agc_state;
        variable last_cfg : ad9361_config;
        variable started : boolean := false;
        variable last_seq : natural := 0;
        variable emitted : natural := 0;
        variable s : rf_spectrum;
        variable f : ad9361_frame;
    begin
        if cfg.sample_rate > 0.0 then
            if not started or cfg /= last_cfg then
                if not started or cfg.gain_mode /= last_cfg.gain_mode or cfg.rx_lo /= last_cfg.rx_lo then
                    agc := ad9361_agc_init(cfg);
                end if;
                emitted := emitted + 1;
                rx1'driver := ad9361_rx_emission(cfg, emitted);      -- LO leakage out of the RX pin
                last_cfg := cfg;
                started := true;
            end if;
            s := rx1'other;
            if s.seq /= 0 and s.seq /= last_seq then
                last_seq := s.seq;
                ad9361_rx_symbol(cfg, st, agc, s, sim_time, f);
                if f.seq /= 0 then
                    rx_data <= f;
                end if;
                rx_gain_db <= agc.gain_db;
            end if;
        end if;
    end process;
end architecture;
