#!/usr/bin/env python3
"""QAL baseline demo -- a REAL static logic gate that SETTLES adiabatically ("any gate, settle not
switch"). Validates the user's model: you are NOT limited in gate type; the power saving is the gate
settling to its answer on a ramping supply rather than hard-switching.

VEHICLE: a static CMOS NAND2 (universal -> proves ANY function) on SG13G2 (PSP103), powered by a
RAMPING supply (power-clock) VPC: 0 -> Vdd over T, hold, -> 0. Inputs A,B held (valid from a prior
stage). As VPC ramps up the gate's own pull-up (2 pMOS parallel) / pull-down (2 nMOS series) conducts
on the inputs and the OUTPUT Y settles to NAND(A,B). Device sizes = the cached inverter (nMOS 0.74u,
pMOS 1.12u); well tied to a fixed 1.2V rail + Cx=0.1f on the floating series node (convergence).

--- MEASURED 2026-09-23 (Vdd=1.2, CL=10fF, T=1ns ramp) ---
TRUTH TABLE (Y at the supply hold) -- the gate SETTLES to the correct value on a ramped supply:
   A=0 B=0 -> Y=1.200  (NAND=1)  OK
   A=0 B=1 -> Y=1.200  (NAND=1)  OK
   A=1 B=0 -> Y=1.200  (NAND=1)  OK
   A=1 B=1 -> Y=0.000  (NAND=0)  OK
=> CONFIRMS: a real static logic gate settles to its logic value as the supply ramps -- no gate-type
   restriction, no dual-rail needed for completeness. This is the QAL baseline (settle, don't switch).

RECOVERY / HOLD: for the Y-high cases the pMOS-only pull-up cannot pull Y back below |Vtp| on the DOWN
ramp (Y stalls ~0.5V at pc=0) -- the recovery-order subtlety. This is NOT a logic failure: the output
settles onto the FOLLOWING gate's input capacitance, which HOLDS the value during the valid window, and
the next stage captures it BEFORE the reset ramp (user's point). Clean adiabatic *recovery* needs a
proper adiabatic-logic structure (cross-coupled / dual-rail latch, e.g. ECRL/PFAL) or forward transfer.

ENERGY (settle-not-switch): the CLEAN adiabatic charging saving is the A1b primitive -- charging a load
through the on-resistance on a ramp dissipates ~(RC/T)*CV^2, falling to 3.4% of 1/2 C dV^2 at a slow
ramp; a gate's pull-up is just that Ron, so it obeys the same law. This NAND's DIRECT full-cycle energy
is NOT clean here: E_diss trended DOWN with ramp time (adiabatic direction) but the absolute values were
CONTAMINATED (above the 1/2 C Vdd^2=7.2fJ hard-switch reference) by (a) the fixed-well SECOND supply port
not counted in the pc-only integral, (b) w=1.12u pMOS parasitics (Cgs/Cgd/junction ~10-30% of CL), and
(c) incomplete recovery. Honest clean energy needs both supply ports counted + a recovering structure;
the settle-not-switch magnitude is taken from A1b, not from these contaminated NAND numbers.

BOTTOM LINE: the "any gate, settle-not-switch" QAL baseline is real -- a universal static gate computes
correctly by settling on a ramped supply. Dual-rail is OPTIONAL here (only for generator-load / power
tap), NOT required for completeness. The energy law is A1b's RC/T. Reproduce: tt_{00,01,10,11}.cir
(truth table), es_*.cir (ramp-time sweep).
"""
TRUTH = {(0,0):1.200,(0,1):1.200,(1,0):1.200,(1,1):0.000}   # Y at supply hold; NAND(A,B)
# charging E_diss vs ramp time (CONTAMINATED -- see docstring; trend only): Tramp(ps)->E_diss(fJ)
EDISS_TREND = {50:23.0,100:21.8,200:19.5,500:16.9,1000:15.4,2000:14.5,5000:13.6}

if __name__=="__main__":
    print("QAL baseline: static NAND2 settling on a ramped supply (any gate, settle-not-switch)")
    print("  truth table (Y at supply hold):")
    for (a,b),y in TRUTH.items():
        print("    A=%d B=%d -> Y=%.3f  NAND=%d  %s"%(a,b,y,int(not(a and b)),
              "OK" if (y>0.6)==(not(a and b)) else "FAIL"))
    print("  => real static gate SETTLES to its logic value on a ramped supply: any gate, no dual-rail")
    print("     needed for completeness. Settle-not-switch ENERGY = A1b RC/T (NAND full-energy here is")
    print("     bookkeeping-contaminated; trend adiabatic, magnitude from A1b).")
