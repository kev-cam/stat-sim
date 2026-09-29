#!/usr/bin/env python3
"""THE TOP-UP CELL ON ITS OWN, on a small fixture -- the standing directive is to prove
a mechanism on a small fixture and use full scale only as confirmation, and I violated
it by debugging this inside the 4-bank chain.

Fixture: ONE linear capacitor standing in for a bank (C_BANK, the MEASURED effective
bank capacitance), pre-charged to V0 (a hop-delivered rail), and nothing else.  No
cells, no hops, no schedule.  The only question asked here:

    does the pulsed-inductor top-up put POSITIVE charge into the cap, and how much?

Everything is metered the same way as in the chain: delivered charge at a 0 V series
source in the cap leg, supply charge on the supply source, gate charge as |I| on every
gate driver.
"""
import json, os, re, subprocess, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = SK.XYCE
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
           PYMS_VAE_CACHE="/tmp/claude-1001/-usr-local-src/"
                           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_skiptu")
VGH = 1.5
EDGE = 2.0
# C_BANK DERIVED from the committed single hop: t_hop = pi*sqrt(L*C) with the MEASURED
# t_hop = 65.495 ps at L = 15 nH gives C = (65.495e-12/pi)^2 / 15e-9 = 28.98 fF.
C_BANK = 28.98
# SWITCH-NODE CAPACITANCE on na -- ASSUMED, and it has to be added explicitly.
# sg13lv_compat.sp ZEROES ad/as/pd/ps, so na (the buck switch node) has NO junction
# capacitance at all in this model; its only capacitance is the two switches' gate
# overlap.  The coupling ratio is then near unity and the 1.5 V gate swing transfers
# almost entirely onto na, driving it to -0.30 V (MEASURED) and reversing the inductor.
# For every other measurement in this campaign the missing junction caps are a
# second-order LOWER-BOUND effect; for a buck switch node they are FIRST-ORDER.
# DERIVED estimate: a w=10 um drain with ~0.3 um contacted extension is ~3 um^2, at
# ~1 fF/um^2 ~ 3 fF per device, two devices ~6 fF, plus ~2 fF wiring ~ 8 fF.
# Swept, because it is an assumption.
T0 = 100.0            # ps, let the fixture settle before the pulse


def deck(ltu, wsw, ton, v0, vsup, tfw=None, tag="", cna=8.0, slew=24.0):
    a, b = T0, T0 + ton
    z = (4000.0 if tfw is None else b + tfw)
    w = SK.widths(wsw * 1.5)
    e = EDGE
    tend = (z if tfw is not None else 900.0) + 200.0
    L = ['* top-up cell on a small fixture',
         '.hdl "%s"' % SK.VA, '.include "%s"' % SK.MODEL, '.include "%s"' % SK.SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         'VHI vhi 0 %g' % VGH,
         'VTSUP tsup 0 %g' % vsup,
         # the bank: one linear cap, metered through a 0 V series source
         'VMTU nb nbx 0',
         'CBK bank 0 %gf' % C_BANK,
         'CNA na 0 %gf' % cna,
         'XTUSW na gtu tsup tsup sg13_lv_pmos w=%gu l=0.13u' % wsw,
         'XTUFW na gfw 0 0 sg13_lv_nmos w=%gu l=0.13u' % wsw,
         'LTU na ntm %gn' % ltu,
         'RTU ntm nb 10',
         'XTUON nbx gto bank 0 sg13_lv_nmos w=%gu l=0.13u' % w["wn"],
         'XTUOP nbx gtop bank vhi sg13_lv_pmos w=%gu l=0.13u' % w["wp"],
         # HS pMOS turns ON one EDGE EARLY, while the LS is still holding na at 0.
         # MEASURED reason: na has almost no capacitance, and if both gates fall
         # together their Cgd coupling yanks na to -0.42 V and the pMOS never gets it
         # above 0.85 V even after the pulse.  With the pMOS already fully on and
         # low-impedance when the LS releases, it holds na up against that coupling.
         # The 2 ps HS/LS overlap is real shoot-through and is METERED in q_supply.
         # HS turns on EARLY and fast, while the LS still clamps na at 0.
         'VGTU gtu 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)'
         % (VGH, a - slew - 4 * e, VGH, a - slew - 2 * e, b, b + e, VGH),
         # LS nMOS: holds na at 0 until the HS is on, then releases so the HS can
         # pull na up to the supply BEFORE the OUT switch connects the bank.
         # LS turns off SLOWLY.  The gate-to-na coupling current is
         # C_couple*dVgate/dt: at a 2 ps edge that is ~3 mA, comparable to what the HS
         # pMOS can source, so na sags to -0.30 V (MEASURED) and reverses the inductor.
         # Stretched over `slew` ps it is ~300 uA and the already-on HS holds na up.
         'VGFW gfw 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)'
         % (VGH, a - slew, VGH, a, b, b + e, VGH),
         ]
    # OUT closes LAST -- after na has been pulled to the supply.  MEASURED reason:
    # if OUT closes while the LS still holds na at 0, the bank drains straight through
    # the inductor to ground for the duration of the overlap.  Sequence:
    # HS-on -> LS-off (na -> tsup) -> OUT-close -> [pulse] -> HS-off/LS-on (freewheel)
    # -> OUT-open at the MEASURED zero.
    if tfw is None:
        L += ['VGTO gto 0 PWL(0 0 %gp 0 %gp %g %gp %g)' % (a - e, a, VGH, z, VGH),
              'VGTOP gtop 0 PWL(0 %g %gp %g %gp 0 %gp 0)' % (VGH, a - e, VGH, a, z)]
    else:
        L += ['VGTO gto 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)'
              % (a - e, a, VGH, z, VGH, z + e),
              'VGTOP gtop 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)'
              % (VGH, a - e, VGH, a, z, z + e, VGH)]
    L += SK.integ("qdel", "I(VMTU)")
    L += SK.integ("qsup", "-I(VTSUP)")
    L += SK.integ("qind", "I(LTU)")
    L += SK.integ("qgab", "abs(I(VGTU))+abs(I(VGFW))+abs(I(VGTO))+abs(I(VGTOP))")
    L += ['.ic V(bank)=%g V(na)=0 V(nb)=0 V(nbx)=0' % v0,
          '.tran 0.05p %gp 0 0.25p' % tend,
          '.measure tran QDEL_Z FIND V(xqdel) AT=0.5p',
          '.measure tran QDEL_D FIND V(xqdel) AT=%gp' % (tend - 5),
          '.measure tran QSUP_Z FIND V(xqsup) AT=0.5p',
          '.measure tran QSUP_D FIND V(xqsup) AT=%gp' % (tend - 5),
          '.measure tran QIND_Z FIND V(xqind) AT=0.5p',
          '.measure tran QIND_D FIND V(xqind) AT=%gp' % (tend - 5),
          '.measure tran QGAB_Z FIND V(xqgab) AT=0.5p',
          '.measure tran QGAB_D FIND V(xqgab) AT=%gp' % (tend - 5),
          '.measure tran VB0 FIND V(bank) AT=%gp' % (a - 5),
          '.measure tran VBF FIND V(bank) AT=%gp' % (tend - 5),
          '.measure tran VBMX MAX V(bank) FROM=%gp TO=%gp' % (a, tend),
          '.measure tran IPK MAX I(LTU) FROM=%gp TO=%gp' % (a, tend),
          '.measure tran IMN MIN I(LTU) FROM=%gp TO=%gp' % (a, tend),
          '.print tran V(bank) I(LTU) V(na) V(nb) I(VMTU)',
          '.end']
    return L, tend


def run(tag, lines):
    fn = os.path.join(HERE, "tc_%s.cir" % tag)
    open(fn, "w").write("\n".join(lines) + "\n")
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=600,
                       cwd=HERE, env=ENV)
    if not os.path.exists(fn + ".prn"):
        return None, "; ".join(l for l in r.stdout.splitlines()
                               if "rror" in l or "bort" in l)[:300]
    return SK.parse_mt0(fn + ".mt0"), fn


def zero_of(fn, t_from, t_to):
    hdr, rows = SK.read_prn(fn + ".prn")
    ic = hdr.index("I(LTU)")
    prev = None
    for r in rows:
        t = r[1] * 1e12
        if t < t_from or t > t_to:
            continue
        if prev is not None and r[ic] <= 0.0 < prev[1]:
            t0, v0 = prev
            return t0 + (0.0 - v0) * (t - t0) / (r[ic] - v0)
        prev = (t, r[ic])
    return None


def main():
    v0, vsup = 0.70, 1.2
    out = {"_doc": __doc__.strip(), "C_bank_fF": C_BANK, "V0": v0, "Vsup": vsup,
           "rows": []}
    print("top-up cell on a %g fF bank pre-charged to %g V, supply %g V" % (C_BANK, v0, vsup))
    print(" Cna  Ltu  wsw t_on | tfw_meas |  q_del   q_sup   q_ind |  V0->Vf   Vmax |"
          " Qmult | Q_gate  E_gate")
    print("(fF) (nH) (um) (ps) |   (ps)   |  (fC)    (fC)    (fC)  |   (V)      (V) |"
          "       |  (fC)    (fJ)")
    SL = float(os.environ.get("TC_SLEW", 24.0))
    for cna in (8.0,):
      for ltu in (1.0, 5.0):
        for ton in (6.0, 12.0):
            for wsw in (10.0,):
                tag = "S%g_C%g_L%g_W%g_t%g" % (SL, cna, ltu, wsw, ton)
                # 1) probe the true zero
                lines, tend = deck(ltu, wsw, ton, v0, vsup, tfw=None, tag=tag, cna=cna, slew=SL)
                m, fn = run("p_" + tag, lines)
                if m is None:
                    print(" probe FAIL %s: %s" % (tag, fn)); continue
                z = zero_of(fn, T0 + ton, 900.0)
                if z is None:
                    print(" %4g %4g %4g %5g | NO ZERO FOUND after the pulse"
                          % (cna, ltu, wsw, ton))
                    out["rows"].append(dict(Cna=cna, Ltu=ltu, wsw=wsw, ton=ton, tfw=None,
                                            note="no current zero after the pulse"))
                    continue
                tfw = z - (T0 + ton)
                # 2) the real cut
                lines, tend = deck(ltu, wsw, ton, v0, vsup, tfw=tfw, tag=tag, cna=cna, slew=SL)
                m, fn = run("r_" + tag, lines)
                if m is None:
                    print(" run FAIL %s: %s" % (tag, fn)); continue
                qd = (m["QDEL_D"] - m["QDEL_Z"]) * 1e15
                qs = (m["QSUP_D"] - m["QSUP_Z"]) * 1e15
                qi = (m["QIND_D"] - m["QIND_Z"]) * 1e15
                qg = 0.5 * (m["QGAB_D"] - m["QGAB_Z"]) * 1e15
                eg = qg * VGH
                print(" %4g %4g %4g %5g | %8.2f | %7.3f %7.3f %7.3f | %.4f->%.4f %.4f |"
                      " %5s | %6.2f %7.2f"
                      % (cna, ltu, wsw, ton, tfw, qd, qs, qi, m["VB0"], m["VBF"], m["VBMX"],
                         round(qd / qs, 3) if qs else "n/a", qg, eg))
                out["rows"].append(dict(
                    Cna_fF=cna, Ltu_nH=ltu, wsw_um=wsw, ton_ps=ton, tfw_measured_ps=round(tfw, 3),
                    q_delivered_fC=round(qd, 4), q_supply_fC=round(qs, 4),
                    q_inductor_fC=round(qi, 4),
                    V_before=round(m["VB0"], 6), V_after=round(m["VBF"], 6),
                    V_max=round(m["VBMX"], 6),
                    dV_mV=round(1000 * (m["VBF"] - m["VB0"]), 3),
                    charge_mult=round(qd / qs, 4) if qs else None,
                    Q_gate_fC=round(qg, 4), E_gate_real_driver_fJ=round(eg, 4),
                    Ipk_uA=round(m.get("IPK", 0) * 1e6, 2),
                    Imin_uA=round(m.get("IMN", 0) * 1e6, 2)))
    json.dump(out, open(os.path.join(HERE, "TUCELL.json"), "w"), indent=1)
    print("\nwrote TUCELL.json")


if __name__ == "__main__":
    main()
