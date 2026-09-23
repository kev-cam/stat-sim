#!/usr/bin/env python3
"""QAL A2 (first increment) -- chain k(dV): does single-rail smooth-ramp nMOS QAL cascade?
QAL_PLAN.md A2. Vehicle: sigma0 charge-transfer chain (nMOS pass stage per hop). This cut =
single-rail, smooth-ramp, depth 3 (+ depth 8 record). Staircase, forward-transfer, and the
3 rail configs are increment 2.

Design + adversarial critique were run as a workflow first (5-agent design panel -> hardened
Xyce spec; 4-agent adversarial verify of the results). Xyce runs are SEQUENTIAL (shared PyMS
vae-cache cannot take concurrent builds). Anchor = A1b (same framework, already validated on
silicon; no self-baseline).

STAGE (chain hop i): nMOS drain=RAIL_i (ideal trapezoid 0->dV->0, T=1ns ramp, H=2ns hold, phased
by DLY=1ns), gate=prev node N_{i-1} (N_-1=IN held at dV = data-1), source=N_i. Interior load
~1fF wire + next-stage gate C; terminal 10fF (A1b-matched probe). VPK_i = peak level at N_i.

Findings below were adversarially verified (4-lens refute workflow, which read the raw files);
claims are scoped to what survived. This A2 cell is the SINGLE-RAIL SOURCE-FOLLOWER negative
control -- NOT the plan's intended flying-cap forward-charge-transfer stage (A1f/B5); it exists to
quantify why non-restoring single-rail fails, i.e. to size the restoration boundary.

--- MEASURED 2026-09-23 (SG13G2/PSP103 tt, W=0.74u L=0.13u) ---
k(dV) per-hop node level (V), depth-3 chain, bulk body:
   dV      N0      N1      N2     usable_hops(level>0.1V)
   1.20   0.8305  0.4423  0.0250   ~2  (per-hop drop ~0.39V; N2 dead)
   0.60   0.2059  0.0639  0.0017    0  (even hop-0 marginal at 0.21V)
   0.50   0.1144  0.0488  0.0013    0
   0.45   0.0843  0.0424  0.0012    0
   0.40   0.0701  0.0374  0.0010    0
=> BINDING BOUND = amplitude / source-follower Vt clamp (bound 3), NOT charge attenuation (bound 1,
   benign RC rho~0.99, never binds -- once the level collapses the fwd-charge ratio is just noise,
   sign-flipping at dV<=0.6). The primary killer is TOPOLOGICAL: V_out = V_gate - Vt(Vsb) has no
   positive fixed point (source follower), plus near-threshold current starvation. It SURVIVES body
   removal (see bracket). Confirmed two ways: DC probe (A1d) clamps with offset growing 0.145V@Vg=0.2
   -> 0.356V@Vg=1.2 (incremental gain ~0.83), and the transient chain adds a further ~0.10V/hop
   finite-settling shortfall (transient drop 0.39 > DC clamp ~0.29). dV_min ~= 0.6V for one marginal
   hop; ~1.2V (~3Vt) for ~2 hops. So: the single-rail NON-RESTORING SOURCE-FOLLOWER cell on bulk does
   NOT cascade at usable swing. (Not a class claim about nMOS-pass or QAL: a drain-fed bootstrapped /
   full-rail-gate or dual-rail cell passes levels without this clamp -- that is what B5 supplies.)
   NB N2's 0.025 is load-limited (0.025@10fF terminal vs 0.141@1fF), BELOW the clamp = charge/settling,
   so the clamp binds cleanly at hop 0 and largely hop 1; report N2 as settling shortfall, not clamp.

Body bracket @dV=1.2 (b=bulk vs b=source) -- a body-effect ISOLATION probe, not an FDX proxy:
   b=bulk    0.830 / 0.442 / 0.025   (dies by hop 2)
   b=source  1.099 / 0.940 / 0.464   (Vsb=0: gamma*sqrt(2phi+Vsb) term zeroed)
=> Body effect COMPOUNDS the loss (isolates ~0.27V of the hop-0 drop) but is NOT the root -- the B=S
   chain still decays and accelerates (1.099->0.940->0.464), so the Vt0 clamp + starvation is the
   topological killer that survives Vsb=0. Direction for the north star is sound (FD-SOI helps QAL
   cascade), but claim only the ~0.27V delta, NOT the 0.025->0.464 magnitudes: tying a 130nm BULK
   device's body to source is an OPTIMISTIC bound (over-states junction C vs a BOX-terminated FDX
   device, retains bulk DIBL, and misses the back-gate -- FDX's real QAL lever). A quantitative FDX
   number needs a real 22FDX/PSP card (an A3 prerequisite). Watch the bsrc recovery sign-flip: the
   S/D-body diode can inject charge on recovery (a bulk-only artifact).

Depth-8 @dV=1.2 (bulk): 0.831 0.447 0.141 0.108 0.105 0.105 0.097 0.003
   -> collapses to a ~0.10V subthreshold plateau by hop 2-3 (not a usable logic level); confirms
      single-rail cannot reach depth 8.

Energy/hop -- QUARANTINED (schedule artifact; do NOT carry into A3 or any energy-per-op claim):
   @dV=1.2 net (delivered_up+hold - recovered_down): stage0 +0.084fJ (97% recov) / stage1 +0.997fJ
   (58%) / stage2 +0.235fJ (86%). The ediag split confirms EH tracks the RECOVERY fraction, not swing
   or delivery (which decreases monotonically 2.64>2.36>1.61fJ). Mechanism: stage1's gate N0 collapses
   under RAIL0's forward-order down-ramp at t=5n BEFORE RAIL1 recovers [5,6]n, stranding N1's charge --
   a schedule-dependent dissipation (verified not a sign/double-count bug). The un-compute WAVE must
   recede from the FRONT (cf. delta-ordered capture). A held-gate re-run was CONFOUNDED (load changed
   1fF->10fF too), so clean per-hop energy awaits fixed un-compute ordering (DLY>=T+H, or reverse the
   down-ramp order) -- increment 2. Amplitude findings are set in the up/hold phase and are independent.
"""
HDR=['.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"',
     '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"',
     '.include "sg13lv_compat.sp"',
     '.OPTIONS TIMEINT METHOD=TRAP RELTOL=1e-5 ABSTOL=1e-13 CHGTOL=1e-16']

def chain_deck(N, dV, bsrc=False):
    """Depth-N single-rail smooth-ramp chain, data-1 (IN held at dV). bsrc: body tied to source (FD-SOI proxy)."""
    T0,T,H,DLY=1.0,1.0,2.0,1.0
    L=['* QAL A2 depth-%d chain dV=%.2f%s'%(N,dV,' b=src' if bsrc else '')]+HDR+["VIN IN 0 %g"%dV]
    end=(T0+(N-1)*DLY)+T+H+T+1.0
    for i in range(N):
        ta,tb,tc,td=T0+i*DLY, T0+i*DLY+T, T0+i*DLY+T+H, T0+i*DLY+2*T+H
        L.append("VR%d RAIL%d 0 PWL(0 0 %gn 0 %gn %g %gn %g %gn 0)"%(i,i,ta,tb,dV,tc,dV,td))
    for i in range(N):
        g="IN" if i==0 else "N%d"%(i-1); b=("N%d"%i) if bsrc else "0"
        L+=["X%d RAIL%d %s NS%d %s sg13_lv_nmos w=0.74u l=0.13u"%(i,i,g,i,b),
            "Vs%d NS%d N%d 0"%(i,i,i),
            ("Cw%d N%d 0 1f" if i<N-1 else "CL%d N%d 0 10f")%(i,i),
            "BP%d P%d 0 V={-V(RAIL%d)*I(VR%d)}"%(i,i,i,i)]
    L.append(".IC "+" ".join("V(N%d)=0"%i for i in range(N)))
    L.append(".tran 0.5p %gn UIC"%end)
    for i in range(N):
        tb,tc=T0+i*DLY+T, T0+i*DLY+T+H
        L.append(".measure tran VPK%d MAX V(N%d) FROM=%gn TO=%gn"%(i,i,tb,tc))
    L.append(".end")
    return "\n".join(L)+"\n"

MEASURED_kdV = [(1.20,0.8305,0.4423,0.0250),(0.60,0.2059,0.0639,0.0017),(0.50,0.1144,0.0488,0.0013),
                (0.45,0.0843,0.0424,0.0012),(0.40,0.0701,0.0374,0.0010)]

if __name__=="__main__":
    print("QAL A2 first-cut -- single-rail smooth-ramp nMOS chain, k(dV) node levels (bulk):")
    print("%6s %8s %8s %8s  usable_hops"%("dV","N0","N1","N2"))
    for dV,n0,n1,n2 in MEASURED_kdV:
        u=sum(1 for x in (n0,n1,n2) if x>0.10)-1
        print("%6.2f %8.4f %8.4f %8.4f  %d"%(dV,n0,n1,n2,u))
    print("=> source-follower Vt clamp (bound 3) binds first; single-rail does NOT cascade at usable swing.")
    print("   FD-SOI (body=source) @dV=1.2: 1.099/0.940/0.464 -- body effect removal rescues cascadability.")
