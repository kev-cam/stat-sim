#!/usr/bin/env python3
"""QAL A1b — adiabatic recovery on real silicon (QAL_PLAN.md A1b).

Question: does adiabatic (slow-ramp) recovery actually reduce energy on a real SG13G2
device, and what is the RC/T coefficient the operating map (../gpu/vortex_three_backend.py)
and the partitioning rule a_crit=2(RC/T)/eta depend on?

Setup: an ideal trapezoid rail ramps 0->dV over time T, drives an SG13G2 nMOS switch
(gate held on) into a load C_L, then ramps back to 0. The device's parasitic caps recover
reactively (~100% charge), so charge-recovery is NOT sensitive to the loss (an early attempt
read >100% recovery for exactly this reason). The adiabatic loss lives in ENERGY, so we
measure the net energy delivered by the source over a full cycle,
    E_cyc = INTEGRAL over cycle of  -V(rail)*I(Vrail) dt,
which equals the dissipation because the network returns to its initial state (reactive
energy nets to zero). E_cyc -> 2*(RC/T)*C*dV^2 in the adiabatic (T >> R_on*C_L) regime.

Reference: a hard step dissipates C*dV^2 per cycle (1/2 C dV^2 each edge). Recovery is the
ratio E_cyc / (C*dV^2): the smaller, the more adiabatic.

--- MEASURED 2026-09-23 (SG13G2/PSP103 tt, W=0.74u L=0.13u, dV=0.6V, C_L=10fF) ---
   T(ps)   E_cyc(fJ)   E/CdV^2   Vpk(V)     (Vpk saturates -> C_L fully charged)
     20      2.2263      61.8%    0.388      RC-limited: C_L can't keep up
     50      2.1709      60.3%    0.477
    100      1.6867      46.9%    0.526
    200      1.1785      32.7%    0.561
    500      0.6447      17.9%    0.590
   1000      0.4060      11.3%    0.599      <- ~1 ns design ramp
   2000      0.2365       6.6%    0.600
   5000      0.1231       3.4%    0.600      deep adiabatic
Non-adiabatic reference C*dV^2 = 3.600 fJ/cycle.

RESULT: energy falls monotonically with ramp time to 3.4% of the hard-step limit at 5 ns
-> adiabatic recovery is real on SG13G2. The Vpk knee (~500-1000 ps) locates R_on*C_L,
giving RC ~= 60-85 ps, hence RC/T = 0.056 at a 1 ns stage ramp. That VALIDATES the
operating map's illustrative RC/T=0.05 (right to first order) and grounds a_crit=2(RC/T)/eta.
RC/T is ramp-time dependent: ~0.11 @500ps, 0.056 @1ns, 0.033 @2ns, 0.017 @5ns.

Caveat (QAL_PLAN sec.7): ideal trapezoid source only -- generator non-idealities (SC ladder
vs inductive) are Track C. Single stage; the chain coefficient k(dV) is A2.
"""
import re, os, sys

# baked measured record (T_ps, E_cyc_J, Vpk_V) from the 2026-09-23 sweep above
MEASURED = [(20,2.2263e-15,0.388),(50,2.1709e-15,0.477),(100,1.6867e-15,0.526),
            (200,1.1785e-15,0.561),(500,0.6447e-15,0.590),(1000,0.4060e-15,0.599),
            (2000,0.2365e-15,0.600),(5000,0.1231e-15,0.600)]
C_L, dV = 10e-15, 0.6

def gen_deck(T_ps, compat_sp):
    """Emit an A1b Xyce deck for ramp time T_ps (ps). compat_sp = path to sg13lv_compat.sp."""
    T=T_ps*1e-3; up0,up1=1.0,1.0+T; hold_end=up1+2*T; dn1=hold_end+T; end=dn1+2.0
    step=min(0.5,T/40.0)
    return "\n".join([
      "* QAL A1b energy sweep T=%dps"%T_ps,
      '.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"',
      '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"',
      '.include "%s"'%compat_sp,
      "Vg g 0 1.2","Xsw rail g n 0 sg13_lv_nmos w=0.74u l=0.13u","Cl n 0 10f",
      "Vrail rail 0 PWL(0 0 %gn 0 %gn %g %gn %g %gn 0 %gn 0)"%(up0,up1,dV,hold_end,dV,dn1,end),
      "Bp p 0 V={-V(rail)*I(Vrail)}",
      ".tran %gp %gn"%(step,end),
      ".measure tran Ecyc INTEGRAL V(p) FROM=%gn TO=%gn"%(up0,end),
      ".measure tran Vpk MAX V(n)",".end",""])

def report(data):
    Estep=C_L*dV*dV
    print("QAL A1b adiabatic energy vs ramp time (SG13G2, dV=0.6V, C_L=10fF)")
    print("  non-adiabatic reference C*dV^2 = %.3f fJ/cycle"%(Estep*1e15))
    print("%7s %11s %9s %9s"%("T(ps)","E(fJ)","E/CdV^2","Vpk(V)"))
    for t,E,v in data: print("%7d %11.4f %8.1f%% %9.3f"%(t,E*1e15,E/Estep*100,v))
    for t,E,v in [d for d in data if d[0] in (1000,2000,5000)]:
        Ts=t*1e-12; RC=E*Ts/(2*C_L*dV*dV)
        print("  T=%dps: RC=%.1f ps, RC/T=%.4f"%(t,RC*1e12,RC/Ts))

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--run":
        # regenerate + re-run against a live Xyce (needs the SG13G2/PSP103 PDK + compat file)
        compat=sys.argv[2] if len(sys.argv)>2 else "sg13lv_compat.sp"
        import subprocess
        data=[]
        for t in [20,50,100,200,500,1000,2000,5000]:
            open("qal_e_%d.cir"%t,"w").write(gen_deck(t,compat))
            subprocess.run(["Xyce","qal_e_%d.cir"%t],capture_output=True)
            d={}
            for ln in open("qal_e_%d.cir.mt0"%t):
                m=re.match(r'\s*(\w+)\s*=\s*([-\d.eE+]+)',ln)
                if m: d[m.group(1).lower()]=float(m.group(2))
            data.append((t,d['ecyc'],d['vpk']))
        report(data)
    else:
        report(MEASURED)  # print the committed measured record
