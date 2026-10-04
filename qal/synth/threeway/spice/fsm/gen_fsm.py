#!/usr/bin/env python3
"""Self-timed static-CMOS accumulator vs clocked golden — energy-vs-duty fixture.

The reframe under test (workflow w2ltp7i1q conclusion): a SELF-TIMED STATIC-CMOS
state machine holds state and dissipates only on transitions, so it sheds the
clock floor at low duty — the real 'lower power' win, duty-shaped. Static-CMOS
(precharge-free) next-state logic, NOT domino. Edge-triggered DFF capture (master-
slave, no transparent-latch feedback race). Done = an in-kind replica delay
(bundled-data self-timing) that pulses the capture only on an actual op.

Two decks, same 4-bit accumulator (s <- s + x) built from SG13G2 stdcells:
  golden     : DFF CLK = free-running clock -> clocks EVERY cycle incl. idle
  selftimed  : DFF CLK = replica-delayed pulse, fired only on a req (op) edge
Same x and same op sequence -> state sequences must MATCH (functional differential).
Energy by supply-current integral over a window holding K ops at duty d; the
clocked deck pays its clock floor on idle cycles, the self-timed deck does not.
ONE Xyce at a time. Transient-only, gmin op-point init (no uic).
"""
import sys

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.include "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
"""
VDD = 1.2
NB = 4            # accumulator width


def accum_subckt():
    """4-bit accumulator: s <- s + x on CLK edge. Ports: x3..x0, CLK, RSTB, VDD, VSS,
    plus state outputs s3..s0. Ripple adder (static) + dfrbp register per bit."""
    s = [".subckt accum4 x0 x1 x2 x3 clk rstb s0 s1 s2 s3 VDD VSS"]
    # ripple adder: a=s (Q), b=x ; sum_i = a^b^c ; c_{i+1}=maj(a,b,c); c0=0
    cin = "VSS"
    for i in range(NB):
        a=f"s{i}"; b=f"x{i}"; axb=f"axb{i}"; sm=f"sum{i}"
        s.append(f"Xxab{i} {axb} {a} {b} VDD VSS sg13g2_xor2_1")        # a^b
        s.append(f"Xsum{i} {sm} {axb} {cin} VDD VSS sg13g2_xor2_1")     # a^b^cin
        if i < NB-1:
            ab=f"ab{i}"; acb=f"acb{i}"; co=f"c{i+1}"
            s.append(f"Xab{i} {ab} {a} {b} VDD VSS sg13g2_and2_1")      # a&b (generate)
            s.append(f"Xacb{i} {acb} {axb} {cin} VDD VSS sg13g2_and2_1")# (a^b)&cin (prop)
            s.append(f"Xco{i} {co} {ab} {acb} VDD VSS sg13g2_or2_1")    # cout
            cin=co
    # register: Q=s_i, D=sum_i, edge-triggered dfrbp (master-slave internal)
    for i in range(NB):
        s.append(f"Xff{i} s{i} sn{i} clk sum{i} rstb VDD VSS sg13g2_dfrbp_1")
    s.append(".ends accum4")
    return "\n".join(s)


def replica_done():
    """In-kind replica delay = a short static chain matching the 4-bit adder's
    worst-case carry settle, driving the capture pulse. buf chain (sized by
    measurement; start ~4 stages). Ports: req -> cap (one capture pulse per req)."""
    # req rising -> delayed rising (done) ; a pulse is made from req & !done_delayed
    s = [".subckt capgen req cap VDD VSS"]
    # replica delay chain (4 buffers ~ adder settle); then AND(req, delayed) edge
    s += [f"Xd0 d0 req VDD VSS sg13g2_buf_4",
          f"Xd1 d1 d0 VDD VSS sg13g2_buf_4",
          f"Xd2 d2 d1 VDD VSS sg13g2_buf_4",
          f"Xd3 done d2 VDD VSS sg13g2_buf_4",
          # capture = rising edge of done -> a DFF CLK that rises once per req.
          # simplest: cap = done (the DFF is edge-triggered; done rises once per req)
          f"Xcb cap done VDD VSS sg13g2_buf_2",
          ".ends capgen"]
    return "\n".join(s)


def pwl(points):
    dd=[]
    for t,v in points:
        if dd and abs(t-dd[-1][0])<1e-15: dd[-1]=(t,v)
        else: dd.append((t,v))
    return "PWL("+" ".join("%.5gn %.4g"%(t*1e9,v) for t,v in dd)+")"


def build(mode, duty_cycles, nops, name):
    """mode: 'golden' (free clock) or 'selftimed' (req-pulsed). duty_cycles = clock
    periods per op (1 = every cycle). nops actual accumulate operations. x = 1 (so
    state = running count, easy to check: s increments by 1 each op, mod 16)."""
    Tc = 1.5e-9                 # base cycle / op spacing
    tr = 0.08e-9
    Ttot = (nops*duty_cycles+1)*Tc
    s = [f"* {name}: {mode} 4-bit accumulator, {nops} ops, duty 1/{duty_cycles} cyc",
         HDR, accum_subckt(), replica_done(),
         f"VDDs VDD 0 {VDD}", "VSSs VSS 0 0"]
    # x = 0001. Self-timed: x0 constant 1 (capture only on req -> +1/op). Golden:
    # x0 DATA-GATED to op cycles (1 only on op cycles, 0 on idle cycles) so the
    # clocked accumulator does the SAME 6 increments as self-timed, while its clock
    # still toggles every cycle -> idle cycles burn the clock floor (the fair test).
    for i in range(1, NB):
        s.append(f"Vx{i} x{i} 0 0")
    if mode == "golden" and duty_cycles > 1:
        # x0 high for a FULL cycle before the op clock edge (>=1 ns setup so the
        # ripple sum is settled before capture) through just after it.
        pts = [(0, 0)]
        for k in range(nops):
            t = 0.5e-9 + (1+k*duty_cycles)*Tc   # op clock edge (warm-up cycle 0)
            r = max(0.0, t-Tc)                   # rise a full cycle early (clamp>=0)
            pts += [(r, 0), (r+tr, VDD), (t+0.4e-9, VDD), (t+0.4e-9+tr, 0)]
        pts.append((Ttot, 0))
        s.append("Vx0 x0 0 " + pwl(pts))
    else:
        s.append(f"Vx0 x0 0 {VDD}")              # every cycle is an op (duty 1) / self-timed
    # reset low for 0.3 ns then high
    s.append(f"Vrst rstb 0 PWL(0 0 0.3n 0 0.33n {VDD} {Ttot*1e9}n {VDD})")
    # the accumulator instance
    s.append("Xacc x0 x1 x2 x3 capnet rstb s0 s1 s2 s3 VDD VSS accum4")
    if mode=="golden":
        # free-running clock: rises every Tc, for the WHOLE window (idle cycles too)
        pts=[(0,0)]
        t=0.5e-9
        while t < Ttot-Tc*0.5:
            pts += [(t,0),(t+tr,VDD),(t+Tc*0.5,VDD),(t+Tc*0.5+tr,0)]
            t += Tc
        s.append("Vclk capnet 0 "+pwl(pts))
    else:
        # self-timed: req pulses ONLY on ops (every duty_cycles cycles); replica->cap
        pts=[(0,0)]
        for k in range(nops):
            t=0.5e-9 + (1+k*duty_cycles)*Tc
            pts += [(t,0),(t+tr,VDD),(t+Tc*0.5,VDD),(t+Tc*0.5+tr,0)]
        s.append("Vreq reqnet 0 "+pwl(pts))
        s.append("Xcap reqnet capnet VDD VSS capgen")
    # measure energy over the full window + print state + capture
    s += [f".tran 2p {Ttot*1e9:.4g}n",
          ".options device gmin=1e-13",
          ".options timeint reltol=1e-6 abstol=1e-12 delmax=5e-12",
          ".options nonlin-tran abstol=1e-12 reltol=1e-6",
          f".measure tran QVDD INTEG I(VDDs) from=0.4n to={Ttot*1e9:.4g}n",
          ".measure tran EVDD PARAM {-1.2*QVDD}",
          ".print tran format=noindex I(VDDs) V(s0) V(s1) V(s2) V(s3) V(capnet)",
          ".end", ""]
    import json
    meta={"mode":mode,"duty_cycles":duty_cycles,"nops":nops,"Tc_ns":Tc*1e9,
          "Ttot_ns":Ttot*1e9,"x":1,"nb":NB}
    return "\n".join(s), meta


if __name__=="__main__":
    import json
    # functional: golden & self-timed, duty 1 (op every cycle), 12 ops -> state 1..12 mod16
    specs = [("golden",2,4,"g_d2"), ("selftimed",2,4,"st_d2")]
    # energy vs duty: 6 ops at duties 1,4,10 (clocked clocks every cycle; st only on ops)
    for d in (2,4,10):
        specs += [("golden",d,4,f"g_d{d}"), ("selftimed",d,4,f"st_d{d}")]
    which = sys.argv[1] if len(sys.argv)>1 else "all"
    for mode,d,n,nm in specs:
        if which!="all" and which!=nm: continue
        txt,meta=build(mode,d,n,nm)
        # flush-left lint
        bad=[i+1 for i,l in enumerate(txt.splitlines()) if l[:1] in (' ','\t')]
        if bad: print("WS LINT FAIL",nm,bad[:4]); sys.exit(2)
        open(nm+".cir","w").write(txt); json.dump(meta,open(nm+".meta.json","w"))
        print(f"wrote {nm}.cir ({mode}, duty 1/{d}, {n} ops)")
