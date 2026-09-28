#!/usr/bin/env python3
"""TRACK B step 1: extract, from the COMMITTED best row's own waveform file, what
the resonant network actually has to SOURCE -- i.e. the load the sustaining
amplifier must drive.  Touches no new simulation; reconstructs the tap current
independently as I = (V(gts)-V(gt))/RS (the trapezoid instrument, which agreed
with the 1F integrators to 0.19% in the skeptic audit).
"""
import sys, math, cmath

RS = 25.0
BEAT = 580.0e-12

def read_prn(p):
    rows, hdr = [], None
    for ln in open(p):
        f = ln.split()
        if hdr is None and f and f[0].lower() == 'index':
            hdr = [h.upper() for h in f]; continue
        if hdr and f and f[0][0].isdigit():
            try: rows.append([float(x) for x in f])
            except ValueError: pass
    return hdr, rows

def col(hdr, n):
    n = n.upper()
    c = [i for i, h in enumerate(hdr) if h == n]
    if not c: c = [i for i, h in enumerate(hdr) if n in h]
    return c[0]

def main(path):
    hdr, rows = read_prn(path)
    it = 1
    igts, igt = col(hdr,'V(GTS)'), col(hdr,'V(GT)')
    igps, igtp = col(hdr,'V(GPS)'), col(hdr,'V(GTP)')
    t  = [r[it] for r in rows]
    # tap currents, source -> gate, positive = network delivering charge to the gate
    ign = [(r[igts]-r[igt])/RS for r in rows]
    igp = [(r[igps]-r[igtp])/RS for r in rows]
    vgn = [r[igts] for r in rows]
    vgp = [r[igps] for r in rows]

    # restrict to the first full beat 0..580 ps
    idx = [i for i in range(len(t)) if t[i] <= BEAT*1.0000001]
    def trap(y, ii):
        s = 0.0
        for a, b in zip(ii[:-1], ii[1:]):
            s += 0.5*(y[a]+y[b])*(t[b]-t[a])
        return s
    # energies over the beat
    Egn = trap([vgn[i]*ign[i] for i in range(len(t))], idx)
    Egp = trap([vgp[i]*igp[i] for i in range(len(t))], idx)
    Qgn = trap(ign, idx); Qgp = trap(igp, idx)
    # RS dissipation
    Ern = trap([ign[i]*ign[i]*RS for i in range(len(t))], idx)
    Erp = trap([igp[i]*igp[i]*RS for i in range(len(t))], idx)
    print("== ONE BEAT (0..580 ps), trapezoid instrument, independent of the 1F cans ==")
    print("  E_gt   source-delivered  %+9.4f fJ   Q_net %+8.4f fC   I_RS^2R %7.4f fJ"
          % (Egn*1e15, Qgn*1e15, Ern*1e15))
    print("  E_gtp  source-delivered  %+9.4f fJ   Q_net %+8.4f fC   I_RS^2R %7.4f fJ"
          % (Egp*1e15, Qgp*1e15, Erp*1e15))
    print("  NET resonant pair        %+9.4f fJ  (committed 580ps figure 2.8603)"
          % ((Egn+Egp)*1e15))

    # ---- harmonic decomposition of the tap CURRENT the network must source ----
    # uniform resample over the beat
    N = 2048
    def resamp(y):
        out = []
        j = 0
        for k in range(N):
            tt = BEAT*k/N
            while j+1 < len(t) and t[j+1] < tt: j += 1
            if j+1 >= len(t): out.append(y[-1]); continue
            f = (tt-t[j])/(t[j+1]-t[j]) if t[j+1] != t[j] else 0.0
            out.append(y[j] + f*(y[j+1]-y[j]))
        return out
    def dft(y, k):
        s = sum(y[n]*cmath.exp(-2j*math.pi*k*n/N) for n in range(N))
        return 2*s/N if k else s/N
    print()
    print("== HARMONIC CONTENT the amplifier must supply (per bank, one beat) ==")
    print("  k   f[GHz]   |V_gt|    |I_gt|uA   Re{Z}ohm  |  |V_gtp|   |I_gtp|uA  Re{Z}ohm")
    Vn, In = resamp(vgn), resamp(ign)
    Vp, Ip = resamp(vgp), resamp(igp)
    tot_p_n = tot_p_p = 0.0
    for k in (0,1,2,3,4,5,6,7):
        vk, ik = dft(Vn,k), dft(In,k)
        vk2, ik2 = dft(Vp,k), dft(Ip,k)
        zn = (vk/ik) if abs(ik) > 1e-12 else complex('nan')
        zp = (vk2/ik2) if abs(ik2) > 1e-12 else complex('nan')
        pn = 0.5*(vk*ik.conjugate()).real if k else (vk*ik).real
        pp = 0.5*(vk2*ik2.conjugate()).real if k else (vk2*ik2).real
        tot_p_n += pn; tot_p_p += pp
        print("  %d  %6.3f  %7.4f  %9.2f  %9.1f  | %7.4f  %9.2f  %9.1f   P=%+.4f/%+.4f fJ/beat"
              % (k, k/ (BEAT*1e9), abs(vk), abs(ik)*1e6, zn.real,
                 abs(vk2), abs(ik2)*1e6, zp.real, pn*BEAT*1e15, pp*BEAT*1e15))
    print("  sum of harmonic powers -> %+8.4f fJ/beat (gt) %+8.4f fJ/beat (gtp)  net %+8.4f"
          % (tot_p_n*BEAT*1e15, tot_p_p*BEAT*1e15, (tot_p_n+tot_p_p)*BEAT*1e15))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv)>1 else
         '/usr/local/src/stat-sim/qal/recov/skeptic/sk_best.cir.prn')
