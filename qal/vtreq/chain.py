#!/usr/bin/env python3
"""Q2 -- HIGH/LOW SEPARATION BY BANK DEPTH vs DELVTO.

Vehicle: qal/restore5 rest.py's k = 6 NO-RESTORE control -- 6 hop-powered banks,
bank N's outputs ARE bank N+1's inputs, L = 15 nH, W = 30 um, dV = 1.2, T = 300 ps.
That is the deck that produced the committed separation series
528.68 / 22.89 / 1.52 / 0.122 / 0.010 / 0.001 mV (qal/restore5/rows.json
k6_T300_control), so the DELVTO = 0 run here is ALSO an instrument check.

rest.py / extract.py are IMPORTED, not copied.  Rebound: HERE -> a per-point
subdirectory (so two DELVTO points never share a deck filename), SHIM -> the
DELVTO shim, ENV -> my own cache, head_lines -> + the .param line.  The true ZCS
zeros are RE-PROBED for every DELVTO point; none is inherited.
"""
import json, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/restore5")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vt                                                            # noqa: E402
import rest, extract                                                 # noqa: E402

HERE = vt.HERE
K, T = 6, 300.0


def separation(outputs, k=K):
    """min(pull-UP output) - max(pull-DOWN output) within a bank, SIGNED, in mV.
    rest.is_hi(j, i) True means the cell's INPUT is HIGH, i.e. it is a pull-DOWN
    cell.  Per bank, never aggregated across banks."""
    sep = {}
    for j, d in sorted(outputs.items(), key=lambda kv: int(kv[0])):
        jj = int(j)
        up = [v for key, v in d.items() if not rest.is_hi(jj, int(key.split("_")[1]))]
        dn = [v for key, v in d.items() if rest.is_hi(jj, int(key.split("_")[1]))]
        sep[jj] = 1e3 * (min(up) - max(dn)) if up and dn else None
    return sep


def one(tag, dvtn, dvtp, vtn=None, vtp=None):
    d = os.path.join(HERE, "chain_" + tag)
    os.makedirs(d, exist_ok=True)
    rest.HERE = d
    rest.SHIM = vt.SHIM
    rest.ENV = vt.ENV
    if vtn is not None:
        extract.VTN = vtn
    if vtp is not None:
        extract.VTP = vtp

    def head_lines():
        return ['.hdl "%s"' % rest.VA, '.include "%s"' % rest.MODEL,
                '.include "%s"' % vt.SHIM,
                ".param DVTN=%.10g DVTP=%.10g" % (dvtn, dvtp),
                ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17"]
    rest.head_lines = head_lines

    t0 = time.monotonic()
    tz = rest.do_probe(K, T, 0.0)
    if tz is None:
        return dict(tag=tag, error="probe failed")
    got = rest.do_row(K, T, 0.0, tz)
    if got is None:
        return dict(tag=tag, error="row failed", tz_ps=tz)
    path, S = got
    r = extract.row_extract(K, T, 0.0, tz, path)
    r["separation_mV"] = separation(r["outputs_at_own_boundary_V"])
    r.update(tag=tag, dvtn=dvtn, dvtp=dvtp, VTN_used=extract.VTN,
             VTP_used=extract.VTP, wall_s=round(time.monotonic() - t0, 1))
    json.dump(r, open(os.path.join(HERE, "rowd", "chain_%s.json" % tag), "w"),
              indent=1)
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    tag, dvtn, dvtp = a[0], float(a[1]), float(a[2])
    vtn = float(a[3]) if len(a) > 3 else None
    vtp = float(a[4]) if len(a) > 4 else None
    r = one(tag, dvtn, dvtp, vtn, vtp)
    if "error" in r:
        print("CHAIN %s ERROR %s" % (tag, r["error"]), flush=True)
    else:
        print("CHAIN %-8s sep_mV %s" % (tag, {k: (None if v is None else round(v, 4))
                                              for k, v in r["separation_mV"].items()}),
              flush=True)
        print("        rails %s" % {k: round(v, 4) for k, v in
                                    r["rail_at_own_boundary_V"].items()}, flush=True)
        print("        worst %.2f%% bank %s  %.0fs"
              % (r["worst_gate_pct_all_banks"], r["worst_gate_bank"], r["wall_s"]),
              flush=True)
