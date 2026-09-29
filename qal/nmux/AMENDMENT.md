# Protocol amendments — qal/nmux

## A1 — the PyMS VAE-cache NULL-MODEL trap (recorded 2026-09-29, before any
## number in this directory was used for anything)

### What happened
`PYMS_VAE_CACHE` was pointed at a fresh, empty directory (`vae_cache_nmux`) as
the sim discipline requires ("own your cache"). The first three Vt decks
(`vtb_0000`, `vtb_0050`, `vtb_0100`) ran to completion, **exit code 0**, and
wrote full-length, well-formed `.prn` files (1501 rows, correct columns).

They are **VOID**. Every current in them is the integrator floor:

```
Index       V(G)              V(S)              V(D)              I(VD)
0        0.00000000e+00    0.00000000e+00    1.00000000e-01   -1.00000000e-13
...      Id at Vgs = 1.0 V:  0.0000 uA          (real device: ~62.24 uA)
```

The PSP103 `.so` had not finished compiling (`cc1plus` on a 1.0 MB `eval.cpp`,
several minutes on a box also running another workflow's nine parallel
compiles). Xyce did not fail, did not warn in anything the runner captured, and
produced a **silently dead device**.

### How it was caught
The pre-registered instrument gate **G1** — "Vtn at V_sb = 0 reproduces the
committed 0.5239460 V within 1 mV" — was evaluated on the first row before any
downstream use. There is no crossing of the 569.2 nA criterion anywhere in a
dead device, so G1 failed loudly. Without G1 this run would have produced a
plausible-looking table of `None`s, or worse, a body-effect curve fitted to
noise.

### Amendment (made BEFORE any measured number was reported)
1. All 17 `vtb_*` decks are **re-run from scratch** once the `.so` exists. No
   number from the void pass is used anywhere.
2. A **warm deck** (`warm.cir`) that instantiates every device geometry this
   study uses is run to completion, and the `.so` is confirmed present on disk,
   **before** any measurement stage starts.
3. A **null-model canary** is added to every stage: a run is rejected unless a
   known-live quantity is non-trivial (DC stages: the device must reach
   > 1 uA somewhere in the sweep; transient stages: the rail must exceed 0.1 V).
   A run failing the canary is an instrument failure, not a data point.

This is the same class of defect as the committed `async_power_anchor` "vae
cache trap" and is recorded here because it cost a pass of 17 decks.

## A2 — gate-source variant added beyond pre-registration (addition, not change)

The pre-registration pins the select drive to the 1.5 V control rail. That is
defensible for a MUX2 (a datapath select is control, generated once and shared
across the word) but **not** for an XOR2, where one operand *must* drive the
pass-transistor gates and therefore arrives at the QAL **rail** level, not at
1.5 V. Runs at `gate_src = "rail"` are therefore **added** for every design.
Nothing pre-registered is dropped; the 1.5 V rows remain primary and the
rail-level rows are reported alongside them.

## A3 — Vt DC sweep start raised from 0 V to 0.2 V (recorded before any Vt number was used)

Pre-registered: `.dc VG 0 1.5 0.001`. With the source lifted for body bias the
drain current near `Vgs = 0` is ~1e-15 A, at or below the deck's `ABSTOL=1e-15`,
and Xyce stalls there: `vtb_0200` and `vtb_0400` each ran **> 6 minutes** without
finishing while neighbouring rows finished in seconds. Both were killed by PID
(`pkill -f` in a compound command would have killed the shell — the campaign's
recorded trap).

**Amended:** sweep `0.2 -> 1.5 V`, everything else identical. Nothing measured is
lost: Vtn over the whole probed `V_sb` range is 0.52-0.85 V, and even the
tightest criterion reported (1 nA*W/L = 5.69 nA) lands near 0.29 V at `V_sb = 0`.
The `V_sb = 0` row therefore still has to reproduce the committed 0.5239460 V,
so instrument gate G1 is unchanged and undiluted.

## A4 — the Vgs axis bug (caught by a physics sanity check, not by a gate)

`vtb.py` printed `V(g)`, `V(s)`, `V(d)`, `I(VD)` and the extractor used column 1,
`V(g)`, as the sweep axis. With the source lifted to `V_sb` for body bias, the
floating gate source `VG(g,s)` puts the **absolute** gate at `V_sb + Vgs`, so
every threshold came out exactly `V_sb` too high.

The symptom was a body-effect slope of **+1.12 V per volt of V_sb**, rigid across
three decades of drain current. A MOSFET body factor is well below 1 at these
biases, and a *rigid* shift across three decades is the signature of an axis
offset, not of a physical threshold shift — a real `gamma*sqrt` effect compresses
with `V_sb`. Instrument gate **G1 did not catch this**: G1 only tests `V_sb = 0`,
where the offset is zero, so it passed at +0.041 mV while every other row was
wrong.

**Fixed:** sweep axis is `V(g) - V(s)`. The `.prn` files already carried both
columns, so **no deck was re-simulated** — the same raw data was re-extracted.
After the fix, `dVt` over the full 0 -> 1.3 V range is **+127.8 mV**, sub-square-root
and compressing with `V_sb`, which is what a bulk body effect looks like.

**Lesson recorded for the campaign:** an instrument gate anchored at a single
operating point cannot catch an error whose size is zero at that point. The
useful check here was dimensional — "is this slope physically possible?" — not a
reproduction check.

## A5 — peer-rail time step relaxed from the committed 0.0177663 ps to 0.05 ps

The committed peer deck (`qal/resv/h_I2_load691_L4.cir`) uses
`.tran 0.00888317p 584.286p 0 0.0177663p`. My peer decks add the pass structure,
four 0 V meter sources and twelve 1F integrators to that netlist, and on a box
carrying another workflow's ~16 concurrent Xyce jobs a single 350 ps PROBE ran
**> 400 s without finishing** — against the brief's "runs < 4 min".

**Amended:** `dt = 0.02 ps`, `max step = 0.05 ps` for both rails (0.05 ps is the
step the committed **tank** chain `ch_res20` already uses, so this is not a new
regime for the campaign). Overridable via `NMUX_DT` / `NMUX_MAXSTEP`.

Two things keep this honest:
1. instrument gate **G2** runs the committed peer deck **verbatim**, at its own
   original step — the reproduction check is untouched;
2. a **step-sensitivity row** re-runs one configuration at the committed
   0.0177663 ps step and reports the difference in the delivered pass level.
   If that difference is not small compared with the effects being reported, the
   relaxation is withdrawn.

## A6 — PyMS compiles one shared object PER DEVICE GEOMETRY (cost discovery, not a protocol change)

Diagnosing why 350 ps decks were taking 6+ minutes turned up the real cause. The
`.so.params` files in my cache show PyMS keys each compiled object on the FULL
device parameter set, **W and L included**:

```
vae_PSP103VA_5535244e13c1862f.so.params : W=6e-07   L=1.3e-07 TYPE=1
vae_PSP103VA_ba9792c1...so.params       : W=7.4e-07 L=1.3e-07 TYPE=1
vae_PSP103VA_d3a89200...so.params       : W=2e-05   L=1.3e-07 TYPE=-1
```

So **every distinct transistor width in this study costs its own ~5 minute
`cc1plus` run** (1.0 MB of generated C++, ~1.8 GB resident). A width sweep is
therefore not free the way it looks in the netlist. This is the same family as
the committed `pyms_callback_params` note ("de-hashed -> 1 .so/geom"), seen from
the cost side.

**Consequence recorded, no result changed:** geometries are now pre-compiled by
warm decks (`warm.cir`, `warm2.cir`) before the measurement stages need them,
and the width sweep is priced accordingly. The first pass of this study paid the
compile cost serially, inside the measurement runs, which is what made them look
like convergence failures.

## A7 — reduced chain geometry (6 banks kept, 8 bits/bank -> 4, step 0.0884 -> 0.2 ps)

Pre-registration P5 specified the committed `qal/resv ch_res20` chain with a pass
structure inserted in every hop. That deck is 1416 lines, ~150 devices, 2500 ps
at a 0.0884183 ps max step. On this box — carrying another workflow's ~16
concurrent Xyce jobs, with PyMS additionally paying a ~5 min `cc1plus` compile
per device geometry (A6) — a single such run is hours, not the brief's 4 minutes.

**Amended, with the direction of the bias stated:**
* **6 banks kept.** Depth IS the question; this is not negotiable.
* **4 bits per bank** instead of 8 — still two HIGH and two LOW cells, which is
  exactly what a `min(pull-up) - max(pull-down)` separation needs.
* **0.2 ps max step** instead of 0.0884183 ps.
* **The rail is deliberately NOT compensated** for the four removed cells. The
  reduced bank is a lighter load, so the delivered rail comes out *higher* than
  the committed 1.326 V. A higher rail makes the nMOS-only pass structure
  **worse** (part (a): the pass ceiling is fixed at 0.883 V, so more rail means
  more shortfall). The approximation therefore biases **against** the hypothesis
  under test, and the delivered rail is reported at every depth rather than
  assumed.

Consequence: chain separations here are **not** directly comparable digit-for-digit
with the committed 1325.7 / 1048.9 / 879.3 / 721.1 / 562.1 / 282.3 mV. The
`wire` variant is therefore run **in the same reduced geometry** as the control,
and every comparison in part (c) is made against that control, never against the
committed numbers.

## A8 — instrument gate G3 dropped, G2 retained

G3 (re-run the committed `ch_res20` deck verbatim in my own cache and reproduce
its six separation values) is unaffordable for the same reason as A7. **G2** —
re-running the committed peer deck `h_I2_load691_L4.cir` verbatim — is retained
and is sufficient for what the gate is for: it exercises the identical model,
cache, binary and options path on committed numbers. G1 (the Vt reproduction)
also passed independently. The loss is that no committed *chain* number is
reproduced; part (c) therefore rests on its own internal `wire` control, which is
stated wherever a part (c) number is used.

## A9 — locus probe added (addition beyond pre-registration)

`locus.py` measures the pass device's charging current along its **actual
operating locus** — gate at VGH, drain held at the rail by the driving cell,
source swept 0 -> 1.3 V with the bulk at 0 — and integrates `t = C * int dV/I`
to predict the level reached in a given window.

This was added because the pre-registration's framing of the "pass ceiling" was
subtly wrong and the data showed it. **A pass transistor has no DC ceiling at
all**: with no load current an ideal switch in steady state drops nothing, so a
pure DC probe would report V_out = V_rail and say nothing useful. What actually
limits the delivered level is that the charging current **collapses** as the
source rises, so the last stretch takes longer than the QAL window. The ceiling
is a **rate limit**, and it therefore depends on the load and the window, which
the `V* = VGH - Vtn(V*)` construction alone does not express.

The locus probe also uses the **real Vds** at every point, whereas the threshold
extraction of part (a) is at a fixed `Vds = 0.1 V` and therefore understates the
current while the node is low. Nothing in part (a) is withdrawn — the ceiling
table there fixes the *sign* of the answer at each rail, which is what it was for
— but the delivered-level numbers quoted in part (d) come from the transient
runs, cross-checked against this locus integration.

## A10 — two extraction defects in the energy metering (no re-simulation needed)

**A10a — UNITS.** A 1 F integrator holds `V = Q/C = Q`, so the node voltage is
**coulombs** for a charge meter and **joules** for a power meter. The first
extraction labelled the raw integrator deltas `_fC` and `_fJ` without the `1e15`
scale, so every energy printed as `0.000 fJ` when the real values were ~1–12 fJ.
Caught because an energy of exactly zero for a circuit that visibly charges a
2 fF node to 0.9 V is not physical. Nothing was wrong with any simulation; the
saved `.prn` files were re-extracted by `reextract.py`.

**A10b — THE GATE-DRIVE WINDOW WAS BLIND TO THE GATE DRIVE.** All integrators
were t0-referenced at `t_close - 5 ps`, but the select edge is at
`t_close - 30 ps`. The window therefore started *after* the only event that
costs gate-drive energy. What it did measure was the rising data node pushing
charge back out of the gate through Cgd — which is why `E_gate` came out
**negative**, and negative gate-drive energy is the tell. Both windows are now
reported and labelled:
* `E_gate_total_fJ` — from t = 1 ps, includes the select transition: the real
  per-operation gate cost;
* `E_gate_hop_only_fJ` — from `t_close - 5 ps`: the data-edge feedthrough alone.

**A10c — the "closure" check was mis-specified** and is withdrawn. It compared
the charge drawn from the driving cell against `C_load * V_out`, assuming all of
it lands on the load. It does not — the pass device's own source/drain
capacitance is charged too, which is a real cost of the pass structure and one of
the things this study is supposed to report. The split
(`Q_onto_load` vs `Q_into_pass_device`) is now measured and reported instead of
being asserted as a closure identity. The first pass's closure column read
`-100.00 %` on every row, which was the units bug (A10a) making `Q_in` look like
zero; it was not evidence about charge conservation either way.

## A11 — E9 refuted, and the reason I got it backwards (recorded with the result)

Pre-registered **E9** predicted the alternating pass/restore chain would survive
with the **skewed** 0.15p/1.48n restoring cell and fail by depth 2–3 with the
**standard** 1.12p/0.74n cell.

**MEASURED: the reverse.** `nmos` + std survives all six depths at 61–198× the
6.44 mV floor; `nmos` + skew falls to 3.2 mV — below the floor — by depth 6.

The error was a **role confusion**. The skewed cell was designed in the committed
boundary study as a **receiver**: it reads a QAL level into a static domain, where
a low trip point is the whole job and pull-up strength is irrelevant. Inside a QAL
chain the same geometry is a **restoring driver**, and its job is to pull its
output up to the resonant rail — with a pMOS that skewing has made 7.5× smaller.
The `wire` + skew control isolates this: with no pass structure at all it still
reaches only 1.1819 V from a 1.5298 V rail.

The committed `qal/chain3` record already said *"Limiting device = pull-UP at
every stage and every L"*. I had that line in front of me and still inverted it.
Recorded here because the brief specifically warned that getting the
transfer-role distinction wrong "in either direction" is the class of error this
campaign keeps catching — and this is an instance of it in a different component.

## A12 — the (g) injection-disposal claim was wrong in the first draft and is corrected

`MEASURED_g_mechanism.md` first argued that select-edge charge injection on a
logic mux "lands on an idle node and is then overwritten". The waveform refutes
it: peak and residue are identical (39.949 / 39.949 mV), because the injected
charge splits onto the **driving cell's output**, which is a pull-up whose only
path is through its pMOS to a rail that is still a **floating LC node**. Nothing
drains it until the rail arrives. The claim is corrected in that file, with the
pull-up / pull-down asymmetry stated (the pass-LOW residue is −0.00001 V because
that cell is a pull-down over a real ground).
