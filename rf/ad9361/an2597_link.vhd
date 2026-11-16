-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- an2597_link: the radio link of Analog Devices AN-2597 in nvc's --std=2040 spectral event-driven mode.
--
-- AN-2597 puts an 802.11n-like OFDM modem in the FPGA of an ADRV9361-Z7035 (AD9361 + Zynq) at each end
-- of a drone / controller link (5, 10 or 20 MHz channels in the 2.4 and 5.2 GHz bands).  Here each end is
-- an AD9361 model with a transmit and a receive antenna, the four antennas stand in an arena, and the
-- modem is software: two processes (drone_sw, ctrl_sw) that call ofdm_soft_pkg and hand the chips one
-- symbol period at a time.  No RTL, no samples on the nets: every event is a spectrum.
--
-- The drone flies out along x; at each distance it sends packets in each modulation, the controller's
-- receiver (fast-attack AGC) demodulates them, and the scoreboard prints one line per distance and
-- modulation:  AN2597 dist=<m> mod=<n> packets=<sent> detected=<n> evm_db=<dB> bit_errors=<n> bits=<n> gain_db=<dB>
--
-- Run through an2597_nvc.py (it writes the resolver network and the wrapper, and sets the generics).
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library rf;
use rf.iq_pkg.all;
use work.rf_spectrum_pkg.all;
use work.ad9361_pkg.all;
use work.ad9361_spectral_pkg.all;
use work.ofdm_soft_pkg.all;

entity an2597_link is
    generic (
        lo        : real := 2.437e9;        -- carrier, Hz
        fs        : real := 20.0e6;         -- sample rate = channel width, Hz
        atten_db  : real := 0.0;            -- TX attenuation
        ant_dbi   : real := 2.0;            -- gain of every antenna
        drone_ppm : real := 1.0;            -- reference clock errors
        ctrl_ppm  : real := -1.5;
        backoff_db : real := 12.0;          -- packet rms under DAC full scale
        packets   : positive := 10;         -- per distance and modulation
        symbols   : positive := 20;         -- data symbols per packet
        d0, d1, d2, d3, d4, d5, d6, d7 : real := -1.0   -- distances in metres (negative: not used)
    );
end entity;

architecture sim of an2597_link is
    constant T_SYM : time := integer(round(real(SOFT_SYMBOL_SAMPLES) / fs * 1.0e9)) * 1 ns;
    constant MAX_SYMBOLS : positive := 64;
    type real_vec is array (natural range <>) of real;
    constant DIST : real_vec(0 to 7) := (d0, d1, d2, d3, d4, d5, d6, d7);

    function radio_cfg(ppm : real; ensm : ad9361_ensm) return ad9361_config is
        variable c : ad9361_config := ad9361_default_config;
    begin
        c.rx_lo := lo;
        c.tx_lo := lo;
        c.sample_rate := fs;
        c.rx_rf_bw := 0.9 * fs;
        c.tx_rf_bw := 0.9 * fs;
        c.gain_mode := AGC_FAST_ATTACK;
        c.tx_atten_db := atten_db;
        c.xo_ppm := ppm;
        c.ensm := ensm;
        return c;
    end function;

    -- RF nets: the payload is on each pin's 'driver / 'other; the resolver joins them
    signal n_drone_tx, n_drone_rx, n_ctrl_tx, n_ctrl_rx, air : std_logic;

    -- software side of the two chips.  Half duplex: the drone sends, the controller listens.
    signal drone_cfg : ad9361_config := radio_cfg(drone_ppm, ENSM_TX);
    signal ctrl_cfg  : ad9361_config := radio_cfg(ctrl_ppm, ENSM_RX);
    signal drone_tx, drone_rx, ctrl_tx, ctrl_rx : ad9361_frame := AD9361_NO_FRAME;
    signal drone_gain, ctrl_gain : real := 0.0;

    -- where the antennas are; each board's two antennas are 5 cm apart
    signal drone_tx_pos : rf_position := (1.0, 0.0, 0.0);
    signal drone_rx_pos : rf_position := (1.0, 0.05, 0.0);
    signal ctrl_tx_pos  : rf_position := (0.0, 0.05, 0.0);
    signal ctrl_rx_pos  : rf_position := (0.0, 0.0, 0.0);

    -- scoreboard (not part of the radio): what was sent, for the EVM and bit-error count at the receiver
    type sent_t is array (0 to MAX_SYMBOLS - 1) of soft_indices;
    signal sb_sent : sent_t := (others => (others => 0));
    signal sb_mod : soft_modulation := MOD_BPSK;
    signal sb_dist : real := 0.0;
    signal sb_batch : natural := 0;          -- counts finished batches (one distance, one modulation)
begin
    assert symbols <= MAX_SYMBOLS report "at most 64 data symbols per packet" severity failure;

    drone_chip: entity work.ad9361
        generic map (seed => 11)
        port map (tx1 => n_drone_tx, rx1 => n_drone_rx, cfg => drone_cfg, tx_data => drone_tx, rx_data => drone_rx,
                  rx_gain_db => drone_gain);
    drone_ant_tx: entity work.rf_spec_antenna
        generic map (gain_dbi => ant_dbi)
        port map (feed => n_drone_tx, air => air, position => drone_tx_pos);
    drone_ant_rx: entity work.rf_spec_antenna
        generic map (gain_dbi => ant_dbi)
        port map (feed => n_drone_rx, air => air, position => drone_rx_pos);

    ctrl_chip: entity work.ad9361
        generic map (seed => 23)
        port map (tx1 => n_ctrl_tx, rx1 => n_ctrl_rx, cfg => ctrl_cfg, tx_data => ctrl_tx, rx_data => ctrl_rx,
                  rx_gain_db => ctrl_gain);
    ctrl_ant_tx: entity work.rf_spec_antenna
        generic map (gain_dbi => ant_dbi)
        port map (feed => n_ctrl_tx, air => air, position => ctrl_tx_pos);
    ctrl_ant_rx: entity work.rf_spec_antenna
        generic map (gain_dbi => ant_dbi)
        port map (feed => n_ctrl_rx, air => air, position => ctrl_rx_pos);

    -- The drone's software: flies, and sends packets.
    drone_sw: process
        constant amp : real := 32768.0 * 10.0 ** (-backoff_db / 20.0);   -- sample rms, data-port units
        variable seed1 : positive := 4711;
        variable seed2 : positive := 815;
        variable u : real;
        variable seqno : natural := 0;
        variable idx : soft_indices;

        procedure send(x : spec_lines) is
            variable f : ad9361_frame;
        begin
            seqno := seqno + 1;
            for k in x'range loop
                f.lines(k) := (i => x(k).i * amp, q => x(k).q * amp);
            end loop;
            f.seq := seqno;
            drone_tx <= f;
            wait for T_SYM;
        end procedure;
    begin
        wait for T_SYM;
        for di in DIST'range loop
            if DIST(di) > 0.0 then
                drone_tx_pos <= (DIST(di), 0.0, 0.0);
                drone_rx_pos <= (DIST(di), 0.05, 0.0);
                sb_dist <= DIST(di);
                wait for T_SYM;
                for m in soft_modulation loop
                    sb_mod <= m;
                    for pk in 1 to packets loop
                        send(soft_stf);
                        send(soft_stf);
                        send(soft_ltf);
                        send(soft_ltf);
                        for sy in 0 to symbols - 1 loop
                            for k in idx'range loop
                                uniform(seed1, seed2, u);
                                idx(k) := integer(floor(u * real(soft_points(m)))) mod soft_points(m);
                            end loop;
                            sb_sent(sy) <= idx;
                            send(soft_data(m, idx));
                        end loop;
                        send(LINES_ZERO);                  -- two idle periods: carrier leakage and noise only
                        send(LINES_ZERO);
                    end loop;
                    sb_batch <= sb_batch + 1;
                    wait for T_SYM;
                end loop;
            end if;
        end loop;
        report "AN2597 done";
        wait;
    end process;

    -- The controller's software: receives, and keeps score.
    ctrl_sw: process (ctrl_rx, sb_batch)
        type state_t is (IDLE, GOT_STF, GOT_LTF1, DATA);
        variable state : state_t := IDLE;
        variable last_seq, last_batch : natural := 0;
        variable ltf1, h, x : spec_lines;
        variable eps : real;
        variable n : natural;
        variable eq : soft_symbols;
        variable want : iq_sample;
        variable got : natural;
        -- per batch
        variable detected, bit_errors, bits : natural := 0;
        variable err_power, ref_power, gain_sum : real := 0.0;
        -- per packet
        variable p_err, p_ref : real;
        variable p_bit_errors : natural;
    begin
        if ctrl_rx.seq /= last_seq then
            last_seq := ctrl_rx.seq;
            case state is
                when IDLE =>
                    if soft_is_stf(ctrl_rx.lines) then
                        state := GOT_STF;
                    end if;
                when GOT_STF =>
                    if not soft_is_stf(ctrl_rx.lines) then
                        ltf1 := ctrl_rx.lines;             -- the first long-training event
                        state := GOT_LTF1;
                    end if;
                when GOT_LTF1 =>
                    eps := soft_cfo(ltf1, ctrl_rx.lines);
                    h := soft_channel(soft_correct(ltf1, eps, 0), soft_correct(ctrl_rx.lines, eps, 1));
                    n := 0;
                    p_err := 0.0;
                    p_ref := 0.0;
                    p_bit_errors := 0;
                    gain_sum := gain_sum + ctrl_gain;
                    state := DATA;
                when DATA =>
                    x := soft_correct(ctrl_rx.lines, eps, 2 + n);
                    eq := soft_equalise(x, h);
                    for k in eq'range loop
                        want := soft_point(sb_mod, sb_sent(n)(k));
                        p_err := p_err + (eq(k).i - want.i) ** 2 + (eq(k).q - want.q) ** 2;
                        p_ref := p_ref + want.i ** 2 + want.q ** 2;
                        got := soft_decide(sb_mod, eq(k));
                        p_bit_errors := p_bit_errors + soft_bit_errors(sb_mod, got, sb_sent(n)(k));
                    end loop;
                    n := n + 1;
                    if n = symbols then
                        detected := detected + 1;
                        err_power := err_power + p_err / p_ref;
                        bit_errors := bit_errors + p_bit_errors;
                        state := IDLE;
                    end if;
            end case;
        end if;
        if sb_batch /= last_batch then
            last_batch := sb_batch;
            bits := packets * symbols * SOFT_CARRIERS * soft_bits(sb_mod);
            -- a packet that was not found counts half its bits as wrong
            bit_errors := bit_errors + (packets - detected) * symbols * SOFT_CARRIERS * soft_bits(sb_mod) / 2;
            if detected > 0 then
                report "AN2597 dist=" & to_string(sb_dist, "%.3f") & " mod=" & integer'image(soft_modulation'pos(sb_mod))
                    & " packets=" & integer'image(packets) & " detected=" & integer'image(detected)
                    & " evm_db=" & to_string(10.0 * log10(err_power / real(detected)), "%.3f")
                    & " bit_errors=" & integer'image(bit_errors) & " bits=" & integer'image(bits)
                    & " gain_db=" & to_string(gain_sum / real(detected), "%.2f");
            else
                report "AN2597 dist=" & to_string(sb_dist, "%.3f") & " mod=" & integer'image(soft_modulation'pos(sb_mod))
                    & " packets=" & integer'image(packets) & " detected=0 evm_db=nan"
                    & " bit_errors=" & integer'image(bit_errors) & " bits=" & integer'image(bits) & " gain_db=nan";
            end if;
            detected := 0;
            bit_errors := 0;
            err_power := 0.0;
            gain_sum := 0.0;
            state := IDLE;
        end if;
    end process;
end architecture;
