#!/usr/bin/env python3
"""STEP 4b -- THE CORRECTED PULSED-INDUCTOR TOP-UP, AT CHAIN SCALE.

The 34 ptu decks in skiptu carry the top-up cell as tu.py's `topup_dev` built it
at 21:56-21:59.  That cell is missing BOTH fixes that the small fixture forced
between 22:05 and 22:09:

  1. NO SWITCH-NODE CAPACITANCE.  sg13lv_compat.sp zeroes ad/as/pd/ps, so na_k's
     only capacitance is gate overlap and its own gate drive moves it hundreds of
     mV (AMENDMENT A6: for a buck switch node this is FIRST-ORDER, and any number
     taken without it "is an artefact of the shim").  tu.py never emits a CNA --
     not even in its final 22:17 version.  tucell.py does.
  2. THE OLD GATE SEQUENCE.  tu.py uses simultaneous make-before-break (HS on and
     LS off in ONE 2 ps window).  The fixture measured that this yanks na to
     -0.42 V; tucell.py's corrected sequence turns the HS on EARLY, while the LS
     still clamps na at 0, then releases the LS SLOWLY (24 ps) so the already-on
     pMOS holds na up, and closes OUT LAST.

So the chain was never run with the corrected cell.  That is the gap this file
closes.  Everything else -- the 4-bank/5-bank skip schedule, the cells, the hops,
the boundary rule, the probe-then-cut protocol, the metering -- is skiptu's own
harness, imported and not modified.

`tu.HERE`/`tu.ENV` are rebound so nothing is written into qal/skiptu.
"""
import json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skiptu")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK
import tu
import tuextract as TX

CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_ptu"
tu.HERE = HERE
tu.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)

EDGE, VGH = SK.EDGE, SK.VGH

# ---- ASSUMED, and swept.  DERIVED central estimate ~8 fF (A6's own arithmetic:
# a w=10 um drain with ~0.3 um contacted extension is ~3 um^2, ~1 fF/um^2 -> ~3 fF
# per device, two devices ~6 fF, plus ~2 fF wiring).
CNA_FF = 8.0
SLEW = 24.0          # ps, low-side turn-off slew -- tucell.py's corrected value

_orig_topup_dev = tu.topup_dev


def topup_dev_corrected(k, ltu_nh, wsw, t_fire, t_on, vsup, tfw, big=None):
    """tucell.py's CORRECTED top-up cell, re-instanced per bank k.

    Sequence, all of it MEASURED-driven (see tucell.py's own comments):
        HS pMOS ON  at t_fire            (while the LS still clamps na at 0)
        LS nMOS OFF over SLEW ps, ending at a = t_fire + SLEW + 4*EDGE
        OUT switch CLOSES last, [a-EDGE, a]
        HS conducts to b = a + t_on, then HS off / LS on -> freewheel
        OUT OPENS at the MEASURED zero, z = b + tfw
    plus the CNA that AMENDMENT A6 makes mandatory.

    t_fire is tu.py's own `t_open + 6*EDGE`, so the WHOLE prepared sequence still
    begins after the charging hop's switch is open and its park is on (A1c).
    """
    e = EDGE
    a = t_fire + SLEW + 4 * e            # end of the LS release == pulse start
    b = a + t_on
    probe_form = tfw is None
    z = (big if probe_form else b + tfw)
    w = SK.widths(wsw * 1.5)
    L = [
        "CNA%d na%d 0 %gf" % (k, k, CNA_FF),      # <-- THE A6 FIX, never applied here before
        "XTUSW%d na%d gtu%d tsup tsup sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, wsw),
        "XTUFW%d na%d gfw%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, wsw),
        "LTU%d na%d ntm%d %gn" % (k, k, k, ltu_nh),
        "RTU%d ntm%d nb%d %g" % (k, k, k, tu.RSTU),
        "VMTU%d nb%d nbx%d 0" % (k, k, k),        # A5b: deliver-charge meter in the RAIL leg
        "XTUON%d nbx%d gto%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
        % (k, k, k, k, w["wn"]),
        "XTUOP%d nbx%d gtop%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
        % (k, k, k, k, w["wp"]),
        # HS pMOS: ON EARLY (gate low from t_fire), OFF at b
        "VGTU%d gtu%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
        % (k, k, VGH, t_fire, VGH, t_fire + 2 * e, b, b + e, VGH),
        # LS nMOS: clamps na at 0 until the HS is on, then releases SLOWLY over SLEW
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

# the pulse now starts SLEW + 4*EDGE after t_fire, so the top-up ZCS probe must
# search from there, not from t_fire.  tu.probe_topup_zeros uses fires[k]["t_fire"]
# as the search start; that is still EARLIER than the pulse, so the search window
# remains valid (it only has to start before the peak).

LK = threading.Lock()
ZC = os.path.join(HERE, "zeros.json")
TZC = os.path.join(HERE, "tu_zeros.json")


def _load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def _save(p, o):
    tmp = p + ".tmp"
    json.dump(o, open(tmp, "w"), indent=1)
    os.replace(tmp, p)


def _zeros_raw(scheme, dv, T, mode, ltu, wsw, ton, cna, tfw=None):
    key = "%s|%g|%g|%s|%g|%g|%g|%g|%s" % (scheme, dv, T, mode, ltu, wsw, ton, cna,
                                          "tfw" if tfw else "-")
    with LK:
        c = _load(ZC)
        if key in c:
            return c[key]
    kw = {}
    if mode.startswith("ptu"):
        kw = dict(ltu_nh=ltu, wsw=wsw, t_on=ton, tfw=tfw)
    tag = "z_%s_%s_T%g_dv%g_L%g_t%g_C%g%s" % (scheme, mode, T, dv * 1000, ltu,
                                              ton, cna, "_f" if tfw else "")
    tz = tu.probe_zeros(scheme, T, 30.0, 15.0, dv, tag, mode=mode, **kw)
    if tz is None:
        return None
    with LK:
        c = _load(ZC); c[key] = tz; _save(ZC, c)
    return tz


def _tfw_raw(scheme, dv, T, ltu, wsw, ton, cna, tz):
    """AMENDMENT A1: the top-up freewheel is cut at its MEASURED current zero,
    probed PER BANK (the banks sit at different rails)."""
    key = "%s|%g|%g|%g|%g|%g|%g" % (scheme, dv, T, ltu, wsw, ton, cna)
    with LK:
        c = _load(TZC)
        if key in c:
            return {int(k): v for k, v in c[key].items()}
    tag = "tz_%s_T%g_dv%g_L%g_t%g_C%g" % (scheme, T, dv * 1000, ltu, ton, cna)
    r = tu.probe_topup_zeros(scheme, T, 30.0, 15.0, dv, tag, tz, ltu, wsw, ton)
    if r is None:
        return None
    # OFFSET CORRECTION, and it is load-bearing.  tu.probe_topup_zeros returns
    #     tfw_raw = z_measured - (t_fire + t_on)
    # because tu.py's ORIGINAL cell starts conducting at t_fire.  The CORRECTED
    # cell does not: its high side turns on at t_fire but the pulse proper runs
    # [a, b] with a = t_fire + SLEW + 4*EDGE, so its high side shuts off at
    #     b = t_fire + SLEW + 4*EDGE + t_on
    # and the freewheel measured from the END OF THE PULSE is
    #     tfw_true = z_measured - b = tfw_raw - (SLEW + 4*EDGE).
    # Using tfw_raw unaltered would hold the OUT switch closed 32 ps past the
    # inductor's measured current zero -- which is precisely defect A1a (the
    # freewheel conducting past the true zero runs the path backwards and turns
    # the top-up into a net sink), reintroduced by an arithmetic mismatch between
    # the probe's convention and the cell's.
    PREP = SLEW + 4 * EDGE
    tfw = {}
    for k, v in r.items():
        raw = v["tfw"] if isinstance(v, dict) else v
        tfw[int(k)] = max(0.0, raw - PREP)
    with LK:
        c = _load(TZC)
        c[key + "|raw"] = {str(k): (v["tfw"] if isinstance(v, dict) else v)
                           for k, v in r.items()}
        c[key + "|prep_offset_ps"] = PREP
        _save(TZC, c)
    with LK:
        c = _load(TZC); c[key] = {str(k): v for k, v in tfw.items()}; _save(TZC, c)
    return tfw


def zeros_and_tfw(scheme, dv, T, mode, ltu, wsw, ton, cna):
    """A8, APPLIED TO THE ptu PATH -- which the committed harness never did.

    skiptu/go.py::one_row reads

        zmode = "rtu" if mode == "rtu" else "free"

    so a `ptu` row's HOP zeros are probed in FREE mode.  A8 was written about
    exactly this defect ("the top-up's transmission gates sit on the destination
    rail and their drain capacitance loads that rail EVEN WHILE THE GATES ARE OFF
    ... the top-up does not have to conduct to change the hop") and the fix was
    applied to `rtu` only.  The consequence is MEASURED and on disk: every
    committed ptu deck reads IZ1 = +122.4 uA and IZ2 = +110.7 to +120.2 uA of
    interrupted inductor current against the pre-registered 1.0 uA A6 gate, while
    the rtu rows are clean at 0.018 uA and the free rows at 0.0027 uA.

    Probing a ptu row's hops in ptu mode is chicken-and-egg: the hop-2 probe deck
    instantiates bank 3's top-up, which needs bank 3's MEASURED freewheel, which
    is found from a deck that needs the hop zeros.  So: BOOTSTRAP, and then check
    that it converged with the A6 gate on the final row.

        1. tz0 <- hop zeros probed in FREE mode          (bootstrap only)
        2. tfw <- top-up ZCS probed per bank using tz0   (A1)
        3. tz1 <- hop zeros RE-probed in ptu mode with the real tfw installed (A8)

    tz1 is what the reported row uses.  If the bootstrap had not converged, the
    row's own A6 interrupted-current gate would fail, and it is reported either way.
    """
    if not mode.startswith("ptu"):
        return _zeros_raw(scheme, dv, T, mode, ltu, wsw, ton, cna), None
    tz0 = _zeros_raw(scheme, dv, T, "free", ltu, wsw, ton, cna)
    if tz0 is None:
        return None, None
    tfw = _tfw_raw(scheme, dv, T, ltu, wsw, ton, cna, tz0)
    if tfw is None:
        return None, None
    tz1 = _zeros_raw(scheme, dv, T, mode, ltu, wsw, ton, cna, tfw=tfw)
    if tz1 is None:
        return None, None
    return tz1, tfw


def one_row(spec):
    try:
        return _one_row(spec)
    except Exception as e:
        scheme, mode, T, dv, ltu, ton = spec
        return dict(scheme=scheme, mode=mode, T_ps=T, dv=dv, ltu_nH=ltu,
                    t_on_ps=ton, Cna_fF=CNA_FF,
                    tag="%s_%s_T%g_dv%g_L%g_t%g" % (scheme, mode, T, dv * 1000,
                                                    ltu, ton),
                    error="%s: %s" % (type(e).__name__, e))


def _one_row(spec):
    scheme, mode, T, dv, ltu, ton = spec
    cna = CNA_FF
    tag = "%s_%s_T%g_dv%g_L%g_t%g_C%g" % (scheme, mode, T, dv * 1000, ltu, ton, cna)
    rec = dict(scheme=scheme, mode=mode, T_ps=T, dv=dv, ltu_nH=ltu, t_on_ps=ton,
               Cna_fF=cna, slew_ps=SLEW, tag=tag, L_nH=15.0, W_um=30.0, wsw_um=10.0)
    tz, tfw = zeros_and_tfw(scheme, dv, T, mode, ltu, 10.0, ton, cna)
    if tz is None:
        rec["error"] = ("hop-zero probe or top-up ZCS probe failed "
                        "(reported, not hidden)")
        return rec
    rec["tz_ps"] = [round(z, 3) for z in tz]
    rec["hop_zero_mode"] = ("ptu (A8 applied to the ptu path, which the committed "
                            "harness does not do)" if mode.startswith("ptu") else mode)
    if tfw is not None:
        rec["tfw_ps"] = {str(k): round(v, 4) for k, v in tfw.items()}
        rec["tfw_source"] = "MEASURED"
    kw = dict(ltu_nh=ltu, wsw=10.0, t_on=ton, tfw=tfw) if mode.startswith("ptu") \
        else dict(ltu_nh=ltu, wsw=10.0, t_on=ton)
    lines, S, fires = tu.deck(scheme, mode, T, 30.0, 15.0, dv, tz=tz, **kw)
    p, msg = tu.run("R_%s.cir" % tag, lines)
    rec["run_msg"] = msg
    if p is None:
        rec["error"] = msg; return rec
    m = SK.parse_mt0(p + ".mt0")
    rec.update(TX.row(scheme, mode, T, dv, m, S, fires, 15.0, 30.0, ltu, 10.0,
                      ton, 0.0, tz))
    rec["deck"] = "R_%s.cir" % tag
    return rec


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "core"
    grids = {
        # the operating points the CLAMP rows were reported at
        "core": [("s4", "ptu", T, 1.2, 1.0, 12.0) for T in (120., 160., 200., 300.)]
                + [("s4", "ptu", 200., dv, 1.0, 12.0) for dv in (1.0, 1.5)],
        "str":  [("s4", "ptu", 200., 1.2, L, t)
                 for L in (1.0, 5.0, 15.0) for t in (6.0, 12.0, 24.0)],
        "s5":   [("s5", "ptu", T, 1.2, 1.0, 12.0) for T in (200., 300.)],
        # THE FIXTURE-SELECTED POINT.  FIXTURE.json measures Ltu = 1 nH, t_on = 24 ps
        # at the DERIVED Cna = 8 fF as the ONLY setting in a 27-point sweep that
        # delivers POSITIVE charge into the bank (+0.93 fC, bank 0.765884 ->
        # 0.787285 V).  Every other point is still a net sink.  So the chain is
        # given its best available shot at exactly that point, not at a setting
        # the small fixture already says cannot work.
        "best": [("s4", "ptu", T, 1.2, 1.0, 24.0) for T in (120., 160., 200., 300.)]
                + [("s4", "ptu", 200., dv, 1.0, 24.0) for dv in (1.0, 1.5)]
                + [("s5", "ptu", T, 1.2, 1.0, 24.0) for T in (200., 300.)],
    }
    specs = grids[which]
    out = []
    op = os.path.join(HERE, "ROWS_%s.json" % which)
    with ThreadPoolExecutor(max_workers=3) as ex:
        for rec in ex.map(one_row, specs):
            out.append(rec)
            print("%-44s %s" % (rec["tag"], rec.get("error") or
                                "worst/stage %s | rail %s" %
                                (rec.get("worst_gate_by_stage_pct"),
                                 rec.get("rail_by_stage_at_its_boundary_V"))),
                  flush=True)
            json.dump(out, open(op, "w"), indent=1)
    json.dump(out, open(op, "w"), indent=1)
    print("wrote", op)


if __name__ == "__main__":
    main()
