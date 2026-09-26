#!/usr/bin/env python3
"""Fit the deck Q(V) to the MEASURED CHARGE curve Q(V) (not E(V)).

The qal_bankcap element IS a charge state Q(V); the hop dynamics depend on
C_inc = dQ/dV and on the charge transferred, so the natural fit target is the
measured Q(V) = int -I(VS) dt from the slow-ramp calibration -- and it pins the
operating-point charge Q(dV) far better than an energy-shape fit (which traded
the endpoint to fill the sharp inversion knee).

    Q(V) = C0*V + CT*W*softplus((V-VK)/W),  W = NSS*PHIT = 0.047823 V fixed.

Fit target = dV=1.0 curve ONLY (the hop design point); dV=0.6/0.8/1.2 holdout.
  * bank A (full):  Q_tr(V)           (bare cap, no cells)
  * deck B (floor): Q_tr(V)-Q_bh(V)   (8 cells already carry ~8 fC above VTP)
Report E(V) residuals too (energy = int V dQ, quadrature) as the physical check.
"""
import numpy as np, math, json

KEEP = "/usr/local/src/stat-sim/qal/va/probe_runs"
W = 1.85*0.02585

def curves(kind, dv):
    fn = "%s/cv_%s_dv%03d.cir.prn" % (KEEP, kind, int(round(dv*100)))
    rows = []
    for ln in open(fn):
        p = ln.split()
        if len(p) >= 5 and p[0][0].isdigit():
            try: rows.append([float(x) for x in p[1:5]])
            except ValueError: pass
    a = np.array(rows)
    t, v, pw, q = a[:,0], a[:,1], a[:,2], a[:,3]
    E = np.concatenate([[0.0], np.cumsum(0.5*(pw[1:]+pw[:-1])*np.diff(t))])
    Q = np.concatenate([[0.0], np.cumsum(0.5*(q[1:]+q[:-1])*np.diff(t))])
    return v, E, Q

def qmodel(V, c0, ct, vk):
    z = (V-vk)/W
    sp = np.where(z > 0, z, 0.0) + np.log1p(np.exp(-np.abs(z)))
    return c0*V + ct*W*sp

def emodel(V, c0, ct, vk):
    V = np.atleast_1d(V).astype(float); out = np.empty_like(V)
    for i, vv in enumerate(V):
        g = np.linspace(0, vv, 3001)
        z = (g-vk)/W
        s = np.where(z >= 0, 1.0/(1.0+np.exp(-z)), np.exp(z)/(1.0+np.exp(z)))
        out[i] = np.trapezoid(g*(c0+ct*s), g)
    return out if out.size > 1 else float(out[0])

def nelder(f, x0, step, it=600):
    n = len(x0); S = [np.array(x0,float)]
    for i in range(n):
        x = np.array(x0,float); x[i] += step[i]; S.append(x)
    fv = [f(x) for x in S]
    for _ in range(it):
        o = np.argsort(fv); S = [S[i] for i in o]; fv = [fv[i] for i in o]
        c = np.mean(S[:-1],axis=0); xr = c+(c-S[-1]); fr = f(xr)
        if fr < fv[0]:
            xe = c+2*(c-S[-1]); fe = f(xe)
            S[-1],fv[-1] = (xe,fe) if fe < fr else (xr,fr)
        elif fr < fv[-2]:
            S[-1],fv[-1] = xr,fr
        else:
            xc = c+0.5*(S[-1]-c); fc = f(xc)
            if fc < fv[-1]: S[-1],fv[-1] = xc,fc
            else:
                for i in range(1,n+1):
                    S[i] = S[0]+0.5*(S[i]-S[0]); fv[i] = f(S[i])
        if max(abs(v-fv[0]) for v in fv) < 1e-14: break
    o = np.argsort(fv); return S[o[0]], fv[o[0]]

def fit(target_kind, dv=1.0):
    """CONSTRAINED charge fit: CT is set so Q(dV) matches the measured charge
    EXACTLY (the operating-point charge sets the hop transfer), and (C0, VK) fit
    the shape. Guarantees zero endpoint charge bias."""
    vt, Et, Qt = curves("tr", dv)
    grid = np.arange(0.10, dv+1e-9, 0.025)
    Qtr = np.interp(grid, vt, Qt)
    if target_kind == "full":
        tgt = Qtr; qend = float(np.interp(dv, vt, Qt))
    else:
        vb, Eb, Qb = curves("bh", dv)
        tgt = Qtr - np.interp(grid, vb, Qb)
        qend = float(np.interp(dv, vt, Qt) - np.interp(dv, vb, Qb))
    def ct_of(c0, vk):
        z = (dv-vk)/W; sp = (z if z > 0 else 0.0) + math.log1p(math.exp(-abs(z)))
        return (qend - c0*1e-15*dv)/(1e-15*W*sp)   # in fF units
    def sse(p):
        c0, vk = p
        if c0 < 0 or not (0.2 < vk < 0.9): return 1e30
        ct = ct_of(c0, vk)
        if ct < 0: return 1e30
        r = (qmodel(grid, c0*1e-15, ct*1e-15, vk) - tgt)/np.maximum(Qtr, 1e-16)
        return float(np.dot(r,r))
    best, bs = None, 1e31
    for vk0 in (0.35, 0.45, 0.55):
        x, s = nelder(sse, [23.0, vk0], [2, 0.05])
        if s < bs: best, bs = x, s
    c0, vk = best
    return (c0, ct_of(c0, vk), vk), math.sqrt(bs/len(grid))

def main():
    resA, rmsA = fit("full")
    resB, rmsB = fit("deckB")
    c0A,ctA,vkA = resA; c0B,ctB,vkB = resB
    print("CHARGE fit (dV=1.0 curve only, W=%.6f):" % W)
    print("  bank A (full):  C0=%.4f CT=%.4f VK=%.5f  rms rel-Q=%.2f%%" % (c0A,ctA,vkA,rmsA*100))
    print("  deck B (floor): C0=%.4f CT=%.4f VK=%.5f  rms rel-Q=%.2f%%" % (c0B,ctB,vkB,rmsB*100))
    fa = (c0A*1e-15,ctA*1e-15,vkA); fb = (c0B*1e-15,ctB*1e-15,vkB)
    print("\n  bank A Q(1.0)=%.4f fC (meas 35.979)  E(1.0)=%.4f fJ (meas 19.220)" %
          (qmodel(1.0,*fa)*1e15, emodel(1.0,*fa)*1e15))
    print("  deck B + cells Q(1.0)=%.4f fC (meas 35.979)" % (qmodel(1.0,*fb)*1e15 + curves("bh",1.0)[2][-1]*1e15))
    # residual tables (charge AND energy), all dV
    for dv in (0.6,0.8,1.0,1.2):
        vt,Et,Qt = curves("tr",dv); vb,Eb,Qb = curves("bh",dv)
        if abs(dv-0.6)<1e-9: chk=[0.1,0.2,0.3,0.4,0.5,0.55,0.6]
        else: chk=[round(f*dv,4) for f in (0.167,0.333,0.5,0.667,0.833,0.917,1.0)]
        tag = "FIT" if abs(dv-1.0)<1e-9 else "holdout"
        print("\n dV=%.1f (%s):  V   Q_meas  Q_model  errQ  | E_meas  E_model  errE (composed deckB+cells)" % (dv,tag))
        for v in chk:
            qm = np.interp(v,vt,Qt)*1e15
            qmod = (qmodel(v,*fb) + np.interp(v,vb,Qb))*1e15
            em = np.interp(v,vt,Et)*1e15
            emod = (emodel(v,*fb) + np.interp(v,vb,Eb))*1e15
            print("   %5.3f  %7.4f %7.4f  %+5.1f%% | %7.4f %7.4f %+6.1f%%" %
                  (v, qm, qmod, (qmod/qm-1)*100 if qm else 0, em, emod, (emod/em-1)*100 if em else 0))
    json.dump({"deckB":{"C0_fF":c0B,"CT_fF":ctB,"VK_V":vkB,"W_V":W},
               "bankA_full":{"C0_fF":c0A,"CT_fF":ctA,"VK_V":vkA,"W_V":W}},
              open("cv_fit_q.json","w"), indent=1)
    print("\nwrote cv_fit_q.json")

if __name__ == "__main__":
    main()
