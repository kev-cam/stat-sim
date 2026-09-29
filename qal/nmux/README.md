# qal/nmux — nMOS-only pass logic for QAL, against a full-TG control

Answers the user's suggestion *"n-chan only muxes might work too"* by measuring
it, on the PSP103 SG13G2 device, in one harness with a transmission-gate control.

## Read in this order
| file | what |
|---|---|
| `PRE_REGISTERED.json` | acceptance + numbered predictions E1–E12, written and hashed before any deck existed (`PRE_REGISTERED.sha256`, `MTIME_BEFORE_FIRST_DECK.txt`) |
| `AMENDMENT.md` | every protocol change, what was pre-registered, what the data showed, and when relative to the runs it affects |
| `MEASURED_a_body.md` | **(a)** Vtn(V_sb) 0–1.3 V, body-effect coefficient, the pass ceiling |
| `DERIVED_gate_drive.md` | why MUX2 and XOR2 separate, and the ceiling for each gate drive |
| `MEASURED_bd_cells.md` | **(b)(d)** the cells, pass level, timing, energy, count and area |
| `MEASURED_c_chain.md` | **(c)** alternating pass/restore chain, separation by depth |
| `MEASURED_f_contention.md` | **(f)** static contention into the next static cell |
| `MEASURED_g_mechanism.md` | **(g)** the committed nMOS-only transfer-switch failure, and what transfers |
| `RESULTS.json` | everything machine-readable, with provenance |

## Harness
* Rail generators are the committed configurations: peer-fed =
  `qal/resv/h_I2_load691_L4` (VBEND 0.7546 V), tank-fed = the `ch_res20`
  reservoir arrangement (rail ~1.33 V).
* Instrument gates: **G1** Vtn(0) vs the committed 0.5239460 V; **G2** the
  committed peer deck re-run verbatim in this study's own PyMS cache. G3 dropped
  (AMENDMENT A8).
* Three separate meters per run — input charge from the driving cell, select
  gate drive, and any static supply. The nMOS-only cell has no static supply
  path; that meter reading zero is a pre-registered check (E8), not an assumption.

## Scripts
`vtb.py` (a) · `fit_body.py` (a) · `nm.py` deck builder · `run_cells.py` (b)(d)
gates + matrix · `stepcheck.py` (A5 obligation) · `cont.py` (f) · `chain.py` (c)
· `area.py` (d, DRC-grounded) · `assemble.py` → `RESULTS.json` ·
`run_all.sh` staged runner (**needs a warm PyMS cache — see AMENDMENT A6**).

## Caveats that apply to every number here
* `sg13lv_compat.sp` zeroes `ad/as/pd/ps`: junction capacitance is **absent**, so
  energies and settle times are **lower bounds**. The shim omits *twice* as much
  junction area for the TG as for the nMOS-only cell, so it flatters the TG more.
* The box was shared with other workflows throughout; time steps and the chain
  geometry were relaxed accordingly (A5, A7), each with the direction of the bias
  stated.
