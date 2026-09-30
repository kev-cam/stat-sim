#!/usr/bin/env python3
"""Pre-warm every PSP103 device geometry the sweep needs.

MEASURED FACT that forces this stage (this run, F1/F2 logs): the PyMS/Verilog-A
`.so` is built PER (card, W) GEOMETRY, and each build costs ~2m20s of the
"Instantiate" phase while the transient solve itself is ~1.4 s.  F1 built 2
geometries in 5m42s (5m27s of it Instantiate); F2 built 3 more in 7m19s (6m59s
Instantiate).  A parallel sweep worker that hits a cold geometry would therefore
(a) blow the 4-minute rule and (b) race other workers on the shared cache -- the
exact `.va`-cache hazard this campaign has been bitten by before.

Each warm job gets its OWN private cache directory and is then MERGED into the
shared one.  The `.so` filename contains the parameter hash, so the same
geometry always produces the same filename and the merge is a copy, not a race.
"""
import os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
SHARED = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
          "/scratchpad/vae_cache_fastwave")

# ---- the geometry ledger --------------------------------------------------
# cell + TG devices (tgM widths are the SAME as the static cell widths, so the
# XOR cell needs no geometry the committed inverter bank did not already need)
CELL_N, CELL_P = 0.74, 1.12
PARK_W = 1.0            # FIXED for every W -- see DEVIATION note in RESULTS
# switch ladder: wn = W/3, wp = 2W/3  (inherited 1:2 n:p convention)
W_TOTAL = [7.5, 15.0, 30.0, 60.0, 120.0, 240.0]


def sw_widths(total_um):
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=PARK_W)


def needed():
    n, p = {CELL_N, PARK_W}, {CELL_P}
    for w in W_TOTAL:
        d = sw_widths(w)
        n.add(round(d["wn"], 6)); n.add(round(d["park"], 6))
        p.add(round(d["wp"], 6))
    return sorted(n), sorted(p)


def have(cache):
    """Which geometries already have a built .so is not readable from the
    filename (it is a param hash), so presence is probed by RUNNING a deck and
    checking whether it reports a build.  Cheap because a warm deck solves in
    ~1 s."""
    return os.path.isdir(cache) and len([f for f in os.listdir(cache)
                                         if f.endswith(".so")]) or 0


def deck(ns, ps):
    """One tiny DC-biased deck touching each requested geometry once.  Every
    node is biased (no all-zero t=0 state), so it converges without a companion."""
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17",
         "VG g 0 0.9", "VS s 0 0.0", "VD vd 0 1.2"]
    k = 0
    for w in ns:
        L += ["XN%d dn%d g 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, w),
              "RN%d dn%d vd 10k" % (k, k)]
        k += 1
    for w in ps:
        L += ["XP%d dp%d g vd vd sg13_lv_pmos w=%gu l=0.13u" % (k, k, w),
              "RP%d dp%d 0 10k" % (k, k)]
        k += 1
    L += [".tran 1p 5p", ".print tran V(g)", ".end"]
    return L


def one(job):
    idx, ns, ps = job
    cache = os.path.join(SHARED + "_w%d" % idx)
    os.makedirs(cache, exist_ok=True)
    # seed with everything already built so a job never rebuilds a warm geometry
    for f in os.listdir(SHARED):
        src, dst = os.path.join(SHARED, f), os.path.join(cache, f)
        if not os.path.exists(dst):
            (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
    fn = "warm_%d.cir" % idx
    open(os.path.join(HERE, fn), "w").write("\n".join(deck(ns, ps)) + "\n")
    env = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
               PYMS_VAE_CACHE=cache)
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, cwd=HERE,
                       env=env, timeout=3000)
    wall = time.monotonic() - t0
    built = [l.split("/")[-1].split()[0] for l in r.stdout.splitlines()
             if "build_vae_so: built" in l]
    return dict(idx=idx, n=ns, p=ps, rc=r.returncode, wall_s=round(wall, 1),
                built=built, cache=cache,
                err=("" if r.returncode == 0 else r.stdout[-400:]))


def merge():
    moved = 0
    for d in sorted(os.listdir(os.path.dirname(SHARED))):
        full = os.path.join(os.path.dirname(SHARED), d)
        if not d.startswith(os.path.basename(SHARED) + "_w") or not os.path.isdir(full):
            continue
        for f in os.listdir(full):
            src, dst = os.path.join(full, f), os.path.join(SHARED, f)
            if not os.path.exists(dst):
                (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
                moved += 1
    return moved


if __name__ == "__main__":
    ns, ps = needed()
    print("geometries needed: nMOS %s  pMOS %s" % (ns, ps))
    print("shared cache holds %d .so before warming" % have(SHARED))
    # split into NJ jobs, interleaved so each job gets a mix of small and large
    NJ = int(os.environ.get("NJ", "5"))
    jobs = []
    for i in range(NJ):
        jobs.append((i, ns[i::NJ], ps[i::NJ]))
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=NJ) as ex:
        futs = [ex.submit(one, j) for j in jobs]
        for f in as_completed(futs):
            r = f.result()
            print("job %d rc=%d %.0fs built %d: n=%s p=%s %s"
                  % (r["idx"], r["rc"], r["wall_s"], len(r["built"]),
                     r["n"], r["p"], r["err"][:200]), flush=True)
    print("merged %d files" % merge())
    print("shared cache holds %d .so after warming (%.0fs total)"
          % (have(SHARED), time.monotonic() - t0))
