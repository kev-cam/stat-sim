#!/usr/bin/env python3
import math
CT=359.79e-15
Qb, band_tank, band_rail = 33.95e-15, 0.09660, 0.0902   # MY measurements
Qb32, band_tank32 = 35.44e-15, 0.0748/0.93373
T_PULSE, T_CYCLE = 64.064, 1600.0
K = T_CYCLE/T_PULSE
c_tap = 5.51e-15                      # MEASURED from the width sweep
MIM = 1.5                             # fF/um^2, MEASURED-FROM-PDK
A_mux, A_buck, A_tsw = 18.85, 24.04, 36.52

print("="*78); print("(e) AREA LEDGER -- my own arithmetic, two inductor models"); print("="*78)
C1 = Qb*(T_PULSE/T_CYCLE)/band_tank
a1 = C1*1e15/MIM
print(f"  marginal tank per unit N: C_1 = {C1*1e15:.2f} fF -> a_1 = {a1:.2f} um^2   [DERIVED]")
print(f"  (balance run: C_1 = 14.72 fF, a_1 = 9.81 um^2)\n")
for tag,A_ind,nr in (("PDK DEFAULT winding w=2u s=2.1u nr=2 (the balance run's choice)",9679.3,2),
                     ("smallest LEGAL winding w=2u nr=3 (PDK inductor_minD enforced)",4374.0,3)):
    Ncross = (A_ind+A_buck)/a1
    print(f"  {tag}")
    print(f"    A(1 nH) = {A_ind:,.0f} um^2  ->  area crossover N = {Ncross:.0f}")
print()
print("  charge ceiling from (f): N = 16 - 26 depending on R and phase locking")
print(f"  -> the crossover is {469/26:.0f}x to {1035/16:.0f}x ABOVE the ceiling. "
      "AREA IS NEVER BINDING.")
print(f"  even a 1 nH inductor 10x smaller than the PDK default (968 um^2) gives")
print(f"  crossover N = {(968+A_buck)/a1:.0f}, still {((968+A_buck)/a1)/26:.0f}x above the ceiling.")
print("  S5 CONFIRMED.\n")
print("  THE RATIO THE BALANCE RUN DREW ITS HEADLINE CORRECTION FROM:")
print(f"    15 nH / 1 nH at the PDK DEFAULT nr=2 : 756,128 / 9,679 = {756128/9679:.1f}x")
print(f"    each at its own smallest LEGAL winding: 18,174 / 4,374 = {18174/4374:.1f}x")
print(f"    a designer's realistic pick (nr=8 / nr=3): 25,758 / 4,374 = {25758/4374:.1f}x")
N=24
print(f"\n    at N={N}:  saving = {N-1} x A(1nH) ; transfer bill = {N} x A(15nH)")
for tag,a1n,a15 in (("PDK default nr=2 (balance run)",9679,756128),
                    ("realistic nr=3 / nr=8",4374,25758)):
    print(f"      {tag:<32} saved {(N-1)*a1n:>10,.0f} um^2  of {N*a15:>11,.0f} "
          f"= {(N-1)*a1n/(N*a15)*100:5.1f}% of the inductor bill")

print()
print("="*78); print("(d cont.) SHARED-NODE COST vs VISIT ORDER  [DERIVED from measured c_tap]"); print("="*78)
for N in (4,8,16,24,32,64):
    Cs = N*c_tap
    per_visit_order = Cs*2*band_tank/N *1e15
    per_visit_rand  = Cs*band_tank/3 *1e15
    print(f"   N={N:3d}  C_shared={Cs*1e15:7.1f} fF   "
          f"visit-in-voltage-order {per_visit_order:6.2f} fC/visit   "
          f"arbitrary order {per_visit_rand:6.2f} fC/visit   "
          f"ratio {per_visit_rand/per_visit_order:4.1f}x")
print("   -> voltage-ordered service makes the shared-node cost INDEPENDENT of N (it amortises).")
print("      Arbitrary order makes it proportional to N (it does not).")
print("      Plain round-robin over uniformly phase-staggered banks IS approximately voltage-ordered.")
print("      WEIGHTED round-robin -- the balance run's recommendation -- deliberately breaks that order.")
