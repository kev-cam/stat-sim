#!/usr/bin/env python3
"""Track 3 H2: sync -> QAL.  Does a full-swing synchronous driver work as the
"converter" into a QAL bank, and what does the extra gate overdrive cost?

METHOD: wrap the AUDITED committed extractor qal/swsweep/sw_hop_meter.py.  The
ONLY change is that the cell DATA sources are decoupled from the bank swing:
committed code drives them at DV (= the bank swing, 1.0 V); here they are driven
at VIN, swept 1.0 (control, == committed convention) / 1.2 (sync rail) / 1.5
(overdrive rail already present in the deck as VHI).  Every other line -- cells,
switch, integrators, options, timing protocol (true ZCS) -- is the committed
harness verbatim.  The replaced function is printed line-by-line so the diff is
on the record.

Static reference: the committed report() needs a calibration ramp taken with the
SAME cell input level (gate overdrive changes the cells' static supply charge),
so calib is re-run per level and report() is called while that level's
sw_calib.cir.prn is in place.
"""
import inspect, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "swsweep"))
import sw_hop_meter as shm                                   # noqa: E402

CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_boundT3")
shm.HERE = HERE
shm.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
               PYMS_VAE_CACHE=CACHE)

DESIGN = "tg15p"          # the measured switch optimum
VIN = 1.0                 # set per level by main()

_committed_cells_metered = shm.cells_metered


def cells_metered(pinned=False, supply="bkb"):
    """committed cells_metered with ONE change: data sources at VIN, not DV."""
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    if pinned:
        raise NotImplementedError("pinned path not used by this track")
    for i in range(shm.MGATE):
        gnd = "gnh" if i in shm.HI else "gnl"
        L.append("VI%d in%d 0 %g" % (i, i, VIN if i in shm.HI else 0.0))
        gp = gn = "in%d" % i
        L.append("XP%d o%d %s %s %s sg13_lv_pmos w=%gu l=0.13u"
                 % (i, i, gp, supply, supply, shm.WP))
        L.append("XN%d o%d %s %s %s sg13_lv_nmos w=%gu l=0.13u"
                 % (i, i, gn, gnd, gnd, shm.WN))
        L.append("CL%d o%d %s %gf" % (i, i, gnd, shm.CLOAD))
    return L


def show_diff():
    a = inspect.getsource(_committed_cells_metered).splitlines()
    b = inspect.getsource(cells_metered).splitlines()
    import difflib
    print("--- committed cells_metered  +++ track3 override ---")
    for ln in difflib.unified_diff(a, b, lineterm="", n=1):
        print(ln)
    print("--- end diff ---")


def main():
    global VIN
    show_diff()
    shm.cells_metered = cells_metered
    rows = {}
    out = os.path.join(HERE, "s2q_rows.json")
    if os.path.exists(out):
        rows = json.load(open(out))
    # args are "VIN:CLOAD" pairs (CLOAD in fF, default the committed 2.0).
    # The CLOAD sweep is the DIRECT measurement of the capacitive boundary tax:
    # a receiver hung on a cell output is, to first order, exactly extra CLOAD,
    # and CLOAD is the committed harness's own global -- no new device geometry,
    # so no new PyMS .so build.
    cfgs = []
    for a in sys.argv[1:]:
        if ":" in a:
            v, c = a.split(":")
            cfgs.append((float(v), float(c)))
        else:
            cfgs.append((float(a), 2.0))
    for lvl, cl in cfgs or [(1.0, 2.0), (1.2, 2.0), (1.5, 2.0)]:
        VIN = lvl
        shm.CLOAD = cl
        key = "vin%03d_cl%03d" % (int(round(lvl * 100)), int(round(cl * 10)))
        print("\n========== VIN = %.2f V  CLOAD = %.2f fF ==========" % (lvl, cl))
        shm.stage_calib()
        shutil.copy(os.path.join(HERE, "sw_calib.cir.prn"),
                    os.path.join(HERE, "sw_calib_%s.cir.prn" % key))
        z = shm.stage_probe(DESIGN)
        if z is None:
            print("PROBE FOUND NO ZERO at VIN=%.2f CL=%.2f -- row abandoned" % (lvl, cl))
            continue
        suf = "z_%s" % key
        shm.stage_hop(DESIGN, z, suffix=suf)
        # report() writes into HERE/sweep_rows.json keyed by `key`
        shm.report(DESIGN, z, suffix=suf, key=key)
        r = json.load(open(os.path.join(HERE, "sweep_rows.json")))[key]
        m = shm.parse_mt0(os.path.join(
            HERE, "sw_%s_%s.cir.mt0" % (DESIGN, suf)))
        r["VIN_V"] = lvl
        r["CLOAD_fF"] = cl
        r["true_zero_ps"] = z
        r["timing_convention"] = "TRUE ZCS (committed amended protocol)"
        # raw data-source (gate-drive) cost of the boundary, t0-referenced
        f = 1e15
        for tag in ("qih", "eih", "qil"):
            zz = m["%s_Z" % tag.upper()]
            r["raw_%s_D_fC_or_fJ" % tag] = (m["%s_D" % tag.upper()] - zz) * f
        rows[key] = r
        json.dump(rows, open(out, "w"), indent=1)
        print("ROW %s: VBEND %.6f  E_hop %.4f fJ  outs %s"
              % (key, r["VBEND"], r["E_hop_fJ"],
                 ["%.4f" % v for v in r["outputs_end"]]))
    print("\nwrote %s" % out)


if __name__ == "__main__":
    main()
