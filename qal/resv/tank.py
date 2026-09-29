#!/usr/bin/env python3
"""TRACK A (e) -- WHAT THE TANK COSTS.

A reservoir modelled as an ideal source is a BOOKING.  This campaign has had three
verdicts overturned by exactly that booking.  So the tank here is a REAL finite
capacitor with a REAL initial charge, and the question is what it costs to hold it.

TWO ROWS, and the difference between them is the whole point:

  NO-RETURN   the tank charges the bank, the switch opens at ZCS, the bank settles,
              and the bank's charge is then WRITTEN OFF (dumped at the end of the
              beat, as the committed decks do).  Energy out of the tank per hop is
              read straight off the committed `ea` integrator.  Nothing new is
              needed for this row -- every sweep row already carries it.

  WITH-RETURN the switch RE-CLOSES after the settle window and the bank's remaining
              charge is rung BACK into the tank through the same L, opening again at
              the return current zero (ZCS both ways).  Net energy out of the tank
              over the full cycle is what the tank's supply must actually replace.

WHY THIS IS THE RIGHT QUESTION.  In the committed PEER chain, bank N's charge
BECOMES bank N+1's charge -- the recycling IS the peer hop, and that is what makes
the loss adiabatic.  A tank-fed bank does not consume its predecessor's charge, so
the recycling has to be put back by hand or it is simply gone.  Pre-registered as E5.

Cells, transfer switch, series R, .OPTIONS, the 1F-integrator metering with t0
reference, and the TRUE-ZCS probe-then-cut discipline are qal/skept/sk.py verbatim
(imported, not copied).  The PHASE SCHEDULE is new: it has two conduction windows
instead of one, and the park must be released before the second.

usage: tank.py run <tag> <L_nH> <W_um> <dV> <CA_MULT> <settle_ps> [cl_fF]
"""
import json, math, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skept")
import sk                                                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_resv")
sk.HERE = HERE
sk.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
CB_FF = sk.CA_FF
ROWD = os.path.join(HERE, "tankd")


def deck(L, tot, dv, ca, th1, settle, th2, cl, tail=300.0):
    """th1 = None -> the FORWARD PROBE (window 1 closes and never opens).
       th2 = None -> the RETURN PROBE  (window 2 closes and never opens).
    The forward probe MUST use this same source-cut topology, not sk.probe's
    receiving-cut-only one: the extra series transmission gate moves the current
    zero, and the committed discipline is that the zero is re-probed on the deck it
    will be used in."""
    e = sk.EDGE
    t0 = sk.T0
    if th1 is None:
        tp0 = math.pi * math.sqrt((L * 1e-9) * (ca * CB_FF / (ca + CB_FF)) * 1e-15) * 1e12
        tend = t0 + 5.0 * tp0
        ps0, ms0 = min(0.05, tp0 / 3000.0), min(0.10, tp0 / 1500.0)
        gt = [(0, 0), (t0 - e, 0), (t0, VGH_now()), (tend * 2, VGH_now())]
        gtp = [(0, VGH_now()), (t0 - e, VGH_now()), (t0, 0), (tend * 2, 0)]
        pk = [(0, VGH_now()), (t0, VGH_now()), (t0 + e, 0), (tend * 2, 0)]
        return _assemble(L, tot, dv, ca, cl, gt, gtp, pk, ps0, ms0, tend), \
            dict(t0=t0, o1=None, c2=None, o2=None, tend=tend)
    o1 = t0 + th1                      # window 1 opens (forward ZCS)
    c2 = o1 + settle                   # window 2 closes (return)
    big = c2 + (th2 if th2 else 0.0) + tail + 1000.0
    o2 = (c2 + th2) if th2 else big
    tend = (o2 + tail) if th2 else (c2 + 6.0 * (th1 if th1 else 100.0))
    VGH = sk.VGH
    # nMOS gate: 0 -> VGH over [t0-e,t0], VGH -> 0 over [o1,o1+e],
    #            0 -> VGH over [c2-e,c2], VGH -> 0 over [o2,o2+e]
    gt = [(0, 0), (t0 - e, 0), (t0, VGH), (o1, VGH), (o1 + e, 0),
          (c2 - e, 0), (c2, VGH)]
    gtp = [(0, VGH), (t0 - e, VGH), (t0, 0), (o1, 0), (o1 + e, VGH),
           (c2 - e, VGH), (c2, 0)]
    if th2:
        gt += [(o2, VGH), (o2 + e, 0), (big, 0)]
        gtp += [(o2, 0), (o2 + e, VGH), (big, VGH)]
    else:
        gt += [(big, VGH)]
        gtp += [(big, 0)]
    # PARK: the committed srccut phase -- ON whenever the hop is idle (which is what
    # pins the inductor island), OFF through each conduction window.  See the
    # SOURCE-SIDE CUT note below for why both are now required.
    pk = [(0, VGH), (t0, VGH), (t0 + e, 0), (o1 + e, 0), (o1 + 2 * e, VGH),
          (c2 - e, VGH), (c2, VGH), (c2 + e, 0)]
    if th2:
        pk += [(o2 + e, 0), (o2 + 2 * e, VGH), (big, VGH)]
    else:
        pk += [(big, 0)]

    tp = math.pi * math.sqrt((L * 1e-9) * (ca * CB_FF / (ca + CB_FF)) * 1e-15) * 1e12
    ps = min(0.05, tp / 3000.0)
    ms = min(0.10, tp / 1500.0)
    return _assemble(L, tot, dv, ca, cl, gt, gtp, pk, ps, ms, tend), \
        dict(t0=t0, o1=o1, c2=c2, o2=o2, tend=tend)


def VGH_now():
    return sk.VGH


def _assemble(L, tot, dv, ca, cl, gt, gtp, pk, ps, ms, tend):
    VGH = sk.VGH

    def pwl(nm, node, pts):
        return "%s %s 0 PWL(%s)" % (nm, node, " ".join(
            ("%gp %g" % (t, v)) if t else ("0 %g" % v) for t, v in pts))

    out = sk.head() + [
        ".param LT=%gn RS=%g CA=%gf" % (L, sk.RS, ca),
        "CA bka 0 {CA}", "VHI vhi 0 %g" % VGH,
        pwl("VGT", "gt", gt), pwl("VGTP", "gtp", gtp), pwl("VPK", "pk", pk),
    ] + sw_lines_cut(tot) + ["LT a mid {LT}", "RT mid sw {RS}"] \
      + sk.cells(dv, "inv", cl)
    out += sk.integ("qlt", "I(LT)") + sk.integ("ea", "V(bka)*I(LT)")
    out += sk.integ("ean", "V(a)*I(LT)")
    out += sk.integ("eb", "V(bkb)*I(LT)") + sk.integ("er", "I(LT)*I(LT)*%g" % sk.RS)
    out += sk.integ("esw", "V(sw)*I(LT)")
    sh = "I(VMGH)+" + "+".join("I(VI%d)" % i for i in sk.HI)
    sl = "I(VMGL)+" + "+".join("I(VI%d)" % i for i in sk.LO)
    out += sk.integ("ebk", "V(bkb)*((%s)+(%s))" % (sh, sl))
    out += sk.integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)")
    out += [".ic V(bka)=%g V(bkb)=0 V(a)=0" % dv]
    pr = ["V(bka)", "V(bkb)", "V(sw)", "V(a)", "I(LT)"] + ["V(o%d)" % i for i in range(sk.MGATE)] \
         + ["V(xqlt)", "V(xea)", "V(xean)", "V(xeb)", "V(xer)", "V(xesw)",
            "V(xebk)", "V(xegt)"]
    for k in range(0, len(pr), 8):
        out.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    out += [".tran %gp %gp 0 %gp" % (ps, tend, ms), ".end"]
    return out


def sw_lines_cut(tot):
    """THE SOURCE-SIDE CUT, chain3/restore5 AMENDMENT A3, applied to a single
    tank-fed hop.  The committed single-hop deck cuts only the RECEIVING side, so
    the tank stays wired to the inductor forever.  At CA_MULT = 1 that is harmless
    (the tank ends empty).  With a real tank it is not, and BOTH failure modes were
    MEASURED here before this function existed:
      * park ON after ZCS  -> the park grounds `sw`, and the tank is still tied to
        `sw` through L and R, so the park DUMPS THE TANK.  MEASURED on my m=5 row:
        the `ea` integrator ran to 244.8814 fJ against a full-tank 0.5*C*dv^2 =
        244.8821 fJ, i.e. the entire 62.92 fJ residual went to ground.
      * park OFF after ZCS -> the inductor island {mid, sw} floats and the tank-L-sw
        loop RINGS undamped for the whole hold window.  MEASURED on the same point:
        I(LT) still swinging +-3000 uA at t = 80-300 ps with the switch open, V(bka)
        wandering 0.99 -> 1.28 -> 1.15 V, and the "tank" appearing to GAIN 29.6 fC
        with its switch open -- which is the arbitrary-phase-of-a-ringing-waveform
        artefact qal_hop_gates.py's own docstring warns about.
    With the cut, opening the hop isolates the tank AND leaves an island that the
    park can hold at ground without touching the tank.  Same phases on both TGs."""
    w = sk.widths(tot)
    return ["XSWSN a gt bka 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
            "XSWSP a gtp bka vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
            "XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
            "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
            "XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % w["park"]]


def zero_up(path, tmin):
    """first interpolated UPWARD crossing of I(LT)=0 after its NEGATIVE peak
    following tmin -- the return hop's ZCS instant."""
    w = sk.W(path)
    i = w.v("I(LT)")
    k0 = next(k for k in range(len(w.t)) if w.t[k] >= tmin)
    ip = min(range(k0, len(i)), key=lambda k: i[k])
    for k in range(ip + 1, len(i)):
        if i[k] >= 0.0 > i[k - 1]:
            t0, t1 = w.t[k - 1], w.t[k]
            f = -i[k - 1] / (i[k] - i[k - 1])
            return t0 + f * (t1 - t0), i[ip] * 1e6
    return None, i[ip] * 1e6


def run(tag, L, W, dv, ca_mult, settle, cl=6.91):
    ca = ca_mult * CB_FF
    sk.VGH = max(1.5, dv)
    t0 = time.monotonic()
    # 1. forward ZCS, committed probe
    flines, fm = deck(L, W, dv, ca, None, settle, None, cl)
    lp, msg = sk.run("tp1_%s.cir" % tag, flines, timeout=2400)
    print("  fwd probe:", msg, flush=True)
    tz1, ipk1, _ = sk.zero_of(lp + ".prn")
    th1 = tz1 - sk.T0
    print("  fwd t_hop %.4f ps (Ipk %.1f uA)" % (th1, ipk1), flush=True)
    # 2. return probe: window 2 closes and never opens
    lines, m = deck(L, W, dv, ca, th1, settle, None, cl)
    rp, msg = sk.run("tp2_%s.cir" % tag, lines, timeout=3600)
    print("  ret probe:", msg, flush=True)
    if rp is None:
        return dict(tag=tag, error=msg)
    tz2, ipk2 = zero_up(rp + ".prn", m["c2"])
    if tz2 is None:
        return dict(tag=tag, error="no return current zero")
    th2 = tz2 - m["c2"]
    print("  ret t_hop %.4f ps (Ineg %.1f uA)" % (th2, ipk2), flush=True)
    # 3. the measured deck, ZCS both ways
    lines, m = deck(L, W, dv, ca, th1, settle, th2, cl)
    hp, msg = sk.run("th_%s.cir" % tag, lines, timeout=3600)
    print("  cycle:", msg, flush=True)
    if hp is None:
        return dict(tag=tag, error=msg)
    w = sk.W(hp + ".prn")

    def dI(tg, t):
        return (w.at("V(x%s)" % tg, t) - w.at("V(x%s)" % tg, 0.5)) * 1e15

    tE = m["tend"] - 5.0
    vb_o1 = w.at("V(bkb)", m["o1"])
    vb_c2 = w.at("V(bkb)", m["c2"])
    vb_E = w.at("V(bkb)", tE)
    va_E = w.at("V(bka)", tE)
    r = dict(tag=tag, L_nH=L, W_um=W, dv=dv, ca_mult=ca_mult, ca_fF=ca, cl_fF=cl,
             settle_window_ps=settle, t_hop_fwd_ps=th1, t_hop_ret_ps=th2,
             VBPK=max(w.v("V(bkb)")), V_bank_at_open1=vb_o1,
             V_bank_at_close2=vb_c2, V_bank_end=vb_E,
             V_tank_start=dv, V_tank_at_open1=w.at("V(bka)", m["o1"]),
             V_tank_at_close2=w.at("V(bka)", m["c2"]), V_tank_end=va_E,
             # energy OUT of the tank, by the committed integrator
             E_tank_out_fwd_fJ=dI("ea", m["o1"]),
             E_tank_out_net_fJ=dI("ea", tE),
             # independent, from the tank's own terminal voltage
             E_tank_exact_fwd_fJ=0.5 * ca * (dv ** 2 - w.at("V(bka)", m["o1"]) ** 2),
             E_tank_exact_net_fJ=0.5 * ca * (dv ** 2 - va_E ** 2),
             Q_fwd_fC=dI("qlt", m["o1"]), Q_net_fC=dI("qlt", tE),
             E_R_fJ=dI("er", tE), E_switchblock_fJ=dI("esw", tE) - dI("eb", tE),
             E_gate_drive_fJ=dI("egt", tE), cells_ebk_fJ=dI("ebk", tE),
             timing=m, wall_s=round(time.monotonic() - t0, 1))
    r["closure_E_pct"] = (100.0 * (r["E_tank_out_net_fJ"] - r["E_tank_exact_net_fJ"])
                          / r["E_tank_exact_net_fJ"]) if r["E_tank_exact_net_fJ"] else None
    r["recovery_pct"] = (100.0 * (1.0 - r["E_tank_out_net_fJ"] / r["E_tank_out_fwd_fJ"])
                         if r["E_tank_out_fwd_fJ"] else None)
    r["Q_recovered_pct"] = (100.0 * (1.0 - r["Q_net_fC"] / r["Q_fwd_fC"])
                            if r["Q_fwd_fC"] else None)
    os.makedirs(ROWD, exist_ok=True)
    json.dump(r, open(os.path.join(ROWD, "%s.json" % tag), "w"), indent=1)
    print("  E_tank fwd %.4f fJ -> net %.4f fJ (recovery %.2f%%), closure %.3f%%"
          % (r["E_tank_out_fwd_fJ"], r["E_tank_out_net_fJ"],
             r["recovery_pct"] or 0.0, r["closure_E_pct"] or 0.0), flush=True)
    print("  tank %.5f -> %.5f V | bank peak %.5f, at open1 %.5f, at close2 %.5f, end %.5f"
          % (dv, va_E, r["VBPK"], vb_o1, vb_c2, vb_E), flush=True)
    return r


if __name__ == "__main__":
    a = sys.argv
    run(a[2], float(a[3]), float(a[4]), float(a[5]), float(a[6]), float(a[7]),
        float(a[8]) if len(a) > 8 else 6.91)
