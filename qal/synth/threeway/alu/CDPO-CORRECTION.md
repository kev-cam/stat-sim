# CORRECTION: alu_direct_cdpo.v's completion signal is not delay-insensitive-safe

Found by the polysynth skeptic (2026-09-26), reproduced independently by the main session:
`verify_alu_direct.py` CHECK 4 (input-completeness: 1 of 462 input bits held NULL) gives
**259/400 premature 'done'** on this netlist — identical on the polysynth-emitted and committed
copies, so inherited, not a regression.

CAUSE: PO-scope completion detection on a 43%-MUX block. Mux cones have no input-complete
dual-rail form (proven minimal-form search, mylex SELECTION-RULE.md:209-210), so a completion
tree that observes only primary outputs can assert before unselected inputs arrive.

WHAT STANDS: energy composition (the 523.7 pJ/op row), hazard and NULL-return checks, and
sha_slice (which passes the full verifier). WHAT IS DOWNGRADED: the EMITTABLE status of PO-scope
CD on mux-heavy blocks — until the CD scope covers register-D inputs (the 681-cell po+regD tree)
or presence augmentation lands, this netlist's 'done' must not be used as a QDI handshake.
