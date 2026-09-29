#!/usr/bin/env python3
"""Driver for qal/tankfed.  The 2x2 (top-up DESTINATION x tank SIZING) plus m.

Order of operations, and it matters:
  1. C_bank(M) MEASURED first (cbank.py) -- the matching rule needs it.
  2. T fixed GLOBALLY from the DERIVED slowest hop, so the matrix cells are
     comparable; verified after the fact against the MEASURED zeros.
  3. hop ZCS zeros RE-PROBED per configuration (tank sizing changes C_ser).
  4. rows: free control (top-up devices PRESENT but parked off) and topped.
"""
import json, math, os, sys, threading
from concurrent.futures import ThreadPoolExecutor
import tf, extract

HERE = tf.HERE
LK = threading.Lock()
ZC = os.path.join(HERE, "zeros.json")
TZC = os.path.join(HERE, "tu_zeros.json")
CB = os.path.join(HERE, "CBANK.json")


def _load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def _save(p, o):
    t = p + ".tmp"
    json.dump(o, open(t, "w"), indent=1)
    os.replace(t, p)


def cbank():
    d = {}
    for r in _load(CB):
        if "C_bank_fF" in r:
            d[r["M"]] = r["C_bank_fF"]
    return d


def cell_caps():
    """MEASURED decomposition of the bank rail capacitance into a per-cell
    pull-DOWN and pull-UP contribution.  The fixture measures C_bank(M) for
    M in {1,2,3,8,19,48} with alternating inputs; those six numbers are fitted
    EXACTLY (to 4-5 digits) by

        C_bank = n_down * C_DOWN + n_up * C_UP

    because a pull-UP cell's output node tracks the rail and so its 2 fF load
    IS incremental rail capacitance, while a pull-DOWN cell's output sits at
    ground and only its off-state pMOS drain contributes.  C_DOWN comes from the
    M=1 fixture directly, C_UP from M=2 minus M=1; M=3/8/19/48 then reproduce to
    0.001-0.01%.  This decomposition is needed because the chain's parity
    convention is is_hi(k,i) = (i+k) odd, which for an ODD-sized bank gives a
    different up/down split than the fixture's -- bank 4 of the profile is a
    SINGLE PULL-UP cell (5.745 fF), not the 2.486 fF the M=1 fixture reads."""
    d = cbank()
    c_down = d.get(1)
    c_up = (d.get(2) - d.get(1)) if (1 in d and 2 in d) else None
    return c_down, c_up


def cbank_of_bank(k, prof=tf.PROFILE):
    """C_bank for bank k, using the CHAIN's own parity."""
    c_down, c_up = cell_caps()
    n_dn = sum(1 for i in range(prof[k - 1]) if tf.is_hi(k, i))
    n_up = prof[k - 1] - n_dn
    return n_dn * c_down + n_up * c_up


def ctk_map(sizing, m, prof=tf.PROFILE):
    """matched: C_tank_k = m * C_bank_k.
    uniform : the SAME TOTAL tank capacitance spread equally -- the only fair
              uniform control, since it holds tank area (and therefore cost)
              constant between the two arms at the same m."""
    per = [m * cbank_of_bank(k + 1, prof) for k in range(len(prof))]
    if sizing == "matched":
        return {k + 1: per[k] for k in range(len(prof))}
    u = sum(per) / len(per)
    return {k + 1: u for k in range(len(prof))}


def probe_span(ctk, prof=tf.PROFILE):
    """DERIVED probe window: 5x the largest undamped half-period pi*sqrt(L*C_ser)
    over the hops of this configuration, floored at the committed 6*t_est."""
    import math
    tot = {k + 1: ctk[k + 1] + cbank_of_bank(k + 1, prof) for k in range(len(prof))}
    worst = 0.0
    for s_, t_ in tf.HOPS:
        cser = tot[s_] * tot[t_] / (tot[s_] + tot[t_])
        worst = max(worst, math.pi * math.sqrt(15e-9 * cser * 1e-15) * 1e12)
    return max(6.0 * tf.TZ_ANCHOR * tf.CHAIN_F, 5.0 * worst)


def cfg_of(dest, sizing, m, form, T, dv, ltu=1.0, ton=24.0):
    return dict(dest=dest, sizing=sizing, m=m, form=form, T=T, dv=dv,
                ctk=ctk_map(sizing, m), ltu=ltu, ton=ton, prof=tf.PROFILE,
                probe_span=probe_span(ctk_map(sizing, m)),
                cbank={k + 1: cbank_of_bank(k + 1) for k in range(len(tf.PROFILE))})


def tag_of(cfg):
    return "%s_%s_m%g_%s_T%g_dv%g" % (cfg["dest"], cfg["sizing"], cfg["m"],
                                      cfg["form"], cfg["T"], cfg["dv"] * 1000)


def zkey(cfg):
    """The hop zeros depend on the tank sizing, m, T, dV and on which parasitic
    top-up devices are present (clamp TG vs buck).  They do NOT depend on whether
    the top-up is LIVE, which is why the free control shares them with its own
    topped row -- and must, or the difference is not attributable."""
    fam = {"ptu": "buck", "bare": "none"}.get(cfg["form"], "tg")
    return "%s|%s|%g|%s|%g|%g" % (cfg["dest"], cfg["sizing"], cfg["m"], fam,
                                  cfg["T"], cfg["dv"])


def probe_hops(cfg):
    key = zkey(cfg)
    with LK:
        c = _load(ZC)
        if key in c:
            return c[key]
    tz = []
    nh = len(tf.HOPS)
    pcfg = dict(cfg)
    pcfg["form"] = {"ptu": "ptu", "bare": "bare"}.get(cfg["form"], "free")
    for h in range(1, nh + 1):
        full = tz + [tf.TZ_ANCHOR * tf.CHAIN_F] * (nh - len(tz))
        L, S = tf.deck(pcfg, tz=full, probe=h)
        fn = "p%d_%s.cir" % (h, tag_of(pcfg))
        p, msg = tf.run(fn, L)
        print("    probe%d %s" % (h, msg), flush=True)
        if p is None:
            return None
        hdr, rows = tf.read_prn(p + ".prn")
        z, pk = tf.zero_after_peak(hdr, rows, "I(L%d)" % h, S["close"][h - 1])
        if z is None:
            print("    probe%d NO ZERO" % h, flush=True)
            return None
        tz.append(z - S["close"][h - 1])
        print("      hop%d t_zcs = %.4f ps (Ipk %.2f uA)" % (h, tz[-1], pk * 1e6),
              flush=True)
    with LK:
        c = _load(ZC); c[key] = tz; _save(ZC, c)
    return tz


def probe_topup(cfg, tz):
    """The top-up freewheel zero, RE-PROBED PER BANK (the banks sit at different
    rails, and under matched sizing at very different tank sizes too)."""
    key = zkey(cfg) + "|tu|%g|%g" % (cfg["ltu"], cfg["ton"])
    with LK:
        c = _load(TZC)
        if key in c:
            return {int(k): v for k, v in c[key].items()}
    out = {}
    for k in tf.TOPPED:
        L, S = tf.deck(cfg, tz=tz, tu_probe=k)
        fn = "q%d_%s.cir" % (k, tag_of(cfg))
        p, msg = tf.run(fn, L)
        print("    tuprobe%d %s" % (k, msg), flush=True)
        if p is None:
            return None
        hdr, rows = tf.read_prn(p + ".prn")
        t_open = S["open"][[t for _, t in tf.HOPS].index(k)]
        t_fire = t_open + 6 * tf.EDGE
        a = t_fire + tf.SLEW + 4 * tf.EDGE
        b = a + cfg["ton"]
        z, pk = tf.zero_after_peak(hdr, rows, "I(LTU%d)" % k, a)
        if z is None:
            print("    tuprobe%d NO ZERO" % k, flush=True)
            return None
        out[k] = max(0.0, z - b)
        print("      bank%d freewheel zero at %.4f ps -> tfw %.4f ps (Ipk %.2f uA)"
              % (k, z, out[k], pk * 1e6), flush=True)
    with LK:
        c = _load(TZC); c[key] = {str(x): v for x, v in out.items()}; _save(TZC, c)
    return out


def one_row(cfg):
    tg = tag_of(cfg)
    try:
        tz = probe_hops(cfg)
        if tz is None:
            return dict(tag=tg, error="hop ZCS probe failed (reported, not hidden)")
        tfw = None
        if cfg["form"] == "ptu":
            tfw = probe_topup(cfg, tz)
            if tfw is None:
                return dict(tag=tg, error="top-up ZCS probe failed")
        L, S = tf.deck(cfg, tz=tz, tfw=tfw)
        p, msg = tf.run("r_%s.cir" % tg, L)
        print("  row %s" % msg, flush=True)
        if p is None:
            return dict(tag=tg, error=msg)
        m = tf.parse_mt0(p + ".mt0")
        r = extract.row(cfg, m, S, p)
        r["tag"] = tg
        r["tfw_ps"] = tfw
        r["run_msg"] = msg
        return r
    except Exception as e:
        return dict(tag=tg, error="%s: %s" % (type(e).__name__, e))


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "matrix"
    T = float(sys.argv[2]) if len(sys.argv) > 2 else 340.0
    specs = []
    if which in ("m6", "m2", "matrix"):
        ms = {"m6": (6.0,), "m2": (2.0,), "matrix": (2.0, 6.0)}[which]
        for m in ms:
            for dest in ("bank", "tank"):
                for sizing in ("uniform", "matched"):
                    for form in ("free", "clamp"):
                        specs.append(cfg_of(dest, sizing, m, form, T, 1.2))
    elif which == "buck":
        for dest in ("bank", "tank"):
            for form in ("free", "ptu"):
                specs.append(cfg_of(dest, "matched", 6.0, form, T, 1.2))
    elif which == "bare":
        specs = [cfg_of("bank", "matched", 6.0, "bare", T, 1.2)]
    elif which == "dv165":
        for dest in ("bank", "tank"):
            for form in ("free", "clamp"):
                specs.append(cfg_of(dest, "matched", 6.0, form, T, 1.65))
    elif which == "one":
        specs = [cfg_of(sys.argv[3], sys.argv[4], float(sys.argv[5]),
                        sys.argv[6], T, float(sys.argv[7]))]
    out, op = [], os.path.join(HERE, "ROWS_%s.json" % which)
    nw = int(os.environ.get("TF_WORKERS", "3"))
    with ThreadPoolExecutor(max_workers=nw) as ex:
        for r in ex.map(one_row, specs):
            out.append(r)
            print("%-52s %s" % (r["tag"], r.get("error") or
                                "worst/stage %s | rail %s"
                                % ([None if v is None else round(v, 2)
                                    for v in r["worst_gate_by_stage_pct"]],
                                   [None if v is None else round(v, 4)
                                    for v in r["rail_by_stage_V"]])), flush=True)
            _save(op, out)
    _save(op, out)
    print("wrote", op)


if __name__ == "__main__":
    main()
