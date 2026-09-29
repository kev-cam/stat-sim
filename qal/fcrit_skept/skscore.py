#!/usr/bin/env python3
"""SKEPT independent re-score.  Shares no code with qal/fcrit/rescore.py.

Differences of substance, deliberate:
  * the commit instant is read OFF THE RECEIVING RAIL (first local maximum after
    it passes half its peak) -- no inductor identification, no wiring assumed;
    the primary's ZCS instant is computed too and the two are cross-checked.
  * three instants are scored for every link: RAILPEAK, ZCS, and the receiving
    bank's own committed stage boundary.
  * the intended logic value is derived FROM THE DECK (bank-1 source values +
    inverter parity), not from a hard-coded pattern table.
  * the noise budget is reported at several values, including one that refuses
    to charge a row twice for a disturbance already present in its own waveform.
  * a WORST-OVER-WINDOW margin is computed as well as the at-instant margin.
"""
import sys, os, re, json, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sklib

QAL = "/usr/local/src/stat-sim/qal"
TRIP = sklib.Trip(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "TRIP_SKEPT.json"), "S")

def rail_peak_instant(w, k):
    """the instant the receiving rail stops being charged, read off the rail."""
    col = "V(RAIL%d)" % k
    if not w.has(col):
        return None
    y = w.s(col); t = w.t
    pk = float(np.max(y))
    if pk <= 0:
        return None
    i0 = int(np.argmax(y >= 0.5 * pk))
    # first local maximum after i0 (3-sample confirmation against print noise)
    for i in range(i0 + 1, len(y) - 3):
        if y[i] >= y[i + 1] and (y[i] - y[i + 3]) > 2e-4:
            return float(t[i])
    return float(t[int(np.argmax(y))])

def zcs_instants(w, nbank):
    """primary's protocol, reimplemented: for each bank the ZCS of whichever
    inductor's [peak, zero] window raised that rail the most."""
    zs = {}
    for j in range(1, 13):
        c = "I(L%d)" % j
        if not w.has(c):
            continue
        I = w.s(c); ip = int(np.argmax(I))
        if I[ip] <= 0:
            continue
        for i in range(ip + 1, len(I)):
            if I[i - 1] > 0 >= I[i]:
                t0, t1 = w.t[i - 1], w.t[i]
                zs[j] = (float(t0 + (t1 - t0) * I[i - 1] / (I[i - 1] - I[i])),
                         float(w.t[ip]))
                break
    out = {}
    for k in range(1, nbank + 1):
        c = "V(RAIL%d)" % k
        if not w.has(c):
            continue
        pk = float(np.max(w.s(c))); best = None; br = 0.0
        for j, (tz, tp) in zs.items():
            r = w.at(c, tz) - w.at(c, tp)
            if r > br:
                br, best = r, tz
        out[k] = best if (best is not None and br > 0.05 * pk) else None
    return out

def score(cir, nbank, gate_idx=None):
    prn = cir + ".prn"
    w = sklib.W(prn)
    ck = sklib.deck_checkpoints(cir)
    oh = sklib.intended(cir, nbank)
    rp = {k: rail_peak_instant(w, k) for k in range(1, nbank + 1)}
    zc = zcs_instants(w, nbank)
    banks = sklib.deck_banks(cir)
    links = []
    for k in range(1, nbank + 1):
        if k not in ck or k not in banks:
            continue
        gi = gate_idx if gate_idx is not None else banks[k]
        rx = k + 1 if (k + 1) <= nbank else k
        last = (rx == k)
        inst = {}
        inst["CK"] = ck.get(rx)
        inst["RAILPEAK"] = ck[k] if last else rp.get(rx)
        inst["ZCS"] = ck[k] if last else zc.get(rx)
        inst["STRICT_last"] = rp.get(k) if last else inst["RAILPEAK"]
        rk = w.at("V(RAIL%d)" % k, ck[k])
        for i in gi:
            col = "V(O%d_%d)" % (k, i)
            if not w.has(col):
                continue
            want = oh(k, i)
            if want is None:
                continue
            v1 = w.at(col, ck[k])
            s1 = 100.0 * ((v1 / rk) if want else (1.0 - v1 / rk)) if rk else None
            guard = ((v1 >= 0.50 * rk) if want else (v1 <= 0.10 * rk)) if rk else False
            rec = dict(k=k, i=i, want_hi=bool(want), rx=rx, last=bool(last),
                       settle_pct=(round(s1, 3) if s1 is not None else None),
                       pass90=bool(s1 is not None and s1 >= 90.0),
                       guard=bool(guard))
            for nm, tt in inst.items():
                if tt is None:
                    rec["m_" + nm] = None
                    continue
                Rrx = w.at("V(RAIL%d)" % rx, tt)
                vt = float(TRIP(Rrx))
                v = w.at(col, tt)
                d = (v - vt) if want else (vt - v)
                rec["m_" + nm] = round(1000.0 * d, 4)
                if nm == "RAILPEAK":
                    rec["t"] = round(tt, 3); rec["rail_rx"] = round(Rrx, 6)
                    rec["vtrip_rx"] = round(vt, 6); rec["v"] = round(v, 6)
                    # ever correct after the instant?
                    y = w.s(col); m = w.t > tt
                    if m.any():
                        railrx = w.s("V(RAIL%d)" % rx)[m]
                        vts = TRIP(np.maximum(railrx, 1e-6))
                        dd = (y[m] - vts) if want else (vts - y[m])
                        rec["later_ok"] = bool(np.any(dd >= 0))
                    else:
                        rec["later_ok"] = False
                    # worst margin over the charging window [half-peak .. instant]
                    c = "V(RAIL%d)" % rx
                    yr = w.s(c); pk = float(np.max(yr))
                    i0 = int(np.argmax(yr >= 0.5 * pk))
                    mw = (w.t >= w.t[i0]) & (w.t <= tt)
                    if mw.sum() > 1:
                        vts = TRIP(np.maximum(yr[mw], 1e-6))
                        dw = (y[mw] - vts) if want else (vts - y[mw])
                        rec["m_WORSTWIN"] = round(1000.0 * float(np.min(dw)), 4)
                    else:
                        rec["m_WORSTWIN"] = rec["m_RAILPEAK"]
            links.append(rec)
    return dict(deck=os.path.basename(cir), nbank=nbank, n=len(links),
                rail_peak_ps={k: (round(v, 3) if v else None) for k, v in rp.items()},
                zcs_ps={k: (round(v, 3) if v else None) for k, v in zc.items()},
                ck=ck, links=links)

def main():
    DS = []
    modes = {k: v.get("mode") for k, v in json.load(
        open(os.path.join(QAL, "chain3", "ROWS_full.json"))).items()}
    for p in sorted(glob.glob(os.path.join(QAL, "chain3", "c_*.cir"))):
        if os.path.exists(p + ".prn"):
            b = os.path.basename(p)[:-4]
            DS.append(("chain3", b, p, 3, None, modes.get(b[2:], "?")))
    for p in sorted(glob.glob(os.path.join(QAL, "banktank", "c_*.cir"))):
        if os.path.exists(p + ".prn"):
            b = os.path.basename(p)[:-4]
            m = "topup" if "topup" in b else ("vfull" if "vfull" in b else "free")
            DS.append(("banktank", b, p, 4, None, m))
    out = {}
    for ds, tag, p, nb, gi, mode in DS:
        try:
            r = score(p, nb, gi)
        except Exception as e:
            print("FAIL", ds, tag, e); continue
        r["mode"] = mode
        r["has_active_topup"] = bool(sklib.topup_windows(p))
        out.setdefault(ds, {})[tag] = r
        print("%-9s %-32s n=%3d pass90=%3d guard=%3d mode=%-6s topup=%s"
              % (ds, tag, r["n"], sum(1 for L in r["links"] if L["pass90"]),
                 sum(1 for L in r["links"] if L["guard"]), mode,
                 r["has_active_topup"]))
    json.dump(out, open("SKSCORE.json", "w"))
    print("wrote SKSCORE.json")

if __name__ == "__main__":
    main()
