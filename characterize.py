#!/usr/bin/env python3
"""
stat-sim characterize -- extract a flop's metastability parameters (tau, T0,
setup/hold, tcq) from its cross-coupled regenerative pair, for genmodel.

This is the bfit extension point. bfit's `merge.recognize_xcoupled()` already
finds the regenerative pair (two inverters with qa<->qb positive feedback -- the
storage/metastable core of any latch or flip-flop) and gives us its square-law
device params (kp, vth) folded into one component. stat-sim reads that pair and
derives the metastability resolution time constant.

Physics: linearize the qa<->qb loop at its metastable balance point (qa=qb=Vm).
Each node has capacitance C; each device contributes transconductance gm at Vm.
The loop has one positive real eigenvalue lambda ~= gm_eff/C; a small imbalance
grows as exp(+lambda*t), so the resolution time constant is

        tau = 1 / lambda = C / gm_eff .

That tau is exactly the exponent in P(still metastable after t) = exp(-t/tau).

`analytic_spec()` computes a first-order tau from the pair NOW (no simulator) --
useful immediately and a good MC seed. `refine_with_mc()` then drives the real
cell through bfit's SimDriver/shim layer across sky130 MC corners to measure
tau/T0/setup/hold/tcq directly; that loop is the next increment.
"""
import os, sys, math
from genmodel import CellSpec

# bfit lives next door; import its regenerative-pair detector + driver layer.
BFIT_DIR = os.environ.get("BFIT_DIR", "/usr/local/src/sv2ghdl/bfit")
if BFIT_DIR not in sys.path:
    sys.path.insert(0, BFIT_DIR)


def find_regen_pair(netlist_text):
    """Return the cross-coupled regenerative pair(s) in a cell netlist, via
    bfit's `merge.recognize_xcoupled`. Each entry carries qa/qb/vdd/vss and the
    per-device square-law params (kp, vth). Raises if bfit isn't importable."""
    import merge  # bfit/merge.py
    net = merge.parse_netlist(netlist_text) if hasattr(merge, "parse_netlist") else netlist_text
    matches = merge.recognize_xcoupled(net)
    return matches


def analytic_spec(name, kp_n, vth_n, kp_p, vth_p, vdd=1.8, cnode=2e-15,
                  corner="tt", **kw):
    """First-order CellSpec from the regenerative pair's square-law params.

    Balance point Vm: solve i_n(Vm) = i_p(Vm) for the cross-coupled inverter
    (saturation, equal node voltages). Then gm_eff = gm_n + gm_p at Vm and
    tau = cnode / gm_eff. setup/hold/tcq are left at CellSpec defaults and
    flagged for MC measurement (not analytically available from dc params).
    """
    # Saturation drain currents: i = 0.5*kp*(Vgs-vth)^2. At balance qa=qb=Vm, the
    # NMOS sees Vgs=Vm, the PMOS sees Vsg=vdd-Vm. Solve i_n=i_p for Vm.
    # 0.5 kp_n (Vm-vth_n)^2 = 0.5 kp_p (vdd-Vm-|vth_p|)^2
    rn, rp = math.sqrt(max(kp_n, 1e-18)), math.sqrt(max(kp_p, 1e-18))
    vtp = abs(vth_p)
    # rn*(Vm-vth_n) = rp*(vdd-vtp-Vm)  ->  Vm*(rn+rp) = rn*vth_n + rp*(vdd-vtp)
    vm = (rn * vth_n + rp * (vdd - vtp)) / (rn + rp)
    vm = min(max(vm, vth_n + 1e-3), vdd - vtp - 1e-3)
    gm_n = kp_n * (vm - vth_n)            # d/dV of 0.5 kp (V-vth)^2
    gm_p = kp_p * (vdd - vm - vtp)
    gm_eff = max(gm_n + gm_p, 1e-9)
    tau = cnode / gm_eff
    # T0 (aperture): order-of-magnitude tied to tau pending MC; documented stub.
    t0 = tau
    return CellSpec(name=name, vdd=vdd, vth=round(vm, 6), tau=tau, t0=t0,
                    corner=corner)


def refine_with_mc(spec, pair, driver, corners=("tt", "ss", "ff"),
                   n_trials=200):
    """Measure tau/T0/setup/hold/tcq directly from the transistor cell across
    sky130 MC corners using bfit's SimDriver/shim layer.

    Method (next increment):
      tau  -- bisect the input/clock timing to drive the pair into its metastable
              balance, then fit the exp(+t/tau) divergence of V(qa)-V(qb).
      T0   -- width of the data-vs-clock window that produces resolution time > a
              threshold, integrated over MC draws.
      tsu/th/tcq -- edge-sweep the data arrival vs clock and read the failure
              boundary and the resolved clk->q delay.
    Returns a per-corner dict of refined CellSpecs.
    """
    raise NotImplementedError(
        "MC refinement loop is the next increment; analytic_spec() seeds it. "
        "Driver/shim wiring and the bisect-to-balance measurement go here.")


if __name__ == "__main__":
    # demo: analytic tau for a representative sky130-scale inverter pair
    s = analytic_spec("statsim_dfxtp", kp_n=2e-4, vth_n=0.45,
                      kp_p=1e-4, vth_p=-0.45, vdd=1.8, cnode=2e-15)
    print(f"balance Vm={s.vth:.3f} V   tau={s.tau:.3e} s   T0={s.t0:.3e} s")
    print(f"MTBF(slack=1ns, fc=100MHz, fd=50MHz) = "
          f"{__import__('genmodel').mtbf(s, 1e-9, 100e6, 50e6):.3e} s")
