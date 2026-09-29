#!/usr/bin/env python3
"""Generate + run the fixture sweep: PROPERLY TIMED SYNCHRONOUS BUCK vs L,
with the prior agent's no-freewheel form as the control."""
import os, sys, json, subprocess, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mkfix import deck

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ)
ENV["PYMS_DIR"] = "/usr/local/share/xyce/PyMS"
ENV["PYMS_VAE_CACHE"] = os.path.join(HERE, "vae_cache_skep")
XYCE = "/usr/local/src/xyce-build/src/Xyce"

def run_batch(jobs, npar=4):
    """jobs: list of dicts with 'path'. Runs at most npar at a time."""
    pending = list(jobs)
    live = []
    done = []
    while pending or live:
        while pending and len(live) < npar:
            j = pending.pop(0)
            lg = j["path"].replace(".cir", ".log")
            p = subprocess.Popen([XYCE, os.path.basename(j["path"])],
                                 cwd=HERE, env=ENV,
                                 stdout=open(lg, "w"), stderr=subprocess.STDOUT)
            j["proc"] = p
            live.append(j)
        for j in list(live):
            rc = j["proc"].poll()
            if rc is not None:
                j["rc"] = rc
                del j["proc"]
                live.remove(j)
                done.append(j)
                print("done", os.path.basename(j["path"]), "rc=", rc, flush=True)
        if live:
            import time; time.sleep(2)
    return done

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "L"
    jobs = []
    if which == "L":
        CB = 30e-15
        for L in [1e-9, 3e-9, 10e-9, 30e-9, 100e-9, 300e-9]:
            for mode in ["buck", "nofw"]:
                tag = "F_%s_L%g_T35_CB30" % (mode, L * 1e9)
                p = os.path.join(HERE, tag + ".cir")
                j = deck(p, L=L, TON=35.0, W=10.0, CB=CB, mode=mode, tend=600.0)
                j["tag"] = tag
                jobs.append(j)
    meta = {}
    for j in jobs:
        meta[j["tag"]] = {k: v for k, v in j.items() if k != "proc"}
    json.dump(meta, open(os.path.join(HERE, "FIXMETA_%s.json" % which), "w"), indent=1)
    run_batch(jobs, npar=4)
    print("ALL DONE")
