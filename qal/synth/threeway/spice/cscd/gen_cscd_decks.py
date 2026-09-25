#!/usr/bin/env python3
"""CSCD (current-sensing completion detection) signature measurement.

Builds Xyce/PSP103 transistor decks for the 56-cell CMOS sha_slice from
work/sha_slice.cmos.v, drives them with CONTROLLED-HAMMING-DISTANCE vectors,
and PRINTS the supply current I(VDD) vs time so we can see what a current
sensor would actually see.

Also builds fault-injected variants:
  sa0/sa1 : driver disconnected, net tied to a rail (clean stuck-at)
  bridge  : resistor from an internal node to a rail (IDDQ defect, function intact)
  contend : net tied to a rail while still driven (metal short, driver fights)

Discipline: .measure tran Q INTEG I(Vsrc) + PARAM (never INTEGRAL of a B-source).
Sign: Xyce reports I(VDD) as current INTO the source's + node, so the block's
supply current is -I(VDD) (positive when the block draws charge).
"""
import re, sys, os, json, random

HERE  = os.path.dirname(os.path.abspath(__file__))
NET   = "/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice.cmos.v"
SPF   = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
COMPAT= "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
VDD   = 1.2
CLOAD = 2.0   # fF on every primary output

# ---------------------------------------------------------------- parse lib
pinorder = {}
for line in open(SPF):
    m = re.match(r'\.subckt\s+(sg13g2_\S+)\s+(.*)', line, re.I)
    if m:
        pinorder[m.group(1).lower()] = m.group(2).split()

# ---------------------------------------------------------------- parse netlist
txt = open(NET).read()
mm  = re.search(r'module\s+sha_slice\s*\((.*?)\);(.*)endmodule', txt, re.S)
body = mm.group(2)

def expand(body, direction):
    out = []
    for m in re.finditer(r'\b%s\b\s*(\[(\d+):(\d+)\])?\s*([A-Za-z_][\w,\s]*);' % direction, body):
        rng, hi, lo, names = m.group(1), m.group(2), m.group(3), m.group(4)
        for nm in names.split(','):
            nm = nm.strip()
            if not nm: continue
            if rng:
                for i in range(int(lo), int(hi)+1):
                    out.append("%s[%d]" % (nm, i))
            else:
                out.append(nm)
    return out

INB  = expand(body, 'input')
OUTB = expand(body, 'output')

INSTS = []
for m in re.finditer(r'(sg13g2_\w+)\s+(\S+)\s*\(\s*(.*?)\)\s*;', txt, re.S):
    ctype, inst, conns = m.group(1).lower(), m.group(2), m.group(3)
    cmap = {}
    for pm in re.finditer(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', conns):
        cmap[pm.group(1)] = pm.group(2).strip()
    INSTS.append((ctype, inst, cmap))

def sanitize(n):
    return n.replace('[', '_').replace(']', '').replace('\\', '').replace('.', '_')

# ---------------------------------------------------------------- logic model
# functions confirmed against
# IHP-Open-PDK/.../lib/sg13g2_stdcell_typ_1p20V_25C.lib output-pin `function:` fields
FUNC = {
 'sg13g2_inv_1':    (lambda p: 1 - p['A'],                                'Y'),
 'sg13g2_nand2_1':  (lambda p: 1 - (p['A'] & p['B']),                     'Y'),
 'sg13g2_nor2_1':   (lambda p: 1 - (p['A'] | p['B']),                     'Y'),
 'sg13g2_nor2b_1':  (lambda p: 1 - (p['A'] | (1 - p['B_N'])),             'Y'),
 'sg13g2_o21ai_1':  (lambda p: 1 - ((p['A1'] | p['A2']) & p['B1']),       'Y'),
 'sg13g2_a21o_1':   (lambda p: (p['A1'] & p['A2']) | p['B1'],             'X'),
 'sg13g2_a21oi_1':  (lambda p: 1 - ((p['A1'] & p['A2']) | p['B1']),       'Y'),
 'sg13g2_and2_1':   (lambda p: p['A'] & p['B'],                           'X'),
 'sg13g2_or2_1':    (lambda p: p['A'] | p['B'],                           'X'),
 'sg13g2_mux2_1':   (lambda p: p['A1'] if p['S'] else p['A0'],            'X'),
 'sg13g2_xnor2_1':  (lambda p: 1 - (p['A'] ^ p['B']),                     'Y'),
 'sg13g2_xor2_1':   (lambda p: p['A'] ^ p['B'],                           'X'),
}

def evaluate(vec, forced=None):
    """Topological evaluation. Returns {net: value}. forced = {net: 0/1} stuck-ats."""
    forced = forced or {}
    st = dict(vec)
    for n, v in forced.items():
        st[n] = v
    pending = list(INSTS)
    for _ in range(64):
        nxt = []
        for ct, inst, cmap in pending:
            fn, opin = FUNC[ct]
            ins = {p: n for p, n in cmap.items() if p != opin}
            if all(cmap[p] in st or cmap[p] in ("1'b0", "1'b1") for p in ins):
                pv = {}
                for p in ins:
                    n = cmap[p]
                    pv[p] = 0 if n == "1'b0" else (1 if n == "1'b1" else st[n])
                o = cmap[opin]
                if o in forced:
                    st[o] = forced[o]
                else:
                    st[o] = fn(pv)
            else:
                nxt.append((ct, inst, cmap))
        pending = nxt
        if not pending:
            break
    assert not pending, "combinational loop / unresolved: %d" % len(pending)
    return st

CELL_OUT_NETS = [cmap[FUNC[ct][1]] for ct, inst, cmap in INSTS]

def node_toggles(s0, s1):
    """Toggles of CELL OUTPUT nets only -- these are the nets whose charge comes
    from VDD. Primary inputs are driven by ideal PWL sources, so their switching
    charge is supplied by those sources, not by VDD."""
    return sum(1 for n in CELL_OUT_NETS if s0[n] != s1[n])

# ---------------------------------------------------------------- vectors
def make_vectors():
    """Controlled input Hamming distance between consecutive windows.

    W3 is the important one: a[0] 0->1 with b=0xFF is a SINGLE input-bit change
    that forces a FULL 8-bit carry ripple (sum 0xFF -> 0x00). It exercises the
    longest sequential path with ~1-2 gates switching per logic level, which is
    the condition under which inter-level current lulls -- the false-completion
    hazard -- should be visible if they exist at all.
    """
    random.seed(20260925)
    z = {b: 0 for b in INB}
    vs = []
    vs.append(("V0_init_allzero", dict(z), None))

    v1 = dict(z)                                          # HD=0 NON-EVENT
    vs.append(("V1_repeat_HD0", v1, 0))

    # SINGLE-GATE window. c[1] drives inverter _32_ -> _13_ -> o21ai _40_ input A1.
    # With a[1]=b[1]=0, _18_=nor2(0,0)=1 and _19_=nand2(0,0)=1, so
    # maj[1] = !((_13_ + _18_) * _19_) = !((x+1)*1) = 0 for either value of _13_.
    # The toggle therefore stops dead at _13_: EXACTLY ONE net switches.
    v2 = dict(z); v2['c[1]'] = 1
    vs.append(("V2_single_gate", v2, 1))

    v3 = dict(v2)
    for i in range(8): v3['b[%d]' % i] = 1                # b = 0xFF, a = 0x00
    vs.append(("V3_setup_b_FF", v3, 8))

    v4 = dict(v3); v4['a[0]'] = 1                         # HD=1 -> FULL CARRY RIPPLE
    vs.append(("V4_carry_ripple_HD1", v4, 1))

    v5 = dict(v4)
    for b in random.sample(INB, 24): v5[b] ^= 1           # HD=24
    vs.append(("V5_HD24", v5, 24))

    v6 = {b: 1 - v5[b] for b in INB}                      # HD=48 full complement
    vs.append(("V6_HD48", v6, 48))

    v7 = dict(v6)                                         # HD=0 NON-EVENT, busy state
    vs.append(("V7_repeat_HD0", v7, 0))
    return vs

# ---------------------------------------------------------------- deck
def build_deck(vecs, tvec_ns, tstep_ps, faults=None, title="golden",
               extra_nets=(), method=None):
    """faults: list of dicts.
       {'kind':'sa','net':'_16_','val':0}        driver removed, net tied to rail
       {'kind':'bridge','net':'_16_','to':'vdd','r':1e5}
       {'kind':'contend','net':'_16_','to':'vdd'} net driven AND tied (driver fights)
    """
    faults = faults or []
    sa = {f['net']: f['val'] for f in faults if f['kind'] == 'sa'}

    L = ["* CSCD supply-current signature: CMOS sha_slice (56 SG13G2 stdcells) -- %s" % title,
         '.hdl "%s"' % VA,
         '.include "%s"' % MODEL,
         '.include "%s"' % COMPAT,
         '.include "%s"' % SPF,
         "VDD vdd 0 %g" % VDD,
         "VSS vss 0 0"]

    # PWL input drivers
    for b in INB:
        sb = sanitize(b)
        pts = []
        for k, (nm, v, hd) in enumerate(vecs):
            t0 = k * tvec_ns
            if k == 0:
                pts.append("0 %g" % (v[b] * VDD))
            else:
                pts.append("%.5gn %g" % (t0, vecs[k-1][1][b] * VDD))
                pts.append("%.5gn %g" % (t0 + 0.05, v[b] * VDD))
        pts.append("%.5gn %g" % (len(vecs) * tvec_ns, vecs[-1][1][b] * VDD))
        L.append("V%s %s 0 PWL(%s)" % (sb, sb, " ".join(pts)))

    def netmap(n):
        n = n.strip()
        if n in ("1'b0", "1'h0"): return "0"
        if n in ("1'b1", "1'h1"): return "vdd"
        return sanitize(n)

    for ct, inst, cmap in INSTS:
        order = pinorder[ct]
        _, opin = FUNC[ct]
        pins = []
        for p in order:
            if p == "VDD": pins.append("vdd")
            elif p == "VSS": pins.append("vss")
            else:
                n = cmap.get(p, "0")
                # clean stuck-at: disconnect this driver's output
                if p == opin and n in sa:
                    pins.append(sanitize(n) + "_open")
                else:
                    pins.append(netmap(n))
        L.append("X%s %s %s" % (sanitize(inst), " ".join(pins), ct))

    # stuck-at rail ties (driver already disconnected above)
    for f in faults:
        if f['kind'] == 'sa':
            L.append("V_SA_%s %s 0 %g" % (sanitize(f['net']), sanitize(f['net']),
                                          VDD if f['val'] else 0.0))
            L.append("C_SA_%s %s 0 1f" % (sanitize(f['net']), sanitize(f['net']) + "_open"))
        elif f['kind'] == 'bridge':
            L.append("R_BR_%s %s %s %g" % (sanitize(f['net']), sanitize(f['net']),
                                           f['to'], f['r']))
        elif f['kind'] == 'contend':
            # hard metal short to the RAIL NODE (not to a separate source), so the
            # contention current is drawn from VDD and therefore appears in I(VDD)
            L.append("R_CT_%s %s %s %g" % (sanitize(f['net']), sanitize(f['net']),
                                           f['to'], f.get('r', 1.0)))

    # output loads
    for o in OUTB:
        L.append("CL%s %s 0 %gf" % (sanitize(o), sanitize(o), CLOAD))

    ttot = len(vecs) * tvec_ns
    # NO uic: the DC operating point converges (14 s) and starting from it removes
    # a ~170 nA slow settling tail that otherwise masks the real 1.56 nA floor by 109x.
    L.append(".tran %gp %gn" % (tstep_ps, ttot))
    # print supply current AND every primary output, so the LAST real transition
    # time is measurable in the same run as the current waveform
    L.append(".print tran format=noindex I(VDD) %s"
             % " ".join("V(%s)" % sanitize(o) for o in list(OUTB) + list(extra_nets)))
    if method is not None:
        L.append(".options timeint method=%d" % method)
    # Without DELMAX Xyce takes ~0.6 ns steps in the settled tail and the printed
    # current is then dominated by integration noise (~1e-7 A, i.e. 30x the real
    # leakage). Cap the step and tighten both the LTE and the Newton tolerances.
    L.append(".options timeint reltol=1e-6 abstol=1e-12 delmax=%ge-12" % tstep_ps)
    # NONLIN-TRAN only: tightening plain NONLIN (the DCOP solver) makes the t=0
    # operating point fail to converge ("Failed DCOP Steps 1"). And abstol=1e-13
    # is unreachable once a window draws mA -- that asks Newton for 9 decades of
    # dynamic range and aborts with "Time step too small" at the first big vector
    # (measured: step 2055, t=7.55 ns). 1e-12 A still resolves the 1.56 nA floor
    # to 0.06%; what actually fixed that floor was dropping uic, not this.
    L.append(".options nonlin-tran abstol=1e-12 reltol=1e-6")
    L.append(".options output initialinterval=%ge-12" % tstep_ps)

    # per-window charge
    for k, (nm, v, hd) in enumerate(vecs):
        if k == 0: continue
        t0 = k * tvec_ns; t1 = (k + 1) * tvec_ns
        L.append(".measure tran Q%d INTEG I(VDD) from=%gn to=%gn" % (k, t0, t1))
        L.append(".measure tran E%d PARAM {%g*Q%d}" % (k, -VDD, k))
        # quiescent floor: last 0.5 ns of the window
        L.append(".measure tran IQ%d AVG I(VDD) from=%gn to=%gn" % (k, t1 - 0.5, t1))
        L.append(".measure tran IPK%d MIN I(VDD) from=%gn to=%gn" % (k, t0, t1))
    L.append(".end")
    return "\n".join(L) + "\n"

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    tvec = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    nwin = int(sys.argv[3]) if len(sys.argv) > 3 else 7

    vecs = make_vectors()[:nwin]

    # activity census (logic level) for each window
    census = []
    states = [evaluate(v) for _, v, _ in vecs]
    for k in range(1, len(vecs)):
        census.append({
            "window": k,
            "name": vecs[k][0],
            "hd_in": vecs[k][2],
            "internal_node_toggles": node_toggles(states[k-1], states[k]),
            "output_toggles": sum(1 for o in OUTB if states[k-1][o] != states[k][o]),
        })
    json.dump({"n_cells": len(INSTS), "n_inputs": len(INB), "n_outputs": len(OUTB),
               "tvec_ns": tvec, "windows": census},
              open(os.path.join(HERE, "activity_census.json"), "w"), indent=1)
    print("cells=%d inputs=%d outputs=%d" % (len(INSTS), len(INB), len(OUTB)))
    for c in census:
        print("  W%d %-16s HD_in=%2d  net_toggles=%3d  out_toggles=%2d"
              % (c['window'], c['name'], c['hd_in'],
                 c['internal_node_toggles'], c['output_toggles']))

    decks = {
      "golden":      [],
      "sa0_16":      [{'kind': 'sa',      'net': '_16_', 'val': 0}],
      "br100k_16":   [{'kind': 'bridge',  'net': '_16_', 'to': 'vdd', 'r': 1e5}],
      "contend1_16": [{'kind': 'contend', 'net': '_16_', 'to': 'vdd'}],
    }
    for nm, f in decks.items():
        fn = os.path.join(HERE, "cscd_%s.cir" % nm)
        open(fn, "w").write(build_deck(vecs, tvec, step, f, nm))
        print("wrote", fn)
