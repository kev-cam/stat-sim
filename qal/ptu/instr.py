#!/usr/bin/env python3
"""A5: reproduce the committed robust single-hop point DIGIT-CHECKED in THIS
directory, under MY OWN PYMS_VAE_CACHE, from BYTE-IDENTICAL copies of the
committed decks (md5 verified).  If this does not pass, nothing else reports."""
import json, os, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

HERE = "/usr/local/src/stat-sim/qal/ptu"
COMMITTED = "/usr/local/src/stat-sim/qal/lsweep"

REF = {"TZ_ps": 65.49500982344826, "VBEND": 0.7138163, "VBPK": 0.8368896,
       "IZ_uA": -0.0004958676}
T0_CLOSE = 50.0   # ps: the committed probe deck closes its transfer switch at 50 ps
                  # (VGT ... 48p 0 50p 1.5), and the committed t_hop is measured
                  # RELATIVE TO THAT CLOSE, not absolutely.  Reading the absolute
                  # zero gives 115.495 ps = 65.495 + 50.000 exactly.


def main():
    mine = SK.parse_mt0(os.path.join(HERE, "instr_anchor.cir.mt0"))
    theirs = SK.parse_mt0(os.path.join(COMMITTED, "h_L15_W30_dv120.cir.mt0"))
    out = {"_what": "committed robust single-hop point re-run here: L=15 nH, "
                    "TG 10/20 um + 2 um park (30 um total), dV=1.2",
           "_decks": "instr_anchor.cir / instr_probe.cir are md5-identical byte "
                     "copies of qal/lsweep/h_L15_W30_dv120.cir / p_L15_W30_dv120.cir",
           "_cache": "PYMS_VAE_CACHE=.../vae_cache_ptu (my own; the sibling's "
                     "prebuilt .so was deliberately NOT copied -- copying a VAE cache "
                     "is the shell-cache poisoning trap the record already root-caused)"}

    # the true hop zero, re-measured from MY probe .prn by the committed rule
    hdr, rows = SK.read_prn(os.path.join(HERE, "instr_probe.cir.prn"))
    icol = [c for c in hdr if c.startswith("I(L")][0]
    tz_abs, pk = SK.zero_after_peak(hdr, rows, icol, 0.0)
    tz = tz_abs - T0_CLOSE
    out["t_hop_ps"] = {"mine": round(tz, 8), "committed": REF["TZ_ps"],
                       "mine_absolute_ps": round(tz_abs, 8),
                       "switch_close_ps": T0_CLOSE,
                       "rel": abs(tz - REF["TZ_ps"]) / REF["TZ_ps"]}
    out["IPK_uA_from_prn"] = round(pk * 1e6, 4)

    for k, ref in (("VBEND", REF["VBEND"]), ("VBPK", REF["VBPK"])):
        if k in mine:
            out[k] = {"mine": mine[k], "committed": ref,
                      "rel": abs(mine[k] - ref) / abs(ref)}
    if "IZ" in mine:
        out["IZ_uA"] = {"mine": mine["IZ"] * 1e6, "committed": REF["IZ_uA"],
                        "rel": abs(mine["IZ"] * 1e6 - REF["IZ_uA"]) / abs(REF["IZ_uA"])}

    # full mt0 key-by-key comparison against the committed mt0
    shared = sorted(set(mine) & set(theirs))
    ident, worst, worstk = 0, 0.0, None
    for k in shared:
        a, b = mine[k], theirs[k]
        if a == b:
            ident += 1
            continue
        d = abs(a - b) / max(abs(a), abs(b), 1e-30)
        if d > worst:
            worst, worstk = d, k
    out["mt0_keys_compared"] = len(shared)
    out["mt0_keys_BIT_IDENTICAL"] = ident
    out["mt0_worst_rel"] = worst
    out["mt0_worst_key"] = worstk

    # 8/8 cells settled.  Committed anchor: even i has input 1.2 (HIGH -> pull-DOWN,
    # output -> 0), odd i has input 0 (LOW -> pull-UP, output -> the bank rail).
    vr = mine.get("VBEND")
    cells, worst = {}, 100.0
    for i in range(8):
        vo = mine.get("O%dE" % i)
        if vo is None or not vr:
            continue
        f = (1.0 - vo / vr) if (i % 2 == 0) else (vo / vr)
        cells[i] = dict(kind="pulldown" if i % 2 == 0 else "pullup",
                        v_o=vo, settle_pct=100.0 * f)
        worst = min(worst, 100.0 * f)
    out["cells"] = cells
    out["cells_measured"] = len(cells)
    out["cells_settled"] = "%d/%d, minimum %.6f%%" % (
        sum(1 for c in cells.values() if c["settle_pct"] >= 99.9), len(cells), worst)

    gates = [out["t_hop_ps"]["rel"] < 1e-6,
             out.get("VBEND", {}).get("rel", 1) < 1e-6,
             out.get("VBPK", {}).get("rel", 1) < 1e-6,
             out["cells_measured"] == 8, worst >= 99.9]
    out["VERDICT"] = "PASS, digit-checked" if all(gates) else "FAIL"
    json.dump(out, open(os.path.join(HERE, "INSTRUMENT.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
