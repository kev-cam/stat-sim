#!/usr/bin/env python3
"""COMPOSED-FROM-MEASURED: direct-threshold sha_slice block energy from the measured
per-arc E(CL) models. Structure is DERIVED (cell mix); activity is the stated model.
Loads come from the SPICE-gold liberty pin caps (th_cells_sg13g2_spice.lib), pF->fF.
"""
from math import comb
W = 8
P = [comb(3, i)/8 for i in range(4)]          # popcount(a,b,cin) ~ Bin(3,1/2)

# MEASURED E(CL)=E0+k*CL, fJ  (this session, except th22/th12 = prior session)
M = {"th23_1of3": (0.0637, 0.0),   "th23_2of3": (53.1111, 1.7567),
     "th23_3of3": (48.7470, 1.7364),
     "th34_a":    (0.0805, 0.0),   "th34_w2p1": (65.4279, 1.8008),
     "th34_bc":   (6.0884, 0.0001),"th34_bcd":  (56.2279, 1.8268),
     "th22_both": (39.398, 1.7369),"th22_one":  (0.0072, 0.0),
     "th12_one":  (23.004, 1.4697)}

# pin caps (fF) from th_cells_sg13g2_spice.lib
C_TH23_C, C_TH34_A, C_TH12_IN, C_OUT = 3.079, 5.323, 2.11, 2.0

def mix(L, CL):  # L = [(prob,(E0,k))]
    return sum(p*(e0+k*CL) for p, (e0, k) in L)

# --- th23: fires iff popcount>=2 ---------------------------------------------
def e_th23(CL):
    return mix([(P[0], (0, 0)), (P[1], M["th23_1of3"]),
                (P[2], M["th23_2of3"]), (P[3], M["th23_3of3"])], CL)
# --- th34w2 sum rail, A=coutf asserted iff popcount<=1 -----------------------
def e_th34(CL):
    return mix([(P[0], M["th34_a"]), (P[1], M["th34_w2p1"]),
                (P[2], M["th34_bc"]), (P[3], M["th34_bcd"])], CL)
# --- th22 DIMS minterm: both rails match 1/4 of ops, exactly one 1/2 ---------
def e_th22(CL):
    return mix([(0.25, M["th22_both"]), (0.5, M["th22_one"]), (0.25, (0, 0))], CL)
# --- th12 rail collector: its rail is the selected one 1/2 of ops ------------
def e_th12(CL):
    return mix([(0.5, M["th12_one"]), (0.5, (0, 0))], CL)

carry_CL = C_TH23_C + C_TH34_A          # coutt -> next th23.C + this th34w2.A
items = [
    ("maj   th23  (2/bit, primary out)", 2*W, e_th23(C_OUT)),
    ("cpa   th23  carry, CL=%.2ffF" % carry_CL, 2*W, e_th23(carry_CL)),
    ("cpa   th34w2 sum, primary out",    2*W, e_th34(C_OUT)),
    ("ch    th22  minterms",             4*W, e_th22(C_TH12_IN)),
    ("ch    th12  collectors",           2*W, e_th12(C_OUT)),
]
tot = 0.0
print("%-38s %5s %12s %12s" % ("group", "n", "E/cell fJ", "E total fJ"))
for name, n, e in items:
    print("%-38s %5d %12.4f %12.2f" % (name, n, e, n*e)); tot += n*e
print("%-38s %5d %12s %12.2f fJ/op" % ("TOTAL direct-threshold sha_slice",
                                       sum(i[1] for i in items), "", tot))
print()
print("CMOS measured          232 fJ/op   -> direct-threshold async = %.2fx CMOS" % (tot/232))
print("DIMS async (524 cell) 7230 fJ/op   -> direct-threshold is    %.2fx cheaper" % (7230/tot))
print("QAL  projected        136.8 fJ/op")
