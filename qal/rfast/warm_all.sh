#!/bin/bash
# Pre-warm every PSP103 geometry this run needs, each build in its OWN private
# cache (no concurrent builds into one cache -- the skeptic's measured 6.6%
# contamination), then merge by filename (the .so name is a parameter hash).
set -u
RF=/usr/local/src/stat-sim/qal/rfast
SC="/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad"
MAIN="$SC/vae_cache_rfast"
mkdir -p "$MAIN"
GEOMS="n:0.74 n:1.0 n:2 n:3 n:4 n:6 n:10 n:15 n:20 n:30 p:1.12 p:20 p:30 p:40 p:60"
printf '%s\n' $GEOMS | xargs -P 8 -I{} bash -c '
  g="{}"; kind="${g%%:*}"; w="${g##*:}"
  c="'"$SC"'/vae_rf_${kind}${w}"
  mkdir -p "$c"
  python3 '"$RF"'/rf.py warmone "$c" "$kind" "$w" > '"$RF"'/warm/log_${kind}${w}.txt 2>&1
  echo "done $g $?"
'
# merge: copy every artefact not already present (same name => same content)
for d in "$SC"/vae_rf_*; do
  cp -n "$d"/* "$MAIN"/ 2>/dev/null
done
echo "MERGED: $(ls "$MAIN" | wc -l) files in $MAIN"
