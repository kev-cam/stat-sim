# P620a runbook — running campaign decks on the certified second node

## Access
`ssh p620a` (key auth; ICMP filtered — NEVER ping). Lands in Cygwin; the
simulators live in WSL: `wsl -u claude -e bash -c '...'` (login shell not
required; /usr/local/src is a symlink to the 9p mount and is always visible).

## Xyce (P620A-XYCE, certified digit-identical 2026-09-29)
- Binary: /usr/local/src/xyce-build/src/Xyce
  = DEVELOPMENT-202609292309-(Release-7.10.0-203-g1c36edca), ADMS OFF.
- Env for PyMS decks:
  PYMS_DIR=/usr/local/share/xyce/PyMS
  PYMS_VAE_CACHE=<your cache>   # vae math .so per geometry
  PYMS_CACHE=<your shell cache> # device shells; default /tmp/pyms_hdl_cache
- PSP103 loads via the level=103 AUTO-LOAD (the committed decks' line-1 .hdl
  is a TITLE line everywhere — never count on it). ALWAYS verify the log
  shows ".HDL: compiled and registered PSP103VA"; a run WITHOUT that line
  used built-in NMOS and is silently wrong (~1 s tell-tale runtime).
- /usr/local/src/xyce-build/src/libXyceLib.so must exist (copy of
  libxyce.so). A rebuild regenerates libxyce.so only — refresh the copy.
- DO NOT reconfigure with default CMake options: Xyce_ADMS_MODELS must stay
  FALSE or the compiled-in ADMS PSP103 shadows PyMS (silent wrong physics).

## Long jobs (WSL kills session trees; WSL service resets happen)
Cygwin-side supervisor pattern, proven:
  ssh p620a 'cat > /tmp/sup.sh && chmod +x /tmp/sup.sh' < sup.sh
  ssh p620a '(nohup bash /tmp/sup.sh > /tmp/sup.log 2>&1 &)'
where sup.sh relaunches a RESUMABLE `wsl -u claude -e <script>` until a
terminal STATUS file exists. Scripts must be marker-resumable.
NOTE the &-binding trap: `(nohup ... &)` in its own subshell, never chained
with && from the same command line.

## VACASK (P620A-VACASK, offsets per OFFSET_TABLE.md)
- /opt/build.VACASK/Release/simulator/vacask (0.3.3-8-g9b9c7b2)
- OSDI: /opt/openvaf-r/openvaf-r (OSDI 0.4) on /usr/local/src/VACASK/devices
- sg13g2 cards: qal/p620a/vacask_port/sg13g2_models.inc (generated from the
  kestrel tt lib; regenerate with gen_models_sg13g2.py after card changes).
- Port rules that MUST be honored (all measured this campaign):
  * never icmode="uic" for pre-charged rails (non-cap nodes float);
  * forced-ic op needs the FULL consistent inductor-island node set,
    or use the series-vinit pre-charge trick;
  * do not copy Xyce's ABSTOL=1e-15/CHGTOL=1e-17 (stepper collapse);
    gear + reltol=1e-5 validated;
  * energies via offline_meter.py on the raw (validated 2e-5 on closed form).
- Per-device DELVTO MC stays Xyce-only (no PyMS callback path in VACASK).

## Rules
Label every number (host, engine). P620a never pushes; scp results back and
commit from the local box. P620A-VACASK numbers carry OFFSET_TABLE.md.
