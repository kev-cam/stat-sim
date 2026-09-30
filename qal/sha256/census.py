#!/usr/bin/env python3
"""PHASE 1(b): the per-family QAL SETTLING CENSUS.

Thin wrapper over the committed qal/skept/sk.py bank (IMPORTED, not copied): its
topology, its true-ZCS probe, its waveform-only extractor.  Rebound here:
  sk.HERE -> this directory,  sk.ENV -> own PYMS_VAE_CACHE,  sk.VGH -> max(1.5,dV)
and ONE substantive override: sk.cells is replaced so the bank carries the REAL PDK
std-cell of each family instead of a hand-built inverter/o21ai.

Declared modification to the PDK subckt (PRE_REGISTERED phase1b.device_source):
the device lines are VERBATIM from sg13g2_stdcell.spice; the shim zeroes ad/as/pd/ps
so pure series-internal nodes would otherwise carry NO capacitance at all, which is
both unphysical and a convergence hazard.  One explicit 0.1 fF is added per internal
node, referenced to the nearest supply -- the same value and the same convention the
committed sk.py o21ai bank already uses (CX1 nt<i> bkb 0.1f / CX2 ns<i> g 0.1f).

  g0            reproduce the committed o21ai anchor with sk.py's OWN topology
  g0b           the same point with the PDK subckt (methodology delta)
  fam <name>    one family at the census operating point
  merge         collect rowd/*.json -> CENSUS.json
"""
import json, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skept")
import sk                                                          # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stacks                                                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_sha256")
sk.HERE = HERE
sk.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)
ROWD = os.path.join(HERE, "rowd")
SUB = os.path.join(HERE, "cells", "census_cells.sp")

# the pre-registered best-in-envelope census point
PT = dict(dv=1.65, L=6.0, tot=120.0, tail=500.0, cl=2.0)
# the committed anchor point (dvopt i0_o21_dv150)
ANCHOR = dict(dv=1.5, L=15.0, tot=30.0, tail=500.0, cl=2.0)

# the 12 families of the committed mapped netlist, PLUS buf (AMENDMENT R1: abc will
# not accept a library with no buffer cell, so buf is offered to the mapper and is
# therefore measured here too).
FAMS = ["inv", "nand2", "nor2", "and2", "or2", "nor2b", "xnor2", "xor2",
        "mux2", "a21oi", "a21o", "o21ai", "buf"]
CELL = {f: "sg13g2_%s_1" % f for f in FAMS}
DEPTH = json.load(open(os.path.join(HERE, "cells", "stack_depths.json")))
DEPTH.update(json.load(open(os.path.join(HERE, "cells", "stack_depths_extra.json"))))


# ----------------------------------------------------- local subckt generation
def emit_subckts():
    """VERBATIM PDK device lines + one explicit 0.1 fF per internal node."""
    info = stacks.parse(stacks.PDK, set(CELL.values()))
    out = ["* census cells: device lines VERBATIM from %s" % stacks.PDK,
           "* plus one explicit CINT=0.1f per internal node (see census.py docstring)"]
    for f in FAMS:
        c = CELL[f]
        ports, devs = info[c]["ports"], info[c]["devs"]
        out.append(".subckt %s %s" % (c, " ".join(ports)))
        nodes = set()
        for d in devs:
            nodes |= {d["d"], d["s"]}
            out.append("%s %s %s %s %s %s w=%s l=%s"
                       % (d["name"], d["d"], d["g"], d["s"], d["b"],
                          "sg13_lv_pmos" if d["typ"] == "p" else "sg13_lv_nmos",
                          d["w"], d["l"]))
        internal = sorted(n for n in nodes if n not in ports)
        for k, n in enumerate(internal):
            typs = {d["typ"] for d in devs if n in (d["d"], d["s"])}
            ref = "VDD" if typs == {"p"} else "VSS"
            out.append("CINT%d %s %s 0.1f" % (k, n, ref))
        out.append(".ends")
    os.makedirs(os.path.dirname(SUB), exist_ok=True)
    open(SUB, "w").write("\n".join(out) + "\n")
    return SUB


def vectors(fam):
    """(vec_out_hi, vec_out_lo) worst-case stimuli from the static analysis."""
    r = DEPTH[CELL[fam]]
    hi, lo = r["vec_out_hi"], r["vec_out_lo"]
    if isinstance(hi, str):
        hi, lo = eval(hi), eval(lo)          # json wrote dicts via default=str
    return r["inputs"], hi, lo


# --------------------------------------------------------- the cells() override
_ORIG_CELLS = sk.cells


def cells_pdk(dv, kind="inv", cl=sk.CLOAD):
    """8 real PDK cells on the bank node.  HI indices expect output LOW, LO indices
    expect output HIGH -- the same convention sk.extract_hop's s_of() assumes.

    DEFECT FOUND AND FIXED (AMENDMENT R7): every PDK family is passed to sk as
    "pdk_<fam>", NEVER as the bare name.  sk.hop() branches on `kind == "inv"` to
    build its cell-energy integrators out of the HAND-BUILT bank's per-cell input
    sources (V(in0), I(VI0), ...).  A PDK family literally named "inv" took that
    branch and produced a deck referring to nodes that do not exist:
        Netlist error: Device BXEIH refers to unknown solution node IN0
    It aborted loudly rather than mis-metering, but the prefix removes the collision
    for every family at once.  With "pdk_*" sk.hop takes its else branch, which meters
    the ground-return sources only -- the same treatment the committed o21ai bank
    declared, and appropriate here because this census answers a SETTLING question."""
    if kind in ("inv_handbuilt", "o21ai_handbuilt"):
        return _ORIG_CELLS(dv, kind.replace("_handbuilt", ""), cl)
    fam = kind[4:] if kind.startswith("pdk_") else kind
    c = CELL[fam]
    ports, vhi, vlo = vectors(fam)
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    info = stacks.parse(stacks.PDK, {c})[c]
    plist = info["ports"]                    # [OUT, inputs..., VDD, VSS]
    for i in range(sk.MGATE):
        g = "gnh" if i in sk.HI else "gnl"
        vec = vlo if i in sk.HI else vhi     # HI index -> output must stay LOW
        conn = []
        for p in plist:
            if p == plist[0]:
                conn.append("o%d" % i)
            elif p == "VDD":
                conn.append("bkb")
            elif p == "VSS":
                conn.append(g)
            else:
                nd = "i%s_%d" % (p, i)
                L.append("VI%s_%d %s 0 %g" % (p, i, nd, dv if vec[p] else 0.0))
                conn.append(nd)
        L.append("XC%d %s %s" % (i, " ".join(conn), c))
        L.append("CL%d o%d %s %gf" % (i, i, g, cl))
    return L


def head_with_subckts():
    return sk._head_orig() + ['.include "%s"' % SUB]


sk._head_orig = sk.head
sk.head = head_with_subckts
sk.cells = cells_pdk


# --------------------------------------------------------------------- runner
def run_pt(tag, fam, pt, handbuilt=False):
    dv, Lh, tot, tail, cl = pt["dv"], pt["L"], pt["tot"], pt["tail"], pt["cl"]
    sk.VGH = max(1.5, dv)
    kind = (fam + "_handbuilt") if handbuilt else ("pdk_" + fam)
    t0 = time.monotonic()
    # AMENDMENT R6: the probe timeout is 2400 s, not the committed 900 s.  Under the
    # cold private VAE cache a probe spends most of its wall time in build_vae_so.py,
    # and with three workflows sharing the box a single .so compile was measured at
    # 4-5 minutes.  900 s would have timed out on the BUILD, not on the circuit.
    lp, msg = sk.run("p_%s.cir" % tag, sk.probe(Lh, tot, dv, kind=kind, cl=cl),
                     timeout=2400)
    print(" probe:", msg)
    if lp is None:
        return dict(tag=tag, error=msg)
    tz, ipk, tipk = sk.zero_of(lp + ".prn")
    if tz is None:
        return dict(tag=tag, error="no current zero after the peak")
    print("  true zero %.4f ps (t_hop %.4f), Ipk %.2f uA" % (tz, tz - sk.T0, ipk))
    lines, meta = sk.hop(Lh, tot, dv, tz - sk.T0, tail=tail, kind=kind, cl=cl)
    hp, msg = sk.run("h_%s.cir" % tag, lines, timeout=1800)
    print(" hop:", msg)
    if hp is None:
        return dict(tag=tag, error=msg)
    r = sk.extract_hop(hp + ".prn", meta, Lh, tot, dv)
    r.update(tag=tag, family=fam, cell=CELL.get(fam), handbuilt=handbuilt,
             cl_fF=cl, tail_ps=tail, VGH=sk.VGH, probe_Ipk_uA=ipk,
             wall_s=round(time.monotonic() - t0, 1))
    if not handbuilt:
        d = DEPTH[CELL[fam]]
        ports, vhi, vlo = vectors(fam)
        r["binding_pmos_rise_depth"] = d["binding_pmos_rise_depth"]
        r["vec_out_hi"], r["vec_out_lo"] = vhi, vlo
        # C1 VALUE gate: correct side of half the end rail
        half = 0.5 * r["VBEND"]
        vals = {}
        for i in range(sk.MGATE):
            want_hi = i in sk.LO
            v = r["v_end"]["o%d" % i]
            vals["o%d" % i] = dict(want_hi=want_hi, v_end=v,
                                   correct=bool(v > half if want_hi else v < half))
        r["value_check"] = vals
        r["C1_VALUE"] = all(x["correct"] for x in vals.values())
        r["C2_SETTLE"] = r["t_valid90_ps"] is not None
        r["t_level_meas_ps"] = (max(r["t_hop_ps"], r["t_valid90_ps"])
                                if r["t_valid90_ps"] is not None else None)
    os.makedirs(ROWD, exist_ok=True)
    json.dump(r, open(os.path.join(ROWD, "%s.json" % tag), "w"), indent=1)
    print(" s_end:", {k: round(v, 2) for k, v in r["s_end"].items()})
    print(" v_end:", {k: round(v, 4) for k, v in r["v_end"].items()})
    print(" VBEND %.5f VA_open %+.5f t_valid80 %s t_valid90 %s"
          % (r["VBEND"], r["VA_open"], r["t_valid80_ps"], r["t_valid90_ps"]))
    if not handbuilt:
        print(" C1_VALUE %s  C2_SETTLE %s  t_level %s"
              % (r["C1_VALUE"], r["C2_SETTLE"], r["t_level_meas_ps"]))
    return r


def stage_g0():
    """G0: the committed anchor, sk.py's OWN hand-built o21ai topology."""
    REF = dict(VBEND=0.6076701932224732, t_hop_ps=67.31716163004057,
               VA_open=-0.17394619083354046, t_valid80_ps=515.148911,
               IPK_uA=1435.09869)
    r = run_pt("g0_o21ai_handbuilt_dv150", "o21ai", ANCHOR, handbuilt=True)
    if "error" in r:
        print("FAIL", r["error"]); return False
    ok = True
    for k, ref in REF.items():
        rel = abs(r[k] - ref) / max(abs(ref), 1e-30)
        ok &= rel < 1e-6
        print("%s %-14s mine %.10g committed %.10g (rel %.2e)"
              % ("OK  " if rel < 1e-6 else "FAIL", k, r[k], ref, rel))
    s = min(r["s_end"].values()); rel = abs(s - 82.99) / 82.99
    ok &= rel < 1e-3
    print("%s s_end(min) mine %.4f committed 82.99 (rel %.2e)"
          % ("OK  " if rel < 1e-3 else "FAIL", s, rel))
    print("%s t_valid90 mine %s committed None"
          % ("OK  " if r["t_valid90_ps"] is None else "FAIL", r["t_valid90_ps"]))
    ok &= r["t_valid90_ps"] is None
    print("G0 ANCHOR %s" % ("PASS" if ok else "FAIL"))
    return ok


def merge():
    rows = {}
    if os.path.isdir(ROWD):
        for fn in sorted(os.listdir(ROWD)):
            if fn.endswith(".json"):
                r = json.load(open(os.path.join(ROWD, fn)))
                rows[r["tag"]] = r
    json.dump(rows, open(os.path.join(HERE, "CENSUS.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    emit_subckts()
    c = sys.argv[1]
    if c == "emit":
        print("wrote", SUB)
    elif c == "g0":
        sys.exit(0 if stage_g0() else 1)
    elif c == "g0b":
        run_pt("g0b_o21ai_pdk_dv150", "o21ai", ANCHOR)
    elif c == "fam":
        run_pt("f_%s" % sys.argv[2], sys.argv[2], PT)
    elif c == "merge":
        print("merged %d rows" % len(merge()))
