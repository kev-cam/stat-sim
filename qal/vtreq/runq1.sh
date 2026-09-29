#!/bin/bash
# Q1 grid: one PROCESS per point (sk.py is monkey-patched per process, so two
# points must never share an interpreter), MAXPAR bounded because this box is
# shared and RAM is the limit, not cores.
cd /usr/local/src/stat-sim/qal/vtreq
STAGE=${STAGE:-q1}
MAXPAR=${MAXPAR:-4}
TAGS=${TAGS:-"d000 d050P d050N d050B d100P d100N d100B d150P d150N d150B d200P d200N d200B d300P d300N d300B"}
for t in $TAGS; do echo "$t"; done | xargs -P "$MAXPAR" -I{} sh -c \
  "python3 drive.py $STAGE {} > log_${STAGE}_{}.txt 2>&1; echo \"[\$(date +%H:%M:%S)] done $STAGE {}\""
