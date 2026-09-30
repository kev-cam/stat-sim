#!/usr/bin/env python3
"""One sweep POINT end to end: probe the true zeros, run the row, extract it,
escalate the beat if it fails.  One process per N, so different N values run
concurrently while each N's own probe sequence stays strictly sequential (the
committed protocol requires predecessors cut at their OWN measured zeros).

usage: drive.py <N> [--dv 1.65] [--H 4] [--nb 3] [--wmul 1.0] [--mstep S]
                    [--T T0] [--extra TAG] [--noescalate]
"""
import json, math, os, subprocess, sys, time
import wb, wbx

HERE = os.path.dirname(os.path.abspath(__file__))
MARGIN_PS = 73.5        # = committed dV=1.65 working row's T minus its own t_zcs


def t0_of(n, mult=1.0):
    pred = wb.TZ8 * math.sqrt(n / 8.0)
    return math.ceil((pred + MARGIN_PS) * mult / 10.0) * 10.0


def main():
    a = sys.argv[1:]
    n = int(a[0])
    kw = dict(dv=1.65, H=4, nb=3, wmul=1.0, mstep=None, T=None, extra="",
              noescalate=False, rnd=0)
    i = 1
    while i < len(a):
        if a[i] == "--noescalate":
            kw["noescalate"] = True; i += 1; continue
        k = a[i].lstrip("-"); v = a[i + 1]; i += 2
        kw[k] = (v if k == "extra" else
                 int(v) if k in ("H", "nb", "rnd") else float(v))
    dv, H, nb, wmul = kw["dv"], int(kw["H"]), int(kw["nb"]), kw["wmul"]
    mstep, extra = kw["mstep"], kw["extra"]

    # PER-GATE FIXTURE CONTROL: a pseudo-random pattern with the SAME number of
    # HIGH inputs as the tiled pattern, so the activity fraction is unchanged
    # and only the ARRANGEMENT differs.  Declared in PRE_REGISTERED.json as the
    # mitigation for the two-electrical-class caveat.
    P = None
    if kw["rnd"]:
        import random
        rg = random.Random(kw["rnd"])
        nh = sum(wb.PAT8) * (n // 8)
        P = [1] * nh + [0] * (n - nh)
        rg.shuffle(P)
        if not extra:
            extra = "rnd%d" % kw["rnd"]

    Ts = [kw["T"]] if kw["T"] else [t0_of(n), t0_of(n, 1.25), t0_of(n, 1.6)]
    if kw["noescalate"]:
        Ts = Ts[:1]
    out = dict(N=n, dv=dv, H=H, nb=nb, wmul=wmul, mstep=mstep, extra=extra,
               attempts=[])
    t_start = time.monotonic()
    for att, T in enumerate(Ts):
        print("[N=%d] attempt %d  T=%g ps" % (n, att, T), flush=True)
        zf = "zeros_n%d_dv%g_T%g_H%d_nb%d%s%s.json" % (
            n, dv * 1000, T, H, nb, ("_w%g" % wmul) if wmul != 1.0 else "",
            ("_rnd%d" % kw["rnd"]) if kw["rnd"] else "")
        zp = os.path.join(HERE, zf)
        if os.path.exists(zp):
            z = json.load(open(zp))
            print("[N=%d] reusing %s" % (n, zf), flush=True)
        else:
            tp = time.monotonic()
            z = wb.do_probe(n, dv, T, H, nb=nb, wmul=wmul, P=P)
            if z is None:
                out["attempts"].append(dict(T=T, status="PROBE_FAIL"))
                break
            z["probe_wall_s"] = round(time.monotonic() - tp, 1)
            open(zp, "w").write(json.dumps(z, indent=1))
        tr = time.monotonic()
        p, S, msg = wb.do_row(n, T, H, dv, "free", z, nb=nb, wmul=wmul,
                              mstep=mstep, extra=extra, P=P)
        wall = round(time.monotonic() - tr, 1)
        if p is None:
            out["attempts"].append(dict(T=T, status="ROW_FAIL", msg=msg,
                                        wall_s=wall))
            print("[N=%d] ROW FAIL: %s" % (n, msg), flush=True)
            break
        r = wbx.row_extract(n, 10.0, T, H, dv, "free", z, p, wmul=wmul, nb=nb,
                            mstep=mstep, wall_s=wall, P=P)
        tag = wb.tag_of(n, T, H, dv, "free", wmul, nb, extra)
        open(os.path.join(HERE, "row_%s.json" % tag), "w").write(
            json.dumps(r, indent=1, default=str))
        A2 = r["A2_functional"]
        print("[N=%d] %s PASS=%s A1=%s A2bare=%s(min %.2f mV) worst90=%.2f%% "
              "t_hop=%.2f Lvl=%s E/gate=%.4f fJ Ipk=%.0f uA Qg=%.2f fC wall=%.0fs"
              % (n, tag, r["PASS"], r["A1_value_all_banks_pass"],
                 A2["PASS_bare"], A2["margin_min_mV"], r["worst_gate_pct"],
                 r["t_hop_rise_ps"], r["LEVEL_TIME_measured_bank2_ps"],
                 r["E_per_gate_headline_fJ"], r["IPK_uA"][2],
                 r["LEDGER"]["Q_gate_MEASURED_fC"], wall), flush=True)
        out["attempts"].append(dict(T=T, status="OK", tag=tag, wall_s=wall,
                                    PASS=r["PASS"],
                                    A1=r["A1_value_all_banks_pass"],
                                    A2=A2["PASS_bare"]))
        if r["PASS"]:
            out["accepted_tag"] = tag
            out["accepted_T"] = T
            out["escalations"] = att
            break
    out["total_wall_s"] = round(time.monotonic() - t_start, 1)
    nm = "POINT_n%d%s%s.json" % (n, ("_w%g" % wmul) if wmul != 1.0 else "",
                                 ("_" + extra) if extra else "")
    open(os.path.join(HERE, nm), "w").write(json.dumps(out, indent=1))
    print("[N=%d] DONE %s" % (n, json.dumps(out.get("attempts"))), flush=True)


if __name__ == "__main__":
    main()
