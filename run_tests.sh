#!/bin/bash
# run_tests.sh -- verify stat-sim: the Python discipline self-tests + the nvc
# VHDL testbenches (lock-step, end-to-end resolution, and the CDC detection demo).
#
# Env (defaults assume this box):
#   NVC      nvc binary           (default /usr/local/src/nvc-build/bin/nvc)
#   NVCLIB   nvc std/sv2vhdl libs (default /usr/local/src/nvc-build/lib)
#   PYTHON   python3
set -u
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
NVC=${NVC:-/usr/local/src/nvc-build/bin/nvc}
NVCLIB=${NVCLIB:-/usr/local/src/nvc-build/lib}
NVCWORK="--std=2040 -L $NVCLIB --work=statsim:build/statsim"
fail=0

say() { printf '\n=== %s ===\n' "$1"; }

say "Python self-tests"
for m in disc spef genmodel nvcgen klayout2spef; do
  if $PY "$m.py" --self-test 2>/dev/null || $PY "$m.py" 2>/dev/null; then
    :
  else
    echo "FAIL: $m.py"; fail=1
  fi
done

say "regenerate the generated cell set from the spec"
$PY genmodel.py --spec specs/sky130_dfxtp.json --out models >/dev/null || fail=1
$PY nvcgen.py  --spec specs/sky130_dfxtp.json --out models >/dev/null || fail=1

if [ ! -x "$NVC" ] && ! command -v "$NVC" >/dev/null 2>&1; then
  echo "nvc not found ($NVC) -- skipping VHDL testbenches"; exit $fail
fi

say "nvc: analyse library + generated cells"
rm -rf build && mkdir -p build
$NVC $NVCWORK -a lib/statsim_disc.vhd lib/statsim_taps.vhd lib/statsim_io.vhd \
     models/sky130_dfxtp.vhd models/sky130_dfxtp_cdc_trap.vhd \
     test/statsim_disc_tb.vhd test/statsim_cdc_tb.vhd test/cdc_latch_tb.vhd \
     test/statsim_rc_tb.vhd test/cdc_latch_wire_tb.vhd \
  || { echo "FAIL: analyse"; exit 1; }

run_tb() { # entity  expect-substring
  $NVC $NVCWORK -e "$1" >/dev/null 2>&1 || { echo "FAIL elaborate $1"; fail=1; return; }
  out=$($NVC $NVCWORK -r "$1" ${3:-} 2>&1 | grep -vE "older than|ignore-time")
  if echo "$out" | grep -q "$2"; then echo "PASS: $1"; else echo "FAIL: $1 (no '$2')"; fail=1; fi
}

say "nvc: testbenches"
run_tb statsim_disc_tb     "ALL OK"
run_tb statsim_cdc_tb      "DFF OK"
run_tb cdc_latch_tb        "CDC metastability risk" "--stop-time=200ns"
run_tb statsim_rc_tb       "OK flight delay"        "--stop-time=15ns"
run_tb cdc_latch_wire_tb   "DONE"                   "--stop-time=200ns"

say "result"
[ $fail -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $fail
