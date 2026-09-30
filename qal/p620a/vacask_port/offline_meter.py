#!/usr/bin/env python3
"""Engine-neutral offline meter for the tg15p offset table and the RC
metering validation. Reads a Xyce .prn or a VACASK .raw, computes the
committed-measure definitions with ONE shared implementation:
  FIND x AT=t      -> linear interpolation
  MAX x FROM TO    -> max over window (grid points)
  INTEGRAL x       -> trapezoid on the engine's own timegrid
  true zero        -> first interpolated downward zero of I_L after its peak

Usage:
  offline_meter.py tg15p_xyce   <prn>            # -> json on stdout
  offline_meter.py tg15p_vacask <raw>            # -> json on stdout
  offline_meter.py rc_xyce      <prn>
  offline_meter.py rc_vacask    <raw>
"""
import json, sys, math

def read_prn(path):
    names, rows = None, []
    for ln in open(path):
        p = ln.split()
        if not p:
            continue
        if names is None and p[0].lower() == "index":
            names = [c.upper() for c in p]
            continue
        if names is None or p[0].lower().startswith("end"):
            continue
        try:
            rows.append([float(x) for x in p])
        except ValueError:
            continue
    cols = {n: [r[i] for r in rows] for i, n in enumerate(names)}
    return cols

def read_raw(path):
    sys.path.insert(0, "/usr/local/src/VACASK/python")
    from rawfile import rawread
    plot = rawread(path).get()
    out = {}
    for n in plot.names:
        out[n.upper()] = [float(x) for x in plot[n]]
    if "TIME" not in out:
        for n in plot.names:
            if n.lower() in ("time", "t"):
                out["TIME"] = [float(x) for x in plot[n]]
    return out

def interp(t, y, tt):
    for k in range(1, len(t)):
        if t[k] >= tt:
            if t[k] == t[k - 1]:
                return y[k]
            f = (tt - t[k - 1]) / (t[k] - t[k - 1])
            return y[k - 1] + f * (y[k] - y[k - 1])
    return y[-1]

def wmax(t, y, t0, t1):
    return max(v for tt, v in zip(t, y) if t0 <= tt <= t1)

def trapz(t, y, t0=None, t1=None):
    s = 0.0
    for k in range(1, len(t)):
        if t0 is not None and t[k] <= t0:
            continue
        if t1 is not None and t[k - 1] >= t1:
            break
        s += 0.5 * (y[k] + y[k - 1]) * (t[k] - t[k - 1])
    return s

def true_zero(t, i):
    ip = max(range(len(i)), key=lambda k: i[k])
    for k in range(ip + 1, len(i)):
        if i[k] <= 0.0 < i[k - 1]:
            f = i[k - 1] / (i[k - 1] - i[k])
            return t[k - 1] + f * (t[k] - t[k - 1])
    return None

def col(cols, *cands):
    for c in cands:
        if c.upper() in cols:
            return cols[c.upper()]
    raise KeyError("none of %s in %s" % (cands, sorted(cols)[:40]))

def tg15p(cols):
    t = col(cols, "TIME")
    vbka = col(cols, "V(BKA)", "BKA")
    vbkb = col(cols, "V(BKB)", "BKB")
    try:
        il = col(cols, "I(LT)", "LT:FLOW(BR)")
    except KeyError:
        vmid = col(cols, "V(MID)", "MID")
        vsw = col(cols, "V(SW)", "SW")
        il = [(a - b) / 10.0 for a, b in zip(vmid, vsw)]
    TEND = 811.755e-12
    r = {
        "EOUTA": trapz(t, [a * b for a, b in zip(vbka, il)]),
        "EINB":  trapz(t, [a * b for a, b in zip(vbkb, il)]),
        "QTR":   trapz(t, il),
        "VBPK":  wmax(t, vbkb, 50e-12, 816.755e-12),
        "VBEND": interp(t, vbkb, TEND),
        "VAEND": interp(t, vbka, TEND),
        "IPK":   max(il),
        "IZ":    interp(t, il, 316.755e-12),
        "t_zcs_ps": (true_zero(t, il) - 50e-12) * 1e12 if true_zero(t, il) else None,
        "npoints": len(t),
    }
    for k in range(8):
        for nm, tt in (("%dZ", 316.755e-12), ("%dE", TEND)):
            key = "O" + nm % k
            try:
                r[key] = interp(t, col(cols, "V(O%d)" % k, "O%d" % k), tt)
            except KeyError:
                r[key] = None
    return r

def rc(cols):
    t = col(cols, "TIME")
    v = col(cols, "V(N1)", "N1")
    r = {
        "ER_offline": trapz(t, [x * x / 1000.0 for x in v]),
        "V_at_tau": interp(t, v, 1e-9),
        "V_end": v[-1],
        "npoints": len(t),
        "ER_analytic": 0.5e-12 * (1.0 - math.exp(-20.0)),
        "V_at_tau_analytic": math.exp(-1.0),
    }
    r["ER_rel_err"] = r["ER_offline"] / r["ER_analytic"] - 1.0
    for extra in ("V(XER)", "V(P)"):
        if extra in cols:
            r[extra] = cols[extra][-1]
    return r

if __name__ == "__main__":
    mode, path = sys.argv[1], sys.argv[2]
    cols = read_prn(path) if mode.endswith("xyce") else read_raw(path)
    fn = tg15p if mode.startswith("tg15p") else rc
    print(json.dumps(fn(cols), indent=1))
