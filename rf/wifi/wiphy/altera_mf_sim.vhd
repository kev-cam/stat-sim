-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- altera_mf_sim: behavioural stand-ins for the two Altera (Intel) megafunctions that bladeRF-wiphy
-- instantiates, so that the modem simulates without the vendor's simulation library.  Compile into a
-- library named altera_mf.
--
--   scfifo   single-clock FIFO        dcfifo   dual-clock FIFO
--
-- Written from the megafunctions' published port, parameter and latency descriptions (Altera "SCFIFO
-- and DCFIFO IP Cores User Guide", UG-MFNALT_FIFO, 2016.08.29); nothing of the vendor's source.  What
-- the design uses is modelled: show-ahead and normal read, the status flags and word counts,
-- asynchronous and synchronous clear, a request ignored when the FIFO is full (write) or empty (read),
-- which is the megafunctions' default (overflow and underflow checking on).
--
-- The LATENCIES are the guide's (its tables "Output Latency of the Status Flags"), because the modem
-- depends on them: its receiver places the FFT window by counting the samples that come out of a
-- dual-clock FIFO from a mark that does not go through it, so a FIFO that hands the samples over too
-- soon puts every window late, into the next symbol.
--
--   scfifo   wrreq or rdreq to full, to usedw: 1 clock.  rdreq to empty, to q: 1.
--            wrreq to empty (and, show-ahead, to q): normal output 1, show-ahead 2, and one more of
--            each with add_ram_output_register "ON".
--   dcfifo   wrreq to wrfull, wrempty: 1 wrclk; to wrusedw: 2 wrclk;
--            to rdempty, rdfull: 2 wrclk and the n rdclk that follow; to rdusedw: one rdclk more.
--            rdreq to rdempty, rdfull, q: 1 rdclk; to rdusedw: 2 rdclk;
--            to wrfull, wrempty: 1 rdclk and the n wrclk that follow; to wrusedw: one wrclk more.
--            n is the number of synchroniser stages: rdsync_delaypipe (for the write pointer going to
--            the read side) or wrsync_delaypipe, less two, and one when the parameter is not given
--            (the guide: "the default value of 3 for these parameters corresponds to a single
--            synchronization stage", for Stratix II, Cyclone II and later).
--
-- A pointer leaves its clock domain TCQ after the clock edge, so that a register of the other domain
-- clocked at the same instant takes the old value whatever the order of the two edges in delta cycles,
-- as a flip-flop does.
library ieee;
use ieee.std_logic_1164.all;

package altera_mf_components is
    component scfifo is
        generic (
            lpm_width               : natural;
            lpm_widthu              : natural := 1;
            lpm_numwords            : natural;
            lpm_showahead           : string := "OFF";
            lpm_type                : string := "scfifo";
            lpm_hint                : string := "UNUSED";
            intended_device_family  : string := "unused";
            add_ram_output_register : string := "OFF";
            almost_full_value       : natural := 0;
            almost_empty_value      : natural := 0;
            overflow_checking       : string := "ON";
            underflow_checking      : string := "ON";
            use_eab                 : string := "ON");
        port (
            clock        : in  std_logic;
            data         : in  std_logic_vector(lpm_width - 1 downto 0);
            wrreq        : in  std_logic;
            rdreq        : in  std_logic;
            aclr         : in  std_logic := '0';
            sclr         : in  std_logic := '0';
            q            : out std_logic_vector(lpm_width - 1 downto 0);
            empty        : out std_logic;
            full         : out std_logic;
            almost_full  : out std_logic;
            almost_empty : out std_logic;
            usedw        : out std_logic_vector(lpm_widthu - 1 downto 0));
    end component;

    component dcfifo is
        generic (
            lpm_width              : natural;
            lpm_widthu             : natural := 1;
            lpm_numwords           : natural;
            lpm_showahead          : string := "OFF";
            lpm_type               : string := "dcfifo";
            lpm_hint               : string := "UNUSED";
            intended_device_family : string := "unused";
            overflow_checking      : string := "ON";
            underflow_checking     : string := "ON";
            rdsync_delaypipe       : natural := 0;
            wrsync_delaypipe       : natural := 0;
            use_eab                : string := "ON");
        port (
            aclr    : in  std_logic := '0';
            wrclk   : in  std_logic;
            wrreq   : in  std_logic;
            data    : in  std_logic_vector(lpm_width - 1 downto 0);
            wrfull  : out std_logic;
            wrempty : out std_logic;
            wrusedw : out std_logic_vector(lpm_widthu - 1 downto 0);
            rdclk   : in  std_logic;
            rdreq   : in  std_logic;
            q       : out std_logic_vector(lpm_width - 1 downto 0);
            rdfull  : out std_logic;
            rdempty : out std_logic;
            rdusedw : out std_logic_vector(lpm_widthu - 1 downto 0));
    end component;
end package;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity scfifo is
    generic (
        lpm_width               : natural;
        lpm_widthu              : natural := 1;
        lpm_numwords            : natural;
        lpm_showahead           : string := "OFF";
        lpm_type                : string := "scfifo";
        lpm_hint                : string := "UNUSED";
        intended_device_family  : string := "unused";
        add_ram_output_register : string := "OFF";
        almost_full_value       : natural := 0;
        almost_empty_value      : natural := 0;
        overflow_checking       : string := "ON";
        underflow_checking      : string := "ON";
        use_eab                 : string := "ON");
    port (
        clock        : in  std_logic;
        data         : in  std_logic_vector(lpm_width - 1 downto 0);
        wrreq        : in  std_logic;
        rdreq        : in  std_logic;
        aclr         : in  std_logic := '0';
        sclr         : in  std_logic := '0';
        q            : out std_logic_vector(lpm_width - 1 downto 0);
        empty        : out std_logic;
        full         : out std_logic;
        almost_full  : out std_logic;
        almost_empty : out std_logic;
        usedw        : out std_logic_vector(lpm_widthu - 1 downto 0));
end entity;

architecture sim of scfifo is
    type mem_t is array (0 to lpm_numwords - 1) of std_logic_vector(lpm_width - 1 downto 0);
    signal mem   : mem_t := (others => (others => '0'));
    constant SHOWAHEAD : boolean := lpm_showahead = "ON";
    constant OUTREG    : boolean := add_ram_output_register = "ON";
    -- clocks, after the one that writes a word, until the read side has it
    constant LAG : natural := boolean'pos(SHOWAHEAD) + boolean'pos(OUTREG);
    signal rd, wr : natural range 0 to lpm_numwords - 1 := 0;
    signal count : natural range 0 to lpm_numwords := 0;     -- words held
    signal seen  : natural range 0 to lpm_numwords := 0;     -- of them, those the read side has
    signal late  : std_logic_vector(0 to 2) := "000";        -- late(k): a word was written k + 1 clocks ago
    signal q_reg : std_logic_vector(lpm_width - 1 downto 0) := (others => '0');

    function bool_sl(b : boolean) return std_logic is
    begin
        if b then
            return '1';
        end if;
        return '0';
    end function;
begin
    process (clock, aclr)
        variable do_wr, do_rd : boolean;
        variable new_seen : natural range 0 to lpm_numwords + 1;
        variable new_rd : natural range 0 to lpm_numwords - 1;
    begin
        if aclr = '1' then
            rd <= 0;
            wr <= 0;
            count <= 0;
            seen <= 0;
            late <= "000";
            q_reg <= (others => '0');
        elsif rising_edge(clock) then
            if sclr = '1' then
                rd <= 0;
                wr <= 0;
                count <= 0;
                seen <= 0;
                late <= "000";
            else
                do_wr := wrreq = '1' and count < lpm_numwords;
                do_rd := rdreq = '1' and seen > 0;
                new_seen := seen;
                new_rd := rd;
                if do_wr then
                    mem(wr) <= data;
                    wr <= (wr + 1) mod lpm_numwords;
                end if;
                if do_rd then
                    if not SHOWAHEAD then
                        q_reg <= mem(rd);
                    end if;
                    new_rd := (rd + 1) mod lpm_numwords;
                    new_seen := new_seen - 1;
                end if;
                if (LAG = 0 and do_wr) or (LAG > 0 and late(LAG - 1) = '1') then
                    new_seen := new_seen + 1;
                end if;
                late <= bool_sl(do_wr) & late(0 to 1);
                if do_wr and not do_rd then
                    count <= count + 1;
                elsif do_rd and not do_wr then
                    count <= count - 1;
                end if;
                rd <= new_rd;
                seen <= new_seen;
                -- show-ahead: the output register takes the word at the head as soon as the read side
                -- has one (it was written at an earlier clock, so the memory already holds it)
                if SHOWAHEAD and new_seen > 0 then
                    q_reg <= mem(new_rd);
                end if;
            end if;
        end if;
    end process;

    q <= q_reg;
    empty <= '1' when seen = 0 else '0';
    full <= '1' when count = lpm_numwords else '0';
    almost_full <= '1' when count >= almost_full_value and almost_full_value > 0 else '0';
    almost_empty <= '1' when seen < almost_empty_value else '0';
    usedw <= std_logic_vector(to_unsigned(count mod 2 ** lpm_widthu, lpm_widthu));
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity dcfifo is
    generic (
        lpm_width              : natural;
        lpm_widthu             : natural := 1;
        lpm_numwords           : natural;
        lpm_showahead          : string := "OFF";
        lpm_type               : string := "dcfifo";
        lpm_hint               : string := "UNUSED";
        intended_device_family : string := "unused";
        overflow_checking      : string := "ON";
        underflow_checking     : string := "ON";
        rdsync_delaypipe       : natural := 0;
        wrsync_delaypipe       : natural := 0;
        use_eab                : string := "ON");
    port (
        aclr    : in  std_logic := '0';
        wrclk   : in  std_logic;
        wrreq   : in  std_logic;
        data    : in  std_logic_vector(lpm_width - 1 downto 0);
        wrfull  : out std_logic;
        wrempty : out std_logic;
        wrusedw : out std_logic_vector(lpm_widthu - 1 downto 0);
        rdclk   : in  std_logic;
        rdreq   : in  std_logic;
        q       : out std_logic_vector(lpm_width - 1 downto 0);
        rdfull  : out std_logic;
        rdempty : out std_logic;
        rdusedw : out std_logic_vector(lpm_widthu - 1 downto 0));
end entity;

architecture sim of dcfifo is
    type mem_t is array (0 to lpm_numwords - 1) of std_logic_vector(lpm_width - 1 downto 0);
    signal mem   : mem_t := (others => (others => '0'));
    constant SHOWAHEAD : boolean := lpm_showahead = "ON";
    constant TCQ : time := 1 ps;

    -- synchroniser stages for a pipeline parameter: the parameter less two, and one for the default
    function stages(delaypipe : natural) return positive is
    begin
        if delaypipe <= 3 then
            return 1;
        end if;
        return delaypipe - 2;
    end function;
    constant NR : positive := stages(rdsync_delaypipe);      -- write pointer, into the read clock
    constant NW : positive := stages(wrsync_delaypipe);      -- read pointer, into the write clock

    -- the pointers count words modulo twice the depth, which tells full from empty
    constant M : positive := 2 * lpm_numwords;
    subtype ptr_t is natural range 0 to M - 1;
    type sync_t is array (natural range <>) of ptr_t;
    signal wptr, wptr_d, wptr_x : ptr_t := 0;      -- write pointer; a wrclk later; as it leaves the domain
    signal rptr, rptr_x : ptr_t := 0;              -- read pointer; as it leaves the domain
    signal wsync : sync_t(0 to NR - 1) := (others => 0);     -- the write pointer in the read clock
    signal rsync : sync_t(0 to NW - 1) := (others => 0);     -- the read pointer in the write clock
    signal wfill, rfill : natural range 0 to M - 1 := 0;     -- the fill as each side has it
    signal wrusedw_r, rdusedw_r : natural range 0 to M - 1 := 0;
    signal q_reg : std_logic_vector(lpm_width - 1 downto 0) := (others => '0');
begin
    wptr_x <= transport wptr_d after TCQ;
    rptr_x <= transport rptr after TCQ;
    wfill <= (wptr + M - rsync(NW - 1)) mod M;
    rfill <= (wsync(NR - 1) + M - rptr) mod M;

    process (wrclk, aclr)
    begin
        if aclr = '1' then
            wptr <= 0;
            wptr_d <= 0;
            rsync <= (others => 0);
            wrusedw_r <= 0;
        elsif rising_edge(wrclk) then
            if wrreq = '1' and wfill < lpm_numwords then
                mem(wptr mod lpm_numwords) <= data;
                wptr <= (wptr + 1) mod M;
            end if;
            wptr_d <= wptr;
            for k in NW - 1 downto 1 loop
                rsync(k) <= rsync(k - 1);
            end loop;
            rsync(0) <= rptr_x;
            wrusedw_r <= wfill;
        end if;
    end process;

    process (rdclk, aclr)
    begin
        if aclr = '1' then
            rptr <= 0;
            wsync <= (others => 0);
            rdusedw_r <= 0;
            q_reg <= (others => '0');
        elsif rising_edge(rdclk) then
            if rdreq = '1' and rfill > 0 then
                q_reg <= mem(rptr mod lpm_numwords);
                rptr <= (rptr + 1) mod M;
            end if;
            for k in NR - 1 downto 1 loop
                wsync(k) <= wsync(k - 1);
            end loop;
            wsync(0) <= wptr_x;
            rdusedw_r <= rfill;
        end if;
    end process;

    -- show-ahead: the word at the head, which has been in the memory for two write clocks and more by
    -- the time rdempty lets the reader take it
    q <= mem(rptr mod lpm_numwords) when SHOWAHEAD else q_reg;
    rdempty <= '1' when rfill = 0 else '0';
    rdfull <= '1' when rfill >= lpm_numwords else '0';
    wrempty <= '1' when wfill = 0 else '0';
    wrfull <= '1' when wfill >= lpm_numwords else '0';
    rdusedw <= std_logic_vector(to_unsigned(rdusedw_r mod 2 ** lpm_widthu, lpm_widthu));
    wrusedw <= std_logic_vector(to_unsigned(wrusedw_r mod 2 ** lpm_widthu, lpm_widthu));
end architecture;
