# rf/ -- spectral RF signals: GPU benchmarks and transistor-level fitting

Prototype work, 2026-11-15, on the RTX 3070 Ti Laptop GPU (CUDA 13.5) and i9-12900H.

## gpu_bench/ -- does a GPU process spectral signals faster?

`smak && ./bench all > results.csv`. Three operations on B signals of K complex bins:
`linear` (y = H.*x), `nonlin` (IFFT -> polynomial -> FFT, cuFFT vs FFTW) and `arena`
(Friis-coupled sum over M antennas per bin). CPU is one thread and 20 threads
(AVX2, -O3 -ffast-math); GPU is timed with data resident on the device (`gpu_res`) and
with a host round trip per event (`gpu_rt`).

- Fixed GPU cost per event: ~5 us launch+sync, ~18 us with the round trip. The CPU does a
  64-bin linear op in 0.16 us and a 64-bin nonlinearity in 0.25 us, so single small
  spectra are 30-100x slower on the GPU.
- Break-even with data resident (float): ~32k bins total for linear, ~8-16k for nonlin,
  M ~ 8-16 antennas for the arena.
- Arena, 64 bins, float: M=1024 is 107 ms on one thread, 30 ms on 20 threads, 0.70 ms on
  the GPU (153x / 44x). In double the GPU advantage drops to ~12x / 3.5x.
- Float loses phase accuracy in the arena (6e-5 relative error; the path phase is
  thousands of radians). Forming the phase in double and the rest in float (`f32+p64`)
  gives 1e-7..6e-7 error and M=512: 68.6 ms / 15.0 ms CPU-double vs 0.78 ms GPU (88x / 19x).
- Batched nonlinearity, 4096 signals x 64 bins, float: 335 us / 81 us CPU vs 17.6 us GPU
  resident (19x / 4.6x); with the round trip (404 us) the GPU loses to 20 threads.
- Linear ops with a host round trip never win (copy-bound, 0.5x at best).

## rffit.py -- fit a spectral model to a transistor-level circuit

Drives an existing SPICE netlist with Xyce harmonic balance, sweeps level and frequency,
fits per-harmonic complex gain vs drive (table + polynomial), holds out every other level,
and (amp) predicts a two-tone IM test that Xyce then runs. Writes `models/<name>.json` and
a VHDL package using `rf.rf_signal_pkg` (checked with nvc in `vhdl_check/`).

    rffit.py amp   --netlist N --src V1 --out 'V(out)' --freqs 1e6 --amps 1e-3:0.5:17 --twotone 2e4 --name x
    rffit.py mixer --netlist N --lo VLO --rf V5 --flo 1e6 --frf 1.1e6 --lo-amp 0.1 --out 'V(5,3)' --amps 1e-3:0.2:13 --name y

Results so far (commands in the session; models in `models/`):

| circuit | source | result |
|---|---|---|
| BJT common-emitter amp, 1 MHz | Xyce_Regression/HB/common_emitter_hb.cir | 14.6 dB; two-tone IM3 predicted within 0.1 dB from -163 to -67 dBc |
| BJT Gilbert-cell mixer | Xyce_Regression/HB/gilbert_cell_hbt.cir | 26.4 dB conversion gain; table hold-out -72 dBc; 3 highest RF levels did not converge |
| sky130 2.4 GHz LNA (fit not in repo: source has no licence) | ~/rf_spectral/circuits/chinmay-sky130-lna-2g4/lna_xyce_fit.cir | 24.8 dB at 2.4 GHz, P1dB(in) 102 mV pk; IM3 within 0.5 dB at 2 MHz spacing, 3 dB off at 20 MHz (gain slope ~0.12 dB/MHz) |
| class-E PA, 850 MHz, BSIM3 | ~/rf_spectral/circuits/asco-classe-pa/classE_xyce.cir | needs `--hbopts tahb=2 --harm 15 --src-dc 1.0`; IM3 within 0.5 dB up to 79 mV/tone, Xyce two-tone fails above |

Known limits: the polynomial form is poor for hard-compressing circuits (use the table;
the VHDL package currently emits the polynomial); e.g. the
`ft8_lna4_ext` package used by `vhdl_check/tb.vhd` reports 79.9 dB small-signal at 28 MHz where
the table has 90.1 dB; the model uses the nearest fitted
frequency, so narrowband circuits need per-bin frequency response; the sky130 LNA repo
has no licence; the IHP SG13G2 circuits in `~/rf_spectral/circuits/ihp-*` do not run (no VBIC level 12
in this Xyce build).

## pipeline/ -- real-time factor of a windowed TX -> air -> RX pipeline

`smak && ./pipe 64 > results.csv`. M radios each send B 64-bin OFDM symbols (4 us each)
per window; on the device: TX filter -> PA (fitted class-E table) -> all-pairs Friis
arena (precomputed coupling, phase formed in double) -> LNA (fitted table, extracted FT8 LNA) ->
mixer/filter. One sync per window; float; GPU matches the CPU reference to 3e-7..8e-7.

- Fixed cost ~22 us per window (9 launches), so a window must hold >= ~16 symbols
  (64 us of lookahead) before the GPU passes real time; at 1-4 symbols it is 0.15-0.7x.
- Real-time factor at the best window size: M=2: 115x, M=8: 26x, M=32: 4.3x, M=128: 0.46x,
  M=512: 0.03x.  20 CPU threads: 16x, 3.8x, 0.57x, 0.08x, 0.006x.
- The TX/RX chains are cheap (M=128, B=1024: 1.3 ms of a 22.8 ms window); the all-pairs
  arena kernel is the O(M^2) bottleneck and is memory-bound (throughput halves once the
  window outgrows cache).  A batched-GEMM layout and distance culling are the next things to try.

## Third-party circuits

The test circuits are not part of stat-sim and stay outside the repo, in `~/rf_spectral/circuits`
(ASCO examples are GPL-2, the ngspice examples BSD, the sky130 LNA repo has no licence). The fit of
the unlicensed LNA is kept out of the repo too (`~/rf_spectral/models-not-in-repo`); the pipeline
timings in `results.csv` were taken with its table and are unchanged with the FT8 LNA table. The
files in `models/` are fits measured from simulations of those netlists, not copies of them.
The generated VHDL packages `use rf.rf_signal_pkg` from nvc's `lib/rf`.

## Layout-extracted circuits (ext2xyce.py)

Circuits published only as GDS can be fitted from an extraction. Flow, as run on the
4-stage LNA of efabless mpw-006 slot-008 (Apache-2.0, FT8 receiver, 7-70 MHz):

1. `klayout -b -r $PDK/libs.tech/klayout/lvs/sky130.lvs -rd input=... -rd net_only=true ...`
   (absolute paths; any dummy schematic) -> 704 devices in 3 s.
2. `ext2xyce.py x_ext.cir -o x_xyce.cir --pin '$604=in' ... --report` renames nets, makes
   MOS lines PDK subcircuit instances, turns poly resistors / MiM caps into ideal elements,
   drops dangling dummies (192) and dummy MOS (64), folds fingers (352 -> 32 devices; the
   operating point is unchanged, and HB goes from not finishing in 2 min to ~1 s per point).
   `--report` lists net connectivity; the layout has no pin labels, so pins were found from it
   (gate-only net = input, last stage drain = output, PMOS bulk = supply).
3. A testbench supplies what the cell leaves open (here: DC bias for the first gate through
   an RF-decoupled feedback), then `rffit.py amp ... --hbopts tahb=1`.

Result: 94.4 dB at 7 MHz, 90.1 dB at 28 MHz, 76.7 dB at 70 MHz, input P1dB 8-45 uV peak,
table hold-out about -31 dBc. Xyce two-tone HB does not run on this circuit (transient-assist
fails with close tones, no convergence without it), so there is no independent IM check.
Not extracted: wiring parasitics. `layopt` (mylex) reads the same GDS and gives per-net RC
(SPEF) but recognises only MOS devices, so it cannot replace the KLayout deck here; merging
its RC into the KLayout netlist needs net matching by position and is not done.

OsciBear (ucb-ee290c, sky130) has no RF in its public GDS: SAR ADC, Rocket core and SRAMs only;
its analog sources are on a private Berkeley server.

## Control states

`rffit.py amp ... --state nominal:VDD=1.8 --state lowvdd:VDD=1.5 --state off:VDD=0` fits one
level-dependent transfer function per named state (a set of DC source values) and writes
them all to one `<name>.json`: the block as a small state machine over static controls, each
state a spectral transfer function. Extracted LNA: nominal 94.4 dB, 1.5 V supply 66.7 dB,
off -287 dB (numerical zero) at 7 MHz.
