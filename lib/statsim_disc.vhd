-- statsim_disc.vhd -- the stat-sim discipline (nature) for nvc multi-UDN nodes.
-- Mirrors disc.py field-for-field, number-for-number (self-tests enforce it).
--
-- prob_load is the probabilistic sibling of sv2vhdl.logic3da (a Thevenin
-- (voltage, resistance) record). It is a bond-graph 0-junction carrying a
-- conjugate pair:
--   FORWARD / effort (driver -> node): the probability simplex (p0,p1,px)
--       weighted by drive conductance gdrv = 1/R_drive (S). px = P(invalid) is
--       the CDC-trap metric. Common to all ports (like voltage).
--   BACKWARD / flow (node -> driver): capacitive load cload (F) + lumped series
--       wire R rwire (ohm) the fan-out + interconnect present back. Summed at the
--       junction (parallel caps add), like charge/current.
-- Conjugate product tau = (R_drive + rwire)*cload = the on-the-fly delay.
-- logic3da is the degenerate one-way bond (voltage fwd, resistance back, no
-- capacitive return); prob_load completes it with cload so delay is COMPUTED.
-- No algebraic loop: cload/rwire are topology-static, independent of p0/p1/px,
-- and only feed a non-zero scheduled DELAY.

library ieee;
use ieee.math_real.all;

package statsim_disc_pkg is

    type prob_load is record
        p0    : real;   -- FWD: P(clean 0)
        p1    : real;   -- FWD: P(clean 1)
        px    : real;   -- FWD: P(invalid/metastable)   (p0+p1+px = 1 for a driver)
        gdrv  : real;   -- FWD: drive conductance 1/R_drive (S); 0 => pure load (no vote)
        cload : real;   -- BWD: capacitance this port adds to the node (F); additive
        rwire : real;   -- BWD: lumped series wire R for this net (ohm)
    end record;

    type prob_load_vector is array (natural range <>) of prob_load;

    function resolve_pl (drivers : prob_load_vector) return prob_load;
    subtype resolved_pl is resolve_pl prob_load;       -- multi-driver resolved type

    -- physical constants (lock-step with disc.py)
    constant G_STRONG  : real := 1.0e-2;    -- = 1/R_STRONG (100 ohm): default gate drive
    constant G_EPS     : real := 1.0e-12;   -- = 1/R_OPEN: gdrv below this is non-driving
    constant R_STRONG  : real := 100.0;     -- strong-drive output resistance (ohm)
    constant LN2       : real := 0.6931471805599453;
    constant LN9       : real := 2.1972245773362196;
    constant TPD_FLOOR : real := 1.0e-15;   -- 1 fs: minimum scheduled delay

    constant PL_0     : prob_load := (1.0, 0.0, 0.0, G_STRONG, 0.0, 0.0);
    constant PL_1     : prob_load := (0.0, 1.0, 0.0, G_STRONG, 0.0, 0.0);
    constant PL_X     : prob_load := (0.0, 0.0, 1.0, G_STRONG, 0.0, 0.0);  -- driven metastable
    constant PL_FLOAT : prob_load := (0.0, 0.0, 1.0, 0.0,      0.0, 0.0);  -- undriven sentinel

    function PL_LOAD (cin  : real) return prob_load;    -- receiver pin tap (g=0)
    function PL_WIRE (c, r : real) return prob_load;    -- SPEF wire tap (C and R)

    -- on-the-fly delay / slew from a resolved node
    function delay_of (pl : prob_load; r_drive : real;
                       tpd0 : real := 0.0; k : real := LN2) return real;
    function slew_of  (pl : prob_load; r_drive : real; k : real := LN9) return real;
    function px_of    (pl : prob_load) return real;     -- the CDC-trap metric

    -- multi-UDN bridges
    function from_electrical (v, vlo, vhi : real;
                              gdrv : real := G_STRONG; cin : real := 0.0) return prob_load;
    function to_electrical   (pl : prob_load; vdd, vth : real) return real;
    function from_logic3da   (voltage : real; known : boolean; vlo, vhi : real;
                              gdrv : real := G_STRONG; cin : real := 0.0) return prob_load;

end package;

package body statsim_disc_pkg is

    function resolve_pl (drivers : prob_load_vector) return prob_load is
        variable C, Rw, G, Gw, p0, p1, px, cont, remn, s : real := 0.0;
    begin
        -- single source: MUST be the identity (return the driver verbatim, exactly
        -- like logic3da's l3da_resolve). nvc resolves a resolved RECORD signal
        -- sub-element-by-sub-element -- it calls this function per field and keeps
        -- only that field of the result -- and only re-resolves a field when that
        -- field's own driving value changes. If the length=1 result depended on a
        -- DIFFERENT field (e.g. forcing px=1 when gdrv<G_EPS), the record tears:
        -- during staggered initialization the px/p1 fields resolve while the
        -- driver's gdrv field is still 0, latching a float px that never updates
        -- (px doesn't change on a clean 0/1 toggle). Identity has no cross-field
        -- dependency, so every field stays self-consistent. The "a passive tap
        -- floats" semantic is encoded in the TAP itself (PL_LOAD/PL_WIRE carry
        -- px=1, gdrv=0) instead of in a cross-field branch here, so a lone load
        -- still floats (px=1) through this identity, and an undriven multi-tap net
        -- floats via the active-sum-empty branch below. (gdrv=0 keeps every passive
        -- tap out of the forward vote, so its px never pollutes a driven node.)
        if drivers'length = 1 then
            return drivers(drivers'low);
        end if;
        -- backward channel: extensive additive sums over ALL taps
        for i in drivers'range loop
            C  := C  + drivers(i).cload;
            Rw := Rw + drivers(i).rwire;
            G  := G  + drivers(i).gdrv;
        end loop;
        -- forward channel: gdrv-weighted mix over ACTIVE drivers only
        for i in drivers'range loop
            if drivers(i).gdrv >= G_EPS then
                Gw := Gw + drivers(i).gdrv;
                p0 := p0 + drivers(i).gdrv * drivers(i).p0;
                p1 := p1 + drivers(i).gdrv * drivers(i).p1;
                px := px + drivers(i).gdrv * drivers(i).px;
            end if;
        end loop;
        if Gw = 0.0 then
            return (0.0, 0.0, 1.0, 0.0, C, Rw);   -- floating (PL_FLOAT) + loads
        end if;
        p0 := p0 / Gw; p1 := p1 / Gw; px := px / Gw;
        cont := 2.0 * p0 * p1;                    -- contention -> mid-rail
        px := px + cont;
        if px > 1.0 then px := 1.0; end if;
        remn := 1.0 - px;
        s := p0 + p1;
        if s > 0.0 then
            p0 := p0 / s * remn;
            p1 := p1 / s * remn;
        end if;
        return (p0, p1, px, G, C, Rw);
    end function;

    function PL_LOAD (cin : real) return prob_load is
    begin
        return (0.0, 0.0, 1.0, 0.0, cin, 0.0);   -- passive: floats (px=1), gdrv=0 -> no vote
    end function;

    function PL_WIRE (c, r : real) return prob_load is
    begin
        return (0.0, 0.0, 1.0, 0.0, c, r);       -- passive: floats (px=1), gdrv=0 -> no vote
    end function;

    function delay_of (pl : prob_load; r_drive : real;
                       tpd0 : real := 0.0; k : real := LN2) return real is
    begin
        return tpd0 + k * (r_drive + pl.rwire) * pl.cload;
    end function;

    function slew_of (pl : prob_load; r_drive : real; k : real := LN9) return real is
    begin
        return k * (r_drive + pl.rwire) * pl.cload;
    end function;

    function px_of (pl : prob_load) return real is
    begin
        return pl.px;
    end function;

    function from_electrical (v, vlo, vhi : real;
                              gdrv : real := G_STRONG; cin : real := 0.0) return prob_load is
        variable mid, depth, lean, remn : real;
    begin
        if v >= vhi then return (0.0, 1.0, 0.0, gdrv, cin, 0.0); end if;
        if v <= vlo then return (1.0, 0.0, 0.0, gdrv, cin, 0.0); end if;
        mid   := 0.5 * (vlo + vhi);
        depth := 1.0 - 2.0 * abs(v - mid) / (vhi - vlo);   -- 1 at mid, 0 at edges
        lean  := (v - vlo) / (vhi - vlo);
        remn  := 1.0 - depth;
        return ((1.0 - lean) * remn, lean * remn, depth, gdrv, cin, 0.0);
    end function;

    function to_electrical (pl : prob_load; vdd, vth : real) return real is
    begin
        return pl.p1 * vdd + pl.px * vth;
    end function;

    function from_logic3da (voltage : real; known : boolean; vlo, vhi : real;
                            gdrv : real := G_STRONG; cin : real := 0.0) return prob_load is
    begin
        if not known then return (0.0, 0.0, 1.0, gdrv, cin, 0.0); end if;
        return from_electrical(voltage, vlo, vhi, gdrv, cin);
    end function;

end package body;
