---
name: pyms_callback_params
description: PyMS runtime-callback params — keep a param symbolic + fetch live via _pcb() so Xyce .SAMPLING/.STEP/AGAUSS reaches it (Monte-Carlo)
metadata: 
  node_type: memory
  type: project
  originSessionId: 4921ad0c-f17b-4b84-986a-5917c9ebd2a6
  modified: 2026-09-23T16:19:21.571Z
---

PyMS JIT normally BAKES every param as a compile-time constant, so Xyce
`.SAMPLING`/`.STEP`/AGAUSS on a device param (e.g. PSP103 `DELVTO` for MC Vt
mismatch) is INERT — the built `.so` ignores post-build member updates. Fix
(user's idea: "call-backs from the model to get the relevant parameters;
compilers don't optimize calls out"): a **runtime-callback param** path,
opt-in via env `PYMS_CALLBACK_PARAMS=DELVTO` (comma list; shell writes a
`__CALLBACK__=` marker into the params file, part of the cache key).

Mechanism (all in xyce tree `utils/PyMS/vae/`, mirrored to
`/usr/local/share/xyce/PyMS/vae/`):
- **ginac_emitter.py**: `callback_params` kept symbolic (moved out of
  param_values into instance_params), declared as GiNaC symbols, and emitted in
  BOTH eval + jacobian preambles as `double NAME = _pcb("NAME");`.
- **build_vae_so.py**: wrapper defines `_pcb` + exports `vae_set_param_cb`;
  parses `__CALLBACK__` + reads the env.
- **xyce_device_gen.py** (device shell): `Instance::getCbParam(nm)` (strcmp
  chain over params → the instance/model member); file-scope `g_pyms_cur` set to
  `this` before each `vae_eval_`/`vae_jac_` call (per-device local mismatch);
  installs `pyms_param_cb` via `vae_set_param_cb` after dlopen (guarded, so
  legacy .so w/o the symbol are skipped). **De-hashing**: callback params are
  serialized with a fixed placeholder (0.0) so their sampled VALUE does NOT fork
  the .so cache → all DELVTO samples share ONE .so per geometry.

A compiler can't const-fold an opaque call, so the value stays live. Default
(env unset) = byte-identical to before (empty `__CALLBACK__` never appended).
PROVEN (2026-09-20): `.STEP DELVTO` → Id–Vg translates by exactly DELVTO (rigid Vt shift),
one .so; `.SAMPLING useExpr=true` finds the AGAUSS random params and varies
per-device DELVTO live. See [[nulex_async_ncl_bringup]] MC study. Related:
[[feedback_pyms_emitter_choice]] [[feedback_pyms_regime_dispatch]].

**★★ REGRESSION 2026-09-23 — CALLBACK MC VARIATION IS SILENTLY BROKEN NOW.** The canonical
`mylex/nulex/asic/chr/mc/run_sweep.sh` (th22, the exact flow that produced RESULTS.md's
th22/th23 kvt=1 = mean ± 5.3ps sd) — re-run fresh with the same PyMS-fixed Xyce
(`/usr/local/src/xyce-build/src/Xyce`), `PYMS_CALLBACK_PARAMS=DELVTO`, fresh `PYMS_VAE_CACHE`
— now gives **stddev = 0** (every MC sample byte-identical: TSET1 = 3.56894e-10 for all N).
The MEAN is correct (matches known), so it looks fine but reports FALSELY-PERFECT reliability —
a silent-wrong-answer, the class [[feedback_no_self_baseline]]/[[accel_corpus_sweep_result]] warn about.
So the whole cell-MC characterization tier is currently untrustworthy for sd/σ_frac. Blocked my
reduced-Vdd σ_frac(Vdd) measurement [[gpgpu_older_node_target]] (had to fall back to a σ_frac-scale
sensitivity sweep). ROOT CAUSE unconfirmed — suspect the callback install (`vae_set_param_cb` /
`pyms_param_cb` guard skipping, or `g_pyms_cur` not set, or the AGAUSS not reaching `_pcb`) regressed
in a rebuild since 2026-09-20. **★★★ ROOT CAUSE FOUND (2026-09-23): stale DEVICE-SHELL cache, bad invalidation in
`src/DeviceModelPKG/Core/N_DEV_PyMS.C`.** Two separate caches: the MODEL .so
(`build_vae_so`, env `PYMS_VAE_CACHE`, /tmp/pyms_vae_cache) AND the Xyce DEVICE-SHELL .so
(`xyce_device_gen.py` output compiled by N_DEV_PyMS.C, env `PYMS_CACHE`, **/tmp/pyms_hdl_cache**,
named `pyms_<MODULE>.so`). The device shell's `Instance::getCbParam` + the `vae_set_param_cb`
install live in the device-shell .so's constructor. N_DEV_PyMS.C step-4 staleness check compares
the cached `pyms_PSP103VA.so` mtime **against the .va file ONLY** — NOT against the freshly
regenerated `N_DEV_PYMS_PSP103VA.C` nor xyce_device_gen.py. So: xyce_device_gen.py (Sep-20, +callback)
regenerates the .C WITH the callback every run, but because psp103.va is unchanged, the OLD Sep-19
`pyms_PSP103VA.so` (0 callback symbols) is judged "up to date" and reused → callback never installs →
`_pcb`→0.0 → zero variance. (libXyceLib.so Sep-17 is a RED HERRING — commit 2e7d65a5 touched only the
3 .py files, no Xyce C++; N_DEV_PyMS.C is unchanged since Jun and just dlopens the shell.)
**IMMEDIATE FIX (verified): `rm /tmp/pyms_hdl_cache/pyms_*.so`** → the shell recompiles from the fresh
.C; confirmed the new pyms_PSP103VA.so then EXPORTS getCbParam. (Also clear the model cache
/tmp/pyms_vae_cache if its .so predate the callback, so eval fetches via _pcb.) **PROPER FIX:**
N_DEV_PyMS.C step-4 must invalidate the device-shell .so when the generated .C (or xyce_device_gen.py)
is newer than the .so, not only when the .va is. Verify by re-running run_sweep.sh th22 kvt=1 → sd>0. Also observed: th23 SET delay 272.8ps@1.2V →
**51.2ns@0.6V (188×)** — 3-series-PMOS pull-up nearly dies near threshold (NCL series stacks do NOT
voltage-scale; another reason bundled-data single-rail std cells beat NCL at low Vdd).
