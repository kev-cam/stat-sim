#!/usr/bin/env python3
"""What beat period does the block ACTUALLY need?

Read off ONE deck instead of bisected with one 600 s run per candidate T: every one
of the 161 gates is measured at a ladder of offsets after its OWN bank's rail start,
against its OWN bank's instantaneous rail, using the committed banktank guard
(expected-LOW <= 0.10*rail, expected-HIGH >= 0.50*rail) and the committed 90 %
settling convention.  t_valid(k) is the first offset at which EVERY gate of bank k
is on the correct side and stays there; the beat period the block needs is the
maximum over banks.
"""
import json, os, sys
import bt, blk

HERE, N = blk.HERE, blk.N


def main(tag, scan):
    mt = bt.parse_mt0(os.path.join(HERE, "b_%s.cir.mt0" % tag))
    D = N["D"]
    out, det = {}, {}
    for k in range(1, D + 1):
        rows, ok_from, ok90_from = [], None, None
        for si, off in enumerate(scan):
            key = "VR%dS%d" % (k, si)
            if key not in mt:
                continue
            rail = mt[key]
            worst_s, nbad, badcell = 1e9, 0, None
            for j, cn in enumerate(N["banks"][k]):
                v = mt.get("S%d_%d_%d" % (k, j, si))
                if v is None:
                    continue
                hi = bool(N["val"][N["cells"][cn]["out"]])
                s = (v / rail) if hi else (1.0 - v / rail)
                good = (v >= 0.50 * rail) if hi else (v <= 0.10 * rail)
                if not good:
                    nbad += 1
                if s < worst_s:
                    worst_s, badcell = s, cn
            rows.append(dict(off_ps=off, rail_V=round(rail, 5),
                             worst_settle_pct=round(100.0 * worst_s, 2),
                             worst_cell=badcell,
                             worst_typ=N["cells"][badcell]["typ"].replace("sg13g2_", ""),
                             n_guard_fail=nbad))
            if nbad == 0 and ok_from is None:
                ok_from = off
            elif nbad:
                ok_from = None
            if worst_s >= 0.90 and ok90_from is None:
                ok90_from = off
            elif worst_s < 0.90:
                ok90_from = None
        det[k] = rows
        out[k] = dict(n_cells=len(N["banks"][k]), H_k=N["H"][k],
                      t_value_valid_ps=ok_from, t_settle90_ps=ok90_from,
                      max_offset_probed_ps=(rows[-1]["off_ps"] if rows else None),
                      worst_at_max_offset_pct=(rows[-1]["worst_settle_pct"]
                                               if rows else None),
                      guard_fails_at_max_offset=(rows[-1]["n_guard_fail"]
                                                 if rows else None))
    have = [out[k]["t_value_valid_ps"] for k in out]
    unmet = [k for k in out if out[k]["t_value_valid_ps"] is None]
    res = dict(tag=tag, scan_ps=scan, per_bank=out, detail=det,
               banks_never_valid_inside_probe=unmet,
               T_required_ps=(max(v for v in have if v) if not unmet else None),
               NOTE=("the block needs a beat period of at least max_k t_value_valid; "
                     "banks listed in banks_never_valid_inside_probe did not reach "
                     "the guard anywhere in the probed ladder, which is capped by "
                     "that bank's own hold r_k"))
    json.dump(res, open(os.path.join(HERE, "SCAN_%s.json" % tag), "w"), indent=1)
    print("bank  n    H_k   t_value_valid   t_settle90   worst@max_off   fails@max_off")
    for k in range(1, D + 1):
        o = out[k]
        print("  %2d  %3d   %3d   %13s   %10s   %11s   %s"
              % (k, o["n_cells"], o["H_k"],
                 ("%.0f ps" % o["t_value_valid_ps"]) if o["t_value_valid_ps"] else "NEVER",
                 ("%.0f ps" % o["t_settle90_ps"]) if o["t_settle90_ps"] else "NEVER",
                 ("%.1f%%" % o["worst_at_max_offset_pct"])
                 if o["worst_at_max_offset_pct"] is not None else "-",
                 o["guard_fails_at_max_offset"]))
    print("\nT_required =", res["T_required_ps"], " never-valid banks:", unmet)
    return res


if __name__ == "__main__":
    tag = sys.argv[1]
    scan = [float(x) for x in sys.argv[2].split(",")]
    main(tag, scan)
