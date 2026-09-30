"""p2 DIAGNOSTIC -- why the unbuffered TG-XOR wave does not restore.

The T-sweep beat decks came back with every scored bank failing its value check by
100-520 mV, and bank 1 -- whose inputs are IDEAL 1.20 V sources -- delivering only
62.8% of its own rail on a cell that is RESTORED, fully selected and should track
the rail.  Something is HOLDING THE OUTPUTS DOWN.

HYPOTHESIS, read off the netlist: while the SUCCESSOR bank's rail is still at 0
(it rises one beat later), that bank's select nodes bb cannot go high, so BOTH of
its transmission-gate pMOS conduct.  Its cell therefore ties the predecessor's
output, through TG1's pMOS, to its own y node, and that y node is tied through
TG2's pMOS to ab -- which its own grounded nMOS holds at 0.  Every predecessor
output is thus RESISTIVELY SHORTED TO GROUND through two series pMOS for the whole
beat before its successor rises, and a pass-gate output has no strength to hold
against that.

THE TEST.  Hold bank 1's rail at dV and bank 1's inputs at their chain values, and
measure the DC current out of each of bank 1's four outputs, with the successor's
rail held at 0 (the chain condition) and then at dV (the control).  If the
hypothesis is right the current is tens of microamps at rail2 = 0 and collapses at
rail2 = dV.  A capacitive load draws NO DC current in either case.
"""
import json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W

HERE = W.HERE


def deck(k, wire, rail2_V, dv=1.65, vgh=2.4, vinhi=1.20, tend=3000.0):
    """Bank k at a FIXED rail = dV with its chain inputs, feeding a real bank k+1
    whose rail is held at rail2_V.  Long enough to reach DC."""
    ws, _ = W.logic()
    win = W.X0 if k == 1 else ws[k - 2]
    kd = k + 1 if k < len(W.ROT) else 1
    wr = W.WIRE[wire]
    r, rd = W.ROT[k - 1], W.ROT[kd - 1]
    L = W.head_lines() + [
        # rail k ramped once then HELD, so the DC state is reached from a
        # convergent start rather than asserted
        "VS rail%d 0 PWL(0 0 200p 0 700p %g %gp %g)" % (k, dv, tend * 2, dv),
        "VHI vhi 0 %g" % vgh,
        "VMG%d gn%d 0 0" % (k, k),
        "VMGD gnd%d 0 0" % kd,
        "VRD rail%d 0 %g" % (kd, rail2_V)]
    for j in range(W.NCELL):
        L.append("VW%d wsrc%d gn%d %g" % (j, j, k, vinhi if win[j] else 0.0))
    for i in range(W.NCELL):
        L += W.cell(k, i, W.FORMS[k - 1][i], "wsrc%d" % i,
                    "wsrc%d" % ((i + r) % W.NCELL), "rail%d" % k, "gn%d" % k)
    # ammeters in series with every output so the current OUT of each y is metered
    for i in range(W.NCELL):
        L.append("VAM%d ytap%d y%d_%d 0" % (i, i, k, i))
    for i in range(W.NCELL):
        ls, a_net = W.wire_seg("s%d_%d" % (kd, i), "ytap%d" % i,
                               "a%d_%d" % (kd, i), wr["strC"], wr["strR"])
        L += ls
        ls, b_net = W.wire_seg("r%d_%d" % (kd, i), "ytap%d" % ((i + rd) % W.NCELL),
                               "b%d_%d" % (kd, i), wr["rotC"][rd], wr["rotR"][rd])
        L += ls
        L += W.cell(kd, i, W.FORMS[kd - 1][i], a_net, b_net,
                    "rail%d" % kd, "gnd%d" % kd)
    L += [".print tran " + " ".join(
        ["V(rail%d)" % k]
        + ["V(y%d_%d)" % (k, i) for i in range(W.NCELL)]
        + ["I(VAM%d)" % i for i in range(W.NCELL)]
        + ["V(ab%d_%d)" % (kd, i) for i in range(W.NCELL)]
        + ["V(bb%d_%d)" % (kd, i) for i in range(W.NCELL)]
        + ["V(y%d_%d)" % (kd, i) for i in range(W.NCELL)]),
        ".tran 2p %gp 0 4p" % tend, ".end"]
    return L


def run1(fn, lines, timeout=900):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([W.XYCE, fn], capture_output=True, text=True,
                       timeout=timeout, cwd=HERE, env=W.ENV)
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        return None, (r.stderr or r.stdout)[-400:], time.monotonic() - t0
    return path + ".prn", None, time.monotonic() - t0


def final(prn, cols):
    hdr, rows = W.read_prn(prn)
    return {c: rows[-1][hdr.index(c.upper())] for c in cols if c.upper() in hdr}


if __name__ == "__main__":
    W.check_logic_against_prereg()
    ws, ps = W.logic()
    out = {"_what": __doc__}
    for wire in ("W2", "W0"):
        out[wire] = {}
        for k in (1, 3):
            out[wire]["bank%d" % k] = {}
            for lbl, v in (("successor_rail_0_THE_CHAIN_CONDITION", 0.0),
                           ("successor_rail_dV_THE_CONTROL", 1.65)):
                fn = "dg_%s_k%d_%s.cir" % (wire, k, "r0" if v == 0.0 else "rdv")
                prn, err, wall = run1(fn, deck(k, wire, v))
                if err:
                    out[wire]["bank%d" % k][lbl] = dict(FAILED=err)
                    print("%s FAILED" % fn, flush=True)
                    continue
                kd = k + 1 if k < len(W.ROT) else 1
                f = final(prn, (["V(rail%d)" % k]
                                + ["V(y%d_%d)" % (k, i) for i in range(W.NCELL)]
                                + ["I(VAM%d)" % i for i in range(W.NCELL)]
                                + ["V(bb%d_%d)" % (kd, i) for i in range(W.NCELL)]))
                want = ws[k - 1]
                rec = dict(rail_V=f["V(rail%d)" % k], wall_s=round(wall, 1))
                for i in range(W.NCELL):
                    rec["cell%d" % i] = dict(
                        path=ps[k - 1][i], form=W.FORMS[k - 1][i], want=want[i],
                        V_out=f["V(y%d_%d)" % (k, i)],
                        I_out_uA=f["I(VAM%d)" % i] * 1e6,
                        successor_bb_V=f["V(bb%d_%d)" % (kd, i)])
                out[wire]["bank%d" % k][lbl] = rec
                print("%-24s rail=%.4f" % (fn, rec["rail_V"]), flush=True)
                for i in range(W.NCELL):
                    c = rec["cell%d" % i]
                    print("   cell%d %s/%s want=%d  V_out=%.4f  I_out=%+9.3f uA"
                          "  succ_bb=%.4f"
                          % (i, c["form"], c["path"], c["want"], c["V_out"],
                             c["I_out_uA"], c["successor_bb_V"]), flush=True)
    json.dump(out, open(os.path.join(HERE, "DIAG_CROWBAR.json"), "w"), indent=1)
    print("wrote DIAG_CROWBAR.json", flush=True)
