#!/usr/bin/env python3
"""Transplant a top-up gate schedule into the COMMITTED chain deck.

The deck is a byte-identical copy of qal/ptusk/SR_s4_ptu_T200_dv1200_L1_t12.cir.
The ONLY lines this file rewrites are the eight top-up gate PWLs (VGTU/VGFW/
VGTO/VGTOP for banks 3 and 4).  Nothing else -- not the cells, not the hops, not
the hop-switch timings, not one .measure point -- is touched, so a difference
between the committed row and a fixed row is attributable to the gate schedule
and to nothing else.
"""
import os, re, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_buckfix")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
BASE = os.path.join(HERE, "IC_SR_s4_ptu_T200_dv1200_L1_t12.cir")
VGH, E = 1.5, 2.0

# MEASURED off the committed deck (both banks), recorded here so the transplant
# reuses the committed t_fire and t_on exactly.
COMMITTED = {3: dict(t_fire=313.137, a=345.137, b=357.137, z=363.355),
             4: dict(t_fire=510.096, a=542.096, b=554.096, z=560.495)}
T_ON = 12.0


def pwl(pairs):
    return "PWL(" + " ".join("%g %g" % (t, v) if t == 0 else "%gp %g" % (t, v)
                             for t, v in pairs) + ")"


def gate_block(k, s):
    """s: dict(hs=(t0,t1,t2,t3), fw=(...)|None, out_close=(o0,o1), out_open=z|None)"""
    h0, h1, h2, h3 = s["hs"]
    o0, o1 = s["out_close"]
    z = s["out_open"]
    L = {"VGTU%d" % k: "VGTU%d gtu%d 0 %s" % (k, k, pwl([(0, VGH), (h0, VGH), (h1, 0), (h2, 0), (h3, VGH)]))}
    if s["fw"] is None:
        L["VGFW%d" % k] = "VGFW%d gfw%d 0 %s" % (k, k, pwl([(0, 0), (4400, 0)]))
    else:
        f0, f1, f2, f3 = s["fw"]
        L["VGFW%d" % k] = "VGFW%d gfw%d 0 %s" % (k, k, pwl([(0, VGH), (f0, VGH), (f1, 0), (f2, 0), (f3, VGH)]))
    if z is None:
        L["VGTO%d" % k] = "VGTO%d gto%d 0 %s" % (k, k, pwl([(0, 0), (o0, 0), (o1, VGH), (4400, VGH)]))
        L["VGTOP%d" % k] = "VGTOP%d gtop%d 0 %s" % (k, k, pwl([(0, VGH), (o0, VGH), (o1, 0), (4400, 0)]))
    else:
        L["VGTO%d" % k] = "VGTO%d gto%d 0 %s" % (k, k, pwl([(0, 0), (o0, 0), (o1, VGH), (z, VGH), (z + E, 0)]))
        L["VGTOP%d" % k] = "VGTOP%d gtop%d 0 %s" % (k, k, pwl([(0, VGH), (o0, VGH), (o1, 0), (z, 0), (z + E, VGH)]))
    return L


# ------------------------------------------------------------------ schedules
def sch_C1(k, t_on=T_ON, z=None):
    """The committed schedule, reconstructed."""
    c = COMMITTED[k]
    tf, a = c["t_fire"], c["a"]
    b = a + t_on
    return dict(hs=(tf, tf + 2 * E, b, b + E),
                fw=(a - 24.0, a, b, b + E),
                out_close=(a - E, a),
                out_open=(c["z"] if z is None else z))


def sch_C2(k, t_on=T_ON, z=None):
    """C2: break-before-make at TURN-ON.  Only the FW turn-off moves."""
    s = sch_C1(k, t_on, z)
    tf = COMMITTED[k]["t_fire"]
    b = s["hs"][2]
    s["fw"] = (tf - 2 * E, tf - E, b, b + E)
    return s


def sch_C3(k, t_on=T_ON, z=None):
    """C3 = C2 + a 2 ps dead time at TURN-OFF (HS fully off before FW turns on)."""
    s = sch_C2(k, t_on, z)
    b = s["hs"][2]
    s["fw"] = (s["fw"][0], s["fw"][1], b + 2 * E, b + 3 * E)
    return s


def sch_C4(k, t_on=T_ON, z=None):
    """C4 = C3 + the OUT switch spanning the WHOLE conduction and freewheel,
    and the 32 ps of dead preparation removed: the pulse starts at t_fire."""
    c = COMMITTED[k]
    tf = c["t_fire"]
    hs0, hs1 = tf, tf + E
    b = hs1 + t_on
    return dict(hs=(hs0, hs1, b, b + E),
                fw=(tf - 3 * E, tf - 2 * E, b + 2 * E, b + 3 * E),
                out_close=(tf - 2 * E, tf - E),
                out_open=z)


def sch_C9(k, t_on=45.0, z=None, settle=4.0, fire_lead=8.0):
    """C9 on the chain -- the DIODE-FREEWHEEL buck the fixture selected.

    Differences from the committed cell, all of them in the gate schedule except
    the inductor value, which is stated separately and changed explicitly:
      * the freewheel nMOS gate is held at 0 for the whole run (its drain-bulk
        junction does the freewheeling), which deletes BOTH of its 1.5 V gate
        transitions -- MEASURED on the fixture as the dominant loss,
      * the high-side turns on FIRST and is given `settle` ps to charge the
        switch node to tsup BEFORE the OUT switch closes,
      * the OUT switch closes at t_fire and opens at the RE-PROBED inductor zero.
    `fire_lead` pulls the whole sequence earlier so the delivery can complete
    inside the stage boundary."""
    c = COMMITTED[k]
    tf = c["t_fire"] - fire_lead
    e = E
    hs0 = tf - settle - 2 * e
    b = tf + t_on
    return dict(hs=(hs0, hs0 + e, b, b + e),
                fw=None,                       # gate pinned at 0 -- diode freewheel
                out_close=(tf - e, tf),
                out_open=z)


SCHEDS = {"C1": sch_C1, "C2": sch_C2, "C3": sch_C3, "C4": sch_C4, "C9": sch_C9}


def build(name, t_on=T_ON, zeros=None, probe=False, banks=(3, 4), ltu_nh=None):
    """zeros: {k: t_out_open_ps} or None.  probe=True -> OUT never opens.
    ltu_nh: if given, ALSO rewrite the LTU_k inductor value (declared change)."""
    src = open(BASE).read().splitlines()
    fn = SCHEDS[name]
    repl = {}
    for k in banks:
        z = None if probe else (zeros or {}).get(k)
        if not probe and z is None:
            z = sch_C1(k, t_on)["out_open"]      # fall back to the committed cut
        repl.update(gate_block(k, fn(k, t_on, z)))
    out, hits = [], set()
    for line in src:
        m = re.match(r"^(VG(?:TU|FW|TO|TOP)\d)\s", line)
        if m and m.group(1) in repl:
            out.append(repl[m.group(1)]); hits.add(m.group(1))
            continue
        m2 = re.match(r"^(LTU(\d))\s+(\S+)\s+(\S+)\s+\S+\s*$", line)
        if ltu_nh is not None and m2 and int(m2.group(2)) in banks:
            out.append("%s %s %s %gn" % (m2.group(1), m2.group(3), m2.group(4), ltu_nh))
            hits.add(m2.group(1))
            continue
        out.append(line)
    missing = set(repl) - hits
    if missing:
        raise RuntimeError("gate lines not found in base deck: %s" % sorted(missing))
    return out, sorted(hits)


def run(fn, lines, timeout=900):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT %gs" % timeout
    w = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(p + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs) %s" % (fn, w, err or r.stdout[-300:])
    return p, "ran %s in %.1fs" % (fn, w)
