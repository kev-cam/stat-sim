-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
-- sky130_dfxtp -- metastable D flip-flop, nvc/prob_load runtime form (stat-sim generated)
-- Authored in Verilog-AMS (sky130_dfxtp.vams). Event-driven; load-dependent delay.
-- Corner: tt.  Output holds PL_X (mid-rail/invalid) for an Exp(tau) window
-- after a setup/hold violation, then resolves -- all scheduled, no analog solve.
library ieee;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity sky130_dfxtp is
  generic ( TAU       : real := 1.57e-11;          -- s, regeneration time constant
            TSETUP    : time := 90 ps;       -- setup aperture (backward 'last_event)
            THOLD     : time := 35 ps;        -- hold; NOTE: hold-after-edge is not
                                                   -- detectable with backward 'last_event (known gap)
            T0        : real := 1.57e-11;            -- s, metastability aperture -> feeds the
                                                   -- analytic MTBF (genmodel.mtbf), not per-trial entry
            TCQ0      : time := 110 ps;          -- intrinsic UNLOADED clock->q
            R_DRIVE   : real := 100.0;       -- output drive resistance (ohm)
            TMETA_MAX : time := 5000 ps;
            SEED      : integer := 1;
            DEFECT    : integer := -1 );           -- '213 seam: good=-1; 0/1 = stuck-at variant
  port ( d   : in    resolved_pl;
         clk : in    resolved_pl;
         q   : inout resolved_pl := PL_FLOAT );    -- inout: read RESOLVED net load back
end entity;

architecture pwl of sky130_dfxtp is
begin
  process(clk)
    variable prev_hi : boolean := false;
    variable hi, dhi, meta : boolean;
    variable s1, s2  : integer := SEED;
    variable u, ts, tpd, tsl : real;
    variable tcq_eff, tmeta, tslew, tplat : time;
  begin
    hi := clk.p1 > 0.5;                            -- rising clock edge (prob terms)
    if hi and not prev_hi then
      dhi := d.p1 >= d.p0;                          -- sampled data value
      -- on-the-fly load-dependent delay from the RESOLVED output net (q is inout)
      tpd := LN2 * (R_DRIVE + q.rwire) * q.cload;
      tsl := LN9 * (R_DRIVE + q.rwire) * q.cload;
      tcq_eff := TCQ0 + integer(maximum(tpd, TPD_FLOOR) * 1.0e15) * 1 fs;
      tslew   := integer(maximum(tsl, 0.0) * 1.0e15) * 1 fs;
      -- metastable if the data EDGE landed in the setup aperture, OR the sampled
      -- data LEVEL is itself invalid (an already-metastable input propagates).
      meta := (d'last_event < TSETUP) or (px_of(d) > 0.5);
      if DEFECT = 0 then                            -- '213 minimal defect: stuck-at-0
        q <= PL_0 after tcq_eff;
      elsif DEFECT = 1 then                         -- stuck-at-1
        q <= PL_1 after tcq_eff;
      elsif meta then
        uniform(s1, s2, u);
        ts := -TAU * log(u);                        -- Exp(tau) metastable duration, s
        tmeta := integer(ts * 1.0e15) * 1 fs;
        if tmeta > TMETA_MAX then tmeta := TMETA_MAX; end if;
        tplat := tmeta + tslew;
        if tplat < 1 fs then tplat := 1 fs; end if; -- never drop the PL_X plateau (unloaded net)
        if dhi then
          q <= PL_X after tcq_eff, PL_1 after tcq_eff + tplat;
        else
          q <= PL_X after tcq_eff, PL_0 after tcq_eff + tplat;
        end if;
      else                                          -- clean capture
        if dhi then q <= PL_1 after tcq_eff; else q <= PL_0 after tcq_eff; end if;
      end if;
    end if;
    prev_hi := hi;
  end process;
end architecture;
