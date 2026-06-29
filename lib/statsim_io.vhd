-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
-- statsim_io.vhd -- stat-sim boundary cells for CDC analysis.
--   statsim_inv   : converts 01XZ digital logic (std_ulogic) -> prob_load (inverting).
--                   This is the "lift into the probability domain" entry point: a
--                   regular 4-state testbench drives 01XZ, the inverter hands the
--                   probability discipline to the stat-sim latch.
--   statsim_latch : a level-sensitive D-latch on prob_load that FLAGS the CDC
--                   metastability risk -- if the data is transitioning (or already
--                   invalid) when the latch closes, it drives PL_X and reports.

library ieee;
use ieee.std_logic_1164.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_inv is
  port ( i : in  std_ulogic;          -- 01XZ digital input (the "Verilog" side)
         o : out resolved_pl );        -- probability output (inverted)
end entity;

architecture rtl of statsim_inv is
begin
  process(i) begin
    case i is
      when '1' | 'H' => o <= PL_0;     -- NOT 1 = clean 0
      when '0' | 'L' => o <= PL_1;     -- NOT 0 = clean 1
      when others    => o <= PL_X;     -- X/Z/U/W -> invalid probability level
    end case;
  end process;
end architecture;


library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_latch is
  generic ( TAU       : real := 15.7e-12;     -- metastability resolution constant (s)
            TSETUP    : time := 90 ps;        -- aperture before the latching edge
            TCQ0      : time := 60 ps;        -- intrinsic enable->q
            R_DRIVE   : real := 100.0;
            TMETA_MAX : time := 5 ns;
            SEED      : integer := 1 );
  port ( d   : in    resolved_pl;
         clk : in    resolved_pl;            -- enable: transparent when high
         q   : inout resolved_pl := PL_FLOAT );
end entity;

architecture pwl of statsim_latch is
begin
  process(clk, d)
    variable en, prev_en, dhi, meta : boolean := false;
    variable s1, s2 : integer := SEED;
    variable u, ts  : real;
    variable tmeta, tplat : time;
  begin
    en  := clk.p1 > 0.5;                       -- enable high -> transparent
    dhi := d.p1 >= d.p0;
    if en then
      -- transparent: q tracks d (and an invalid d propagates as PL_X)
      if px_of(d) > 0.5 then q <= PL_X after TCQ0;
      elsif dhi             then q <= PL_1 after TCQ0;
      else                       q <= PL_0 after TCQ0;
      end if;
    elsif prev_en and not en then
      -- latching (falling) edge: metastable if the data is moving or invalid
      meta := (d'last_event < TSETUP) or (px_of(d) > 0.5);
      if meta then
        uniform(s1, s2, u);
        ts := -TAU * log(u);
        tmeta := integer(ts * 1.0e15) * 1 fs;
        if tmeta > TMETA_MAX then tmeta := TMETA_MAX; end if;
        tplat := tmeta;
        if tplat < 1 fs then tplat := 1 fs; end if;
        report "statsim_latch: CDC metastability risk -- data unsettled at latch close (px=1 plateau "
             & time'image(tplat) & ")" severity warning;
        if dhi then q <= PL_X after TCQ0, PL_1 after TCQ0 + tplat;
        else        q <= PL_X after TCQ0, PL_0 after TCQ0 + tplat;
        end if;
      else
        if dhi then q <= PL_1 after TCQ0; else q <= PL_0 after TCQ0; end if;  -- clean hold
      end if;
    end if;
    prev_en := en;
  end process;
end architecture;
