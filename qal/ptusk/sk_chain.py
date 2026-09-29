#!/usr/bin/env python3
"""SKEPTIC re-run: the matched triple at ONE operating point, from scratch.

  free   -- no top-up (the control)
  rtu    -- the SWITCHED CLAMP to the ideal dV node (what the committed verdict used)
  ptu    -- the PULSED INDUCTOR, with the corrected cell (what the brief says was
            pre-registered, built, run, and then not reported)

TWO fixes are carried, and both are stated so they can be checked:

  (1) the corrected top-up cell.  Verified line-by-line against qal/skiptu/tucell.py
      (the small fixture): HS pMOS on at a-SLEW-2*EDGE while the LS still clamps na,
      LS released over SLEW ps ending at a, OUT closed last on [a-EDGE, a], plus the
      CNA that AMENDMENT A6 makes mandatory at a buck switch node.

  (2) THE A8 FIX ON THE ptu PATH, which the committed harness never applied and which
      the ptu re-analysis also left unfixed.  sk_tu.py (my patched copy) instantiates
      the destination bank's top-up devices in the PARKED state inside every probe
      deck instead of dropping them, so the OUT switch's drain capacitance loads the
      rail whose zero is being measured.  Without it every pulsed row fails the
      pre-registered A6 |IZ| < 1.0 uA gate.

Cache, directory and zeros are MINE.  qal/skiptu and qal/ptu are read-only from here.
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK
import sk_tu as tu

CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_ptusk")
tu.HERE = HERE
tu.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)

EDGE, VGH = SK.EDGE, SK.VGH
CNA_FF = 8.0      # ASSUMED; DERIVED central estimate ~8 fF (A6's own arithmetic)
SLEW = 24.0       # ps, tucell.py's corrected low-side turn-off slew
tu.CNA_OFF_FF = CNA_FF


def topup_dev_corrected(k, ltu_nh, wsw, t_fire, t_on, vsup, tfw, big=None):
    """tucell.py's corrected cell, re-instanced per bank.  Sequence verified
    against the fixture: HS falls [t_fire, t_fire+2e] = [a-SLEW-4e, a-SLEW-2e];
    LS falls [a-SLEW, a]; OUT closes [a-e, a]; pulse [a, b]; freewheel to the
    MEASURED zero z = b + tfw."""
    e = EDGE
    a = t_fire + SLEW + 4 * e
    b = a + t_on
    probe_form = tfw is None
    z = (big if probe_form else b + tfw)
    w = SK.widths(wsw * 1.5)
    L = [
        "CNA%d na%d 0 %gf" % (k, k, CNA_FF),
        "XTUSW%d na%d gtu%d tsup tsup sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, wsw),
        "XTUFW%d na%d gfw%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, wsw),
        "LTU%d na%d ntm%d %gn" % (k, k, k, ltu_nh),
        "RTU%d ntm%d nb%d %g" % (k, k, k, tu.RSTU),
        "VMTU%d nb%d nbx%d 0" % (k, k, k),
        "XTUON%d nbx%d gto%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
        % (k, k, k, k, w["wn"]),
        "XTUOP%d nbx%d gtop%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
        % (k, k, k, k, w["wp"]),
        "VGTU%d gtu%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
        % (k, k, VGH, t_fire, VGH, t_fire + 2 * e, b, b + e, VGH),
        "VGFW%d gfw%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
        % (k, k, VGH, a - SLEW, VGH, a, b, b + e, VGH),
    ]
    if probe_form:
        L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)"
              % (k, k, a - e, a, VGH, z, VGH),
              "VGTOP%d gtop%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
              % (k, k, VGH, a - e, VGH, a, z)]
    else:
        L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (k, k, a - e, a, VGH, z, VGH, z + e),
              "VGTOP%d gtop%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (k, k, VGH, a - e, VGH, a, z, z + e, VGH)]
    return L, (None if probe_form else tfw)


tu.topup_dev = topup_dev_corrected
PREP = SLEW + 4 * EDGE            # 32 ps of gate preparation before the pulse

LK = threading.Lock()
ZC = os.path.join(HERE, "sk_zeros.json")
TZC = os.path.join(HERE, "sk_tu_zeros.json")


def _load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def _save(p, o):
    t = p + ".tmp"
    json.dump(o, open(t, "w"), indent=1)
    os.replace(t, p)


def _zeros(scheme, dv, T, mode, ltu, wsw, ton, tfw=None):
    key = "%s|%g|%g|%s|%g|%g|%g|%s" % (scheme, dv, T, mode, ltu, wsw, ton,
                                       "tfw" if tfw else "-")
    with LK:
        c = _load(ZC)
        if key in c:
            return c[key]
    # DEFECT FOUND BY ME, 2026-09-29: this used to pass {} for non-ptu modes, so an
    # rtu row's hop zeros were probed with tu.deck's DEFAULT t_on = 12 ps while the
    # reported row ran at t_on = 20 ps.  Hop 2's zero depends strongly on the clamp's
    # t_on (committed cache: t10 -> 100.783, t20 -> 101.016, t40 -> 101.449 ps), so
    # that is the SAME class of error as the A8 defect I am auditing: probing the
    # zeros in a configuration the row does not use.  t_on is now always passed.
    kw = dict(ltu_nh=ltu, wsw=wsw, t_on=ton, tfw=tfw) if mode.startswith("ptu") \
        else dict(t_on=ton)
    tag = "sz_%s_%s_T%g_dv%g_L%g_t%g%s" % (scheme, mode, T, dv * 1000, ltu, ton,
                                           "_f" if tfw else "")
    tz = tu.probe_zeros(scheme, T, 30.0, 15.0, dv, tag, mode=mode, **kw)
    if tz is None:
        return None
    with LK:
        c = _load(ZC); c[key] = tz; _save(ZC, c)
    return tz


def _tfw(scheme, dv, T, ltu, wsw, ton, tz):
    """A1: freewheel cut at the MEASURED zero, per bank.  The probe reports
    tfw_raw = z - (t_fire + t_on) because tu.py's ORIGINAL cell conducts from
    t_fire; the corrected cell's high side shuts off at b = t_fire + PREP + t_on,
    so tfw_true = tfw_raw - PREP.  Using tfw_raw unaltered would hold OUT closed
    PREP ps past the measured zero -- defect A1a, reintroduced by a convention
    mismatch between the probe and the cell."""
    key = "%s|%g|%g|%g|%g|%g" % (scheme, dv, T, ltu, wsw, ton)
    with LK:
        c = _load(TZC)
        if key in c:
            return {int(k): v for k, v in c[key].items()}
    tag = "stz_%s_T%g_dv%g_L%g_t%g" % (scheme, T, dv * 1000, ltu, ton)
    r = tu.probe_topup_zeros(scheme, T, 30.0, 15.0, dv, tag, tz, ltu, wsw, ton)
    if r is None:
        return None
    tfw, raw = {}, {}
    for k, v in r.items():
        rr = v["tfw"] if isinstance(v, dict) else v
        raw[str(k)] = rr
        tfw[int(k)] = max(0.0, rr - PREP)
    with LK:
        c = _load(TZC)
        c[key] = {str(k): v for k, v in tfw.items()}
        c[key + "|raw"] = raw
        c[key + "|prep_offset_ps"] = PREP
        _save(TZC, c)
    return tfw


def run_row(spec):
    scheme, mode, T, dv, ltu, ton = spec
    tag = "%s_%s_T%g_dv%g_L%g_t%g" % (scheme, mode, T, dv * 1000, ltu, ton)
    rec = dict(scheme=scheme, mode=mode, T_ps=T, dv=dv, ltu_nH=ltu, t_on_ps=ton,
               Cna_fF=CNA_FF, slew_ps=SLEW, tag=tag, L_nH=15.0, W_um=30.0,
               wsw_um=10.0, A8_fix="applied (sk_tu.py)" if mode.startswith("ptu")
               else "n/a")
    try:
        tfw = None
        if mode.startswith("ptu"):
            tz0 = _zeros(scheme, dv, T, "free", ltu, 10.0, ton)
            if tz0 is None:
                rec["error"] = "free bootstrap zero probe failed"; return rec
            tfw = _tfw(scheme, dv, T, ltu, 10.0, ton, tz0)
            if tfw is None:
                rec["error"] = "top-up ZCS probe failed"; return rec
            tz = _zeros(scheme, dv, T, mode, ltu, 10.0, ton, tfw=tfw)
        else:
            tz = _zeros(scheme, dv, T, mode, ltu, 10.0, ton)
        if tz is None:
            rec["error"] = "hop zero probe failed"; return rec
        rec["tz_ps"] = [round(z, 4) for z in tz]
        if tfw:
            rec["tfw_ps"] = {str(k): round(v, 4) for k, v in tfw.items()}
            rec["tfw_source"] = "MEASURED"
        kw = dict(ltu_nh=ltu, wsw=10.0, t_on=ton, tfw=tfw) \
            if mode.startswith("ptu") else dict(ltu_nh=ltu, wsw=10.0, t_on=ton)
        lines, S, fires = tu.deck(scheme, mode, T, 30.0, 15.0, dv, tz=tz, **kw)
        p, msg = tu.run("SR_%s.cir" % tag, lines)
        rec["run_msg"] = msg
        if p is None:
            rec["error"] = msg; return rec
        rec["deck"] = "SR_%s.cir" % tag
        rec["prn"] = "SR_%s.cir.prn" % tag
        rec["bound_ps"] = {str(k): S["bound"][k] for k in S["bound"]}
        rec["close_ps"] = S["close"]
        rec["open_ps"] = S["open"]
        rec["nbank"] = S["nbank"]
        rec["fires"] = {str(k): v for k, v in fires.items()}
        m = SK.parse_mt0(p + ".mt0")
        rec["mt0_keys"] = len(m)
        for h in (1, 2):
            if "IZ%d" % h in m:
                rec["A6_IZ%d_uA" % h] = m["IZ%d" % h] * 1e6
        izs = [abs(rec.get("A6_IZ%d_uA" % h, 0.0)) for h in (1, 2)]
        rec["A6_worst_IZ_uA"] = max(izs) if izs else None
        rec["A6_pass"] = bool(max(izs) < 1.0) if izs else None
        for k in ("QTU3_D", "QTU4_D", "QSUP_D", "QGABS_D", "EGTU_D",
                  "QRGA_D", "ERGT_D", "QDV_D"):
            if k in m:
                rec[k] = m[k]
    except Exception as e:
        rec["error"] = "%s: %s" % (type(e).__name__, e)
    return rec


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "triple"
    grids = {
        # THE MATCHED TRIPLE -- one operating point, three top-up forms.
        "triple": [("s4", "free", 200.0, 1.2, 1.0, 12.0),
                   ("s4", "rtu", 200.0, 1.2, 1.0, 20.0),
                   ("s4", "ptu", 200.0, 1.2, 1.0, 12.0),
                   ("s4", "ptu", 200.0, 1.2, 1.0, 24.0)],
        # clamp strength ladder, to show the coupling is monotone in its own strength
        "ladder": [("s4", "rtu", 200.0, 1.2, 1.0, 10.0),
                   ("s4", "rtu", 200.0, 1.2, 1.0, 40.0)],
    }
    specs = grids[which]
    out, op = [], os.path.join(HERE, "SK_ROWS_%s.json" % which)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for rec in ex.map(run_row, specs):
            out.append(rec)
            print("%-34s %s" % (rec["tag"], rec.get("error") or
                                "IZ=%s uA A6=%s" % (
                                    None if rec.get("A6_worst_IZ_uA") is None
                                    else round(rec["A6_worst_IZ_uA"], 3),
                                    rec.get("A6_pass"))), flush=True)
            _save(op, out)
    _save(op, out)
    print("wrote", op)


if __name__ == "__main__":
    main()
