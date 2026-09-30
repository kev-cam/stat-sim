# qal/mcsize — the mismatch Monte-Carlo on the QAL chains that actually compute

**This closes the A3 GO/NO-GO loop.** A3 was designated the QAL go/no-go, the harness was
built (`qal/qal_a3_mc.cir`, `qal/run_a3_mc.sh`, 2026-09-23), and there was never a working
chain to run it on. There is now: `qal/banktank` (committed `0aae11e`) computes, and
`qal/resv` (committed `812a172`) is the other arrangement that works.

Everything previously measured in this campaign is **nominal** — typical corner, zero
mismatch. σ(Vt) had been used only as a *static floor* (6.441 mV, `qal/vtaudit/AUDIT.md:68`,
itself a lower bound). No chain had ever been Monte-Carlo'd. "32/32 gates correct at a
200 ps beat" was a **typical-device** result, not a yield.

- Pre-registration: `PRE_REGISTERED.json`, sha256 `a99fdd70e0e0b9f64812d55502ae53a78b7c3e4f8dd2a69f12f607e95ab4ef6b`,
  17208 B, mtime **2026-09-29 14:38:29.545 -0700** — written before the first deck.
- Departures from it: `AMENDMENT.md` (nine, each with the forcing fact and mtimes).
- Criterion: **adopted from `qal/fcrit/PRE_REGISTERED.json`** (mtime 14:35:08, i.e. 3 min 21 s
  before mine), with one declared adaptation and one declared correction — see §3.

Every number is labelled **MEASURED** (this study's own deck), **MEASURED-COMMITTED**
(another run's committed record, path given), **DERIVED** (arithmetic on those), or
**ASSUMED**.

---

## 0. Bounds to state before anything else

| bound | effect on an MC specifically |
|---|---|
| `qal/sg13lv_compat.sp` passes **ad=as=pd=ps=0** — zero junction capacitance on every device in both DUTs | Real drain/source junction caps add load that (a) slows every edge, eating the timing margin this study measures, and (b) is *itself* a mismatched, geometry-dependent quantity that is absent from the draw. Both omissions push the same way: **the yields here are UPPER bounds** on the same circuit with junctions. |
| only `delvto` mismatch applied; the PDK also carries `factuo_mm` (0.005 n / 0.0033 p), `dw_mm` 4 nm, `dl_mm` 2 nm | Every σ here is a **lower bound**, so every margin-in-σ is an **upper bound**. Inherited from `AUDIT.md`, which says so on its face. |
| **tt corner only**, nominal temperature | This is **not PVT sign-off**. No global corner, no temperature. (`.OPTIONS DEVICE TEMP` is inert against PyMS-compiled PSP103 in this toolchain; corners would need instance-level DTA and were not swept.) |
| 4 banks / 24 scored links (DUT_A), 6 banks (DUT_B) | A chain-level yield on a 4-deep chain. A real datapath is thousands of gates deep; see §6 for the scaling, which is stated rather than used to move the bar. |

**A mismatch yield is one term of a manufacturing yield and must not be read as one.**

---

## 1. A_VT — extracted from the PDK, not assumed  *(MEASURED)*

`/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models/sg13g2_moslv_mismatch.lib`

    .param sg13g2_lv_nmos_delvto_mm = 0.0039      ; V*um
    .param sg13g2_lv_pmos_delvto_mm = 0.0022      ; V*um

applied by the PDK's own wrapper (`sg13g2_moslv_mod_mismatch.lib:87,100,110,126,139,149,173`) as

    delvto = agauss(0, delvto_mm / sqrt(m*l*w*1e12), 1)

so **σ(Vt) = A_VT / √(W·L·m)** with A_VT in V·µm — a Pelgrom coefficient, *not* an
absolute-volts sigma.

**Does PSP103 carry an explicit matching parameter? No.** The PSP103.6 cards in
`sg13g2_psp103_tt.lib` carry no A_VT/AVTO/matching entry. The PDK supplies mismatch
**out of band** — the four `*_mm` params above plus an ngspice `agauss` wrapper that is
not part of the card this toolchain compiles through PyMS. This study therefore takes
A_VT from the PDK's own mismatch lib and applies it through the PSP103 instance parameter
`DELVTO`, which is the same physical knob (a rigid Vt translation) the PDK's wrapper drives.

*Cross-check:* re-deriving `AUDIT.md`'s three committed sigmas from these two coefficients
reproduces them exactly — 0.74 µm n → 12.574 mV, 1.12 µm p → 5.766 mV, 10 µm n → 3.421 mV.

### Per-geometry σ(Vt), L = 0.13 µm  *(DERIVED)*

| device | W (µm) | σVt (mV) | where |
|---|---|---|---|
| skewed-RX pMOS | 0.15 | **15.754** | resv boundary receiver — **worst-matched device in the study** |
| cell nMOS | 0.74 | **12.574** | every inverter, both DUTs |
| skewed-RX nMOS | 1.48 | 8.891 | resv boundary receiver |
| park nMOS | 2.00 | 7.649 | held OFF all run |
| cell pMOS | 1.12 | 5.766 | every inverter, both DUTs |
| transfer nMOS | 10.0 | 3.421 | hop switch |
| transfer pMOS | 20.0 | 1.364 | hop switch |

> **Correction to the inherited harness.** `qal_a3_mc.cir`'s header assumed
> "A_Vt = 3.5 mV·µm" **for both polarities**. That was never read from the PDK. It is
> 11 % low for nMOS, 59 % high for pMOS, and using one constant for both polarities is
> wrong in principle.

---

## 2. The instrument gate — DELVTO *does* vary per device *(MEASURED, blocking)*

No sample was trusted until per-device independence was demonstrated. All three
pre-registered tests pass, plus an at-scale check in the real DUT.

### (b.1/b.2) DC characteristics shift independently — and the shim is innocent

`b1_indep.cir`: three devices in **one** deck, biased identically, DC-swept together;
Vt by constant current (100 nA·W/L). Commanded shift +10.000 mV on one device at a time.

| shifted | MA (direct M-line, n 0.74 µm) | XB (**through the shim**, n 0.74 µm) | XC (**through the shim**, p 1.12 µm) |
|---|---|---|---|
| nothing (ref) | Vt = 464.7918 mV | 464.7918 mV | \|Vtp\| = 388.4773 mV |
| MA only | **+9.991166** | 0.000000 | 0.000000 |
| XB only | 0.000000 | **+9.991166** | 0.000000 |
| XC only | 0.000000 | 0.000000 | **+10.020965** |
| MA **and** XB | +9.991166 | +9.991166 | 0.000000 |

d(Vt)/d(DELVTO) = 0.9991 (n) and 1.0021 (p), against `AUDIT.md`'s 1.0000 / 1.0040.
**Every cross-term is 0.000000 to six decimals**, and the shifts are additive.

> **Correction.** `qal_a3_mc.cir`'s header says the devices are inlined as direct M-lines
> because the compat shim "would eat the random param" and the nested-subckt wrapper
> "silently kills AGAUSS sampling". **Measured, that is false.** `shim_mc.sp` is the
> committed shim plus one forwarded `dvt=0` parameter, and the shim path and the direct
> path agree to six decimals. Both DUTs are therefore MC'd **through the shim they were
> committed with**, which removes a whole class of "did you change the DUT" doubt.

### (b.3) `.SAMPLING` draws independently, at the commanded σ

`b2_sampling.cir`, N = 300, three independent AGAUSS draws; Vt recovered per sample by a
constant-current `WHEN` on a DC sweep, so the recovered Vt **is** the draw.

Xyce writes the per-sample draws to `.res` as `XA:DVT`, `XB:DVT`, `XC:DVT` — per **device
instance**. Each device's measured Vt tracks its own draw at slope 0.99999 / 0.99998 /
−1.00420 V/V with |corr| = **1.000000**; cross-correlations −0.0288 / +0.0215 / −0.0456
against a ±0.115 noise band; **300 distinct values** per device.

One σ came back 12.8 % low at N = 300 (−3.1 standard errors), so the generator was
re-checked at **N = 4000** (`b3_rng.cir`) before it was trusted:

| device | commanded σ | measured σ | deviation | observed tails |
|---|---|---|---|---|
| n 0.74 µm | 12.5741 mV | 12.8046 | +1.64 SE | −3.52 … +3.68 σ |
| n 0.74 µm | 12.5741 mV | 12.5997 | +0.18 SE | −3.67 … +4.29 σ |
| p 1.12 µm | 5.7656 mV | 5.8194 | +0.83 SE | −4.10 … +3.59 σ |

The N=300 deficit was sampling noise. The tails reach ±4.3 σ, so the generator is **not
truncated at 3 σ** — a truncated generator would have silently understated failures.

### At scale: all 76 devices of the real DUT_A deck

| class | n | commanded σ | pooled measured σ |
|---|---|---|---|
| cell nMOS | 32 | 12.5741 | 12.377 |
| cell pMOS | 32 | 5.7656 | 5.735 |
| park nMOS | 4 | 7.6485 | 7.414 |
| transfer nMOS | 4 | 3.4205 | 3.013 |
| transfer pMOS | 4 | 1.3644 | 1.352 |

5700 pairwise correlations: mean −0.0043, max +0.541 against a 1/√N = 0.162 noise scale;
**zero pairs above r = 0.9** (a shared parameter would read 1.0); every device shows the
full count of distinct values. Device shell verified to export the runtime-callback getter
(`nm -D pyms_shell/pyms_PSP103VA.so | grep -c getCbParam` = 1).

**Gate verdict: PASSED.** The oldest failure mode in this campaign — a sweep whose
parameter is silently shared or inert — is excluded by measurement, not by assumption.

---

## 3. The criterion

Adopted from `qal/fcrit/PRE_REGISTERED.json` §THE_CRITERION: *a signal is good enough if,
at the instant the receiver commits, it is on the correct side of **that** receiver's
measured decision threshold, at **that** receiver's delivered rail.* Scored per **link**
(sender bank k gate i → receiver bank k+1 cell i); the last bank has no in-deck receiver
and is out of link scope, which is reported rather than hidden.

**Two declared departures:**

**(i) The noise budget — fcrit's NB would double-count.** fcrit sets
NB = 3σ_trip + coupling + droop, with 3σ_trip = 19.323 mV. That term is a *static
allowance for exactly the random Vt mismatch this study draws explicitly per sample*.
The MC therefore scores at **NB = the deterministic terms only** (coupling and droop, both
zero for a free-running no-top-up chain) — which is fcrit's own "NB = 0, pure threshold
crossing" column. fcrit's full NB is reported alongside every point, labelled as the
conservative variant that double-counts.

**(ii) The commit instant — fcrit's justifying claim is false, so both instants are scored.**
fcrit defines t_commit as the receiving bank's ZCS/open instant, justified by claim (ii):
"the receiving cells' pull-up path can no longer reach any level it has not already
reached." **On the committed waveform it does.** In `resv/ch_res20`, `V(o6_0)` rises
**0.15906 → 0.34466 V** between the open instant (1821.43 ps) and the committed boundary
(2000 ps) — 186 mV *after* the charge island is cut, because the cells keep settling out
of the now-floating rail's own capacitance rather than out of the inductor. fcrit's own
document invites this ("if [it does] not hold, the definition is wrong and I will say so").

Both are scored. **`bound` (= c_k + T) is primary** — it is what every committed extractor
samples and the instant the beat schedule actually allows the next stage to look. `open`
is the harsher variant and its nominal failures are reported as nominal failures.

**Receiver-output form (MC-native, no composition).** fcrit's threshold is "the input at
which the receiver, supplied at its delivered rail, has Vout = Vdd/2". For a monotone
inverting cell that is *exactly* equivalent to asking whether the receiver's own output has
crossed its own mid-rail. The receiver is physically in the deck **with its own DELVTO
draw**, so scoring on the receiver's output needs no per-sample trip composition and no
sensitivity coefficients at all. Absolute-trip checks (RX_STD 0.6452/0.6548 V,
RX_SKEW 0.4595 V — MEASURED-COMMITTED, `qal/bound/dc_rows.json`, `qal/skept/trips.json`)
are reported separately for the chain *exit*, where a synchronous receiver would sit.

---

## 4. Nominal, before any mismatch — and the deck self-test

`mkmc.py` makes three declared cost reductions (drop `.print`; drop the 1F energy
integrators `CX*/BX*/RX*`, which hang on isolated nodes and drive nothing; truncate the
transient past the last needed commit instant). **Self-test — the stripped, truncated
DUT_A deck reproduces the committed `HEADLINE_pre_registered_point`:**

| | mcsize `bt_nom` | committed banktank | Δ |
|---|---|---|---|
| rail2 @ bound_2 | 0.676724 V | 0.67672 V | +0.0039 mV |
| rail3 @ bound_3 | 0.731246 V | 0.73125 V | −0.0044 mV |
| rail4 @ bound_4 | 0.720088 V | 0.72009 V | −0.0023 mV |

### DUT_A (banktank, m=10, T=200 ps, H=4, dV=1.2, free) — nominal

| instant | link 1→2 | link 2→3 | link 3→4 | chain verdict |
|---|---|---|---|---|
| **bound** | +278.51 mV, 0/8 fail | +296.48 mV, 0/8 | +307.16 mV, 0/8 | **PASS**, worst +278.51 mV |
| open | −31.71 mV, 5/8 fail | −55.43 mV, 3/8 | −14.16 mV, 5/8 | **FAIL**, worst −55.43 mV |

Chain exit (bank 4) against a synchronous receiver: HIGH class 0.6672 V, LOW class
−0.0042 V, rail 0.72009 V → **0/8 wrong at all three absolute trips** (0.4595, 0.6452,
0.6548 V).

> Note against my own pre-registration: I worried the 90 %-settled proxy would put gates
> below the standard 0.6452 V trip. It does — but on the *intermediate* banks (bank 2 HIGH
> sits at 0.6169 V), which are read by QAL cells on depleted rails, not by synchronous
> cells on 1.2 V. At the chain **exit**, where a synchronous receiver would actually sit,
> bank 4 clears every trip. The mechanism I flagged is real; it lands somewhere that does
> not matter. **Architectural consequence: this chain works because its receivers are QAL
> cells on depleted rails. It is not readable mid-chain by a 1.2 V receiver.**

### DUT_B (resv res20, ca_mult=20, K=6, T=300 ps) — nominal, **and it already fails**

Read directly off the committed `c_res20.cir.prn` at zero simulation cost:

| bank | instant | rail (V) | sep (mV) | RX(rail/2) | ABS 0.4595 | ABS 0.6548 |
|---|---|---|---|---|---|---|
| 1 | bound | 1.32574 | 1325.7 | PASS | PASS | PASS |
| 2 | bound | 1.04892 | 1048.9 | PASS | PASS | PASS |
| 3 | bound | 0.87943 | 879.3 | PASS | PASS | PASS |
| 4 | bound | 0.72340 | 721.1 | PASS | PASS | PASS |
| 5 | bound | 0.59804 | 562.1 | PASS | PASS | **FAIL** |
| 6 | bound | 0.53185 | 282.3 | PASS | **FAIL** | **FAIL** |
| 4 | open | 0.78156 | 369.7 | **FAIL** | FAIL | FAIL |
| 5 | open | 0.67915 | 208.4 | **FAIL** | FAIL | FAIL |
| 6 | open | 0.58315 | **14.3** | **FAIL** | FAIL | FAIL |

**The decisive one — DUT_B's own in-deck boundary receiver.** resv instantiates a skewed
0.15 µm-p / 1.48 µm-n receiver (`XRP1_*a`/`XRN1_*a`) on a **hard 1.2 V supply**, reading
bank 6. At nominal, zero mismatch, at bank 6's committed boundary:

    rm1_0 = 1.20918 V   (should be LOW: its input o6_0 is an intended HIGH)   ** WRONG **
    rm1_1 = 1.19788 V   (should be HIGH: its input o6_1 is an intended LOW)      ok
    rb1_0 = -0.00002 V  (restored, should be HIGH)                            ** WRONG **
    rb1_1 = -0.00001 V  (restored, should be LOW)                                ok

`rb1_0 ≈ rb1_1 ≈ 0` — **both classes collapse to the same value; the restored output
carries no data.** The mechanism: bank 6's intended-HIGH sits at 0.34466 V on a 0.53185 V
rail (64.8 % of rail — healthy *relative to its own rail*), but the receiver is referenced
to a hard 1.2 V supply whose trip is 0.4595 V. The signal never crosses it. In fcrit's
taxonomy this is **FAIL_never**, not FAIL_late.

This was **pre-stated** (PRE_REGISTERED §6 `expectation_about_DUT_B_nominal`) so it could
not be claimed as a discovery afterwards. The prediction was right about the outcome and
**wrong about the mechanism**: I predicted both candidate trips would fail; in fact the
rail-referenced criterion *passes* at bank 6 and only the hard-supplied absolute one fails.
The distinction matters, and it is the design fix: **the boundary receiver is one bank too
late.** It belongs after bank 5 (which clears 0.4595 V with 562 mV of separation), or bank 6
needs a rail-referenced receiver rather than a 1.2 V one.

---

*(§5 MC yields, §6 sensitivity ranking, §7 Phase-2 sizing: filled in below from the runs.)*

---

## 5. DUT_A — the mismatch yield of the chain that computes  *(MEASURED, N = 300)*

`bt_mc_{2001,2002,2003}.cir`, 100 samples each, independent seeds; 76 mismatched devices,
24 scored links. Per-sample cost 17.5 s (1747/1773/1762 s per chunk).

### The headline

| commit instant | failures / N | yield | **95 % CI** | one-sided failure bound |
|---|---|---|---|---|
| **bound** (= c_k + T, primary) | **0 / 300** | 100 % | **[98.78 %, 100 %]** | ≤ **1.00 %** (rule of three) |
| open (fcrit's literal t_commit) | **300 / 300** | 0 % | [0 %, 1.22 %] | — |

**Zero failures in 300 is not "100 % yield".** It bounds the chain failure rate at
≤ 1.00 % (one-sided 95 %; the two-sided Clopper-Pearson lower bound on yield is 98.78 %).
Scored at fcrit's *full* NB = 19.323 mV — the variant that double-counts the random term —
the bound instant still gives **0 / 300**.

### Why it passes so comfortably: the margin is ~16 σ, not ~1 σ

Chain worst margin over the 24 links: **262.01 ± 15.93 mV**, minimum over 300 samples
**+142.36 mV** → **16.45 σ to failure**. Per-gate, the tightest gate in the design is
o4_1 at **13.24 σ**.

**The pull-up/pull-down asymmetry is the whole story.** Margin σ, by gate class:

| link | pull-UP (HIGH) margin | pull-DOWN (LOW) margin |
|---|---|---|
| 1→2 | +277.5…278.4 ± **7.3–8.1** mV (34–38 σ) | +333.7…333.8 ± **0.70–0.80** mV (418–474 σ) |
| 2→3 | +295.4…296.4 ± **7.1–8.3** mV (35–42 σ) | +320.1…322.2 ± **14.6–17.3** mV (18–22 σ) |
| 3→4 | +301.0…304.9 ± **19.6–22.7** mV (13–16 σ) | +364.1…364.3 ± **2.4–2.7** mV (137–152 σ) |

Two things read straight off this:

1. **Mismatch variance accumulates with depth.** The pull-up margin σ roughly triples from
   link 1→2 (7.3–8.1 mV) to link 3→4 (19.6–22.7 mV). Bank 1 is driven by ideal sources, so
   its receivers see no upstream mismatch; by bank 4 the draw of every upstream device is in
   the answer. **A 4-bank chain is the best case.** Extrapolating the observed growth, the
   16.45 σ chain margin would be consumed somewhere around a few tens of banks — which is
   the number that matters for a real datapath and which this 4-bank run cannot measure. It
   is stated as an extrapolation, not a result.
2. **The binding gate moves with the instant.** At `bound`, 210 of 300 samples have their
   worst gate in link 1→2 (smallest *mean* margin) and 89 in link 3→4 (largest *σ*, hence
   the extreme tail: the 142.36 mV minimum is an o4 gate). At `open`, 290 of 300 worst gates
   are in link 2→3.

### Both polarities — checked, and the answer is completely one-sided

Scored at the `open` instant, the only instant with failures, over all 7200 gate-instances:

| polarity | gate-instances | failures |
|---|---|---|
| pull-UP shortfall (HIGH read as LOW) | 3900 | **3694 (94.72 %)** |
| pull-DOWN shortfall (LOW read as HIGH) | 3300 | **0 (0.00 %)** |

**Every failure in this study is a pull-up shortfall.** The pull-down side did not fail once
in 3300 gate-instances, and at the bound instant it sits at 137–474 σ. This is the mismatch
counterpart of the campaign's measured regime split (free-running chains bind on the pMOS
pull-UP): the free-running per-bank-tank chain binds on the pull-up under mismatch too.
A one-sided MC would not have *missed* half the failures here — there is no other half —
but that is a **measured** result, not an assumption, and it required scoring both.

### The result that actually changes a design decision: the exit receiver

Bank 4 is the chain exit, where a synchronous receiver would sit. Same 300 samples:

| boundary receiver | trip | failures / 300 | yield | 95 % CI |
|---|---|---|---|---|
| **RX_SKEW** 0.15 µm-p / 1.48 µm-n | 0.4595 V | **0 / 300** | 100 % | [98.78, 100] % |
| **RX_STD** 1.12 µm-p / 0.74 µm-n | 0.6452 V | **191 / 300** | **36.33 %** | [30.9, 42.1] % |

Nominally bank 4's HIGH class sits at 0.6672 V — only **22 mV** above the standard cell's
0.6452 V trip — while the mismatch σ on that level is ≈ 21 mV. So the standard receiver sits
about **1 σ** from the decision boundary and the QAL→synchronous boundary becomes a coin flip.
The skewed receiver has ≈ 10 σ.

Per gate, each of the five HIGH-class exit lanes fails 33–58 times in 300 (11–19 %); the
union over five lanes is what gives 191/300. Measured exit levels: HIGH class
0.6618–0.6657 V ± 19.4–22.4 mV, LOW class −0.0034 V ± 2.0–2.3 mV. The LOW class clears
both trips by a wide margin — again, the pull-up is the only side at risk.

> **This is the single most actionable number in the study.** The brief calls the receiver
> choice "a design lever"; measured, it is the difference between **36 % and 100 % yield** at
> the same chain, same beat, same devices. It is also a case where the *nominal* result was
> actively misleading: at zero mismatch **both** receivers read bank 4 correctly (§4), so
> nothing short of an MC could have exposed it.

## 6. Per-device sensitivity ranking — the input to Phase 2  *(MEASURED)*

Response: the chain's worst margin (min over all 24 scored gates) at the bound instant,
regressed on each device's own per-sample DELVTO draw.

### By class — variance share

| rank | class | n | σVt (mV) | rms contribution | **variance share** |
|---|---|---|---|---|---|
| **1** | **cell nMOS 0.74 µm** | 32 | 12.57 | 7.098 mV | **52.42 %** |
| **2** | **cell pMOS 1.12 µm** | 32 | 5.77 | 6.192 mV | **39.89 %** |
| 3 | transfer pMOS 20 µm | 4 | 1.36 | 2.090 mV | 4.55 % |
| 4 | park nMOS 2 µm | 4 | 7.65 | 1.607 mV | 2.69 % |
| 5 | transfer nMOS 10 µm | 4 | 3.42 | 0.658 mV | 0.45 % |

### Top individual devices

| rank | device | σVt (mV) | d(margin)/d(Vt) | contribution (mV) |
|---|---|---|---|---|
| 1 | XN3_7 | 12.67 | −0.2385 | 3.022 |
| 2 | XN3_1 | 13.78 | −0.2147 | 2.958 |
| 3 | XN3_0 | 11.95 | −0.2195 | 2.624 |
| 4 | XP2_2 | 6.05 | −0.4097 | 2.479 |
| 5 | XP3_6 | 6.01 | −0.3892 | 2.339 |
| … | | | | |
| **12** | **XSWP4** | **1.33** | **−1.1834** | 1.574 |

### Scoring my pre-stated predictions (PRE_REGISTERED §6)

| prediction | outcome |
|---|---|
| rank 1 = cell nMOS 0.74 µm | ✅ **right** (52.42 %) |
| rank 2 = cell pMOS 1.12 µm | ✅ **right** (39.89 %) |
| cellN carries ~81.7 % of variance (from the trip-only model) | ❌ **wrong — 52.42 %.** The trip-only model over-weights it. cellP measures **39.89 %** against a predicted 18.3 % — a 2.2× under-prediction. |
| "the failure set splits: nMOS threshold vs pMOS drive; pMOS share rises as the beat shortens" | ✅ **right in mechanism.** The pMOS excess over the trip-only prediction is the drive term, and every failure that occurs is a pull-up shortfall. |
| park nMOS "ranks near zero despite its σ" (2nd-largest σ in DUT_A) | ✅ **right** — 2.69 % on a 7.65 mV σ, because it is held OFF all run. σ alone does not rank devices. |
| transfer pMOS 20 µm ranks **last** | ❌ **wrong — it ranks 3rd (4.55 %)**, ahead of two devices with 2.5–5.6× its σ. |

**The transfer-pMOS miss is the instructive one.** XSWP4 has the *smallest* σ in the design
(1.33 mV) and the *largest* per-millivolt leverage of any device (**d(margin)/d(Vt) = −1.18**,
3–5× a cell device). It ranks 3rd because leverage × σ, not σ, is what matters — and it has
small σ **because it is 20 µm wide**. That is σ(Vt) = A_VT/√(WL) already doing its job in the
committed design: the highest-leverage device was made the widest. The lesson generalises to
Phase 2 — **rank by leverage × σ, and spend area where the product is largest, not where σ is.**

---

## 7. DUT_B — the reservoir chain  *(MEASURED, N = 30)*

`rv_mc_{3001,3002,3003}.cir`, 10 samples each; 158 mismatched devices, 6 banks.
Per-sample cost 150 s (1506/1507/1509 s per chunk). **N = 30 is small and the interval is
correspondingly wide — that is reported, not smoothed.** The pre-registered fallback
(§5 of PRE_REGISTERED: "N is reduced and the WIDER confidence interval is reported
honestly") applies: DUT_B costs 8.6× DUT_A per sample, and its headline turned out not to
need a large N (below).

| criterion | instant | failures / 30 | yield | 95 % CI |
|---|---|---|---|---|
| link criterion, banks 1–6, rail-referenced | bound | **0 / 30** | 100 % | **[88.43, 100] %** |
| link criterion | open | 30 / 30 | 0 % | [0, 11.57] % |
| bank 6 vs its **own rail**/2 | bound | 0 / 30 | 100 % | [88.43, 100] % |
| bank 6 vs the **absolute** 0.4595 V trip | bound | **30 / 30** | **0 %** | [0, 11.57] % |
| **DUT_B's own in-deck boundary receiver** | bound | **30 / 30** | **0 %** | [0, 11.57] % |

### The boundary receiver fails deterministically, and mismatch has nothing to do with it

The data-carrying quantity is the **class separation** — the gap between the intended-HIGH
and intended-LOW lane groups. Traced through the boundary at the committed bound instant:

| node | class separation | what it means |
|---|---|---|
| `o6` (bank-6 outputs) | **+280.27 ± 8.14 mV**, min +263.13 | **the data IS present** — 34 σ of separation, healthy |
| `rm1` (receiver a-stage out) | **−11.18 ± 0.25 mV** | wrong sign, and 0.93 % of its 1.2 V supply |
| `rb1` (restored out) | **−0.01 ± 0.00 mV** | **no data at all** |

Absolute levels: `o6` HIGH 0.34406 V / LOW 0.06380 V on a 0.53207 V rail;
`rm1` 1.20912 V (from HIGH) / 1.19794 V (from LOW) — **the a-stage output spans 11.18 mV of a
1200 mV supply and never switches.** Its pMOS never turns off, because the receiver is
referenced to a hard 1.2 V rail whose trip is 0.4595 V, which is **above both** bank-6
classes.

**So this is a reference/level-shift design failure, not a yield problem.** The mismatch
spread on that wrong-sign separation is 0.25 mV against an 11.18 mV deficit — about 45× too
small to rescue it in any sample, which is why 0/30 is already conclusive and why a larger
N would buy nothing. In fcrit's taxonomy: **FAIL_never**, every sample.

> **Self-correction, recorded.** My first pass reported this as "−5.59 ± 0.13 mV, 43 σ on the
> wrong side". That number was an artefact: I had averaged a signed per-lane margin over 8
> lanes in which 4 terms are ≈ −609 mV and 4 are ≈ +598 mV, so the mean was the near-
> cancellation of two large opposite quantities and its tiny σ was the cancellation's
> residue, not a margin spread. It is exactly the "tautology of the deck" failure this
> campaign has been bitten by before. The corrected statistic is the class separation above.

**The design fix is placement, not sizing.** Bank 5 clears the 0.4595 V absolute trip with
562 mV of separation (§4); bank 6 does not. The boundary receiver is **one bank too late**.
Either terminate at bank 5, or give bank 6 a rail-referenced receiver instead of a 1.2 V one.
No amount of area on the receiver fixes a reference that sits above both signal classes.

### DUT_B sensitivity — and my headline DUT_B prediction is REFUTED

Variance share, two responses (the second is the one that contains the receiver's own Vt):

| class | n | σVt (mV) | share of **bank-6 level** | share of **receiver decision** |
|---|---|---|---|---|
| cell nMOS 0.74 µm | 48 | 14.19 | **37.28 %** | **31.87 %** |
| cell pMOS 1.12 µm | 48 | 6.22 | **30.95 %** | **25.93 %** |
| **skewed-RX pMOS 0.15 µm** | 8 | 13.72 | 3.67 % | **8.73 %** |
| park nMOS 2 µm | 6 | 8.58 | 2.90 % | 8.31 % |
| skewed-RX nMOS 1.48 µm | 8 | 10.07 | 4.03 % | 5.95 % |
| transfer pMOS 20 µm | 6 | 1.39 | 5.10 % | 5.37 % |
| restoring pMOS 1.12 µm | 8 | 5.30 | 5.15 % | 2.96 % |
| source-switch nMOS 10 µm | 6 | 3.50 | 3.99 % | 3.82 % |
| source-switch pMOS 20 µm | 6 | 1.32 | 3.96 % | 1.94 % |
| restoring nMOS 0.74 µm | 8 | 11.88 | 1.86 % | 3.72 % |
| transfer nMOS 10 µm | 6 | 4.03 | 1.11 % | 1.39 % |

*(measured σ at N = 30 carries ≈ 4–5 % standard error per class and more for the 6–8-device
classes; the shares, not the σ estimates, are the result.)*

| prediction (PRE_REGISTERED §6) | outcome |
|---|---|
| **DUT_B rank 1 = skewed-RX pMOS 0.15 µm** — "the worst-matched device in the whole study … if it is rank 1, the fix is pure geometry" | ❌ **REFUTED. It is rank 3 (8.73 %) even on the response that contains its own Vt**, and rank 8 (3.67 %) on the bank-6 level. |
| DUT_B rank 2 = skewed-RX nMOS 1.48 µm | ❌ rank 5 (5.95 %) |
| DUT_B rank 3 = cell nMOS 0.74 µm | ❌ — it is **rank 1** (31.87 %) |

**Why the prediction failed, and it is the same lesson as DUT_A's transfer-pMOS miss.** I
ranked by "largest σ **and** sits in the decision path". Both premises were true and the
conclusion was still wrong, because I ignored **multiplicity**: there are 48 cell nMOS and
48 cell pMOS, each feeding the six-bank cascade that *produces* the signal, against only 8
skewed-RX pMOS that affect only the final read. Collectively the cell devices carry 57.8 %
of the receiver decision's variance. The correct ranking rule is
**leverage × σ × (number of decisions the device touches)** — and it was *not* obtainable
from σ and topology by inspection. That is the case for running the MC rather than reasoning
about it.

---

## 8. Phase 2 — buying margin with area, and what it actually costs

σ(Vt) = A_VT/√(W·L) says mismatch falls as the square root of device **area**, so sizing is
the mechanism by which layout buys margin. Phase 2 measures that on the chain, in two
separable axes, because **"mismatch got smaller" and "the cell got bigger and slower" are a
confound** that a naive sizing sweep cannot separate:

* **pure-σ axis** (`--kvt`): every σ scaled, **geometry unchanged**. Isolates mismatch.
* **geometry axis** (`--sizing`): W or L scaled, σ following A_VT/√(WL) as the PDK dictates.
  All variants scale **n and p together** so the P/N ratio — hence the cell's trip point —
  is held at 1.5135. Pre-registered (§9) as the only way to buy σ without moving the trip.

The response is **timing slack**: `bound − (earliest instant from which every scored gate is
correct through the boundary)`, min over links. Measured on a 9-point grid per link, step
**10.28 ps**, so *any sd below ~10 ps is quantisation-limited and means "no resolvable spread"*.

### 8a. The pure-σ axis — geometry fixed  *(MEASURED, N = 50 each)*

| deck | σ multiplier | cell σVt n / p (mV) | slack mean ± sd (ps) | slack min | fail @ bound | **yield** | 95 % CI |
|---|---|---|---|---|---|---|---|
| `p2_base` | **1× (the PDK's own σ)** | 12.57 / 5.77 | **61.93 ± 1.40** | 52.71 | **0 / 50** | **100 %** | [92.89, 100] % |
| `p2_k4` | 4× | 50.30 / 23.06 | 44.61 ± 15.93 | 11.34 | 5 / 50 | 90.0 % | [78.19, 96.67] % |
| `p2_k8` | 8× | 100.59 / 46.12 | 27.11 ± 21.56 | 0.00 | 32 / 50 | **36.0 %** | [22.92, 50.81] % |

**At the PDK's real σ the chain has 61.93 ps of timing slack with no resolvable spread**
(sd 1.40 ps is a seventh of a grid step; only three distinct grid values occur in 50 samples).
The committed 200 ps beat is not mismatch-limited — it is ~62 ps clear of the earliest
instant at which the data is already correct.

**It takes an 8× σ inflation to push this chain to a coin flip.** For scale, the committed
th22 C-element MC reached 4× Vt mismatch with 0 fails in 800 samples; this chain fails 10 %
at 4× and 64 % at 8×, so it is *less* mismatch-robust than th22 — which is expected, since
th22 is one gate and this is a 4-bank cascade on a decaying rail.

**Where the failures land confirms depth accumulation.** Failures by link:

| σ multiplier | link 1→2 | link 2→3 | link 3→4 |
|---|---|---|---|
| 1× | 0 | 0 | 0 |
| 4× | 0 | 0 | **5** |
| 8× | 0 | 9 | **28** |

Every failure at 4× and the great majority at 8× are at the **deepest** link. Per-link mean
slack at 8×: 51.98 / 47.21 / 39.83 ps — monotonically decreasing with depth.

**Sensitivity caveat, stated rather than glossed.** The `p2_base` slack class share
(cellP 48.9 %, cellN 30.7 %) is **not trustworthy**: at 1× σ the slack response takes only
three distinct quantised values, so that regression has almost no dynamic range. The two
runs with real spread agree with each other and with the independent margin-based ranking
of §6:

| response | cell nMOS | cell pMOS | transfer pMOS | park | transfer nMOS |
|---|---|---|---|---|---|
| margin, 1× σ (§6, N = 300) | **52.42 %** | 39.89 % | 4.55 % | 2.69 % | 0.45 % |
| slack, 4× σ | **59.60 %** | 29.37 % | 3.43 % | 3.55 % | 4.04 % |
| slack, 8× σ | **55.92 %** | 32.51 % | 6.41 % | 0.80 % | 4.36 % |
| slack, 1× σ — *quantisation-limited, do not use* | *30.74 %* | *48.91 %* | *8.15 %* | *7.68 %* | *4.52 %* |

**Cell nMOS is rank 1 on every response that has resolvable spread, cell pMOS rank 2.**

### 8b. The geometry axis — and W and L are NOT interchangeable  *(MEASURED, N = 50 each)*

All variants scale cell n **and** p together, so P/N = 1.5135 and the trip point are held.
σ follows the PDK's own A_VT/√(W·L).

| variant | cell W (µm) n/p | cell L | cell σVt n / p (mV) | **device area** | slack mean ± sd (ps) | slack min | fail @ bound | yield |
|---|---|---|---|---|---|---|---|---|
| `p2_base` | 0.74 / 1.12 | 0.13 | 12.574 / 5.766 | 24.38 µm² | 61.93 ± 1.40 | 52.71 | 0 / 50 | 100 % |
| **`p2_wx2`** W×2 | 1.48 / 2.24 | 0.13 | **8.891 / 4.077** | **32.12 µm²** | **72.36 ± 0.56** | **72.08** | 0 / 50 | 100 % |
| `p2_wx4` W×4 | 2.96 / 4.48 | 0.13 | 6.287 / 2.883 | 47.59 µm² | 64.20 ± 2.94 | 63.12 | 0 / 50 | 100 % |
| **`p2_lx2`** L×2 | 0.74 / 1.12 | **0.26** | **8.891 / 4.077** | **32.12 µm²** | **30.10 ± 3.42** | 21.71 | 0 / 50 | 100 % |

σ(Vt) = A_VT/√(W·L) is confirmed to the digit: W×2 and L×2 both land on **8.8912 mV**
(= 0.0039/√(0.1924)) at **identical 32.12 µm² area**, because σ sees only the product.

#### Three results, in order of how much they change a design decision

**1. W and L buy the same σ for the same area and cost wildly different amounts of time.**
`p2_wx2` and `p2_lx2` are matched on both axes a mismatch model can see — same σ, same area —
and differ by **42.3 ps of timing slack (72.36 vs 30.10 ps, a 2.4× loss)**. W×2 doubles drive
while doubling load; L×2 *quarters* drive while doubling load. **Design rule: buy mismatch
margin with WIDTH, never with LENGTH, on a resonant rail.** A sizing optimiser that treats
"area for σ" as the objective — as the σ = A_VT/√(WL) relation alone invites — will pick these
two as equivalent and be wrong by more than half the slack.

**2. Width has an interior optimum, and it is at ×2, not at "wider is better".**
Slack goes 61.93 → **72.36** → 64.20 ps for W× 1 → 2 → 4, while σ falls monotonically
12.574 → 8.891 → 6.287 mV. **W×4's σ is a further 29.3 % below W×2's** (6.287 vs 8.891 mV)
**and it gives back 8.2 ps of slack for 48 % more area than W×2.** The mechanism is the one
the campaign already measured on the
transfer switch (30 → 80 µm improved rail drain but *degraded* level time 116.75 → 125.18 ps):
past a point the cell's own capacitance joins the resonance and the load term overtakes the
drive term. **This is the pre-stated non-monotonicity (PRE_REGISTERED §9), confirmed.**

**3. At the PDK's real σ, yield cannot discriminate between any of these.** All four
variants are 0/50 — as they must be, when the baseline already has 16.45 σ of margin (§6).
**Reporting "sizing improves yield" here would be unsupportable.** What sizing measurably
improves is **slack and σ**, and to see it in a *yield* at all the mismatch has to be
inflated — which is §8c.

#### The honest cost table

| variant | σ reduction | area cost | slack change | verdict |
|---|---|---|---|---|
| W×2 | −29.3 % | **+31.7 %** | **+10.4 ps** | **the optimum: cheaper σ AND more time** |
| W×4 | −50.0 % | +95.2 % | +2.3 ps | σ still falling, slack past its peak, area doubled |
| L×2 | −29.3 % | +31.7 % | **−31.8 ps** | same σ and area as W×2, **loses half the slack** — do not |

Energy is **not** costed here: this study dropped the 1F energy integrators from the decks
(§4, declared), so switched capacitance scales as the area column but the measured
per-hop energy was not taken. That is a stated gap, not an estimate.

### 8c. Sizing vs YIELD — resolved by inflating σ 8×  *(MEASURED, N = 50 each)*

At the PDK's real σ no sizing variant fails (§8b), so the sizing-vs-yield question cannot be
answered there at all. It is answered at the **8× stress point**, where the baseline is a coin
flip. **The 8× multiplier is a deliberate stress test, not a process claim.**

| variant | area | cell σVt n (mV) | slack mean ± SEM (ps) | fail / 50 | **yield** | 95 % CI |
|---|---|---|---|---|---|---|
| base | 24.38 µm² | 100.59 | 27.11 ± 5.08 | 32 | **36 %** | [22.92, 50.81] % |
| **W×2** | 32.12 µm² | 71.13 | **49.58 ± 2.51** | 13 | **74 %** | [59.66, 85.37] % |
| W×4 | 47.59 µm² | 50.30 | 42.74 ± 3.11 | 16 | 68 % | [53.30, 80.48] % |
| **L×2** | 32.12 µm² | 71.13 | **11.48 ± 1.21** | 8 | **84 %** | [70.89, 92.83] % |

Fisher exact, two-tailed:

| comparison | p | verdict |
|---|---|---|
| base vs W×2 | **0.0003** | resizing helps, **significant** |
| base vs W×4 | **0.0025** | resizing helps, **significant** |
| base vs L×2 | **< 0.0001** | resizing helps, **significant** |
| W×2 vs W×4 | 0.66 | **not significant** |
| W×2 vs L×2 | 0.33 | **not significant** |
| W×4 vs L×2 | 0.10 | **not significant** |

**This is the sharpest statement the study supports, and it needed both axes to get here.**

1. **Resizing buys mismatch yield, decisively**: 36 % → 68–84 %, every route significant
   against the baseline at p ≤ 0.0025. σ ∝ 1/√(W·L) works as advertised.
2. **The three resize routes are indistinguishable on yield** (p = 0.10–0.66 at N = 50).
   L×2's apparent 84 % vs W×2's 74 % is **not** a real difference — reporting it as one
   would be over-reading N = 50. Which is expected: **they have identical σ, so they should
   have identical mismatch yield.**
3. **The entire differentiator between W and L is TIME.** W×2 vs L×2, at identical σ and
   identical area: slack differs by **38.10 ± 2.79 ps = 13.7 standard errors.** The yield
   axis cannot see the difference; the timing axis sees it at 13.7 σ.

> ### The design rule
> **Buy mismatch margin with WIDTH, never with LENGTH.** At equal area they buy the same σ
> and — measured — the same yield; width additionally buys ~38 ps of timing slack where
> length spends it. And **width has an interior optimum (here ×2)**: past it the cell's own
> capacitance joins the resonance, so σ keeps falling while slack turns over and area keeps
> being spent. A sizing optimiser driven by σ = A_VT/√(WL) alone sees W and L as
> interchangeable and picks wrong.
>
> **Where a device wants upsizing for mismatch but downsizing for speed, that tension is
> real and it resolves in favour of width-at-moderate-multiple** — not of area for its own
> sake. The committed design already embodies the same principle at the transfer switch: the
> highest-leverage device in the chain (XSWP, d(margin)/d(Vt) = −1.18, 3–5× a cell) has the
> smallest σ in the design because it is 20 µm wide.

---

## 9. What this closes, and what it does not

**A3 was designated the QAL GO/NO-GO. On mismatch, at the configuration that computes, the
answer is GO — and mismatch turns out not to be the binding constraint.**

| question | answer |
|---|---|
| Does the per-bank-tank chain survive Vt mismatch at its committed 200 ps beat? | **Yes.** 0 failures / 300, yield ≥ 98.78 % (95 % CI), failure rate ≤ 1.00 % one-sided. |
| How much margin does it have? | **16.45 σ** at chain level (262.01 ± 15.93 mV); tightest single gate 13.24 σ; 61.93 ps of timing slack with no resolvable spread. |
| What breaks it? | Not mismatch at 1×. It takes **8× σ** to reach a coin flip. |
| Which device dominates? | **Cell nMOS 0.74 µm (52.4 % of margin variance), then cell pMOS 1.12 µm (39.9 %)** — rank 1 and 2 on every response with resolvable spread. |
| Both polarities? | Checked. **Every failure is a pull-up shortfall; 0 failures in 3300 pull-down gate-instances.** |
| Does the reservoir chain work? | **No — and not for a mismatch reason.** Its own boundary receiver fails 30/30 and also at zero mismatch: bank 6 carries +280 mV of separation and the receiver, referenced to a hard 1.2 V supply with a 0.4595 V trip above both signal classes, never switches (class separation at its output −11.18 ± 0.25 mV; at the restored output −0.01 mV, i.e. no data). The fix is **placement** — the receiver is one bank too late. |
| Can sizing buy margin? | **Yes, and the route matters more than the amount.** See §8c. |

### The result most likely to change what gets built

**The QAL→synchronous boundary receiver choice is worth 36 % vs 100 % yield** (§5) on the
same chain, same beat, same devices — and **at zero mismatch both receivers read it
correctly**, so only an MC could expose it. This is the concrete content of "MC & layout
optimization is where we guarantee behavior": the nominal result was not merely imprecise
here, it was **actively misleading**.

### Not covered — restated so no one reads past it

- **tt corner only, nominal temperature. This is NOT PVT sign-off.**
- `delvto` mismatch only — no `factuo`, `dw`, `dl`. **Every σ is a lower bound**, so every
  margin-in-σ is an **upper** bound.
- **Zero junction capacitance** (`ad=as=pd=ps=0` in the committed shim). Both the added load
  and its own mismatch are absent; both push optimistic. **The yields are upper bounds.**
- **4 banks / 24 links.** Margin σ roughly **triples** from link 1→2 to link 3→4, and every
  failure at 4× σ lands on the deepest link — **mismatch variance accumulates with depth, so
  a 4-bank chain is the best case.** What a thousand-gate datapath does is an extrapolation
  this run cannot make.
- **A mismatch yield is one term of a manufacturing yield and is not one.**
- Energy was not metered (the 1F integrators were dropped); area is reported as device area.
- DUT_B's N = 30 gives a [88.43, 100] % interval on its passing criteria. Its decisive
  result (the receiver) is deterministic, so N does not limit it.

---

## Files

| file | what |
|---|---|
| `PRE_REGISTERED.json` | pre-registration, sha256 `a99fdd70…`, mtime 14:38:29 |
| `AMENDMENT.md` | nine departures, each with forcing fact + mtimes |
| `shim_mc.sp` | committed `sg13lv_compat.sp` + one `dvt` pass-through |
| `mkmc.py` | committed deck → MC deck (per-geometry σ from the PDK; `--sizing`, `--kvt`) |
| `score.py` / `slack.py` / `rx6.py` | margin-, timing- and boundary-receiver scorers |
| `b1_indep.cir`, `b2_sampling.cir`, `b3_rng.cir` | the three instrument-gate decks |
| `bt_nom.cir` | zero-mismatch self-test vs the committed banktank row |
| `bt_mc_200{1,2,3}.cir` | DUT_A baseline MC, N = 300 |
| `rv_mc_300{1,2,3}.cir` | DUT_B MC, N = 30 |
| `p2_{base,k4,k8}.cir` | Phase-2 pure-σ axis (geometry fixed) |
| `p2_{wx2,wx4,lx2}.cir` | Phase-2 geometry axis at 1× σ |
| `p2k8_{wx2,wx4,lx2}.cir` | Phase-2 geometry axis at 8× σ (yield-resolving) |
| `RES_*.json` | all scored results |
