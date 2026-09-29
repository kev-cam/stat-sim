#!/usr/bin/env python3
"""(e) DROOP OVER THE EPHEMERAL WINDOW, against the MEASURED receiver threshold.

Reads the hop waveforms already on disk (no new decks).  The hold portion of the
beat is the interval AFTER the transfer switch freezes: from t_open onward the
tank is disconnected, the rail is floating on the bank's own capacitance, and
nothing is holding the outputs except -- for the stripped cell -- the
cross-coupled pair, and -- for the ephemeral premise -- nothing at all.

Reported per node, never aggregated:
  * absolute droop of each node from t_open
  * the RAIL's own droop over the same window (a HIGH is referenced to the rail,
    so this is part of the budget, not a separate effect -- the chain3/skip4
    complementarity result)
  * the node's voltage relative to the INSTANTANEOUS rail
  * margin against this study's own measured receiver trip and the width of its
    transition window
"""
import json, os, sys
import common as C

HERE = C.HERE
ROWD = os.path.join(HERE, "rowd")
WIN = [0.0, 50.0, 100.0, 150.0, 200.0, 300.0, 400.0, 495.0]


def do(tag, trip=None, window_mV=None):
    rp = os.path.join(ROWD, tag + ".json")
    hp = os.path.join(HERE, "h_%s.cir.prn" % tag)
    if not (os.path.exists(rp) and os.path.exists(hp)):
        return None
    r = json.load(open(rp))
    w = C.W(hp)
    to = r["t_open_ps"]
    out = dict(tag=tag, mode=r["mode"], fam=r["fam"], dv=r["dv"],
               t_open_ps=to, VBOPEN=r["VBOPEN"], VBEND=r["VBEND"],
               trip_V=trip, window_mV=window_mV, rail={}, nodes={})
    r0 = w.at("V(bkb)", to)
    for dt in WIN:
        v = w.at("V(bkb)", to + dt)
        out["rail"]["t+%gps" % dt] = dict(V=v, droop_mV=(r0 - v) * 1e3)
    for n, nd in r["per_node"].items():
        # THE HOLD WINDOW STARTS WHEN THE NODE IS ESTABLISHED, NOT AT THE FREEZE.
        # An earlier version measured from t_open and reported "droops" of up to
        # 472 mV -- which were nodes still RISING, not falling.  The hold window
        # here starts at the node's own extremum after the freeze (its peak for
        # an expected-HIGH node, its trough for an expected-LOW one): the first
        # instant at which there is a value to hold.  A node that is still moving
        # toward its value at the end of the run has no hold window and is
        # reported as such rather than given a number.
        yv = w.v("V(%s)" % n)
        idx = [k for k in range(len(w.t)) if w.t[k] >= to]
        pick = max if nd["expect_hi"] else min
        kref = pick(idx, key=lambda k: yv[k])
        tref, v0 = w.t[kref], yv[kref]
        still_moving = bool(kref >= idx[-1] - 2)
        e = dict(expect_hi=nd["expect_hi"], cell=nd["cell"],
                 V_at_open=w.at("V(%s)" % n, to),
                 t_hold_start_ps=tref, V_at_hold_start=v0,
                 still_moving_at_end=still_moving, pts={})
        for dt in WIN:
            v = w.at("V(%s)" % n, tref + dt)
            rr = w.at("V(bkb)", tref + dt)
            e["pts"]["t+%gps" % dt] = dict(
                V=v, droop_from_open_mV=(v0 - v) * 1e3,
                frac_of_rail=v / rr if rr else None,
                margin_to_trip_mV=(None if trip is None else
                                   ((v - trip * rr / (trip / trip if trip else 1))
                                    if False else (v - trip) * 1e3)))
        # the decisive numbers for the hold: droop measured from the moment the
        # node is first settled (t_open) to one beat later, and to the end
        e["droop_over_beat_mV"] = e["pts"]["t+200ps"]["droop_from_open_mV"]
        e["hold_window_available_ps"] = max(0.0, (r["tend_ps"] - 5.0) - tref)
        e["droop_over_150ps_mV"] = e["pts"]["t+150ps"]["droop_from_open_mV"]
        e["droop_over_300ps_mV"] = e["pts"]["t+300ps"]["droop_from_open_mV"]
        e["droop_to_end_mV"] = e["pts"]["t+495ps"]["droop_from_open_mV"]
        if window_mV is not None:
            e["A5_inside_window_at_200ps"] = bool(
                abs(e["droop_over_beat_mV"]) < window_mV)
            e["A5_inside_window_at_end"] = bool(
                abs(e["droop_to_end_mV"]) < window_mV)
        out["nodes"][n] = e
    hi = [v for v in out["nodes"].values() if v["expect_hi"]]
    lo = [v for v in out["nodes"].values() if not v["expect_hi"]]
    out["worst_hi_droop_over_beat_mV"] = (max(abs(v["droop_over_beat_mV"])
                                              for v in hi) if hi else None)
    out["worst_lo_droop_over_beat_mV"] = (max(abs(v["droop_over_beat_mV"])
                                              for v in lo) if lo else None)
    out["rail_droop_over_beat_mV"] = out["rail"]["t+200ps"]["droop_mV"]
    return out


def main():
    trip = wnd = None
    rf = os.path.join(HERE, "RECEIVER.json")
    if os.path.exists(rf):
        rr = json.load(open(rf))
        # Prefer a receiver row whose 90%-10% window is actually WELL-POSED.
        # At rails <= 0.56 V the static inverter's own pull-up sits at or below
        # |Vtp| = 0.4403 V, so its DC transfer curve never traverses the rail and
        # the window is undefined (reported as None) -- that is itself a finding,
        # but it cannot serve as the A5 threshold.  The QAL-rail row
        # static @ 0.6077 V is the one that is well-posed.
        cands = [rr.get("static", {}).get("0.6077"),
                 rr.get("strip", {}).get("0.6077"),
                 rr.get("static", {}).get("1.0000")]
        for s in cands:
            if s and s.get("window_mV"):
                trip, wnd = s.get("trip_V"), s.get("window_mV")
                break
    tags = sys.argv[1:] or [f[:-5] for f in sorted(os.listdir(ROWD))
                            if f.endswith(".json")]
    out = {"_trip_V_used": trip, "_window_mV_used": wnd, "rows": {}}
    for t in tags:
        d = do(t, trip, wnd)
        if d:
            out["rows"][t] = d
            print("%-34s rail droop/beat %7.2f mV  worst HI %7.2f  worst LO %7.2f"
                  % (t, d["rail_droop_over_beat_mV"],
                     d["worst_hi_droop_over_beat_mV"] or 0,
                     d["worst_lo_droop_over_beat_mV"] or 0))
    json.dump(out, open(os.path.join(HERE, "DROOP.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
