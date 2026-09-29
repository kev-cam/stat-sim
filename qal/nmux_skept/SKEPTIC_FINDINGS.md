# SKEPTIC RE-RUN of qal/nmux -- independent decks, own PYMS_VAE_CACHE, own extractors

Cache: /usr/local/src/stat-sim/qal/nmux_skept/vae  (11 .so compiled from scratch this session)
Pre-registration integrity of the primary run verified BEFORE I started:
  sha256sum -c PRE_REGISTERED.sha256 -> OK ; pre-reg mtime 11:50:38, first primary deck 12:04.

## NULL-MODEL CANARY (A1 defence) -- every stage
warm_n074: Id(Vgs=1.0,w=0.74u) = 62.2413 uA  [record 62.24]   -> model live
warm_all : I(VD)=199.4 uA, I(VSP)=194.1 uA                     -> 9 geometries live
warm_sw  : I(VD)=759.7 uA, I(VSP)=1764.8 uA                    -> 10u/20u live
Every Vt deck checked for Imax > 1e-6 A: 17/17 pass.

## (a) Vtn(V_sb) -- 17 decks, Vgs taken as V(G)-V(S) (A4 axis bug avoided by construction)
G1: Vtn(0) = 0.5239876 V vs committed 0.5239460 -> +0.0416 mV
Curve matches the record to <= 3 uV at all 17 points. Total shift 0->1.3 V = 127.78 mV.
gamma = 0.23025 V^0.5, 2phi_F = 0.7985 V, RMS resid 0.0117 mV (max 0.0208).
gamma stable across criteria: 0.23025 / 0.22946 / 0.22966 (100n / 10n / 1n).
V* = VGH - Vtn(V*), VGH=1.5:  0.8832 (100n) / 0.9621 (10n) / 1.0346 (1n)
Margin: peer 0.755 -> +128.2 mV OPEN ; tank 1.26 -> -376.8 mV CLOSED ; 1.326 -> -442.8 mV

### NEW: body effect is NOT the deciding mechanism
gamma forced to 0 -> V* = 0.9760 V, still 284.0 mV BELOW the tank rail.
Body effect costs 92.8 mV of ceiling (24.6% of the 376.8 mV tank deficit); Vt0 costs 524.0 mV.
VGH required to pass: 1.9086 V at rail 1.26 ; 1.9798 V at 1.326. (No HV model card in this
lib -- only sg13g2_nmos/pmos level=103 -- so the overvoltage option is UNTESTED here.)

## (b) pass HIGH -- clean ideal-rail harness, w=0.60u, CL=2 fF, 13 rails
At the campaign's 293 ps hold window:
  rail 0.7550 -> 0.7546 (shortfall   0.4 mV)   TG 0.7549 (0.1)   operand 0.2101 (544.9)
  rail 0.8832 -> 0.8403 (           42.9 mV)   TG 0.8830 (0.2)   operand 0.3245 (558.7)
  rail 1.2600 -> 0.8779 (          382.1 mV)   TG 1.2600 (0.0)   operand 0.6702 (589.8)
Same node vs time at rail 1.26: 0.8779 @293ps, 0.9312 @1ns, 1.0293 @20ns -- tracking the
100n/10n/1n ceilings 0.8832/0.9621/1.0346. The criterion IS a time scope; A9 is right.
DOES MEASURED BEAT THE ARITHMETIC? No -- at 293 ps it lands 3-5 mV BELOW V*. The record's
0.8951 exceeds V* by 11.9 mV; that is a harness effect (its measured +39.9 mV injection
pedestal on a real node, plus a moving rail), not a physics surprise. [DERIVED]
Practical crossover rail (293 ps): 0.8173 V @10 mV tol, 0.8557 @25 mV, 0.8920 @50 mV.
TG reaches the rail exactly at EVERY rail here -> the record's "TG worse at peer" is a
LOADING effect, not pass fidelity. Confirmed by chain rails: nmos 1.2836 vs tg 1.0728.
E6 pass LOW independently CONFIRMED: from a worst-case 1.30 V precharge, nMOS-only reaches
< 0.0001 mV within 100 ps. The asymmetry is the whole story.
Injection peak +97 to +101 mV onto 2 fF at w=0.60. NEW: residue 0.000 mV for rails <= 0.95 V
but +62 to +98 mV for rails >= 1.0 V -- above the ceiling the device cannot conduct the
excess back, so the kick is unremovable (data-independent pedestal, eats margin).
NEW mux-tree depth (peer rail, 293 ps): 1-deep 0.4 mV, 2-deep 18.0, 3-deep 62.3.
  Ceiling unchanged (all reach 0.7550 at 20 ns) -> rate penalty, constrains tree depth.
NEW dynamic select: switching sel rather than holding it static costs 2.3 mV extra. Fine.

## (c) chain -- all 5 committed decks re-run in my cache, my extractor, polarity derived
    independently from each deck's VI1_* inputs and the inverter count.
MY FIRST EXTRACTION WAS WRONG: I sampled at the switch-open instant and got depth 5 for
nmos_std. The cells keep settling after the switch opens. Sampling one phase period
(300 ps) after each bank's own close reproduces the record on all 30 values:
  wire_std  1504.2 1227.8 1051.5  885.6  732.1  639.7   depth 6   (delta +0.1..+2.1)
  nmos_std  1278.0  980.6  786.2  610.6  395.8  399.8   depth 6   (delta -0.2..+0.9)
  tg_std    1048.7  856.8  772.7  634.4  402.3  390.2   depth 6   (delta -0.2..+1.2)
  wire_skew 1186.4  904.8  701.8  513.3  332.5   50.1   depth 6   (delta +0.7..+4.0)
  nmos_skew  573.6  411.6  267.8  111.0   29.4    3.2   depth 5   (delta +0.0..+1.7)  FAILS
E9 refutation CONFIRMED. Restoration CONFIRMED: bank 2 passed high = 0.9196 V (record
0.9196, identical) from a 1.2836 V rail.
CAVEAT I ADD: pass loss by depth = 356.3, 102.7, 3.7, 2.8, 2.4 mV. The clamp binds only at
depths 2-3; from depth 4 the source is below V* (0.7988 V) and the pass is near-lossless.
So six-deep survival is NOT evidence of nMOS-only working at a SUSTAINED tank rail -- the
reservoir droops into the peer-like regime. Only 2 of 6 depths test the hard case.
A8 stands: G3 was dropped; I re-ran the same decks, so I verify simulation + extraction,
NOT deck generation or the ZCS probe.

## (d) contention -- 8 DC sweeps, plus an independent |Vtp| anchor
Instrument check (std, VDD 1.2, Vin 0.6759): 8.779 uA / 3.0867 fJ / 36.71%
  vs committed 8.780 / 3.0896 / 36.75%  -> -0.011% on current.
Std receiver at nMOS-pass 0.8832: 0.000 / 0.119 / 0.682 / 3.335 uA at VDD 0.90/1.20/1.26/1.33
  = 0.00% / 0.50% / 2.99% / 15.46% of the 8.408 fJ hop.  Record 0.000/0.119/0.678/3.323.
Trips 0.4936 / 0.6428 / 0.6709 / 0.7027 -- identical to the record.
Skewed 0.15p/1.48n: 0.000 / 0.000 / 0.000 / 0.004 uA -> removes it completely.
MECHANISM ANCHORED INDEPENDENTLY: |Vtp| = 0.4402848 V (committed 0.4402734, +0.011 mV);
VDD-Vin crosses it between VDD 1.26 (0.3768) and 1.33 (0.4468) -- exactly where it returns.
I ALSO QUANTIFIED THE READ MARGIN as Vout: at VDD 1.26/1.33 the std cell MISREADS the
committed QAL high 0.6759 (Vout 0.5780 / 1.1238) but reads 0.8832 correctly everywhere
(Vout <= 6.4 mV). The pass structure genuinely improves read margin.

## (e) analogy -- challenged both ways
Shared and measured by me: (ii) top-of-swing collapse, quantified; (i) uncancelled injection,
and it becomes UNREMOVABLE above the ceiling.
Structural and genuinely absent from logic: no inductor, unidirectional, success criterion is
the destination LEVEL not source depletion (VA_open).
MY OWN SUPPORTING ARGUMENT FAILED: at the top of swing, per micron, the chain's transfer
switch carries 1.76 uA/um and the logic mux 7.27 uA/um -- the mux is driven ~4x HARDER per
micron. So logic is NOT easier because it moves less current. (Caveat: I probed the chain's
TG-based switch, rail peaking 1.5604 V, so the nMOS is not the conducting device there --
inconclusive, but it does not support the "less current" reading.)
NOT REPRODUCED BY ME: the nMOS-only transfer switch itself. Mechanism (iii) rests on the
committed swsweep record. Largest un-reproduced dependency in this pass.
MECHANISM WAVED AWAY, in the other direction: the operand-gated case is a LOGIC failure from
the same source-follower physics, fatal at every rail (544.9 mV shortfall at the peer rail).
The record measures it; the headline does not carry it. XOR2 -- explicitly asked for -- is out.

## PROCESS
I hit the campaign's own pgrep self-match trap: `pgrep -f 'Xyce warm_all'` inside a compound
command matched its own command line and spun 600 s. Fixed by waiting on explicit PIDs.
A6 CONFIRMED (I doubted it and was wrong): 9 distinct widths -> 9 separate .so, ~2.5 min each.
STANDING CAVEAT: sg13lv_compat.sp zeroes ad/as/pd/ps -> all energies and settle times are
LOWER bounds, and the TG has twice the omitted junction area, so every comparison here is
conservative in the direction of the nMOS-only conclusion.
