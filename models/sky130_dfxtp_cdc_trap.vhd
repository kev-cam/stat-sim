-- sky130_dfxtp_cdc_trap -- CDC bug detector, nvc/prob_load runtime form (stat-sim generated)
-- At each RISING clock edge (the capture instant, matching the rising-edge DFF) flag
-- px_of(d) > PX_THR: the data node is not at a clean rail = captured-metastability /
-- CDC hazard. p_bad = n_bad/n_sample over Monte Carlo seeds = failure probability.
-- This IS the probability waveform read natively off the node (no voltage sampling).
library ieee;
library statsim;
use statsim.statsim_disc_pkg.all;

entity sky130_dfxtp_cdc_trap is
  generic ( PX_THR : real := 0.5 );                -- px above this at a clock edge = hazard
  port ( clk : in resolved_pl; d : in resolved_pl );
end entity;

architecture pwl of sky130_dfxtp_cdc_trap is
  signal n_sample : natural := 0;
  signal n_bad    : natural := 0;
begin
  process(clk)
    variable prev_hi : boolean := false;
    variable hi      : boolean;
  begin
    hi := clk.p1 > 0.5;
    if hi and not prev_hi then                      -- RISING edge only (matches the DFF capture)
      n_sample <= n_sample + 1;
      if px_of(d) > PX_THR then                     -- not a clean rail -> CDC hazard
        n_bad <= n_bad + 1;
        report "sky130_dfxtp_cdc_trap: CDC hazard, px=" & real'image(px_of(d))
          severity warning;
      end if;
    end if;
    prev_hi := hi;
  end process;
  -- p_bad = n_bad / n_sample, summarized by the MC driver across seeds.
end architecture;
