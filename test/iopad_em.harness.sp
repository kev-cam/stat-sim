* hot-spot EM stress harness for iopad_em.spef  (append to the instrumented deck).
* Drives the extracted pad-net parasitics so real current flows, then hot-spot
* reduces each segment's ammeter current to avg/rms/peak and screens for EM.
*
* Current loop:  VDD -(vdd_rail)-> drv_top -(Rpu)-> pad_drv -(pad_drv segs)->
*                PAD -(Rload)-> vss_bot -(vss_rail)-> VSS
* The driver is abstracted to its on-resistance Rpu (an IO output stage sourcing
* into a low-Z external load); the pulsed supply makes avg current < peak so the
* avg/rms/peak EM limits are exercised independently.
*
* Node names are the SPEF's own (pad_drv, drv_top, vss_bot, PAD, IN, sig_in_1).

.param ron=5 rload=30

VDD  VDD 0 PULSE(0 1.8 0 100p 100p 4.9n 10n)   ; VDDIO, ~50% duty, 100 MHz
VSS  VSS 0 0
Rpu  drv_top pad_drv {ron}                      ; output-driver on-resistance
Rload PAD vss_bot {rload}                        ; external load, returns via vss_rail
Cpad PAD 0 2p                                     ; pad + package capacitance

* pre-driver control input (small current -> sig_in stays well under EM limit)
VIN  IN 0 PULSE(0 1.8 0 100p 100p 4.9n 10n)
Cg   sig_in_1 0 5f

.options tran
.tran 20p 40n
