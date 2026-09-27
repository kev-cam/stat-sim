#!/usr/bin/env python3
"""Regression test for the 2026-09-26 "PyMS drops the softplus reassignments"
toolchain regression (v3 stop-verdict; README |4.7 box).

WHAT ACTUALLY HAPPENED (root-caused 2026-09-26, evidence in the gate-A report):
the emitter never dropped anything. The .hdl device-shell cache in Xyce's
N_DEV_PyMS.C is keyed by MODULE NAME (pyms_<module>.so) and was validated only
by mtime ordering against the CURRENT deck's .va path. A same-named module
compiled from a DIFFERENT .va file (a scratchpad v1check/ copy of qal_gate.va,
pre-softplus) captured the cache slot; every later run of the repo's
qal_gate.va reused that stale shell, whose baked _va path made even the
freshly built vae eval.cpp compile the WRONG .va -- zero log/exp, all seven
conductances bound to the hard clamp, silently.

THIS TEST replays that exact collision with a minimal module (softplus_chain):
  1. run a deck against dir_a/softplus_chain.va  (v1 hard-clamp variant)
  2. make dir_b/softplus_chain.va (the softplus self-reassignment chain) LOOK
     OLD (mtime before step 1's shell build -- the v3 situation: qal_gate.va
     at 11:14, poisoned shell at 11:47)
  3. run the same deck against dir_b's file
ASSERTS (all against step 3's run):
  A. the freshly used vae eval.cpp contains the softplus reassignment chain
     (a log( and an exp( in the eval, and the versioned ov reassignment)
  B. the measured current matches the ANALYTIC reference for the softplus
     form:  V=0.5 -> ov_eff = K*ln 2 -> I = K*ln(2)/(1.2*R)*0.5 = 2.21636e-6 A
     (the hard clamp gives exactly 0 -- the silent-wrong signature)
  C. control: step 1's run itself measured the hard-clamp 0 (the two variants
     really are distinguishable through the full Xyce+PyMS pipeline)

Fixed by: xyce 71d0b770's successor commit -- N_DEV_PyMS.C records a
<so>.src sidecar (va path + content hash) and reuses the shell only on an
exact match; xyce_device_gen.py additionally keys the vae .so cache on the
.va CONTENT, not just its path+params.

Runs the BUILD-AREA Xyce (regress doctrine) with private PYMS_CACHE /
PYMS_VAE_CACHE dirs; ~1-2 min total. Exit 0 = PASS.
"""
import os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = os.environ.get("XYCE", "/usr/local/src/xyce-build/src/Xyce")
# regress doctrine: test the build area. The build-tree binary must resolve
# the build-tree libXyceLib.so (an installed /usr/local/lib copy may be older).
XYCE_LIBDIR = os.path.dirname(XYCE)

K, R = 0.0478, 6229.0
I_SOFTPLUS = (K * 0.6931471805599453) / (1.2 * R) * 0.5   # 2.21636e-6 A
RTOL = 1e-3

DECK = """* softplus_chain regression deck (V=0.5 sits exactly on the clamp knee)
.hdl "%(va)s"
.model m1 softplus_chain
YSOFTPLUS_CHAIN X1 p 0 m1
VS p 0 0.5
.tran 1p 10p
.measure tran IDEV FIND I(VS) AT=9p
.end
"""


def run_deck(va_path, work, env):
    deck = os.path.join(work, "run_" + os.path.basename(os.path.dirname(va_path)) + ".cir")
    with open(deck, "w") as f:
        f.write(DECK % {"va": va_path})
    r = subprocess.run([XYCE, deck], capture_output=True, text=True,
                       timeout=230, cwd=work, env=env)
    mt0 = deck + ".mt0"
    if not os.path.exists(mt0):
        print("FAIL: no .mt0 for %s\nXyce tail:\n%s" % (deck, r.stdout[-2000:]))
        sys.exit(1)
    for ln in open(mt0):
        m = re.match(r"\s*IDEV\s*=\s*(\S+)", ln)
        if m:
            return float(m.group(1))
    print("FAIL: IDEV not found in %s" % mt0)
    sys.exit(1)


def main():
    work = tempfile.mkdtemp(prefix="shellpoison_")
    dir_a = os.path.join(work, "dir_a"); os.makedirs(dir_a)
    dir_b = os.path.join(work, "dir_b"); os.makedirs(dir_b)
    va_a = os.path.join(dir_a, "softplus_chain.va")
    va_b = os.path.join(dir_b, "softplus_chain.va")
    shutil.copy(os.path.join(HERE, "softplus_chain_v1.va"), va_a)
    shutil.copy(os.path.join(HERE, "softplus_chain.va"), va_b)

    env = dict(os.environ)
    env["PYMS_CACHE"] = os.path.join(work, "hdl_cache")
    env["PYMS_VAE_CACHE"] = os.path.join(work, "vae_cache")
    env["LD_LIBRARY_PATH"] = XYCE_LIBDIR + (
        ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    env.pop("VAE_SO_PATH", None); env.pop("VAE_SO_DIR", None)

    # Step 1+C: the v1 hard clamp, from dir_a -- captures the module-name slot.
    i_a = run_deck(va_a, work, env)
    if abs(i_a) > 1e-12:
        print("FAIL (control): hard-clamp variant measured %.4g, expected 0" % i_a)
        sys.exit(1)

    # Step 2: the v3 mtime situation -- the real .va is OLDER than the shell.
    old = time.time() - 3600
    os.utime(va_b, (old, old))

    # Step 3: the real cell, same module name, different directory.
    i_b = run_deck(va_b, work, env)

    # Assert B: numerics -- softplus, not the poisoned hard clamp.
    if not (abs(-i_b - I_SOFTPLUS) <= RTOL * I_SOFTPLUS):
        print("FAIL: softplus run measured I=%.6g (|I| expected %.6g +-%g rel)."
              % (i_b, I_SOFTPLUS, RTOL))
        print("      0 here = the module-name cache-poisoning regression is back.")
        sys.exit(1)

    # Assert A: the freshly built eval.cpp carries the reassignment chain.
    evals = []
    for root, _dirs, files in os.walk(env["PYMS_VAE_CACHE"]):
        for fn in files:
            if fn == "eval.cpp" and "softplus_chain" in root:
                evals.append(os.path.join(root, fn))
    ok = False
    for ev in evals:
        txt = open(ev).read()
        if "log(" in txt and "exp(" in txt and re.search(r"\bov__\d+\s*=", txt):
            ok = True
    if not ok:
        print("FAIL: no eval.cpp in %s contains the softplus reassignment chain"
              % env["PYMS_VAE_CACHE"])
        print("      (checked: %s)" % ", ".join(evals) if evals else "(none built)")
        sys.exit(1)

    print("PASS: shell-cache poisoning regression")
    print("  control (v1 hard clamp)  I = %.6g A (expected 0)" % i_a)
    print("  softplus after collision I = %.6g A (analytic %.6g, rtol %g)"
          % (i_b, -I_SOFTPLUS, RTOL))
    print("  eval.cpp chain check: %d candidate(s), reassignment present" % len(evals))
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
