#!/usr/bin/env python3
"""(d) the initiation interval.  II = H*T (banktank README 7d, pre-stated there).

Re-analysis only.  Two extra things G3 did not do:
  1. tabulate II over ALL hold depths H, not just the H=4 headline, because the
     committed record's BEST II came from H=2 (500 ps), not from H=4 (800 ps);
  2. re-score the last bank STRICTLY (at its own ZCS, no GENEROUS allowance) and
     report whether any II conclusion depends on the generous last bank.

Iso-swing only: dV = 1.2, mode = free.  The committed README forbids quoting the
vfull rows as speed results (they deliver a 1.45 V rail) and the dV = 1.65 rows
are a 1.65 V swing, not iso-swing with the 1.2 V CMOS comparator.
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rescore import Trip, score_deck, NB, Wave, commit_instants, committed_checkpoints

HERE = os.path.dirname(os.path.abspath(__file__))
QAL = os.path.dirname(HERE)
TRIP = Trip(os.path.join(HERE, "TRIP.json"), "S")
PAT = [1, 1, 1, 0, 1, 0, 0, 1]


def oh_pat(k, i):
    in_hi = (PAT[i] == 1) if (k % 2 == 1) else (PAT[i] == 0)
    return not in_hi


def strict_last_bank(cir, nbank, mgate, out_hi, trip, nb):
    """Same criterion, but the LAST bank is scored at its OWN ZCS -- no generous
    allowance.  Returns (links_pass, n, worst_margin_mV)."""
    w = Wave(cir + ".prn")
    ck = committed_checkpoints(cir)
    tc = commit_instants(w, nbank)
    n = 0
    npass = 0
    worst = None
    for k in range(1, nbank + 1):
        if k not in ck:
            continue
        rx = k + 1 if (k + 1) <= nbank else k
        trx = tc[rx]["t"]                     # STRICT: own ZCS even for k == N
        Rrx = w.at("V(RAIL%d)" % rx, trx)
        vt_rx, _ = trip(Rrx)
        for i in range(mgate):
            col = "V(O%d_%d)" % (k, i)
            if not w.has(col):
                continue
            want_hi = bool(out_hi(k, i))
            v3 = w.at(col, trx)
            d3 = (v3 - vt_rx) if want_hi else (vt_rx - v3)
            n += 1
            if d3 >= nb:
                npass += 1
            worst = d3 if worst is None else min(worst, d3)
    return npass, n, (round(1000 * worst, 3) if worst is not None else None)


def main():
    rows = {}
    # committed banktank rows + the three NEW fcrit/btk rows
    srcs = [(p, "committed") for p in
            sorted(glob.glob(os.path.join(QAL, "banktank", "c_*.cir")))]
    srcs += [(p, "new_fcrit") for p in
             sorted(glob.glob(os.path.join(HERE, "btk", "c_*.cir")))]
    for p, origin in srcs:
        b = os.path.basename(p)[:-4]
        if not os.path.exists(p + ".prn"):
            continue
        m = re.match(r"c_m(\d+)_T(\d+)_H(\d+)_dv(\d+)_(\w+)$", b)
        if not m:
            continue
        mm, T, H, dv, mode = (int(m.group(1)), int(m.group(2)), int(m.group(3)),
                              int(m.group(4)), m.group(5))
        if not (mm == 10 and dv == 1200 and mode == "free"):
            continue                      # iso-swing headline family only
        nbn = "free"
        r = score_deck(p, 4, 8, oh_pat, TRIP, NB[nbn], label=b)
        sp, sn, sw = strict_last_bank(p, 4, 8, oh_pat, TRIP, NB[nbn])
        mar = [L["S3_margin_mV"] for L in r["links"]]
        rows[b] = dict(
            m=mm, T=T, H=H, dv=dv, mode=mode, origin=origin, II_ps=H * T,
            n=r["n_gates"], S1=r["S1_pass"], VALUE=r["value_guard_pass"],
            S3=r["S3_pass"], ROW_S1=r["ROW_S1"], ROW_VALUE=r["ROW_VALUE"],
            ROW_S3=r["ROW_S3"],
            FAIL_budget=r["S3_FAIL_budget"], FAIL_late=r["S3_FAIL_late"],
            FAIL_never=r["S3_FAIL_never"],
            worst_margin_mV=round(min(mar), 3) if mar else None,
            strict_last_bank=dict(links_pass=sp, n=sn, row_pass=(sp == sn),
                                  worst_margin_mV=sw),
        )
        print("%-34s %-9s H=%d T=%3d II=%4d  S1row=%-5s VALrow=%-5s S3row=%-5s "
              "S3=%2d/%2d worst=%9.3f mV | STRICT %2d/%2d worst=%9.3f mV"
              % (b, origin, H, T, H * T, r["ROW_S1"], r["ROW_VALUE"],
                 r["ROW_S3"], r["S3_pass"], r["n_gates"], min(mar), sp, sn, sw))

    # ---- II tables
    out = {"rows": rows, "II_TABLE": {}}
    for bar, key in (("bar_90pct", "ROW_S1"), ("functional", "ROW_S3"),
                     ("functional_strict_last_bank", "STRICT")):
        tab = {}
        for b, d in rows.items():
            ok = d["strict_last_bank"]["row_pass"] if key == "STRICT" else d[key]
            if not ok:
                continue
            H = d["H"]
            if H not in tab or d["T"] < tab[H]["T"]:
                tab[H] = dict(T=d["T"], II_ps=d["H"] * d["T"], row=b,
                              origin=d["origin"])
        best = min(tab.values(), key=lambda x: x["II_ps"]) if tab else None
        out["II_TABLE"][bar] = dict(per_H=tab, BEST=best)
        print("\n%s:" % bar)
        for H in sorted(tab):
            print("  H=%d  earliest correct T = %3d ps  ->  II = %4d ps  (%s)"
                  % (H, tab[H]["T"], tab[H]["II_ps"], tab[H]["row"]))
        if best:
            print("  BEST II = %d ps  (%s)" % (best["II_ps"], best["row"]))
    json.dump(out, open(os.path.join(HERE, "II.json"), "w"), indent=1)
    print("\nwrote II.json")


if __name__ == "__main__":
    main()
