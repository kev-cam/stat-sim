#!/usr/bin/env python3
"""Geometry warm-up for MY OWN PyMS vae cache.

Each distinct (model card, W, L) bakes its own vae .so (~7 min to build here), so
the cache must be warmed BEFORE any timed deck runs, and the record's own gotcha
applies: launching N Xyce concurrently on the SAME geometry races the .so build.
Different geometries have different hashes, so they are safe to build in parallel;
the limit here is RAM (cc1plus peaks ~1.5 GB), hence MAXPAR.

DELVTO is a CALLBACK param (PYMS_CALLBACK_PARAMS=DELVTO), so it is kept symbolic
in the .so and does NOT fork the cache -- one .so per geometry serves the whole
sweep.  Verified on disk: the .so.params file carries DELVTO=0 (placeholder) and
__CALLBACK__=DELVTO.
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
VA = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM = os.path.join(HERE, "shim_dvt.sp")
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_vtreq")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
           PYMS_VAE_CACHE=CACHE, PYMS_CALLBACK_PARAMS="DELVTO")
MAXPAR = 3

# (kind, W um) -> every geometry any deck in this study instantiates
GEOMS = [
    ("n", 0.74),    # cell nMOS                      (all decks)
    ("p", 1.12),    # cell pMOS                      (all decks)
    ("n", 10.0),    # transfer-gate nMOS  W_tot=30   (hop decks)
    ("p", 20.0),    # transfer-gate pMOS  W_tot=30   (hop decks)
    ("n", 2.0),     # park nMOS           W_tot=30   (hop decks)
    ("n", 1.48),    # restoring-stage skewed nMOS    (restore5 chain)
    ("p", 0.15),    # restoring-stage skewed pMOS    (restore5 chain)
    ("n", 1.0),     # head pre-charge nMOS           (restore5 chain)
]


def deck(kind, w):
    sub = "sg13_lv_nmos" if kind == "n" else "sg13_lv_pmos"
    if kind == "n":
        body = ["VD d 0 0.1", "VG g 0 1.0",
                "X1 d g 0 0 %s w=%gu l=0.13u" % (sub, w)]
    else:
        body = ["VS s 0 1.2", "VD d 0 1.1", "VG g 0 0.2",
                "X1 d g s s %s w=%gu l=0.13u" % (sub, w)]
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            ".param DVTN=0 DVTP=0"] + body + [".op", ".print dc V(d)", ".end"]


def run(kind, w):
    tag = "warm_%s%s" % (kind, str(w).replace(".", "p"))
    fn = os.path.join(HERE, tag + ".cir")
    open(fn, "w").write("\n".join(deck(kind, w)) + "\n")
    t = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, cwd=HERE,
                       env=ENV, timeout=3600)
    return tag, time.monotonic() - t, r.returncode


if __name__ == "__main__":
    todo = list(GEOMS)
    running = []
    done = []
    while todo or running:
        while todo and len(running) < MAXPAR:
            kind, w = todo.pop(0)
            tag = "warm_%s%s" % (kind, str(w).replace(".", "p"))
            fn = os.path.join(HERE, tag + ".cir")
            open(fn, "w").write("\n".join(deck(kind, w)) + "\n")
            p = subprocess.Popen([XYCE, fn], stdout=open(os.path.join(HERE, tag + ".log"), "w"),
                                 stderr=subprocess.STDOUT, cwd=HERE, env=ENV)
            running.append((tag, p, time.monotonic()))
            print("launch", tag, flush=True)
        time.sleep(5)
        still = []
        for tag, p, t0 in running:
            if p.poll() is None:
                still.append((tag, p, t0))
            else:
                print("done  %-14s rc=%d  %.0fs" % (tag, p.returncode,
                                                    time.monotonic() - t0), flush=True)
                done.append(tag)
        running = still
    print("ALL WARM", len(done), flush=True)
