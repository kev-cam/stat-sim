#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
"""
stat-sim nvcgen -- emit the nvc runtime form of the metastable models, on the
bidirectional `prob_load` discipline (lib/statsim_disc.vhd).

The models are AUTHORED in Verilog-AMS (genmodel.py) but RUN event-driven in nvc
on the prob_load nature: a node carries the logic probability forward and a
capacitance-like load backward, so propagation delay is computed ON THE FLY from
the resolved fan-out + SPEF load (no static delay generic, no analog solve).

Per cell we emit:
  * the metastable D flip-flop -- ports `resolved_pl`; `q` is `inout` so the
    process reads the RESOLVED net load (its own taps) back to size delay.
      - rising clock edge: hi := clk.p1 > 0.5
      - data value:        d.p1 >= d.p0
      - aperture violation: d'last_event < TSETUP  -> metastable: drive PL_X
        (mid-rail plateau) for an Exp(tau) window + slew, then resolve.
      - on-the-fly delay:  TCQ0 + ln2*(R_DRIVE + q.rwire)*q.cload
      - DEFECT generic (-1 = good): the US20230334213A1 good/bad model-switch seam.
  * the CDC trap -- at each clock transition, flag px_of(d) > PX_THR (the data
    node not at a clean rail = captured-metastability hazard).

Passive load/wire taps live in lib/statsim_taps.vhd; the binder instantiates them
from spef.taps_for_net().
"""
import os, sys
from dataclasses import asdict
from genmodel import CellSpec


def _ps(seconds: float) -> str:
    """real seconds -> a VHDL `time` literal in ps (1 fs resolution)."""
    return f"{seconds * 1e12:.6g} ps"


def _real(x: float) -> str:
    """real -> a valid VHDL real literal (must carry a '.' or exponent; '100' is
    illegal as a real, '100.0' is fine)."""
    s = f"{x:g}"
    if "." not in s and "e" not in s and "E" not in s:
        s += ".0"
    return s


_VHDL_DFF = """\
-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
-- {name} -- metastable D flip-flop, nvc/prob_load runtime form (stat-sim generated)
-- Authored in Verilog-AMS ({name}.vams). Event-driven; load-dependent delay.
-- Corner: {corner}.  Output holds PL_X (mid-rail/invalid) for an Exp(tau) window
-- after a setup/hold violation, then resolves -- all scheduled, no analog solve.
library ieee;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;

entity {name} is
  generic ( TAU       : real := {tau_r};          -- s, regeneration time constant
            TSETUP    : time := {tsetup_ps};       -- setup aperture (backward 'last_event)
            THOLD     : time := {thold_ps};        -- hold; NOTE: hold-after-edge is not
                                                   -- detectable with backward 'last_event (known gap)
            T0        : real := {t0_r};            -- s, metastability aperture -> feeds the
                                                   -- analytic MTBF (genmodel.mtbf), not per-trial entry
            TCQ0      : time := {tcq_ps};          -- intrinsic UNLOADED clock->q
            R_DRIVE   : real := {r_drive_r};       -- output drive resistance (ohm)
            TMETA_MAX : time := {tmeta_max_ps};
            SEED      : integer := {seed:d};
            DEFECT    : integer := -1 );           -- '213 seam: good=-1; 0/1 = stuck-at variant
  port ( d   : in    resolved_pl;
         clk : in    resolved_pl;
         q   : inout resolved_pl := PL_FLOAT );    -- inout: read RESOLVED net load back
end entity;

architecture pwl of {name} is
begin
  process(clk)
    variable prev_hi : boolean := false;
    variable hi, dhi, meta : boolean;
    variable s1, s2  : integer := SEED;
    variable u, ts, tpd, tsl : real;
    variable tcq_eff, tmeta, tslew, tplat : time;
  begin
    hi := clk.p1 > 0.5;                            -- rising clock edge (prob terms)
    if hi and not prev_hi then
      dhi := d.p1 >= d.p0;                          -- sampled data value
      -- on-the-fly load-dependent delay from the RESOLVED output net (q is inout)
      tpd := LN2 * (R_DRIVE + q.rwire) * q.cload;
      tsl := LN9 * (R_DRIVE + q.rwire) * q.cload;
      tcq_eff := TCQ0 + integer(maximum(tpd, TPD_FLOOR) * 1.0e15) * 1 fs;
      tslew   := integer(maximum(tsl, 0.0) * 1.0e15) * 1 fs;
      -- metastable if the data EDGE landed in the setup aperture, OR the sampled
      -- data LEVEL is itself invalid (an already-metastable input propagates).
      meta := (d'last_event < TSETUP) or (px_of(d) > 0.5);
      if DEFECT = 0 then                            -- '213 minimal defect: stuck-at-0
        q <= PL_0 after tcq_eff;
      elsif DEFECT = 1 then                         -- stuck-at-1
        q <= PL_1 after tcq_eff;
      elsif meta then
        uniform(s1, s2, u);
        ts := -TAU * log(u);                        -- Exp(tau) metastable duration, s
        tmeta := integer(ts * 1.0e15) * 1 fs;
        if tmeta > TMETA_MAX then tmeta := TMETA_MAX; end if;
        tplat := tmeta + tslew;
        if tplat < 1 fs then tplat := 1 fs; end if; -- never drop the PL_X plateau (unloaded net)
        if dhi then
          q <= PL_X after tcq_eff, PL_1 after tcq_eff + tplat;
        else
          q <= PL_X after tcq_eff, PL_0 after tcq_eff + tplat;
        end if;
      else                                          -- clean capture
        if dhi then q <= PL_1 after tcq_eff; else q <= PL_0 after tcq_eff; end if;
      end if;
    end if;
    prev_hi := hi;
  end process;
end architecture;
"""


_VHDL_TRAP = """\
-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
-- {name}_cdc_trap -- CDC bug detector, nvc/prob_load runtime form (stat-sim generated)
-- At each RISING clock edge (the capture instant, matching the rising-edge DFF) flag
-- px_of(d) > PX_THR: the data node is not at a clean rail = captured-metastability /
-- CDC hazard. p_bad = n_bad/n_sample over Monte Carlo seeds = failure probability.
-- This IS the probability waveform read natively off the node (no voltage sampling).
library ieee;
library statsim;
use statsim.statsim_disc_pkg.all;

entity {name}_cdc_trap is
  generic ( PX_THR : real := 0.5 );                -- px above this at a clock edge = hazard
  port ( clk : in resolved_pl; d : in resolved_pl );
end entity;

architecture pwl of {name}_cdc_trap is
  signal n_sample : natural := 0;
  signal n_bad    : natural := 0;
begin
  process(clk)
    variable prev_hi : boolean := false;
    variable hi      : boolean;
  begin
    hi := clk.p1 > 0.5;
    if hi and not prev_hi then                      -- RISING edge only (matches the DFF capture)
      n_sample <= n_sample + 1;
      if px_of(d) > PX_THR then                     -- not a clean rail -> CDC hazard
        n_bad <= n_bad + 1;
        report "{name}_cdc_trap: CDC hazard, px=" & real'image(px_of(d))
          severity warning;
      end if;
    end if;
    prev_hi := hi;
  end process;
  -- p_bad = n_bad / n_sample, summarized by the MC driver across seeds.
end architecture;
"""


def vhdl_dff(spec: CellSpec) -> str:
    d = asdict(spec)
    d.update(tsetup_ps=_ps(spec.tsetup), thold_ps=_ps(spec.thold),
             tcq_ps=_ps(spec.tcq), tmeta_max_ps=_ps(spec.tmeta_max),
             tau_r=_real(spec.tau), t0_r=_real(spec.t0), r_drive_r=_real(spec.r_drive))
    return _VHDL_DFF.format(**d)


def vhdl_cdc_trap(spec: CellSpec) -> str:
    return _VHDL_TRAP.format(**asdict(spec))


def emit(spec: CellSpec, outdir: str) -> list:
    """Write <name>.vhd and <name>_cdc_trap.vhd (nvc/prob_load runtime form)."""
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for fname, text in ((f"{spec.name}.vhd", vhdl_dff(spec)),
                        (f"{spec.name}_cdc_trap.vhd", vhdl_cdc_trap(spec))):
        p = os.path.join(outdir, fname)
        with open(p, "w") as fh:
            fh.write(text)
        paths.append(p)
    return paths


def _self_test() -> int:
    spec = CellSpec(name="statsim_dfxtp", tau=45e-12, tsetup=90e-12,
                    tcq=110e-12, r_drive=100.0, corner="ss")
    dff, trap = vhdl_dff(spec), vhdl_cdc_trap(spec)
    needles = [
        ("entity statsim_dfxtp is", dff),
        ("q   : inout resolved_pl", dff),                       # prob_load inout port
        ("hi := clk.p1 > 0.5;", dff),                           # edge in prob terms
        ("tpd := LN2 * (R_DRIVE + q.rwire) * q.cload;", dff),   # on-the-fly delay
        ("meta := (d'last_event < TSETUP) or (px_of(d) > 0.5);", dff),  # aperture OR invalid input
        ("q <= PL_X after tcq_eff,", dff),                      # PWL plateau->resolve
        ("ts := -TAU * log(u);", dff),                          # Exp(tau)
        ("if tplat < 1 fs then tplat := 1 fs;", dff),           # plateau never dropped
        ("THOLD     : time", dff),                              # hold generic plumbed
        ("T0        : real", dff),                              # aperture generic plumbed
        ("DEFECT    : integer := -1", dff),                     # '213 model-switch seam
        ("if DEFECT = 0 then", dff),                            # defect variant branch
        ("entity statsim_dfxtp_cdc_trap is", trap),
        ("if hi and not prev_hi then", trap),                   # rising-only (matches DFF)
        ("if px_of(d) > PX_THR then", trap),                    # px-native trap
    ]
    for n, hay in needles:
        if n not in hay:
            print(f"SELF-TEST FAIL: missing {n!r}")
            return 1
    print("self-test OK: prob_load metastable DFF (+DEFECT seam) + px CDC trap emitted")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--self-test" in argv:
        sys.exit(_self_test())
    out = argv[argv.index("--out") + 1] if "--out" in argv else "models"
    if "--spec" in argv:
        from genmodel import load_spec
        spec = load_spec(argv[argv.index("--spec") + 1])
    else:
        spec = CellSpec()
    for p in emit(spec, out):
        print("wrote", p)
