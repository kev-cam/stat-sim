-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ucb_bmc_radio: the Berkeley baseband-modem as a radio in the arena, with the ports of entity
-- cc2652r, so that the same link layer (ble_controller) drives it and the same tester (ble_tester)
-- tests it.
--
-- The design is BMC of github.com/ucb-bar/baseband-modem (Chisel, BSD-3-Clause; not part of stat-sim):
-- its baseband (packet assembler and disassembler, whitening, CRC), modem (GFSK modulator, low-IF
-- receiver with image rejection, matched filters, clock and data recovery) and controller, without
-- the TileLink registers and DMA that Chipyard puts around them.  ucb_bmc/ makes its Verilog, sv2ghdl
-- translates that to VHDL.  It has no RF part, and its host is a processor; this entity is both:
--
--   host       gives the commands a link layer's driver would (configure, send, receive), and is the
--              memory behind the DMA streams the packets come and go by
--   sending    the modulator's 8-bit VCO code (the VCO_MOD table of the frequency index, loaded here:
--              code 2 + 4 index, VCO gain KMOD Hz a step about code 128) turns a carrier at the channel
--              that the coarse code (the VCO_CT_BLE table, loaded here: the RF channel) asks for, while
--              the design says it sends (offChipMode_tx); one sample a clock, 64 to an event
--   receiving  the pin's events, with the receiver's carrier error and thermal noise (nf_db), go
--              through a channel filter (rx_bw) and up to the 2 MHz intermediate frequency, are scaled
--              by an ideal AGC (the design's own AGC and offset loops are off) and quantised by the two
--              8-bit ADCs
--   clock      32 MHz, the ADC clock and the system clock alike, running only while a packet is sent or
--              the receiver has a signal at the pin (as the CC2652R model's receiver sleeps until
--              something arrives).  Reset, the tables and the configuration take no time here (1 ps a
--              clock).
--
-- The design whitens with its channel index (the seed is the index and a one), and takes the VCO's
-- coarse code from the table at the same index; its documentation calls the index the frequency's
-- (0: 2402 MHz), which would whiten every channel but three as another.  The table is loaded here by
-- BLE channel index, so that index is both.
--
-- The design's controller takes the end of a transmission from its 802.15.4 modulator, also when the
-- GFSK one sends (Controller.scala connects both to the one port, and the last connection stands): it
-- stays in its transmit state, the carrier on and no command taken, for 32 us an octet (octets + 8)
-- where the packet takes 8.  That is how it is here.  With tx_end the host does not wait: when the
-- GFSK modulator's state (which a host can read) goes back to idle, the carrier goes off and the design
-- is reset before it is used again.
--
-- The time between a packet handed over on tx and its first sample at the pin is BMC_TX_DELAY; a link
-- layer that keeps T_IFS hands the packet over that much early (ble_controller: radio_tx_delay).
--
-- Not there in the design, so not here: LE 2M and Coded, unwhitened reception (cfg.whiten < 0).
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
use std.textio.all;
library rf;
use rf.iq_pkg.all;
library sv2vhdl;
use sv2vhdl.logic3d_types_pkg.all;
use work.rf_spectrum_pkg.all;
use work.ble_phy_pkg.all;
use work.cc2652r_pkg.all;
use work.cc2652r_spectral_pkg.all;
use work.ucb_bmc_radio_pkg.all;

entity ucb_bmc_radio is
    generic (
        seed  : positive := 1;
        nf_db : real := 6.0;                -- noise figure of the front end
        rx_bw : real := 1.0e6;              -- cutoff of the channel filter, Hz from the carrier
        -- the receiver's latency: from the end of the access address at the pin to the design's rxStart
        rx_hit_delay : time := 4250 ns;
        adc_level : real := 0.4;            -- amplitude the AGC holds at the ADCs, of full scale 0.5
        tx_end : boolean := false;          -- the host ends a transmission with the GFSK modulator
        -- a file to write the design's inputs and outputs to, clock by clock (ucb_bmc/replay.v puts
        -- the inputs to the Verilog and compares the outputs: what the translation to VHDL is worth)
        trace : string := "";
        debug : boolean := false
    );
    port (
        ant     : inout std_logic;
        cfg     : in cc2652r_config;
        tx      : in cc2652r_packet;
        tx_busy : out boolean;
        rx      : out cc2652r_packet
    );
end entity;

architecture wrapped of ucb_bmc_radio is
    constant HALF : time := 15625 ps;       -- of the 32 MHz clock
    constant FAST : time := 1 ps;
    constant NT : positive := 33;           -- taps of the channel filter
    constant FLUSH : positive := 8;         -- silent events after which the receiver sleeps
    constant KMOD : real := 250.0e3 / 126.0;    -- Hz a step of the VCO's modulation code
    constant RX_BASE : natural := 16#1000#; -- where the design is told to store what it receives

    function l3v(n : integer; w : positive) return logic3d_vector is
        variable r : logic3d_vector(w - 1 downto 0);
        variable v : integer := n;
    begin
        for i in 0 to w - 1 loop
            if v mod 2 = 1 then
                r(i) := L3D_1;
            else
                r(i) := L3D_0;
            end if;
            v := (v - v mod 2) / 2;
        end loop;
        return r;
    end function;

    function int_of(v : logic3d_vector) return integer is
        alias a : logic3d_vector(v'length - 1 downto 0) is v;
        variable r : integer := 0;
    begin
        for i in a'high downto 0 loop
            r := r * 2;
            if is_one(a(i)) then
                r := r + 1;
            end if;
        end loop;
        return r;
    end function;

    function b(x : logic3d) return natural is
    begin
        if is_one(x) then
            return 1;
        end if;
        return 0;
    end function;

    -- the design takes the access address as a number whose least significant bit goes first
    function aa_of(b : bit_vector(0 to 31)) return logic3d_vector is
        variable r : logic3d_vector(31 downto 0);
    begin
        for i in 0 to 31 loop
            if b(i) = '1' then
                r(i) := L3D_1;
            else
                r(i) := L3D_0;
            end if;
        end loop;
        return r;
    end function;

    -- the RF channel (2402 + 2 k MHz) of a BLE channel index
    function rf_channel(index : natural) return natural is
    begin
        if index = 37 then
            return 0;
        elsif index = 38 then
            return 12;
        elsif index = 39 then
            return 39;
        elsif index <= 10 then
            return index + 1;
        end if;
        return index + 2;
    end function;

    type real_taps is array (0 to NT - 1) of real;
    function channel_filter return real_taps is
        constant M : real := real(NT - 1) / 2.0;
        constant W : real := 2.0 * rx_bw / CC_FS;
        variable h : real_taps;
        variable x, sum : real := 0.0;
    begin
        for n in h'range loop
            x := MATH_PI * W * (real(n) - M);
            if abs x < 1.0e-9 then
                h(n) := W;
            else
                h(n) := W * sin(x) / x;
            end if;
            h(n) := h(n) * (0.54 - 0.46 * cos(2.0 * MATH_PI * real(n) / real(NT - 1)));
            sum := sum + h(n);
        end loop;
        for n in h'range loop
            h(n) := h(n) / sum;
        end loop;
        return h;
    end function;
    constant FIR : real_taps := channel_filter;

    signal sending : boolean := false;
    signal pin_in, pin_out : rf_spectrum := spec_silent(1);

    -- the design's pins
    signal clk, rst : logic3d := L3D_0;
    signal zero : logic3d := L3D_0;
    signal one : logic3d := L3D_1;
    signal zero8 : logic3d_vector(7 downto 0) := (others => L3D_0);
    signal zero9 : logic3d_vector(8 downto 0) := (others => L3D_0);
    signal zero22 : logic3d_vector(21 downto 0) := (others => L3D_0);
    signal zero32 : logic3d_vector(31 downto 0) := (others => L3D_0);
    signal zero4 : logic3d_vector(3 downto 0) := (others => L3D_0);
    signal zero6 : logic3d_vector(5 downto 0) := (others => L3D_0);
    signal cap_coarse : logic3d_vector(9 downto 0);
    signal cap_mod : logic3d_vector(7 downto 0);
    signal adc_i, adc_q : logic3d_vector(7 downto 0) := l3v(128, 8);
    signal tx_on, cmd_ready : logic3d;
    signal cmd_valid : logic3d := L3D_0;
    signal cmd_prim, cmd_sec : logic3d_vector(3 downto 0) := (others => L3D_0);
    signal cmd_data : logic3d_vector(23 downto 0) := (others => L3D_0);
    signal cmd_add : logic3d_vector(31 downto 0) := (others => L3D_0);
    signal rreq_valid, rresp_ready, rdata_ready : logic3d;
    signal rreq_bytes : logic3d_vector(8 downto 0);
    signal rresp_valid, rdata_valid : logic3d := L3D_0;
    signal rresp_bytes : logic3d_vector(8 downto 0) := (others => L3D_0);
    signal rdata_bits : logic3d_vector(31 downto 0) := (others => L3D_0);
    signal wreq_valid : logic3d;
    signal wreq_addr, wreq_data : logic3d_vector(31 downto 0);
    signal wreq_bytes : logic3d_vector(2 downto 0);
    signal irq_rx_error, irq_rx_start, irq_rx_finish, irq_tx_error, irq_tx_finish : logic3d;
    signal lut_valid : logic3d := L3D_0;
    signal lut_id : logic3d_vector(3 downto 0) := (others => L3D_0);
    signal lut_addr : logic3d_vector(5 downto 0) := (others => L3D_0);
    signal lut_value : logic3d_vector(21 downto 0) := (others => L3D_0);
    signal msg_rx_error_valid, msg_rx_finish_valid, msg_tx_error_valid : logic3d;
    signal msg_rx_error, msg_rx_finish, msg_tx_error : logic3d_vector(31 downto 0);
    signal st_main : logic3d_vector(2 downto 0);
    signal st_tx, st_txc : logic3d_vector(1 downto 0);
    signal st_asm : logic3d_vector(2 downto 0);
    signal mod_index : logic3d_vector(5 downto 0);
begin
    pin_watch: process (ant'other)
        variable s : rf_spectrum;
    begin
        s := ant'other;
        pin_in <= s;
    end process;

    -- (ant'driver cannot be assigned in a subprogram)
    pin_drive: process (pin_out)
        variable s : rf_spectrum;
    begin
        s := pin_out;
        ant'driver := s;
    end process;

    tx_busy <= sending;

    design: entity work.BMC
        port map (
            clock => clk, reset => rst, io_adc_clock => clk,
            io_analog_data_tx_vco_cap_coarse => cap_coarse, io_analog_data_tx_vco_cap_medium => open,
            io_analog_data_tx_vco_cap_mod => cap_mod, io_analog_data_tx_vco_freq_reset => open,
            io_analog_data_rx_i_data => adc_i, io_analog_data_rx_i_valid => one,
            io_analog_data_rx_q_data => adc_q, io_analog_data_rx_q_valid => one,
            io_analog_data_tuning_i_vgaAtten => open, io_analog_data_tuning_i_vga_s2 => open,
            io_analog_data_tuning_q_vgaAtten => open, io_analog_data_tuning_q_vga_s2 => open,
            io_analog_enable_rx_mix => open, io_analog_enable_rx_buf => open, io_analog_enable_rx_tia => open,
            io_analog_enable_rx_vga => open, io_analog_enable_rx_bpf => open, io_analog_enable_lna => open,
            io_analog_offChipMode_rx => open, io_analog_offChipMode_tx => tx_on,
            io_cmd_ready => cmd_ready, io_cmd_valid => cmd_valid,
            io_cmd_bits_inst_primaryInst => cmd_prim, io_cmd_bits_inst_secondaryInst => cmd_sec,
            io_cmd_bits_inst_data => cmd_data, io_cmd_bits_additionalData => cmd_add,
            io_dma_readReq_ready => one, io_dma_readReq_valid => rreq_valid,
            io_dma_readReq_bits_addr => open, io_dma_readReq_bits_totalBytes => rreq_bytes,
            io_dma_readResp_ready => rresp_ready, io_dma_readResp_valid => rresp_valid,
            io_dma_readResp_bits_bytesRead => rresp_bytes,
            io_dma_readData_ready => rdata_ready, io_dma_readData_valid => rdata_valid, io_dma_readData_bits => rdata_bits,
            io_dma_writeReq_ready => one, io_dma_writeReq_valid => wreq_valid,
            io_dma_writeReq_bits_addr => wreq_addr, io_dma_writeReq_bits_data => wreq_data,
            io_dma_writeReq_bits_totalBytes => wreq_bytes,
            io_interrupt_rxError => irq_rx_error, io_interrupt_rxStart => irq_rx_start,
            io_interrupt_rxFinish => irq_rx_finish, io_interrupt_txError => irq_tx_error,
            io_interrupt_txFinish => irq_tx_finish,
            io_lutCmd_valid => lut_valid, io_lutCmd_bits_lut => lut_id, io_lutCmd_bits_address => lut_addr,
            io_lutCmd_bits_value => lut_value,
            io_firCmd_valid => zero, io_firCmd_bits_fir => zero4, io_firCmd_bits_coeff => zero6,
            io_firCmd_bits_value => zero22,
            io_messages_rxErrorMessage_ready => one, io_messages_rxErrorMessage_valid => msg_rx_error_valid,
            io_messages_rxErrorMessage_bits => msg_rx_error,
            io_messages_rxFinishMessage_ready => one, io_messages_rxFinishMessage_valid => msg_rx_finish_valid,
            io_messages_rxFinishMessage_bits => msg_rx_finish,
            io_messages_txErrorMessage_ready => one, io_messages_txErrorMessage_valid => msg_tx_error_valid,
            io_messages_txErrorMessage_bits => msg_tx_error,
            io_tuning_i_AGC_control_sampleWindow => zero8, io_tuning_i_AGC_control_idealPeakToPeak => zero8,
            io_tuning_i_AGC_control_toleranceP2P => zero8, io_tuning_i_AGC_control_gainInc => zero8,
            io_tuning_i_AGC_control_gainDec => zero8, io_tuning_i_AGC_control_reset => zero,
            io_tuning_i_AGC_useAGC => zero, io_tuning_i_DCO_control_gain => zero9,
            io_tuning_i_DCO_control_reset => zero, io_tuning_i_DCO_useDCO => zero,
            io_tuning_q_AGC_control_sampleWindow => zero8, io_tuning_q_AGC_control_idealPeakToPeak => zero8,
            io_tuning_q_AGC_control_toleranceP2P => zero8, io_tuning_q_AGC_control_gainInc => zero8,
            io_tuning_q_AGC_control_gainDec => zero8, io_tuning_q_AGC_control_reset => zero,
            io_tuning_q_AGC_useAGC => zero, io_tuning_q_DCO_control_gain => zero9,
            io_tuning_q_DCO_control_reset => zero, io_tuning_q_DCO_useDCO => zero,
            io_tuning_debug_enabled => zero,
            io_state_assemblerState => st_asm, io_state_disassemblerState => open, io_state_txState => st_tx,
            io_state_rxControllerState => open, io_state_txControllerState => st_txc,
            io_state_mainControllerState => st_main, io_state_modIndex => mod_index,
            io_state_i_agcIndex => open, io_state_i_dcoIndex => open,
            io_state_q_agcIndex => open, io_state_q_dcoIndex => open,
            io_state_bleBitCount => open, io_state_lrwpanBitCount => open,
            io_ifCounter_input_ifTickThreshold => zero32, io_ifCounter_input_control_restartCounter => zero,
            io_ifCounter_output_adcTicks => open, io_ifCounter_output_ifTicksPacket => open,
            io_ifCounter_output_adcTicksPacket => open, io_ifCounter_output_ifTicksPrevPacket => open,
            io_ifCounter_output_adcTicksPrevPacket => open, io_ifCounter_output_thresholdInterrupt => open);

    radio: process
        constant SGM : real := sqrt(CC_K_BOLTZ * CC_T0 * 10.0 ** (nf_db / 10.0) * CC_FS / 2.0);
        variable s1, s2 : positive := seed;
        variable up : boolean := false;                     -- reset done, tables loaded
        variable last_seq, out_seq, pin_seq : natural := 0;
        variable c : cc2652r_config;
        variable p : cc2652r_packet;
        variable t_ev, t_hit : time;
        variable stop : boolean;
        -- what the design shows before a clock edge
        variable v_cmd_ready, v_rreq, v_rresp_ready, v_rdata_ready, v_wreq, v_tx_on : boolean := false;
        variable v_rx_start, v_rx_finish, v_rx_error, v_tx_error, v_tx_finish : boolean := false;
        variable v_main, v_cap, v_coarse, v_mod : natural := 0;
        -- the host's side of the DMA streams and the messages
        type octets is array (natural range <>) of natural;
        variable mem : octets(0 to 511) := (others => 0);
        variable rd_total, rd_sent, rd_beats, wr_at : natural := 0;
        variable rd_data, rd_resp : boolean := false;
        variable fin_len, err_code : natural := 0;
        -- sending
        variable t : spec_lines := (others => IQ_ZERO);
        variable n, ns, nc, limit, first_on : natural := 0;
        variable amp, doff, ph, fc : real := 0.0;
        variable was_on, moved, modulating : boolean := false;
        -- receiving
        variable sig : rf_spectrum;
        variable dl : iq_array(0 to NT - 1) := (others => IQ_ZERO);
        variable dpos, quiet, plen, ifn, events : natural := 0;
        variable dec : iq_array(0 to SPEC_N - 1);
        variable rxph, drx, pw, gain, pw_hit : real := 0.0;
        variable busy, got : boolean := false;
        file trace_file : text;

        procedure gauss(g1, g2 : out real) is
            variable u1, u2, r : real;
        begin
            uniform(s1, s2, u1);
            uniform(s1, s2, u2);
            r := sqrt(-2.0 * log(realmax(u1, 1.0e-300)));
            g1 := r * cos(2.0 * MATH_PI * u2);
            g2 := r * sin(2.0 * MATH_PI * u2);
        end procedure;

        impure function tx_pending return boolean is
        begin
            return tx.seq /= last_seq and tx.seq /= 0 and tx.len >= 2;
        end function;

        function beat_of(m : octets; at : natural) return logic3d_vector is
            variable r : logic3d_vector(31 downto 0);
        begin
            for k in 0 to 3 loop
                r(8 * k + 7 downto 8 * k) := l3v(m(at + k), 8);
            end loop;
            return r;
        end function;

        -- One clock.  What the design shows is taken just before the edge, when what was put on its
        -- inputs after the edge before has settled; then the host's side of the DMA streams and of
        -- the messages moves on, as the edge has moved the design's.
        procedure cycle(h : time) is
            variable a : natural;
            variable l : line;
        begin
            wait for h;
            if trace /= "" then
                -- inputs: reset, ADCs, command, read count, read data, table command
                write(l, 16 * b(rst) + 8 * b(cmd_valid) + 4 * b(rresp_valid) + 2 * b(rdata_valid) + b(lut_valid));
                write(l, ' '); write(l, int_of(adc_i));
                write(l, ' '); write(l, int_of(adc_q));
                write(l, ' '); write(l, int_of(cmd_prim));
                write(l, ' '); write(l, int_of(cmd_sec));
                write(l, ' '); write(l, int_of(cmd_data));
                write(l, ' '); write(l, int_of(cmd_add(31 downto 16)));
                write(l, ' '); write(l, int_of(cmd_add(15 downto 0)));
                write(l, ' '); write(l, int_of(rresp_bytes));
                write(l, ' '); write(l, int_of(rdata_bits(31 downto 16)));
                write(l, ' '); write(l, int_of(rdata_bits(15 downto 0)));
                write(l, ' '); write(l, int_of(lut_id));
                write(l, ' '); write(l, int_of(lut_addr));
                write(l, ' '); write(l, int_of(lut_value));
                -- outputs
                write(l, ' ');
                write(l, 8192 * b(tx_on) + 4096 * b(cmd_ready) + 2048 * b(rreq_valid) + 1024 * b(rresp_ready) + 512 * b(rdata_ready)
                         + 256 * b(wreq_valid) + 128 * b(irq_rx_error) + 64 * b(irq_rx_start) + 32 * b(irq_rx_finish)
                         + 16 * b(irq_tx_error) + 8 * b(irq_tx_finish) + 4 * b(msg_rx_error_valid) + 2 * b(msg_rx_finish_valid)
                         + b(msg_tx_error_valid));
                write(l, ' '); write(l, int_of(cap_mod));
                write(l, ' '); write(l, int_of(cap_coarse));
                write(l, ' '); write(l, int_of(mod_index));
                write(l, ' '); write(l, int_of(st_main));
                write(l, ' '); write(l, int_of(st_tx));
                write(l, ' '); write(l, int_of(rreq_bytes));
                write(l, ' '); write(l, int_of(wreq_addr(15 downto 0)));
                write(l, ' '); write(l, int_of(wreq_data(31 downto 16)));
                write(l, ' '); write(l, int_of(wreq_data(15 downto 0)));
                write(l, ' '); write(l, int_of(wreq_bytes));
                write(l, ' '); write(l, int_of(msg_rx_finish(15 downto 0)));
                write(l, ' '); write(l, int_of(msg_rx_error(15 downto 0)));
                writeline(trace_file, l);
            end if;
            v_cmd_ready := is_one(cmd_ready);
            v_rreq := is_one(rreq_valid);
            v_rresp_ready := is_one(rresp_ready);
            v_rdata_ready := is_one(rdata_ready);
            v_wreq := is_one(wreq_valid);
            v_tx_on := is_one(tx_on);
            v_rx_start := is_one(irq_rx_start);
            v_rx_finish := is_one(irq_rx_finish);
            v_rx_error := is_one(irq_rx_error);
            v_tx_error := is_one(irq_tx_error);
            v_tx_finish := is_one(irq_tx_finish);
            v_main := int_of(st_main);
            v_mod := int_of(st_tx);
            v_cap := int_of(cap_mod);
            v_coarse := int_of(cap_coarse);
            if v_wreq then                                  -- (ready is held)
                a := int_of(wreq_addr(15 downto 0));
                for k in 0 to int_of(wreq_bytes) - 1 loop
                    if a >= RX_BASE and a - RX_BASE + k <= mem'high then
                        mem(a - RX_BASE + k) := int_of(wreq_data(8 * k + 7 downto 8 * k));
                        wr_at := a - RX_BASE + k + 1;
                    end if;
                end loop;
            end if;
            if is_one(msg_rx_finish_valid) then
                fin_len := int_of(msg_rx_finish(9 downto 0));
            end if;
            if is_one(msg_rx_error_valid) then
                err_code := int_of(msg_rx_error(5 downto 0));
            end if;
            if is_one(msg_tx_error_valid) then
                report "ucb_bmc_radio: the design's transmit error " & integer'image(int_of(msg_tx_error(5 downto 0))) severity warning;
            end if;
            clk <= L3D_1;
            wait for h;
            clk <= L3D_0;
            -- the read side of the DMA: the request, then the data in beats of four and the count
            if v_rreq then
                rd_total := int_of(rreq_bytes);
                rd_beats := (rd_total + 3) / 4;
                rd_sent := 0;
                rd_data := true;
                rd_resp := true;
                rdata_valid <= L3D_1;
                rdata_bits <= beat_of(mem, 0);
                rresp_valid <= L3D_1;
                rresp_bytes <= l3v(rd_total, 9);
            else
                if rd_data and v_rdata_ready then
                    rd_sent := rd_sent + 1;
                    if rd_sent >= rd_beats then
                        rd_data := false;
                        rdata_valid <= L3D_0;
                    else
                        rdata_bits <= beat_of(mem, 4 * rd_sent);
                    end if;
                end if;
                if rd_resp and v_rresp_ready then
                    rd_resp := false;
                    rresp_valid <= L3D_0;
                end if;
            end if;
        end procedure;

        procedure command(prim, sec, data : natural; add : logic3d_vector(31 downto 0); h : time) is
            variable k : natural := 0;
        begin
            cmd_prim <= l3v(prim, 4);
            cmd_sec <= l3v(sec, 4);
            cmd_data <= l3v(data, 24);
            cmd_add <= add;
            cmd_valid <= L3D_1;
            loop
                cycle(h);
                exit when v_cmd_ready;
                k := k + 1;
                assert k < 1000 report "ucb_bmc_radio: the design does not take a command" severity failure;
            end loop;
            cmd_valid <= L3D_0;
        end procedure;

        -- reset and the tables (once, and when the design was left in the middle of something), then
        -- the link's constants
        procedure configure is
        begin
            if not up or v_main /= 0 then
                rst <= L3D_1;
                for k in 1 to 4 loop
                    cycle(FAST);
                end loop;
                rst <= L3D_0;
                rd_data := false;
                rd_resp := false;
                rdata_valid <= L3D_0;
                rresp_valid <= L3D_0;
                lut_valid <= L3D_1;
                for k in 0 to 63 loop                       -- VCO_MOD
                    lut_id <= l3v(0, 4);
                    lut_addr <= l3v(k, 6);
                    lut_value <= l3v(2 + 4 * k, 22);
                    cycle(FAST);
                end loop;
                for k in 0 to 39 loop                       -- VCO_CT_BLE: coarse code, the RF channel
                    lut_id <= l3v(1, 4);
                    lut_addr <= l3v(k, 6);
                    lut_value <= l3v(rf_channel(k), 22);
                    cycle(FAST);
                end loop;
                lut_valid <= L3D_0;
                cycle(FAST);
                up := true;
            end if;
            command(0, 0, 0, l3v(0, 32), FAST);                             -- BLE
            command(0, 1, 0, l3v(c.crc_init, 32), FAST);
            command(0, 2, 0, aa_of(c.access_address), FAST);
            command(0, 4, 0, l3v(c.whiten, 32), FAST);
            cycle(FAST);
            fc := ble_rf_channel_frequency(v_coarse);
        end procedure;

        -- the event gathered in t, to the pin
        procedure emit is
        begin
            pin_seq := pin_seq + 1;
            pin_out <= (h => time_to_lines(t), v => LINES_ZERO, freq => fc, df => CC_FS / real(SPEC_N), seq => pin_seq);
            t := (others => IQ_ZERO);
            n := 0;
            t_ev := now;
        end procedure;

        -- front end: one event of the pin (sig) with the receiver's carrier error and noise, through
        -- the channel filter and up to the intermediate frequency: dec.  pw: the signal's power in
        -- this event, W.  gain: what brings it to adc_level.
        procedure front_end is
            variable r : rf_spectrum;
            variable x : spec_lines := LINES_ZERO;
            variable pwf, g1, g2, cs, sn, re, im, a : real := 0.0;
            variable y : iq_sample;
            variable j : natural;
        begin
            pw := 0.0;
            if spec_is_silent(sig) then
                quiet := quiet + 1;
            else
                quiet := 0;
                r := spec_regrid(sig, fc, 0.0);
                if not spec_is_silent(r) then
                    x := lines_to_time(r.h);
                end if;
            end if;
            for i in x'range loop
                pw := pw + x(i).i * x(i).i + x(i).q * x(i).q;
                cs := cos(rxph);
                sn := sin(rxph);
                gauss(g1, g2);
                re := x(i).i * cs - x(i).q * sn + g1 * SGM;
                im := x(i).i * sn + x(i).q * cs + g2 * SGM;
                rxph := rxph + drx;
                if rxph > MATH_PI then
                    rxph := rxph - 2.0 * MATH_PI;
                elsif rxph < -MATH_PI then
                    rxph := rxph + 2.0 * MATH_PI;
                end if;
                dpos := (dpos + 1) mod NT;
                dl(dpos) := (re, im);
                y := IQ_ZERO;
                j := dpos;
                for k in 0 to NT - 1 loop
                    y.i := y.i + FIR(k) * dl(j).i;
                    y.q := y.q + FIR(k) * dl(j).q;
                    if j = 0 then
                        j := NT - 1;
                    else
                        j := j - 1;
                    end if;
                end loop;
                pwf := pwf + y.i * y.i + y.q * y.q;
                -- the mixer's oscillator is 2 MHz below the channel: a sixteenth of a turn a sample
                a := 2.0 * MATH_PI * real(ifn) / 16.0;
                ifn := (ifn + 1) mod 16;
                dec(i) := (y.i * cos(a) - y.q * sin(a), y.i * sin(a) + y.q * cos(a));
            end loop;
            pw := pw / real(SPEC_N);
            gain := adc_level / sqrt(realmax(pwf / real(SPEC_N), 1.0e-30));
        end procedure;

        function adc(x : real) return logic3d_vector is
        begin
            return l3v(integer(realmax(realmin(round(256.0 * (x + 0.5)), 255.0), 0.0)), 8);
        end function;
    begin
        if trace /= "" then
            file_open(trace_file, trace, write_mode);
        end if;
        loop
            if not tx_pending then
                wait on tx, pin_in, cfg;
            end if;
            stop := true;
            if tx_pending then
                stop := false;
            elsif cfg.rx_on and pin_in'event and not spec_is_silent(pin_in) and cfg.phy = PHY_1M and cfg.whiten >= 0 then
                stop := false;
            end if;

            if not stop then
                c := cfg;
                assert c.phy = PHY_1M and c.whiten >= 0
                    report "ucb_bmc_radio: LE 1M, whitened, only" severity failure;
                if tx_pending then
                    p := tx;
                    last_seq := p.seq;
                    sending <= true;
                    configure;
                    for k in 0 to p.len - 1 loop
                        mem(k) := p.pdu(k);
                    end loop;
                    amp := sqrt(cc_dbm_w(c.tx_power));
                    doff := 2.0 * MATH_PI * fc * c.xo_ppm * 1.0e-6 / CC_FS;
                    limit := (p.len + 12) * 64 * 32;
                    modulating := false;
                    t := (others => IQ_ZERO);
                    n := 0;
                    ns := 0;
                    nc := 0;
                    ph := 0.0;
                    was_on := false;
                    moved := false;
                    command(1, 0, p.len, l3v(0, 32), HALF);                 -- send
                    loop
                        cycle(HALF);
                        nc := nc + 1;
                        if v_tx_on then
                            -- the VCO: its modulation code about the middle one, and the crystal's error
                            ph := ph + 2.0 * MATH_PI * KMOD * real(v_cap - 128) / CC_FS + doff;
                            if ph > MATH_PI then
                                ph := ph - 2.0 * MATH_PI;
                            elsif ph < -MATH_PI then
                                ph := ph + 2.0 * MATH_PI;
                            end if;
                            t(n) := (amp * cos(ph), amp * sin(ph));
                            n := n + 1;
                            ns := ns + 1;
                            if not moved and abs (v_cap - 128) > 8 then
                                moved := true;
                                first_on := ns;
                            end if;
                            was_on := true;
                            if n = SPEC_N then
                                emit;
                            end if;
                        end if;
                        exit when was_on and not v_tx_on;
                        if v_mod /= 0 then
                            modulating := true;
                        elsif modulating and tx_end then
                            exit;                           -- (left in its transmit state: the next configure resets it)
                        end if;
                        if nc > limit then
                            report "ucb_bmc_radio: the design did not finish a packet of " & integer'image(p.len) & " octets (controller "
                                & integer'image(v_main) & ", transmit controller " & integer'image(int_of(st_txc)) & ", assembler "
                                & integer'image(int_of(st_asm)) & ", modulator " & integer'image(int_of(st_tx)) & ", read "
                                & integer'image(rd_sent) & " of " & integer'image(rd_beats) & " beats, count taken " & boolean'image(not rd_resp) & ")" severity warning;
                            exit;
                        end if;
                    end loop;
                    if debug then
                        report "ucb_bmc_radio: sent " & integer'image(p.len) & " octets, " & integer'image(ns) & " samples in "
                            & integer'image(nc) & " clocks, the code moves at sample " & integer'image(first_on);
                    end if;
                    if n > 0 then                           -- the last, part-filled event
                        wait for t_ev + CC_T_EVENT - now;
                        emit;
                    end if;
                    wait for t_ev + CC_T_EVENT - now;
                    pin_seq := pin_seq + 1;
                    pin_out <= spec_silent(pin_seq);
                    sending <= false;
                else
                    configure;
                    wr_at := 0;
                    busy := false;
                    got := false;
                    events := 0;
                    command(2, 0, 0, l3v(RX_BASE, 32), FAST);               -- receive
                    for k in 1 to 8 loop
                        cycle(FAST);
                    end loop;
                    if debug then
                        report "ucb_bmc_radio: receiver wakes";
                    end if;
                    drx := -2.0 * MATH_PI * fc * c.xo_ppm * 1.0e-6 / CC_FS;
                    dl := (others => IQ_ZERO);
                    quiet := 0;
                    t_ev := now + CC_T_EVENT / 2;
                    wait for t_ev - now;
                    loop
                        sig := pin_in;
                        front_end;
                        events := events + 1;
                        for k in dec'range loop
                            adc_i <= adc(dec(k).i * gain);
                            adc_q <= adc(dec(k).q * gain);
                            cycle(HALF);
                            if v_rx_start then
                                t_hit := now;
                                pw_hit := pw;
                                busy := true;
                                if debug then
                                    report "ucb_bmc_radio: access address found";
                                end if;
                            end if;
                            if v_rx_finish or v_rx_error then
                                p := CC2652R_NO_PACKET;
                                p.crc_ok := v_rx_finish;
                                p.rssi := round(cc_w_dbm(pw_hit));
                                if p.crc_ok then
                                    plen := fin_len + 2;             -- (the design counts the payload)
                                    p.len := plen;
                                    for a in 0 to p.len - 1 loop
                                        p.pdu(a) := mem(a);
                                    end loop;
                                    p.t_end := t_hit - rx_hit_delay + (8 * plen + 24) * 1 us;
                                else
                                    p.len := 2;
                                    p.t_end := now;
                                end if;
                                out_seq := out_seq + 1;
                                p.seq := out_seq;
                                rx <= p;
                                got := true;
                                if debug then
                                    report "ucb_bmc_radio: packet of " & integer'image(fin_len) & " octets (" & integer'image(wr_at)
                                        & " stored), CRC " & boolean'image(p.crc_ok) & ", error " & integer'image(err_code);
                                end if;
                            end if;
                            stop := got or tx_pending or cfg /= c;
                            exit when stop;
                        end loop;
                        exit when stop or (quiet >= FLUSH and not busy) or events > 2000;
                        t_ev := t_ev + CC_T_EVENT;
                        if now < t_ev then
                            wait for t_ev - now;
                        end if;
                    end loop;
                    -- (a packet taken leaves the design idle; anything else is reset by the next configure)
                    for k in 1 to 4 loop
                        cycle(FAST);
                    end loop;
                end if;
            end if;
        end loop;
    end process;
end architecture;
