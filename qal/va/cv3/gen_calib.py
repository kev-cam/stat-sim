#!/usr/bin/env python3
"""v3 C(V) characterization -- T0 slow-ramp calibrations, regenerated FINE.

Two families, both are CHARACTERIZATION (static, not the hop):
  cv_tr_dv*  : the REAL transistor gate bank (8 SG13G2 static inverters,
               qal_hop_gates.py calib() pattern exactly), 20 ns ramp to dV,
               waveform-printed so E_stored(V) comes out continuous; INTEGRAL
               checkpoint measures cross-check the committed curve at dV=0.6.
  cv_bh_dv*  : the BEHAVIOURAL 8-cell bank alone (qal_gate TOPO=0, run_bankhop
               model card), same ramp -- measures the share of the calibration
               curve the cells ALREADY represent, so the new deck element is
               fit to the REMAINDER (no double counting).
"""
import os, re, subprocess, sys, time

QAL  = "/usr/local/src/stat-sim/qal"
VA   = QAL + "/va"
KEEP = VA + "/probe_runs"
XYCE = "/usr/local/src/xyce-build/src/Xyce"
PSP  = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL= "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM = QAL + "/sg13lv_compat.sp"
ENV  = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")
WP, WN, CLOAD, MGATE = 1.12, 0.74, 2.0, 8
TRAMP_PS = 20000.0

def wait_free():
    for _ in range(120):
        if subprocess.run(["pgrep","Xyce"],capture_output=True).stdout.strip()==b"":
            return
        time.sleep(5)
    sys.exit("Xyce never freed")

def bank_tr(supply, dv):
    L=[]
    for i in range(MGATE):
        L.append("VI%d in%d 0 %g" % (i,i, dv if i%2==0 else 0.0))
        L.append("XP%d o%d in%d %s %s sg13_lv_pmos w=%gu l=0.13u" % (i,i,i,supply,supply,WP))
        L.append("XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i,i,i,WN))
        L.append("CL%d o%d 0 %gf" % (i,i,CLOAD))
    return L

def bank_bh(supply, dv):
    L=[".model qm qal_gate TOPO=0 RON_N=2.5e3 RON_P=6229 VTN=0.35 VTP=0.50 NSS=1.85",
       "+ VREF=1.2 CY=2f CIN=2f CX=0.1f CW=0.1f GM0=1e-12 ESCALE=1e15"]
    for i in range(MGATE):
        L.append("VI%d in%d 0 %g" % (i,i, dv if i%2==0 else 0.0))
        L.append("YQAL_GATE XG%d in%d in%d o%d %s 0 ed%d er%d eq%d 0 qm" % (i,i,i,i,supply,i,i,i))
    return L

def chk_list(dv):
    # committed checkpoints at dv=0.6 for regeneration cross-check; isocurrent
    # fractions elsewhere
    if abs(dv-0.6) < 1e-9:
        return [0.1,0.2,0.3,0.4,0.5,0.55,0.6]
    return [round(f*dv,4) for f in (0.167,0.333,0.5,0.667,0.833,0.917,1.0)]

def deck(kind, dv):
    t = TRAMP_PS
    # Xyce eats the FIRST line as the title -- never put .hdl there
    L = ["* cv3 %s slow-ramp calibration dv=%g" % (kind, dv)]
    if kind=="tr":
        L += ['.hdl "%s"' % PSP, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
              '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
              'VS bk 0 PWL(0 0 %gp %g)' % (t, dv)] + bank_tr("bk", dv)
    else:
        L += ['.hdl "%s/qal_gate.va"' % VA,
              '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
              'VS bk 0 PWL(0 0 %gp %g)' % (t, dv)] + bank_bh("bk", dv)
    L += ['Bp p 0 V={ -V(bk)*I(VS) }', 'Bq q 0 V={ -I(VS) }',
          '.print tran V(bk) V(p) V(q)',
          '.tran %gp %gp%s' % (t/4000.0, t*1.02, " UIC" if kind=="bh" else "")]
    keys=[]
    for v in chk_list(dv):
        tv = t*(v/dv); nm = "E%03d" % int(round(v*1000))
        L.append('.measure tran %s INTEGRAL V(p) FROM=0 TO=%gp' % (nm, tv)); keys.append(nm)
    L += ['.measure tran QTOT INTEGRAL V(q) FROM=0 TO=%gp' % t, '.end']; keys.append("QTOT")
    return "\n".join(L)+"\n", keys

def run(kind, dv):
    fn = os.path.join(KEEP, "cv_%s_dv%03d.cir" % (kind, int(round(dv*100))))
    txt,keys = deck(kind,dv)
    open(fn,"w").write(txt)
    wait_free()
    t0=time.time()
    r = subprocess.run([XYCE,fn],capture_output=True,text=True,timeout=580,env=ENV,cwd=KEEP)
    wall=time.time()-t0
    g={}
    for k in keys:
        m=re.search(r"^%s\s*=\s*(\S+)"%k, r.stdout, re.M)
        if m:
            try: g[k]=float(m.group(1))
            except ValueError: pass
    ok = os.path.exists(fn+".prn")
    print("%s dv=%g wall=%.1fs prn=%s measures=%d" % (kind,dv,wall,ok,len(g)))
    if not g:
        print("  XYCE TAIL: "+r.stdout[-600:].replace("\n"," | "))
    else:
        for k in keys:
            if k in g: print("   %s = %.6g" % (k, g[k]))
    return g

if __name__=="__main__":
    kinds = sys.argv[1].split(",") if len(sys.argv)>1 else ["tr","bh"]
    dvs   = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv)>2 else [0.6,0.8,1.0,1.2]
    for kind in kinds:
        for dv in dvs:
            run(kind,dv)
