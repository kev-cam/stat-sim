#!/usr/bin/env python3
"""PHASE 2 -- THE FAIRNESS TEST AT THE LEVEL.

Same cell (1.12u p / 0.74u n), same load (2 fF), same 1.2 V, same 2 ps edge,
same reference instant (t = 100 ps), both bars measured in the SAME run:

  CMOS   : supply held at 1.2 V, the INPUT steps.        (switch)
  QAL    : the INPUT is held, the SUPPLY steps 0 -> 1.2. (settle-not-switch)

  bar 1 (committed) : output reaches 90% of the final rail
  bar 2 (commit)    : output crosses the MEASURED trip of the receiver it drives
                      (same cell, same delivered rail -> 0.645162 V at 1.2 V) by
                      the noise budget NB = 3*sigma_trip = 19.323 mV

THE QUESTION IS NOT whether QAL gets faster.  It is whether QAL gains MORE than
CMOS does.  Both sides are scored identically here; the noise budget is the same
3-sigma term on both, and the coupling/droop terms are zero on both (neither arm
has a top-up or a held rail), so no asymmetry is smuggled in.
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
TRIP12 = 0.645162        # MEASURED, fcrit/TRIP.json receiver S at 1.2 V
NB = 0.019323            # 3 * 6.441 mV
CL = "2f"

L = ["* fcrit level fairness test -- CMOS switch vs QAL settle, identical bars",
     '.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"',
     '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"',
     '.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"',
     ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17",
     "* ---- CMOS arm: fixed supply, input steps",
     "VSC sc 0 1.2",
     "VCR cir 0 PWL(0 1.2 100p 1.2 102p 0)",
     "XPCR ocr cir sc sc sg13_lv_pmos w=1.12u l=0.13u",
     "XNCR ocr cir 0 0 sg13_lv_nmos w=0.74u l=0.13u",
     "CLCR ocr 0 " + CL,
     "VCF cif 0 PWL(0 0 100p 0 102p 1.2)",
     "XPCF ocf cif sc sc sg13_lv_pmos w=1.12u l=0.13u",
     "XNCF ocf cif 0 0 sg13_lv_nmos w=0.74u l=0.13u",
     "CLCF ocf 0 " + CL,
     "* ---- QAL arm: input held, supply steps.  qu = pull-UP cell (input LOW,",
     "*      output must follow the rail up).  qd = pull-DOWN cell (input HIGH,",
     "*      output must stay at 0 while the rail rises).",
     "VSQ sq 0 PWL(0 0 100p 0 102p 1.2)",
     "VQUI qui 0 0",
     "XPQU oqu qui sq sq sg13_lv_pmos w=1.12u l=0.13u",
     "XNQU oqu qui 0 0 sg13_lv_nmos w=0.74u l=0.13u",
     "CLQU oqu 0 " + CL,
     "VQDI qdi 0 1.2",
     "XPQD oqd qdi sq sq sg13_lv_pmos w=1.12u l=0.13u",
     "XNQD oqd qdi 0 0 sg13_lv_nmos w=0.74u l=0.13u",
     "CLQD oqd 0 " + CL,
     ".tran 0.02p 400p 0 0.1p",
     "* committed bar: 90% of the 1.2 V rail",
     ".measure tran T90_CMOS_R WHEN V(ocr)=1.08 RISE=1",
     ".measure tran T90_CMOS_F WHEN V(ocf)=0.12 FALL=1",
     ".measure tran T90_QAL_U  WHEN V(oqu)=1.08 RISE=1",
     "* commit bar",
     ".measure tran TC_CMOS_R WHEN V(ocr)=%.6f RISE=1" % (TRIP12 + NB),
     ".measure tran TC_CMOS_F WHEN V(ocf)=%.6f FALL=1" % (TRIP12 - NB),
     ".measure tran TC_QAL_U  WHEN V(oqu)=%.6f RISE=1" % (TRIP12 + NB),
     "* NB = 0 sensitivity",
     ".measure tran T0_CMOS_R WHEN V(ocr)=%.6f RISE=1" % TRIP12,
     ".measure tran T0_CMOS_F WHEN V(ocf)=%.6f FALL=1" % TRIP12,
     ".measure tran T0_QAL_U  WHEN V(oqu)=%.6f RISE=1" % TRIP12,
     "* the pull-DOWN QAL cell must never rise past the trip at all",
     ".measure tran QD_MAX MAX V(oqd) FROM=100p TO=400p",
     ".measure tran QU_END FIND V(oqu) AT=399p",
     ".measure tran RAIL_END FIND V(sq) AT=399p",
     ".print tran V(ocr) V(ocf) V(oqu) V(oqd) V(sq)",
     ".end"]

p = os.path.join(HERE, "level.cir")
open(p, "w").write("\n".join(L) + "\n")
env = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
           PYMS_VAE_CACHE="/tmp/claude-1001/-usr-local-src/"
                          "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/"
                          "vae_cache_fcrit")
t0 = time.time()
rc = subprocess.call([XYCE, p], stdout=open(p + ".log", "w"),
                     stderr=subprocess.STDOUT, env=env, cwd=HERE)
print("rc=%d %.1fs" % (rc, time.time() - t0))
