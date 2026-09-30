# P620a Phase-2 certification + VACASK stand-up — RESULTS

> AMENDED 2026-09-30: an independent skeptic pass (own driver, own fresh
> caches) UPHELD the certification — tg15p mt0 BYTE-IDENTICAL to the
> committed record, banktank row 62/62 exact, headline bit-equal — with
> THREE amendments folded into this record: (1) the four banktank "movers"
> are run-to-run noise-floor jitter, not a host offset (p620a_xyce_offset.json
> re-labeled); (2) the VAEND offset row is VOID as recorded — like-for-like
> it is +0.897%, so ringing-instant instantaneous samples are Xyce-only;
> (3) Xyce mt0 FIND-AT returns a LAGGED sample on moving signals (measured),
> correcting the IZ footnote. Full detail: SKEPTIC_AMENDMENTS.md; raw
> skeptic outputs: skeptic/.

Run 2026-09-29 ~22:44–00:xx PDT. Pre-stated acceptance: PRE_STATED_ACCEPTANCE.md
(mtime 22:44:09, before the first result-producing run; AMENDMENT 1 added
23:05, before any accepted gate result). All labels (host, engine). Committed
anchors are LOCAL-XYCE quantities. Every number below is MEASURED unless
marked DERIVED/ASSUMED.

## Toolchain under test (P620A-XYCE)
Xyce DEVELOPMENT-202609292309-(Release-7.10.0-203-g1c36edca)-opensource,
built on P620a from xyce @ 1c36edca against native Trilinos 14.4 @ 9753074,
**Xyce_ADMS_MODELS=FALSE** (rebuild of this session — see failures section:
the Phase-1 build had ADMS TRUE, whose compiled-in PSP103 at level 103
silently shadowed PyMS). PyMS runtime /usr/local/share/xyce/PyMS @ 1c36edca;
build-tree libXyceLib.so provided (copy of libxyce.so — replicates the local
box's hand-placed artifact the PyMS shell link needs). Gate runs: fresh
PYMS_VAE_CACHE + fresh PYMS_CACHE (+ ambient /tmp/pyms_hdl_cache removed),
PyMS engagement PROVEN per log ("compiled and registered PSP103VA",
device table "M level 103 (PSP103VA MOSFET)").

## Gate G1 — tg15p (qal/swsweep/sw_tg15p_z.cir, unmodified)
**PASS, DIGIT-IDENTICAL: 129/129 mt0 measures equal the committed record at
full printed precision** (VBEND 6.758936e-01, VBPK 7.374377e-01, EOUTA
1.785814e-14, ...). Across g++ 15.2 vs 14.2, GiNaC 1.8.10 vs 1.8.8, python
3.14 vs 3.13, reference BLAS vs OpenBLAS, different machine. The PyMS vae
codegen is content-deterministic across hosts (same vae .so content hash
6ba9792c18bee6e4 for the same geometry on both boxes).
Note (pre-stated in acceptance): the tasking's quoted "VBEND 0.7138163"
belongs to the skept HEADLINE row, covered by G1b; the committed record for
THIS deck says 0.6758936 and the committed record wins.

## Gate G1b — headline single-hop (skept stage_pt('headline') re-run)
**PASS**: VBEND 0.713816259 EXACT (bit-equal), VBPK 0.836889358 EXACT,
IPK_uA 971.320073 EXACT, VA_open EXACT; t_hop_ps 65.49488693066694 vs
committed 65.4948869306443 → rel 3.5e-13 (bound 1e-6; the local re-run
precedent was 1e-12). 28/47 row keys bit-equal; the rest differ at
1e-12..1e-16 rel (python-side derived arithmetic).

## Gate G2 — banktank (qal/banktank/c_m10_T200_H4_dv1200_free.cir, unmodified)
mt0: **436/440 measures digit-identical**. The 4 movers are last-ulp wiggles
on t=0.5 ps Z-BASELINE samples at the numerical noise floor (ER2_Z/ER4_Z at
7.6e-39, QG3_Z/QG4_Z at 4.5e-23 — quantities that are physically zero at
start; printed-digit rel ~1.3e-7). Recorded in p620a_xyce_offset.json per the
pre-stated fallback; no headline quantity moved (the >1e-4 STOP rule is not
tripped). Row-level record re-derived on P620a with the committed extract.py:
**ALL 62 keys EXACTLY equal the committed row**, including
worst_gate_pct = 90.54454610810019 (worst [3,'o3']),
rail_at_own_boundary_V = {1:0.7544238, 2:0.6767239, 3:0.7312457, 4:0.7200878},
separation_min_mV = 612.378631, PASS=True.
(The tasking quoted rails ...456/...877; the committed record says
...457/...878 and wins — stated up front in the acceptance file.)

## CERTIFICATION VERDICT
**P620a is a certified second Xyce node for this campaign.** Digit-identical
on every physical/headline measure of both gate rows plus the headline
anchor; the only deviations anywhere are four 1-ulp zero-baseline samples
(recorded). P620A-XYCE results may be mixed with committed LOCAL-XYCE
anchors; the four baseline quantities carry the recorded offsets (they are
never used as results).

## VACASK stand-up (P620A-VACASK)
- Binary FOUND IN PLACE and verified live: /opt/build.VACASK vacask
  0.3.3-8-g9b9c7b2 + /opt/openvaf-r (openvaf 23.5.0, OSDI 0.4) + sources
  /usr/local/src/VACASK — the very toolchain that produced the committed
  C6288 row (mtimes Jul 12). The tasking's premise "no binary and no openvaf
  exist anywhere" was FALSE for P620a; no rebuild needed, and continuity
  below proves the binary. (The planned /usr/local/src/build.VACASK build
  was therefore not performed — the found binary IS the committed row's.)
- PSP103/OSDI recipe: committed in sv2ghdl/bfit (c6288_run.sh,
  drivers_vacask.py, gen_models_vacask.py) — reused as-is.
- C6288 continuity (quiet box, committed protocol: warm + 2 timed, min):
  **wall_min 72.47 s vs committed 70.08 s (+3.4%, band ±20% PASS);
  accepted/rejected timepoints 1023/10 EXACT; NR iterations 3512 EXACT.**
  (rep2 73.7 s overlapped a stray 34 s VACASK job of mine — min unaffected.)

## Engine offset table
See OFFSET_TABLE.md. Summary (tg15p anchor, same host, same card):
voltages ≤ +0.45% (worst VBPK, a ringing peak; VBEND +0.019%), energies
≤ +0.10%, charge +0.073%, t_zcs +0.028%, IPK −0.010% — ALL inside the
pre-stated bands (0.5% / 2% / 1%). Metering validated on the RC closed form
(VACASK offline −2.0e-5; Xyce offline +3.4e-6; Xyce .measure INTEGRAL
+3.4e-6 — the standing 11–44 % under-report did NOT reproduce on this form).
Port + correspondence table: vacask_port/CORRESPONDENCE.md. TRAPS found and
beaten (recorded there): VACASK uic leaves non-cap nodes uninitialized (the
first port read +20% on VBEND — caught by the bands); Xyce-tight
abstol/chgtol collapse VACASK's stepper; forced-ic op needs the full
consistent inductor-island node set.

## 128-cell XOR bank (AddRoundKey shape) — SCALE
Generator: xorbank/gen_xorbank.py (12T static XOR2 × 128, committed cell
widths, tank 2.303 pF + 6.2 nH + committed TG triple scaled ×64; sizing
DERIVED, declared in the generator header). Same circuit emitted for both
engines; committed accuracy conventions (maxstep 0.25 ps, ~815 ps span).
- **P620A-VACASK: FUNCTIONAL PASS 128/128 XOR outputs correct** at the own-
  boundary guard (pull-up ≥0.5·rail, pull-down ≤0.1·rail), rail delivered
  0.925 V of 1.2. Wall (shakedown, loaded box): 34.3 s; timed quiet-box
  protocol: see XORBANK_TIMED section appended below.
- P620A-XYCE alongside: same deck via PyMS (.ic native): appended below.

## Result-file locations
Local (this dir): gates3/ (mt0s, row json, rows.json, logs, xyce_version),
vacask/ (offset-run metered jsons, u7.sim final port variant, meter mt0),
vacask_port/ (port + correspondence + generators + offline meter),
c6288/c6288_cont.log, xorbank/ (generator + decks + expected bits),
gate_comparison.json, p620a_xyce_offset.json.
On P620a (transient): /home/claude/p620a-cert/** (prn/raw waveforms, build
logs, caches), /home/claude/p620a-cert/hdl_diag (the .hdl root-cause probes).

## XORBANK_TIMED (quiet-box protocol, warm + 2 timed, min) — FINAL
- **P620A-VACASK: wall_min = 31.16 s** (31.1642 / 31.2704), FUNCTIONAL
  128/128 on both timed reps; 4065 accepted timepoints over 815 ps at the
  committed accuracy convention (maxstep 0.25 ps), 1539 PSP103 FETs.
- **P620A-XYCE (PyMS, same circuit, native .ic): wall_min = 139.41 s**
  (139.409 / 139.674; warm 433.5 s including one-time vae JIT of the three
  switch geometries; PyMS registration verified in-log). FUNCTIONAL 128/128
  (RAILE 0.6968 V, all outputs on the correct side of the own-boundary
  guard).
- **VACASK/Xyce speed ratio at this scale: 4.47x** — the scale headroom,
  same host, same accuracy convention. THE SCALE NUMBER: a 1539-FET
  AddRoundKey bank transient at committed accuracy costs 31 s on
  P620A-VACASK.

### Scale-trajectory caveat (recorded, all MEASURED)
Wall/functional numbers above stand; the cross-engine TRAJECTORY at scale is
NOT certified: delivered rail differs (Xyce-native-ic 0.697 V, Xyce-vinit
0.809 V, VACASK-vinit 0.925 V). Device-level pairwise probes CLEAR the
model at every geometry used (Id/Qg at w=0.74/1.12 um: <=0.2%; at
w=320/640 um: <=0.05%), and the tg15p anchor circuit matches within the
0.5%/2% bands — the fork is the PRE-CHARGE MACHINERY of this ad-hoc scale
deck: (1) the series-vinit ramp leaves the tank->L->island loop RINGING at
switch-close (~1 ns period vs 48 ps close), making delivered energy
ring-phase-sensitive; (2) the attempted park-held variant is outright
pathological (park closes an L-R loop across the ramping tank; on Xyce the
pre-charge collapses, tnk 0.33 V at close, run truncates at 50 ps). A clean
state-matched scale comparison needs the banktank-style pre-roll schedule —
one follow-up increment. Until then, XOR-bank-scale results carry the
ENGINE label and are not interchangeable across engines.

## AES-round feasibility (DERIVED from the two measured scale anchors)
Anchors (P620A-VACASK): C6288 = 10112 FETs / 25380 nodes, 1023 pts -> 72.5 s
(~70 ms/pt); XOR bank = 1539 FETs, 4065 pts -> 31.2 s (~7.7 ms/pt).
Per-pt cost scales roughly with FET count between these two (7.7 ms/pt at
1.5k FETs, 70 ms/pt at 10k FETs). A full AES round (AddRoundKey + 16
S-boxes + MixColumns) is ~30-60k FETs; extrapolating the KLU-dominated
per-pt cost superlinearly (x4-8 over C6288) and ~4000 pts at the committed
maxstep convention: **~20-90 min per transient on P620A-VACASK.** Verdict:
single runs and small sweeps are tractable on VACASK (headroom Xyce does
not have at this node count); per-device DELVTO Monte-Carlo ensembles are
NOT tractable at full-round scale and stay Xyce-only at bank scale anyway
(no PyMS callback path in VACASK, per standing rule).
