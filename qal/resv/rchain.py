#!/usr/bin/env python3
"""TRACK A (d) -- THE 6-BANK RESERVOIR CHAIN.

Thin wrapper over qal/restore5/rest.py.  Cells, transfer switch, series R,
.OPTIONS, gate phases, park, head pre-charge, the TRUE-ZCS probe-then-cut
protocol, the 1F integrators, the +1.0 ps FIND lag and the stage-boundary
convention are that file VERBATIM.  The separation extractor is
qal/vtaudit/reext.py's, verbatim in form (min pull-UP minus max pull-DOWN at the
bank's own stage boundary, o_0/o_1 class representatives).

WHAT IS NEW -- exactly three monkeypatches, all pre-registered:

  1. rest.src_node(k, j) -> "res1" for EVERY bank.  In the committed chain only
     bank 1 is fed from the reservoir; banks 2..6 are fed PEER-TO-PEER from their
     predecessor's already-depleted rail, which is what makes the loss COMPOUND
     (0.611-0.659 per hop) and collapses the separation
     528.68 / -22.89 / 1.52 / -0.122 / 0.010 / -0.001 mV.  With a shared tank every
     bank is DEPTH-1 in rail.  The DATA path is untouched: bank j's cells are still
     driven by o{j-1}, same net, no buffer of any kind.
  2. rest.has_srccut(k, j) -> True for EVERY hop.  Committed AMENDMENT A3 omits the
     source-side cut on a reservoir hop because there was only ONE reservoir hop in
     the whole deck.  Here all six hops hang off one tank, so five idle inductors
     would sit permanently across it -- the exact pathology A3 was written for
     (MEASURED 42.3% of a hop's charge diverted into ONE idle inductor, and an idle
     ring with tau = 2L/R = 55.6 ns that never damps).  Pre-registered as E6.
  3. rest.CA_FF -> CA_MULT * 35.979 fF, the tank size.

k = 6 gives ONE segment, so restore_into is empty and there is NO restoring stage
inside the chain -- the unbuffered case, identical in that respect to the committed
k6_T300_control.  trailing_restore is left ON so bank 6 carries the same output load
it carries in the control.

usage: rchain.py ctl                 -- reproduce the committed peer chain (control)
       rchain.py res <CA_MULT>       -- the reservoir chain
"""
import json, math, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/restore5")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/vtaudit")
import rest                                                          # noqa: E402
import aud                                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_resv")
rest.HERE = HERE
rest.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                PYMS_VAE_CACHE=CACHE)

K, T, TRES = 6, 300.0, 0.0
CB_FF = 35.979
ROWD = os.path.join(HERE, "chaind")

_src_peer = rest.src_node
_cut_peer = rest.has_srccut


_sched = rest.schedule


def patch_window(t_est_ps):
    """rest.schedule hard-codes t_est = TZ_ANCHOR * CHAIN_F = 88.42 ps, the PEER
    hop's own duration, and rest.deck sizes a probe run as close + 1.8 * t_est.
    A tank-fed hop is LONGER (C_ser rises from C_bank/2 toward C_bank), so that
    window cuts the probe off before the current zero -- MEASURED: my first
    CA_MULT = 100 probe ran to 359.2 ps with I(L1) still at +64.8 uA and falling,
    and rest reported 'NO ZERO'.  The window is widened; mstep is pinned back to the
    COMMITTED value so the widening cannot buy resolution it did not earn."""
    def sched(k, T, tres, nbank=rest.NBANK):
        S = _sched(k, T, tres, nbank)
        S["t_est"] = t_est_ps
        S["mstep"] = min(0.25, rest.TZ_ANCHOR * rest.CHAIN_F / 1000.0)
        S["pstep"] = 0.1
        return S
    rest.schedule = sched


def patch_reservoir(ca_mult):
    rest.CA_FF = ca_mult * CB_FF
    rest.src_node = lambda k, j: "res1"
    rest.has_srccut = lambda k, j: True
    patch_window(320.0)


def patch_peer():
    rest.CA_FF = CB_FF
    rest.src_node = _src_peer
    rest.has_srccut = _cut_peer


def separation(prn, S, nbank=6):
    """qal/vtaudit/reext.py verbatim in form."""
    w = aud.Wv(prn)
    sep, rails, outs, peak = {}, {}, {}, {}
    for j in range(1, nbank + 1):
        tb = S["bound"][j]
        rails[j] = w.at("V(rail%d)" % j, tb)
        v = {i: w.at("V(o%d_%d)" % (j, i), tb) for i in (0, 1)}
        outs[j] = v
        up = [x for i, x in v.items() if not rest.is_hi(j, i)]
        dn = [x for i, x in v.items() if rest.is_hi(j, i)]
        sep[j] = 1e3 * (min(up) - max(dn))
        peak[j] = max(w.c("V(rail%d)" % j))
    return sep, rails, outs, peak


def tank_trace(prn, S, nbank=6):
    w = aud.Wv(prn)
    tr = {}
    try:
        for j in range(1, nbank + 1):
            tr["at_bound%d" % j] = w.at("V(res1)", S["bound"][j])
        tr["start"] = w.at("V(res1)", 0.5)
        tr["end"] = w.c("V(res1)")[-1]
        tr["min"] = min(w.c("V(res1)"))
    except KeyError:
        pass
    return tr


def go(mode, ca_mult=1.0):
    tag = "ctl" if mode == "ctl" else "res%g" % ca_mult
    # Each configuration gets its OWN working directory.  rest.do_probe names its
    # decks p{h}_k{k}_T{T}.cir with no configuration in the name, so two configs run
    # from the same directory COLLIDE on both the deck and its .prn -- and its
    # "byte-identical deck already run" cache check would then silently reuse the
    # wrong waveform.  Caught before either run finished; both were killed by PID and
    # restarted under this fix.
    rest.HERE = os.path.join(HERE, "ch_" + tag)
    os.makedirs(rest.HERE, exist_ok=True)
    if mode == "ctl":
        patch_peer()
    else:
        patch_reservoir(ca_mult)
    t0 = time.monotonic()
    print("== %s : probing the six hop zeros (one-segment deck) ==" % tag, flush=True)
    tz = rest.do_probe(K, T, TRES)
    if tz is None:
        print("PROBE FAILED"); return
    print("  zeros:", [round(z, 4) for z in tz], flush=True)
    lines, S = rest.deck(K, T, TRES, nbank=rest.NBANK, tz=tz)
    fn = "c_%s.cir" % tag
    p, msg = rest.run(fn, lines, timeout=3000)
    print("  row", msg, flush=True)
    if p is None:
        return
    sep, rails, outs, peak = separation(p + ".prn", S)
    r = dict(tag=tag, mode=mode, ca_mult=ca_mult, ca_fF=rest.CA_FF,
             K=K, T=T, tres=TRES, tz_ps=tz,
             separation_mV=sep, rail_at_own_boundary_V=rails,
             rail_peak_V=peak, outputs_at_own_boundary_V=outs,
             bound_ps=S["bound"], close_ps=S["close"], open_ps=S["open"],
             tank=tank_trace(p + ".prn", S),
             extractor="waveform, o_0/o_1 class representatives (vtaudit/reext.py form)",
             prn=p + ".prn", wall_s=round(time.monotonic() - t0, 1))
    os.makedirs(ROWD, exist_ok=True)
    json.dump(r, open(os.path.join(ROWD, "%s.json" % tag), "w"), indent=1)
    print("%-8s sep  %s" % (tag, " ".join("%+12.4f" % sep[j] for j in range(1, 7))),
          flush=True)
    print("%-8s rail %s" % ("", " ".join("%12.5f" % rails[j] for j in range(1, 7))),
          flush=True)
    print("%-8s peak %s" % ("", " ".join("%12.5f" % peak[j] for j in range(1, 7))),
          flush=True)
    print("%-8s tank %s" % ("", json.dumps({k: round(v, 5)
                                            for k, v in r["tank"].items()})), flush=True)
    return r


if __name__ == "__main__":
    if sys.argv[1] == "ctl":
        go("ctl")
    else:
        go("res", float(sys.argv[2]))
