#!/bin/bash
# Skeptic cache warm: every geometry my re-runs need, each built in its OWN
# private cache (no concurrent builds into one cache), merged by filename.
set -u
SK=/usr/local/src/stat-sim/qal/rfast_skept
SC="/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad"
MAIN="$SC/vae_cache_skept"
mkdir -p "$MAIN" "$SK/warm"
# cell: n0.74 p1.12 | W=15: n5 p10 n1.0 | W=30: n10 p20 n2 | W=60: n20 p40 n4
GEOMS="n:0.74 n:5 n:1.0 n:10 n:2 n:20 n:4 p:1.12 p:10 p:20 p:40"
printf '%s\n' $GEOMS | xargs -P 8 -I{} bash -c '
  g="{}"; kind="${g%%:*}"; w="${g##*:}"
  c="'"$SC"'/vae_sk_${kind}${w}"
  mkdir -p "$c"
  python3 '"$SK"'/sk.py warmone "$c" "$kind" "$w" > '"$SK"'/warm/log_${kind}${w}.txt 2>&1
  echo "done $g $?"
'
for d in "$SC"/vae_sk_*; do
  cp -n "$d"/* "$MAIN"/ 2>/dev/null
done
echo "MERGED: $(ls "$MAIN" | wc -l) files in $MAIN"
