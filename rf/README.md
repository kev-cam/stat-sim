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
model of the same chip is the reference it is checked against.

    ad9361.py check                  the Python model measured the way the data sheet measures the chip
    ad9361_vhdl.py emit              write ad9361_pkg.vhd from the tables in ad9361.py
    ad9361_vhdl.py check --nvc N     compile the package, run tb_ad9361.vhd, compare with ad9361.py
    an2597_nvc.py --nvc N --compare  the link in nvc, beside the link budget and the Python model
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
`ad9361_vhdl.py check`: 211 values from `tb_ad9361.vhd` in nvc against Python -- the noise-free paths
bit for bit (RX codes equal, TX envelopes to 6e-16), Monte Carlo NF / noise / EVM / leakage within 0.2 dB.

**Spectral event-driven VHDL** (all `--std=2040`):

| file | what |
|---|---|
| `rf_spectrum_pkg.vhd` | `rf_spectrum`: 64 lines (complex amplitude per frequency, both polarisations) around a carrier, one value per event; Friis per line, carrier-offset regridding, `arena_resolve` |
| `ad9361_pkg.vhd` | generated: data sheet tables, per-sample transmit and receive procedures |
| `ad9361_spectral_pkg.vhd` | one event through the chip: filters on the lines, everything non-linear on the 64 samples of the event (DAC/ADC words, compression, AGC changing gain part-way) |
| `ad9361.vhd` | the chip: RF pins `tx1`, `rx1` (std_logic nets, payload on `'driver` / `'other`), software side `cfg`, `tx_data`, `rx_data` (one symbol period per event) |
| `rf_spec_antenna.vhd` | antenna: a driver and a receiver in the arena, with a position port (it can move) |
| `arena_resolver.py` | writes the resolver network: wires between pins and feeds, and the arena -- each antenna's `air'other` is the sum of every other antenna's `air'driver` through free space between their positions |
| `ofdm_soft_pkg.vhd` | software OFDM modem on spectra (802.11a/g numerology, no coding): training, data, carrier-offset estimate and removal, channel estimate, pilots |
| `an2597_link.vhd` | the link: two chips, four antennas, and two processes as the drone's and the controller's software; the drone flies out and sends packets, the controller's fast AGC and modem receive them |

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

Speed: nvc 0.008 x real time (3.9 s for 8320 symbol events, 33 ms of air time, two radios); Python
time domain 0.07 - 0.12 x; the same event model on the GPU 18 - 47 x (next section).  nvc is not tuned: the per-sample procedures recompute their constants (band
interpolation, dB conversions) on every sample, and the arena regrids the receivers' LO leakage onto
the transmitter's grid for every antenna on every event.

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

Limits: one receive and one transmit channel per chip in the VHDL (the Python model has both and their
isolation); sample-clock offset is not modelled (the reference error moves the LOs only); propagation
delay is each line's phase, not a delay of the event (fine while it is shorter than the guard interval);
the digital FIR / half-band filters are not modelled, only the analog baseband response; no coding in the
modem, so no packet error rate; AN-2597's own modem (HT-mixed preamble, convolutional coding, 2x2 STBC)
is not reproduced -- the app note itself could not be opened, its parameters are from ADI's wiki page.

### ad9361/gpu/ -- the same spectral events on the GPU

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

## Control states

`rffit.py amp ... --state nominal:VDD=1.8 --state lowvdd:VDD=1.5 --state off:VDD=0` fits one
level-dependent transfer function per named state (a set of DC source values) and writes
them all to one `<name>.json`: the block as a small state machine over static controls, each
state a spectral transfer function. Extracted LNA: nominal 94.4 dB, 1.5 V supply 66.6 dB,
off numerically zero (below -200 dB) at 7 MHz.
