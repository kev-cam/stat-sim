#!/usr/bin/env python3
"""Build a chain deck whose ONLY change vs the committed deck is the top-up
cell: the eight gate PWL lines and (declared separately) the LTU values.

K1 = PROPERLY TIMED SYNCHRONOUS BUCK, the experiment the prior agent did not run:
  FW off -> dead -> HS on -> OUT close -> conduct TON -> HS off -> dead -> FW on
  -> freewheel into the bank -> at the inductor current zero, FW off AND OUT open.

The prior agent's C9 instead ties the freewheel gate low for the whole run, which
bounds Qdel/Qsup <= 1 by construction because a buck's charge gain comes entirely
from the freewheel phase (inductor sources charge from GROUND, not the supply).
"""
import sys, os, re, json

def sched(fire, TON, tzero, dead1=4.0, outdel=4.0, dead2=2.0):
    """Return the six edge times for one top-up cell (ps)."""
    fw_off_a, fw_off_b = fire,                fire + 2.0
    hs_on_a,  hs_on_b  = fire + dead1,        fire + dead1 + 2.0
    out_a,    out_b    = hs_on_b + outdel,    hs_on_b + outdel + 2.0
    hs_off_a, hs_off_b = out_b + TON,         out_b + TON + 2.0
    fw_on_a,  fw_on_b  = hs_off_b + dead2,    hs_off_b + dead2 + 2.0
    return dict(fw_off=(fw_off_a, fw_off_b), hs_on=(hs_on_a, hs_on_b),
                out=(out_a, out_b), hs_off=(hs_off_a, hs_off_b),
                fw_on=(fw_on_a, fw_on_b), tzero=tzero)

def pwls(n, s, tend=4400.0, mode="buck"):
    """Gate PWL lines for top-up cell n (3 or 4)."""
    o = []
    # HS pMOS: 1.5 (off) -> 0 (on) -> 1.5 (off)
    o.append("VGTU%d gtu%d 0 PWL(0 1.5 %.4fp 1.5 %.4fp 0 %.4fp 0 %.4fp 1.5)"
             % (n, n, s["hs_on"][0], s["hs_on"][1], s["hs_off"][0], s["hs_off"][1]))
    if mode == "buck":
        # FW nMOS: 1.5 (on, clamping na to 0) -> 0 (off) -> 1.5 (on, freewheel)
        # -> 0 (off) at the inductor current zero
        o.append("VGFW%d gfw%d 0 PWL(0 1.5 %.4fp 1.5 %.4fp 0 %.4fp 0 %.4fp 1.5 %.4fp 1.5 %.4fp 0)"
                 % (n, n, s["fw_off"][0], s["fw_off"][1], s["fw_on"][0], s["fw_on"][1],
                    s["tzero"], s["tzero"] + 2.0))
    elif mode == "fwlate":
        # FW nMOS gate starts LOW and is pulsed HIGH only for the freewheel
        # phase. This gives a REAL freewheel (charge sourced from ground while
        # the inductor ramps down) WITHOUT any gate transition before the pulse,
        # so it cannot produce the pre-pulse turn-off feedthrough that drives
        # the switch node negative and forward-biases the drain-bulk junction.
        o.append("VGFW%d gfw%d 0 PWL(0 0 %.4fp 0 %.4fp 1.5 %.4fp 1.5 %.4fp 0)"
                 % (n, n, s["fw_on"][0], s["fw_on"][1], s["tzero"], s["tzero"] + 2.0))
    else:
        o.append("VGFW%d gfw%d 0 PWL(0 0 %.4fp 0)" % (n, n, tend))
    # OUT transmission gate: closed from out_b until the current zero
    o.append("VGTO%d gto%d 0 PWL(0 0 %.4fp 0 %.4fp 1.5 %.4fp 1.5 %.4fp 0)"
             % (n, n, s["out"][0], s["out"][1], s["tzero"], s["tzero"] + 2.0))
    o.append("VGTOP%d gtop%d 0 PWL(0 1.5 %.4fp 1.5 %.4fp 0 %.4fp 0 %.4fp 1.5)"
             % (n, n, s["out"][0], s["out"][1], s["tzero"], s["tzero"] + 2.0))
    return o

def build(src, dst, L, s3, s4, mode="buck"):
    lines = open(src).read().split("\n")
    out = []
    drop = re.compile(r"^(VGTU[34]|VGFW[34]|VGTO[34]|VGTOP[34])\s")
    for ln in lines:
        s = ln.strip()
        if drop.match(s):
            continue                      # replaced below
        if s.startswith("LTU3 "):
            out.append("LTU3 na3 ntm3 %g" % L); continue
        if s.startswith("LTU4 "):
            out.append("LTU4 na4 ntm4 %g" % L); continue
        if s.startswith("XTUON3 "):
            out.append(ln)
            out.extend(pwls(3, s3, mode=mode))   # put cell 3's gates right here
            continue
        if s.startswith("XTUON4 "):
            out.append(ln)
            out.extend(pwls(4, s4, mode=mode))
            continue
        out.append(ln)
    open(dst, "w").write("\n".join(out))
    return dst

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    L = float(sys.argv[3])
    fire3, ton3, tz3 = [float(x) for x in sys.argv[4].split(",")]
    fire4, ton4, tz4 = [float(x) for x in sys.argv[5].split(",")]
    mode = sys.argv[6] if len(sys.argv) > 6 else "buck"
    s3 = sched(fire3, ton3, tz3); s4 = sched(fire4, ton4, tz4)
    build(src, dst, L, s3, s4, mode)
    print(json.dumps(dict(dst=dst, L=L, s3=s3, s4=s4, mode=mode), indent=1))
