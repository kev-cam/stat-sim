-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
-- statsim_cdc_tb.vhd -- end-to-end runtime check of the prob_load CDC flow:
--   * metastable DFF drives q; a SPEF wire tap + 3 fan-out load taps share q
--     (so q.cload = 12fF + 3*2fF = 18fF resolves on the multi-UDN node);
--   * a setup violation makes q go PL_X (mid-rail) -> the monitor sees it;
--   * the CDC trap flags px>0.5 at a clock edge on an invalid data node.
library ieee;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_cdc_tb is
end entity;

architecture tb of statsim_cdc_tb is
    signal clk   : resolved_pl := PL_0;
    signal d     : resolved_pl := PL_0;
    signal q     : resolved_pl := PL_FLOAT;     -- DFF output net (DFF + taps drive it)
    signal tclk  : resolved_pl := PL_0;
    signal probe : resolved_pl := PL_1;
    signal saw_meta  : boolean := false;
    signal q_cload_seen : real := 0.0;
begin
    -- DUT: metastable DFF + its loaded output net
    dut : entity statsim.sky130_dfxtp
        port map (d => d, clk => clk, q => q);
    wseg : entity statsim.statsim_pl_wire generic map (C => 12.0e-15, R => 350.0)
        port map (n => q);
    fo1 : entity statsim.statsim_pl_load generic map (CIN => 2.0e-15) port map (n => q);
    fo2 : entity statsim.statsim_pl_load generic map (CIN => 2.0e-15) port map (n => q);
    fo3 : entity statsim.statsim_pl_load generic map (CIN => 2.0e-15) port map (n => q);

    -- trap on a deterministic probe node (proves px-detection)
    trap : entity statsim.sky130_dfxtp_cdc_trap
        port map (clk => tclk, d => probe);

    -- monitor: did q ever plateau metastable?
    mon : process(q) begin
        if q.px > 0.5 then saw_meta <= true; end if;
        q_cload_seen <= q.cload;
    end process;

    -- DFF stimulus: one clean capture, then one setup-violating capture
    stim : process begin
        clk <= PL_0; d <= PL_1;                          -- define drivers at t=0 (clk low, d=1 stable)
        wait for 1 ns;                                   -- settle; q resolves from taps
        assert abs(q_cload_seen - 18.0e-15) < 1.0e-18
            report "FAIL: resolved q.cload /= 18fF (got " & real'image(q_cload_seen) & ")"
            severity failure;
        -- CLEAN capture: d has been stable since t=0, now a rising clock at t=3
        wait for 2 ns;
        clk <= PL_1; wait for 1 ns;                      -- rising edge, d stable -> clean q=1
        report "clean-capture probe: clk.p1=" & real'image(clk.p1)
             & " d.p1=" & real'image(d.p1) & " d'last_event=" & time'image(d'last_event)
             & " | q.p1=" & real'image(q.p1)
             & " q.px=" & real'image(q.px) & " q.cload=" & real'image(q.cload);
        assert q.p1 > 0.5 and q.px < 0.5 report "FAIL: clean capture not logic-1" severity failure;
        clk <= PL_0; wait for 2 ns;
        -- VIOLATING capture: d toggles at the same instant as the clock edge
        d <= PL_0; wait for 2 ns;
        d <= PL_1; clk <= PL_1; wait for 3 ns;           -- d'last_event = 0 < TSETUP -> metastable
        assert saw_meta
            report "FAIL: DFF did not inject metastability on a setup violation" severity failure;
        report "DFF OK: q.cload=18fF resolved; clean capture clean; setup violation -> PL_X seen";
        wait;
    end process;

    -- trap stimulus: clean sample (no hazard), then invalid-data sample (hazard)
    trapstim : process begin
        tclk <= PL_0; probe <= PL_1;                     -- define drivers at t=0
        wait for 1 ns;
        tclk <= PL_1; wait for 1 ns;                     -- sample while probe=PL_1 -> no hazard
        tclk <= PL_0; wait for 1 ns;
        probe <= PL_X;                                   -- data goes invalid (mid-rail)
        wait for 1 ns;
        tclk <= PL_1; wait for 1 ns;                     -- sample while probe=PL_X -> HAZARD report
        wait;
    end process;
end architecture;
