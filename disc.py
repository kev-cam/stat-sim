#!/usr/bin/env python3
"""
stat-sim discipline -- Python reference model + validator for the `prob_load`
nature: a BIDIRECTIONAL CONJUGATE pair on a multi-UDN node in nvc.

`prob_load` is the probabilistic sibling of `sv2vhdl.logic3da` (a Thevenin
(voltage, resistance) record). It is a bond-graph 0-junction carrying:

  FORWARD / effort (driver -> node):  the logic-probability simplex (p0,p1,px)
      weighted by the driver's drive conductance gdrv = 1/R_drive (Siemens).
      px = P(invalid/metastable level) -- the CDC-trap metric. Common to all ports.
  BACKWARD / flow (node -> driver):   the capacitive load cload (F) and lumped
      series wire resistance rwire (ohm) the fan-out + interconnect present back.
      Summed at the junction (parallel caps add), like charge/current.

The conjugate product is the RC time constant tau = (R_drive + rwire)*cload =
the on-the-fly propagation delay. logic3da is the degenerate one-way bond
(voltage forward, resistance back, NO capacitive return); prob_load completes it
with the cload channel so delay is COMPUTED, not a static generic. Adding/removing
a fan-out tap changes the resolver vector -> changes cload -> changes delay,
automatically ("outgoing = probability, return = loading factor; handles variable
fan-out").

No algebraic loop: cload/rwire are pure topology constants (independent of
p0/p1/px); the only forward->backward coupling is "read the resolved load to size
a non-zero DELAY" (a time, not a value), which breaks every delta/comb loop.

This file is the executable spec; lib/statsim_disc.vhd is the runtime form and is
kept field-for-field, number-for-number in lock-step (the self-tests enforce it).
"""
import sys
from dataclasses import dataclass

# --- physical constants (lock-step with statsim_disc.vhd) -------------------
G_STRONG  = 1.0e-2     # = 1/R_STRONG (100 ohm): default gate drive conductance (S)
G_EPS     = 1.0e-12    # = 1/R_OPEN  (1e12 ohm): gdrv below this is non-driving
R_STRONG  = 100.0      # strong-drive output resistance (ohm)
LN2       = 0.6931471805599453
LN9       = 2.1972245773362196
TPD_FLOOR = 1.0e-15    # 1 fs: minimum scheduled delay (never schedule 0)


@dataclass(frozen=True)
class PL:
    p0: float                  # FWD: P(clean 0)
    p1: float                  # FWD: P(clean 1)
    px: float                  # FWD: P(invalid/metastable); p0+p1+px = 1 for a driver
    gdrv:  float = G_STRONG     # FWD: drive conductance 1/R_drive (S); 0 => pure load (no vote)
    cload: float = 0.0          # BWD: capacitance this port adds to the node (F); additive
    rwire: float = 0.0          # BWD: lumped series wire R for this net (ohm)

    def clean(self) -> bool:
        return self.px < 1e-9


PL_0     = PL(1.0, 0.0, 0.0, G_STRONG, 0.0, 0.0)
PL_1     = PL(0.0, 1.0, 0.0, G_STRONG, 0.0, 0.0)
PL_X     = PL(0.0, 0.0, 1.0, G_STRONG, 0.0, 0.0)   # ACTIVELY-driven metastable (plateauing flop)
PL_FLOAT = PL(0.0, 0.0, 1.0, 0.0,      0.0, 0.0)   # UNDRIVEN sentinel / resolve([]) result


def PL_LOAD(cin: float) -> PL:
    """A fan-out receiver pin tap: votes nothing (gdrv=0), only loads the node.
    Carries px=1 (floating): a lone load IS an undriven node, and gdrv=0 keeps it
    out of the forward vote so this px never pollutes a driven multi-tap node.
    Encoding 'floating' in the tap lets resolve()'s single-source path stay a pure
    identity (required for nvc's per-sub-element resolved-record resolution)."""
    return PL(0.0, 0.0, 1.0, 0.0, cin, 0.0)


def PL_WIRE(c: float, r: float) -> PL:
    """One SPEF wire tap per net: carries the wire C (load) and wire R (series).
    px=1/gdrv=0 like PL_LOAD: passive, floats alone, never votes (see PL_LOAD)."""
    return PL(0.0, 0.0, 1.0, 0.0, c, r)


def resolve(drivers) -> PL:
    """ONE pass: backward additive sums over ALL taps + forward gdrv-weighted mix
    over ACTIVE drivers (gdrv >= G_EPS). Loads/wires/tristate (gdrv<G_EPS) load the
    node but never move the probability vote. Mirrors logic3da's parallel Thevenin
    (conductances add -> R_out = 1/G), lifted to the probability simplex."""
    drivers = [d for d in drivers if d is not None]
    if len(drivers) == 1:                      # single source: MUST be the identity
        return drivers[0]                       # (return the driver verbatim, exactly
        # like logic3da). nvc resolves a resolved RECORD signal sub-element-by-sub-
        # element and only re-resolves a field when that field's own driving value
        # changes, so a length=1 result that depends on a DIFFERENT field (e.g.
        # forcing px=1 when gdrv<G_EPS) tears the record during staggered init and
        # never recovers. A truly undriven net (load taps only) still floats via the
        # multi-driver path below (empty active set -> px=1); real nets have >=2 taps.

    # backward channel: extensive additive sums over ALL taps
    C  = sum(d.cload for d in drivers)         # parallel caps add -> node load (F)
    Rw = sum(d.rwire for d in drivers)         # 1 wire tap/net exact; >1 = lumped series approx
    G  = sum(d.gdrv  for d in drivers)         # parallel drivers -> conductances add

    # forward channel: gdrv-weighted mix over ACTIVE drivers only
    active = [d for d in drivers if d.gdrv >= G_EPS]
    if not active:
        # undriven (or loads only): floating node, px=1, but loads STILL reported
        return PL(0.0, 0.0, 1.0, 0.0, C, Rw)
    Gw = sum(d.gdrv for d in active)
    p0 = sum(d.gdrv * d.p0 for d in active) / Gw
    p1 = sum(d.gdrv * d.p1 for d in active) / Gw
    px = sum(d.gdrv * d.px for d in active) / Gw
    cont = 2.0 * p0 * p1                       # contention: split 0-vs-1 -> mid-rail
    px = min(1.0, px + cont)
    rem = 1.0 - px
    s = p0 + p1
    if s > 0.0:
        p0, p1 = p0 / s * rem, p1 / s * rem
    return PL(p0, p1, px, G, C, Rw)


# --- on-the-fly delay (replaces the SPEF constant) --------------------------
def delay_of(node: PL, r_drive: float, tpd0: float = 0.0, k: float = LN2) -> float:
    """50% propagation delay from the resolved node load. tau=(R_drive+rwire)*cload;
    t_pd = tpd0 + k*tau. Caller floors at TPD_FLOOR when scheduling."""
    return tpd0 + k * (r_drive + node.rwire) * node.cload


def slew_of(node: PL, r_drive: float, k: float = LN9) -> float:
    """10-90% output edge from the resolved node load."""
    return k * (r_drive + node.rwire) * node.cload


# --- RC-in-path wire helpers (the statsim_pl_rc 2-port element) --------------
def g_series(gdrv: float, r: float) -> float:
    """Driver conductance after a series wire R (R_drive and R in series):
    gdrv/(1+gdrv*r). 0 below G_EPS so an undriven near end stays undriven at the
    far end."""
    return 0.0 if gdrv < G_EPS else gdrv / (1.0 + gdrv * r)


def wire_flight_delay(c: float, r: float, cin_far: float,
                      alpha: float = 0.5, k: float = LN2) -> float:
    """Wire flight delay (driver end -> receiver end) for a routing R-C with far
    load cin_far: k*R*(alpha*C + cin_far). alpha=0.5 = pi/Elmore self-cap (default,
    more accurate); alpha=1.0 reproduces the legacy lumped receiver arrival."""
    return k * r * (alpha * c + cin_far)


# --- multi-UDN bridges: convert other natures to/from prob_load -------------
def from_electrical(v: float, vlo: float, vhi: float,
                    gdrv: float = G_STRONG, cin: float = 0.0) -> PL:
    """electrical V/I node -> prob_load. Outside (vlo,vhi) it's a clean rail;
    inside, px rises toward 1 at mid-band and p1/p0 carry the lean."""
    if v >= vhi:
        return PL(0.0, 1.0, 0.0, gdrv, cin, 0.0)
    if v <= vlo:
        return PL(1.0, 0.0, 0.0, gdrv, cin, 0.0)
    mid = 0.5 * (vlo + vhi)
    depth = 1.0 - 2.0 * abs(v - mid) / (vhi - vlo)   # 1 at mid, 0 at edges
    lean = (v - vlo) / (vhi - vlo)                   # 0 at vlo, 1 at vhi
    rem = 1.0 - depth
    return PL((1.0 - lean) * rem, lean * rem, depth, gdrv, cin, 0.0)


def to_electrical(pl: PL, vdd: float, vth: float) -> float:
    """prob_load -> expected node voltage (px contributes the mid-rail level)."""
    return pl.p1 * vdd + pl.px * vth


def from_logic3da(voltage: float, known: bool, vlo: float, vhi: float,
                  gdrv: float = G_STRONG, cin: float = 0.0) -> PL:
    """logic3da (3D-logic) -> prob_load. Unknown/Z maps to px; known uses V.
    Caller passes gdrv=1/resistance (clamp to 0 if resistance>=R_OPEN)."""
    if not known:
        return PL(0.0, 0.0, 1.0, gdrv, cin, 0.0)
    return from_electrical(voltage, vlo, vhi, gdrv, cin)


def px_of(pl: PL) -> float:
    """The CDC-trap metric: P(node at an invalid/metastable level)."""
    return pl.px


def _self_test() -> int:
    eps = 1e-9
    # clean rails pass through resolution unchanged
    assert resolve([PL_0]).clean() and resolve([PL_0]).p0 == 1.0
    assert resolve([PL_1]).p1 == 1.0
    # hard contention 0 vs 1 -> node goes invalid (px up); conductances add
    r = resolve([PL_0, PL_1])
    assert abs(r.px - 0.5) < eps, f"contention px={r.px}"
    assert abs(r.p0 - 0.25) < eps and abs(r.p1 - 0.25) < eps
    assert abs(r.gdrv - 0.02) < eps, f"parallel gdrv={r.gdrv}"      # 0.01+0.01
    # backward additivity + loads-don't-vote: PL_1 + 3 receivers@2fF + wire(12fF,350)
    node = resolve([PL_1, PL_LOAD(2e-15), PL_LOAD(2e-15), PL_LOAD(2e-15),
                    PL_WIRE(12e-15, 350.0)])
    assert abs(node.cload - 18e-15) < 1e-18, f"cload={node.cload}"   # 6fF fanout + 12fF wire
    assert abs(node.rwire - 350.0) < eps, f"rwire={node.rwire}"
    assert node.p1 == 1.0 and node.px == 0.0                        # loads never moved the vote
    assert abs(node.gdrv - G_STRONG) < eps                          # only PL_1 drives
    # forward/backward decoupling: same logic value regardless of load
    assert resolve([PL_1]).p1 == resolve([PL_1, PL_LOAD(99e-15)]).p1
    # on-the-fly delay: numeric + monotone in fan-out
    d18 = delay_of(node, R_STRONG)                                  # ln2*(100+350)*18e-15
    assert abs(d18 - LN2 * 450.0 * 18e-15) < 1e-18
    assert abs(d18 - 5.61449e-12) < 1e-17, f"t_pd={d18:.6e}"        # 5.6145 ps
    node20 = resolve([PL_1, PL_LOAD(2e-15), PL_LOAD(2e-15), PL_LOAD(2e-15),
                      PL_LOAD(2e-15), PL_WIRE(12e-15, 350.0)])      # +1 fan-out -> 20fF
    assert delay_of(node20, R_STRONG) > d18                        # monotone: more fan-out -> >= delay
    # electrical bridge: mid-band fully invalid, rails clean, distribution sums to 1
    mid = from_electrical(0.9, 0.18, 1.62)
    assert abs(mid.px - 1.0) < eps
    hi = from_electrical(1.4, 0.18, 1.62)
    assert hi.p1 > hi.p0 and 0.0 < hi.px < 1.0
    assert abs(hi.p0 + hi.p1 + hi.px - 1.0) < eps
    assert abs(to_electrical(PL_1, 1.8, 0.9) - 1.8) < eps
    # undriven / loads-only -> PL_FLOAT (px=1) but load still summed
    assert resolve([]).px == 1.0 and resolve([]).gdrv == 0.0
    lo = resolve([PL_LOAD(5e-15), PL_WIRE(3e-15, 100.0)])
    assert lo.px == 1.0 and abs(lo.cload - 8e-15) < 1e-18 and lo.gdrv == 0.0
    # tristate / disabled driver: MODELING RULE -- encode it in the passive-tap shape
    # (gdrv=0, px=1), NOT as (p1=1, gdrv<G_EPS). Then it floats consistently whether it
    # is the sole driver (length=1 identity -> px=1) or one of many (excluded from vote).
    tri = PL(0.0, 0.0, 1.0, 0.0, 4e-15, 0.0)                       # disabled driver (floats)
    t = resolve([PL_0, tri])
    assert t.p0 == 1.0 and abs(t.cload - 4e-15) < 1e-18            # PL_0 wins; tri only loads
    assert resolve([tri]).px == 1.0                                # lone disabled driver -> floats (no false clean rail)
    # RC-in-path helpers (statsim_pl_rc): flight delay + series conductance
    assert abs(wire_flight_delay(12e-15, 350.0, 6e-15, 0.5) - LN2 * 350.0 * 12e-15) < 1e-18
    near = LN2 * R_STRONG * (12e-15 + 6e-15)                       # driver-end (rwire=0)
    flight1 = wire_flight_delay(12e-15, 350.0, 6e-15, 1.0)         # legacy anchor (alpha=1)
    assert abs(near + flight1 - LN2 * (R_STRONG + 350.0) * 18e-15) < 1e-18   # == old lumped d18
    assert abs(g_series(G_STRONG, 350.0) - G_STRONG / (1.0 + G_STRONG * 350.0)) < 1e-15
    assert g_series(1e-13, 350.0) == 0.0                           # sub-G_EPS -> undriven
    print("self-test OK: bidirectional prob_load (fwd prob + bwd load) consistent")
    print(f"  contention(0,1)->px={r.px:.3f} gdrv={r.gdrv:.3f} | "
          f"node cload={node.cload*1e15:.1f}fF rwire={node.rwire:.0f} "
          f"t_pd={d18*1e12:.2f}ps -> {delay_of(node20,R_STRONG)*1e12:.2f}ps(+1 fanout)")
    return 0


if __name__ == "__main__":
    sys.exit(_self_test())
