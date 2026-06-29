-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
-- statsim_rc_tb.vhd -- functional test of the RC-in-path element statsim_pl_rc.
-- A driver feeds net_a; pl_rc(C,R) straddles net_a (near) and net_b (far); a
-- receiver load sits on net_b. Checks: the receiver edge (net_b) lags the driver
-- edge (net_a) by the wire flight delay, and a metastable PL_X plateau propagates
-- through the wire (delayed, not swallowed -- TRANSPORT).
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_rc_tb is
end entity;

architecture tb of statsim_rc_tb is
  signal net_a, net_b : resolved_pl := PL_0;
  signal t_a_rise     : time := 0 ns;
  signal saw_b_meta   : boolean := false;
  signal checked_lag  : boolean := false;
begin
  rc : entity statsim.statsim_pl_rc
       generic map (C => 12.0e-15, R => 350.0, ALPHA => 0.5)
       port map (a => net_a, b => net_b);
  ld : entity statsim.statsim_pl_load generic map (CIN => 6.0e-15)
       port map (n => net_b);

  -- driver of net_a (the "cell output")
  drv : process begin
    net_a <= PL_0; wait for 2 ns;
    net_a <= PL_1; wait for 5 ns;          -- rising edge at t=2 ns
    net_a <= PL_X; wait for 1 ns;          -- inject a metastable plateau at t=7 ns
    net_a <= PL_0; wait for 4 ns;          -- end plateau at t=8 ns
    report "statsim_rc_tb done" severity note;
    std.env.finish;
  end process;

  mon_a : process(net_a) begin            -- record when net_a goes clean-1
    if net_a.p1 > 0.5 and net_a.px < 0.5 then t_a_rise <= now; end if;
  end process;

  mon_b : process(net_b)                  -- on net_b clean-1, check the flight lag
    variable lag : time;
  begin
    if net_b.px > 0.5 then saw_b_meta <= true; end if;
    if net_b.p1 > 0.5 and net_b.px < 0.5 and not checked_lag then
      lag := now - t_a_rise;              -- expect ln2*350*(0.5*12f+6f) = 2911 fs
      assert lag > 2900 fs and lag < 2920 fs
        report "FAIL flight delay: net_b lags net_a by " & time'image(lag)
             & " (expect ~2911 fs)" severity failure;
      report "OK flight delay: net_b rose " & time'image(lag) & " after net_a";
      checked_lag <= true;
    end if;
  end process;

  chk : process begin                     -- px must propagate through the wire
    wait for 10 ns;
    assert saw_b_meta
      report "FAIL: PL_X plateau did not propagate through pl_rc to net_b"
      severity failure;
    report "OK: PL_X plateau propagated through the wire (px pass-through)";
    wait;
  end process;
end architecture;
