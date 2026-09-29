#!/usr/bin/env python3
"""STEP 4a -- THE SMALL FIXTURE FIRST, as the standing directive requires, and as
AMENDMENT A6 says should have been done before debugging inside the chain.

skiptu's A7 swept the switch-node capacitance only up to the DERIVED 8 fF and
stopped, concluding NOT DEMONSTRATED.  The trend in its own table is monotone
toward zero FROM BELOW as Cna rises:

    Cna = 2 fF, Ltu = 1 nH, t_on = 6 ps  ->  q_delivered = -15.735 fC
    Cna = 8 fF, Ltu = 1 nH, t_on = 6 ps  ->  q_delivered =  -2.560 fC
    Cna = 8 fF, Ltu = 1 nH, t_on = 12 ps ->  q_delivered =  -1.203 fC

so the obvious question A7 did not ask is whether it CROSSES zero at a larger
switch-node capacitance, and whether it ever reaches the Qmult > 1 that buck
action requires.  That is what this sweeps.

Fixture and corrected gate sequence reused VERBATIM by import from
skiptu/tucell.py (HS on early, LS off slewed, OUT closes last, delivered charge
metered at a 0 V series source in the bank leg).  tucell.py is NOT modified and
NOT written to; only its HERE and ENV are rebound so every artefact lands in
qal/ptu under MY OWN cache.

V0 is set to the CHAIN's actual measured free rail3 at its boundary, 0.765884 V,
not to tucell's round 0.700 V, so the fixture is asked the chain's own question.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skiptu")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK
import tucell as TC

CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_ptu"
TC.HERE = HERE
TC.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)

# The VAE cache had to be built from scratch here (own PYMS_VAE_CACHE, nothing
# copied in), and the first decks on a cold cache exceed tucell.run's 600 s
# timeout while a .so compiles.  So: longer timeout, per-point fault isolation,
# and reuse of any .mt0 already on disk.  None of this changes a circuit.
_TCrun = TC.run


def _run(tag, lines):
    fn = os.path.join(HERE, "tc_%s.cir" % tag)
    if os.path.exists(fn + ".mt0") and os.path.exists(fn + ".prn"):
        old = open(fn).read() if os.path.exists(fn) else ""
        if old.strip() == "\n".join(lines).strip():
            return SK.parse_mt0(fn + ".mt0"), fn       # already measured, reuse
    open(fn, "w").write("\n".join(lines) + "\n")
    import subprocess
    try:
        r = subprocess.run([TC.XYCE, fn], capture_output=True, text=True,
                           timeout=1800, cwd=HERE, env=TC.ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT 1800s"
    if not os.path.exists(fn + ".mt0"):
        return None, "; ".join(l for l in r.stdout.splitlines()
                               if "rror" in l or "bort" in l)[:300]
    return SK.parse_mt0(fn + ".mt0"), fn


TC.run = _run

V0 = 0.765884       # MEASURED: the free chain's rail3 at its own boundary
VSUP = 1.2          # dV
SLEW = 24.0         # tucell's corrected low-side turn-off slew


def one(spec):
    try:
        return _one(spec)
    except Exception as e:
        cna, ltu, ton = spec
        return {"Cna_fF": cna, "Ltu_nH": ltu, "ton_ps": ton,
                "error": "%s: %s" % (type(e).__name__, e)}


def _one(spec):
    cna, ltu, ton = spec
    tag = "C%g_L%g_t%g" % (cna, ltu, ton)
    rec = {"Cna_fF": cna, "Ltu_nH": ltu, "ton_ps": ton, "V0": V0, "Vsup": VSUP,
           "C_bank_fF": TC.C_BANK, "slew_ps": SLEW}
    # pass 1: PROBE -- freewheel never opens, find I(LTU)'s own measured zero
    lines, tend = TC.deck(ltu, 10.0, ton, V0, VSUP, tfw=None, tag="p_" + tag,
                          cna=cna, slew=SLEW)
    m, fn = TC.run("p_" + tag, lines)
    if m is None:
        rec["error"] = "probe failed: %s" % fn
        return rec
    a = TC.T0
    z = TC.zero_of(fn, a + ton, tend - 5)
    if z is None:
        rec["tfw_source"] = "NO ZCS FOUND"
        rec["error"] = "no current zero anywhere after the pulse"
        return rec
    tfw = z - (a + ton)
    rec["tfw_measured_ps"] = round(tfw, 4)
    rec["tfw_source"] = "MEASURED"
    if tfw <= 0:
        rec["error"] = "measured zero precedes the end of the on-time"
        return rec
    # pass 2: the real deck, cut at the MEASURED zero
    lines, tend = TC.deck(ltu, 10.0, ton, V0, VSUP, tfw=tfw, tag="r_" + tag,
                          cna=cna, slew=SLEW)
    m, fn = TC.run("r_" + tag, lines)
    if m is None:
        rec["error"] = "row failed: %s" % fn
        return rec
    ig = lambda t: (m["%s_D" % t] - m["%s_Z" % t]) if ("%s_D" % t) in m else None
    qd, qs, qi, qg = ig("QDEL"), ig("QSUP"), ig("QIND"), ig("QGAB")
    rec.update(
        q_delivered_fC=round(qd * 1e15, 4) if qd is not None else None,
        q_supply_fC=round(qs * 1e15, 4) if qs is not None else None,
        q_inductor_fC=round(qi * 1e15, 4) if qi is not None else None,
        Q_gate_fC=round(qg * 1e15, 4) if qg is not None else None,
        V_before=round(m.get("VB0", float("nan")), 6),
        V_after=round(m.get("VBF", float("nan")), 6),
        V_max=round(m.get("VBMX", float("nan")), 6),
        Ipk_uA=round(m.get("IPK", 0) * 1e6, 2),
        Imin_uA=round(m.get("IMN", 0) * 1e6, 2))
    if qd is not None and qs not in (None, 0):
        rec["charge_mult"] = round(qd / qs, 5)
    if rec["V_before"] == rec["V_before"]:
        rec["dV_mV"] = round(1e3 * (rec["V_after"] - rec["V_before"]), 3)
        rec["bank_ROSE"] = bool(rec["V_after"] > rec["V_before"])
    return rec


def main():
    grid = [(c, l, t) for c in (8.0, 20.0, 50.0)
            for l in (1.0, 5.0, 15.0) for t in (6.0, 12.0, 24.0)]
    out = {"_doc": __doc__.strip(), "V0_MEASURED_from": "free chain rail3 at its "
           "boundary, r_s4_free_T200_dv1200 = 0.765884 V",
           "_acceptance": "buck action requires charge_mult > 1; the minimum the "
                          "chain needs is merely q_delivered > 0 with the bank rising.",
           "rows": []}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for rec in ex.map(one, grid):
            out["rows"].append(rec)
            print("Cna%-5g Ltu%-5g ton%-4g | tfw %-9s q_del %-11s q_sup %-10s "
                  "Qmult %-9s V %s->%s" %
                  (rec["Cna_fF"], rec["Ltu_nH"], rec["ton_ps"],
                   rec.get("tfw_measured_ps", rec.get("tfw_source", "-")),
                   rec.get("q_delivered_fC", rec.get("error", "-")),
                   rec.get("q_supply_fC", "-"), rec.get("charge_mult", "-"),
                   rec.get("V_before", "-"), rec.get("V_after", "-")), flush=True)
            json.dump(out, open(os.path.join(HERE, "FIXTURE.json"), "w"), indent=1)
    pos = [r for r in out["rows"] if (r.get("q_delivered_fC") or -1) > 0]
    out["n_positive_delivery"] = len(pos)
    out["n_buck_action"] = len([r for r in out["rows"]
                                if (r.get("charge_mult") or -1) > 1])
    out["VERDICT"] = ("POSITIVE DELIVERY FOUND at %d of %d points"
                      % (len(pos), len(out["rows"])) if pos else
                      "NO POSITIVE DELIVERY ANYWHERE in the swept grid")
    json.dump(out, open(os.path.join(HERE, "FIXTURE.json"), "w"), indent=1)
    print("\n", out["VERDICT"], "| buck action (Qmult>1) at",
          out["n_buck_action"], "points")


if __name__ == "__main__":
    main()
