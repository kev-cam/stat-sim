#!/bin/bash
cd "$(dirname "$0")"
{
echo "trap 80 3 P0 1"; echo "trap 80 3 P0 10"; echo "trap 80 3 P0 30"; echo "trap 80 3 P0 100"
echo "trap 92 3 P0 1"; echo "trap 92 3 P0 10"; echo "trap 92 3 P0 30"; echo "trap 92 3 P0 100"
} | xargs -P 7 -n 5 sh -c 'python3 mesh3.py one "$0" "$1" "$2" "$3" "$4" >> log_stiff.txt 2>&1; echo "stiff $0 tt$1 d$2 rs$4 rc=$?"'
python3 - <<'PY' >> log_stiff.txt 2>&1
import mesh3, os, subprocess
lines, S = mesh3.deck("trap", 92.0, 3, "P0")
rd = os.path.join(mesh3.RUNS_SCRATCH, "exemplar_trap_tt92_d3")
p, msg = mesh3.run_xyce(rd, "c_trap_tt92_d3.cir", lines, timeout=4800)
print("EXEMPLAR", msg)
if p:
    o = mesh3.extract(rd, S, keep_prn=True)
    subprocess.run(["gzip", "-f", p + ".prn"])
    import json
    ref = json.load(open(os.path.join(mesh3.HERE, "runs", "trap_tt92_d3", "OUT.json")))
    same = (o["erosion"][3] == {int(k) if k.isdigit() else k: v for k, v in ref["erosion"]["3"].items()} if False else
            o["erosion"][3]["width_0mV_ps_links"] == ref["erosion"]["3"]["width_0mV_ps_links"]
            and o["acceptance"] == ref["acceptance"])
    print("EXEMPLAR reproduces committed row (widths+acceptance):", same)
PY
echo ALL-STIFF-DONE
