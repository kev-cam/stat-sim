"""p2 FINAL -- one arrival definition, applied once, to every saved waveform.

AMENDMENT P14 settles a definition that moved three times during this phase and
must not move again:

  ARRIVAL(k) = the start of the FIRST contiguous interval, searched from bank k's
               own rail start to the END OF THE DECK, in which all four of bank
               k's outputs are on the correct side of the receiver's MEASURED trip
               at bank k's own INSTANTANEOUS delivered rail by the 3-sigma budget
               (19.323 mV).
  HOLD(k)    = that interval's length.
  STAGE(k)   = ARRIVAL(k) - ARRIVAL(k-1).
  BEAT       = max STAGE over the scored banks that arrived.  MEASURED, a
               difference of two waveform instants, never the scheduled T.
  OWN LEVEL(k) = ARRIVAL(k) - bank k's own rail-start instant.

Why FIRST and not LONGEST: a wave uses the first correct value, not the best one.
The longest-interval rule was tried and MEASURED to misbehave -- at W2/T=400 bank 3
it skipped a real 151.1 ps interval at 1247.6 ps in favour of a later, longer one
at 2234.9 ps that is the rail drifting into a state that happens to read correct,
not a computation, and it inflated that row's beat from 436 ps to 2194 ps.  Glitches
in the other direction stay visible because the interval count and the hold are
reported on every bank.

Why to the END OF THE DECK and not one beat: capping the search at one beat makes
a bank that computes correctly 450 ps after its own rail start indistinguishable
from a bank that never computes (MEASURED: W0/T=400 bank 5).  Whether a bank met
the REQUESTED beat is reported separately as the K4 gate.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W
import comp

HERE = W.HERE
WS, PS = W.logic()
ROWFILES = ("ROWS.json", "ROWS_SYNC.json", "ROWS_RESTORE.json")


def scan(prn, nb, c):
    hdr, rows = W.read_prn(prn)
    ir = {k: hdr.index("V(RAIL%d)" % k) for k in range(1, nb + 1)}
    iy = {(k, i): hdr.index("V(Y%d_%d)" % (k, i))
          for k in range(1, nb + 1) for i in range(W.NCELL)}
    T = [r[1] * 1e12 for r in rows]
    out = {}
    for k in range(1, nb + 1):
        want = WS[k - 1]
        runs, cur, first_marg = [], None, None
        for n, t in enumerate(T):
            if t < c[k]:
                continue
            vb = rows[n][ir[k]]
            ok, mm = False, None
            if vb > 0.2:
                tv = W.trip_at(vb)
                mm = min((rows[n][iy[(k, i)]] - tv) if want[i]
                         else (tv - rows[n][iy[(k, i)]]) for i in range(W.NCELL))
                ok = mm > W.NB_V
            if ok:
                if cur is None:
                    cur = [t, t, mm]
                else:
                    cur = [cur[0], t, min(cur[2], mm)]
            elif cur is not None:
                runs.append(tuple(cur)); cur = None
        if cur is not None:
            runs.append(tuple(cur))
        o = dict(n_intervals=len(runs),
                 intervals_ps=[[round(a, 2), round(b, 2)] for a, b, _ in runs[:6]])
        if runs:
            a, b, mg = runs[0]
            # state AT arrival, for the settling and separation tables
            n0 = min(range(len(T)), key=lambda n: abs(T[n] - a))
            rail = rows[n0][ir[k]]
            tv = W.trip_at(rail)
            cells = []
            for i in range(W.NCELL):
                v = rows[n0][iy[(k, i)]]
                cells.append(dict(
                    cell=i, path=PS[k - 1][i], form=W.FORMS[k - 1][i],
                    want=want[i], V=v, trip=tv,
                    margin_mV=1000.0 * ((v - tv) if want[i] else (tv - v)),
                    settled_pct_of_own_rail=(100.0 * v / rail if want[i]
                                             else 100.0 * (1.0 - v / rail)),
                    K2_floor_ok=bool(v >= W.FLOOR) if want[i]
                    else bool(v <= 1.65 - W.FLOOR)))
            o.update(arrived=True, arrival_abs_ps=a, hold_ps=b - a,
                     own_level_ps=a - c[k], rail_at_arrival_V=rail,
                     rail_peak_V=max(rows[n][ir[k]] for n, t in enumerate(T)
                                     if t >= c[k]),
                     min_margin_mV=min(x["margin_mV"] for x in cells),
                     min_margin_sigma=min(x["margin_mV"] for x in cells) / W.SIG_MV,
                     min_settled_pct=min(x["settled_pct_of_own_rail"] for x in cells),
                     K2_all_ok=all(x["K2_floor_ok"] for x in cells), cells=cells)
        else:
            o.update(arrived=False, arrival_abs_ps=None, hold_ps=None,
                     own_level_ps=None,
                     rail_peak_V=max(rows[n][ir[k]] for n, t in enumerate(T)
                                     if t >= c[k]))
        out[k] = o
    return out


def one_row(tag, r):
    prn = os.path.join(HERE, r["deck"] + ".prn")
    nb = r["nbank"]
    c = {int(k): r["banks"][k]["c_ps"] for k in r["banks"]}
    pb = scan(prn, nb, c)
    depth = 0
    for k in range(1, W.NSCORE + 1):
        if pb[k]["arrived"]:
            depth = k
        else:
            break
    st = {}
    for k in range(2, W.NSCORE + 1):
        if pb[k]["arrived"] and pb[k - 1]["arrived"]:
            st["%d_minus_%d" % (k, k - 1)] = (pb[k]["arrival_abs_ps"]
                                             - pb[k - 1]["arrival_abs_ps"])
    stw = {k: v for k, v in st.items() if int(k.split("_")[0]) <= depth}
    beat = max(stw.values()) if stw else None
    casc = {}
    for k in range(1, depth):
        need = st.get("%d_minus_%d" % (k + 1, k))
        if need is not None:
            casc["bank%d" % k] = dict(hold_ps=pb[k]["hold_ps"], required_ps=need,
                                      margin_ps=pb[k]["hold_ps"] - need,
                                      ok=bool(pb[k]["hold_ps"] >= need))
    return dict(
        tag=tag, T_requested_ps=r["T_ps"], wire=r["wire"], l_nh=r["l_nh"],
        vgh=r["vgh"], m=r["m"], H=r["H"],
        arrangement=("SYNCHRONOUS rails" if r.get("sync_flag") else "SKEWED wave"),
        bank=("RESTORING, 2 transistor levels" if r.get("restore_flag")
              else "TG-XOR only, 1 transistor level"),
        cbank_fF=r["cbank_fF"],
        per_deck_instrument_T90ZC_ps=r.get("T90ZC_ps"),
        per_deck_instrument_rel=(abs(r["T90ZC_ps"] - 57.1428) / 57.1428
                                if r.get("T90ZC_ps") else None),
        deepest_correct_bank=depth,
        all_six_correct=bool(depth >= W.NSCORE),
        SUSTAINED_BEAT_ps=beat,
        stage_time_ps=st,
        own_level_ps={k: pb[k]["own_level_ps"] for k in pb},
        hold_ps={k: pb[k]["hold_ps"] for k in pb},
        K4_own_level_within_requested_T={
            k: (bool(pb[k]["own_level_ps"] <= r["T_ps"])
                if pb[k]["arrived"] else None) for k in pb},
        cascade_hold=casc,
        cascade_holds_everywhere=bool(casc) and all(v["ok"] for v in casc.values()),
        latency_by_depth_ps={
            k: (pb[k]["arrival_abs_ps"] - c[1]) if pb[k]["arrived"] else None
            for k in range(1, W.NSCORE + 1)},
        separation_by_depth={
            k: dict(min_margin_mV=pb[k].get("min_margin_mV"),
                    sigma_multiples=pb[k].get("min_margin_sigma"),
                    rail_at_arrival_V=pb[k].get("rail_at_arrival_V"))
            for k in range(1, W.NSCORE + 1)},
        K5_IZ_max_uA=r.get("K5_IZ_max_uA"),
        energy_ledger_fJ_REPORTED_NOT_A_GATE=r.get(
            "energy_ledger_fJ_REPORTED_NOT_A_GATE"),
        per_bank=pb)


if __name__ == "__main__":
    W.check_logic_against_prereg()
    allrows = {}
    for rf in ROWFILES:
        p = os.path.join(HERE, rf)
        if not os.path.exists(p):
            continue
        for tag, r in json.load(open(p)).items():
            if r.get("FAILED"):
                allrows[tag] = dict(tag=tag, FAILED=r["FAILED"],
                                    T_requested_ps=r.get("T_ps"),
                                    wire=r.get("wire"))
                continue
            r["sync_flag"] = "sync" in tag
            r["restore_flag"] = "rst" in tag
            allrows[tag] = one_row(tag, r)
    json.dump(allrows, open(os.path.join(HERE, "FINAL_ROWS.json"), "w"), indent=1)
    print("%-34s %-18s %-32s depth beat_ps  own_level_ps                 casc"
          % ("tag", "arrangement", "bank"))
    for tag in sorted(allrows):
        r = allrows[tag]
        if r.get("FAILED"):
            print("%-34s FAILED %s" % (tag, r["FAILED"][:50])); continue
        ol = " ".join(("%6.1f" % r["own_level_ps"][k])
                      if r["own_level_ps"][k] is not None else "     -"
                      for k in range(1, 7))
        print("%-34s %-18s %-32s %d/6  %8s  %s  %s"
              % (tag, r["arrangement"][:18], r["bank"][:32],
                 r["deepest_correct_bank"],
                 ("%.2f" % r["SUSTAINED_BEAT_ps"]) if r["SUSTAINED_BEAT_ps"]
                 else "none", ol, r["cascade_holds_everywhere"]))
    print("\nwrote FINAL_ROWS.json")
