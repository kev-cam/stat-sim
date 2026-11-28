-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- lpm_sim: a behavioural stand-in for the LPM divider that bladeRF-wiphy instantiates (wlan_divide),
-- so that the modem simulates without the vendor's simulation library.  Compile into a library named
-- lpm.
--
--   lpm_divide   quotient and remainder of numer / denom, lpm_pipeline clocks later
--
-- Written from the LPM_DIVIDE description (EIA-IS103 library of parameterized modules, Intel "Integer
-- Arithmetic IP Cores User Guide"); nothing of the vendor's source.  Each operand is signed or
-- unsigned as its representation parameter says.  With LPM_REMAINDERPOSITIVE=TRUE in lpm_hint the
-- remainder is never negative (the quotient is rounded down for a negative numerator); otherwise the
-- quotient is rounded towards zero.  A zero denominator gives zeros (the real divider gives no
-- defined value).
library ieee;
use ieee.std_logic_1164.all;

package lpm_components is
    component lpm_divide is
        generic (
            lpm_widthn          : natural;
            lpm_widthd          : natural;
            lpm_nrepresentation : string := "UNSIGNED";
            lpm_drepresentation : string := "UNSIGNED";
            lpm_pipeline        : natural := 0;
            lpm_type            : string := "LPM_DIVIDE";
            lpm_hint            : string := "LPM_REMAINDERPOSITIVE=TRUE");
        port (
            numer    : in  std_logic_vector(lpm_widthn - 1 downto 0);
            denom    : in  std_logic_vector(lpm_widthd - 1 downto 0);
            clock    : in  std_logic := '0';
            aclr     : in  std_logic := '0';
            clken    : in  std_logic := '1';
            quotient : out std_logic_vector(lpm_widthn - 1 downto 0);
            remain   : out std_logic_vector(lpm_widthd - 1 downto 0));
    end component;
end package;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity lpm_divide is
    generic (
        lpm_widthn          : natural;
        lpm_widthd          : natural;
        lpm_nrepresentation : string := "UNSIGNED";
        lpm_drepresentation : string := "UNSIGNED";
        lpm_pipeline        : natural := 0;
        lpm_type            : string := "LPM_DIVIDE";
        lpm_hint            : string := "LPM_REMAINDERPOSITIVE=TRUE");
    port (
        numer    : in  std_logic_vector(lpm_widthn - 1 downto 0);
        denom    : in  std_logic_vector(lpm_widthd - 1 downto 0);
        clock    : in  std_logic := '0';
        aclr     : in  std_logic := '0';
        clken    : in  std_logic := '1';
        quotient : out std_logic_vector(lpm_widthn - 1 downto 0);
        remain   : out std_logic_vector(lpm_widthd - 1 downto 0));
end entity;

architecture sim of lpm_divide is
    constant W : positive := lpm_widthn + lpm_widthd + 2;      -- room for either operand, signed
    constant N_SIGNED : boolean := lpm_nrepresentation = "SIGNED";
    constant D_SIGNED : boolean := lpm_drepresentation = "SIGNED";

    function has(s, what : string) return boolean is
    begin
        for i in s'low to s'high - what'length + 1 loop
            if s(i to i + what'length - 1) = what then
                return true;
            end if;
        end loop;
        return false;
    end function;
    constant REM_POSITIVE : boolean := not has(lpm_hint, "LPM_REMAINDERPOSITIVE=FALSE");

    subtype result_t is std_logic_vector(lpm_widthn + lpm_widthd - 1 downto 0);     -- quotient & remainder
    type stage_array is array (natural range <>) of result_t;
    signal stages : stage_array(0 to lpm_pipeline) := (others => (others => '0'));
    signal now_r : result_t;

    function divide(numer : std_logic_vector(lpm_widthn - 1 downto 0);
                    denom : std_logic_vector(lpm_widthd - 1 downto 0)) return result_t is
        variable n, d, q, r : signed(W - 1 downto 0);
    begin
        if is_x(numer) or is_x(denom) then
            return (result_t'range => '0');
        end if;
        if N_SIGNED then
            n := resize(signed(numer), W);
        else
            n := signed(resize(unsigned(numer), W));
        end if;
        if D_SIGNED then
            d := resize(signed(denom), W);
        else
            d := signed(resize(unsigned(denom), W));
        end if;
        if d = 0 then
            return (result_t'range => '0');
        end if;
        q := n / d;                      -- rounds towards zero
        r := n - resize(q * d, W);
        if REM_POSITIVE and r < 0 then
            if d > 0 then
                q := q - 1;
                r := r + d;
            else
                q := q + 1;
                r := r - d;
            end if;
        end if;
        return std_logic_vector(q(lpm_widthn - 1 downto 0)) & std_logic_vector(r(lpm_widthd - 1 downto 0));
    end function;
begin
    now_r <= divide(numer, denom);

    comb: if lpm_pipeline = 0 generate
        quotient <= now_r(now_r'high downto lpm_widthd);
        remain <= now_r(lpm_widthd - 1 downto 0);
    end generate;

    piped: if lpm_pipeline > 0 generate
        process (clock, aclr)
        begin
            if aclr = '1' then
                stages <= (others => (others => '0'));
            elsif rising_edge(clock) then
                if clken = '1' then
                    stages(1 to lpm_pipeline) <= now_r & stages(1 to lpm_pipeline - 1);
                end if;
            end if;
        end process;
        quotient <= stages(lpm_pipeline)(result_t'high downto lpm_widthd);
        remain <= stages(lpm_pipeline)(lpm_widthd - 1 downto 0);
    end generate;
end architecture;
