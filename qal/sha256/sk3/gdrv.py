#!/usr/bin/env python3
"""SKEPTIC: MEASURE the gate-drive cost of the block's timing hardware.

The headline decks drive all 42 transfer-switch gates from IDEAL PWL sources.
BUILD correctly flags that as a booking and correctly says the totals are lower
bounds, but the SIZE of the bound it reports is the ideal source's own recovered
integral (-22.5 fJ), which is not what a real driver pays.  What a real driver
pays is set by the SWITCH GATE CAPACITANCE, and these switches are large
(40u/80u per wide bank).  So measure it.

Stage A  qgate  : all 42 switch gates ramped 0 -> VGH -> 0 from a metered ideal
                  source, with the switch terminals held at representative bias.
                  Q_gate from the integral; a real driver switching that charge
                  from a VGH supply dissipates Q_gate*VGH per full cycle.
Stage B  realdrv: the same 42 gates driven by REAL CMOS inverters from a metered
                  VGH supply, so the dissipated energy is measured rather than
                  inferred.  Excludes the pre-driver chain -> still a LOWER BOUND.

Geometry is read out of the headline deck so it is the block's own hardware.
"""
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
VA = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_sk3")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
DECK = os.path.join(HERE, "..", "p2", "b_HF300.cir")
VGH = 1.65


def switches():
    txt = open(DECK).read()
    out = []
    for m in re.finditer(r"^(XSW[NP]\d+|XPK\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+"
                         r"(sg13_lv_[pn]mos)\s+w=([\d.]+)u\s+l=([\d.]+)u", txt, re.M):
        nm, d, g, s, b, mod, w, l = m.groups()
        out.append(dict(nm=nm, d=d, g=g, s=s, b=b, mod=mod,
                        w=float(w), l=float(l)))
    return out


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17"]


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def deck(mode, vrail):
    """mode 'qgate': ideal metered gate source.  mode 'realdrv': CMOS drivers."""
    sw = switches()
    L = head() + ["VR vr 0 %g" % vrail, "VSWN vsn 0 %g" % vrail,
                  "VHI vhi 0 %g" % VGH, "VZ vz 0 0"]
    # gate command: 0 -> VGH at 100 ps, back to 0 at 600 ps (one full cycle)
    L += ["VCMD cmd 0 PWL(0 0 98p 0 102p %g 598p %g 602p 0 1200p 0)" % (VGH, VGH)]
    nodes = {}
    for k, s in enumerate(sw):
        # terminals: pMOS bulk -> vhi ; everything else to the held rail nodes
        dn = "vr" if s["d"].startswith("sw") else "vsn"
        sn = "vsn" if s["s"].startswith("rail") else ("vhi" if s["s"] == "vhi"
                                                      else ("vz" if s["s"] == "0"
                                                            else "vr"))
        bn = "vhi" if s["mod"].endswith("pmos") else "vz"
        if s["nm"].startswith("XPK"):
            dn, sn, bn = "vr", "vz", "vz"
        gn = "gg%d" % k
        nodes[k] = gn
        L.append("XS%d %s %s %s %s %s w=%gu l=%gu"
                 % (k, dn, gn, sn, bn, s["mod"], s["w"], s["l"]))
    if mode == "qgate":
        # ONE metered ideal source drives every gate: Q and E read off integrators
        L += ["VG gnet 0 PWL(0 0 98p 0 102p %g 598p %g 602p 0 1200p 0)" % (VGH, VGH)]
        for k in nodes:
            L.append("RG%d gnet %s 0.001" % (k, nodes[k]))
        L += integ("qg", "-I(VG)") + integ("eg", "-V(gnet)*I(VG)")
        pr = ["V(gnet)", "V(xqg)", "V(xeg)", "I(VG)"]
    else:
        # REAL CMOS inverter per gate from a metered VGH supply.  Driver sized at
        # 1/8 of the switch it drives (a normal fanout-of-8 final stage).
        L += ["VDRV vdrv 0 %g" % VGH]
        for k, s in enumerate(sw):
            wp = max(0.2, s["w"] / 8.0 * 2.0 / 3.0)
            wn = max(0.15, s["w"] / 8.0 / 3.0)
            L += ["XDP%d %s cmdb vdrv vdrv sg13_lv_pmos w=%gu l=0.13u"
                  % (k, nodes[k], wp),
                  "XDN%d %s cmdb 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, nodes[k], wn)]
        # the driver's own input: an ideal PWL pre-driver (EXCLUDED -> lower bound)
        L += ["VCB cmdb 0 PWL(0 %g 98p %g 102p 0 598p 0 602p %g 1200p %g)"
              % (VGH, VGH, VGH, VGH)]
        L += integ("edrv", "-%g*I(VDRV)" % VGH)
        pr = ["V(vdrv)", "V(xedrv)", "I(VDRV)"]
    L += [".print tran " + " ".join(pr), ".tran 0.2p 1200p 0 0.5p",
          ".measure tran M_Z FIND V(x%s) AT=0.5p" % ("qg" if mode == "qgate" else "edrv"),
          ".measure tran M_UP FIND V(x%s) AT=590p" % ("qg" if mode == "qgate" else "edrv"),
          ".measure tran M_D FIND V(x%s) AT=1195p" % ("qg" if mode == "qgate" else "edrv"),
          ".end"]
    if mode == "qgate":
        L.insert(-1, ".measure tran E_Z FIND V(xeg) AT=0.5p")
        L.insert(-1, ".measure tran E_UP FIND V(xeg) AT=590p")
        L.insert(-1, ".measure tran E_D FIND V(xeg) AT=1195p")
    return L, sw


def run(fn, lines):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=2400,
                       cwd=HERE, env=ENV)
    if not os.path.exists(p + ".prn"):
        return None, "FAIL " + r.stdout[-600:]
    return p, "ok %.0fs" % (time.monotonic() - t)


def mt(path):
    out = {}
    for m in re.finditer(r"^\s*(\w+)\s*=\s*([-+\d.eE]+)", open(path).read(), re.M):
        out[m.group(1).upper()] = float(m.group(2))
    if not out:
        lines = [l.split() for l in open(path).read().splitlines() if l.strip()]
        hdr = [x.upper() for x in lines[0]]
        vals = lines[1]
        out = {hdr[i]: float(vals[i]) for i in range(min(len(hdr), len(vals)))}
    return out


if __name__ == "__main__":
    mode, vrail = sys.argv[1], float(sys.argv[2])
    tag = "%s_vr%d" % (mode, round(vrail * 1000))
    lines, sw = deck(mode, vrail)
    p, m = run("g_%s.cir" % tag, lines)
    print(m, flush=True)
    assert p, m
    d = mt(p + ".mt0")
    tw = sum(s["w"] for s in sw)
    ga = sum(s["w"] * s["l"] for s in sw)
    r = dict(mode=mode, v_rail_held=vrail, n_switch_devices=len(sw),
             total_switch_width_um=tw, total_gate_area_um2=ga)
    if mode == "qgate":
        q_up = (d["M_UP"] - d["M_Z"]) * 1e15
        e_up = (d["E_UP"] - d["E_Z"]) * 1e15
        r.update(Q_gate_charge_up_fC=q_up,
                 C_gate_effective_fF=q_up / VGH,
                 Cox_implied_fF_per_um2=q_up / VGH / ga,
                 E_ideal_source_up_fJ=e_up,
                 E_real_driver_full_cycle_LOWER_BOUND_fJ=q_up * VGH / 1000.0 * 1000.0)
    else:
        r.update(E_driver_supply_full_cycle_fJ=(d["M_D"] - d["M_Z"]) * 1e15,
                 E_driver_supply_rise_only_fJ=(d["M_UP"] - d["M_Z"]) * 1e15)
    json.dump(r, open(os.path.join(HERE, "GDRV_%s.json" % tag), "w"), indent=1)
    for k, v in r.items():
        print("  %-42s %s" % (k, v))
