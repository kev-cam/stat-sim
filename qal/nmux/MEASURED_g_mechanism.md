# (g) Why the committed nMOS-only TRANSFER SWITCH failed, and whether it carries over

The committed sweep `qal/swsweep/RESULTS.json` measured an nMOS-only transfer
switch at four widths and recorded it as failing at every one:

| design | w (um) | VA_open (V) | VBPK (V) | VBEND (V) | cells_burn (fJ) | IPK (uA) |
|---|---|---|---|---|---|---|
| nm40 | 40 | **0.6415** | 0.8531 | 0.5266 | 4.888 | 93.2 |
| nm20 | 20 | **0.4924** | 0.8140 | 0.5802 | 3.234 | 102.5 |
| nm10 | 10 | **0.3874** | 0.7858 | 0.6354 | 2.285 | 128.4 |
| nm5  | 5  | **0.3363** | 0.7618 | 0.6669 | 2.206 | 150.5 |
| *tg15p (the committed TG)* | 5n+10p | *0.0978* | 0.7374 | 0.6759 | 1.695 | 194.4 |

`VA_open` is the SENDING rail at the moment the switch opens; it must reach ~0.098 V.
It reaches 0.34–0.64 V. The committed verdict also records the switch charge
per phase: turn-on injects **+9.16 to +16.39 fC** into the bank (the TG injects
+6.26 fC and then takes most of it back at turn-off).

## The mechanism has three parts, and only one of them is about the threshold

The committed record's own summary is the key evidence: *"conduction margin
exists (Vgs ~0.9 V at the peak) yet the topology still fails on charge
dynamics."* The failure was **never** primarily a pass-level failure. Decomposed:

### (i) UNCANCELLED GATE-CHARGE INJECTION — shared in kind, not in size
A single nMOS whose gate swings 1.5 V dumps its channel + overlap charge into
whichever node it is connected to. In a transmission gate the nMOS and pMOS gate
transitions are complementary, so their injected charges have **opposite sign and
cancel to first order**. An nMOS-only switch has no partner, so the whole kick
lands on the signal node. In the transfer switch that kick was 9.2–16.4 fC into a
~36 fF bank — the committed note's "feedthrough pump", large enough to push VBPK
to 0.85 V (above the TG's 0.74 V) while the source rail still had not drained.
**MEASURED here**, linear in width, onto a 2 fF load at the tank rail:

| pass width | 0.15 um | 0.30 um | 0.60 um | 1.20 um | TG 0.60 um |
|---|---|---|---|---|---|
| injection | 9.5 mV | 20.1 mV | 39.9 mV | 70.8 mV | 50.7 mV |

**Verdict: CARRIES OVER, and it is the one real cost the pass form inherits.**

**CORRECTION — I had the disposal mechanism wrong.** My first draft of this file
argued the kick "lands on an idle node and is then overwritten". The waveform
says otherwise: the peak and the residue when the data arrives are **identical**
(39.949 vs 39.949 mV at 0.60 um). The kick does **not** decay, and the reason is
specific to QAL:

```
 t(ps)   V(sel)   V(o1)     V(yh)     V(rail)
 168.0   0.0000   0.00000   0.00000    0.0000
 170.0   1.5000   0.06588   0.00445   -0.0002     <- select edge
 195.0   1.5000   0.04001   0.03992   -0.0009     <- equalised, and STAYS
```

The injected channel charge splits between the mux output and the **driving
cell's output node**, and neither has a path to ground: the driving cell is a
pull-UP, so its only route is through its pMOS to **the rail, which before the
hop is a floating LC node, not a supply**. In a conventional static domain this
charge would simply drain into VDD/GND. In QAL there is nothing to drain into
until the rail arrives. On the pass-LOW side the residue is **−0.00001 V**,
because that cell is a pull-DOWN whose nMOS is on and which does have a real
ground beneath it.

So the honest statement is: **injection persists on pull-up-driven nodes and is
sunk on pull-down-driven nodes** — which is the *same* mechanism as the transfer
switch's "feedthrough pump", scaled down by `W` and by the load. It is tolerable
here (10–71 mV against a 1.3 V rail) and fatal there (9–16 fC into a 36 fF bank
during the transfer), but it is one mechanism, not two.

One further measured detail that cuts against the usual intuition: the
**transmission gate injects MORE, not less** (50.7 mV vs 39.9 mV at the same
0.60 um nMOS). A TG's complementary gate edges are supposed to cancel, and in a
static domain with a stiff supply they largely do — but here both legs' devices
inject into a node that cannot drain, and the nMOS and pMOS edges are neither
matched in strength nor simultaneous. So the cancellation argument, which is
correct in principle, does **not** rescue the TG in this harness.

### (ii) TOP-OF-SWING CONDUCTANCE COLLAPSE — shared, and it IS the pass-level question
As the low-side terminal approaches `VGH − Vtn(V_sb)` the channel starves. This
is exactly the ceiling measured in part (a): **V\* = 0.8832 V** at the campaign
criterion. In the transfer switch this shows up as the last part of the resonant
half-cycle being starved, so the LC never completes and bank A never empties.
**Verdict: CARRIES OVER in full.** It is the whole subject of parts (a) and (d),
and it is why the answer is rail-dependent.

### (iii) THE SENDING RAIL MUST BE LEFT DRAINED, AND A RESONANT CURRENT MUST BE
### INTERRUPTED BIDIRECTIONALLY — **does NOT carry over**
This is the part the numbers above actually measure, and it is a requirement a
logic mux simply does not have:

* A transfer switch is the series element of an **LC resonator**. It must carry a
  ~100–200 uA inductor current in *both* terminal-voltage orderings as V_A falls
  past V_B, and then interrupt it at the zero crossing. An off nMOS cannot hold a
  bidirectional standoff: the committed rows show B drooping 0.1–0.33 V back
  through the "off" device after opening.
* Its success criterion is **charge conservation at the source** — the sending
  rail must end at ~0 so its energy has moved, not been shared. That is what
  `VA_open` measures and what every nMOS row fails.
* A logic mux is **unidirectional into a small, passive gate capacitance**. Its
  source is held by a driving QAL cell that is *supposed* to stay at the rail; it
  is never asked to drain. It interrupts no inductor. Its success criterion is a
  **valid logic level**, not a drained source.

## So the answer to (g)
The committed nMOS-only transfer-switch failure is **not** transferable as a
verdict. Two of its three mechanisms — the drained-source requirement and the
bidirectional resonant interrupt — are properties of the *resonator*, not of
nMOS pass transistors, and a logic pass structure has neither. The third, gate
charge injection, does transfer but shrinks with the device width and the
question becomes whether the kick is small next to the signal, which is a
measurement, not an argument, and is made in part (d).

What the transfer-switch study **does** hand over intact is the threshold
ceiling. The committed record's line "conduction margin exists (Vgs ~0.9 V at the
peak)" was evaluated at a *bank peak of 0.61–0.85 V*, i.e. below V\* = 0.883 V —
so it was true there and is still true at the peer-fed rail. It stops being true
the moment the rail goes above V\*, which is precisely what the tank-fed
configuration does.

**Getting this wrong in the other direction would have been just as bad**: it
would have been easy to read "nMOS-only failed at every width" and conclude that
nMOS-only logic cannot work, when the measured cause of that failure was a
requirement logic does not impose.
