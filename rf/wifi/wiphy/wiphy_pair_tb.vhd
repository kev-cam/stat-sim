-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- wiphy_pair_tb: one or two of bladeRF-wiphy's complete modem (wlan_top: transmitter, receiver,
-- acknowledgement generator, channel access) on a wire, each with a host, and a place to put frames
-- from elsewhere on the same wire.  Everything that goes over the wire and everything the hosts are
-- told is written to files, for wiphy_pair.py to judge with the reference decoder.
--
--   station s:   host (staS.script -> packets; staS.log <- what the modem hands up)
--                wlan_top
--                DAC -> the wire -> the other station's ADC (GAIN), 20 MS/s on the 40 MHz clock
--   inject.csv:  samples added at every ADC ("<clock> <i> <q>", even clocks, ascending)
--   mute.txt:    "<from> <to> <first clock> <last clock>": that path of the wire is cut meanwhile
--                (from = STATIONS means the injected samples)
--   air.log:     "T <station> <clock> <i> <q>" for every DAC sample; "O <station> <clock> <0|1>"
--                when a station's transmit-on-air flag changes
--
-- The host follows the packet mode of the bladeRF's fifo_reader, which is what feeds wlan_top on the
-- board: a 32-bit word stream whose next word is always on show, a word taken (data_valid) in each
-- clock the modem holds packet_ready, pkt_sop with the first.  A packet is a 16-octet header and the
-- frame without its FCS:  word 1 = bandwidth (2: 20 MHz) & rate (0..7 for 6..54 Mb/s), word 2 =
-- length in octets, word 3 = a cookie the modem returns with the transmit status.
--
-- The gain controls are tied as the bladeRF's own top level ties them (no acknowledge, always
-- "nack", gain at maximum, transmit request granted at once); gain_lock is left low.
library ieee;
    use ieee.std_logic_1164.all;
    use ieee.numeric_std.all;
library std;
    use std.textio.all;
library nuand;
    use nuand.fifo_readwrite_p.all;

entity wiphy_host is
    generic (
        SCRIPT : string;       -- lines: <clock> <rate 0..7> <cookie> <octets of the frame, hex, spaced>
        LOG    : string );
    port (
        clock             : in  std_logic;
        reset             : in  std_logic;
        clk_n             : in  natural;
        tx_packet_control : out packet_control_t := PACKET_CONTROL_DEFAULT;
        tx_packet_empty   : out std_logic := '1';
        tx_packet_ready   : in  std_logic;
        rx_packet_control : in  packet_control_t;
        rx_packet_ready   : out std_logic );
end entity;

architecture bfm of wiphy_host is
    constant MAXW : natural := 512;      -- words in a packet
    constant MAXP : natural := 16;       -- packets waiting
    type words_t is array (0 to MAXW - 1) of std_logic_vector(31 downto 0);
    type queue_t is array (0 to MAXP - 1) of words_t;
    type len_t is array (0 to MAXP - 1) of natural;
begin
    rx_packet_ready <= '1';

    send : process (clock)
        file fs : text;
        variable opened, at_end, waiting : boolean := false;
        variable status : file_open_status;
        variable l : line;
        variable t_next, rate, cookie, n, w : natural := 0;
        variable octet : std_logic_vector(7 downto 0);
        variable good : boolean;
        variable q : queue_t;
        variable q_len : len_t := (others => 0);
        variable q_head, q_tail, q_count : natural := 0;
        variable meta_empty_r : std_logic := '1';        -- the queue's empty flag, a clock late
        -- the reader's registers
        type mstate_t is (S_LOAD, S_WAIT, S_DOWN);
        variable m_state, n_state : mstate_t := S_LOAD;
        variable m_sop, m_go, n_sop, n_go : std_logic := '0';
        variable m_down, n_down : integer := 0;
        variable cur, cur_len, k : natural := 0;
        variable pc, n_pc : packet_control_t := PACKET_CONTROL_DEFAULT;
    begin
        if rising_edge(clock) then
            if not opened then
                file_open(status, fs, SCRIPT, read_mode);
                opened := true;
                at_end := status /= open_ok;
            end if;
            if reset = '1' then
                m_state := S_LOAD;
                m_sop := '0';
                m_go := '0';
                pc := PACKET_CONTROL_DEFAULT;
            else
                -- the script: a packet joins the queue at its time
                loop
                    if not waiting and not at_end then
                        if endfile(fs) then
                            at_end := true;
                        else
                            readline(fs, l);
                            if l'length > 0 and l(l'low) /= '#' then
                                read(l, t_next);
                                read(l, rate);
                                read(l, cookie);
                                n := 0;
                                q(q_tail) := (others => (others => '0'));
                                loop
                                    hread(l, octet, good);
                                    exit when not good;
                                    w := 4 + n / 4;
                                    q(q_tail)(w)(8 * (n mod 4) + 7 downto 8 * (n mod 4)) := octet;
                                    n := n + 1;
                                end loop;
                                q(q_tail)(0) := x"00000000";
                                q(q_tail)(1) := x"0002" & std_logic_vector(to_unsigned(rate, 16));
                                q(q_tail)(2) := x"0000" & std_logic_vector(to_unsigned(n, 16));
                                q(q_tail)(3) := std_logic_vector(to_unsigned(cookie, 32));
                                q_len(q_tail) := 4 + (n + 3) / 4 + 1;
                                waiting := true;
                            end if;
                        end if;
                    end if;
                    exit when not waiting or t_next > clk_n;
                    assert q_count < MAXP report "host: too many packets waiting" severity failure;
                    q_tail := (q_tail + 1) mod MAXP;
                    q_count := q_count + 1;
                    waiting := false;
                end loop;

                -- the packet framing (fifo_reader's meta state machine)
                n_state := m_state;
                n_sop := '0';
                n_go := m_go;
                n_down := m_down;
                case m_state is
                    when S_LOAD =>
                        n_go := '0';
                        if meta_empty_r = '0' and q_count > 0 and tx_packet_ready = '1' then
                            n_state := S_WAIT;
                            cur := q_head;
                            cur_len := q_len(q_head);
                            k := 0;
                            q_head := (q_head + 1) mod MAXP;
                            q_count := q_count - 1;
                        end if;
                    when S_WAIT =>
                        n_down := cur_len - 1;
                        if tx_packet_ready = '1' then
                            n_go := '1';
                            n_state := S_DOWN;
                            n_sop := '1';
                        else
                            n_go := '0';
                        end if;
                    when S_DOWN =>
                        n_go := '1';
                        if pc.data_valid = '1' then
                            n_down := m_down - 1;
                        end if;
                        if m_down <= 1 and tx_packet_ready = '1' then
                            n_state := S_LOAD;
                        end if;
                end case;
                -- the word stream
                n_pc := PACKET_CONTROL_DEFAULT;
                n_pc.pkt_sop := m_sop;
                if k < MAXW then
                    n_pc.data := q(cur)(k);
                end if;
                if m_go = '1' and m_down > 0 and tx_packet_ready = '1' then
                    n_pc.data_valid := '1';
                    if m_down = 1 then
                        n_pc.pkt_eop := '1';
                    end if;
                    k := k + 1;
                end if;
                if q_count = 0 then
                    meta_empty_r := '1';
                else
                    meta_empty_r := '0';
                end if;
                m_state := n_state;
                m_sop := n_sop;
                m_go := n_go;
                m_down := n_down;
                pc := n_pc;
                -- no packet waiting, as the reader says it: from its registers
                if meta_empty_r = '1' and m_state /= S_WAIT then
                    tx_packet_empty <= '1';
                else
                    tx_packet_empty <= '0';
                end if;
            end if;
            tx_packet_control <= pc;
        end if;
    end process;

    receive : process (clock)
        file fl : text open write_mode is LOG;
        variable l : line;
    begin
        if rising_edge(clock) then
            if rx_packet_control.data_valid = '1' then
                write(l, string'("RX ") & integer'image(clk_n) & " ");
                write(l, rx_packet_control.pkt_sop);
                write(l, string'(" "));
                write(l, rx_packet_control.pkt_eop);
                write(l, string'(" "));
                hwrite(l, rx_packet_control.data);
                writeline(fl, l);
            end if;
        end if;
    end process;
end architecture;

library ieee;
    use ieee.std_logic_1164.all;
    use ieee.numeric_std.all;
    use ieee.math_real.all;
library std;
    use std.textio.all;
library nuand;
    use nuand.fifo_readwrite_p.all;

entity wiphy_pair_tb is
    generic (
        STATIONS   : positive := 2;
        GAIN_M     : natural := 2170;    -- one station's DAC to another's ADC, in thousandths
        INJ_GAIN_M : natural := 1000;    -- the injected samples at an ADC, in thousandths
        NOISE_M    : natural := 2000;    -- rms on each rail of each ADC, in thousandths of a count
        ADC_MAX    : natural := 2047;    -- the ADC clips beyond this (12 bits)
        RUN_CLOCKS : natural := 200000 );
end entity;

architecture bench of wiphy_pair_tb is
    type s16_array is array (natural range <>) of signed(15 downto 0);
    type nat_array is array (natural range <>) of natural;
    type int_array is array (natural range <>) of integer;
    constant GAIN     : real := real(GAIN_M) / 1000.0;
    constant INJ_GAIN : real := real(INJ_GAIN_M) / 1000.0;
    constant NOISE    : real := real(NOISE_M) / 1000.0;
    signal clock    : std_logic := '1';
    signal reset    : std_logic := '1';
    signal finished : boolean := false;
    signal clk_n    : natural := 0;
    signal out_i, out_q, in_i, in_q : s16_array(0 to STATIONS - 1) := (others => (others => '0'));
    signal out_valid, in_valid, tx_ota, tx_ota_req : std_logic_vector(0 to STATIONS - 1) := (others => '0');
    signal tx_pc, rx_pc : packet_controls_t(0 to STATIONS - 1) := (others => PACKET_CONTROL_DEFAULT);
    signal tx_empty, tx_ready, rx_ready, tx_fifo_read, rx_fifo_write : std_logic_vector(0 to STATIONS - 1);
begin
    clock <= not clock after 12.5 ns when not finished;
    reset <= '1', '0' after 500 ns;

    stations_g : for s in 0 to STATIONS - 1 generate
        host : entity work.wiphy_host
          generic map (
            SCRIPT => "sta" & integer'image(s) & ".script",
            LOG    => "sta" & integer'image(s) & ".log" )
          port map (
            clock => clock, reset => reset, clk_n => clk_n,
            tx_packet_control => tx_pc(s), tx_packet_empty => tx_empty(s), tx_packet_ready => tx_ready(s),
            rx_packet_control => rx_pc(s), rx_packet_ready => rx_ready(s) );

        modem : entity work.wlan_top
          port map (
            rx_clock => clock, rx_reset => reset, rx_enable => '1',
            tx_clock => clock, tx_reset => reset, tx_enable => '1',
            config_reg => x"00000000",
            packet_en => '1',
            tx_packet_control => tx_pc(s), tx_packet_empty => tx_empty(s), tx_packet_ready => tx_ready(s),
            rx_packet_control => rx_pc(s), rx_packet_ready => rx_ready(s),
            rx_fifo_usedw => x"000", rx_fifo_write => rx_fifo_write(s), rx_fifo_full => '0', rx_fifo_data => open,
            tx_fifo_usedw => x"000", tx_fifo_read => tx_fifo_read(s), tx_fifo_empty => '1', tx_fifo_data => x"00000000",
            gain_inc_req => open, gain_dec_req => open, gain_rst_req => open,
            gain_ack => '0', gain_nack => '1', gain_lock => '0', gain_max => '1',
            tx_ota_req => tx_ota_req(s), tx_ota_ack => '1',
            out_i => out_i(s), out_q => out_q(s), out_valid => out_valid(s),
            wlan_tx_ota => tx_ota(s),
            in_i => in_i(s), in_q => in_q(s), in_valid => in_valid(s) );
    end generate;

    air : process (clock)
        file fa : text open write_mode is "air.log";
        file fi : text;
        file fm : text;
        variable l : line;
        variable opened : boolean := false;
        variable status : file_open_status;
        variable inj_end, inj_have : boolean := false;
        variable inj_clk, inj_vi, inj_vq : integer := 0;
        variable inj_i, inj_q : integer := 0;
        variable hold_i, hold_q : int_array(0 to STATIONS - 1) := (others => 0);
        variable idle : nat_array(0 to STATIONS - 1) := (others => 0);
        variable was_ota : std_logic_vector(0 to STATIONS - 1) := (others => '0');
        -- cuts in the wire
        constant MAXM : natural := 32;
        variable m_from, m_to, m_c0, m_c1 : nat_array(0 to MAXM - 1) := (others => 0);
        variable m_n : natural := 0;
        variable seed1 : positive := 4711;
        variable seed2 : positive := 1147;
        variable u, acc_i, acc_q, g : real;
        variable v : integer;

        impure function cut(from, to_s : natural) return boolean is
        begin
            for m in 0 to m_n - 1 loop
                if m_from(m) = from and m_to(m) = to_s and clk_n >= m_c0(m) and clk_n <= m_c1(m) then
                    return true;
                end if;
            end loop;
            return false;
        end function;

        impure function gauss return real is
            variable a : real := 0.0;
        begin
            for n in 1 to 4 loop
                uniform(seed1, seed2, u);
                a := a + u;
            end loop;
            return (a - 2.0) * sqrt(3.0) * NOISE;
        end function;

        function clip(x : real) return integer is
        begin
            if x > real(ADC_MAX) then
                return ADC_MAX;
            elsif x < -real(ADC_MAX) - 1.0 then
                return -ADC_MAX - 1;
            end if;
            return integer(round(x));
        end function;
    begin
        if rising_edge(clock) then
            if not opened then
                opened := true;
                file_open(status, fi, "inject.csv", read_mode);
                inj_end := status /= open_ok;
                file_open(status, fm, "mute.txt", read_mode);
                if status = open_ok then
                    while not endfile(fm) and m_n < MAXM loop
                        readline(fm, l);
                        if l'length > 0 and l(l'low) /= '#' then
                            read(l, m_from(m_n));
                            read(l, m_to(m_n));
                            read(l, m_c0(m_n));
                            read(l, m_c1(m_n));
                            m_n := m_n + 1;
                        end if;
                    end loop;
                end if;
            end if;
            clk_n <= clk_n + 1;
            if clk_n >= RUN_CLOCKS then
                finished <= true;
            end if;

            -- the DACs
            for s in 0 to STATIONS - 1 loop
                if out_valid(s) = '1' then
                    hold_i(s) := to_integer(out_i(s));
                    hold_q(s) := to_integer(out_q(s));
                    idle(s) := 0;
                    write(l, string'("T ") & integer'image(s) & " " & integer'image(clk_n) & " "
                             & integer'image(hold_i(s)) & " " & integer'image(hold_q(s)));
                    writeline(fa, l);
                else
                    if idle(s) < 2 then
                        idle(s) := idle(s) + 1;
                    else
                        hold_i(s) := 0;
                        hold_q(s) := 0;
                    end if;
                end if;
                if tx_ota(s) /= was_ota(s) then
                    write(l, string'("O ") & integer'image(s) & " " & integer'image(clk_n) & " ");
                    write(l, tx_ota(s));
                    writeline(fa, l);
                    was_ota(s) := tx_ota(s);
                end if;
            end loop;

            -- the ADCs, every second clock
            if clk_n mod 2 = 0 then
                -- the injected sample for this clock, if there is one
                inj_i := 0;
                inj_q := 0;
                loop
                    if not inj_have and not inj_end then
                        if endfile(fi) then
                            inj_end := true;
                        else
                            readline(fi, l);
                            read(l, inj_clk);
                            read(l, inj_vi);
                            read(l, inj_vq);
                            inj_have := true;
                        end if;
                    end if;
                    exit when not inj_have or inj_clk >= clk_n;
                    inj_have := false;
                end loop;
                if inj_have and inj_clk = clk_n then
                    inj_i := inj_vi;
                    inj_q := inj_vq;
                    inj_have := false;
                end if;
                for s in 0 to STATIONS - 1 loop
                    acc_i := 0.0;
                    acc_q := 0.0;
                    for o in 0 to STATIONS - 1 loop
                        if o /= s and not cut(o, s) then
                            acc_i := acc_i + GAIN * real(hold_i(o));
                            acc_q := acc_q + GAIN * real(hold_q(o));
                        end if;
                    end loop;
                    if not cut(STATIONS, s) then
                        acc_i := acc_i + INJ_GAIN * real(inj_i);
                        acc_q := acc_q + INJ_GAIN * real(inj_q);
                    end if;
                    in_i(s) <= to_signed(clip(acc_i + gauss), 16);
                    in_q(s) <= to_signed(clip(acc_q + gauss), 16);
                    in_valid(s) <= '1';
                end loop;
            else
                in_valid <= (others => '0');
            end if;
        end if;
    end process;
end architecture;
