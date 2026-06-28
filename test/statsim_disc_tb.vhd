-- statsim_disc_tb.vhd -- lock-step check: resolve_pl/delay_of must produce the
-- SAME numbers as disc.py's _self_test (run under nvc). Keep in sync with disc.py.
library ieee;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity statsim_disc_tb is
end entity;

architecture tb of statsim_disc_tb is
    function approx(a, b, tol : real) return boolean is
    begin
        return abs(a - b) <= tol;
    end function;
begin
    process
        variable r, node, node20, fl : prob_load;
        variable d18, d20 : real;
    begin
        -- hard contention 0 vs 1 -> px up, conductances add
        r := resolve_pl((PL_0, PL_1));
        assert approx(r.px, 0.5, 1.0e-9)  report "FAIL contention px"  severity failure;
        assert approx(r.p0, 0.25, 1.0e-9) and approx(r.p1, 0.25, 1.0e-9)
            report "FAIL contention p0/p1" severity failure;
        assert approx(r.gdrv, 0.02, 1.0e-9) report "FAIL gdrv parallel-add" severity failure;

        -- backward additivity + loads-don't-vote (PL_1 + 3 receivers@2fF + wire 12fF/350)
        node := resolve_pl((PL_1, PL_LOAD(2.0e-15), PL_LOAD(2.0e-15),
                            PL_LOAD(2.0e-15), PL_WIRE(12.0e-15, 350.0)));
        assert approx(node.cload, 18.0e-15, 1.0e-18) report "FAIL cload sum"  severity failure;
        assert approx(node.rwire, 350.0, 1.0e-9)     report "FAIL rwire sum"  severity failure;
        assert node.p1 = 1.0 and node.px = 0.0       report "FAIL loads voted" severity failure;
        assert approx(node.gdrv, G_STRONG, 1.0e-12)  report "FAIL gdrv (only PL_1 drives)" severity failure;

        -- on-the-fly delay: numeric + monotone in fan-out
        d18 := delay_of(node, R_STRONG);
        assert approx(d18, LN2 * 450.0 * 18.0e-15, 1.0e-18) report "FAIL delay numeric" severity failure;
        node20 := resolve_pl((PL_1, PL_LOAD(2.0e-15), PL_LOAD(2.0e-15), PL_LOAD(2.0e-15),
                              PL_LOAD(2.0e-15), PL_WIRE(12.0e-15, 350.0)));
        d20 := delay_of(node20, R_STRONG);
        assert d20 > d18 report "FAIL delay not monotone in fan-out" severity failure;

        -- undriven / loads-only -> floating (px=1) but load still summed
        fl := resolve_pl((0 => PL_LOAD(5.0e-15)));
        assert fl.px = 1.0 and fl.gdrv = 0.0 and approx(fl.cload, 5.0e-15, 1.0e-18)
            report "FAIL float (loads only)" severity failure;

        report "statsim_disc_tb ALL OK: px=0.5 gdrv=0.02 cload=18fF d18="
            & real'image(d18) & "s d20=" & real'image(d20) & "s";
        wait;
    end process;
end architecture;
