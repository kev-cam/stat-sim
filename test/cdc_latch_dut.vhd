-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
-- cdc_latch_dut.vhd -- the probability-domain DUT for the Verilog CDC testbench.
-- Boundary ports are logic3d (the 01XZ type a Verilog signal presents once nvc
-- translates the testbench via sv2ghdl). Inside, they convert to std_ulogic, the
-- two stat-sim inverters lift to the probability domain, and the stat-sim latch
-- flags the CDC metastability risk.
library ieee;
use ieee.std_logic_1164.all;
library sv2vhdl;
use sv2vhdl.logic3d_types_pkg.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity cdc_latch_dut is
  port ( clk_v : in logic3d;             -- latch clock (from Verilog, 01XZ)
         dat_v : in logic3d );           -- data = async clock (from Verilog, 01XZ)
end entity;

architecture rtl of cdc_latch_dut is
  signal clk_s, dat_s : std_ulogic;
  signal clk_p, dat_p, q_p : resolved_pl;
begin
  clk_s <= to_std_logic(clk_v);          -- logic3d -> 01XZ std_ulogic
  dat_s <= to_std_logic(dat_v);
  ci  : entity statsim.statsim_inv port map (i => clk_s, o => clk_p);
  di  : entity statsim.statsim_inv port map (i => dat_s, o => dat_p);
  lat : entity statsim.statsim_latch generic map (TSETUP => 150 ps)
        port map (d => dat_p, clk => clk_p, q => q_p);
  wq  : entity statsim.statsim_pl_wire generic map (C => 4.0e-15, R => 50.0)
        port map (n => q_p);
end architecture;
