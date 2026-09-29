#!/usr/bin/env python3
"""Driver: for each (k, T) -> probe the segment's hop zeros, MEASURE the restoring
stage's latency on the one-segment deck, then run and extract the full 6-bank row.

Parallelism is ACROSS (k, T) combos; within a combo the runs are sequential (hop
zeros must be found in order).  MAXPAR 4 (sim discipline: ~4 concurrent heavy jobs
on this 16-core box, shared with other workflows).
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

import rest, extract

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, os.environ.get("ROWS_FILE", "rows.json"))
MAXPAR = int(os.environ.get("MAXPAR", "4"))
FALLBACK_TRES = 300.0   # ps, generous inter-segment gap used ONLY when the
                        # restoring stage does not resolve at all (see one())


def one(combo):
    k, T = combo
    tag = "k%d_T%g" % (k, T)
    t0 = time.monotonic()
    try:
        # 1. hop zeros on the ONE-SEGMENT deck (AMENDMENT A2)
        tz = rest.do_probe(k, T, 0.0)
        if tz is None:
            return tag, dict(error="probe failed")
        # 2. the one-segment MEASURED deck -> the restoring stage's own latency.
        #    tres does not enter a one-segment schedule (there is no inter-segment
        #    gap), so it is run at tres=0 and tres comes OUT of it, measured.
        got = rest.do_seg(k, T, 0.0, tz)
        if got is None:
            return tag, dict(error="seg deck failed", tz_ps=tz)
        spath, Sseg = got
        tr = extract.tres_measure(spath, Sseg, k)
        pair = [v["latency_ps"] for kk, v in tr.items()
                if kk.endswith("_pair") and v.get("latency_ps") is not None]
        inv1 = [v["latency_ps"] for kk, v in tr.items()
                if kk.endswith("_inv1") and v.get("latency_ps") is not None]
        note = None
        if not pair:
            # The restoring stage did not resolve at all, so it has no latency to
            # measure.  Do NOT skip the full-chain row: it is a pre-registered
            # deliverable (per-gate per-bank settling at every k) and the reason the
            # restore failed is a LEVEL, not a timing, failure -- so the schedule is
            # given a generous fallback gap and the row is marked VOID for
            # acceptance by the A5 check rather than being absent.
            tres = FALLBACK_TRES
            note = ("restore latency NOT MEASURABLE -- the restoring stage never "
                    "resolved (the QAL level at the end of this segment is below "
                    "its trip point). The schedule uses a generous %g ps fallback "
                    "gap so the full-chain row still exists; the row is VOID for "
                    "acceptance." % FALLBACK_TRES)
        else:
            tres = max(pair)
        # schedule with a CEILING of the measured latency so the next segment's
        # data is certainly valid when its hop closes; the row then verifies it.
        tres_sched = float(int(tres + 5.0))
        # 3. the full 6-bank chain row
        got = rest.do_row(k, T, tres_sched, tz)
        if got is None:
            return tag, dict(error="row failed", tz_ps=tz, tres_ps=tres_sched)
        path, S = got
        r = extract.row_extract(k, T, tres_sched, tz, path)
        r["tres_measured_ps"] = dict(
            pair_max=(max(pair) if pair else None), pair_all=sorted(pair),
            inv1_max=(max(inv1) if inv1 else None), inv1_all=sorted(inv1),
            scheduled_ps=tres_sched, restore_resolved=bool(pair),
            note=note, raw=tr)
        rr = extract.tres_measure(path, S, rest.NBANK)
        r["tres_in_full_chain_ps"] = rr
        r["wall_s"] = round(time.monotonic() - t0, 1)
        return tag, r
    except Exception as e:                                          # noqa
        import traceback
        return tag, dict(error=repr(e), tb=traceback.format_exc()[-2000:])


def main():
    combos = []
    for a in sys.argv[1:]:
        k, T = a.split(",")
        combos.append((int(k), float(T)))
    rows = json.load(open(ROWS)) if os.path.exists(ROWS) else {}
    with ThreadPoolExecutor(max_workers=MAXPAR) as ex:
        for tag, r in ex.map(one, combos):
            rows[tag] = r
            if "error" in r:
                print("%-14s ERROR %s" % (tag, r["error"]), flush=True)
            else:
                tm = r["tres_measured_ps"]["pair_max"]
                print("%-14s worst %6.2f%% (bank %d, pos %d)  PASS=%s  VOID=%s  "
                      "tres %s  %.0fs"
                      % (tag, r["worst_gate_pct_all_banks"], r["worst_gate_bank"],
                         r["pos_in_segment"][r["worst_gate_bank"]], r["PASS"],
                         r.get("VOID_for_acceptance"),
                         ("%.1f" % tm) if tm is not None else "NOT-MEASURABLE",
                         r["wall_s"]), flush=True)
            json.dump(rows, open(ROWS, "w"), indent=1)
    print("rows.json now holds %d rows" % len(rows))


if __name__ == "__main__":
    main()
