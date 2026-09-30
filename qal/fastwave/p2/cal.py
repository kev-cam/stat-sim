"""p2 stage 1 -- the IN-SITU per-bank rail capacitance.

  cp1_n4            INSTRUMENT CHECK.  Phase 1's OWN fw.cbank_deck(4) is imported
                    and called, not re-implemented, and must reproduce
                    CBANK.json["N4"] at rel 0 on every quantity.  (An earlier
                    hand-reproduction of that deck came back at rel 7.05e-07
                    because it dropped two of Phase 1's 1 F integrators -- see
                    AMENDMENT P4.  Re-implementing an instrument is not checking
                    it.)

  ci_k_<wire>_<T>   bank k AS WIRED IN THE CHAIN, ramped 0 -> dV over T_ramp, with
                    its own forms, its own input word, its own output wire
                    segments and a REAL bank k+1 receiving them at rail = 0 V.
                    Run at TWO ramp rates, because the slow-ramp secant number is
                    CONTAMINATED BY A DC PATH (AMENDMENT P4):

                        Q(T) = Q_cap + T * K,   K = (1/dV) * integral I_dc(V) dV

                    which is EXACT for a linear ramp, since stretching the ramp
                    stretches the DC contribution proportionally and leaves the
                    capacitive one alone.  Two ramp rates therefore separate the
                    two terms with no fitting and no assumption beyond linearity
                    of the ramp itself.
"""
import json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, W_P1 := os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import w as W

HERE = W.HERE
TRAMP = (4000.0, 8000.0)          # ps -- the two ramp rates


def p1_deck(n):
    """Phase 1's OWN deck builder, imported.  fw.py reads module globals for its
    constants, which is fine here because this is a reproduction of Phase 1 and
    those globals ARE Phase 1's committed values; nothing from this phase is
    allowed to reach it."""
    sys.path.insert(0, W.P1)
    import fw
    assert fw.DV == 1.65 and fw.VGH == 1.5 and fw.VINHI == 1.20
    assert fw.VEC == [(0, 1), (1, 1), (1, 0), (0, 0)]
    return fw.cbank_deck(n), fw


def insitu_deck(k, wire, t_ramp, dv=1.65, vgh=2.4, vinhi=1.20,
                restore=False):
    """Bank k's rail load AS WIRED IN THE CHAIN."""
    ws, _ = W.logic()
    win = W.X0 if k == 1 else ws[k - 2]
    kd = k + 1 if k < len(W.ROT) else 1
    wr = W.WIRE[wire]
    r = W.ROT[k - 1]
    L = W.head_lines() + ["VS rail%d 0 PWL(0 0 %gp %g)" % (k, t_ramp, dv),
                          "VHI vhi 0 %g" % vgh,
                          "VMG%d gn%d 0 0" % (k, k),
                          "VMGD gnd%d 0 0" % kd,
                          "VRD rail%d 0 0" % kd]
    srcs = []
    for j in range(W.NCELL):
        L.append("VW%d wsrc%d gn%d %g" % (j, j, k, vinhi if win[j] else 0.0))
        srcs.append("I(VW%d)" % j)
    for i in range(W.NCELL):
        L += W.cell(k, i, W.FORMS[k - 1][i], "wsrc%d" % i,
                    "wsrc%d" % ((i + r) % W.NCELL), "rail%d" % k, "gn%d" % k,
                    restore=restore)
    rd = W.ROT[kd - 1]
    for i in range(W.NCELL):
        ls, a_net = W.wire_seg("s%d_%d" % (kd, i), "y%d_%d" % (k, i),
                               "a%d_%d" % (kd, i), wr["strC"], wr["strR"])
        L += ls
        ls, b_net = W.wire_seg("r%d_%d" % (kd, i),
                               "y%d_%d" % (k, (i + rd) % W.NCELL),
                               "b%d_%d" % (kd, i), wr["rotC"][rd], wr["rotR"][rd])
        L += ls
        L += W.cell(kd, i, W.FORMS[kd - 1][i], a_net, b_net,
                    "rail%d" % kd, "gnd%d" % kd, restore=restore)
    L += W.integ("qvs", "-I(VS)")
    L += W.integ("qmg", "I(VMG%d)" % k)
    L += W.integ("qmgd", "I(VMGD)")
    L += W.integ("qrd", "-I(VRD)")
    L += W.integ("qin", "+".join(srcs))
    L += [".print tran V(rail%d) V(xqvs) V(xqmg) V(xqmgd) V(xqrd) V(xqin) " % k
          + " ".join("V(y%d_%d)" % (k, i) for i in range(W.NCELL))
          + " " + " ".join("V(y%d_%d)" % (kd, i) for i in range(W.NCELL)),
          ".tran %gp %gp 0 %gp" % (t_ramp / 2000.0, t_ramp, t_ramp / 1000.0),
          ".end"]
    return L


def extract(prn, vcol, dv, extra_cols=()):
    hdr, rows = W.read_prn(prn)
    iv, iq = hdr.index(vcol), hdr.index("V(XQVS)")
    q0 = rows[0][iq]
    pts = [(rr[iv], (rr[iq] - q0) * 1e15) for rr in rows if rr[iv] >= 0]
    out = {}
    for vt in (0.60, 0.80, 0.9642, 1.00, 1.20, 1.40, dv):
        prev = None
        for v, q in pts:
            if prev and prev[0] <= vt <= v:
                f = (vt - prev[0]) / (v - prev[0]) if v != prev[0] else 0.0
                out["C_secant_at_%.4fV_fF" % vt] = (prev[1] + f * (q - prev[1])) / vt
                break
            prev = (v, q)
    lo, hi, ql, qh, prev = 0.90, 1.10, None, None, None
    for v, q in pts:
        if prev and prev[0] <= lo <= v:
            ql = prev[1] + (lo - prev[0]) / (v - prev[0]) * (q - prev[1])
        if prev and prev[0] <= hi <= v:
            qh = prev[1] + (hi - prev[0]) / (v - prev[0]) * (q - prev[1])
        prev = (v, q)
    if ql is not None and qh is not None:
        out["C_diff_0p9_to_1p1V_fF"] = (qh - ql) / (hi - lo)
    out["Q_total_at_dV_fC"] = pts[-1][1]
    out["C_secant_dV_fF"] = out.get("C_secant_at_%.4fV_fF" % dv)
    # the A4 DIAGNOSTIC, carried on every row: a capacitance FLATTENS.
    c8, c16 = out.get("C_secant_at_0.8000V_fF"), out.get("C_secant_dV_fF")
    if c8 and c16:
        out["A4_secant_rise_0p8_to_dV_pct"] = 100.0 * (c16 / c8 - 1.0)
    if out.get("C_diff_0p9_to_1p1V_fF") and c16:
        out["A4_Cdiff_over_Csecant"] = out["C_diff_0p9_to_1p1V_fF"] / c16
    for col, nm in (("V(XQMG)", "Q_bank_ground_return_fC"),
                    ("V(XQMGD)", "Q_downstream_ground_return_fC"),
                    ("V(XQRD)", "Q_into_downstream_rail_fC"),
                    ("V(XQIN)", "Q_from_input_sources_fC"),
                    ("V(XQBK)", "Q_KCL_contaminated_fC")):
        if col in hdr:
            i = hdr.index(col)
            out[nm] = (rows[-1][i] - rows[0][i]) * 1e15
    for c in extra_cols:
        if c in hdr:
            out["V_end_" + c] = rows[-1][hdr.index(c)]
    return out


def bare_run(fn, lines, timeout=900):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([W.XYCE, fn], capture_output=True, text=True,
                       timeout=timeout, cwd=HERE, env=W.ENV)
    if "build_vae_so" in r.stdout:
        sys.stderr.write("WARNING %s triggered a PyMS build\n" % fn)
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        return None, (r.stderr or r.stdout)[-400:], time.monotonic() - t0
    return path + ".prn", None, time.monotonic() - t0


def one(args):
    k, wire, t_ramp = args[:3]
    restore = args[3] if len(args) > 3 else False
    fn = "ci%s_%d_%s_%g.cir" % ("r" if restore else "", k, wire, t_ramp)
    prn, err, wall = bare_run(fn, insitu_deck(k, wire, t_ramp, restore=restore))
    if err:
        return (k, wire, t_ramp, restore), dict(FAILED=err)
    g = extract(prn, "V(RAIL%d)" % k, 1.65,
                extra_cols=tuple("V(Y%d_%d)" % (k, i) for i in range(W.NCELL)))
    g["wall_s"] = round(wall, 1)
    g["t_ramp_ps"] = t_ramp
    g["rot"] = W.ROT[k - 1]
    g["forms"] = "".join(W.FORMS[k - 1])
    g["paths"] = "".join(W.logic()[1][k - 1])
    g["restore"] = restore
    return (k, wire, t_ramp, restore), g


if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor, as_completed
    W.check_logic_against_prereg()
    out = {}
    # ---------------- INSTRUMENT CHECK: Phase 1's own deck builder ------------
    lines, fw = p1_deck(4)
    prn, err, wall = bare_run("cp1_n4.cir", lines)
    ref = json.load(open(os.path.join(W.P1, "CBANK.json")))["N4"]
    if err:
        out["INSTRUMENT_CHECK"] = dict(verdict="FAIL", err=err)
    else:
        got = fw.cbank_extract(prn, 4)          # Phase 1's OWN extractor, too
        rel = {k: (abs(got[k] - ref[k]) / abs(ref[k]) if isinstance(ref.get(k), float)
                   and ref[k] else None) for k in got if k in ref}
        mx = max(v for v in rel.values() if v is not None)
        out["INSTRUMENT_CHECK"] = dict(
            verdict=("PASS" if mx == 0.0 else "DRIFT"), max_rel=mx,
            wall_s=round(wall, 1), per_quantity_rel=rel, measured=got,
            committed_reference="qal/fastwave/CBANK.json N4",
            method="Phase 1's fw.cbank_deck(4) and fw.cbank_extract IMPORTED and "
                   "called, not re-implemented (AMENDMENT P4).")
        print("INSTRUMENT CHECK %s  max rel %.3e  (%.1f s)"
              % (out["INSTRUMENT_CHECK"]["verdict"], mx, wall), flush=True)
    # ---------------- in situ, per bank, per wire, at TWO ramp rates ----------
    RESTORE = os.environ.get("P2_RESTORE") == "1"
    WIRES = (("W2", "W0") if RESTORE else ("W2", "W0", "W1", "WL"))
    jobs = [(k, wr, tr, RESTORE) for wr in WIRES
            for k in range(1, len(W.ROT) + 1) for tr in TRAMP]
    res = {}
    with ProcessPoolExecutor(max_workers=5) as ex:
        fs = {ex.submit(one, j): j for j in jobs}
        for f in as_completed(fs):
            key, g = f.result()
            res[key] = g
            if "FAILED" in g:
                print("  bank%d %s T=%g restore=%s FAILED" % key, flush=True)
            else:
                print("  bank%d %-3s T=%5g  C_sec=%8.3f fF  rise(0.8->dV)=%+6.1f%% "
                      " Cdiff/Csec=%.2f  Qgnd=%8.1f fC"
                      % (key[0], key[1], key[2], g["C_secant_dV_fF"],
                         g["A4_secant_rise_0p8_to_dV_pct"],
                         g["A4_Cdiff_over_Csecant"],
                         g.get("Q_bank_ground_return_fC", 0)), flush=True)
    # ---------------- the two-rate separation --------------------------------
    for wire in WIRES:
        out[wire] = {}
        cs = []
        for k in range(1, len(W.ROT) + 1):
            a = res.get((k, wire, TRAMP[0], RESTORE))
            b = res.get((k, wire, TRAMP[1], RESTORE))
            if not a or not b or "FAILED" in a or "FAILED" in b:
                out[wire]["bank%d" % k] = dict(FAILED="one or both ramps failed")
                continue
            q1, q2 = a["Q_total_at_dV_fC"], b["Q_total_at_dV_fC"]
            K = (q2 - q1) / (TRAMP[1] - TRAMP[0])          # fC/ps = uA
            qcap = q1 - TRAMP[0] * K
            d = dict(
                C_TRUE_fF=qcap / 1.65,
                Q_cap_fC=qcap,
                K_dc_uA=K,
                Q_total_4ns_fC=q1, Q_total_8ns_fC=q2,
                C_secant_4ns_CONTAMINATED_fF=a["C_secant_dV_fF"],
                C_secant_8ns_CONTAMINATED_fF=b["C_secant_dV_fF"],
                dc_share_of_4ns_Q_pct=100.0 * (TRAMP[0] * K) / q1,
                A4_secant_rise_0p8_to_dV_pct=a["A4_secant_rise_0p8_to_dV_pct"],
                A4_Cdiff_over_Csecant=a["A4_Cdiff_over_Csecant"],
                rot=a["rot"], forms=a["forms"], paths=a["paths"],
                Q_bank_ground_return_fC=a.get("Q_bank_ground_return_fC"),
                Q_downstream_ground_return_fC=a.get("Q_downstream_ground_return_fC"),
                Q_into_downstream_rail_fC=a.get("Q_into_downstream_rail_fC"),
                Q_from_input_sources_fC=a.get("Q_from_input_sources_fC"),
                curves_4ns={q: a[q] for q in a if q.startswith("C_secant_at")},
                wall_s=a["wall_s"] + b["wall_s"])
            out[wire]["bank%d" % k] = d
            cs.append(d["C_TRUE_fF"])
        if cs:
            out[wire]["_mean_C_TRUE_fF"] = sum(cs) / len(cs)
            out[wire]["_min_C_TRUE_fF"] = min(cs)
            out[wire]["_max_C_TRUE_fF"] = max(cs)
            out[wire]["_spread_pct"] = 100.0 * (max(cs) - min(cs)) / (sum(cs) / len(cs))
            out[wire]["_mean_fF"] = out[wire]["_mean_C_TRUE_fF"]   # drive.py key
            print("%-3s  C_TRUE mean %8.3f fF   min %7.3f  max %7.3f  spread %5.1f%%"
                  % (wire, out[wire]["_mean_C_TRUE_fF"], out[wire]["_min_C_TRUE_fF"],
                     out[wire]["_max_C_TRUE_fF"], out[wire]["_spread_pct"]), flush=True)
    out["_METHOD"] = (
        "Q(T_ramp) = Q_cap + T_ramp*K, solved from T_ramp = 4000 and 8000 ps.  "
        "EXACT for a linear ramp: stretching the ramp scales the DC term by the "
        "same factor and leaves the capacitive term alone.  K is the DC crowbar "
        "current in uA (fC/ps), a MEASURED quantity, and C_TRUE_fF = Q_cap/dV is "
        "the charge-equivalent capacitance a tank must be sized against.")
    nm = "CBANK_INSITU_RESTORE.json" if RESTORE else "CBANK_INSITU.json"
    out["_restore"] = RESTORE
    json.dump(out, open(os.path.join(HERE, nm), "w"), indent=1)
    print("wrote %s" % nm, flush=True)
