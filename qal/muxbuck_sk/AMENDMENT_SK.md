# Amendments to `qal/muxbuck_sk/PRE_REGISTERED_SK.json`

Pre-registration: sha256 `91627ad21418204b8114109247abe1e6dcd470017aa10305a7bfe451c671d272`,
7405 B, mtime **2026-09-29 11:22:39.571601455 -0700**, written when the only other
thing in this directory was an empty `vae_cache_sk/`. First deck file
`sk_instr.cir` **11:22:5x**, first result `.mt0` **11:37**.

---

## SK-A1 — decks ADDED that were not in the pre-registered plan

| deck | why |
|---|---|
| `sk_gain58.cir` | the band conversion needs a SLOPE, and one operating point cannot give one. Tank pre-charge 0.58 V, everything else identical. Same reason the balance run added `mb_gain_v58`; I did not read their value before measuring mine. |
| `sk_droop8_r32.cir` | the balance run FLAGGED that the PDK's own estimator says R = 31.76 Ω for the 15 nH transfer inductor against the 10 Ω the committed decks model, and then did not propagate it. One deck settles what it does to the band. |
| `sk_mx_q{1,4,16}.cir`, `sk_mx_qe{1,4,16}.cir` | see SK-A2. |
| `sk_mx_p2_q16.cir`, `sk_mx_p2_qe16.cir` | two-pulse variants under the consistent initial condition. |

## SK-A2 — the pre-registered H1 decks FAILED and were replaced

`sk_mx_e1.cir` / `sk_mx_e16.cir` (mux closed from t=0, otherwise the balance run's
deck verbatim) both **failed to converge at t = 9.978 ps**, the instant the HS gate
starts to fall. The failing device is my own `XQDEL` 1 F integrator on `I(VMTU)`:
with the mux closed, the buck output node is hard-tied to a 360 fF tank and the
turn-on current step is too stiff for the integrator at `RELTOL=1e-6 ABSTOL=1e-15`.

Replaced by `sk_mx_q*` / `sk_mx_qe*`, which differ in exactly two ways:

1. **the `QDEL`/`QGM` integrators are removed.** All charge numbers then come from
   the linear tank capacitor's own voltage (`Q = C·ΔV`), which acceptance criterion
   K2 allows and which needs no B-source at all.
2. **`.ic V(na) = V(nb) = 0.66`** instead of `0`. The balance run's deck sets
   `V(na)=0` and `V(nbx)=0.66`, which puts 0.66 V across a 1 nH inductor at t=0 with
   essentially nothing holding `nbx` up. That initial condition is itself a source of
   the ringing whose consequences this run is auditing, so both my schedules are run
   from the physically consistent quiescent state (zero volts across L, zero inductor
   current). **`sk_mx_q*` is the balance run's schedule under that IC and is the
   control; `sk_mx_qe*` changes only the mux timing.** The N-dependence is read as a
   difference between two decks that share everything else.

## SK-A3 — a row that FAILED and is reported, not fixed

`sk_mx_p2_qe16.cir` (two back-to-back pulses, mux never disconnected) aborts at
**t = 73.04 ps** — "time step too small", failing node `NA` — which is the instant
the mux opens on an inductor carrying ≈4.5 mA with no freewheel path. That is
physical, not numerical prudishness: permanently closing the mux turns the block
into a hard-switched converter. **The single-pulse early-close result stands; there
is no two-pulse early-close row and nothing in the deliverable rests on one.**

## SK-A4 — a deviation from my OWN concurrency cap

For roughly 20 s around 11:37 there were **3** of my Xyce processes alive, not the
2 I pre-registered: I launched batch 2 while the anchor deck was still writing its
`.prn`. Box load average over the whole run stayed **3.5 – 6.5 on 16 cores**, so the
courtesy constraint the cap exists to serve was never at risk, but the cap as
written was exceeded and this records it.

## SK-A5 — a self-inflicted stall worth recording

A waiter written as `until ! pgrep -f "run2.sh"; do sleep 5; done` never exits,
because the shell running it matches its own pattern. Known trap, walked into anyway;
cost one stalled background task and no simulation time.

---

# VERDICTS ON MY OWN PRE-STATED EXPECTATIONS

| | statement | verdict |
|---|---|---|
| **S1** | closing the mux early shrinks the N16−N1 gap by **more than 3×** | **CONFIRMED, 34.9×** (−60.78 fC → −1.74 fC) |
| **S2** | the deficit scales with mux WIDTH, so the pressure is to narrow, the opposite of M1-C | **CONFIRMED.** 0.5×/1×/2× width → 25.66/57.92/105.74 fC, one capacitance density (0.346–0.391 fF/µm) fits all three |
| **S3** | my Q_beat reproduces theirs within 5% | **CONFIRMED, and better than I asked for.** At *their* sample instant I read 35.42 fC against their 35.42 fC. The two runs agree to 4 significant figures; the only difference is which instant is sampled |
| **S4** | K is a booking **and therefore the ceiling is not independent of the disputed buck** | **HALF REFUTED — my miss.** K *is* an un-measured booking. But the ceiling `K·store/Q_beat` contains no `q` at all, so it is genuinely independent of the disputed quantity. The balance run was right about this and I was wrong. What moves the ceiling is K itself (phase locking) and the band (inductor R), not the buck's delivery |
| **S5** | the crossover stays far above the charge ceiling under any plausible inductor model | **CONFIRMED.** Crossover 469 (smallest legal winding) to 1034 (PDK default); ceiling 17–26. Even a 1 nH inductor 10× smaller than the PDK default leaves the crossover 4× above the ceiling |

## Also my miss, unprompted

My hypothesis H1 was framed as "the tax is an artifact of the schedule." The
**N-dependence** is indeed an artifact and collapses 35×. But I half-expected
closing the mux early to make the delivery *good*, and it does not: the buck still
removes ≈36 fC from the tank at N=1 with the mux permanently closed. Fixing the
schedule does not fix the converter. Those are two separate defects and I should
not have let them share one hypothesis.
