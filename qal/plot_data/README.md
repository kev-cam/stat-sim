# Plot data — SG13G2 energy–delay map

All on IHP SG13G2 130 nm, Xyce/PSP103, energy by supply-current integral or exact capacitor
energy. No Liberty power tables, no VCD-derived power.

`P[uW] = E[fJ] * f[GHz]` exactly, which is why constant-energy lines are unit-slope on the log-log plot.

## Files
- `plot_points.csv` — every point on both charts (gate level and block level)
- `qal_path_gate_split.csv` — differential recovery of transfer-path vs gate-settling loss
- `qal_functional_settling.csv` — the functional cliff: does the gate actually settle?

## Things that will bite you if you re-use these
1. **dV = 0.6 V is functionally INVALID** — the bank rail reaches only 0.382 V, below the ~0.4 V
   device threshold, and the gate output settles to just 64% of the rail. It is the lowest-energy
   QAL point and it does not compute. `functionally_valid` marks it.
2. **The async QDI block figure is 7230 fJ, not 21930 fJ.** The earlier value applied alpha=1.0 to
   all 524 cells; DIMS minterms are mutually exclusive so exactly one of four fires (alpha=0.250).
   QDI is 31x CMOS, not 94x. It is also logic-only — completion detection is excluded.
3. **The QAL block point is a projection**, composed as per-gate-settle energy x gate count x depth.
   Only the gate-level QAL points are measured.
4. **The dV = 1.2 V row of the split is not usable** — the quiescent reference returned a negative
   (unphysical) E_hop because its trajectory diverges from the working one.
5. **Energies here are integral-free.** `.measure INTEGRAL V(<B-source>)` was found to under-report
   by 11-44% against the exact linear-cap energy drop, so all energies use exact quantities:
   1/2*C*(Vi^2-Vf^2) for linear caps and a slow-ramp calibration curve E_stored(V) for the
   nonlinear gate bank.
6. **Speed at gate level is 1/delay for a single stage**, not a system clock. The block chart is the
   1/(depth x delay) case.
