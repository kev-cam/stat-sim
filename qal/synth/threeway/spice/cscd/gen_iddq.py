#!/usr/bin/env python3
"""Static (IDDQ) decks for the CMOS sha_slice.

Use (B) health/defect detection: DC operating point, no transient, so these are
cheap. Two questions:
  1. What is the golden quiescent current, and how much does it vary with the
     INPUT VECTOR? (that spread is the noise floor for absolute-threshold IDDQ)
  2. How large a defect conductance is detectable? -> sweep a bridge resistor
     from an internal node to VDD and watch I(VDD).

Sign: Xyce reports I(VDD) into the source + node; block current = -I(VDD).
"""
import os, sys, json
import gen_cscd_decks as G

HERE = os.path.dirname(os.path.abspath(__file__))
VDD = G.VDD
TRAN_MODE = "--tran" in sys.argv     # fallback if the DC op point will not converge
SUF = "_tr" if TRAN_MODE else ""


def static_deck(vec, faults=None, step_r=None, title="iddq"):
    faults = faults or []
    sa = {f['net']: f['val'] for f in faults if f['kind'] == 'sa'}
    L = ["* IDDQ static: CMOS sha_slice -- %s" % title,
         '.hdl "%s"' % G.VA,
         '.include "%s"' % G.MODEL,
         '.include "%s"' % G.COMPAT,
         '.include "%s"' % G.SPF,
         "VDD vdd 0 %g" % VDD,
         "VSS vss 0 0"]
    for b in G.INB:
        L.append("V%s %s 0 %g" % (G.sanitize(b), G.sanitize(b), vec[b] * VDD))

    def netmap(n):
        n = n.strip()
        if n in ("1'b0", "1'h0"): return "0"
        if n in ("1'b1", "1'h1"): return "vdd"
        return G.sanitize(n)

    for ct, inst, cmap in G.INSTS:
        order = G.pinorder[ct]
        _, opin = G.FUNC[ct]
        pins = []
        for p in order:
            if p == "VDD": pins.append("vdd")
            elif p == "VSS": pins.append("vss")
            else:
                n = cmap.get(p, "0")
                if p == opin and n in sa:
                    pins.append(G.sanitize(n) + "_open")
                else:
                    pins.append(netmap(n))
        L.append("X%s %s %s" % (G.sanitize(inst), " ".join(pins), ct))

    for f in faults:
        if f['kind'] == 'sa':
            L.append("V_SA_%s %s 0 %g" % (G.sanitize(f['net']), G.sanitize(f['net']),
                                          VDD if f['val'] else 0.0))
            L.append("R_SA_%s %s 0 1e12" % (G.sanitize(f['net']), G.sanitize(f['net']) + "_open"))
        elif f['kind'] == 'bridge':
            L.append("R_BR_%s %s %s {RBR}" % (G.sanitize(f['net']), G.sanitize(f['net']), f['to']))

    for o in G.OUTB:
        L.append("CL%s %s 0 %gf" % (G.sanitize(o), G.sanitize(o), G.CLOAD))

    if step_r is not None:
        L.insert(6, ".param RBR=1e12")
    probes = " ".join("V(%s)" % G.sanitize(n) for n in ("_16_", "_17_", "maj[0]", "sum[1]"))
    if TRAN_MODE:
        # fallback if the DC operating point will not converge: settle in a short
        # transient and average the current over the settled tail
        L.append(".tran 10p 6n uic")
        L.append(".print tran format=noindex I(VDD) %s" % probes)
        L.append(".measure tran IQ AVG I(VDD) from=4n to=6n")
    else:
        # sweep the supply: gives the operating point at 1.20 V AND the IDDQ-vs-Vdd
        # sensitivity (the largest PVT lever) in the same run
        L.append(".dc VDD 1.08 1.32 0.06")
        L.append(".print dc format=noindex I(VDD) %s" % probes)
    if step_r is not None:
        L.append(".step RBR LIST %s" % " ".join("%g" % r for r in step_r))
    L.append(".end")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    vecs = G.make_vectors()
    # (1) vector-to-vector IDDQ spread, golden block: one deck, .STEP over vectors
    #     is not available for input sources, so emit one deck per vector.
    for k, (nm, v, hd) in enumerate(vecs):
        fn = os.path.join(HERE, "iddq_golden%s_w%d.cir" % (SUF, k))
        open(fn, "w").write(static_deck(v, [], None, "golden %s" % nm))
    print("wrote iddq_golden_w0..w%d.cir" % (len(vecs) - 1))

    # (2) defect conductance sweep at a fixed vector (V5, the busy one)
    RLIST = [1e3, 3e3, 1e4, 3e4, 1e5, 3e5, 1e6, 3e6, 1e7, 3e7, 1e8, 3e8, 1e9, 1e12]
    fn = os.path.join(HERE, "iddq_bridge_sweep%s.cir" % SUF)
    open(fn, "w").write(static_deck(vecs[5][1],
                                    [{'kind': 'bridge', 'net': '_16_', 'to': 'vdd'}],
                                    RLIST, "bridge _16_->VDD sweep @ V5"))
    print("wrote", fn, "RBR list:", RLIST)

    # (3) clean stuck-at-0 on _16_, static -- expect IDDQ ~ unchanged (no contention)
    fn = os.path.join(HERE, "iddq_sa0%s_w5.cir" % SUF)
    open(fn, "w").write(static_deck(vecs[5][1], [{'kind': 'sa', 'net': '_16_', 'val': 0}],
                                    None, "stuck-at-0 _16_ @ V5"))
    print("wrote", fn)
