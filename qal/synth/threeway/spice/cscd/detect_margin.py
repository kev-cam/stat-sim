#!/usr/bin/env python3
"""DETECTION MARGIN from the measured golden waveform.

A level-triggered current completion detector has two hard constraints:
  (1) SAFETY  : its threshold must be BELOW the deepest current lull that occurs
                WHILE the block is still computing, or it declares completion early.
  (2) LATENCY : completion is declared when I falls below that threshold, which
                happens some time AFTER the last real transition.
This script measures both from the golden run, per vector window.
"""
import sys, json
from analyze_cscd import load

VDD = 1.2
I_DC_FLOOR = 1.557948e-9      # MEASURED, DC operating point, all-zero vector


def main(prn, tvec_ns, nwin, census):
    hdr, cols, rows = load(prn)
    ti = cols['TIME']
    ii = [cols[k] for k in hdr if k.upper().startswith('I(VDD')][0]
    outc = [(k, cols[k]) for k in hdr if k.upper().startswith('V(')]
    t = [r[ti] for r in rows]
    raw = [-r[ii] for r in rows]
    ib = [raw[0]] + [0.5 * (raw[k] + raw[k - 1]) for k in range(1, len(raw))]

    print("%-3s %-22s %5s %9s %11s %11s %9s %11s %9s" %
          ("W", "vector", "togs", "Ipeak", "t_lastout", "I@lastout",
           "worst lull", "lull/peak", "SAFE thr"))
    out = []
    for w in range(1, nwin):
        t0, t1 = w * tvec_ns * 1e-9, (w + 1) * tvec_ns * 1e-9
        idx = [k for k in range(len(t)) if t0 <= t[k] <= t1]
        if not idx:
            continue
        tw = [t[k] for k in idx]
        iw = [ib[k] for k in idx]
        ipk = max(iw)

        # last output crossing in this window
        tlast = None
        for name, ci in outc:
            prev = rows[idx[0]][ci]
            for k in idx[1:]:
                v = rows[k][ci]
                if (prev - 0.6) * (v - 0.6) < 0:
                    tlast = t[k] if tlast is None else max(tlast, t[k])
                prev = v
        cen = census[w - 1]
        if tlast is None:
            print("%-3d %-22s %5d %9.4f mA  %10s  (no output transition: NON-EVENT)"
                  % (w, cen['name'], cen['internal_node_toggles'], ipk * 1e3, "-"))
            out.append({"window": w, "name": cen['name'],
                        "toggles": cen['internal_node_toggles'], "non_event": True,
                        "I_peak_A": ipk})
            continue

        # Safety bound = the MINIMUM current at any instant while transitions are
        # still to come. Start the scan at t0+EDGE_SKIP: the ideal PWL input
        # drivers slew over the first 50 ps and shove charge back into VDD
        # through the PMOS gate capacitance (measured: -175 uA in W4), which is
        # a property of the testbench's ideal sources, not of the block.
        EDGE_SKIP = 0.08e-9
        tstart = t0 + EDGE_SKIP
        i_at_last = None
        for k in range(len(tw)):
            if tw[k] >= tlast:
                i_at_last = iw[k]; break
        span = [k for k in range(len(tw)) if tstart <= tw[k] <= tlast]
        if span:
            lull = min(iw[k] for k in span)
            t_lull = tw[min(span, key=lambda k: iw[k])]
        else:
            lull, t_lull = ipk, tw[0]
        safe_thr = lull          # threshold must be below this

        print("%-3d %-22s %5d %9.4f mA %10.3f %10.4f uA %8.4f uA %8.1f%% %9.4f uA"
              % (w, cen['name'], cen['internal_node_toggles'], ipk * 1e3,
                 (tlast - t0) * 1e9, (i_at_last or 0) * 1e6, lull * 1e6,
                 100 * lull / ipk, safe_thr * 1e6))

        # latency: first time after tlast that I stays below a given threshold
        def t_below(thr, tw=tw, iw=iw, tlast=tlast):
            for k in range(len(tw)):
                if tw[k] < tlast:
                    continue
                if all(iw[j] < thr for j in range(k, len(tw))):
                    return (tw[k] - tlast) * 1e12
            return None
        lat = {}
        for nm, thr in (("safe(=lull)", safe_thr), ("half-lull", 0.5 * safe_thr),
                        ("100uA", 1e-4), ("10uA", 1e-5), ("1uA", 1e-6),
                        ("100nA", 1e-7)):
            lat[nm] = t_below(thr)
        print("      latency after last transition: " + "  ".join(
            "%s=%s" % (n, ("%.0f ps" % v) if v is not None else "never")
            for n, v in lat.items()))
        out.append({"window": w, "name": cen['name'],
                    "toggles": cen['internal_node_toggles'],
                    "I_peak_A": ipk, "t_last_out_rel_ns": (tlast - t0) * 1e9,
                    "I_at_last_out_A": i_at_last, "worst_lull_A": lull,
                    "t_lull_rel_ns": (t_lull - t0) * 1e9,
                    "lull_frac_of_peak": lull / ipk,
                    "latency_ps": lat, "_t_below": t_below})
    act = [o for o in out if not o.get("non_event")]
    if act:
        print()
        print("=== CROSS-VECTOR CONSTRAINT (ONE fixed threshold must serve every vector) ===")
        worst = min(act, key=lambda o: o["worst_lull_A"])
        lo = worst["worst_lull_A"]
        hi = max(o["I_peak_A"] for o in act)
        print("  threshold CEILING = deepest pre-completion minimum over all vectors")
        print("      %.4f uA   set by %s at %.3f ns into the window"
              % (lo * 1e6, worst["name"], worst["t_lull_rel_ns"]))
        print("  largest peak over all vectors : %.4f mA" % (hi * 1e3))
        print("  measured DC leakage floor     : %.6f uA (%.4f nA)"
              % (I_DC_FLOOR * 1e6, I_DC_FLOOR * 1e9))
        print("  ceiling / DC floor            : %.0f x   <-- the binding constraint is the"
              % (lo / I_DC_FLOOR))
        print("                                              LULL, not leakage")
        print("  ceiling / largest peak        : %.2f %%" % (100 * lo / hi))
        print()
        print("  latency after the last real transition, at a margined threshold:")
        for frac, lab in ((1.0, "at ceiling"), (0.5, "ceiling/2"), (0.25, "ceiling/4")):
            thr = lo * frac
            row = []
            for o in act:
                v = o["_t_below"](thr)
                row.append("%s=%s" % (o["name"].split("_")[0] + o["name"].split("_")[1][:4],
                                      "never" if v is None else "%.0f ps" % v))
            print("    thr=%8.4f uA (%-10s): %s" % (thr * 1e6, lab, "  ".join(row)))
    for o in out:
        o.pop("_t_below", None)
    json.dump(out, open(prn.replace(".prn", "") + ".margin.json", "w"), indent=1)


if __name__ == "__main__":
    prn, tvec, nwin = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
    cen = json.load(open("activity_census.json"))["windows"]
    main(prn, tvec, nwin, cen)
