"""p2 driver.  Rows run in parallel; every deck-building parameter travels in the
spec dict, so there is no module global for a reused worker to leak (the exact
shape of Phase 1's AMENDMENT A9 bug), and w.audit() re-reads every generated
netlist against the spec that asked for it before Xyce is ever invoked.

usage:  python3 drive.py <stage> [args]
"""
import json, os, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W
import chain as C

HERE = W.HERE
CB = {}


def cb(wire, uniform=False, restore=False):
    """The MEASURED in-situ PER-BANK rail capacitance (AMENDMENTS P2 + P4): the
    two-ramp-rate-separated C_TRUE, NOT the contaminated slow-ramp secant.  The
    restoring bank (AMENDMENT P9) carries its own calibration file."""
    nm = "CBANK_INSITU_RESTORE.json" if restore else "CBANK_INSITU.json"
    if nm not in CB:
        CB[nm] = json.load(open(os.path.join(HERE, nm)))
    d = CB[nm][wire]
    v = [d["bank%d" % k]["C_TRUE_fF"] for k in range(1, W.NBANK + 1)]
    if uniform:
        return [sum(v) / len(v)] * len(v)
    return v


def base(T, wire="W2", l_nh=15.0, vgh=2.4, m=10.0, uniform=False, **kw):
    return W.spec(T, wire=wire, l_nh=l_nh, vgh=vgh, m=m,
                  cbank_fF=cb(wire, uniform, kw.get("restore", False)), **kw)


def tag_of(wire, l_nh, vgh, m, T, extra=""):
    return "%s_L%g_g%g_m%g_T%g%s" % (wire, l_nh, vgh * 1000, m, T, extra)


def job(args):
    wire, l_nh, vgh, m, T, tzq, extra, kw = args
    tg = tag_of(wire, l_nh, vgh, m, T, extra)
    b = base(T, wire=wire, l_nh=l_nh, vgh=vgh, m=m, **kw)
    try:
        r = C.row(tg, b, tzq=tzq, verbose=False)
        r["returns_enabled"] = b.get("returns", True)
    except Exception as e:                                             # noqa
        r = dict(tag=tg, FAILED="EXC %s: %s" % (type(e).__name__, e),
                 T_ps=T, wire=wire)
    return r


def par(jobs, nw=4):
    out = []
    with ProcessPoolExecutor(max_workers=nw) as ex:
        fs = {ex.submit(job, j): j for j in jobs}
        for f in as_completed(fs):
            r = f.result()
            out.append(r)
            print(C.brief(r), flush=True)
    return sorted(out, key=lambda r: (r["wire"], r["T_ps"]))


def save(name, rows):
    p = os.path.join(HERE, name)
    old = json.load(open(p)) if os.path.exists(p) else {}
    for r in rows:
        old[r["tag"]] = r
    json.dump(old, open(p, "w"), indent=1)
    print("wrote %s (%d rows total)" % (name, len(old)), flush=True)
    return old


if __name__ == "__main__":
    stage = sys.argv[1]
    W.check_logic_against_prereg()

    if stage == "ledger":
        # the ONE full H=4 deck WITH the return cuts, for K5/IZQ and the energy
        # ledger (AMENDMENT P5).  Its zeros come from the salvaged probe set.
        T = float(sys.argv[2])
        zq = json.load(open(os.path.join(HERE, "ZQ_W2_L15_g2400_m10.json")))
        b = base(T)
        r = C.row(tag_of("W2", 15.0, 2.4, 10.0, T, "_led"), b,
                  tzr=zq["tzr"], tzq=zq["tzq"], verbose=True, probe_rise=False)
        print(C.brief(r), flush=True)
        save("ROWS_LEDGER.json", [r])

    elif stage == "seed":
        # ONE full row at the primary point: probes its own rises AND returns,
        # so the return zeros exist to be reused (AMENDMENT P3).
        T = float(sys.argv[2]) if len(sys.argv) > 2 else 250.0
        b = base(T)
        t0 = time.monotonic()
        r = C.row(tag_of("W2", 15.0, 2.4, 10.0, T), b, verbose=True)
        print(C.brief(r), flush=True)
        print("seed row total %.0f s" % (time.monotonic() - t0))
        save("ROWS.json", [r])
        json.dump(dict(tzq=r.get("tzq_ps"), tzr=r.get("tzr_ps"), T=T,
                       wire="W2", l_nh=15.0, vgh=2.4, m=10.0),
                  open(os.path.join(HERE, "ZQ_W2_L15_g2400_m10.json"), "w"),
                  indent=1)

    elif stage == "tsweep":
        Ts = [float(x) for x in sys.argv[2].split(",")]
        jobs = [("W2", 15.0, 2.4, 10.0, T, None, "", dict(returns=False))
                for T in Ts]
        save("ROWS.json", par(jobs, nw=int(sys.argv[3]) if len(sys.argv) > 3 else 4))

    elif stage == "wire":
        T = float(sys.argv[2])
        jobs = [(wr, 15.0, 2.4, 10.0, T, None, "", dict(returns=False))
                for wr in ("W0", "W1", "WL")]
        save("ROWS.json", par(jobs, nw=3))

    elif stage == "alt":
        # m control and the Phase-1 FUNCTIONAL optimum (L = 6 nH, VGH = 2.174)
        Ts = [float(x) for x in sys.argv[2].split(",")]
        jobs = ([("W2", 15.0, 2.4, 1.0, T, None, "", dict(returns=False))
                 for T in Ts]
                + [("W2", 6.0, 2.174, 10.0, T, None, "", dict(returns=False))
                   for T in Ts])
        save("ROWS.json", par(jobs, nw=4))

    elif stage == "sync":
        # AMENDMENT P7: all rails raised together, wave carried by the DATA.
        win = float(sys.argv[2])
        jobs = [(wr, L, g, 10.0, win / 6.0, None, "_sync",
                 dict(returns=False, sync=True, window=win))
                for (wr, L, g) in [("W2", 15.0, 2.4), ("W0", 15.0, 2.4),
                                   ("W1", 15.0, 2.4), ("WL", 15.0, 2.4),
                                   ("W2", 6.0, 2.174)]]
        save("ROWS_SYNC.json", par(jobs, nw=5))

    elif stage == "long":
        # does the SKEWED arrangement compute at ANY beat?
        Ts = [float(x) for x in sys.argv[2].split(",")]
        jobs = [("W2", 15.0, 2.4, 10.0, T, None, "", dict(returns=False))
                for T in Ts]
        save("ROWS.json", par(jobs, nw=len(Ts)))

    elif stage == "rskew":
        # AMENDMENT P9 restoring bank, TRUE SKEWED WAVE.  The question this row
        # exists to answer: can a rail-driven inverter output hold against the
        # 78-83 uA successor crowbar that a pass-gate output could not?
        Ts = [float(x) for x in sys.argv[2].split(",")]
        jobs = [("W2", 15.0, 2.4, 10.0, T, None, "_rst",
                 dict(returns=False, restore=True)) for T in Ts]
        save("ROWS_RESTORE.json", par(jobs, nw=len(Ts)))

    elif stage == "rsync":
        win = float(sys.argv[2])
        jobs = [(wr, 15.0, 2.4, 10.0, win / 6.0, None, "_rstsync",
                 dict(returns=False, sync=True, window=win, restore=True))
                for wr in ("W2", "W0")]
        save("ROWS_RESTORE.json", par(jobs, nw=2))

    elif stage == "rwire":
        T = float(sys.argv[2])
        jobs = [(wr, 15.0, 2.4, 10.0, T, None, "_rst",
                 dict(returns=False, restore=True))
                for wr in ("W0", "W1", "WL")]
        save("ROWS_RESTORE.json", par(jobs, nw=3))

    elif stage == "custom":
        spec_json = (json.load(open(sys.argv[2])) if sys.argv[2].endswith(".json")
                     else json.loads(sys.argv[2]))
        jobs = [(j["wire"], j["l_nh"], j["vgh"], j["m"], j["T"],
                 j.get("tzq"), j.get("extra", ""), j.get("kw", {}))
                for j in spec_json]
        save(sys.argv[4] if len(sys.argv) > 4 else "ROWS.json",
             par(jobs, nw=int(sys.argv[3]) if len(sys.argv) > 3 else 4))
