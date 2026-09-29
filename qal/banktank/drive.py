#!/usr/bin/env python3
"""Job pool for the per-bank-tank sweep.  <= 4 concurrent Xyce jobs (two other
workflows share this 16-core box).  Probes first (sequential inside a given
(m,dv) because each zero depends on the previous one being cut at its own),
different (m,dv) in parallel.  Then the rows."""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
MAXJ = 4


def pool(cmds, maxj=MAXJ, tag=""):
    run, done = [], []
    cmds = list(cmds)
    while cmds or run:
        while cmds and len(run) < maxj:
            name, argv = cmds.pop(0)
            lg = open(os.path.join(HERE, "log_%s.txt" % name), "w")
            p = subprocess.Popen(argv, cwd=HERE, stdout=lg, stderr=subprocess.STDOUT)
            run.append((name, p, lg, time.monotonic()))
            print("[%s] START %s (%d queued)" % (tag, name, len(cmds)), flush=True)
        time.sleep(2.0)
        for e in list(run):
            nm, p, lg, t0 = e
            if p.poll() is not None:
                lg.close()
                run.remove(e)
                done.append((nm, p.returncode))
                print("[%s] DONE  %s rc=%d %.1fs" % (tag, nm, p.returncode,
                                                     time.monotonic() - t0), flush=True)
    return done


def main():
    what = sys.argv[1]
    if what == "probes":
        specs = json.loads(sys.argv[2])       # [[m, dv], ...]
        cmds = [("p_m%g_dv%g" % (m, dv * 1000),
                 [PY, "bt.py", "probe", str(m), str(dv)]) for m, dv in specs]
        pool(cmds, tag="probe")
    elif what == "probesT":
        specs = json.loads(sys.argv[2])       # [[m, dv, T, H], ...]
        cmds = [("pT_m%g_dv%g_T%g_H%d" % (m, dv * 1000, T, H),
                 [PY, "bt.py", "probeT", str(m), str(dv), str(T), str(H)])
                for m, dv, T, H in specs]
        pool(cmds, tag="probeT")
    elif what == "rows":
        specs = json.loads(sys.argv[2])       # [[m,T,H,dv,mode], ...]
        cmds = []
        for m, T, H, dv, mode in specs:
            zf = "zeros_m%g_dv%g_T%g_H%d.json" % (m, dv * 1000, T, H)
            if not os.path.exists(os.path.join(HERE, zf)):
                zf = "zeros_m%g_dv%g.json" % (m, dv * 1000)
            nm = "r_m%g_T%g_H%d_dv%g_%s" % (m, T, H, dv * 1000, mode)
            cmds.append((nm, [PY, "bt.py", "row", str(m), str(T), str(H),
                              str(dv), mode, zf]))
        pool(cmds, tag="row")
    print("POOLDONE", flush=True)


if __name__ == "__main__":
    main()
