# The gate-drive question — and why it splits MUX2 from XOR2

A pass-transistor **XOR2 is the same netlist as a pass-transistor MUX2**:
`Y = A ? Bbar : B`. There is no separate "nMOS XOR cell" to build. What differs
is **who drives the pass-transistor gates**:

* **MUX2** — the select is *control*. It is generated once and shared across the
  whole word, so it can legitimately live on the 1.5 V switch rail the campaign
  already runs (`VTSUP`/`VHI` = 1.5 V in the committed decks).
* **XOR2** — one **operand** must drive the gates. An operand is data, and QAL
  data arrives at the **rail** level (0.68–1.33 V), not at 1.5 V.

Solving `V* = VGH - Vtn(V*)` on the MEASURED Vtn(V_sb) curve from part (a):

| gate drive VGH | delivered pass ceiling V\* | what it is |
|---|---|---|
| **1.5 V control rail** | **0.8832 V** | MUX2 select |
| tank-fed rail 1.400 V | 0.7914 V | |
| **tank-fed rail 1.326 V** | **0.7237 V** | XOR2 operand, tank-fed |
| **peer-fed rail 0.755 V** | **0.2060 V** | XOR2 operand, peer-fed |
| peer-fed rail 0.676 V (committed VBEND) | 0.1354 V | XOR2 operand, committed hop |

*(DERIVED by bisection on the measured curve; the transient measurement is the
arbiter of the delivered level, this fixes the ceiling it approaches.)*

## This is the campaign's A2 result, arriving again by a different route

An nMOS whose gate is driven by a signal at the same level as its own output
**is a source follower**. The committed `qal_a2` study measured exactly that
cell and found node levels collapsing ~0.39 V per hop with the binding bound
recorded as *"amplitude (source-follower Vt clamp, no positive fixed point +
near-Vt starvation), NOT charge attenuation"*, killed **topologically** and
surviving body removal.

The numbers above are the fixed point of that same map. At the peer-fed rail the
map `V -> V_rail - Vtn(V)` has its fixed point at **0.206 V**, far below the
~0.52 V an operand needs to be a usable gate drive on the next stage — so an
operand-gated pass chain has **no positive fixed point** and collapses, which is
precisely A2's verdict. That two independent studies in this campaign land on the
same mechanism from opposite directions is the strongest evidence here that it is
real and not a harness artefact.

## Consequence for the user's suggestion

The suggestion — "n-chan only muxes might work too" — says **muxes**, and that is
the case the 1.5 V control rail covers, with a ceiling of 0.883 V. The extension
to XOR is **not** automatic and the arithmetic above says it does not survive
without boosting the operand that drives the gates back up to the switch rail.
A booster is a real circuit with real cost (the committed boundary study's
cheapest level converter is 7.97 fJ/bit and 167.7 ps), and one is needed **per
XOR**, not per word — which is exactly the asymmetry that makes MUX2 attractive
and pass-XOR2 unattractive in this family.
