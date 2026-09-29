#!/usr/bin/env python3
"""STEP 3 of PRE_REGISTERED.json: extract per-gate settling, rails, LOW/HIGH
outputs and topped-rail dV/dt from the EXISTING skiptu ptu decks, plus the
matched rtu (clamp) and free decks, using the COMMITTED settling convention:

    pull-DOWN gate : 100*(1 - V(o)/rail_j)
    pull-UP   gate : 100*(V(o)/rail_j)

rail_j read at the SAME boundary instant, per gate, NEVER aggregated.

Nothing here runs a simulation.  It reads skiptu's .mt0 and .prn only.
Every ptu number produced here is labelled PRE-CNA / A6-DISQUALIFIED.
"""
import json, os, re, sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

SKIPTU = "/usr/local/src/stat-sim/qal/skiptu"
HERE = os.path.dirname(os.path.abspath(__file__))

# COMMITTED convention, imported not reinvented: SK.is_hi(k, i) is True for a
# pull-DOWN cell (logic-HIGH input).  The 0.02 V rail guard is tuextract.py's own.
def stage_from_mt0(m, stage, nbank):
    """per-gate settling of one stage at its OWN boundary, from the .mt0.
    O{stage}_{i}S is the output AT that stage's boundary; VR{k}K{k} is that
    stage's rail at the same instant (the deck writes both at the same AT=)."""
    vr = m.get("VR%dK%d" % (stage, stage))
    if vr is None:
        return None
    out = {"rail_at_bound_V": round(vr, 6), "per_gate": {}}
    for i in range(SK.MGATE):
        vo = m.get("O%d_%dS" % (stage, i))
        if vo is None or not vr or vr <= 0.02:
            continue
        f = (1.0 - vo / vr) if SK.is_hi(stage, i) else (vo / vr)
        out["per_gate"][str(i)] = {
            "v_o": round(vo, 6),
            "kind": "pulldown" if SK.is_hi(stage, i) else "pullup",
            "settle_pct": round(100.0 * f, 2)}
    if not out["per_gate"]:
        return None
    pg = out["per_gate"]
    out["worst_pct"] = round(min(g["settle_pct"] for g in pg.values()), 2)
    lows = [g["v_o"] for g in pg.values() if g["kind"] == "pulldown"]
    highs = [g["v_o"] for g in pg.values() if g["kind"] == "pullup"]
    out["max_LOW_V"] = round(max(lows), 6) if lows else None
    out["min_HIGH_V"] = round(min(highs), 6) if highs else None
    out["separation_mV"] = (round(1e3 * (min(highs) - max(lows)), 4)
                            if (lows and highs) else None)
    return out


def delivered_from_mt0(m, stage):
    """THE THRESHOLD TEST input side, committed form: G{k}_{i} is the
    PREDECESSOR's output read at stage k's boundary."""
    his = [m["G%d_%d" % (stage, i)] for i in range(SK.MGATE)
           if SK.is_hi(stage, i) and ("G%d_%d" % (stage, i)) in m]
    los = [m["G%d_%d" % (stage, i)] for i in range(SK.MGATE)
           if not SK.is_hi(stage, i) and ("G%d_%d" % (stage, i)) in m]
    if not his:
        return None
    return {"min_high_V": round(min(his), 6),
            "max_low_V": round(max(los), 6) if los else None,
            "margin_mV": round(1e3 * (min(his) - 0.4400), 2),
            "clears_0p4400": bool(min(his) >= 0.4400)}


# ---------------------------------------------------------------- dV/dt (D1)
def rail_slope(prn_path, node, t0, t1):
    """max |dV/dt| of `node` over [t0, t1] ps, in V/ns, by centred difference on
    the printed grid.  Also returns the rail's excursion over the window."""
    hdr, rows = SK.read_prn(prn_path)
    want = "V(%s)" % node
    col = None
    for c in hdr:
        if c.lower() == want.lower():
            col = hdr.index(c)
            break
    if col is None:
        return None
    ti = 0
    seg = [(r[ti], r[col]) for r in rows if t0 <= r[ti] <= t1]
    if len(seg) < 3:
        return None
    best, bt, vmin, vmax = 0.0, None, seg[0][1], seg[0][1]
    for j in range(1, len(seg) - 1):
        dt = seg[j + 1][0] - seg[j - 1][0]          # ps
        if dt <= 0:
            continue
        dv = seg[j + 1][1] - seg[j - 1][1]
        s = abs(dv / dt) * 1e3                       # V/ps -> V/ns
        if s > best:
            best, bt = s, seg[j][0]
        vmin = min(vmin, seg[j][1]); vmax = max(vmax, seg[j][1])
    return {"max_abs_dVdt_V_per_ns": round(best, 4), "at_ps": bt,
            "window_ps": [t0, t1], "V_min": round(vmin, 6),
            "V_max": round(vmax, 6), "n_samples": len(seg)}


def main():
    out = {"_what": "per-gate settling + rails + LOW/HIGH + topped-rail dV/dt "
                    "extracted from the EXISTING skiptu decks. NO simulation run.",
           "_convention": "pull-DOWN 100*(1-V/rail_j); pull-UP 100*(V/rail_j); "
                          "rail_j at the same boundary instant; per gate; never aggregated.",
           "_label_ptu": "PRE-CNA / A6-DISQUALIFIED: none of these ptu decks carries a "
                         "switch-node capacitance on na_k, and AMENDMENT A6 rules that any "
                         "buck number taken without it is an artefact of the shim.",
           "decks": {}}

    decks = sorted(f for f in os.listdir(SKIPTU)
                   if f.endswith(".cir") and (("_ptu" in f) or ("_rtu" in f)
                                              or ("_free" in f)))
    for d in decks:
        mt0 = os.path.join(SKIPTU, d + ".mt0")
        prn = os.path.join(SKIPTU, d + ".prn")
        rec = {"has_mt0": os.path.exists(mt0), "has_prn": os.path.exists(prn)}
        if "_ptu" in d:
            rec["mode"] = "ptu"
            rec["role"] = ("PROBE-instrument" if d.startswith(("q3_", "q4_"))
                           else "row-deck")
            rec["label"] = "PRE-CNA / A6-DISQUALIFIED"
        elif "_rtu" in d:
            rec["mode"] = "rtu"; rec["role"] = "row-deck"
            rec["label"] = "ideal-source booking (committed)"
        else:
            rec["mode"] = "free"; rec["role"] = "row-deck"
            rec["label"] = "control"
        nb = 5 if "_s5" in d or d.startswith("p1_s5") else 4
        if rec["has_mt0"]:
            m = SK.parse_mt0(mt0)
            rec["n_mt0_keys"] = len(m)
            st = {}
            for s in range(1, nb + 1):
                r = stage_from_mt0(m, s, nb)
                if r:
                    st[str(s)] = r
            if st:
                rec["settling"] = st
                rec["worst_by_stage_pct"] = {k: v["worst_pct"]
                                             for k, v in sorted(st.items())}
                rec["separation_mV_by_stage"] = {k: v["separation_mV"]
                                                 for k, v in sorted(st.items())}
                rec["max_LOW_V_by_stage"] = {k: v["max_LOW_V"]
                                             for k, v in sorted(st.items())}
                rec["rail_at_bound_V_by_stage"] = {k: v["rail_at_bound_V"]
                                                   for k, v in sorted(st.items())}
            dl = {}
            for s in range(2, nb + 1):
                r = delivered_from_mt0(m, s)
                if r:
                    dl[str(s)] = r
            if dl:
                rec["delivered_input"] = dl
                rec["A2_min_delivered_high_V"] = min(v["min_high_V"]
                                                     for v in dl.values())
                rec["A2_all_stages_clear"] = all(v["clears_0p4400"]
                                                 for v in dl.values())
            for k in ("QTU3_D", "QTU4_D", "QIND3_D", "QIND4_D", "QSUP_D",
                      "ITU3PK", "ITU4PK", "IZ1", "IZ2", "QGABS_D", "EGTU_D"):
                if k in m:
                    rec.setdefault("topup_meters", {})[k] = m[k]
        out["decks"][d] = rec

    json.dump(out, open(os.path.join(HERE, "EXISTING.json"), "w"), indent=1)
    print("wrote EXISTING.json:", len(out["decks"]), "decks")
    for d, r in sorted(out["decks"].items()):
        if "worst_by_stage_pct" in r:
            print("  %-46s %-4s %-16s %s" % (d[:46], r["mode"], r["role"][:16],
                                             r["worst_by_stage_pct"]))


if __name__ == "__main__":
    main()
