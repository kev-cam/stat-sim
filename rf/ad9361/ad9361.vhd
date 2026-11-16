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
--
-- With the spectral accelerator (accel/spectral_accel_pkg.vhd; compiled in, and the library loaded)
-- the same two processes can have their data and processing moved out: while sa_mode = SA_ON_ACCEL they
-- only hand frames over at the data port and collect what the receiver delivers, and when sa_mode
-- changes they push their state and the spectrum on the TX pin out, or pull them back.
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use work.rf_spectrum_pkg.all;
use work.ad9361_pkg.all;
use work.ad9361_spectral_pkg.all;
use work.spectral_accel_pkg.all;

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
    signal accel_id : real := -1.0;          -- this chip in the accelerator (-1.0: none); the bridge reads it

    function flag(b : boolean) return real is
    begin
        if b then
            return 1.0;
        end if;
        return 0.0;
    end function;
begin
    transmitter: process (tx_data, sa_mode)
        variable st : ad9361_state := ad9361_init_state(seed);
        variable s, reflected : rf_spectrum;
        variable pin : rf_spectrum := spec_silent(1);        -- what this process last put on the TX pin
        variable kicks : natural := 0;
        variable sv : real_vector(0 to 2);
        variable lv : real_vector(0 to 2 * SPEC_N - 1);
    begin
        reflected := tx1'other;              -- what comes back into the TX pin is ignored
        if sa_mode'event and accel_id >= 0.0 then
            if sa_mode = SA_ON_ACCEL then
                -- out: the spectrum on the pin, and what this process carries from event to event
                sv := (st.tx_theta, st.tx_leak_phase, flag(not spec_is_silent(pin)));
                sa_push_tx(accel_id, sv, lines_to_reals(pin.h));
            elsif sa_mode = SA_RESTORING then
                -- and back: the pin shows what the accelerator last put there
                sa_pull_tx(accel_id, sv, lv);
                st.tx_theta := sv(0);
                st.tx_leak_phase := sv(1);
                if sv(2) /= 0.0 then
                    pin := (h => reals_to_lines(lv), v => LINES_ZERO, freq => ad9361_lo_actual(cfg.tx_lo, cfg.xo_ppm),
                            df => cfg.sample_rate / real(SPEC_N), seq => pin.seq + 1);
                else
                    pin := spec_silent(pin.seq + 1);
                end if;
                tx1'driver := pin;
            end if;
        end if;
        if tx_data'event and tx_data.seq /= 0 and cfg.sample_rate > 0.0 then
            if sa_mode = SA_ON_ACCEL and accel_id >= 0.0 then
                sa_tx(accel_id, real(tx_data.seq), lines_to_reals(tx_data.lines));
                kicks := kicks + 1;
                sa_kick <= kicks;
            else
                ad9361_tx_symbol(cfg, st, tx_data, s);
                tx1'driver := s;
                pin := s;
            end if;
        end if;
    end process;

    receiver: process (rx1'other, cfg, sa_mode, sa_kick)
        variable st : ad9361_state := ad9361_init_state(seed + 7919);
        variable agc : ad9361_agc_state;
        variable last_cfg : ad9361_config;
        variable started : boolean := false;
        variable last_seq : natural := 0;
        variable emitted : natural := 0;
        variable s : rf_spectrum;
        variable f : ad9361_frame;
        variable id : real := -1.0;
        variable asked : boolean := false;
        variable kicks : natural := 0;
        variable sv : real_vector(0 to 6);
        variable buf : real_vector(0 to 2 * SPEC_N + 1);
    begin
        if not asked then                    -- once: this chip's place in the accelerator, if the run has one
            asked := true;
            if sa_available then
                id := sa_chip_new(real(seed));
                accel_id <= id;
            end if;
        end if;
        if cfg.sample_rate > 0.0 then
            if not started or cfg /= last_cfg then
                if not started or cfg.gain_mode /= last_cfg.gain_mode or cfg.rx_lo /= last_cfg.rx_lo then
                    agc := ad9361_agc_init(cfg);
                    if id >= 0.0 and sa_mode = SA_ON_ACCEL then
                        sa_agc_init(id, agc.gain_db);
                    end if;
                end if;
                emitted := emitted + 1;
                rx1'driver := ad9361_rx_emission(cfg, emitted);      -- LO leakage out of the RX pin
                last_cfg := cfg;
                started := true;
                if id >= 0.0 then            -- the accelerator follows the control state wherever the data is
                    sa_chip_params(id, ad9361_accel_params(cfg, SPEC_N));
                    if sa_mode = SA_ON_ACCEL then
                        sa_touch;            -- what this chip radiates changed: an event, as in the arena
                        kicks := kicks + 1;
                        sa_kick <= kicks;
                    end if;
                end if;
            end if;
            if sa_mode'event and id >= 0.0 then
                if sa_mode = SA_ON_ACCEL then
                    sv := (st.rx_theta, agc.gain_db, real(ad9361_fast_state'pos(agc.fast)), real(agc.settle),
                           real(agc.lost), agc.acc, real(agc.acc_n));
                    sa_push_rx(id, sv);
                elsif sa_mode = SA_RESTORING then
                    sa_pull_rx(id, sv);
                    st.rx_theta := sv(0);
                    agc.gain_db := sv(1);
                    agc.fast := ad9361_fast_state'val(integer(sv(2)));
                    agc.settle := integer(sv(3));
                    agc.lost := integer(sv(4));
                    agc.acc := sv(5);
                    agc.acc_n := integer(sv(6));
                end if;
            end if;
            s := rx1'other;
            if sa_mode = SA_IN_NVC then
                if s.seq /= 0 and s.seq /= last_seq then
                    last_seq := s.seq;
                    ad9361_rx_symbol(cfg, st, agc, s, sim_time, f);
                    if f.seq /= 0 then
                        rx_data <= f;
                    end if;
                    rx_gain_db <= agc.gain_db;
                end if;
            else
                last_seq := s.seq;           -- the net is not where the signal is: nothing on it is an event
                if sa_mode = SA_ON_ACCEL and sa_kick'event and id >= 0.0 then
                    sa_rx(id, sim_time, buf);
                    if buf(2 * SPEC_N + 1) /= 0.0 then
                        f.lines := reals_to_lines(buf(0 to 2 * SPEC_N - 1));
                        f.seq := integer(buf(2 * SPEC_N + 1));
                        rx_data <= f;
                        rx_gain_db <= buf(2 * SPEC_N);
                    end if;
                end if;
            end if;
        end if;
    end process;
end architecture;
