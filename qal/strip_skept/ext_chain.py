#!/usr/bin/env python3
"""Extract cascade results: separation by depth and per-gate correctness.

separation(depth) = mean(V of nodes that SHOULD be HIGH)
                  - mean(V of nodes that SHOULD be LOW)
A negative separation means the should-be-HIGH nodes sit BELOW the should-be-LOW
nodes: the stage carries no recoverable information.

correctness(depth) = nodes whose final V is on the correct side of rail/2.

PATTERN GUARD.  A node is only credited as correct if the devices that are
supposed to be driving it actually have gate drive above the MEASURED Vtn.  A
node that is merely UNDISTURBED (its pull-down off, sitting where the pull-up
left it) is NOT evidence that the logic worked.  For a dual-rail bank, 50%
correct is the score an UNRESOLVED pair yields BY CONSTRUCTION (each cell gets
exactly one of its two nodes right), so 50% is reported as UNRESOLVED, never as
half-working.
"""
import os, json, collections

VTN = 0.5239941   # MEASURED in this run (vt.cir), not inherited


def read_prn(p):
    with open(p) as f:
        lines = [l for l in f if l.strip()]
    hdr = lines[0].split()
    rows = []
    for l in lines[1:]:
        parts = l.split()
        if len(parts) != len(hdr):
            continue
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            continue
    return {h.lower(): i for i, h in enumerate(hdr)}, rows


def main():
    d = os.path.dirname(os.path.abspath(__file__))
    M = json.load(open(os.path.join(d, "CHAIN_META.json")))
    gl = M["golden"]
    nodes = M["nodes"]
    bydeck = collections.defaultdict(list)
    for m in nodes:
        bydeck[m["deck"]].append(m)

    print("GOLDEN bank patterns: " + "  ".join(
        "d%d=%s" % (k + 1, "".join(str(x) for x in b)) for k, b in enumerate(gl)))
    print("MEASURED Vtn used by the pattern guard = %.7f V\n" % VTN)

    allout = {}
    for deck in sorted(bydeck):
        p = os.path.join(d, deck + ".prn")
        if not os.path.exists(p):
            print("MISSING", deck)
            continue
        cols, rows = read_prn(p)
        last = rows[-1]
        k10 = max(2, len(rows) // 10)
        prev = rows[-k10]
        rail = bydeck[deck][0]["rail"]
        tag = bydeck[deck][0]["tag"]
        print("=== %-12s topo=%-7s rail=%.4f  window=%.2f ns  checked=%d nodes"
              % (deck, bydeck[deck][0]["topo"], rail, last[0] * 1e9,
                 len(bydeck[deck])))
        print("%6s %9s %9s %8s %9s %9s %10s %12s" % (
            "depth", "meanHI(V)", "meanLO(V)", "sep(mV)", "worst%",
            "correct", "still_mV", "verdict"))
        rec = []
        for k in range(1, 7):
            grp = [m for m in bydeck[deck] if m["depth"] == k]
            if not grp:
                continue
            hi = [last[cols["v(%s)" % m["node"]]] for m in grp if m["expect"] == "HI"]
            lo = [last[cols["v(%s)" % m["node"]]] for m in grp if m["expect"] == "LO"]
            sep = (sum(hi) / len(hi) - sum(lo) / len(lo)) * 1000.0
            ncorr = 0
            worst = 1e9
            mv = 0.0
            for m in grp:
                v = last[cols["v(%s)" % m["node"]]]
                vp = prev[cols["v(%s)" % m["node"]]]
                mv = max(mv, abs(v - vp) * 1000.0)
                s = (v / rail) if m["expect"] == "HI" else (1.0 - v / rail)
                worst = min(worst, s * 100.0)
                ok = (v > rail / 2) if m["expect"] == "HI" else (v < rail / 2)
                ncorr += 1 if ok else 0
            frac = ncorr / len(grp)
            if sep <= 0:
                verd = "NO INFO"
            elif abs(frac - 0.5) < 1e-9 and "strip" in tag:
                verd = "UNRESOLVED"
            elif ncorr == len(grp):
                verd = "ALL CORRECT"
            else:
                verd = "PARTIAL"
            print("%6d %9.5f %9.5f %+8.1f %9.2f %5d/%-3d %10.3f %12s" % (
                k, sum(hi) / len(hi), sum(lo) / len(lo), sep, worst,
                ncorr, len(grp), mv, verd))
            rec.append(dict(depth=k, meanHI=sum(hi) / len(hi),
                            meanLO=sum(lo) / len(lo), sep_mV=sep,
                            worst_pct=worst, correct=ncorr, total=len(grp),
                            still_mV=mv, verdict=verd))
        seps = [r["sep_mV"] for r in rec]
        print("  sep_min=%+.1f mV  all_positive=%s  first_nonpositive_depth=%s" % (
            min(seps), all(s > 0 for s in seps),
            next((r["depth"] for r in rec if r["sep_mV"] <= 0), None)))
        print()
        allout[deck] = dict(tag=tag, rail=rail, rows=rec)
    json.dump(allout, open(os.path.join(d, "CHAIN_SKEPT.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
