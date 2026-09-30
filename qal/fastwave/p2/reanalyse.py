"""p2 RE-ANALYSIS -- AMENDMENT P11.

The commit instant used up to here is Phase 1's: "correct AND STAYS correct
through the stage boundary".  That is the right rule for a SKEWED deck, where the
boundary is one beat after the bank's own rail start.  It is the WRONG rule for the
SYNCHRONOUS deck, where the boundary is a single late instant common to all seven
banks -- by which time the isolated rails have decayed 40-55% from their peaks, so
a bank whose value was correct for hundreds of picoseconds and then decayed reads
`commit = NEVER` and is indistinguishable from a bank that never computed at all.

This pass re-reads the SAVED waveforms -- no new simulation -- and reports, per
bank, EVERY contiguous interval in which all four outputs are on the correct side
of the receiver's measured trip at that bank's own instantaneous rail by the 3-sigma
budget.  It answers two different questions separately:

    WHEN did the value arrive          -> the first correct interval's start
    HOW LONG did it hold               -> that interval's length

A bank that produces the right answer for 300 ps and then loses it has computed;
whether that is USABLE depends on whether the window is at least one beat wide,
which is now a measured number rather than a pass/fail artefact of where the
checkpoint happened to sit.  BOTH readings are carried on every row.
"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W

HERE = W.HERE
WS, PS = W.logic()


def intervals(prn, nbank, c, bound, dv):
    """Per bank: the contiguous intervals where ALL cells are correct."""
    hdr, rows = W.read_prn(prn)
    ir = {k: hdr.index("V(RAIL%d)" % k) for k in range(1, nbank + 1)}
    iy = {(k, i): hdr.index("V(Y%d_%d)" % (k, i))
          for k in range(1, nbank + 1) for i in range(W.NCELL)}
    T = [r[1] * 1e12 for r in rows]
    out = {}
    for k in range(1, nbank + 1):
        want = WS[k - 1]
        runs, cur = [], None
        best_marg = -1e9
        for n, t in enumerate(T):
            if t < c[k] or t > bound[k]:
                continue
            vb = rows[n][ir[k]]
            if vb <= 0.2:
                ok = False
            else:
                tv = W.trip_at(vb)
                ms = [(rows[n][iy[(k, i)]] - tv) if want[i]
                      else (tv - rows[n][iy[(k, i)]]) for i in range(W.NCELL)]
                mm = min(ms)
                ok = mm > W.NB_V
                if ok:
                    best_marg = max(best_marg, mm * 1000.0)
            if ok:
                cur = [t, t] if cur is None else [cur[0], t]
            elif cur is not None:
                runs.append(tuple(cur)); cur = None
        if cur is not None:
            runs.append(tuple(cur))
        runs = [r for r in runs if r[1] - r[0] >= 0.0]
        o = dict(n_intervals=len(runs),
                 intervals_ps=[[round(a, 2), round(b, 2)] for a, b in runs],
                 best_margin_inside_interval_mV=(best_marg if runs else None))
        if runs:
            first = runs[0]
            longest = max(runs, key=lambda r: r[1] - r[0])
            o.update(first_arrival_abs_ps=first[0],
                     first_arrival_after_own_rail_ps=first[0] - c[k],
                     first_hold_ps=first[1] - first[0],
                     longest_start_abs_ps=longest[0],
                     longest_hold_ps=longest[1] - longest[0],
                     ever_correct=True)
        else:
            o.update(ever_correct=False, first_arrival_abs_ps=None,
                     first_hold_ps=None, longest_hold_ps=None)
        out[k] = o
    return out


def rebuild(rowfile, out_name):
    rows = json.load(open(os.path.join(HERE, rowfile)))
    res = {}
    for tag, r in sorted(rows.items()):
        if r.get("FAILED"):
            res[tag] = dict(FAILED=r["FAILED"])
            continue
        deck = r.get("deck")
        prn = os.path.join(HERE, deck + ".prn")
        if not os.path.exists(prn):
            res[tag] = dict(FAILED="waveform gone: " + str(deck))
            continue
        nb = r["nbank"]
        c = {int(k): r["banks"][k]["c_ps"] for k in r["banks"]}
        bound = {int(k): r["banks"][k]["bound_ps"] for k in r["banks"]}
        iv = intervals(prn, nb, c, bound, r["dv"])
        # AMENDMENT P12 -- A METRIC ARTEFACT I NEARLY REPORTED AS PHYSICS.
        # Every correct interval above ENDS EXACTLY AT THE SCORING BOUNDARY
        # (bank 1 at T=400: [404.0, 600.0] against bound = c_1 + T = 600.0), so
        # `hold` was measuring where I STOPPED LOOKING, not where the value
        # decayed -- and the cascade margin came out identically equal to minus
        # the successor's own level time, which is the algebraic signature of that
        # truncation and not a fact about the circuit.  The hold is therefore
        # re-measured with the window extended to the END OF THE DECK, which is
        # the only way this deck can see a real decay.  The returns are disabled
        # on these decks, so the extended window is GENEROUS: nothing drains the
        # rail on purpose.
        tend_all = {k: 1e18 for k in range(1, nb + 1)}
        ivx = intervals(prn, nb, c, tend_all, r["dv"])
        # ROBUST arrival = the start of the LONGEST correct interval.  The FIRST
        # interval can be a few-picosecond glitch on the way up (MEASURED: W0 at
        # T=400 has a 4.2 ps interval at 355 ps before its real 107 ps one at
        # 492 ps), which would corrupt a stage time.  Both are reported.
        # AMENDMENT P13, and it changes the verdict: the ARRIVAL must also be
        # read from the EXTENDED window.  With the window capped at one beat, a
        # bank that computes correctly 450 ps after its own rail start reads
        # `never correct` and is indistinguishable from a bank that never
        # computes -- MEASURED: W0 at T=400 bank 5 holds a correct value for
        # 765.4 ps in the extended window and read `ever=False` in the capped one.
        # The capped reading is kept as the K4 gate (does the bank meet the
        # REQUESTED beat) and the extended one is the physical measurement.
        arr = {k: ivx[k].get("longest_start_abs_ps") for k in ivx}
        arrf = {k: ivx[k].get("first_arrival_abs_ps") for k in ivx}
        st, stf = {}, {}
        for k in range(2, W.NSCORE + 1):
            if arr.get(k) is not None and arr.get(k - 1) is not None:
                st["%d_minus_%d" % (k, k - 1)] = arr[k] - arr[k - 1]
            if arrf.get(k) is not None and arrf.get(k - 1) is not None:
                stf["%d_minus_%d" % (k, k - 1)] = arrf[k] - arrf[k - 1]
        depth = 0                      # depth on the EXTENDED window (physical)
        for k in range(1, W.NSCORE + 1):
            if ivx[k]["ever_correct"]:
                depth = k
            else:
                break
        depth_cap = 0                  # depth on the CAPPED window (meets T)
        for k in range(1, W.NSCORE + 1):
            if iv[k]["ever_correct"]:
                depth_cap = k
            else:
                break
        res[tag] = dict(
            T_ps=r["T_ps"], wire=r["wire"], l_nh=r["l_nh"], vgh=r["vgh"],
            m=r["m"], sync=("sync" in tag), restore=("rst" in tag),
            T90ZC_ps=r.get("T90ZC_ps"),
            deepest_correct_bank=depth,
            deepest_correct_bank_WITHIN_ONE_BEAT=depth_cap,
            all_six_ever_correct=bool(depth >= W.NSCORE),
            all_six_within_one_beat=bool(depth_cap >= W.NSCORE),
            K4_own_level_within_T={
                k: (bool((arr[k] - c[k]) <= r["T_ps"])
                    if arr.get(k) is not None else None) for k in ivx},
            per_bank=iv,
            stage_time_by_arrival_ps=st,
            stage_time_by_FIRST_arrival_ps=stf,
            sustained_beat_by_arrival_ps=(max(st.values()) if st else None),
            per_bank_own_level_time_ps={
                k: (arr[k] - c[k]) if arr.get(k) is not None else None
                for k in iv},
            min_hold_over_correct_banks_ps=(
                min(ivx[k]["longest_hold_ps"] for k in range(1, depth + 1))
                if depth else None),
            per_bank_extended=ivx,
            # THE CASCADE CONDITION, and it is not invented after the fact: bank
            # k's value must still be valid when bank k+1 commits, i.e.
            #     hold(k) >= arrival(k+1) - arrival(k).
            # A bank whose output decays before its successor has read it is
            # feeding the successor a stale level, which is exactly what the
            # measured depth limit is.
            hold_to_end_of_deck_ps={k: ivx[k].get("longest_hold_ps") for k in ivx},
            capped_window_reading=dict(
                per_bank_own_level_ps={
                    k: ((iv[k]["longest_start_abs_ps"] - c[k])
                        if iv[k].get("longest_start_abs_ps") is not None else None)
                    for k in iv},
                holds_ps={k: iv[k].get("longest_hold_ps") for k in iv}),
            truncated_by_boundary={
                k: bool(iv[k].get("longest_hold_ps") is not None
                        and ivx[k].get("longest_hold_ps") is not None
                        and ivx[k]["longest_hold_ps"]
                        > iv[k]["longest_hold_ps"] + 1.0) for k in iv},
            cascade_hold=({
                "bank%d" % k: dict(
                    hold_in_window_ps=iv[k]["longest_hold_ps"],
                    hold_to_end_of_deck_ps=ivx[k].get("longest_hold_ps"),
                    required_ps=arr[k + 1] - arr[k],
                    margin_ps=((ivx[k]["longest_hold_ps"]
                                - (arr[k + 1] - arr[k]))
                               if ivx[k].get("longest_hold_ps") is not None
                               else None),
                    holds_long_enough=bool(
                        ivx[k].get("longest_hold_ps") is not None
                        and ivx[k]["longest_hold_ps"] >= arr[k + 1] - arr[k]))
                for k in range(1, nb)
                if arr.get(k) is not None and arr.get(k + 1) is not None}),
            cascade_holds_everywhere=None,
            strict_reading_from_ROWS=dict(
                sustained_beat_ps=r["sustained_beat_ps"],
                all_scored_value_correct=r["all_scored_banks_value_correct"],
                min_margin_mV=r["min_margin_over_scored_mV"]))
        rr = res[tag]
        chv = [v["holds_long_enough"] for v in rr["cascade_hold"].values()]
        rr["cascade_holds_everywhere"] = bool(chv) and all(chv)
        ch = rr["cascade_hold"] if False else None
        print("%-34s depth=%d/6 (within one beat %d/6)  beat=%8s  "
              "min_hold=%8s  T90ZC=%s"
              % (tag, depth, depth_cap,
                 ("%.2f" % rr["sustained_beat_by_arrival_ps"])
                 if rr["sustained_beat_by_arrival_ps"] else "none",
                 ("%.1f" % rr["min_hold_over_correct_banks_ps"])
                 if rr["min_hold_over_correct_banks_ps"] else "none",
                 ("%.4f" % rr["T90ZC_ps"]) if rr["T90ZC_ps"] else "FAILED"),
              flush=True)
        for k in range(1, nb + 1):
            v = ivx[k]
            ch = rr["cascade_hold"].get("bank%d" % k)
            print("    bank%d %s ever=%-5s own_level=%8s hold=%8s  "
                  "needs=%8s  holds=%s  nint=%d"
                  % (k, "".join(PS[k - 1]), v["ever_correct"],
                     ("%.1f" % rr["per_bank_own_level_time_ps"][k])
                     if v["ever_correct"] else "-",
                     ("%.1f" % v["longest_hold_ps"]) if v["ever_correct"] else "-",
                     ("%.1f" % ch["required_ps"]) if ch else "-",
                     (ch["holds_long_enough"] if ch else "-"),
                     v["n_intervals"]), flush=True)
    json.dump(res, open(os.path.join(HERE, out_name), "w"), indent=1)
    print("wrote %s" % out_name, flush=True)
    return res


if __name__ == "__main__":
    for rf, on in (("ROWS.json", "REANALYSIS_SKEWED.json"),
                   ("ROWS_SYNC.json", "REANALYSIS_SYNC.json"),
                   ("ROWS_RESTORE.json", "REANALYSIS_RESTORE.json")):
        if os.path.exists(os.path.join(HERE, rf)):
            print("==== %s ====" % rf, flush=True)
            rebuild(rf, on)
