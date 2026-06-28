-- cdc_latch_tb.vhd -- CDC detection demo (runnable under nvc).
-- A regular 4-state (01XZ) testbench: a latch clock and a DATA line that is itself
-- a clock at a slightly different frequency. The two stat-sim INVERTERS lift the
-- 01XZ logic into the probability domain; the stat-sim LATCH flags the CDC
-- metastability risk whenever the data is transitioning as the latch closes.
-- (cdc_latch_tb.v is the same testbench in Verilog; the runnable driver here is the
--  std_ulogic form -- std_ulogic IS the 01XZ logic a Verilog reg presents.)
library ieee;
use ieee.std_logic_1164.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity cdc_latch_tb is
end entity;

architecture tb of cdc_latch_tb is
  signal clk_v : std_ulogic := '0';            -- latch clock (01XZ)
  signal dat_v : std_ulogic := '0';            -- data = a clock at a different freq (01XZ)
  signal clk_p, dat_p, q_p : resolved_pl;      -- probability-domain nets
  signal q_px   : real := 0.0;                 -- scalar mirror of q_p.px for the waveform
  signal n_meta : natural := 0;
begin
  q_px <= q_p.px;                              -- 1.0 during a metastable plateau (the hazard)
  -- regular digital stimulus: two slightly-different clocks
  clk_v <= not clk_v after 1.00 ns;            -- latch clock : 2.00 ns period (500 MHz)
  dat_v <= not dat_v after 1.10 ns;            -- data clock  : 2.20 ns period (~455 MHz)

  -- stat-sim inverters: 01XZ logic -> probability logic
  ci : entity statsim.statsim_inv port map (i => clk_v, o => clk_p);
  di : entity statsim.statsim_inv port map (i => dat_v, o => dat_p);

  -- the stat-sim latch flags the CDC metastability risk (TSETUP widened for a lively demo)
  lat : entity statsim.statsim_latch
        generic map (TSETUP => 150 ps)
        port map (d => dat_p, clk => clk_p, q => q_p);
  wq  : entity statsim.statsim_pl_wire generic map (C => 4.0e-15, R => 50.0) port map (n => q_p);

  -- count each time the latch output goes metastable (a flagged CDC hazard)
  mon : process(q_p) begin
    if q_p.px > 0.5 then n_meta <= n_meta + 1; end if;
  end process;

  -- run window
  process begin
    wait for 200 ns;
    report "cdc_latch_tb DONE: latch output went metastable " & integer'image(n_meta)
         & " times over 200 ns -- the stat-sim latch flagged the async data crossing."
         severity note;
    std.env.finish;
  end process;
end architecture;
