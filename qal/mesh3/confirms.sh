#!/bin/bash
cd "$(dirname "$0")"
{
echo "trap 70 2 P1"; echo "trap 80 3 P1"; echo "trap 92 3 P1"; echo "trap 105 3 P1"
echo "trap 117 3 P1"; echo "trap 130 3 P1"; echo "sine 70 1 P1"; echo "sine 105 2 P1"
echo "sine 117 2 P1"; echo "sine 130 3 P1"; echo "trap 92 3 P2"
} | xargs -P 7 -n 4 sh -c 'python3 mesh3.py one "$0" "$1" "$2" "$3" >> log_confirms.txt 2>&1; echo "confirm $0 $1 d$2 $3 rc=$?"'
echo ALL-CONFIRMS-DONE
