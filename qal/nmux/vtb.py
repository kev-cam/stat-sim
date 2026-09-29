#!/usr/bin/env python3
"""(a) Vtn(V_sb) MEASURED on the PSP103 nMOS, 0 .. 1.3 V of source-body bias.

Protocol P1 of PRE_REGISTERED.json:
  bulk at 0, source at V_sb, drain at V_sb+0.1 (so Vds = 0.1 V always),
  gate driven by a FLOATING source VG(g,s) so the .DC sweep axis IS Vgs.
  V(g) and V(s) are PRINTED EXPLICITLY -- Xyce's .DC .prn column 1 is the
  first printed variable, not the swept source (the vtreq A2 trap).

Criterion: the campaign's  Id = 100 nA * (W/L)  at |Vds| = 0.1 V, on the
campaign's canonical device w=0.74u l=0.13u, so V_sb=0 must reproduce the
committed Vtn = 0.5239460 (gate G1).  Also reported at 10 nA*W/L and
1 nA*W/L so no conclusion rests on the criterion choice.
"""
import json, math, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_nmux"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

W, L = 0.74, 0.13                      # campaign canonical nMOS
VSB  = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75,
        0.8, 0.9, 1.0, 1.1, 1.2, 1.26, 1.3]
COMMITTED_VTN0 = 0.5239460152201223


def deck(vsb):
    return "\n".join([
        '.hdl "%s"' % VA,
        '.include "%s"' % MODEL,
        '.include "%s"' % SHIM,
        ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17",
        "* nMOS with source+drain lifted to V_sb; BULK stays at 0 -> V_sb = %g V" % vsb,
        "VS s 0 %.6f" % vsb,
        "VD d s 0.1",
        "VG g s 0",
        "XN d g s 0 sg13_lv_nmos w=%gu l=%gu" % (W, L),
        # AMENDMENT A3: swept from 0.2 V, not 0.  At V_gs -> 0 with body bias the
        # drain current is ~1e-15 A, at or below ABSTOL, and Xyce stalls (two
        # decks ran 6+ min without finishing).  Vtn is 0.52-0.85 V over the whole
        # probed V_sb range and even the tightest criterion (1 nA*W/L = 5.69 nA)
        # lands near 0.29 V at V_sb = 0, so nothing measured is lost.
        ".dc VG 0.2 1.5 0.001",
        ".print dc V(g) V(s) V(d) I(VD)",
        ".end", ""])


def run(vsb):
    tag = "vtb_%04d" % round(vsb * 1000)
    p = os.path.join(HERE, tag + ".cir")
    open(p, "w").write(deck(vsb))
    t0 = time.monotonic()
    r = subprocess.run([XYCE, p], cwd=HERE, env=ENV,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return tag, vsb, r.returncode, time.monotonic() - t0, r.stdout.decode()[-400:]


def read(tag):
    """-> list of (Vgs, Vs, Vds, Id_A).

    BUG FIXED (see AMENDMENT A4): the printed column is V(g), the ABSOLUTE gate
    potential, and with the source lifted to V_sb that is V_sb + Vgs, not Vgs.
    Using it directly made every threshold come out V_sb too high and produced a
    body-effect slope of ~1.12 V/V, which is unphysical for a MOSFET.  The sweep
    axis is V(g) - V(s)."""
    rows = []
    for ln in open(os.path.join(HERE, tag + ".cir.prn")):
        f = ln.split()
        if not f or not f[0].lstrip("-").replace(".", "").isdigit():
            continue
        try:
            vg, vs, vd, iD = float(f[1]), float(f[2]), float(f[3]), float(f[4])
        except (IndexError, ValueError):
            continue
        rows.append((vg - vs, vs, vd - vs, -iD))   # I(VD) is into VD's + node
    return rows


def crossing(rows, itarget):
    """linear interpolation of the first upward crossing of |Id| = itarget"""
    for i in range(1, len(rows)):
        a, b = rows[i - 1][3], rows[i][3]
        if a < itarget <= b:
            x0, x1 = rows[i - 1][0], rows[i][0]
            return x0 + (itarget - a) * (x1 - x0) / (b - a)
    return None


def main():
    with ThreadPoolExecutor(max_workers=3) as ex:
        res = list(ex.map(run, VSB))
    out = {"_doc": "(a) Vtn(V_sb) MEASURED, PSP103 SG13G2 tt, w=%gu l=%gu, Vds=0.1V" % (W, L),
           "criterion_primary": "Id = 100 nA * W/L = %.1f nA" % (100.0 * W / L),
           "runs": [], "rows": []}
    ic = {"c100": 100e-9 * W / L, "c10": 10e-9 * W / L, "c1": 1e-9 * W / L}
    for tag, vsb, rc, dt, tail in res:
        out["runs"].append({"tag": tag, "vsb": vsb, "rc": rc, "sec": round(dt, 1)})
        if rc != 0:
            out["rows"].append({"vsb": vsb, "FAIL": tail})
            continue
        rows = read(tag)
        r = {"vsb": vsb, "n_pts": len(rows)}
        for k, v in ic.items():
            r["vt_" + k] = crossing(rows, v)
        # the level a source-follower stalls at: Vgs needed, read back as
        # "gate 1.5 V minus the Vt at this source level"
        r["pass_ceiling_if_source_here"] = (1.5 - r["vt_c100"]) if r["vt_c100"] else None
        # raw current at a few Vgs for provenance
        d = {}
        for target in (0.4, 0.6, 0.8, 1.0, 1.5):
            best = min(rows, key=lambda z: abs(z[0] - target))
            d["%.1f" % target] = best[3]
        r["Id_A_at_Vgs"] = d
        out["rows"].append(r)
    out["rows"].sort(key=lambda z: z["vsb"])
    json.dump(out, open(os.path.join(HERE, "vtb_rows.json"), "w"), indent=1)
    for r in out["rows"]:
        print("Vsb=%5.3f  Vtn100=%s  Vtn10=%s  Vtn1=%s" %
              (r["vsb"],
               ("%.6f" % r["vt_c100"]) if r.get("vt_c100") else "None",
               ("%.6f" % r["vt_c10"]) if r.get("vt_c10") else "None",
               ("%.6f" % r["vt_c1"]) if r.get("vt_c1") else "None"))
    v0 = out["rows"][0]["vt_c100"]
    print("\nG1 instrument gate: Vtn(0) = %.7f  vs committed %.7f  ->  %+.3f mV  %s"
          % (v0, COMMITTED_VTN0, (v0 - COMMITTED_VTN0) * 1e3,
             "PASS" if abs(v0 - COMMITTED_VTN0) < 1e-3 else "FAIL"))


if __name__ == "__main__":
    main()
