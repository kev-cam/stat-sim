#!/usr/bin/env python3
"""QAL cell energy MEASURED on a real RECOVERING gate -- kills the self-baseline.

WHY THIS EXISTS. Every QAL energy number so far was E_QAL = f_adia * E_cell * DR, i.e.
*CMOS's* measured cell energy times a model factor -- a self-baseline in the DEFINITION,
not the calibration. And the one QAL gate deck that exists (qal_nand_tt_11.cir) integrates
only the pc port (`Bp p 0 V={-V(pc)*I(VPC)}`) while a second fixed-well supply (Vnw) is
left uncounted, so its own docstring calls the absolute energies "CONTAMINATED".

WHAT THIS MEASURES INSTEAD. An ECRL (Efficient Charge Recovery Logic) dual-rail AND2 on
SG13G2/PSP103 -- a genuinely recovering adiabatic structure:
    MP1: pc -> out   gate=/out  |  MP2: pc -> /out  gate=out   (cross-coupled recovery path)
    N-tree(out ->gnd) = /a || /b   (conducts when a*b = 0  -> out held low)
    N-tree(/out->gnd) = a  &  b    (conducts when a*b = 1  -> /out held low)
so out = a*b with dual-rail outputs. On the pc DOWN-ramp the charge on the high output
returns to the supply THROUGH the cross-coupled pMOS -- that return is the thing a
full-swing model cannot express, and here it is measured, not asserted.

ACCOUNTING. pMOS bulk is tied to pc (source and bulk at the same potential), so there is
exactly ONE supply port and the energy balance closes on it -- no uncounted second port.
E_net over a full up+down cycle = integral of V(pc)*I_pc. Reported alongside:
  E_up    = energy drawn on the up-ramp
  E_down  = energy RETURNED on the down-ramp (negative current => recovery is real)
  E_net   = E_up + E_down = what is actually dissipated
The adiabatic SIGNATURE is E_net falling ~1/T as the ramp slows; a model that hard-codes
f_adia cannot produce that from a current integral, so the sweep is the proof.

REFERENCE for the same gate hard-switched: 1/2 C dV^2 at the same load (and the CMOS
static-gate energy measured separately in threeway/spice), so the ratio is gate-vs-gate,
not gate-vs-formula.
"""
import os, re, subprocess, sys, json

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
VDD   = 1.2
CL    = 10.0           # fF per output rail
RAMPS = [0.25, 0.5, 1.0, 2.0, 5.0]   # ns up/down ramp time T
HOLD  = 1.0            # ns hold at Vdd
WP, WN = 1.12, 0.74    # um, same devices as the CMOS/NAND anchors

def deck(tr, a, b, cl=CL):
    """ECRL AND2, dual-rail inputs held valid; pMOS bulk tied to pc (single supply port)."""
    na, nb = 1 - a, 1 - b
    L = ['* ECRL adiabatic AND2 (SG13G2/PSP103) -- recovering structure, ONE supply port',
         '.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-13 CHGTOL=1e-15',
         '.param Vdd=%g CL=%gf TR=%gn H=%gn' % (VDD, cl, tr, HOLD),
         # power-clock: 0 -> Vdd over TR, hold H, -> 0 over TR
         'VPC pc 0 PWL(0 0 {TR} {Vdd} {TR+H} {Vdd} {2*TR+H} 0)',
         # dual-rail inputs, held (valid from the previous stage)
         'VA  a  0 %g' % (a  * VDD), 'VAN an 0 %g' % (na * VDD),
         'VB  b  0 %g' % (b  * VDD), 'VBN bn 0 %g' % (nb * VDD),
         # cross-coupled pMOS recovery pair; BULK = pc  -> single supply port
         'XP1 out  outn pc pc sg13_lv_pmos w=%gu l=0.13u' % WP,
         'XP2 outn out  pc pc sg13_lv_pmos w=%gu l=0.13u' % WP,
         # N-tree on out: /a || /b  (out held low when a*b=0)
         'XNA out an 0 0 sg13_lv_nmos w=%gu l=0.13u' % WN,
         'XNB out bn 0 0 sg13_lv_nmos w=%gu l=0.13u' % WN,
         # N-tree on /out: a & b in series (/out held low when a*b=1)
         'XNC outn a  s1 0 sg13_lv_nmos w=%gu l=0.13u' % WN,
         'XND s1   b  0  0 sg13_lv_nmos w=%gu l=0.13u' % WN,
         'CL  out  0 {CL}', 'CLN outn 0 {CL}', 'Cs s1 0 0.1f',
         # instantaneous power delivered BY the supply, and its running integral
         'Bp p 0 V={ -V(pc)*I(VPC) }',
         '.tran 0.2p {2*TR+H}',
         '.measure tran EUP   INTEGRAL V(p) FROM=0        TO={TR+H}',
         '.measure tran EDOWN INTEGRAL V(p) FROM={TR+H}   TO={2*TR+H}',
         '.measure tran ENET  INTEGRAL V(p) FROM=0        TO={2*TR+H}',
         '.measure tran OUTH  FIND V(out)  AT={TR+0.5*H}',
         '.measure tran OUTNH FIND V(outn) AT={TR+0.5*H}',
         '.end']
    return "\n".join(L) + "\n"

def run(tag, txt):
    fn = "ecrl_%s.cir" % tag
    open(fn, "w").write(txt)
    env = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=420, env=env).stdout
    except subprocess.TimeoutExpired:
        return None
    g = {}
    for k in ("EUP", "EDOWN", "ENET", "OUTH", "OUTNH"):
        m = re.search(r"^%s\s*=\s*(\S+)" % k, o, re.M)
        if m:
            try: g[k] = float(m.group(1))
            except ValueError: pass
    return g if "ENET" in g else None

def main():
    half_cv2 = 0.5 * (CL * 1e-15) * VDD * VDD * 1e15   # fJ, one rail hard-switched
    print("ECRL adiabatic AND2, SG13G2/PSP103, Vdd=%.1fV, CL=%gfF/rail" % (VDD, CL))
    print("hard-switch reference 1/2 C dV^2 (one rail) = %.3f fJ\n" % half_cv2)

    print("--- LOGIC CHECK (out must = a*b at the supply hold) ---")
    for (a, b) in [(0,0),(0,1),(1,0),(1,1)]:
        g = run("tt_%d%d" % (a,b), deck(1.0, a, b))
        if g is None: print("  a=%d b=%d FAILED" % (a,b)); continue
        print("  a=%d b=%d -> out=%.3f  /out=%.3f   (expect out=%d)"
              % (a, b, g.get("OUTH",0), g.get("OUTNH",0), a*b))

    print("\n--- ADIABATIC SIGNATURE: E vs ramp time T (a=b=1) ---")
    print("   T(ns) |  E_up(fJ) | E_down(fJ) | E_net(fJ) | E_net/(1/2CV^2) | recovered%")
    rows = []
    for tr in RAMPS:
        g = run("T%g" % tr, deck(tr, 1, 1))
        if g is None: print("   %5g   FAILED" % tr); continue
        eu, ed, en = g["EUP"]*1e15, g["EDOWN"]*1e15, g["ENET"]*1e15
        rec = (-ed/eu*100.0) if eu else 0.0
        rows.append({"T_ns": tr, "E_up_fJ": round(eu,4), "E_down_fJ": round(ed,4),
                     "E_net_fJ": round(en,4), "frac_half_cv2": round(en/half_cv2,4),
                     "recovered_pct": round(rec,2)})
        print("   %5g   | %9.3f | %10.3f | %9.3f | %14.3f | %8.1f%%"
              % (tr, eu, ed, en, en/half_cv2, rec))
    json.dump({"_doc": "ECRL adiabatic AND2 measured energy, SG13G2 PSP103. Single supply "
                       "port (pMOS bulk=pc) so the balance closes. E_net from the supply "
                       "current integral -- NOT f_adia*E_cell. E_down<0 => charge returned.",
               "vdd": VDD, "cl_fF": CL, "half_cv2_fJ": round(half_cv2,4), "sweep": rows},
              open("qal_ecrl_measured.json","w"), indent=1)
    if len(rows) >= 2:
        print("\n  adiabatic test: E_net should FALL as T grows (~1/T). "
              "%s" % ("FALLS -> recovery is real" if rows[-1]["E_net_fJ"] < rows[0]["E_net_fJ"]
                      else "DOES NOT FALL -> structure is not recovering; investigate"))
    print("wrote qal_ecrl_measured.json")

if __name__ == "__main__":
    main()
