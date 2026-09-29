#!/usr/bin/env python3
"""MEASUREMENT 4, from the WAVEFORM: are the hop and the settle actually CONCURRENT?

The claim being tested is that a level costs max(t_hop, t_settle) rather than their
sum, i.e. that while hop h is moving charge into bank h+2, the stage that FEEDS bank
h+2 is settling at the same time.  This reads both intervals out of the .prn and
reports whether they overlap, with the overlap fraction.  Nothing is assembled from
parts -- both intervals come from the same trace.
"""
import json, os, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skiptu")
import skip as SK
import tu

HERE = tu.HERE
I_THRESH = 5e-6          # A: the hop is "running" while |I(L)| exceeds 5 uA


def hop_interval(hdr, rows, col, t_close, t_open):
    """The interval over which the hop actually carries current, from the trace."""
    ic = hdr.index(col)
    ts = [r[1] * 1e12 for r in rows if abs(r[ic]) > I_THRESH
          and t_close - 5 <= r[1] * 1e12 <= t_open + 5]
    return (min(ts), max(ts)) if ts else None


def settle_interval(hdr, rows, bank, rail_col, t_start, bound):
    """The interval over which the bank's SLOWEST gate goes from 10% to 90% of its
    rail-referenced ideal, searched from t_start (its charging hop's close) to its
    stage boundary.

    TWO CASES MUST BE REPORTED HONESTLY, and both occur here:

    * the chain's data pattern is STATIC (bank 1's inputs are DC sources), so a HEAD
      bank's outputs are already at their DC solution at t = 0 and there is NO settling
      transition to measure at all.  What this harness measures is the response to the
      RAIL moving, not to a data edge.  Returns kind='no_transition'.
    * a stage that NEVER reaches 90% has no 10-90 interval.  Clamping its t90 to the
      stage boundary would invent one and would make a non-settling stage look like a
      slow-but-settling stage.  Returns kind='never_reaches_90' with the peak fraction
      actually attained.
    """
    best = None
    for i in range(SK.MGATE):
        c = "V(O%d_%d)" % (bank, i)
        if c not in hdr:
            continue
        io, ir = hdr.index(c), hdr.index(rail_col)
        hi = SK.is_hi(bank, i)
        t10 = t90 = None
        fmax = -9e9
        for r in rows:
            t = r[1] * 1e12
            if t < t_start or t > bound:
                continue
            vr = r[ir]
            if vr <= 0.02:
                continue
            f = (1.0 - r[io] / vr) if hi else (r[io] / vr)
            fmax = max(fmax, f)
            if t10 is None and f >= 0.10:
                t10 = t
            if t10 is not None and t90 is None and f >= 0.90:
                t90 = t
        cand = dict(gate=i, t10=t10, t90=t90, fmax=round(fmax, 4))
        if t90 is not None:
            cand["kind"] = "settled"; cand["span"] = t90 - t10
        elif t10 is not None:
            cand["kind"] = "never_reaches_90"; cand["span"] = None
        else:
            cand["kind"] = "never_reaches_10"; cand["span"] = None
        # the SLOWEST gate is the one that matters; a never-settling gate outranks a
        # settling one, and among settling gates the widest span wins.
        rank = (0 if cand["kind"] == "settled" else 1,
                cand["span"] if cand["span"] is not None else 0)
        if best is None or rank > best[0]:
            best = (rank, cand)
    return best[1] if best else None


def main():
    rows_j = json.load(open(os.path.join(HERE, "rows.json")))
    OK = [r for r in rows_j if "ERROR" not in r]
    out = {"_doc": __doc__.strip(), "_I_threshold_uA": I_THRESH * 1e6, "rows": {}}
    # do the evidence on the best row of each mode, per dv, to keep it readable
    pick = {}
    for r in OK:
        k = (r["scheme"], r["mode"], r["dv"])
        if k not in pick or (r["worst_gate_all_stages_pct"] or -1) > \
                (pick[k]["worst_gate_all_stages_pct"] or -1):
            pick[k] = r
    for k, r in sorted(pick.items(), key=lambda kv: str(kv[0])):
        prn = os.path.join(HERE, r["deck"] + ".prn")
        if not os.path.exists(prn):
            continue
        hdr, rws = SK.read_prn(prn)
        T = r["T_ps"]
        ev = []
        for h in r["hops_detail"]:
            hi = hop_interval(hdr, rws, "I(L%d)" % h["hop"],
                              h["t_close_ps"], h["t_open_ps"])
            feeder = h["dst"] - 1
            bd = r["bound_ps"].get(str(feeder), r["bound_ps"].get(feeder))
            # the feeder's own settling starts when ITS rail is charged: its charging
            # hop's close if it has one, else it is a head bank with static DC data
            fc = None
            for hh in r["hops_detail"]:
                if hh["dst"] == feeder:
                    fc = hh["t_close_ps"]
            if fc is None:
                ev.append(dict(hop=h["hop"], src=h["src"], dst=h["dst"],
                               hop_current_interval_ps=[round(hi[0], 2), round(hi[1], 2)]
                               if hi else None,
                               hop_duration_ps=round(hi[1] - hi[0], 2) if hi else None,
                               feeder_stage=feeder,
                               feeder_is_a_HEAD_bank=True,
                               CONCURRENT=None,
                               note=("feeder is a HEAD bank: its rail is up from t=0 and "
                                     "the data pattern is STATIC, so its outputs are at "
                                     "their DC solution from t=0 and there is no settling "
                                     "transition to overlap with. Not an overlap failure -- "
                                     "the quantity does not exist for this stage.")))
                continue
            si = settle_interval(hdr, rws, feeder, "V(RAIL%d)" % feeder, fc, bd)
            rec = dict(hop=h["hop"], src=h["src"], dst=h["dst"],
                       hop_current_interval_ps=[round(hi[0], 2), round(hi[1], 2)]
                       if hi else None,
                       hop_duration_ps=round(hi[1] - hi[0], 2) if hi else None,
                       feeder_stage=feeder, feeder_is_a_HEAD_bank=False,
                       feeder_settle_search_from_ps=round(fc, 2),
                       feeder_boundary_ps=round(bd, 2),
                       feeder_settle=si)
            if hi and si and si["kind"] == "settled":
                lo, hh2 = max(hi[0], si["t10"]), min(hi[1], si["t90"])
                ov = max(0.0, hh2 - lo)
                rec.update(overlap_ps=round(ov, 2),
                           overlap_frac_of_hop=round(ov / max(hi[1] - hi[0], 1e-9), 3),
                           CONCURRENT=bool(ov > 0),
                           level_if_concurrent_ps=round(
                               max(hi[1] - hi[0], si["t90"] - si["t10"]), 2),
                           level_if_serial_ps=round(
                               (hi[1] - hi[0]) + (si["t90"] - si["t10"]), 2))
            else:
                rec.update(CONCURRENT=None,
                           note=("the feeder stage %s, so there is no 10-90 settle "
                                 "interval to place against the hop. max fraction "
                                 "attained = %s" % (si["kind"] if si else "has no trace",
                                                    si["fmax"] if si else None)))
            ev.append(rec)
        out["rows"][r["tag"]] = dict(scheme=r["scheme"], mode=r["mode"], dv=r["dv"],
                                     T_ps=T, evidence=ev)
    json.dump(out, open(os.path.join(HERE, "OVERLAP.json"), "w"), indent=1, default=str)
    for t, v in out["rows"].items():
        print("%s  T=%g" % (t, v["T_ps"]))
        for e in v["evidence"]:
            if e.get("feeder_is_a_HEAD_bank"):
                print("   hop%d -> bank%d : feeder stage %d is a HEAD (static DC data,"
                      " no settle transition)" % (e["hop"], e["dst"], e["feeder_stage"]))
            elif e.get("CONCURRENT") is None:
                print("   hop%d %s : feeder stage %d %s (max %.3f)"
                      % (e["hop"], e["hop_current_interval_ps"], e["feeder_stage"],
                         (e.get("feeder_settle") or {}).get("kind"),
                         (e.get("feeder_settle") or {}).get("fmax") or -1))
            else:
                fs = e["feeder_settle"]
                print("   hop%d %s  feeder %d settle [%.1f, %.1f]  overlap %.1f ps"
                      " (%.0f%% of hop) -> level %s vs serial %s"
                      % (e["hop"], e["hop_current_interval_ps"], e["feeder_stage"],
                         fs["t10"], fs["t90"], e["overlap_ps"],
                         100 * e["overlap_frac_of_hop"], e["level_if_concurrent_ps"],
                         e["level_if_serial_ps"]))
    print("\nwrote OVERLAP.json")


if __name__ == "__main__":
    main()
