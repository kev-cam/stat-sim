# qal/burst amendments (each recorded when the measurement forced it)

## A1 — free-running multi-wave collapses; the sustained burst runs in TOP-UP mode (2026-09-30, after cy_tpre2000)

MEASUREMENT THAT FORCED IT: cy_tpre2000 (free-running, the pre-registered II=800
schedule): wave 0 after the 2 ns park computes 32/32 (the post-park correctness
datum STANDS), but waves 1+ fail 67/128 (bank-1 HIGH 0.334 on a 0.772 V rail;
worst commanded-open residual |I(L)| 146 uA vs the committed single-wave <=1.8 uA).
Mechanism: the free-running tanks are pre-charged once by .ic and never refilled
(the committed banktank rows are single-wave by construction); each wave rises
from a lower tank, the delivered rail falls, and the reused ZCS zeros stop
transferring. This is not a new physics failure -- it is the committed §8 finding
("the measured tank droop IS the recharge requirement") composed over waves.

AMENDED: the cycle decks that carry the energy headline run in the committed
COSTED mode (per-wave tank top-up through a real tg15p-class TG from an ideal
rail at V_t0=0.9075 -- rail generation NOT costed, labelled BOUND, drawn energy
METERED by its own integrator, exactly the committed §8 convention), and the
initiation interval moves 800 -> 1000 ps to give the top-up a ~240 ps window
(the committed 60 ps window measurably under-restores: 0.660->0.639 V at dv1.2).
The free-running rows are kept and reported (they carry the park linearity and
the first-post-park-wave correctness); the pre-registered II=800 free-running
expectation E1 is therefore PARTIALLY REFUTED: the metered-only burst energy
must include the top-up rail draw, not just tank dE.

## A2 — committed comb-leakage band does not reproduce on this fixture (2026-09-30, cmos_idle)

The committed per-cell leakage band used by the Vortex composition
(117-131.5 pW/cell) reads 13.36 pW/cell here (32-inverter chain, held inputs,
1.2 V, junction-zeroed shim). The committed band came from a different cell mix
(o21ai-heavy ALU census) and includes the phys-cell inflation; the inverter is
the least leaky cell and the shim zeroes junctions. BOTH numbers are carried:
the measured-here 427 pW/32-cell figure is the fixture-matched lower bound; the
committed band is quoted as the mixed-logic upper reference. The CMOS idle story
does not depend on the choice (power-gated CMOS is the binding opponent).
