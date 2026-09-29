import math
# --- adjudicated inputs (units: fC, fF, V, ps, um2) ---
CT      = 359.79      # fF committed tank
Qb      = 33.055      # fC MEASURED settled, verified from sk_droop8.cir.prn @1400ps
Qb_r32  = 33.874      # fC MEASURED settled, sk_droop8_r32.cir.prn
g       = 0.93373     # V/V MEASURED incremental gain (skeptic pair); balance 0.93598
railband= 0.0902      # V  chosen band 0.7656 -> 0.6754
railband_r32 = 0.750204-0.6754
tankband= railband/g
tankband_r32 = railband_r32/g
store   = CT*tankband          # fC
store_r32 = CT*tankband_r32
K       = 1600/64.064
Kloc    = K*0.793              # phase-locked H=4 coverage
c_tap   = 5.51                 # fF MEASURED (lower bound, ad/as/pd/ps zeroed)
print(f"tankband={tankband*1e3:.2f} mV  store={store:.2f} fC   r32: band={tankband_r32*1e3:.2f} store={store_r32:.2f}")
print(f"K={K:.3f}  K_locked={Kloc:.2f}")
for nm,k,st,q in [("free phases, R=10  (committed)",K,store,Qb),
                  ("free phases, R=31.76 (PDK)",K,store_r32,Qb_r32),
                  ("H=4 locked, R=10",Kloc,store,Qb),
                  ("H=4 locked, R=31.76",Kloc,store_r32,Qb_r32)]:
    print(f"  ceiling {nm:34s} = {k*st/q:6.2f}")
CEIL = K*store/Qb
print()
# --- shared node ---
pitch = {"PDK default nr=2 (955 um)":955.4, "realistic nr=8 (176 um)":176.3}
for pn,p in pitch.items():
    for cpl in (0.05,0.15,0.25):
        Nb=24; spine=Nb*p; Cs_wire=spine*cpl; Cs_tap=Nb*c_tap
        print(f"  N=24 spine {pn:28s} {spine/1000:6.2f} mm @ {cpl} fF/um -> {Cs_wire:8.1f} fF wire vs {Cs_tap:6.1f} fF taps  ({Cs_wire/Cs_tap:5.1f}x)")
print()
# --- per-visit shared-node cost, two orderings ---
def csn_ordered(ceff): return 2*ceff*tankband           # fC, N-invariant
def csn_arb(ceff,N):   return N*ceff*tankband/3
for label,ceff in [("taps only (5.51 fF)",c_tap),("taps+spine @176um,0.15fF/um (31.9 fF)",c_tap+176.3*0.15)]:
    print(f"  {label}: ordered {csn_ordered(ceff):5.2f} fC/visit (any N) | arbitrary N=24 {csn_arb(ceff,24):5.2f} | N=64 {csn_arb(ceff,64):6.2f}")
print()
# --- N_max curve ---
def nmax_ordered(q,ceff):
    return min(K*q/(Qb+csn_ordered(ceff)), CEIL)
def nmax_arb(q,ceff):
    a=ceff*tankband/3; b=Qb; c=-K*q
    N=(-b+math.sqrt(b*b-4*a*c))/(2*a)
    return min(N,CEIL)
print("  q fC | ordered(taps) | arb(taps) | ordered(+spine) | arb(+spine)")
for q in [1,2,2.86,4.55,5,9.258,15,21.98,30,35,41,50,63,75,100,124.5,251]:
    print(f"  {q:7.2f} | {nmax_ordered(q,c_tap):7.2f} | {nmax_arb(q,c_tap):7.2f} | {nmax_ordered(q,c_tap+176.3*0.15):7.2f} | {nmax_arb(q,c_tap+176.3*0.15):7.2f}")
print()
# --- area ---
MIM=1.5  # fF/um2
A_tank=CT/MIM
C1 = Qb*(64.064/1600)/tankband     # fF of tank per unit N (autonomy term)
a1 = C1/MIM
A_mux=18.8463; A_buck=24.0448; A_txsw=36.5212
IND={"PDK default nr=2":(9679.7,756128.0),"realistic nr=8/nr=3":(4374.2,25758.3),"smallest legal nr=10/nr=3":(4374.2,19681.3)}
print(f"A_tank={A_tank:.1f} um2  C_1={C1:.2f} fF  a_1={a1:.2f} um2/N  ceiling={CEIL:.1f}")
for nm,(Lr,Lt) in IND.items():
    xover=(Lr+A_buck)/a1
    print(f"\n  --- {nm}: recharge L {Lr:.0f}, transfer L {Lt:.0f}  ratio {Lt/Lr:.1f}x   area crossover N={xover:.0f}")
    for N in (8,16,20,24,26):
        Ctk=max(CT,N*C1); At=Ctk/MIM
        own = N*(Lr+A_buck+At)
        shr = (Lr+A_buck)+N*(At+A_mux)
        blk_own = N*(Lt+A_txsw)+own
        blk_shr = N*(Lt+A_txsw)+shr
        print(f"    N={N:3d} recharge-block own {own:10.0f} shared {shr:9.0f} save {own-shr:9.0f} ({own/shr:5.2f}x) | whole block save {100*(blk_own-blk_shr)/blk_own:5.2f}%")
