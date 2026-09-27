* sg13lv_compat with a WORKING temperature knob.
* MEASURED: (1) global .OPTIONS DEVICE TEMP never reaches the PyMS-compiled PSP103
* (identical zeros at 0/27/85C, cached .so all TR=27); (2) model-card dta=58 is
* silently DROPPED (DTA absent from the .so.params __GIVEN__ list -- Xyce registers
* DTA instance-level only); (3) instance dta=58 WORKS (Id 321.7 -> 305.0 uA).
* So: corner = global .param GDTA picked up as every instance's default.
.subckt sg13_lv_nmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0 dta={GDTA}
M1 d g s b sg13g2_nmos W={w} L={l} DTA={dta}
.ends
.subckt sg13_lv_pmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0 dta={GDTA}
M1 d g s b sg13g2_pmos W={w} L={l} DTA={dta}
.ends
