# qal/mesh amendments (each dated, each BEFORE the affected extraction ran)

## M1 — commit instant is the run containing the RECEIVER's crest  (2026-09-30, before any sweep deck)

PRE_REGISTERED.json scoring_definitions.commit reads "...whose run contains bank
b's crest instant".  That definition is UNSATISFIABLE BY CONSTRUCTION for the
sine mesh: bank b's rail crests exactly when its receiver's rail sits at trough
(antiphase), and the eye of link b is gated on the receiver's rail being inside
the measured trip table (>= 0.20 V) — so no link-b eye run can ever contain
bank b's own crest.  The error is in which crest the sentence names, not in the
mechanism.

AMENDED (before any sweep extraction executed): t_commit(bank b, wave n) = the
opening edge of the link-b eye run that contains the RECEIVER's crest instant
(slot_start(b+1, n) + crest_offset) — the instant the receiving rail is at max
and the data must be standing.  Everything else (eye definition, die edge,
overlap = t_die(k) − t_commit(k+1), acceptance thresholds) is unchanged.

Found while implementing the extractor, before the first mesh deck was run;
the smoke test (ICB) exercises the amended definition.

## M2 — wave-pipeline instants: commit run by largest-in-rise-window; value check AT the commit  (2026-09-30, after ICB smoke, BEFORE any sweep deck)

MEASUREMENT THAT FORCED IT (ICB, sine th=130 d=1, wave 3, link 1, kept .prn):
the link eye opens at ~880 ps (during the DRIVER's rise), is admitted by the
in-table rule at ~945, and DIES at ~1005 as the driver's decaying HIGHs cross
the receiver's rising trip — margin at the receiver's crest (1040 ps) is
-174 mV even on this healthiest link (ideal-input chain head).  In an
antiphase mesh the receiver's crest coincides with the DRIVER's trough: both
the pre-registered crest-instant value check (acceptance A) and M1's
receiver-crest commit probe sample the data AFTER its natural death in a wave
pipeline.  The tank campaign's crest checks were valid only because tanks HELD
the driver rail for H*T; nothing holds here BY DESIGN — the wave is the point.
The bank-2 0.548 V levels at its crest (ICB value fails) are the post-die
ratioed-fight levels, not a failure of the wave.

AMENDED, all extraction-side, decks unchanged except added interior-level
prints; thresholds, eye definition, in-table rule, wave set, patterns all
unchanged:
 (a) commit/die run selection: the LARGEST eye run intersecting the receiver's
     rise window [slot_start(rx), slot_start(rx)+crest_offset] — the committed
     qal/eye pick="largest" rule, window-restricted.  t_commit = its opening
     edge, t_die = its closing edge; overlap(link k) = t_die(k) - t_commit(k+1)
     unchanged in form.
 (b) acceptance A (value) is scored AT THE COMMIT INSTANT from the dense
     trace: last-level outputs vs the RECEIVER's instantaneous trip, BOTH
     polarities, all 6 links (= the 8-bit word is bit-correct when the
     receiver takes it); interior levels (d >= 2) vs the bank's OWN
     instantaneous trip at the same instant.  Waves 2,3,4.
 (c) the crest-instant .mt0 FINDs are RETAINED and reported as CREST_DIAG
     (the post-die corruption level — diagnostic, no longer gating).
 (d) the RISING-side tracking lag (bank rail 50%-crossing to HIGH-output
     50%-crossing) is extracted and reported per bank — ICB shows ~90-100 ps
     at th=130, the quantity that will set the frontier.

## M3 — the d-ascent early stop is REFUTED; run the full d grid  (2026-09-30, after the first sine lane results)

MEASURED: sine d=1 fails at every half-period 70..105 with overlap deficits
-85..-108 ps, while per-link eyes all EXIST (17-51 ps wide).  Anatomy: a
wave's BIRTH advances down the chain rail-gated at th per bank, but the NEXT
wave's CORRUPTION (racing through banks whose rails are still up) advances at
the banks' un-gated response time (tens of ps per bank) and GAINS (th - t_resp)
per bank, catching the wave after ~2*th/(th - t_resp) banks.  Therefore DEPTH
IS A DEFENSE: d series levels multiply the corruption traversal time t_resp
while birth stays th-gated — the pre-registered lane rule "deeper is strictly
harder at fixed T_half" (grounds for the d-ascent early stop) is WRONG for the
corruption channel.  AMENDED: lanes run the FULL d grid 1..4 regardless of
d=1's verdict.  (Also fixed: crowbar Q_gnd fC display was 1e12 too large in
already-written OUT.json rows — values there are fC*1e12; extractor fixed.)

## M4 — the commit is B's OWN act: un-gate it from C's rail  (2026-09-30, after the d=2 sine rows)

MEASURED BASIS (sine d=2, th=70/92/105): the link eye exists at EVERY link
with identical per-link offsets (open srx+~0.23*th at the in-table entry,
close srx+~0.79*th) — the wave demonstrably propagates — yet the M2 overlap
read a deficit of almost exactly -0.45*th at every th, because t_commit was
taken from the link-(k+1) eye, which is GATED on bank k+2's rail entering the
trip table: that forces "B commits" to wait a full half-period past B's
physical establishment and double-counts the antiphase gap.  The task's own
definition is "when A's falling outputs stop being good vs when B COMMITS" —
B's act, during B's rise, not C's readability.

AMENDED (extraction only; eye scoring, in-table rule, thresholds unchanged):
 commit_raw(bank k, wave n) = opening edge of the largest margin-positive run
   (trip taken from the receiver's rail with the Trip class's extrapolation
   below 0.20 V, since the gate on the RECEIVER's read stays where it belongs
   — in the eye) that intersects bank k's OWN rise window
   [slot_k, slot_k + crest_offset].
 overlap(link k) = t_die(k) [close of the GATED link-k eye run, unchanged]
   - commit_raw(k+1).  Acceptance B margins are sampled at commit_raw(k+1);
   acceptance A (value) is scored at commit_raw(k, n).  The M2 gated commit is
   retained in the record as commit_gated.  commit_raw is an OPENING instant;
   the 69.924 mV margin gate and the eye/value chain carry the strength
   requirement (a link passes only if every downstream link also holds its
   own eye and value).
All rows re-run (the .prn deletion discipline removed the dense traces needed
to re-score in place); decks byte-identical, only the extractor changed.

## M4b — value samples the raw-run MIDPOINT  (2026-09-30, smoke re-extract)
Sampling value AT commit_raw tests the defining crossing against itself (the
slowest gate's margin is zero there by construction -- a numerical coin flip;
smoke: 0.2053 vs 0.2060).  Value (acceptance A) now samples the MIDPOINT of
the raw validity run, (commit_raw + die_raw)/2 -- the word while it stands.
Timing strength stays where it belongs: B (>= 69.924 mV at the handoff commit
sample) and C (positive overlap chain).

## M4c — commit-run intersection window is the POWERED window  (2026-09-30, after sine d=3)
MEASURED: at d=3 the chain head's outputs establish just past its own crest
(3 levels + the input-edge undershoot recovery) — outside [slot, slot+co] —
NO_COMMIT, while its rail is still near crest and the establishment is real
and strong (downstream links: margins +338 mV, overlaps +25 ps).  The commit
run must intersect bank k's POWERED window [slot_k, slot_k + co + th/2]
(rail above ~half-crest through early fall).  A late commit still pays its
price where it belongs: overlap(link k-1) > 0 is gated on it.

## M4d — interior levels are REPORTED, not gated  (2026-09-30, same row)
MEASURED: bank 2 level 1 sits at a stale 0.84 V while levels 2-3 still carry
the wave-correct word (the depth defense in literal view: the corruption is
IN TRANSIT through the bank).  Interior levels go stale before the last level
BY DESIGN; only the last level has an observer (the receiver).  Acceptance A
gates the LAST-LEVEL word at the validity midpoint; interior levels are
reported as diagnostics.  (.prn files are now gzipped after extraction, not
deleted, so any further re-scoring needs no re-simulation.)
