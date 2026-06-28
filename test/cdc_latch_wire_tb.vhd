-- cdc_latch_wire_tb.vhd -- the CDC latch demo with an RC-in-path wire on the data
-- path (statsim_pl_rc between the data inverter and the latch). Proves the tool
-- still flags the async crossing once routing R-C is pulled into the driver->
-- receiver path; the wire flight delay shifts where the data edges land. Clone of
-- cdc_latch_tb.vhd (left intact) with the pl_rc inserted on dat.
library ieee;
use ieee.std_logic_1164.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity cdc_latch_wire_tb is
end entity;

architecture tb of cdc_latch_wire_tb is
  signal clk_v : std_ulogic := '0';
  signal dat_v : std_ulogic := '0';
  signal clk_p, dat_a, dat_b, q_p : resolved_pl;   -- dat_a=near (inv out), dat_b=far (latch in)
  signal n_meta : natural := 0;
begin
  clk_v <= not clk_v after 1.00 ns;                -- latch clock : 2.00 ns
  dat_v <= not dat_v after 1.10 ns;                -- data clock  : 2.20 ns (async)

  ci : entity statsim.statsim_inv port map (i => clk_v, o => clk_p);
  di : entity statsim.statsim_inv port map (i => dat_v, o => dat_a);

  -- RC-in-path wire on the DATA route: dat_a (driver) -> pl_rc -> dat_b (latch.d)
  wrc : entity statsim.statsim_pl_rc generic map (C => 20.0e-15, R => 800.0)
        port map (a => dat_a, b => dat_b);
  dl  : entity statsim.statsim_pl_load generic map (CIN => 2.0e-15)
        port map (n => dat_b);                     -- latch input cap on the far node

  lat : entity statsim.statsim_latch generic map (TSETUP => 150 ps)
        port map (d => dat_b, clk => clk_p, q => q_p);
  wq  : entity statsim.statsim_pl_wire generic map (C => 4.0e-15, R => 50.0)
        port map (n => q_p);

  mon : process(q_p) begin
    if q_p.px > 0.5 then n_meta <= n_meta + 1; end if;
  end process;

  process begin
    wait for 200 ns;
    report "cdc_latch_wire_tb DONE: latch flagged " & integer'image(n_meta)
         & " metastable events with an RC wire (20fF/800ohm, ~6.7ps flight) on the data path"
         severity note;
    assert n_meta > 0
      report "FAIL: no CDC hazard flagged with the wire in the path" severity failure;
    std.env.finish;
  end process;
end architecture;
