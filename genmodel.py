#!/usr/bin/env python3
"""
stat-sim genmodel -- emit Verilog-AMS models that carry silicon-characterized
metastability, for finding clock-domain-crossing (CDC) bugs by simulation.

This is the headline deliverable: a standalone generator that turns a
per-cell, per-corner metastability characterization (tau, T0, setup/hold, tcq --
produced by `characterize` from transistor-level Monte Carlo on a PDK) into a
portable Verilog-AMS metastable D-flop and a 2-stage synchronizer wrapper.

Implements the probability-waveform method of US8478576B1: on a setup/hold
violation the flop output enters a mid-rail plateau for a duration drawn from
Exp(tau), then resolves. Aggregated over Monte Carlo trials, the executable
model *is* the patent's P(out = 1, t). The mid-rail plateau is exactly the
invalid level a downstream `check` pass flags as a CDC bug.

The emitted Verilog-AMS targets a Verilog-AMS-capable engine (Spectre AMS,
Xyce/PyMS, AMS Designer); it plugs into the same shim/SimDriver layer bfit uses.
"""
import os, sys, json, math, argparse
from dataclasses import dataclass, asdict, field


@dataclass
class CellSpec:
    """Metastability characterization of one flip-flop cell at one corner.

    Times in seconds, voltages in volts. Defaults are placeholder
    order-of-magnitude values for a sky130 1.8 V DFF; real values come from
    `characterize` (transistor-level MC). See README for tau/T0/MTBF meaning.
    """
    name:      str   = "statsim_dff"   # base module name
    vdd:       float = 1.8             # supply / logic-high level
    vth:       float = 0.9             # logic decision threshold (default vdd/2)
    tau:       float = 50e-12          # metastability resolution time constant
    t0:        float = 20e-12          # metastability aperture (window) constant
    tsetup:    float = 80e-12          # setup time
    thold:     float = 40e-12          # hold time
    tcq:       float = 120e-12         # nominal (unloaded) clock->q delay
    r_drive:   float = 100.0           # output drive resistance (ohm) -> on-the-fly delay
    tmeta_max: float = 5e-9            # clamp on injected metastable duration
    seed:      int   = 1               # default RNG seed (per-instance overridable)
    corner:    str   = "tt"            # PDK corner this was characterized at

    def __post_init__(self):
        for f in ("vdd", "tau", "t0", "tsetup", "thold", "tcq", "tmeta_max"):
            if getattr(self, f) <= 0:
                raise ValueError(f"{f} must be > 0 (got {getattr(self, f)})")
        if not (0 < self.vth < self.vdd):
            raise ValueError(f"vth must be in (0, vdd); got {self.vth}/{self.vdd}")


def mtbf(spec: CellSpec, t_slack: float, f_clk: float, f_data: float) -> float:
    """Mean time between (unresolved) failures for available settling slack
    `t_slack`, sampling clock `f_clk`, data toggle rate `f_data`.
    MTBF = exp(t_slack/tau) / (T0 * f_clk * f_data).  Returns seconds (inf if
    no metastability can be entered)."""
    denom = spec.t0 * f_clk * f_data
    if denom <= 0:
        return math.inf
    return math.exp(t_slack / spec.tau) / denom


# ---------------------------------------------------------------------------
# Verilog-AMS templates. No literal '{' '}' in the bodies (Verilog-AMS uses
# begin/end), so str.format substitution is safe.
# ---------------------------------------------------------------------------
_META_DFF = """\
// ===========================================================================
// {name} -- metastable D flip-flop  (stat-sim generated; do not hand-edit)
// Characterized corner: {corner}
//   tau={tau:g}s  T0={t0:g}s  tsetup={tsetup:g}s  thold={thold:g}s  tcq={tcq:g}s
// US8478576B1 probability-waveform metastability. On a setup/hold violation the
// output holds a mid-rail plateau for Exp(tau)-distributed time, then resolves.
// ===========================================================================
`include "constants.vams"
`include "disciplines.vams"

module {name} (d, clk, q);
  input  d, clk;
  output q;
  electrical d, clk, q;

  parameter real vdd       = {vdd:g};
  parameter real vth       = {vth:g};
  parameter real tau       = {tau:g} from (0:inf);
  parameter real tsetup    = {tsetup:g} from [0:inf);
  parameter real thold     = {thold:g} from [0:inf);
  parameter real tcq       = {tcq:g} from [0:inf);
  parameter real tmeta_max = {tmeta_max:g} from (0:inf);
  parameter integer seed   = {seed:d};
  // tmeta_force >= 0 overrides the random draw (lets `check` sweep worst cases
  // deterministically); < 0 means draw from Exp(tau).
  parameter real tmeta_force = -1;

  integer st;            // rng state
  real    last_d_edge;   // $abstime of last data transition
  real    t_resolve;     // absolute time metastability resolves
  real    q_val;         // resolved logic level driven after t_resolve
  real    u, tmeta;

  analog begin
    @(initial_step) begin
      st          = seed;
      last_d_edge = -1e30;
      t_resolve   = -1e30;
      q_val       = (V(d) > vth) ? vdd : 0.0;
    end

    // remember when data last crossed threshold (either direction)
    @(cross(V(d) - vth, 0))
      last_d_edge = $abstime;

    // active (rising) clock edge: sample
    @(cross(V(clk) - vth, +1)) begin
      q_val = (V(d) > vth) ? vdd : 0.0;
      // setup/hold aperture violated if the data edge sits inside it
      if ($abstime - last_d_edge < tsetup && last_d_edge - $abstime < thold) begin
        if (tmeta_force >= 0.0)
          tmeta = tmeta_force;
        else begin
          u     = abs($random(st)) / 2147483647.0 + 1e-12;   // (0,1]
          tmeta = -tau * ln(u);
          if (tmeta > tmeta_max) tmeta = tmeta_max;
        end
        t_resolve = $abstime + tcq + tmeta;
      end else
        t_resolve = $abstime + tcq;
    end

    // output: mid-rail plateau while metastable, else the resolved level
    if ($abstime < t_resolve)
      V(q) <+ vth;              // invalid level -> downstream CDC-bug detector
    else
      V(q) <+ q_val;
  end
endmodule
"""

_SYNC2 = """\
// ===========================================================================
// {name}_sync2 -- standard 2-flop CDC synchronizer (two {name} chained)
// First stage absorbs metastability; second resamples. MTBF is set by the
// slack between stages = one clock period minus tcq.  (stat-sim generated)
// ===========================================================================
`include "disciplines.vams"

module {name}_sync2 (d, clk, q);
  input  d, clk;
  output q;
  electrical d, clk, q, n_mid;

  parameter real vdd        = {vdd:g};
  parameter real vth        = {vth:g};
  parameter real tau        = {tau:g};
  parameter real tsetup     = {tsetup:g};
  parameter real thold      = {thold:g};
  parameter real tcq        = {tcq:g};
  parameter real tmeta_max  = {tmeta_max:g};
  parameter integer seed    = {seed:d};

  {name} #(.vdd(vdd), .vth(vth), .tau(tau), .tsetup(tsetup), .thold(thold),
           .tcq(tcq), .tmeta_max(tmeta_max), .seed(seed))
    stage1 (.d(d),     .clk(clk), .q(n_mid));
  {name} #(.vdd(vdd), .vth(vth), .tau(tau), .tsetup(tsetup), .thold(thold),
           .tcq(tcq), .tmeta_max(tmeta_max), .seed(seed + 1))
    stage2 (.d(n_mid), .clk(clk), .q(q));
endmodule
"""


_CDC_TRAP = """\
// ===========================================================================
// {name}_cdc_trap -- CDC bug detector  (stat-sim generated)
// The trap: at each latch/flop CLOCK TRANSITION (the sampling instant), check
// whether the data node sits at a clean logic rail. A value inside the invalid
// band (vlo, vhi) is a captured-metastability / CDC hazard. Accumulates the
// empirical probability over the run; aggregate p_bad over Monte Carlo seeds to
// get the failure probability (and, with the sampling rate, the MTBF).
// This is the US8478576B1 probability-waveform overlap, evaluated at the clock.
// ===========================================================================
`include "disciplines.vams"

module {name}_cdc_trap (clk, d);
  input clk, d;
  electrical clk, d;

  parameter real vdd  = {vdd:g};
  parameter real vth  = {vth:g};               // clock decision threshold
  parameter real vlo  = {vlo:g};               // <= vlo counts as a clean 0
  parameter real vhi  = {vhi:g};               // >= vhi counts as a clean 1
  // edge: +1 closing/rising only, -1 falling only, 0 either transition
  parameter integer edge = 0;

  integer n_sample, n_bad;
  real    p_bad;

  analog begin
    @(initial_step) begin
      n_sample = 0; n_bad = 0; p_bad = 0.0;
    end
    @(cross(V(clk) - vth, edge)) begin         // clock in transition = sample instant
      n_sample = n_sample + 1;
      if (V(d) > vlo && V(d) < vhi)             // not a clean rail -> CDC hazard
        n_bad = n_bad + 1;
      p_bad = (n_sample > 0) ? (1.0 * n_bad) / n_sample : 0.0;
    end
    @(final_step)
      $strobe("[cdc_trap %M] samples=%0d bad=%0d p_bad=%g", n_sample, n_bad, p_bad);
  end
endmodule
"""


def meta_dff_vams(spec: CellSpec) -> str:
    return _META_DFF.format(**asdict(spec))


def sync2_vams(spec: CellSpec) -> str:
    return _SYNC2.format(**asdict(spec))


def cdc_trap_vams(spec: CellSpec) -> str:
    d = asdict(spec)
    d.setdefault("vlo", 0.1 * spec.vdd)         # clean-0 ceiling
    d.setdefault("vhi", 0.9 * spec.vdd)         # clean-1 floor
    return _CDC_TRAP.format(**d)


def emit(spec: CellSpec, outdir: str) -> list:
    """Write <name>.vams, <name>_sync2.vams, <name>_cdc_trap.vams. Returns paths."""
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for fname, text in ((f"{spec.name}.vams", meta_dff_vams(spec)),
                        (f"{spec.name}_sync2.vams", sync2_vams(spec)),
                        (f"{spec.name}_cdc_trap.vams", cdc_trap_vams(spec))):
        p = os.path.join(outdir, fname)
        with open(p, "w") as fh:
            fh.write(text)
        paths.append(p)
    return paths


def load_spec(path: str) -> CellSpec:
    with open(path) as fh:
        d = json.load(fh)
    known = {k: d[k] for k in d if k in CellSpec.__dataclass_fields__}
    return CellSpec(**known)


def _self_test() -> int:
    spec = CellSpec(name="statsim_dfxtp", tau=45e-12, t0=18e-12,
                    tsetup=90e-12, thold=35e-12, tcq=110e-12, corner="ss")
    dff = meta_dff_vams(spec)
    sync = sync2_vams(spec)
    trap = cdc_trap_vams(spec)
    checks = [
        ("module statsim_dfxtp (d, clk, q);", dff),
        ("@(cross(V(clk) - vth, +1))",        dff),
        ("V(q) <+ vth;",                      dff),       # the metastable plateau
        ("tmeta = -tau * ln(u);",             dff),       # Exp(tau) draw
        ("module statsim_dfxtp_sync2",        sync),
        ("stage1 (.d(d),     .clk(clk), .q(n_mid));", sync),
        ("module statsim_dfxtp_cdc_trap",     trap),
        ("if (V(d) > vlo && V(d) < vhi)",     trap),      # the CDC trap condition
    ]
    for needle, hay in checks:
        if needle not in hay:
            print(f"SELF-TEST FAIL: missing {needle!r}")
            return 1
    # MTBF sanity: more slack -> exponentially larger MTBF; must be monotone
    m1 = mtbf(spec, 1e-9, 100e6, 50e6)
    m2 = mtbf(spec, 2e-9, 100e6, 50e6)
    if not (m2 > m1 > 0):
        print(f"SELF-TEST FAIL: MTBF not monotone ({m1:g} -> {m2:g})")
        return 1
    # exp(1ns/45ps) factor between the two
    ratio = m2 / m1
    want = math.exp((2e-9 - 1e-9) / spec.tau)
    if abs(ratio - want) / want > 1e-9:
        print(f"SELF-TEST FAIL: MTBF ratio {ratio:g} != exp(dt/tau) {want:g}")
        return 1
    print("self-test OK: metastable DFF + sync2 emitted, MTBF math consistent")
    print(f"  MTBF(slack=1ns) = {m1:.3e} s   MTBF(slack=2ns) = {m2:.3e} s")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="genmodel",
        description="Generate Verilog-AMS metastable synchronizer models.")
    ap.add_argument("--spec", help="cell spec JSON (CellSpec fields)")
    ap.add_argument("--out", default="models", help="output directory")
    ap.add_argument("--self-test", action="store_true",
                    help="run a no-simulator self-test and exit")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    spec = load_spec(args.spec) if args.spec else CellSpec()
    paths = emit(spec, args.out)
    for p in paths:
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
