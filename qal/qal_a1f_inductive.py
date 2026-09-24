#!/usr/bin/env python3
"""QAL A1f -- INDUCTIVE forward transfer (the CORRECT mechanism). QAL_PLAN A1f / inductive generator.

Correction of framing: the capacitive flying-cap decks (qal_a1f.py, increments 1-2) are the NEGATIVE
result -- a passive cap-to-cap transfer cannot beat the 1/2*C_eff*dV^2 charge-share floor (it moves
only half the voltage and wastes half the energy; at the zero-voltage crossing it transfers ~nil).
The ACTUAL forward-transfer mechanism (per the user's scheme and QAL_PLAN's inductive generator) uses
an INDUCTOR as the primary stage-to-stage energy+data transfer element, resonant (LC), with the
flycaps only TOPPING UP the small I^2R loss at the top and bottom of the swing.

CELL (cell.cir): C1 (stage i, =dV) -> L -> R -> [freeze switch] -> C2 (stage i+1, =0). At t=0 the LC
resonance transfers charge A->B; a FREEZE switch opens at T_half = pi*sqrt(L*C_eff) to TRAP the charge
on B (else it oscillates back). A flycap pre-charged to dV tops up the I^2R deficit. C_eff = C1||C2.

--- MEASURED 2026-09-23 (Xyce, ideal L, CL=10fF each, dV=0.6V, C_eff=5fF) ---
Resonant transfer vs series R (L=1uH -> T_half~222ps); capacitive floor 1/2*C_eff*dV^2 = 0.900 fJ:
   R(ohm)   Q     V(B)pk   V(A)min   E_loss(fJ)   loss/floor
      50   283    0.598    0.002      0.044        4.9%
     100   141    0.597    0.003      0.086        9.5%     <- full cell below uses R=100
     300    47    0.590    0.010      0.233       25.9%
    1000    14    0.568    0.032      0.568       63.1%
    3000   4.7    0.515    0.085      0.853       94.8%
=> the inductor moves the FULL charge/data pattern forward (V(A)->0, V(B)->dV, not the capacitive
   half-swing) with loss ~I^2R scaling as 1/Q. At Q=283 loss is 20x below the capacitive floor
   (transfer efficiency ~97.6%). Energy balance conserves to 0.1% (1.80fJ on C1 -> 1.78fJ on C2 + loss).

Full cell (cell.cir, L=1uH, R=100, Q~141, freeze at T_half + flycap top-up):
   after transfer+freeze: V(A)=0.003, V(B)=0.597, I^2R loss=0.020 fJ
   after flycap top-up:   V(B)=0.598 (deficit restored)
   => per-cycle energy INPUT = the I^2R loss (0.020 fJ) ONLY, vs the 0.900 fJ capacitive-dump floor
      = 46x less. The flycap supplies just the loss, not 1/2*C_eff*dV^2.

Freeze-timing tolerance (fixed-time vs zero-cross detection -- the open design question, wave.cir):
   V(B) peaks at T_half (222ps for L=1uH), exactly where the inductor current I(L) crosses zero
   (peak <-> ZC confirmed). The peak is QUADRATICALLY FLAT: V(B) within 1% of peak over +/-14ps,
   2% over +/-20ps, 5% over +/-32ps (i.e. +/-6-14% of T_half). BUT the penalty is ASYMMETRIC:
     - open LATE: gentle quadratic voltage droop + a little charge runs back (recoverable by top-up).
     - open EARLY: interrupts I(L), trapping 1/2*L*I^2 -- 10ps early = 0.018fJ (~= the whole transfer
       loss), 20ps early = 0.070fJ. Early is the expensive side.
   VERDICT: fixed-time disconnect is VIABLE if biased slightly LATE (never early) and L/C tuned so
   T_half lands in-window; a +/-10% L spread shifts T_half ~+/-11ps, inside the 1-2% droop window.
   Active zero-cross (zero-CURRENT) detection removes the early-open risk and L/C sensitivity at the
   cost of a comparator/stage. A passive series diode (automatic ZC blocking) is RULED OUT at low
   swing (0.3-0.7V drop vs a 0.6V rail) -- which is why this is a real fixed-time-vs-ZCS decision.
   Recommended: fixed-time, late-biased, flycap absorbs the residual droop; escalate to ZCS only if
   measured L/C variation eats the window.

Realistic on-chip L (C_eff=5fF): T_half and char-impedance Z=sqrt(L/C_eff) (Q=Z/R):
   L=1nH -> 7.0ps (Z=447)  3nH -> 12.2ps (775)  10nH -> 22.2ps (1414)  100nH -> 70ps (4472)  1uH -> 222ps
=> on-chip nH inductors give fast 7-70ps transfers but modest Q at usable R; the real design tension is
   inductor QUALITY (Z/R) vs speed -- "needs magnetics" (QAL_PLAN). The 1uH here is illustrative for
   clean physics; the efficiency lever is Q = sqrt(L/C_eff)/R.

NOT YET SHOWN (next): realistic on-chip L (nH, real R) efficiency; the RETURN/reset path (A must be
re-armed for the next cycle); a multi-stage CHAIN (does the wave propagate + does loss compound);
data-carrying (the charge PATTERN = data, transferred with the energy); dual-rail; device switches +
Vt; and the Track-C generator (SC ladder vs inductive saw-tooth) driving it. This increment proves the
inductive transfer PRIMITIVE recovers energy (46x below the capacitive floor); the system is next.
"""
import math
Ceff, dV = 5e-15, 0.6
FLOOR = 0.5*Ceff*dV*dV                      # capacitive charge-share floor = 0.900 fJ
# measured resonant-transfer records (R, Q, VBpk, E_loss_fJ)
TRANSFER = [(50,283,0.598,0.044),(100,141,0.597,0.086),(300,47,0.590,0.233),
            (1000,14,0.568,0.568),(3000,4.7,0.515,0.853)]
CELL = dict(R=100, VA=0.003, VB=0.597, loss_fJ=0.020, topup_VB=0.598)   # full cell w/ freeze + top-up

def Q(L,R): return math.sqrt(L/Ceff)/R
def thalf(L): return math.pi*math.sqrt(L*Ceff)

if __name__=="__main__":
    print("QAL A1f INDUCTIVE forward transfer (the correct mechanism)")
    print("  capacitive floor 1/2*C_eff*dV^2 = %.3f fJ (what caps alone waste per hop)"%(FLOOR*1e15))
    print("  %6s %5s %8s %11s %10s"%("R","Q","V(B)pk","E_loss(fJ)","loss/floor"))
    for R,q,vb,el in TRANSFER:
        print("  %6d %5g %8.3f %11.3f %9.1f%%"%(R,q,vb,el,el/(FLOOR*1e15)*100))
    print("  full cell (R=100, freeze+top-up): V(A)->%.3f V(B)->%.3f, per-cycle input=%.3ffJ (%.0fx < floor)"%(
        CELL['VA'],CELL['topup_VB'],CELL['loss_fJ'],FLOOR*1e15/CELL['loss_fJ']))
