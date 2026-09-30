# qal/eyebeat amendments — each forced by a measurement or an environment fact

## B1 — IC1 first attempt used the wrong committed zeros file (my error, caught by the byte-identity check)
`zeros_m10_dv1200.json` is the T_probe=120 reference; the committed headline row
was probed at its OWN T (banktank A7): `zeros_m10_dv1200_T200_H4.json`.
First attempt kept in `IC1_wrongzeros.json` / `ic1_wrongzeros/` — it is an
unplanned sensitivity measurement: sub-ps changes in the commanded switch-open
instants move banks 2–4 rails by 0.6–1.1 mV (bank 1, ideal-source-fed, exact).
With the correct file: deck byte-identical, 440/440 keys ≤ 1e-6, worst 3.1e-07.

## B2 — the pre-registered oddeven4-at-own-T probe protocol FAILS at short T; replaced by NEWTON-ON-THE-ROW (measurement-forced)
Measured at T = 60 ps, dV = 1.65:
  1. oddeven4 return probes report NO ZERO: the probe transient window is
     `2.6 * TZ_ANCH = 170 ps` with TZ_ANCH = 65.5 ps, a dv1.2 anchor; at
     dV = 1.65 the measured return zeros run 144–170+ ps and fall outside it.
  2. Even the FULL 8-run sequential probe leaves 12.7 uA at the commanded opens
     (A6 budget 1 uA): at T < ~130 ps the rise windows of adjacent banks
     OVERLAP (c-spacing 60 < tzr ~ 125 ps), so the sequential protocol's
     environment (later banks IDLE during the probe) no longer matches the row
     (later banks RAMPING, coupling through the cell gate loads). The protocol's
     validity condition — non-overlapping windows — held at every committed
     operating point and breaks here for the first time.
REPLACEMENT (applied at EVERY T for uniformity): seed zeros from the sibling
qal/eye measured zeros at T=200 (or an own full8 measurement where one exists),
then iterate the ROW itself: read the conducting current's zero crossing (or
its short linear extrapolation) near each commanded open from the row waveform,
correct each zero (trust region +/-10 ps/iter), re-run, until the UNCHANGED A6
gate (|I(L)| <= 1 uA at every commanded open) passes; max 4 iterations, else
the row is excluded (declared F1). This measures every zero IN the row's own
environment — which is what the sequential protocol was approximating.
The A6 gate itself is untouched.

## B3 — probe artifacts from the abandoned first protocol
T60/P1, T60/P2, T300/* hold probe/row files from the killed first-protocol
sweep; removed before the relaunch. T60/P0's full8 `zeros.json` is kept as the
Newton seed for that lane (it is a legitimate own-T measurement; its 12.7 uA
row residual is what B2 explains).
