#!/usr/bin/env python3
"""THE QAL SHA-256 BLOCK: the Phase-1 remapped sha_slice (161 cells, DEPTH 14,
{sg13g2_inv_1, sg13g2_nand2_1}) run as a 14-bank QAL wave pipeline with PER-BANK
MATCHED TANKS.

Everything electrical is qal/banktank/bt.py VERBATIM -- the tg15p transfer triple
with the tank-referenced park (A6), the series R, the .OPTIONS, the gate-phase PWL
shape, the 1 F integrator metering, the t0-reference, the true-ZCS protocol and the
per-gate settling convention.  bt.py is IMPORTED for the pieces that are pure
functions of the schedule; only what MUST differ is re-written here.

WHAT MUST DIFFER, AND WHY:
  * the bank is not 8 identical inverters: it is the real level of the real mapped
    netlist, a mix of sg13g2_inv_1 and sg13g2_nand2_1 whose count spans 41:1.
  * C_bank is therefore PER BANK and MEASURED (stage `cap`), not the committed
    35.979 fF; C_tank(k) = m * C_bank(k) is matched to it.
  * L is offered in two forms: UNIFORM, and TUNED as L_k ~ 1/C_bank(k) so that
    L_k*C_bank(k) is constant across the profile.
  * the hold is PER BANK and FORCED BY THE NETLIST: H_k = (deepest consumer level
    of any cell in bank k) - k + 1.  In bt.py every bank fed only the next one, so
    H was a free knob; in a real DAG it is not.  See PRE_REGISTERED declared
    correction 1.
  * a cell's inputs come from wherever the netlist says, including banks many
    levels back, so the boundary rule takes the min over that cell's ACTUAL
    producers rather than over bank k-1.

Stages:
  warm                       build every device geometry into the private cache
  cap <dv>                   MEASURE C_bank(k) for every bank (quasi-static secant)
  capcheck <dv>              the same instrument on the committed 8-inverter bank
  probe <m> <dv> <Lmode>     per-bank single-bank true-ZCS probe -> zeros + t_hop
  row <m> <T> <dv> <Lmode> <tag> [iters]   the full 14-bank block
"""
import json, math, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bt                                                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(HERE, "..", "syn", "sw_nand_sc_resyn2.v")
CELLSP = os.path.join(HERE, "..", "cells", "census_cells.sp")
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_sha256p2")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
XYCE = bt.XYCE

# ---- inherited constants (committed banktank; NOT touched) -----------------
CLOAD = bt.CLOAD          # 2.0 fF per cell output
RS_REF = bt.RS_REF        # 10 ohm inductor series R
# committed dvopt amendment P1: VGH = max(1.5, dV).  Overridable so the dV=1.65
# mechanism control can carry its own switch gate drive.
if os.environ.get("VGHOV"):
    bt.VGH = float(os.environ["VGHOV"])
VGH = bt.VGH              # 1.5 V switch gate drive (dV=1.2); 1.65 at dV=1.65
EDGE = bt.EDGE            # 2 ps transfer-gate edge
LAG_PS = bt.LAG_PS        # 1 ps measure-FIND lag of this Xyce build
TAIL = bt.TAIL            # 500 ps
T1 = bt.T1                # 200 ps pre-roll
CBANK8 = bt.CBANK         # 35.979 fF, the committed 8-inverter secant C

# PRE-REGISTERED primary input vector (fixed before any run)
VEC = dict(a=0x5A, b=0xA6, c=0x3C, e=0x69, f=0x96, g=0xC3)

# transfer-gate total width, QUANTISED by bank size so the number of distinct
# device geometries stays bounded (pre-registered).  8 cells -> 30 um is the
# committed banktank point, and the quantisation is anchored on it.
def tg_total(n):
    return 120.0 if n >= 20 else (30.0 if n >= 4 else 7.5)


# =========================================================== the netlist
def load_netlist():
    src = open(SYN).read()
    body = src[src.index("module sha_slice("):]
    body = body[:body.index("endmodule")]
    pin, outp = [], []
    for kind, S in (("input", pin), ("output", outp)):
        for m in re.finditer(r"^\s*%s\s+(?:\[(\d+):(\d+)\]\s+)?(\S+)\s*;" % kind,
                             body, re.M):
            hi, lo, nm = m.groups()
            if hi is None:
                S.append(nm)
            else:
                for i in range(int(lo), int(hi) + 1):
                    S.append("%s[%d]" % (nm, i))
    cells, drv = {}, {}
    for m in re.finditer(r"^\s*(sg13g2_\w+)\s+(\S+)\s*\((.*?)\);", body, re.M | re.S):
        ct, cn, conns = m.groups()
        pins = {k: v.strip() for k, v in re.findall(r"\.(\w+)\(([^)]*)\)", conns)}
        cells[cn] = dict(typ=ct, pins=pins, ins=[pins[p] for p in ("A", "B") if p in pins],
                         out=pins["Y"])
        drv[pins["Y"]] = cn
    pinset = set(pin)
    # levelise
    lvl = {}
    for start in list(cells):
        st = [start]
        while st:
            k = st[-1]
            if lvl.get(k, 0) > 0:
                st.pop(); continue
            pend = [drv[n] for n in cells[k]["ins"]
                    if n not in pinset and n in drv and lvl.get(drv[n], 0) == 0]
            if pend:
                st.extend(pend); continue
            lvl[k] = 1 + max([lvl[drv[n]] for n in cells[k]["ins"]
                              if n not in pinset and n in drv] or [0])
            st.pop()
    D = max(lvl.values())
    banks = {k: [c for c in sorted(cells) if lvl[c] == k] for k in range(1, D + 1)}
    # producers of each cell, and the hold H_k forced by the deepest consumer
    life = {c: 0 for c in cells}
    for cn, cd in cells.items():
        for n in cd["ins"]:
            if n in drv:
                life[drv[n]] = max(life[drv[n]], lvl[cn] - lvl[drv[n]])
    outset = set(outp)
    for cn, cd in cells.items():
        if cd["out"] in outset:
            life[cn] = max(life[cn], D - lvl[cn])
    H = {k: max([life[c] for c in banks[k]]) + 1 for k in range(1, D + 1)}
    # logic values for the pre-registered vector
    val = {}
    for nm in pin:
        b, i = nm[:-3], int(nm[-2])
        val[nm] = (VEC[b] >> i) & 1
    for k in range(1, D + 1):
        for cn in banks[k]:
            cd = cells[cn]
            iv = [val[n] for n in cd["ins"]]
            val[cd["out"]] = (1 - iv[0]) if cd["typ"] == "sg13g2_inv_1" \
                else (1 - (iv[0] & iv[1]))
    # SPICE-safe node names
    nn, seq = {}, 0
    for n in pin:
        nn[n] = "pi%d" % pin.index(n)
    for cn in sorted(cells):
        nn[cells[cn]["out"]] = "w%d" % seq; seq += 1
    return dict(pin=pin, outp=outp, cells=cells, drv=drv, lvl=lvl, banks=banks,
                D=D, H=H, life=life, val=val, nn=nn, pinset=pinset)


N = load_netlist()


def bank_of(cn):
    return N["lvl"][cn]


def producers_bank(k):
    """the set of banks that drive any input of bank k."""
    s = set()
    for cn in N["banks"][k]:
        for n in N["cells"][cn]["ins"]:
            if n in N["drv"]:
                s.add(N["lvl"][N["drv"][n]])
    return s


# =========================================================== deck fragments
def head():
    return bt.head_lines() + ['.include "%s"' % CELLSP]


def pi_sources(dv, only=None):
    """the 48 primary inputs as ideal DC sources.  DECLARED BOOKING."""
    L = []
    for i, nm in enumerate(N["pin"]):
        if only is not None and nm not in only:
            continue
        L.append("VPI%d %s 0 %g" % (i, N["nn"][nm], dv if N["val"][nm] else 0.0))
    return L


def bank_cells(k, dv, rail=None, gnd=None, ext_inputs=False):
    """One LEVEL of the real netlist on bank k's rail.  Cell subckts are the
    Phase-1 cells/census_cells.sp (PDK device lines verbatim)."""
    rail = rail or "rail%d" % k
    gnd = gnd or "gn%d" % k
    L = ["VMG%d %s 0 0" % (k, gnd)]
    ext = []
    for cn in N["banks"][k]:
        cd = N["cells"][cn]
        y = N["nn"][cd["out"]]
        ins = []
        for n in cd["ins"]:
            if n in N["pinset"] or not ext_inputs:
                ins.append(N["nn"][n])
            else:
                ins.append(N["nn"][n]); ext.append(n)
        nm = cn.strip("_")
        if cd["typ"] == "sg13g2_inv_1":
            L.append("XC%s %s %s %s %s sg13g2_inv_1" % (nm, y, ins[0], rail, gnd))
        else:
            L.append("XC%s %s %s %s %s %s sg13g2_nand2_1"
                     % (nm, y, ins[0], ins[1], rail, gnd))
        L.append("CL%s %s %s %gf" % (nm, y, gnd, CLOAD))
    return L, ext


def tank_branch(k, ct_fF, l_nh, tot_um, rs=RS_REF):
    """bt.tank_branch VERBATIM in form; per-bank C, L and switch width."""
    w = bt.widths(tot_um)
    return ["CT%d tnk%d 0 %gf" % (k, k, ct_fF),
            "L%d tnk%d mid%d %gn" % (k, k, k, l_nh),
            "R%d mid%d sw%d %g" % (k, k, k, rs),
            "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (k, k, k, k, w["wp"]),
            "XPK%d sw%d pk%d tnk%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, k, w["park"])]


# =========================================================== schedule
def schedule(T, dv, tzr, tzq, Hk=None):
    D = N["D"]
    Hk = Hk or N["H"]
    c = {k: T1 + (k - 1) * T for k in range(1, D + 1)}
    o = {k: c[k] + tzr[k] for k in range(1, D + 1)}
    r = {k: c[k] + Hk[k] * T for k in range(1, D + 1)}
    ro = {k: r[k] + tzq[k] for k in range(1, D + 1)}
    bnd = {}
    for k in range(1, D + 1):
        b = c[k] + T
        b = min(b, r[k] - EDGE)
        for p in producers_bank(k):
            b = min(b, r[p] - EDGE)
        bnd[k] = b
    tend = max(max(ro.values()), max(bnd.values())) + TAIL
    return dict(D=D, T=T, dv=dv, H=Hk, c=c, o=o, r=r, ro=ro, bound=bnd, tend=tend,
                tzr=tzr, tzq=tzq)


# =========================================================== utils
def run(fn, lines, timeout=5400):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout
    wall = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:500]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-400:])
    return path, "ran %s in %.1fs" % (fn, wall)


# =========================================================== stage: warm
def stage_warm():
    ns, ps = {0.74, 10.0, 2.0}, {1.12, 20.0}
    for n in {len(N["banks"][k]) for k in N["banks"]}:
        w = bt.widths(tg_total(n))
        ns |= {w["wn"], w["park"]}; ps |= {w["wp"]}
    L = head() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    i = 0
    for x in sorted(ns):
        L += ["XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i, i, x),
              "RN%d d%d b 1k" % (i, i)]; i += 1
    for x in sorted(ps):
        L += ["XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (i, i, x),
              "RP%d e%d 0 1k" % (i, i)]; i += 1
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    p, msg = run("warm.cir", L, timeout=3600)
    print(msg, flush=True)
    print("geometries n=%s p=%s" % (sorted(ns), sorted(ps)))
    return p is not None


# =========================================================== stage: cap
def cap_deck(k, dv, nbank_override=None):
    """MEASURE C_bank(k): ramp the bank rail 0 -> dv with an ideal source over a
    quasi-static 500 ps and integrate the current into the rail.  C = Q/dv.
    The bank's REAL input levels (from the pre-registered vector) are applied, so
    this is the capacitance the hop actually sees."""
    L = head() + ["VR rmp 0 PWL(0 0 100p 0 600p %g 1200p %g)" % (dv, dv),
                  "VMR rmp rail%d 0" % k]
    cl, _ = bank_cells(k, dv)
    L += cl
    # every input of every cell in the bank is an ideal DC source at its value
    seen = {}
    for cn in N["banks"][k]:
        for n in N["cells"][cn]["ins"]:
            seen[n] = N["val"][n]
    for j, (n, v) in enumerate(sorted(seen.items())):
        L.append("VS%d %s 0 %g" % (j, N["nn"][n], dv if v else 0.0))
    L += bt.integ("qr", "I(VMR)")
    L += [".ic V(rail%d)=0" % k, ".tran 0.5p 1200p 0 1p",
          ".measure tran QR_Z FIND V(xqr) AT=%gp" % (0.5 + LAG_PS),
          ".measure tran QR_A FIND V(xqr) AT=%gp" % (100.0 + LAG_PS),
          ".measure tran QR_B FIND V(xqr) AT=%gp" % (600.0 + LAG_PS),
          ".measure tran QR_D FIND V(xqr) AT=%gp" % (1195.0 + LAG_PS),
          ".print tran V(rail%d) I(VMR)" % k, ".end"]
    return L


def stage_cap(dv):
    out = {}
    for k in range(1, N["D"] + 1):
        fn = "cap_b%d_dv%g.cir" % (k, dv * 1000)
        p, msg = run(fn, cap_deck(k, dv), timeout=1800)
        print("  cap bank %-2d %s" % (k, msg), flush=True)
        if p is None:
            return None
        mt = bt.parse_mt0(p + ".mt0")
        q = mt["QR_B"] - mt["QR_A"]          # coulombs over the ramp, t0-referenced
        out[k] = dict(n_cells=len(N["banks"][k]), C_bank_fF=q / dv * 1e15,
                      Q_fC=q * 1e15, Q_end_fC=(mt["QR_D"] - mt["QR_A"]) * 1e15)
        print("     bank %-2d n=%-3d C_bank = %.4f fF" % (k, out[k]["n_cells"],
                                                          out[k]["C_bank_fF"]),
              flush=True)
    json.dump(out, open(os.path.join(HERE, "CBANK_dv%g.json" % (dv * 1000)), "w"),
              indent=1)
    return out


def stage_capcheck(dv):
    """the SAME instrument on the committed 8-inverter banktank bank, which has a
    committed secant C of 35.979 fF.  If this does not land on it, the C
    instrument is wrong and every tank in the block is mis-sized."""
    L = head() + ["VR rmp 0 PWL(0 0 100p 0 600p %g 1200p %g)" % (dv, dv),
                  "VMR rmp rail1 0", "VMG1 gn1 0 0"]
    for i in range(bt.MGATE):
        L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if bt.in_hi(1, i) else 0.0))
        L.append("XP1_%d o1_%d in1_%d rail1 rail1 sg13_lv_pmos w=%gu l=0.13u"
                 % (i, i, i, bt.WP))
        L.append("XN1_%d o1_%d in1_%d gn1 gn1 sg13_lv_nmos w=%gu l=0.13u"
                 % (i, i, i, bt.WN))
        L.append("CL1_%d o1_%d gn1 %gf" % (i, i, CLOAD))
    L += bt.integ("qr", "I(VMR)")
    L += [".ic V(rail1)=0", ".tran 0.5p 1200p 0 1p",
          ".measure tran QR_A FIND V(xqr) AT=%gp" % (100.0 + LAG_PS),
          ".measure tran QR_B FIND V(xqr) AT=%gp" % (600.0 + LAG_PS),
          ".print tran V(rail1)", ".end"]
    p, msg = run("capcheck_dv%g.cir" % (dv * 1000), L, timeout=1800)
    print(msg, flush=True)
    if p is None:
        return None
    mt = bt.parse_mt0(p + ".mt0")
    C = (mt["QR_B"] - mt["QR_A"]) / dv * 1e15
    print("  8-inverter bank C = %.4f fF   (committed 35.979 fF, rel %.4f)"
          % (C, abs(C - CBANK8) / CBANK8))
    json.dump(dict(C_fF=C, committed=CBANK8, rel=abs(C - CBANK8) / CBANK8),
              open(os.path.join(HERE, "CAPCHECK_dv%g.json" % (dv * 1000)), "w"), indent=1)
    return C


# =========================================================== stage: probe
def L_of(k, cb, lmode, l_ref):
    """UNIFORM: every bank gets l_ref.  TUNED: L_k * C_bank(k) held constant at the
    reference bank's product, so sqrt(L*C) -- and therefore the hop time -- is
    equal across the profile."""
    if lmode == "uni":
        return l_ref
    return l_ref * cb[str(1)]["C_bank_fF"] / cb[str(k)]["C_bank_fF"]


def in_levels(k, dv, rails=None):
    """the level a HIGH input of bank k actually sits at.  For a primary input that
    is dv (an ideal source); for a net driven by bank j it is bank j's MEASURED
    delivered rail, which is nowhere near dv -- 0.61-0.81 V against 1.2 V.  Getting
    this wrong is what made the first single-bank zeros miss by 243 uA."""
    out = {}
    for cn in N["banks"][k]:
        for n in N["cells"][cn]["ins"]:
            hi = N["val"][n]
            if not hi:
                out[n] = 0.0
            elif n in N["pinset"] or not rails:
                out[n] = dv
            else:
                out[n] = rails[str(N["lvl"][N["drv"][n]])]
    return out


def probe_deck(k, m, dv, l_nh, ct_fF, tot, cbk_fF=None, rails=None):
    """SINGLE-BANK true-ZCS probe: bank k alone, its inputs held at their real
    levels by ideal sources (which is what they ARE during the hop, because every
    producing bank is in hold), its own tank/L/switch.  The switch CLOSES and
    NEVER OPENS, so the first current zero after the peak is the true ZCS."""
    vt0 = bt.vtank0(m, dv)
    cbk_fF = cbk_fF or (ct_fF / m)
    L = head() + ["VHI vhi 0 %g" % VGH]
    cl, _ = bank_cells(k, dv)
    L += cl
    for j, (n, v) in enumerate(sorted(in_levels(k, dv, rails).items())):
        L.append("VS%d %s 0 %g" % (j, N["nn"][n], v))
    L += tank_branch(k, ct_fF, l_nh, tot)
    tc = T1
    big = 40000.0
    L += bt.phase_pwl(k, [(tc, None)], big)
    # the zero we want is the first after the peak, at ~pi*sqrt(L*Cseries); give it
    # 4x that plus 100 ps of margin rather than sizing off the (much larger) tank.
    cser = ct_fF * cbk_fF / (ct_fF + cbk_fF)
    tend = tc + 4.0 * math.pi * math.sqrt(l_nh * 1e-9 * cser * 1e-15) * 1e12 + 100.0
    L += [".ic V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g" % (k, vt0, k, k, vt0),
          ".tran 0.1p %gp 0 0.25p" % tend,
          ".print tran I(L%d) V(rail%d) V(tnk%d) %s"
          % (k, k, k, " ".join("V(%s)" % N["nn"][N["cells"][c]["out"]]
                               for c in N["banks"][k])),
          ".end"]
    return L, tc, tend


def stage_probe(m, dv, lmode, l_ref, railsrc=None, suffix=""):
    cb = json.load(open(os.path.join(HERE, "CBANK_dv%g.json" % (dv * 1000))))
    rails = None
    if railsrc:
        rails = json.load(open(os.path.join(HERE, railsrc)))["rail_at_own_boundary_V"]
        print("  using MEASURED delivered rails from %s" % railsrc)
    out = {}
    for k in range(1, N["D"] + 1):
        n = len(N["banks"][k])
        ct = m * cb[str(k)]["C_bank_fF"]
        l_nh = L_of(k, cb, lmode, l_ref)
        lines, tc, tend = probe_deck(k, m, dv, l_nh, ct, tg_total(n), rails=rails)
        fn = "p_%s%s_m%g_dv%g_b%d.cir" % (lmode, suffix, m, dv * 1000, k)
        p, msg = run(fn, lines, timeout=2400)
        print("  probe bank %-2d %s" % (k, msg), flush=True)
        if p is None:
            return None
        hdr, rows = bt.read_prn(p + ".prn")
        z, pk = bt.zero_after_peak(hdr, rows, "I(L%d)" % k, tc)
        if z is None:
            print("  probe bank %d NO ZERO" % k); return None
        # rail at the zero, and the 90% settle of the worst gate after it
        out[k] = dict(n_cells=n, C_bank_fF=cb[str(k)]["C_bank_fF"], C_tank_fF=ct,
                      L_nH=l_nh, tg_total_um=tg_total(n),
                      t_hop_ps=z - tc, IPK_uA=pk * 1e6)
        print("     bank %-2d n=%-3d L=%8.3f nH C_bank=%8.3f fF  t_hop=%8.4f ps  Ipk=%9.2f uA"
              % (k, n, l_nh, cb[str(k)]["C_bank_fF"], z - tc, pk * 1e6), flush=True)
    th = [out[k]["t_hop_ps"] for k in out]
    res = dict(mode=lmode, m=m, dv=dv, L_ref=l_ref, per_bank=out,
               t_hop_min_ps=min(th), t_hop_max_ps=max(th),
               t_hop_spread_x=max(th) / min(th))
    json.dump(res, open(os.path.join(HERE, "PROBE_%s%s_m%g_dv%g.json"
                                     % (lmode, suffix, m, dv * 1000)), "w"), indent=1)
    print("  HOP SPREAD %s: %.4f ps .. %.4f ps = %.3fx"
          % (lmode, min(th), max(th), max(th) / min(th)))
    return res


# =========================================================== the FIXED buck
# qal/buckfix C9 VERBATIM in sequencing: break-before-make at BOTH edges and an
# ASYNCHRONOUS (DIODE) FREEWHEEL -- the freewheel nMOS gate is held at 0 for the
# whole run and the inductor freewheels through that device's own drain-bulk
# junction, which deletes the two 1.5 V gate transitions that were drawing ~40 fC
# from the supply and dumping it to ground.  It feeds the TANK, not the bank.
# DECLARED BOUND: the generation of the buck's own input rail is NOT costed.
VSUP = 1.2
CNA_FF = 8.0
WSW_BUCK = 10.0
WON_B, WOP_B = 5.0, 10.0
LTU_NH = 10.0
RSTU = 10.0
TON_BUCK = 35.0
SETTLE_B = 8.0


def buck_devices(S, tfire, tout):
    """one C9 cell per tank.  tfire[k] = when the high side turns on; tout[k] = when
    the OUT switch re-opens (the measured I(LTU) zero), or None for the probe form."""
    L = ["VBK vbk 0 %g" % VSUP]
    for k in range(1, N["D"] + 1):
        tf = tfire[k]
        hs0 = tf - SETTLE_B - 2 * EDGE
        hs1 = hs0 + EDGE
        b = tf + TON_BUCK
        o0, o1 = tf - EDGE, tf
        big = S["tend"] * 4.0
        L += ["XTUSW%d na%d gtu%d vbk vbk sg13_lv_pmos w=%gu l=0.13u"
              % (k, k, k, WSW_BUCK),
              "XTUFW%d na%d gfw%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, WSW_BUCK),
              "CNA%d na%d 0 %gf" % (k, k, CNA_FF),
              "LTU%d na%d ntm%d %gn" % (k, k, k, LTU_NH),
              "RTU%d ntm%d nb%d %g" % (k, k, k, RSTU),
              "XTON%d nb%d gto%d tnk%d 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, k, WON_B),
              "XTOP%d nb%d gtp_o%d tnk%d vhi sg13_lv_pmos w=%gu l=0.13u"
              % (k, k, k, k, WOP_B),
              # HS gate: 1.5 -> 0 (ON) at hs0, back to 1.5 (OFF) at b
              "VGTU%d gtu%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (k, k, VGH, hs0, VGH, hs1, b, b + EDGE, VGH),
              # FW gate PINNED AT 0 for the whole run -- diode freewheel (C9)
              "VGFW%d gfw%d 0 0" % (k, k)]
        if tout is None or tout.get(k) is None:
            L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)"
                  % (k, k, o0, o1, VGH, big, VGH),
                  "VGTP_O%d gtp_o%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
                  % (k, k, VGH, o0, VGH, o1, big)]
        else:
            tq = tout[k]
            L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
                  % (k, k, o0, o1, VGH, tq, VGH, tq + EDGE),
                  "VGTP_O%d gtp_o%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
                  % (k, k, VGH, o0, VGH, o1, tq, tq + EDGE, VGH)]
    return L


# =========================================================== stage: the block
def row_deck(m, T, dv, lmode, l_ref, cb, tzr, tzq, Hk=None,
             buck=False, tout=None):
    S = schedule(T, dv, tzr, tzq, Hk)
    D = N["D"]
    vt0 = bt.vtank0(m, dv)
    big = S["tend"] * 4.0
    L = head() + ["VHI vhi 0 %g" % VGH] + pi_sources(dv)
    ct = {}
    for k in range(1, D + 1):
        cl, _ = bank_cells(k, dv)
        L += cl
    for k in range(1, D + 1):
        ct[k] = m * cb[str(k)]["C_bank_fF"]
        L += tank_branch(k, ct[k], L_of(k, cb, lmode, l_ref),
                         tg_total(len(N["banks"][k])))
    noopen = set(int(x) for x in os.environ.get("NOOPEN", "").split(",") if x.strip())
    for k in range(1, D + 1):
        if k in noopen:
            # FULL-BLOCK RISE PROBE for bank k: its transfer switch closes at its
            # beat and NEVER opens, so the first current zero after the peak is the
            # TRUE zero WITH the downstream fanout load present.  The single-bank
            # probe cannot see that load, which is why bank 1's rise zero was the
            # one switch open the iteration could not close (AMENDMENT P2-R6).
            L += bt.phase_pwl(k, [(S["c"][k], None)], big)
        else:
            L += bt.phase_pwl(k, [(S["c"][k], S["o"][k]), (S["r"][k], S["ro"][k])], big)

    tfire = {}
    if buck:
        # the top-up fires AFTER this bank's return has completed, so it restores
        # the tank for the NEXT operation.  20 ps of clearance past the return open.
        for k in range(1, D + 1):
            tfire[k] = S["ro"][k] + 20.0
        S["tend"] = max(S["tend"], max(tfire.values()) + TON_BUCK + 300.0 + TAIL)
        S["tfire"] = tfire
        L += buck_devices(S, tfire, tout)

    # ---- metering: 1 F integrators only, every one t0-referenced at 0.5 ps
    tags = []
    for k in range(1, D + 1):
        for nm, ex in (("qlt%d" % k, "I(L%d)" % k),
                       ("ea%d" % k, "V(tnk%d)*I(L%d)" % (k, k)),
                       ("eb%d" % k, "V(rail%d)*I(L%d)" % (k, k)),
                       ("esw%d" % k, "V(sw%d)*I(L%d)" % (k, k)),
                       ("er%d" % k, "I(L%d)*I(L%d)*%g" % (k, k, RS_REF)),
                       ("qg%d" % k, "I(VMG%d)" % k)):
            L += bt.integ(nm, ex); tags.append(nm)
    npi = len(N["pin"])
    L += bt.integ("qi", "-(" + "+".join("I(VPI%d)" % i for i in range(npi)) + ")")
    L += bt.integ("ei", "-(" + "+".join("V(%s)*I(VPI%d)" % (N["nn"][N["pin"][i]], i)
                                        for i in range(npi)) + ")")
    L += bt.integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (k, k, k, k, k, k)
        for k in range(1, D + 1)))
    L += bt.integ("ehi", "-%g*I(VHI)" % VGH)
    tags += ["qi", "ei", "egt", "ehi"]
    if buck:
        L += bt.integ("qbk", "-I(VBK)")
        L += bt.integ("ebk", "-%g*I(VBK)" % VSUP)
        L += bt.integ("egb", "-" + "-".join(
            "V(gtu%d)*I(VGTU%d)-V(gto%d)*I(VGTO%d)-V(gtp_o%d)*I(VGTP_O%d)"
            % (k, k, k, k, k, k) for k in range(1, D + 1)))
        tags += ["qbk", "ebk", "egb"]

    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                               % (k, vt0, k, k, vt0) for k in range(1, D + 1)))
    L.append(".tran 0.2p %gp 0 0.25p" % S["tend"])

    g = lambda t: t + LAG_PS
    cks = [("Z", 0.5)]
    for k in range(1, D + 1):
        cks += [("O%d" % k, S["o"][k]), ("B%d" % k, S["bound"][k]),
                ("R%d" % k, S["r"][k] - EDGE), ("Q%d" % k, S["ro"][k])]
    cks += [("D", S["tend"] - 5.0)]
    for tg in tags:
        kk = re.sub(r"\D", "", tg)
        want = cks if not kk else [x for x in cks if x[0] in
                                   ("Z", "D", "O" + kk, "B" + kk, "R" + kk, "Q" + kk)]
        for nm, tt in want:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp" % (tg.upper(), nm, tg, g(tt)))
    for k in range(1, D + 1):
        for nm in ("Z", "O%d" % k, "B%d" % k, "R%d" % k, "Q%d" % k, "D"):
            tt = dict(cks)[nm]
            L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp" % (k, nm, k, g(tt)))
            L.append(".measure tran VT%d%s FIND V(tnk%d) AT=%.6fp" % (k, nm, k, g(tt)))
        L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                 % (k, k, S["c"][k], S["tend"]))
        L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp" % (k, k, g(S["o"][k])))
        L.append(".measure tran IZQ%d FIND I(L%d) AT=%.6fp" % (k, k, g(S["ro"][k])))
        L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                 % (k, k, S["c"][k], S["tend"]))
        for j, cn in enumerate(N["banks"][k]):
            y = N["nn"][N["cells"][cn]["out"]]
            L.append(".measure tran G%d_%dB FIND V(%s) AT=%.6fp" % (k, j, y, g(S["bound"][k])))
            L.append(".measure tran G%d_%dD FIND V(%s) AT=%.6fp" % (k, j, y, g(S["tend"] - 5.0)))
    pr = (["I(L%d)" % k for k in range(1, D + 1)] +
          ["V(rail%d)" % k for k in range(1, D + 1)] +
          ["V(tnk%d)" % k for k in range(1, D + 1)])
    if buck:
        pr += ["I(LTU%d)" % k for k in range(1, D + 1)]
        for k in range(1, D + 1):
            L.append(".measure tran ITZ%d FIND I(LTU%d) AT=%.6fp"
                     % (k, k, (tout or {}).get(k, S["tend"] - 10.0) + LAG_PS))
    # SETTLE SCAN: every gate at a ladder of offsets after its own rail start, so
    # the beat period the block ACTUALLY needs is read off one deck instead of
    # being bisected with one full run per candidate T.
    scan = [float(x) for x in os.environ.get("SCAN", "").split(",") if x.strip()]
    if scan:
        for k in range(1, D + 1):
            for si, off in enumerate(scan):
                tt = S["c"][k] + off
                if tt > S["r"][k] - EDGE or tt > S["tend"] - 5.0:
                    continue
                L.append(".measure tran VR%dS%d FIND V(rail%d) AT=%.6fp"
                         % (k, si, k, tt + LAG_PS))
                for j, cn in enumerate(N["banks"][k]):
                    y = N["nn"][N["cells"][cn]["out"]]
                    L.append(".measure tran S%d_%d_%d FIND V(%s) AT=%.6fp"
                             % (k, j, si, y, tt + LAG_PS))
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


def stage_row(m, T, dv, lmode, l_ref, tag, iters=2, Hk=None):
    cb = json.load(open(os.path.join(HERE, "CBANK_dv%g.json" % (dv * 1000))))
    seed = os.environ.get("SEED", "")
    if seed:
        sm = json.load(open(os.path.join(HERE, "ROWMETA_%s.json" % seed)))
        pr = {"per_bank": {k: {"t_hop_ps": v} for k, v in sm["tzr"].items()}}
        print("  rise zeros seeded from ROWMETA_%s" % seed)
    else:
        pr = json.load(open(os.path.join(HERE, "PROBE_%s%s_m%g_dv%g.json"
                                         % (lmode, os.environ.get("PSUF", ""), m, dv * 1000))))
    D = N["D"]
    tzr = {k: pr["per_bank"][str(k)]["t_hop_ps"] for k in range(1, D + 1)}
    rq = os.path.join(HERE, "RETPROBE_%s%s_m%g_dv%g.json"
                      % (lmode, os.environ.get("QSUF", ""), m, dv * 1000))
    if seed:
        tzq = {int(k): v for k, v in sm["tzq"].items()}
        print("  return zeros seeded from ROWMETA_%s" % seed)
    elif os.path.exists(rq):
        d = json.load(open(rq))
        tzq = {k: d[str(k)]["t_ret_ps"] for k in range(1, D + 1)}
        print("  return zeros from %s" % os.path.basename(rq))
    else:
        tzq = dict(tzr)                  # fallback: the return mirrors the rise
    hist = []
    for it in range(iters + 1):
        lines, S = row_deck(m, T, dv, lmode, l_ref, cb, tzr, tzq, Hk)
        fn = "b_%s.cir" % tag
        p, msg = run(fn, lines, timeout=10800)
        print("  row it%d %s" % (it, msg), flush=True)
        if p is None:
            return None
        mt = bt.parse_mt0(p + ".mt0")
        iz = {k: mt["IZ%d" % k] * 1e6 for k in range(1, D + 1)}
        izq = {k: mt["IZQ%d" % k] * 1e6 for k in range(1, D + 1)}
        worst = max(max(abs(v) for v in iz.values()), max(abs(v) for v in izq.values()))
        hist.append(dict(it=it, msg=msg, worst_abs_IZ_uA=worst,
                         IZ_uA={k: round(v, 5) for k, v in iz.items()},
                         IZQ_uA={k: round(v, 5) for k, v in izq.items()}))
        print("     A6 worst |I(L)| at a commanded open = %.4f uA" % worst, flush=True)
        if worst <= 1.0 or it == iters:
            break
        hdr, rows = bt.read_prn(p + ".prn")
        for k in range(1, D + 1):
            # DEFECT FIX (AMENDMENT P2-R1): scan ONLY this bank's rise window.
            # Unbounded, zero_after_peak takes the largest |I(L)| anywhere after
            # c_k, which can be the bank's OWN RETURN peak, and then returns the
            # return's zero as the rise's.
            sub = [rr for rr in rows if S["c"][k] <= rr[1] * 1e12 <= S["r"][k] - EDGE]
            z, _ = bt.zero_after_peak(hdr, sub, "I(L%d)" % k, S["c"][k])
            if z is not None:
                tzr[k] = z - S["c"][k]
    json.dump(dict(tag=tag, m=m, T=T, dv=dv, lmode=lmode, L_ref=l_ref,
                   tzr=tzr, tzq=tzq, iters=hist, H=S["H"],
                   sched={x: S[x] for x in ("c", "o", "r", "ro", "bound", "tend")}),
              open(os.path.join(HERE, "ROWMETA_%s.json" % tag), "w"), indent=1)
    return tag





# =========================================================== stage: lsw
def hop_deck(k, m, dv, l_nh, ct_fF, tot, tz, tail=TAIL):
    """SINGLE-BANK hop with a REAL cut: switch closes at T1, opens at the measured
    ZCS, then a tail.  This is the committed skept/sk.py hop form, on the real
    bank.  Gives the bank's own t_level = max(t_hop, t_valid90)."""
    vt0 = bt.vtank0(m, dv)
    L = head() + ["VHI vhi 0 %g" % VGH]
    cl, _ = bank_cells(k, dv)
    L += cl
    seen = {}
    for cn in N["banks"][k]:
        for n in N["cells"][cn]["ins"]:
            seen[n] = N["val"][n]
    for j, (n, v) in enumerate(sorted(seen.items())):
        L.append("VS%d %s 0 %g" % (j, N["nn"][n], dv if v else 0.0))
    L += tank_branch(k, ct_fF, l_nh, tot)
    tc = T1
    to = tc + tz
    tend = to + tail
    L += bt.phase_pwl(k, [(tc, to)], tend * 4.0)
    L += bt.integ("ea", "V(tnk%d)*I(L%d)" % (k, k))
    L += bt.integ("eb", "V(rail%d)*I(L%d)" % (k, k))
    L += [".ic V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g" % (k, vt0, k, k, vt0),
          ".tran 0.1p %gp 0 0.25p" % tend,
          ".measure tran IZ FIND I(L%d) AT=%.6fp" % (k, to + LAG_PS),
          ".print tran I(L%d) V(rail%d) V(tnk%d) %s"
          % (k, k, k, " ".join("V(%s)" % N["nn"][N["cells"][c]["out"]]
                               for c in N["banks"][k])),
          ".end"]
    return L, tc, to, tend


def t_valid90(hdr, rows, k, cells, t_from, t_to):
    """the first instant in [t_from,t_to] at which EVERY gate of the bank is within
    10 percent of the bank's INSTANTANEOUS rail on its expected side, and stays
    there to t_to.  The committed convention."""
    ir = hdr.index(("V(RAIL%d)" % k).upper())
    ic = {c: hdr.index(("V(%s)" % N["nn"][N["cells"][c]["out"]]).upper()) for c in cells}
    good_from = None
    for rr in rows:
        t = rr[1] * 1e12
        if t < t_from or t > t_to:
            continue
        rail = rr[ir]
        if rail <= 0:
            good_from = None; continue
        ok = True
        for c in cells:
            v = rr[ic[c]]
            s = (v / rail) if N["val"][N["cells"][c]["out"]] else (1.0 - v / rail)
            if s < 0.90:
                ok = False; break
        if ok and good_from is None:
            good_from = t
        elif not ok:
            good_from = None
    return good_from


def stage_lsw(k, m, dv, l_nh):
    cb = json.load(open(os.path.join(HERE, "CBANK_dv%g.json" % (dv * 1000))))
    ct = m * cb[str(k)]["C_bank_fF"]
    tot = tg_total(len(N["banks"][k]))
    tag = "b%d_m%g_dv%g_L%g" % (k, m, dv * 1000, l_nh * 100)
    lines, tc, tend = probe_deck(k, m, dv, l_nh, ct, tot)
    p, msg = run("lp_%s.cir" % tag, lines, timeout=3600)
    print("  lsw probe %s" % msg, flush=True)
    if p is None:
        return None
    hdr, rows = bt.read_prn(p + ".prn")
    z, pk = bt.zero_after_peak(hdr, rows, "I(L%d)" % k, tc)
    if z is None:
        print("  NO ZERO"); return None
    tz = z - tc
    lines, tc, to, tend = hop_deck(k, m, dv, l_nh, ct, tot, tz)
    p, msg = run("lh_%s.cir" % tag, lines, timeout=3600)
    print("  lsw hop   %s" % msg, flush=True)
    if p is None:
        return None
    hdr, rows = bt.read_prn(p + ".prn")
    mt = bt.parse_mt0(p + ".mt0")
    cells = N["banks"][k]
    tv = t_valid90(hdr, rows, k, cells, to, tend - 5.0)
    ir = hdr.index(("V(RAIL%d)" % k).upper())
    vbend = [rr[ir] for rr in rows if rr[1] * 1e12 <= tend - 5.0][-1]
    vbpk = max(rr[ir] for rr in rows)
    # per-gate settling at the END of the window, on the expected side
    send = {}
    for c in cells:
        icx = hdr.index(("V(%s)" % N["nn"][N["cells"][c]["out"]]).upper())
        v = [rr[icx] for rr in rows if rr[1] * 1e12 <= tend - 5.0][-1]
        send[c] = 100.0 * ((v / vbend) if N["val"][N["cells"][c]["out"]]
                           else (1.0 - v / vbend))
    res = dict(bank=k, n_cells=len(cells), m=m, dv=dv, L_nH=l_nh, C_bank_fF=cb[str(k)]["C_bank_fF"],
               C_tank_fF=ct, tg_total_um=tot, t_hop_ps=tz, IPK_uA=pk * 1e6,
               IZ_uA=mt["IZ"] * 1e6, VBPK=vbpk, VBEND=vbend,
               t_valid90_ps=(tv - tc) if tv else None,
               t_level_ps=max(tz, (tv - tc) if tv else 1e9),
               s_end_min_pct=min(send.values()),
               s_end_worst_cell=min(send, key=send.get))
    json.dump(res, open(os.path.join(HERE, "LSW_%s.json" % tag), "w"), indent=1)
    print("  L=%6.2f nH  t_hop=%8.3f  t_valid90=%s  t_level=%8.3f  VBEND=%.4f  "
          "s_end_min=%.2f%%  IZ=%.4f uA"
          % (l_nh, tz, ("%.3f" % (tv - tc)) if tv else "NONE", res["t_level_ps"],
             vbend, res["s_end_min_pct"], res["IZ_uA"]), flush=True)
    return res


def ret_probe_deck(k, m, dv, l_nh, ct_fF, tot, vrail, vtank, rails):
    """SINGLE-BANK RETURN probe.  The bank starts in its HELD state -- rail at the
    MEASURED delivered value, tank at its MEASURED post-rise value, inputs at their
    held levels -- the switch is open for 200 ps so the outputs settle onto that
    rail, then it CLOSES and NEVER OPENS, so the first current zero after the peak
    is the true return ZCS.  Iterating this off the full deck does not work: an
    early cut makes the post-cut ring-down zero look like the answer."""
    L = head() + ["VHI vhi 0 %g" % VGH]
    cl, _ = bank_cells(k, dv)
    L += cl
    for j, (n, v) in enumerate(sorted(in_levels(k, dv, rails).items())):
        L.append("VS%d %s 0 %g" % (j, N["nn"][n], v))
    L += tank_branch(k, ct_fF, l_nh, tot)
    tc = T1
    cser = ct_fF * (ct_fF / m) / (ct_fF + ct_fF / m)
    tend = tc + 4.0 * math.pi * math.sqrt(l_nh * 1e-9 * cser * 1e-15) * 1e12 + 100.0
    L += bt.phase_pwl(k, [(tc, None)], tend * 4.0)
    L += [".ic V(tnk%d)=%g V(rail%d)=%g V(sw%d)=%g" % (k, vtank, k, vrail, k, vtank),
          ".tran 0.1p %gp 0 0.25p" % tend,
          ".print tran I(L%d) V(rail%d) V(tnk%d)" % (k, k, k), ".end"]
    return L, tc


def stage_retprobe(m, dv, lmode, l_ref, src_row, suffix=""):
    """measure every bank's RETURN zero from its own MEASURED held state."""
    cb = json.load(open(os.path.join(HERE, "CBANK_dv%g.json" % (dv * 1000))))
    mt = bt.parse_mt0(os.path.join(HERE, "b_%s.cir.mt0" % src_row))
    rails = json.load(open(os.path.join(HERE, "ROW_%s.json" % src_row)))[
        "rail_at_own_boundary_V"]
    out = {}
    for k in range(1, N["D"] + 1):
        n = len(N["banks"][k])
        ct = m * cb[str(k)]["C_bank_fF"]
        vrail = mt["VR%dR%d" % (k, k)]
        vtank = mt["VT%dR%d" % (k, k)]
        lines, tc = ret_probe_deck(k, m, dv, L_of(k, cb, lmode, l_ref), ct,
                                   tg_total(n), vrail, vtank, rails)
        fn = "q_%s%s_m%g_dv%g_b%d.cir" % (lmode, suffix, m, dv * 1000, k)
        p, msg = run(fn, lines, timeout=2400)
        print("  retprobe bank %-2d %s" % (k, msg), flush=True)
        if p is None:
            return None
        hdr, rows = bt.read_prn(p + ".prn")
        z, pk = bt.zero_after_peak(hdr, rows, "I(L%d)" % k, tc)
        if z is None:
            print("  retprobe bank %d NO ZERO" % k); return None
        out[k] = dict(n_cells=n, V_rail_held=vrail, V_tank_held=vtank,
                      t_ret_ps=z - tc, IPK_uA=pk * 1e6)
        print("     bank %-2d rail_held=%.4f tank_held=%.4f  t_return=%8.4f ps  Ipk=%9.2f uA"
              % (k, vrail, vtank, z - tc, pk * 1e6), flush=True)
    json.dump(out, open(os.path.join(HERE, "RETPROBE_%s%s_m%g_dv%g.json"
                                     % (lmode, suffix, m, dv * 1000)), "w"), indent=1)
    return out


def stage_buck(src_tag, tag, m, T, dv, lmode, l_ref):
    """the FIXED buck (buckfix C9) feeding every TANK, on top of a row whose
    transfer zeros have ALREADY converged.  Two passes: pass 1 leaves the OUT
    switch closed so the true I(LTU) zero can be read; pass 2 cuts at it."""
    cb = json.load(open(os.path.join(HERE, "CBANK_dv%g.json" % (dv * 1000))))
    src = json.load(open(os.path.join(HERE, "ROWMETA_%s.json" % src_tag)))
    tzr = {int(k): v for k, v in src["tzr"].items()}
    tzq = {int(k): v for k, v in src["tzq"].items()}
    D = N["D"]
    tout = None
    hist = []
    for it in range(2):
        lines, S = row_deck(m, T, dv, lmode, l_ref, cb, tzr, tzq,
                            buck=True, tout=tout)
        fn = "k_%s.cir" % tag
        p, msg = run(fn, lines, timeout=14400)
        print("  buck it%d %s" % (it, msg), flush=True)
        if p is None:
            return None
        mt = bt.parse_mt0(p + ".mt0")
        hist.append(dict(it=it, msg=msg,
                         ITZ_uA={k: round(mt.get("ITZ%d" % k, 0.0) * 1e6, 5)
                                 for k in range(1, D + 1)}))
        if it == 1:
            break
        hdr, rows = bt.read_prn(p + ".prn")
        tout = {}
        for k in range(1, D + 1):
            z, _ = bt.zero_after_peak(hdr, rows, "I(LTU%d)" % k, S["tfire"][k])
            tout[k] = z if z else S["tfire"][k] + TON_BUCK + 100.0
        print("     buck OUT cuts:", {k: round(v, 2) for k, v in tout.items()},
              flush=True)
    json.dump(dict(tag=tag, src=src_tag, m=m, T=T, dv=dv, lmode=lmode, L_ref=l_ref,
                   tzr=tzr, tzq=tzq, tout=tout, iters=hist, H=S["H"], buck=True,
                   sched={x: S[x] for x in ("c", "o", "r", "ro", "bound", "tend",
                                            "tfire")}),
              open(os.path.join(HERE, "ROWMETA_%s.json" % tag), "w"), indent=1)
    return tag


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "warm":
        sys.exit(0 if stage_warm() else 1)
    if a[0] == "info":
        print("cells %d depth %d" % (len(N["cells"]), N["D"]))
        print("profile", [len(N["banks"][k]) for k in range(1, N["D"] + 1)])
        print("H_k", N["H"], " II_beats =", max(N["H"].values()))
        print("vector", {k: hex(v) for k, v in VEC.items()})
        hi = sum(1 for c in N["cells"] if N["val"][N["cells"][c]["out"]])
        print("expected HIGH outputs: %d of %d" % (hi, len(N["cells"])))
        for nm in ("maj", "ch", "sum"):
            print("  %s =" % nm, hex(sum(N["val"]["%s[%d]" % (nm, i)] << i for i in range(8))))
    elif a[0] == "cap":
        sys.exit(0 if stage_cap(float(a[1])) else 1)
    elif a[0] == "capcheck":
        sys.exit(0 if stage_capcheck(float(a[1])) else 1)
    elif a[0] == "probe":
        sys.exit(0 if stage_probe(float(a[1]), float(a[2]), a[3], float(a[4]),
                                  a[5] if len(a) > 5 else None,
                                  a[6] if len(a) > 6 else "") else 1)
    elif a[0] == "lsw":
        sys.exit(0 if stage_lsw(int(a[1]), float(a[2]), float(a[3]), float(a[4])) else 1)
    elif a[0] == "lsw":
        sys.exit(0 if stage_lsw(int(a[1]), float(a[2]), float(a[3]), float(a[4])) else 1)
    elif a[0] == "retprobe":
        sys.exit(0 if stage_retprobe(float(a[1]), float(a[2]), a[3], float(a[4]),
                                     a[5], a[6] if len(a) > 6 else "") else 1)
    elif a[0] == "buck":
        sys.exit(0 if stage_buck(a[1], a[2], float(a[3]), float(a[4]), float(a[5]),
                                 a[6], float(a[7])) else 1)
    elif a[0] == "row":
        m, T, dv, lmode, l_ref, tag = (float(a[1]), float(a[2]), float(a[3]),
                                       a[4], float(a[5]), a[6])
        it = int(a[7]) if len(a) > 7 else 2
        sys.exit(0 if stage_row(m, T, dv, lmode, l_ref, tag, it) else 1)
