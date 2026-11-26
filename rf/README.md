# rf/ -- spectral RF signals: GPU benchmarks, transistor-level fitting, and a spectral accelerator for nvc

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

Each `amp` fit ends with two independent checks: the HB gain at the lowest drive level against
Xyce `.ac` (a different code path; warns above 0.1 dB / 1 deg), and with `--twotone` a two-tone
IM prediction against Xyce two-tone HB.  `--hb-direct` switches HB to a dense direct linear
solver (slower; a fallback when the iterative one stalls), `--xyce` picks the simulator.

**Xyce drops MOSFET charge in harmonic balance.**  BSIM3 and BSIM4 compute their charge model
only when `tranopFlag`, `acopFlag` or `transientFlag` (BSIM4 also `dcsweepFlag`) is set, and none
is while the HB system is solved, so in `.hb` a MOSFET keeps only what is computed outside that
block: overlap capacitance for BSIM4, nothing for BSIM3.  Upstream (stock build of 2026-05) and
the kev-cam fork behave the same; BJTs and the level-1 MOSFET are not affected.  One sky130
nfet, W = 22 um: gate capacitance 19 - 33 fF over bias in `.ac`, 10.8 fF (= cgso + cgdo) at
every bias in `.hb`.  Fixed in kev-cam/xyce fb34a1dc (one more term, `|| blockAnalysisFlag_`,
in `N_DEV_MOSFET_B3.C`, `_B3SOI.C`, `_B4p61.C`, `_B4p70.C`, `_B4p82.C`), and the installed
Xyce was rebuilt with it on 2026-11-15 (the previous library is kept beside it as
`libxyce.so.pre-hbfix-2026-11-15`).  With the fix HB equals `.ac` and transient to 0.01 dB /
0.1 deg.  Outside HB nothing changes: BSIM3, BSIMSOI and BSIM4 (4.6.1 / 4.7 / 4.8.2)
regression netlists give byte-identical output.  Of the 154 HB/MPDE netlists in
Xyce_Regression only `HB/mixers/top.cir` uses an affected model, which is why the suite never
showed it; that one's output changes and its gold standard is now stale.  All MOS models below
are fitted with the fix.  What the defect did to the earlier fits: extracted LNA +1.3 dB /
+14 deg at 70 MHz; class-E PA 8.8 dB instead of 11.7; 2.4 GHz LNA 6.6 dB low at 2.3 GHz and
27 deg off at 2.4.

Results (models in `models/`):

| circuit | source | result |
|---|---|---|
| BJT common-emitter amp, 1 MHz | Xyce_Regression/HB/common_emitter_hb.cir | 14.6 dB; two-tone IM3 predicted within 0.1 dB from -163 to -67 dBc |
| BJT Gilbert-cell mixer | Xyce_Regression/HB/gilbert_cell_hbt.cir | 26.4 dB conversion gain; table hold-out -72 dBc; 3 highest RF levels did not converge |
| sky130 2.4 GHz LNA (fit not in repo: source has no licence) | ~/rf_spectral/circuits/chinmay-sky130-lna-2g4/lna_xyce_fit.cir | 24.9 dB at 2.4 GHz (33.3 dB at 2.35), P1dB(in) 109 mV pk; HB = .ac; two-tone at 2 MHz spacing: IM3 within 0.6 dB from -102 to -16 dBc (64 mV/tone), 1.8 dB off at 88 mV |
| class-E PA, 850 MHz, BSIM3 | ~/rf_spectral/circuits/asco-classe-pa/classE_xyce.cir | `--hbopts tahb=2 --harm 15 --src-dc 1.0`; 11.7 dB small-signal, P1dB(in) 268 mV pk; HB = .ac; two-tone at 2 MHz spacing runs at all 17 levels (20 - 457 mV/tone): tone within 0.01 dB, IM3 within 0.5 dB from -73 to -13 dBc |
| extracted 4-stage LNA, 7 - 70 MHz | see "Layout-extracted circuits" | 94.4 dB at 7 MHz drawn; with wiring parasitics 0.5 dB less at 28 MHz, 1.6 dB less at 70 MHz |

The VHDL package carries the fitted table (resampled to 65 points uniform in ln|a|, linear
interpolation, held at the end values outside the fitted range), not the polynomial: on the
extracted FT8 LNA the polynomial was 10 dB low at small signal, the table package matches the
fit to 0.02 dB in nvc.  With `--state` one package holds every state and
`<name>_apply(s, st)` takes the control state (`ST_NOMINAL`, ...).  `rffit.py vhdl model.json`
regenerates a package from a saved fit without re-running Xyce.

Known limits: the VHDL model is fundamental-tone only (harmonics stay in the .json);
the model uses the nearest fitted
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
   drops dangling dummies (136 R/C, 64 MOS), folds fingers (352 -> 32 devices; the operating
   point is unchanged, and HB goes from not finishing in 2 min to about 1 s per point), and
   gives every net without a DC path a leak to ground (`--leak`, 1 Gohm; here the four mid
   nodes of the series-stacked supply decoupling capacitors).
   `--report` lists net connectivity; the layout has no pin labels, so pins were found from it
   (gate-only net = input, last stage drain = output, PMOS bulk = supply).
3. A testbench supplies what the cell leaves open (here: DC bias for the first gate through
   an RF-decoupled feedback), then `rffit.py amp ... --hbopts tahb=1`.

Result, drawn devices only (`models/ft8_lna4_ext`): 94.36 / 93.29 / 89.63 / 82.19 / 75.39 dB
at 7 / 14 / 28 / 50 / 70 MHz, equal to `.ac` and to a transient run; input P1dB 8 - 51 uV
peak; table hold-out about -31 dBc.  Xyce two-tone HB still fails on this circuit (its
transient-assisted start-up aborts on every level tried), so there is no IM check.

A net with no DC path makes the HB matrix singular, and Xyce does not say so: the iterative
solver returns scattered, non-monotonic points or stalls, the direct one fails only when the
pivot is exactly zero.  That is what the leak resistors are for.  (The decoupling capacitors
came into the netlist with a fix made here: ext2xyce used to take the wrong two nodes of the
three-terminal finger capacitors -- plate and floating substrate instead of the two plates --
so all 56 were dropped as dangling.)

### Wiring parasitics (layrc.py)

The KLayout deck gives devices but no wiring R/C; mylex's `layopt` gives per-net C and a
resistor mesh over the wiring rectangles but knows only MOS devices.  `layrc.py` joins them:

4. `layrc.py x.gds x.lvsdb -o x_rc.json` -- runs layopt on the GDS, matches its nets to
   KLayout's by looking every contact/via of a KLayout net up in layopt's shapes, locates each
   device terminal on those shapes, and writes per net the wiring C (area + fringe) and per
   terminal a resistance: the exact terminal-to-terminal resistances of the mesh (sparse
   solve) reduced to a star by non-negative least squares.  3 s on this cell; all 369 layopt
   nets map to a KLayout net (several to one where KLayout connects through the substrate,
   never one to several); star fit within 3.4 % rms of the exact resistances.
5. `ext2xyce.py ... --rc x_rc.json [--rc-mode c|r|rc] [--rmin ohm]` inserts them: one C per
   net to ground, one R per device terminal (legs of folded fingers in parallel).  Here 400
   resistors (1.1 - 145 ohm, median 21) and 96 capacitors: 0.56 pF on signal nets, 5.0 pF on
   the supplies and decoupling nodes.  ext2xyce warns if the netlist and the rc file disagree
   on device ids or terminal order (KLayout writes MOS nodes as S G D B; checked here: all
   2520 terminals of 704 devices map one-to-one).

layopt needed two fixes for analog layout (in mylex, with a test): wire under a resistor
marker (66/13 ... 72/13) is cut out instead of conducting, and a via over a MiM plate (capm,
cap2m) lands on the plate rather than on the metal below.  Before that it had 159 nets where
there are 369.  The 437 sky130_fd_sc_hd cells and the kestrel PLL contain none of these
layers and extract exactly as before.  The LVS deck in turn leaves via4 inside
finger-capacitor markers unconnected (224 one-shape nets with no device); layrc ignores those.

Effect on the LNA (`models/ft8_lna4_rc` is the fit with R and C), small-signal gain in dB:

| | drawn | + wiring C | + wiring R and C |
|---|---|---|---|
| 7 MHz | 94.36 | 94.32 | 94.53 |
| 28 MHz | 89.63 | 89.18 | 89.14 |
| 70 MHz | 75.39 | 74.23 | 73.78 |
| 100 MHz (.ac) | 66.28 | 64.89 | 64.30 |
| 1 GHz (.ac) | -13.62 | -15.14 | -15.96 |

The -3 dB bandwidth goes from 22 to 20 MHz.  Compression is set by the output swing and does
not move (gain at 1 mV in, 70 MHz: 54.0 drawn, 53.9 with R and C); input P1dB with R and C is
8 - 60 uV.  The capacitance does most of it; the resistance adds 0.45 dB at 70 MHz and costs
HB time (600 unknowns instead of 200: 100 s instead of 40 s for 165 points).

Limits: C is lumped to ground at the net node (no coupling between nets, and the plates of
the finger capacitors are counted as ordinary wire, which overstates the decoupling nets);
gate resistance is lumped at the centre of the gate poly; external connections attach at the
net node, since this layout has no pin shapes; R/C values are layopt's analytic
sheet/area/fringe numbers, not sign-off; no reference extractor (magic, OpenRCX) is installed
here to compare against.

OsciBear (ucb-ee290c, sky130) has no RF in its public GDS: SAR ADC, Rocket core and SRAMs only;
its analog sources are on a private Berkeley server.

## ad9361/ -- AD9361 behavioural model; the AN-2597 link in nvc (--std=2040, spectral events)

A model of the Analog Devices AD9361 transceiver at its data port, driven from software rather than
RTL, and the drone / controller link of ADI's AN-2597 ("An OFDM-Based HDL Reference Modem Using the
AD936x RF Transceivers": ADRV9361-Z7035 at each end, 5 / 10 / 20 MHz channels at 2.4 and 5.2 GHz,
BPSK to 64-QAM) built from it.  The model that runs is VHDL in nvc's `--std=2040` mode; a Python
model of the same chip is the reference it is checked against.  For a reader who knows the AD9361 and
the app note: [ad9361/AN-2597.md](ad9361/AN-2597.md) (what is reproduced and what is not, every number
with its source, results for both bands and the three channel widths, and what to ask ADI).

    ad9361.py check                  the Python model measured the way the data sheet measures the chip
    ad9361_vhdl.py emit              write ad9361_pkg.vhd from the tables in ad9361.py
    ad9361_vhdl.py check --nvc N     compile the package, run tb_ad9361.vhd, compare with ad9361.py
    an2597_nvc.py --nvc N --compare  the link in nvc, beside the link budget and the Python model
    an2597_nvc.py --nvc N --accel    the same, its RF path moved out to the spectral accelerator (accel/)
    radar_nvc.py --nvc N -n 8 --both a phased-array radar in nvc, then with the accelerator
    an2597_link.py                   the same link in Python alone (time domain, sample by sample)

**What is modelled** (`ad9361.py`, same numbers and maths in `ad9361_pkg.vhd`): transmit: 12-bit DAC
word, analog baseband filters, attenuator (0.25 dB steps), third-order compression set by OIP3, carrier
leakage (the data sheet's 0 dB and 40 dB points), noise floor, LO phase noise and a residual that brings
the EVM to the data sheet's; receive: noise figure, third-order compression (input intercept rising as
gain falls), filters, quadrature gain and phase error, gain in 1 dB steps, 12-bit ADC with clipping, the
same EVM treatment, LO leakage out of the RX pin, and three gain modes (manual, slow attack, a
fast-attack burst AGC with acquire / stronger-signal / energy-lost).  Controls are the ones a program
sets through the Linux IIO driver (pyadi-iio's names: `rx_lo`, `sample_rate`, `gain_control_mode_chan0`,
`tx()`, `rx()` ...); there is no SPI register map and no LVDS/CMOS port timing.

**Where the numbers come from.**  `ad9361.py spec` prints every value with its status.  The data sheet
PDF could not be opened from the machine this was written on (analog.com and the distributor copies
refused or timed out), so the 'ds' values were read from published text of Table 1 returned by web
searches (Rev. F / G copies), not off the page: gain, NF, IIP3, EVM, LO leakage, output power, OIP3,
TX noise, carrier leakage, isolation, ranges.  'rec' values are from recollection and unchecked: the
integrated LO phase noise (0.13 / 0.37 / 0.59 deg), TX EVM and 40 dB carrier leakage at 5.5 GHz, the
sample-rate limits, the filter-corner multipliers.  ADC full scale (0.625 V peak, +5.9 dBm at 0 dB gain)
is from an EngineerZone staff reply.  What the data sheet gives only as plots (NF and IIP3 against gain,
AGC timing) is the model's own assumption, listed in `MODEL`.  Check all of it against Rev. G before
relying on a number.

`ad9361.py check`: every data sheet figure measured back from the model (two-tone tests, full-scale
tone, noise with no input, EVM of a modulated signal) is within 0.2 dB at 800 MHz, 2.4 GHz and 5.5 GHz.
`ad9361_vhdl.py check`: 309 values from `tb_ad9361.vhd` in nvc against Python -- the noise-free paths
bit for bit (RX codes equal, TX envelopes to 6e-16), Monte Carlo NF / noise / EVM / leakage within 0.2 dB,
and the chip's constants as the accelerator is given them (two control states, 49 values each).

**Spectral event-driven VHDL** (all `--std=2040`):

| file | what |
|---|---|
| `rf_spectrum_pkg.vhd` | `rf_spectrum`: 64 lines (complex amplitude per frequency, both polarisations) around a carrier, one value per event; Friis per line, carrier-offset regridding, `arena_resolve` (antennas, platforms whose antennas do not hear each other, point scatterers) |
| `ad9361_pkg.vhd` | generated: data sheet tables, per-sample transmit and receive procedures |
| `ad9361_spectral_pkg.vhd` | one event through the chip: filters on the lines, everything non-linear on the 64 samples of the event (DAC/ADC words, compression, AGC changing gain part-way) |
| `ad9361.vhd` | the chip: RF pins `tx1`, `rx1` (std_logic nets, payload on `'driver` / `'other`), software side `cfg`, `tx_data`, `rx_data` (one symbol period per event) |
| `rf_spec_antenna.vhd` | antenna: a driver and a receiver in the arena, with a position port (it can move) and a platform |
| `rf_spec_scatterer.vhd` | a point target in the arena: radar cross-section, a position port (it can move: Doppler) |
| `arena_resolver.py` | writes the resolver network: wires between pins and feeds, the arena -- each antenna's `air'other` is the sum of every other antenna's `air'driver` through free space between their positions, and of every antenna's signal off every scatterer -- and the bridge to the accelerator |
| `ofdm_soft_pkg.vhd` | software OFDM modem on spectra (802.11a/g numerology, no coding): training, data, carrier-offset estimate and removal, channel estimate, pilots |
| `an2597_link.vhd` | the link: two chips, four antennas, and two processes as the drone's and the controller's software; the drone flies out and sends packets, the controller's fast AGC and modem receive them |
| `phased_radar.vhd` | a phased-array radar: n chips on one LO, n transmit and n receive elements, three moving targets, and the radar as one software process (focused beams, range from the lines, speed pulse to pulse, bearing across the elements) |
| `accel/spectral_accel_pkg.vhd` | nvc's side of the spectral accelerator (next section but one) |

An OFDM packet is 2 short-training, 2 long-training and N data events (plus 2 idle), one per 4 us symbol,
instead of 80 samples each.  Linear blocks scale lines; the chip goes through the event's time domain
for what is not linear; a carrier offset between two radios is a regrid (exact for the event) plus the
offset's phase at the event's start.

Result at 2.437 GHz, 20 MHz channel, bare chips (full-scale tone 7.5 dBm, packets 12 dB under: -4.5 dBm
average), 2 dBi antennas, +1.0 / -1.5 ppm references (6.1 kHz carrier offset), 10 packets of 20 symbols
per point; "budget" is thermal noise in the used subcarriers plus the two EVM floors, times 1.5 for a
two-symbol channel estimate:

| distance | Prx | AGC gain | budget EVM | nvc EVM (64-QAM) | Python EVM | uncoded BER 16-QAM / 64-QAM (nvc) |
|---|---|---|---|---|---|---|
| 1 m | -40.7 dBm | 33.9 dB | -36.0 | -36.1 | -36.2 | 0 / 0 |
| 10 m | -60.7 | 53.9 | -33.2 | -33.2 | -33.4 | 0 / 0 |
| 30 m | -70.2 | 63.9 | -26.4 | -26.3 | -26.4 | 0 / 0 |
| 100 m | -80.7 | 72.9 (max) | -16.3 | -16.1 | -16.4 | 2.0e-3 / 4.4e-2 |
| 300 m | -90.2 | 72.9 | -6.8 | -5.9 | -6.7 | 0.12 / 0.22 |

All four modulations are within 0.9 dB of the budget from 1 m to 300 m in nvc, and within 0.5 dB of the
Python time-domain model up to 100 m (0.8 dB at 300 m); the AGC settles at the same gain in both.  At
1 km (SNR -3 dB) neither receives; the spectral detector still fires on about half the packets, the
time-domain one on none.  5.2 GHz agrees the same way (-32.5 dB at 1 m, -18.4 at 30 m).  With an ideal
20 dB PA and a 15 dB / 1.5 dB-NF LNA at each end (Python): -27.6 dB at 300 m, -17.7 at 1 km.

Speed: nvc 0.008 x real time (3.0 s for 6240 symbol events, 25 ms of air time, two radios); the same
run with its RF path on the spectral accelerator 0.048 x (`accel/`, below); Python time domain 0.07 -
0.12 x; a standalone GPU program that takes whole windows of events 18 - 47 x (`gpu/`, below).  nvc is
not tuned: the per-sample procedures recompute their constants (band interpolation, dB conversions) on
every sample, and the arena regrids the receivers' LO leakage onto the transmitter's grid for every
antenna on every event.  A position change is not an event (it used to re-resolve the arena): an antenna
or target that moves changes what the next event sees.

**Things learned about nvc `--std=2040`** (nvc 1.19-devel r619, da8ece172):
- A pin's `'driver` / `'other` signals exist only in a component that mentions both, and take their type
  from a typed variable (`v := p'other; p'driver := v;`); a function result or an attribute used as an
  argument does not type them.
- An event needs a changed value: two equal spectra in a row are no event, hence `rf_spectrum.seq`;
  `seq = 0` marks a net never written (its reals are uninitialised and must not be read).
- A frequency-domain filter has to be applied on the grid the signal is periodic on (the sender's)
  before a carrier offset is applied; filtering after it wraps the filter's transient round a block
  whose ends differ by the offset's phase (it cost 4 dB of EVM at 6 kHz offset until fixed).
- nvc crashes (SIGSEGV in `async_fast_driver` / `split_nexus_slow`, a signal assignment landing on a
  neighbouring signal's nexus) once a process that allocates and deposits to a `'driver` has run some
  tens of times.  `NVC_NO_EVAL_ARENA=1` avoids it (so do `NVC_NO_STITCH=1` and `NVC_SCOPE_SCRATCH=1`);
  `an2597_nvc.py` sets it, and `an2597_nvc.py --eval-arena` reproduces the crash.  Not fixed in nvc.
- A process sensitive only to a real signal and comparing it with a constant fails at elaboration
  ("cmp trigger right argument must be integer").
- Foreign code (`VHPIDIRECT`, library given with `--load`): the subprogram needs a body in VHDL even
  though it is never run; INTEGER is 64 bits in this mode and an `out real` scalar does not arrive, so
  the accelerator's interface is reals and `real_vector`s only (arrays are a pointer and a length).
  `std.env` here is the 2008 one: no `getenv`.  Signals declared in a package, resolved ones driven from
  many instances included, and external names through `for ... generate` (`.top.dut.g(3).chip.tx1.driver`)
  work.  A process with megabytes of variables needs `-H` (the heap is 16 MB by default).

Limits: one receive and one transmit channel per chip in the VHDL (the Python model has both and their
isolation); sample-clock offset is not modelled (the reference error moves the LOs only); propagation
delay is each line's phase, not a delay of the event (fine while it is shorter than the guard interval);
the digital FIR / half-band filters are not modelled, only the analog baseband response; no coding in the
modem, so no packet error rate; AN-2597's own modem (HT-mixed preamble, convolutional coding, 2x2 STBC)
is not reproduced -- the app note itself could not be opened, its parameters are from ADI's wiki page.

### ad9361/accel/ -- the spectral accelerator: the RF path's data and processing out of nvc, a thread per frequency line

nvc's accelerators move a subtree's data and processing out of the simulator and can pull them back at
a settled point, to debug or to suspend (`--accel`: a digital subtree as a compiled state machine,
demoted back to interpretation on request).  This is that for the spectral RF path.  The design is the
same VHDL; what moves is the data on its RF nets -- one spectrum per net per event, an array of complex
lines -- and the processing of the chips' transmit and receive paths, the antennas and the arena.  On
the accelerator every frequency line is a thread: a block of K threads is one element's spectrum, the
linear parts (filters, free space, the arena's sums) are done by each line's thread on its own, and
the chip's non-linear parts by the same K threads as the K samples of the event (an in-block
transform between the two, a parallel prefix for the LO phase noise, the AGC stepping sub-block by
sub-block).  Events are processed one at a time in the simulator's order, so the chips' state (AGC,
phase noise) carries from event to event exactly as the VHDL's does.

    smak                                         (or make) builds accel/libspectral_accel.so
    an2597_nvc.py --nvc N --accel                the AN-2597 link, RF path on the accelerator
    an2597_nvc.py --nvc N --accel --schedule 0:out,6ms:in,12.5ms:out,19ms:in     out, back, out, back
    radar_nvc.py --nvc N -n 64 --accel           the phased-array radar, 64 + 64 elements
    accel/spectral_accel.py check | radar | mimo the library without a simulator (ctypes)

**How it attaches.**  nvc is not changed: `libspectral_accel.so` is loaded with `--load` and called
through `VHPIDIRECT` subprograms (`accel/spectral_accel_pkg.vhd`).  Compile `accel/spectral_accel_on.vhd`
(or `_off.vhd`: no library needed, nothing is called) before the package.  Each chip, antenna and
scatterer registers itself; the bridge process that `arena_resolver.py` writes into the resolver hands
over the wiring and the arena, asks the accelerator whether it admits the design (it declines, and the
design stays in nvc, when a wire is not one chip pin to one antenna feed, an antenna has a polarisation
angle, or the chips do not share a sample rate), and drives the package signal `sa_mode` from
`SPECTRAL_ACCEL_SCHEDULE` (default `0:out`).  The chips' constants in their control state reach the
accelerator as one vector from `ad9361_pkg.ad9361_accel_params`, so both sides compute from the same
tables.

**Out and back.**  When `sa_mode` goes to `SA_ON_ACCEL` each chip process pushes what it carries from
event to event (LO phase, carrier-leakage phase, AGC state) and the spectrum on its TX pin.  While out,
a chip's transmitter only hands the frame at its data port over (`sa_tx`), its receiver only collects
what the accelerator delivers (`sa_rx`; the first one after new frames runs the event), and the nets in
nvc stand still: no antenna or resolver process runs.  On the way back (`SA_RESTORING`, then
`SA_IN_NVC`) the chips pull their state and put the pulled-back spectra on their pins, the VHDL arena
resolves once so every net shows what the accelerator last had, and the receivers do not treat that as
a new event.  A switch asked for time t happens 1 fs after t.  `spectral_accel.py check` shows the
pulled-back state is everything: pull after 97 events, overwrite the accelerator's copy, push back, and
the next 143 events are bit-identical to an uninterrupted run (and differ if the state is not put
back).  In nvc, `--schedule 0:out,6.001ms:in,12.5ms:out,19ms:in` on the link (switches in the middle
of packets): 3109 of 6240 events on the accelerator, every packet still found, EVM as before.

**Checks.**  The AN-2597 link (table above), 64-QAM EVM in dB at 1 / 10 / 30 / 100 / 300 m: budget
-36.0 / -33.2 / -26.4 / -16.3 / -6.8; nvc alone -36.1 / -33.2 / -26.3 / -16.1 / -5.9; nvc with the
accelerator within 1.1 dB of the budget for all four modulations (nvc alone: 0.9), the AGC at the same gains (33.9,
43.9, 53.9, 63.9, 72.9 dB), bit error rates alike.  The device against the same stages run as CPU loops
with the same random numbers (`SPECTRAL_ACCEL_DEVICE=cpu`), every event of the sweep: no gain differs,
received lines within one ADC word in one sample.  `spectral_stages.inc` is one text compiled both
ways.

**A phased-array radar** (`phased_radar.vhd`, `radar_nvc.py`): n transmit and n receive elements half
a wavelength apart on one LO, the receive array 3 m above the transmit array and hearing it directly
(the leakage and its phase noise are what limit the small arrays), three targets (10 / 30 / 100 m2 at
120 / 210 / 160 m, moving at -40 / 75 / 120 m/s), 64 OFDM pulses of 64 lines per look, 100 us apart.
The radar software focuses both beams on the target's cell, divides the echoes by the pulse, the AGC
gain and its chips' known filter responses, and reads range off the lines, speed off the pulses and
bearing off the elements.  From 8 + 8 elements up, nvc alone and nvc with the accelerator find the same
three targets (range within 2 m, speed within a Doppler cell, bearing within a fraction of the beam);
at 4 + 4 the leakage's noise hides one or both of the first two targets in either.  Steady-state time
per pulse (each pulse is 2 n events at the chips):

| elements | nvc alone | nvc + accelerator | of which on the GPU |
|---|---|---|---|
| 4 + 4 | 1.3 ms | 0.22 ms | 0.12 ms |
| 8 + 8 | 2.9 | 0.27 | 0.12 |
| 16 + 16 | 7.3 | 0.41 | 0.14 |
| 32 + 32 | 21 | 0.80 | 0.19 |
| 64 + 64 | 71 | 1.7 | 0.28 |
| 128 + 128 | - | 3.2 | 0.40 |
| 256 + 256 | - | 6.7 | 0.67 |

So 64 + 64 elements run about 43 times faster with the RF path out, and what is left is nvc's own: one
process activation and one 64-line frame per element at the data ports, and the radar's software.

**The accelerator alone** (`spectral_accel.py radar`, `mimo`; RTX 3070 Ti Laptop GPU, one event per
call, 64 lines, time from frames in to frames out):

| elements | arrays hear each other (N x N pairs) | arrays isolated, 4 targets | isolated, targets moving every event |
|---|---|---|---|
| 8 + 8 | 0.062 ms | 0.054 ms | 0.082 ms |
| 64 + 64 | 0.10 | 0.072 | 0.10 |
| 256 + 256 | 0.35 | 0.17 | 0.21 |
| 512 + 512 | 0.79 | 0.32 | 0.39 |

| base-station antennas, 8 users each on its own LO | 16 | 64 | 256 | 1024 | 4096 |
|---|---|---|---|---|---|
| ms per event | 0.062 | 0.067 | 0.10 | 0.35 | 2.5 |

512 + 512 elements all hearing each other is 16.8 million line-pair terms per event, each with its own
phase, in 0.79 ms; the same stages as CPU loops on 20 threads take 6.2 ms at 256 + 256 (GPU 0.35).
With 256 lines per event: 0.082 / 0.18 / 0.79 ms at 8 / 64 / 256 elements a side.

**What this is in real time.**  A pulsed radar at a 1 ms repetition interval is real time on the
accelerator alone at every size in the table, and under nvc up to 32 + 32 elements (1250 pulses a
second); at 100 us, alone up to 32 + 32 (64 + 64 takes 102 us).  Continuous 20 MSPS OFDM (an event
every 4 us) is not: one event per call costs about 45 us before any arithmetic (two kernel launches and
three copies), so the
two-radio link runs at 0.09 x on the accelerator alone and 0.048 x under nvc.  The earlier `gpu/`
program below reaches 18 - 47 x on that link by taking thousands of events per launch; doing that
here means the software handing over and collecting buffers of frames while the design is out, which
is the next step, together with moving the per-element data-port traffic out of nvc.

Limits and differences from the VHDL: the random numbers are the accelerator's own (the two agree
statistically, not sample by sample); single precision on the device, geometry in double; with several
carriers on the air each group of transmitters is filtered on its own grid before the carrier offset
(the VHDL arena first puts everything on the first transmitter's grid; the same when one carrier
transmits); the receivers' LO leakage is not scattered off targets; one polarisation; switches come
from the environment's schedule only (nothing in VHDL can ask for one yet); while the design is out a
waveform dump of its nets shows them standing still.

### ad9361/gpu/ -- an earlier experiment: whole windows of events in one launch

Not an nvc accelerator: a standalone program with its own copy of the chip model, one thread per radio
and symbol event, written before `accel/`.  It stays as the measure of what batching events buys.

`smak` (or make) builds `ad9361_gpu`; `an2597_gpu.py` runs the link on it, checks it and times it.
`ad9361_kernels.h` is the chip's event model once more (transmit; receive before the gain; gain and ADC),
compiled for the device -- one thread per radio and symbol event, a window of events per launch -- and for
the host, with the same counter-based random numbers, so the two are compared event by event.  The
scenario (each radio's constants in its control state, the coupling per pair, the symbols to send) is
written by Python from the tables in `ad9361.py`.  Per window on the device: transmit; arena (each
receiver sums the transmitters it hears, with their carrier offsets) and receiver front; the AGC state
machines over per-sub-block power and peak, sequential per radio, on the host; gain and ADC.

Two things differ from the VHDL, both to run a window's symbols in parallel: LO phase noise starts each
event from a fresh stationary value (no correlation from one symbol to the next), and the AGC decides
from the power the ADC would measure without compression (the same decisions unless a sub-block clips,
where both step down alike).

Check, AN-2597 link as above (10 packets per modulation and distance): EVM within 0.6 dB of the budget
from 1 m to 300 m (-36.3 / -33.0 / -26.2 / -16.1 / -6.4 dB for 64-QAM at 1 / 10 / 30 / 100 / 300 m), the
AGC at the same gains as nvc and Python (33.9, 43.9, 53.9, 63.9, 72.9 dB), bit error rates alike; GPU
against the CPU build of the same code: no gain differs, and the received lines differ by at most one
ADC code in one sample of an event.

Real-time factor (air time of a window / wall time), RTX 3070 Ti Laptop GPU, float, 20 MSPS, 4 us
symbols; "held" leaves the gains as they are (no AGC round trip to the host); CPU is the same code on
the i9-12900H:

| radios | window (air time) | GPU with AGC | GPU, gains held | CPU 1 thread | CPU 20 threads |
|---|---|---|---|---|---|
| 2 (the link: one sends, one receives) | 0.42 ms | 1.2 | 1.5 | 0.57 | 0.47 |
| 2 | 6.7 ms | 18 | 26 | 0.53 | 2.1 |
| 2 | 27 ms | 30 | 48 | 0.55 | 2.5 |
| 2 | 107 ms | 38 | 55 | 0.54 | 2.3 |
| 2 | 426 ms | 47 | 62 | 0.55 | 2.3 |
| 4, all sending and receiving, all hearing each other | 107 ms | 12 | 16 | 0.12 | 0.67 |
| 8 | 107 ms | 4.8 | 5.5 | 0.046 | 0.28 |
| 16 | 107 ms | 1.6 | 1.7 | 0.015 | 0.08 |
| 32 | 107 ms | 0.47 | 0.50 | 0.005 | 0.025 |

So the two-radio link runs 18 - 47 times faster than real time on the GPU once a window holds a few
milliseconds of air time (about 0.3 ms of fixed cost per window), against 0.008 for the VHDL in nvc and
2.3 for the same code on 20 CPU threads.  The all-pairs arena is what limits more radios: each receiver
does one inverse FFT and one phase ramp per transmitter it hears, so cost grows with the square of the
number of radios and real time is lost near 20.  Not tried: summing transmitters that share a carrier
before the transform, distance culling, double precision.

## cc2652r/ -- TI CC2652R Bluetooth LE radio, with the Bluetooth side from the Core Specification

A model of the CC2652R's 2.4 GHz radio in its four Bluetooth LE modes, the counterpart of ad9361/ for a
chip whose software never sees a sample: it hands the radio a packet and is handed packets back.  The
data sheet stops at the antenna pin; modulation, packet formats and what a program does with the chip
are the Bluetooth Core Specification's, so the model is in three layers.  The Python model is the
reference; the VHDL for nvc's spectral events, in the arena and federated, follows below.

    ble_phy.py check     the Bluetooth physical layer against the specification's own sample data
    cc2652r.py check     the radio measured the way the data sheet measures the chip, beside the data sheet
    cc2652r.py fit       adjust the radio to the data sheet (writes cc2652r_fit.py; about 20 minutes a pass)
    cc2652r.py spec      the data sheet tables, the assumptions, the fitted values
    ble_host.py range    packet error rate against distance, two controllers in Direct Test Mode
    ble_host.py scan     an advertiser, an active scanner and a neighbour advertising beside them

| file | what | from |
|---|---|---|
| `ble_phy.py` | GFSK, the 40 channels, packets of LE 1M / 2M / Coded S=2 and S=8, whitening, CRC, the Coded PHY's convolutional code and its Viterbi decoder, a sequence detector for the uncoded PHYs | Core Specification 6.1, Vol 6 |
| `cc2652r.py` | the radio: symbols to an envelope at the set power; envelope through noise, a third-order front end, AGC, the channel filter, the detector and packet search to packets with CRC result and RSSI | data sheet SWRS207J, 8.9 - 8.11 |
| `cc2652r_fit.py` | per PHY: noise figure, input intercept, the channel filter's rejection at each offset, how far the detector allows for neighbouring symbols | fitted |
| `ble_host.py` | a controller round the radio, driven by HCI commands (legacy advertising, passive and active scanning, Direct Test Mode), and an arena of controllers in free space | Core Specification, Vol 4 Part E, Vol 6 Part B |

**Where the numbers come from.**  The data sheet PDF (Rev. J) was fetched and its tables read off the
page: sensitivity, co-channel rejection, selectivity at every offset, intermodulation and out-of-band
blocking for each PHY, output power and its range, RSSI range.  The specification's HTML edition was
read for Part A, Part B up to 2.4 and Part C; the CRC polynomial, the whitening register, the FEC
polynomials and pattern mapper, T_IFS and the advertising and HCI timing rules are from recollection
(the text would not load), and `ble_phy.py check` reproduces Part C's sample data bit for bit with them:
five whitening sequences, a complete advertising packet with its CRC, the encoder's output for the
access address, the reference packet's CRC and durations (15 of 15).  What the data sheet does not give
is `MODEL` in cc2652r.py: the AGC threshold, the range of what follows the gain, the filter's passband,
transmit power in 1 dB steps, nothing added to the transmitted signal (no phase noise or spectrum
figures are given).  The noise figure the fit arrives at (4.6 to 6.8 dB by PHY) and the input intercept
(-28 dBm; -21 dBm for LE 2M) are what this detector needs to give the data sheet's figures, not
measurements of the chip.

`cc2652r.py check` (BER 1e-3 by bisection, 300,000 bits a point, a seed the fit did not use; the
interferer 7.3 kHz off its nominal offset and not symbol-aligned, without which the result depends on
its phase by 2 dB): sensitivity -105.1 / -100.2 / -97.0 / -91.1 dBm (data sheet -105 / -100 / -97 /
-91), co-channel within 0.5 dB, intermodulation within 0.2 dB, blocking within 0.1 dB, selectivity
within 0.5 dB at 33 of 40 offsets.  The other seven are all on the good side: 0.6 to 0.9 dB at
+-2 MHz for LE 1M and -4 MHz for LE 2M, and 0.8 to 2.7 dB at +-2 MHz for the Coded PHY, where the fit
does not settle.  No errors with the wanted signal at +5 dBm.

`ble_host.py range` (LE 1M, 0 dBm, isotropic antennas, 37-octet test packets, 40 a point): none lost
at 10 m and 300 m (-89.7 dBm), 25 % at 700 m (-97.1 dBm; BER 1e-3 loses 29 % of such packets), 87 % at
1 km; the RSSI the receiver reports is within 0.4 dB of the link budget.  `ble_host.py scan`, 2 s:
the scanner reports 9 ADV_IND of the 57 sent (it listens to one channel in three, half the time), asks
9 times and gets 9 scan responses, and reports 39 of a neighbour's 240 non-connectable advertisements.

Limits: no connections (CONNECT_IND is ignored), extended or directed advertising, scanner backoff,
filter policies or privacy; packets are found by correlation on preamble and access address with one
frequency-offset estimate per packet, and the data sheet's frequency and data-rate error tolerances
are not checked; propagation delay is left out of the Python arena; IEEE 802.15.4 is not modelled.

### cc2652r/ in nvc (--std=2040, spectral events), in the arena and federated

    ble_nvc.py selftest              tb_cc2652r: packets against ble_phy.py; a packet of each PHY chip to chip
    ble_nvc.py range [--compare]     Direct Test Mode range in nvc; --compare runs ble_host.py beside it
    ble_nvc.py scan                  the beacon, the neighbour and the active scanner in nvc
    ble_nvc.py connect               the tester (a central and its host) puts a peripheral through its tests
    ... --fed                        the same as two simulations sharing the arena; must report the same lines
    ... --dut btle | btle-tail       the device's radio is an open baseband from Verilog (below), not the CC2652R
    ... --dut bmc | bmc-txend        ... or the Berkeley baseband-modem, from Chisel (below; slow, give --heap 2g)
    ... --accel                      nvc --accel: the translated design as one compiled model (below; 18 times faster)
    (--nvc-build or NB: an nvc build with the arena support, as for ad9361/an2597_arena.sh; global options
    such as --fed and --dut go before the subcommand)

| file | what |
|---|---|
| `cc2652r_vhdl.py` | writes `cc2652r_pkg.vhd`: the filter taps of each PHY, symbol timing, detector taps, the modulator's pulse and the scalars, all worked out by cc2652r.py; and reference packets for the bench |
| `ble_phy_pkg.vhd` | ble_phy.py in VHDL: packets of the four PHYs, whitening, CRC, the convolutional code, the sequence detector and the Viterbi decoder |
| `cc2652r_spectral_pkg.vhd`, `cc2652r.vhd` | the chip: one RF pin (`'driver` / `'other`, an rf_spectrum), `cfg`, a packet to send, packets received |
| `rf_spec_antenna_td.vhd` | the antenna, its air pin an `rf_air_td` |
| `ble_controller.vhd` | the link layer as the chip's software: test transmitter and receiver, advertiser, scanner, peripheral |
| `ble_ll_pkg.vhd` | what a connection needs: CONNECT_IND, channel selection algorithm #1, data PDUs and their acknowledgement, L2CAP framing |
| `ble_tester.vhd` | the tester: a central and the little of a host above it that tests a peripheral over the air |
| `btle_phy_radio.vhd`, `btle_phy_radio_pkg.vhd`, `btle_phy_radio_none.vhd` | a device under test from outside: the open BTLE baseband (translated Verilog) behind an RF front end, with the chip's ports; its transmit latency; the empty stand-in when it is not asked for |
| `ucb_bmc_radio.vhd`, `ucb_bmc_radio_pkg.vhd`, `ucb_bmc_radio_none.vhd` | another one: the Berkeley baseband-modem (translated Verilog from Chisel) behind an RF front end and a host, with the chip's ports; its transmit latency; the empty stand-in |
| `ucb_bmc/` | `emit.sh`: fetches the baseband-modem, the DMA it uses and rocket-chip and has sbt write `BMC.v` (`build.sbt`, `src/`: the top to emit and the one object the DMA takes from testchipip); `replay.v`: a trace of the translated design's pins put to the Verilog |
| `ble_link.vhd`, `tb_cc2652r.vhd`, `tb_btle_phy_radio.vhd`, `tb_ucb_bmc_radio.vhd` | the two scenarios of ble_host.py and the tester's; the self-check benches |

**How a GFSK signal is a spectral event.**  An OFDM symbol is periodic over its event; a Bluetooth
packet is not, so a transmission is a run of consecutive events, each the spectrum of the next 64
samples (2 us at the model's 32 MHz; lines 500 kHz apart).  That needed one thing the AD9361 arena does
not have, added to rf_spectrum_pkg as the subtype `rf_air_td` (its own band, `ism2g4_td`): in an
`rf_air` arena a path's delay is a phase on every line, which rotates the samples of an event round on
themselves (harmless inside a cyclic prefix, wrong here); in an `rf_air_td` arena the delay is in time
only (the generated resolver hears every antenna as it was distance / c ago) and a path is one complex
gain.  Carriers stay on the channel raster and each chip puts its crystal's error in its own samples,
so signals on different channels add line by line with no time reference.  The receiver sleeps until
something arrives, then reads its pin every 2 us from half an event after the first arrival, and runs
the same chain as cc2652r.py on the samples as they come: noise, compression, channel filter,
discriminator, correlation for preamble and access address, header, packet.  It reports when the
packet ended at the pin, which is what the link layer times T_IFS from.

Differences from cc2652r.py: one sample rate for all PHYs (cc2652r.py's `check` runs the 1 Msym/s PHYs
at 16 MHz; at 32 MHz its sensitivity, co-channel and +-1 to 3 MHz selectivity figures are within
0.5 dB of those); the AGC follows each event's power; a second signal with another path delay is
taken as it stands at the receiver's reads (under one event of timing error); signals more than
16 MHz from the receiver's channel are not seen (no blocking by them); the receiver keeps 2^17
discriminator samples (generic `ring_log2`), enough for any uncoded packet and Coded packets of up
to 229 (S=2) or 51 (S=8) octets.

Results (WSL, nvc 1.19-devel r624 with the arena support; 40 packets a point, 37 octets, 0 dBm):

| PHY | distance, level | nvc | ble_host.py |
|---|---|---|---|
| LE 1M, crystals +10 / -10 ppm | 300 m, -89.7 dBm | 40/40 | 40/40 |
| | 700 m, -97.1 dBm | 30/40 | 32/40 |
| | 1000 m, -100.2 dBm | 1/40 | 3/40 |
| LE 2M | 250 m, -88.2 dBm | 40/40 | 40/40 |
| | 350 m, -91.1 dBm | 27/40 | 31/40 |
| | 500 m, -94.2 dBm | 2/40 | 3/40 |
| LE Coded S=2 | 800 m, -98.3 dBm | 39/40 | 39/40 |
| | 1000 m, -100.2 dBm | 32/40 | 33/40 |
| | 1400 m, -103.1 dBm | 3/40 | 1/40 |
| LE Coded S=8 | 1500 m, -103.7 dBm | 40/40 | 40/40 |
| | 1800 m, -105.3 dBm | 30/40 | 31/40 |
| | 2500 m, -108.2 dBm | 0/40 | 0/40 |

The two models draw different noise, so they agree as statistics, not packet for packet; the reported
RSSI is within 0.2 dB of the link budget where the signal is well above the noise.  `scan`, 2 s,
crystals +10 / -10 ppm: the beacon makes 20 advertising events, the scanner reports 10 ADV_IND, sends
10 scan requests, the beacon hears 9 and answers 9, the scanner reports 9 SCAN_RSP and 39
ADV_NONCONN_IND of the neighbour's, one packet with a bad CRC (ble_host.py: 9, 9, 9, 39, none).
Speed: about 0.008 x real time while a receiver is hearing a packet (one nvc thread; the 321-tap filter
at 32 MHz is most of it), nothing while the air is silent: 2 s of the scan scenario take 17 s.
Federated (`--fed`: the transmitting side and the other as two nvc simulations in one arena through
arena_ctl.py), both scenarios report the same lines as the one simulation.

**The tester** (`ble_tester.vhd`, `ble_nvc.py connect`) is a central with a CC2652R for its radio.  The
device under test is whatever advertises connectably in the arena, in the same simulation or in
another one of the federation, so a model of somebody else's Bluetooth IC is tested by putting it
(its own simulation, an antenna on the `ism2g4_td` band) in the arena with the tester.  One pass:

| step | what the tester does and checks |
|---|---|
| `adv`, `adv_chan` | hears four ADV_INDs on channel 37: interval 20 ms or more, advDelay within 10 ms; then one on 38 and on 39 |
| `scan` | three SCAN_REQs, each answered by a SCAN_RSP 150 us (+-2) after it |
| `connect` | CONNECT_IND; the device answers within the first six connection events |
| `version`, `features` | LL_VERSION_IND and LL_FEATURE_REQ / LL_FEATURE_RSP exchanges |
| `mtu`, `services` | ATT Exchange MTU and GATT primary service discovery (generic `host_tests`: the device has a host) |
| `per` | 40 connection events of empty packets: fewer than 30.8 % unanswered or with a bad CRC |
| `t_ifs` | the device's T_IFS over the connection, 150 us +-2 (the known path delay taken out) |
| `terminate` | LL_TERMINATE_IND is acknowledged; reports the data channels of the events that were not answered |

The reference device is ble_controller's `NODE_PERIPHERAL` on a CC2652R: at 10 m all eleven steps pass
(T_IFS 150.00 us, RSSI -60 dBm, two services found, 48 connection events) in 5 s of run time; at 700 m
with crystals +20 / -30 ppm (-97 dBm, the chip's sensitivity) the connection holds through 2 unanswered
events and 4 bad CRCs by retransmission and every step passes but `scan` (one SCAN_RSP of three lost); at
850 m advertising is heard too rarely and no connection is made.  Federated, tester and peripheral as two
simulations, the report is the same line for line.  Connections are LE 1M, one packet each way in an
event, without encryption or the PHY, parameter and channel map update procedures.

**A device under test from outside: the open BTLE baseband** (`--dut btle`).  The Verilog is `btle_phy`
of [JiaoXianjun/BTLE](https://github.com/JiaoXianjun/BTLE) (Apache-2.0; fetched by the user, not part of
stat-sim): an LE 1M GFSK modulator and a receiver that decodes in eight sampling phases, 8 samples a
symbol, no RF part.  ble_nvc.py has sv2ghdl translate it whole (`bin/iverilog-sv2ghdl`: iverilog's VHDL
back end over nvc's sv2vhdl library; 17 modules, 2 s) and compiles it with `btle_phy_radio.vhd`, which is
the rest of a radio around it with the ports of entity cc2652r: its samples interpolated to the pin's
spectral events on the way out; noise, a channel filter, decimation and an ideal AGC on the way in; a
16 MHz clock that runs only while a packet is sent or the pin has a signal.  ble_controller is its link
layer unchanged, but for handing a packet over `radio_tx_delay` (3.4 us here) early where T_IFS counts.

    BTLE_SRC=<BTLE checkout>/verilog SV2GHDL=<sv2ghdl checkout> IVERILOG=<an iverilog with -tvhdl>         ble_nvc.py --dut btle selftest | scan | connect

- The translation is exact: a loopback of the translated btle_phy in nvc gives the same 1216 I/Q samples
  as the Verilog in vvp, and the same receiver result.
- `selftest` (tb_btle_phy_radio: pin to pin with a CC2652R, 70 dB between): packets on an advertising and
  a data channel are received both ways, the end of a received packet is timed exactly and the transmit
  latency is constant.
- **What the tester found.**  As it is, the device fails the first step: `adv seen=0 crc_errors=29`, every
  advertisement heard with a wrong CRC.  The modulator's Gaussian filter delays the waveform by one symbol
  and it stops after exactly 8 samples a bit, so the last symbol, the last bit of the CRC, is not sent
  (measured on the Verilog in vvp: no phase advance is left in it).  The baseband's own receiver decides
  on what leaks into the symbol before and does not notice; the CC2652R's receiver gets that bit wrong
  for some packets (this ADV_IND among them) and right for others.
- With the last symbol completed by the front end (`--dut btle-tail`: 8 more samples turning the way of
  the last bit) all eleven steps pass at 10 m: T_IFS 149.75 us, two services found, 48 connection events.
  Federated, tester and device as two simulations, the report is the same line for line.  1.5 s of the
  link (enough for the tests) take 49 s to simulate, 5 s take 150 s (the CC2652R model as the device: 9 s).
- One of those 48 events is not answered: `terminate ... not_answered=1 not_answered_on_channels=0`.  The
  baseband takes channel number 0 as "not set" and whitens with 63 instead (scramble_core.v), so it
  neither receives nor sends on data channel 0 (2404 MHz); the connection gets over it by the next event.
  (crc24_core.v does the same with a CRC initial value of 0.)
- btle_phy also depends on which clock after reset `tx_start` comes on: one clock off and its upsampler
  drops one sample in eight (the radio resets it before each packet, so the start is always the same).

**Another device from outside: the Berkeley baseband-modem** (`--dut bmc`).  The design is `BMC` of
[ucb-bar/baseband-modem](https://github.com/ucb-bar/baseband-modem) (Chisel, BSD-3-Clause; fetched by the
user, not part of stat-sim): the baseband (packet assembler and disassembler, whitening, CRC), the modem
(a GFSK modulator that drives a VCO's tuning code; a low-IF receiver with image rejection, matched
filters, clock and data recovery) and the controller of a dual-mode BLE and 802.15.4 peripheral for a
Chipyard SoC, here without the TileLink registers and the DMA around them.  `ucb_bmc/emit.sh <directory>`
fetches it with the DMA whose streams it uses and rocket-chip v1.6 and has sbt write `BMC.v` (79 000
lines, 99 modules; a minute once rocket-chip is compiled; the design's sources are not touched).
ble_nvc.py has sv2ghdl translate that whole (55 s, kept until BMC.v changes) and compiles it with
`ucb_bmc_radio.vhd`, which is what the design lacks to be a radio with the ports of entity cc2652r:

- the **host**: the commands a link layer's driver would give (the link's constants, send, receive) and
  the memory behind the DMA streams the packets come and go by;
- the **transmitter's VCO**: the tables the design looks its tuning codes up in are loaded here (coarse
  code: the RF channel; modulation code: 2 + 4 x the modulator's 6-bit frequency index), and a carrier
  turns by the code, one sample a clock, while the design says it sends;
- the **receiver's front end**: noise, a channel filter, a mixer to the 2 MHz intermediate frequency the
  design expects, an ideal AGC (the design's own AGC and offset loops are left off) and two 8-bit ADCs;
- a 32 MHz **clock** for both of the design's clock inputs, running only while a packet is sent or the
  pin has a signal.

    ucb_bmc/emit.sh <directory>     (JAVA_HOME: a JDK up to 17; SBT: sbt)
    BMC_V=<directory>/out/BMC.v SV2GHDL=<sv2ghdl checkout> IVERILOG=<an iverilog with -tvhdl>         ble_nvc.py --heap 2g --dut bmc selftest | connect

- The translation holds: with generic `trace`, ucb_bmc_radio writes what is on the design's pins clock by
  clock, and `ucb_bmc/replay.v` puts those inputs to the Verilog in vvp and compares the outputs.  A
  packet each way, 24 626 clocks: no difference, but for 149 clocks at which the Verilog's own value has
  unknown bits (the design reads registers that have no reset: the modulator's filter as the first packet
  starts, its state before the first reset), where the translation computes with unknowns as 0.
- `selftest` (tb_ucb_bmc_radio: pin to pin with a CC2652R, 70 dB between): packets on two advertising
  channels and two data channels (0 among them) are received both ways with a good CRC, the end of a
  received packet is timed to 0.2 us and the transmit latency is constant (3.437 us).
- **What the tester found.**  As it is, the device fails at the second kind of step: `adv` and `adv_chan`
  pass (its advertisements are heard, CRC good, on all three channels), then `scan requests=3
  responses=0` and no connection.  The design's controller takes the end of a transmission from its
  802.15.4 modulator, also when the GFSK one sends: Controller.scala connects the one port of the transmit
  controller to both modulators and the last connection stands (in BMC.v:
  `txController_io_modemTXControl_out_done = io_modemControl_mskTX_out_done`).  The 802.15.4 modulator
  runs a timer of 32 us an octet, so after a BLE packet of n octets the design stays in its transmit
  state for 32 (n + 8) us where the packet took 8 (n + 9): its transmit enable stays up and it takes no
  command, so it cannot listen for what answers an advertisement 150 us after it.
- With the host ending a transmission when the GFSK modulator's state goes back to idle (`--dut
  bmc-txend`: the carrier goes off and the design is reset before its next use; the state is one a host
  can read) all eleven steps pass at 10 m: T_IFS 149.91 to 149.94 us, two services found, no event
  missed.  Federated, tester and device as two simulations, the report is the same line for line.
- The design whitens with its channel index and looks the VCO's coarse code up at the same index; its
  documentation calls that index the frequency's (0: 2402 MHz), which would whiten all channels but
  three as another.  The table is loaded here by BLE channel index, which makes the index both.
- It is slow: the Verilog takes 28 s a simulated millisecond of its clock in vvp, the translation 40 s
  in nvc (every clock moves eight 32-tap filters), some 20 s a packet.  The self-check takes 3.5 minutes;
  the tester's run is cut to what the tests need (`connect --events 10 --time 0.25`: 8 minutes, as it
  is 16, federated 16).  Not run: the scan scenario with this radio as the scanner.
- `ble_nvc.py --accel` (nvc's `--accel`, NVC_ACCEL=1) takes the cost away: nvc gives the design's Verilog
  to yosys and runs it as one compiled model (27,794 cells, 8,597 registers) with the translated VHDL's
  ports as its boundary.  It needs sv2ghdl's `yosys/gen_statemachine` built (`GEN_STATEMACHINE` if it is
  not at nvc's place for it).  The model's C is 88 MB and takes gcc 13 minutes, once per bench (kept in
  `~/.cache/nvc/accel`); after that the self-check takes 1.3 minutes and the tester's run 28 s (44 s
  with compile and elaboration) with the same report, T_IFS included.  nvc needed two repairs for it
  (the bridge looked for ports by their lower-case VHDL names and silently left out those with a
  capital in their Verilog name, 85 of this design's 108; and reading the model's text back took 80 s
  a run).
- `--dut btle-tail --accel` gives the plain run's report too, in 3.4 s for 17.9 s.  It took three more
  repairs.  A port named `rst` was not an input of the model: nvc put the model in its power-on state
  while the pin was high, memories and all, and btle_phy, reset before every packet, lost its sine
  tables (sv2ghdl gen_statemachine and nvc: `rst` is an input, the reset is the design's own logic).  A
  memory was written on the main clock's edges whatever clock its write port has (gen_statemachine;
  btle_phy's packet memory is written on `clkb`).  And an output behind logic after a register is
  published two delta cycles after the edge, which nvc did not make happen: with a bench that raises
  the clock and waits, the outputs came with the clock's fall, where btle_phy_radio reads them.
- ucb_bmc_radio's waits are in a procedure of its process: it needs nvc from 8da5a95ef on (below), or
  NVC_NO_EVAL_ARENA=1, which ble_nvc.py sets.

nvc notes from this: in nvc r626 a procedure suspended in a `wait` lost its state once it was compiled and
its process had filled its 64 KB allocation buffer (compiled code put the overflow in an arena that is
reset at every evaluation; a `wait for` of 31 ns became one of 0.1 s), so all the waits of
btle_phy_radio's process are in its body.  Fixed in nvc since (regress tlabwait1, tlabwait2); the waits
stay where they are.  And `'driver` cannot be assigned in a subprogram.

nvc note: in nvc before 30bf1386c (also with --std=2008) a `wait for` is cut short by an event on a signal
that an earlier `wait on` of the same process named; the model waits with `cc_wait_until` (a loop on
`now`) instead, and runs on either.  A process that reads a pin's `'other` is also woken by every event on it, so the
chip copies its pin to an ordinary signal in a process of its own.  The resolver plugin does not follow
a pin up through a port of an enclosing entity, so chip, antenna and controller are siblings at the
top (as in an2597_link).

## Federation -- the same spectral simulation split across the arena

The air pins' type says how their net resolves: `rf_air` (rf_spectrum_pkg) carries `resolution`
"arena", `arena_band` "ism2g4" and `arena_delay` "free_space_delay", so nvc's resolver plugin
(lib/sv2vhdl) generates one resolver per antenna, each hearing every other antenna one path delay
(distance / c) ago.  Antennas in other simulations come through libarena: the federation controller
(`arena_ctl.py`) maps each band to a logical arena (later a named IPv6 VLAN from net-chat), runs the
arena's rendezvous point and launches the simulations with `FED_NAME` / `FED_ARENAS`; after the
rendezvous they talk to each other directly.  Driver values go out tagged with their time as they
happen; each simulation reports its time, next event and counts, and runs ahead of another by the
slack between them -- the shortest delay between their antennas (10 ft: 10 ns) -- without
speculating.

`ad9361/an2597_arena.sh` runs AN-2597 three ways: hand-written zero-delay resolver, one simulation
with the delayed plugin resolver, and drone + controller as two simulations in one arena
(`an2597_link`'s `role` generic).  The federated scoreboard equals the one-simulation one (32 of 32
lines, 1 m to 3 km, 10 packets: 5.96 s federated vs 6.30 s one simulation); the path delays move EVM a
few tenths of a dB from the zero-delay reference.

    NB=/path/to/nvc-build DISTS="1.0 3.0 10.0 30.0 100.0 300.0 1000.0 3000.0" PK=10 ad9361/an2597_arena.sh

Across machines, `ad9361/an2597_side.sh` builds and runs one side (same `DISTS`/`PK`/`LEAD` on both):

    NB=<nvc-build> W=/tmp/ctrl  ROLE=2 NAME=ctrl  LEAD=8us ad9361/an2597_side.sh gen     # host B
    NB=<nvc-build> W=/tmp/drone ROLE=1 NAME=drone LEAD=8us ad9361/an2597_side.sh gen     # host A
    python3 <nvc>/lib/sv2vhdl/arena_ctl.py rendezvous --arena lab-2g4 --listen '[fd00::1]:7600' --expect drone,ctrl
    NB=<nvc-build> W=/tmp/ctrl  NAME=ctrl  RV='[fd00::1]:7600' ad9361/an2597_side.sh run
    NB=<nvc-build> W=/tmp/drone NAME=drone RV='[fd00::1]:7600' ad9361/an2597_side.sh run

The simulations connect to each other on the address they reach the rendezvous from (any free port);
a side behind NAT only dials out, so give it the lower rank (ROLE=1). Full sweep, drone in WSL and
ctrl on a second Linux host over the LAN: identical to the single simulation (32/32) both ways; with
no lead the drone took 8.92 s, 5.3 s of it waiting, and with `LEAD=8us` 6.27 s, 0.10 s waiting.
Not yet: joining a running arena, more than one arena per simulation, scatterers in the plugin path.

## Control states

`rffit.py amp ... --state nominal:VDD=1.8 --state lowvdd:VDD=1.5 --state off:VDD=0` fits one
level-dependent transfer function per named state (a set of DC source values) and writes
them all to one `<name>.json`: the block as a small state machine over static controls, each
state a spectral transfer function. Extracted LNA: nominal 94.4 dB, 1.5 V supply 66.6 dB,
off numerically zero (below -200 dB) at 7 MHz.
