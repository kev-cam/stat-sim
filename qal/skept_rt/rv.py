#!/usr/bin/env python3
"""TRACK A -- THE RESERVOIR.  Thin wrapper over qal/skept/sk.py (the independently
written deck generator + waveform-only extractor) and qal/dvopt/skept2/s2sk.py
(its per-cell settling extractor).  NOTHING is copied: every number is produced by
the same code path that reproduced the committed rows bit-identically.

WHAT IS NEW: the source-bank capacitance `ca` becomes a swept axis.  It already
exists as a keyword on sk.probe / sk.hop / sk.extract_hop; the committed harnesses
simply never moved it off CA_FF = 35.979 fF (qal_hop_gates.py:79 hard-codes
CA_MULT = 1.0 with the comment "IDENTICAL banks (a real chain)").

ONE PATCH, stated in PRE_REGISTERED.json before the first deck:
  sk.t_pred(L, ca) hard-codes C_ser = ca/2, the EQUAL-BANK series capacitance.
  It is used ONLY to size the run window and the timestep ladder.  It is replaced
  by C_ser = ca*CB/(ca+CB), CB = 35.979 fF, which is ALGEBRAICALLY IDENTICAL at
  ca = CB (so the instrument check is bit-unaffected) and keeps the window sane as
  the tank grows.  The ZCS instant is MEASURED by probe in every single row.

usage: rv.py pt <tag> <L_nH> <W_um> <dV> <CA_MULT> [tail_ps] [kind] [cl_fF]
       rv.py merge
"""
import json, math, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/dvopt/skept2")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skept")
import sk                                                            # noqa: E402
import s2sk                                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_skrt")
sk.HERE = HERE
sk.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
s2sk.HERE = HERE
ROWD = os.path.join(HERE, "rowd")
s2sk.ROWD = ROWD

CB_FF = sk.CA_FF          # 35.979 fF, the MEASURED secant C of one 8-cell bank


def t_pred_series(L, ca=CB_FF):
    """pi*sqrt(L*C_ser) with the TRUE series capacitance of tank ca against the
    one-bank capacitance CB.  Identical to sk's ca/2 form when ca == CB."""
    cser = (ca * CB_FF) / (ca + CB_FF)
    return math.pi * math.sqrt((L * 1e-9) * cser * 1e-15) * 1e12


sk.t_pred = t_pred_series                     # window/timestep sizing only


def add_srccut(lines):
    """Insert the chain3/restore5 AMENDMENT A3 SOURCE-SIDE CUT into an sk.hop /
    sk.probe deck by textual substitution, so the rest of the committed deck is
    untouched.  The inductor's near end moves from the tank node `bka` to a new
    island node `acut`, and an IDENTICAL transmission-gate pair on the SAME phases
    sits between `bka` and `acut`.

    WHY THIS ROW EXISTS.  The committed single-hop deck cuts only the RECEIVING side.
    That is sound when the source is one bank that ends up empty, and every row in
    the (c) sweep uses it -- correctly, because the receiving bank is isolated at ZCS
    and its settling cannot see what the tank does afterwards.  It is NOT sound for a
    SHARED tank: MEASURED here, the committed park then grounds the tank through L
    and R and dumps it (244.8814 fJ out of a 244.8821 fJ tank), and with the park
    removed the island rings for the whole hold window.  A shared tank therefore has
    to carry the cut, the cut is a SECOND transmission gate in the transfer path, and
    this row measures what that costs at the level optimum."""
    out = []
    for ln in lines:
        if ln.startswith("LT bka mid"):
            out.append(ln.replace("LT bka mid", "LT acut mid"))
        elif ln.startswith("XSWN sw gt"):
            w = ln.split("w=")[1].split()[0]
            out.append("XSWSN acut gt bka 0 sg13_lv_nmos w=%s l=0.13u" % w)
            out.append(ln)
        elif ln.startswith("XSWP sw gtp"):
            w = ln.split("w=")[1].split()[0]
            out.append("XSWSP acut gtp bka vhi sg13_lv_pmos w=%s l=0.13u" % w)
            out.append(ln)
        elif ln.startswith(".ic "):
            out.append(ln + " V(acut)=0")
        else:
            out.append(ln)
    return out


def run_pt(tag, L, W, dv, ca_mult, tail=500.0, kind="inv", cl=2.0, srccut=False):
    """s2sk.run_pt VERBATIM in structure, with `ca` threaded through."""
    ca = ca_mult * CB_FF
    sk.VGH = max(1.5, dv)                     # skept2 amendment P1
    t0 = time.monotonic()
    # timeout 2400 s, not sk.run's default 560: on this box a deck shape not yet in
    # the PyMS VAE cache spends 5-10 min COMPILING psp103 before it simulates at all,
    # and the committed 560 s default was measured against an already-warm cache.
    # MEASURED here: the same probe deck timed out at 560 s cold and ran in 31.1 s warm.
    pl = sk.probe(L, W, dv, ca=ca, kind=kind, cl=cl)
    if srccut:
        pl = add_srccut(pl)
    # WINDOW ONLY.  sk.probe ends the probe run at T0 + 4*pi*sqrt(L*C_ser) with C_ser
    # built from the NOMINAL 35.979 fF bank.  The bank's MEASURED chord capacitance
    # rises with the rail it is charged to (50.7 fF at CA_MULT=1 up to 113.7 fF at
    # the ideal-source bound), so at a large tank and a small L that window can end
    # BEFORE the current zero -- MEASURED on SC_m20_L2: the run stopped at 154.0 ps
    # with I(LT) still at +426 uA.  RESV_WIN lengthens the run and NOTHING else: the
    # printed timestep and the max timestep are left exactly as sk.probe set them, so
    # the zero is found at the committed resolution.
    win = float(os.environ.get("RESV_WIN", "1"))
    if win != 1.0:
        pl = [(("%s %s %s 0 %s" % tuple(x.split()[:3] + [x.split()[4]]))
               .replace(x.split()[2], "%gp" % (float(x.split()[2][:-1]) * win), 1)
               if False else x) for x in pl]
        out = []
        for x in pl:
            if x.startswith(".tran "):
                f = x.split()
                te = float(f[2].rstrip("p")) * win
                out.append(".tran %s %gp %s %s" % (f[1], te, f[3], f[4]))
            else:
                out.append(x)
        pl = out
    lp, msg = sk.run("p_%s.cir" % tag, pl, timeout=2400)
    print("  probe:", msg, flush=True)
    if lp is None:
        return dict(tag=tag, error=msg)
    tz, ipk, tipk = sk.zero_of(lp + ".prn")
    if tz is None:
        return dict(tag=tag, error="no current zero after the peak")
    print("  true zero %.4f ps -> t_hop %.4f ps, Ipk %.2f uA"
          % (tz, tz - sk.T0, ipk), flush=True)
    lines, meta = sk.hop(L, W, dv, tz - sk.T0, ca=ca, tail=tail, kind=kind, cl=cl)
    if srccut:
        lines = add_srccut(lines)
    hp, msg = sk.run("h_%s.cir" % tag, lines, timeout=3600)
    print("  hop:", msg, flush=True)
    if hp is None:
        return dict(tag=tag, error=msg)
    r = sk.extract_hop(hp + ".prn", meta, L, W, dv, ca=ca)
    r.update(tag=tag, cell_kind=kind, cl_fF=cl, tail_ps=tail, VGH=sk.VGH,
             ca_mult=ca_mult, srccut=srccut, probe_Ipk_uA=ipk, wall_s=round(time.monotonic() - t0, 1))
    try:
        r.update(s2sk.percell_times(hp + ".prn", r["VBEND"], r["VBPK"]))
    except Exception as e:                                           # noqa
        r["percell_error"] = repr(e)
    w = sk.W(hp + ".prn")
    to = meta["t_open"]
    r["VA_open_printed"] = w.at("V(bka)", to)
    r["VA_open_derived_minus_printed_mV"] = 1000.0 * (r["VA_open"] - r["VA_open_printed"])
    # RESERVOIR-SPECIFIC: the tank is the source bank.  Its droop, and the rail
    # measured AS A FRACTION OF THE TANK, are the reservoir's own figures of merit.
    v_tank0 = dv
    r["V_tank_start"] = v_tank0
    r["V_tank_at_open"] = r["VA_open_printed"]
    r["V_tank_end"] = r["VAEND"]
    r["tank_droop_at_open_mV"] = 1000.0 * (v_tank0 - r["VA_open_printed"])
    r["ratio_VBPK_over_Vtank"] = r["VBPK"] / v_tank0
    r["ratio_VBEND_over_Vtank"] = r["VBEND"] / v_tank0
    r["overshoot_above_tank"] = bool(r["VBPK"] > v_tank0)
    r["over_1p65V_limit"] = bool(r["VBPK"] > 1.65)
    r["loss_factor_r_pk_over_ideal"] = r["VBPK"] / (2.0 * dv * ca_mult / (ca_mult + 1.0))
    r["s_end_min"] = min(r["s_end"].values())
    r["C2_abs"] = "PASS" if r["VA_open"] <= 0.1478 else "FAIL"
    r["C3_abs"] = "PASS" if r["VBEND"] >= 0.60 else "FAIL"
    os.makedirs(ROWD, exist_ok=True)
    json.dump(r, open(os.path.join(ROWD, "%s.json" % tag), "w"), indent=1)
    print("  VBEND %.7f VBPK %.7f t_hop %.7f t_level %.6f | tank %.4f->%.4f "
          "| VBPK/Vtank %.4f | s_end_min %.4f"
          % (r["VBEND"], r["VBPK"], r["t_hop_ps"], r["t_level_ps"],
             v_tank0, r["VA_open_printed"], r["ratio_VBPK_over_Vtank"],
             r["s_end_min"]), flush=True)
    return r


def merge():
    rows = {}
    if os.path.isdir(ROWD):
        for fn in sorted(os.listdir(ROWD)):
            if fn.endswith(".json"):
                r = json.load(open(os.path.join(ROWD, fn)))
                rows[r["tag"]] = r
    json.dump(rows, open(os.path.join(HERE, "rows.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "pt":
        a = sys.argv
        r = run_pt(a[2], float(a[3]), float(a[4]), float(a[5]), float(a[6]),
                   float(a[7]) if len(a) > 7 else 500.0,
                   a[8] if len(a) > 8 else "inv",
                   float(a[9]) if len(a) > 9 else 2.0,
                   (len(a) > 10 and a[10] == "srccut"))
        print("DONE", r.get("tag"), r.get("error", ""))
    elif c == "merge":
        print("merged %d" % len(merge()))
