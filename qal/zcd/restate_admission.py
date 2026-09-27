#!/usr/bin/env python3
"""Restate the QAL admission test with a MEASURED E_ZCD.

Rule (SELECTION-RULE.md:148-166): N_min = (39.6 + E_ZCD)/(h - 0.0361),
h = 0.867 fJ generic basis. Admit iff the block's BUSH (longest prefix whose
best contiguous partition, span <= 4 levels, sustains min-bank >= N_min)
covers the block, tail excisable. Working threshold 50 / confident 150;
50-400 was UNDECIDABLE under the ASSUMED 30-300 fJ ZCD band.
"""
import json, sys

H, TAX, OV0 = 0.867, 0.0361, 39.6
SHA = [48, 22, 19, 3, 2, 4, 2, 3, 1, 1]                      # work/levels.json
ALU = json.load(open("/usr/local/src/stat-sim/qal/synth/threeway/work/alu/"
                     "alu_levels.json"))["profile"]           # 37 levels
FPU_MIN_BANK = 63    # alu_top@fpsat_fma best min-bank (POLYSYNTH.md:120)


def n_min(e_zcd):
    return (OV0 + e_zcd) / (H - TAX)


def best_minbank(prof, span=4):
    """max over contiguous partitions (block span<=4) of the min block sum."""
    n = len(prof)
    best = [0.0] * (n + 1)          # best[i] = best min-bank for prefix i
    best[0] = float("inf")
    pre = [0]
    for x in prof:
        pre.append(pre[-1] + x)
    for i in range(1, n + 1):
        b = 0.0
        for k in range(1, span + 1):
            if i - k < 0:
                break
            blk = pre[i] - pre[i - k]
            b = max(b, min(best[i - k], blk))
        best[i] = b
    return best                      # best[n] = whole block


def bush(prof, nmin, span=4):
    """longest prefix whose best partition sustains min-bank >= nmin."""
    best = best_minbank(prof, span)
    d = 0
    for i in range(1, len(prof) + 1):
        if best[i] >= nmin:
            d = i
    return d, best


def verdict(e_zcd):
    nm = n_min(e_zcd)
    out = {"E_ZCD_fJ": e_zcd, "N_min": round(nm, 1)}
    for name, prof in (("sha_slice", SHA), ("alu_top_bush", ALU)):
        d, best = bush(prof, nm)
        covered = sum(prof[:d])
        out[name] = {
            "bush_levels": "%d/%d" % (d, len(prof)),
            "gates_covered_pct": round(100.0 * covered / sum(prof), 1),
            "whole_block_best_minbank": round(best[len(prof)], 1),
            "whole_block_admits": bool(best[len(prof)] >= nm),
        }
    out["alu_fpsat_minbank63"] = "PASS bank criterion" if nm <= FPU_MIN_BANK \
        else "FAIL bank criterion"
    return out


if __name__ == "__main__":
    e = float(sys.argv[1])
    for tag, ez in (("measured", e), ("zero_floor", 0.0),
                    ("old_low", 30.0), ("old_high", 300.0)):
        print(tag, json.dumps(verdict(ez), indent=1))
    print("thresholds: E_ZCD<=%.2f fJ -> N_min<=50 (working); <=%.2f -> N_min<=63 "
          "(fpsat block); <=%.2f -> N_min<=150 (confident); >=%.2f -> N_min>=400"
          % (50 * (H - TAX) - OV0, 63 * (H - TAX) - OV0,
             150 * (H - TAX) - OV0, 400 * (H - TAX) - OV0))
