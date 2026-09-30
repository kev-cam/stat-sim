#!/usr/bin/env python3
"""SKEPTIC's OWN census harness.  Deck generator AND extractor written from
scratch -- it does NOT import sk.py or census.py.  Same physical configuration
(so the numbers are comparable) but an independent code path, so a reproduction
is evidence rather than a re-print.

Extra stage the track does NOT have: `nand2w`, the nand2 family driven at its
TRUE worst-case RISE vector (A=0,B=1, ONE pull-up conducting) instead of the
track's max-DEPTH vector (A=0,B=0, BOTH pull-ups conducting).  For a depth-1
cell with parallel pull-ups the max-depth vector is the max-DRIVE vector, so the
track's 60.0 ps nand2 row is a best-case-drive number.  115 of the 161 block
cells are nand2, so this is load-bearing.

usage: myc.py <tag>      where tag in inv nand2 nand2w nor2 o21ai
"""
import json, math, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
VA = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_sk3")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
           PYMS_VAE_CACHE=CACHE)
PDK = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell"
       "/spice/sg13g2_stdcell.spice")

# census operating point (pre-registered by the track; adopted verbatim so the
# comparison is like-for-like)
DV, LH, TOT, TAIL, CL, VGH = 1.65, 6.0, 120.0, 500.0, 2.0, 1.65
CA = 35.979
T0, RS, EDGE, N = 50.0, 10.0, 2.0, 8
HI = [0, 2, 4, 6]        # these cells' outputs must stay LOW
LO = [1, 3, 5, 7]        # these cells' outputs must follow the rail UP

# tag -> (cell, {input: value} for the RISE case).  The LOW case is the
# complement vector that turns the deepest pull-DOWN on.  Both are re-derived
# here from the truth table I read out of the PDK myself.
CASE = {
    "inv":    ("sg13g2_inv_1",   {"A": 0},                     {"A": 1}),
    "nand2":  ("sg13g2_nand2_1", {"A": 0, "B": 0},             {"A": 1, "B": 1}),
    "nand2w": ("sg13g2_nand2_1", {"A": 0, "B": 1},             {"A": 1, "B": 1}),
    "nor2":   ("sg13g2_nor2_1",  {"A": 0, "B": 0},             {"A": 0, "B": 1}),
    "o21ai":  ("sg13g2_o21ai_1", {"A1": 0, "A2": 0, "B1": 1},  {"A1": 0, "A2": 1, "B1": 1}),
}


# ------------------------------------------------------- PDK subckt extraction
def subckt(cell):
    """read the .subckt VERBATIM out of the PDK and re-emit with the shim's
    device names, plus 0.1 fF on every internal node (the shim zeroes
    ad/as/pd/ps so series-internal nodes would otherwise be capacitance-free)."""
    lines, grab = [], False
    for ln in open(PDK):
        s = ln.strip()
        if s.lower().startswith(".subckt " + cell + " "):
            grab = True
        if grab:
            lines.append(s)
            if s.lower().startswith(".ends"):
                break
    assert lines, cell
    ports = lines[0].split()[2:]
    devs = []
    for s in lines[1:-1]:
        p = s.split()
        nm, d, g, sr, b = p[0], p[1], p[2], p[3], p[4]
        kv = dict(x.split("=") for x in p[6:] if "=" in x)
        devs.append(dict(name=nm, d=d, g=g, s=sr, b=b, mod=p[5],
                         w=kv["w"], l=kv["l"]))
    out = [".subckt %s %s" % (cell, " ".join(ports))]
    nodes = set()
    for dv in devs:
        nodes |= {dv["d"], dv["s"]}
        out.append("%s %s %s %s %s %s w=%s l=%s"
                   % (dv["name"], dv["d"], dv["g"], dv["s"], dv["b"],
                      dv["mod"], dv["w"], dv["l"]))
    for k, nd in enumerate(sorted(n for n in nodes if n not in ports)):
        typs = {dv["mod"] for dv in devs if nd in (dv["d"], dv["s"])}
        ref = "VDD" if typs == {"sg13_lv_pmos"} else "VSS"
        out.append("CI%d %s %s 0.1f" % (k, nd, ref))
    out.append(".ends")
    return ports, out


def head(cell):
    _, sub = subckt(cell)
    return (['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
             ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17"]
            + sub)


def bank(tag):
    cell, vhi, vlo = CASE[tag]
    ports, _ = subckt(cell)
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    for i in range(N):
        g = "gnh" if i in HI else "gnl"
        vec = vlo if i in HI else vhi          # HI index -> output stays LOW
        conn = []
        for p in ports:
            if p == ports[0]:
                conn.append("o%d" % i)
            elif p == "VDD":
                conn.append("bkb")
            elif p == "VSS":
                conn.append(g)
            else:
                nd = "i%s_%d" % (p, i)
                L.append("VI%s_%d %s 0 %g" % (p, i, nd, DV if vec[p] else 0.0))
                conn.append(nd)
        L.append("XC%d %s %s" % (i, " ".join(conn), cell))
        L.append("CL%d o%d %s %gf" % (i, i, g, CL))
    return L


def sw():
    wn, wp, pk = TOT / 3.0, 2.0 * TOT / 3.0, TOT / 15.0
    return ["XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % wn,
            "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % wp,
            "XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % pk]


def tpred():
    return math.pi * math.sqrt((LH * 1e-9) * (CA / 2.0) * 1e-15) * 1e12


def probe(tag):
    tp, tend = tpred(), T0 + 4.0 * tpred()
    ps, ms = min(0.05, tp / 3000.0), min(0.10, tp / 1500.0)
    cell = CASE[tag][0]
    return head(cell) + [
        "CA bka 0 %gf" % CA, "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)" % (T0 - EDGE, T0, VGH, tend * 2, VGH),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0)" % (VGH, T0 - EDGE, VGH, T0, tend * 2),
        "VPK pk 0 0", "LT bka mid %gn" % LH, "RT mid sw %g" % RS,
    ] + sw() + bank(tag) + [
        ".ic V(bka)=%g V(bkb)=0" % DV,
        ".print tran I(LT) V(bkb) V(bka) V(sw)",
        ".tran %gp %gp 0 %gp" % (ps, tend, ms), ".end"]


def hop(tag, thalf):
    tp = tpred()
    to = T0 + thalf
    tend = to + TAIL
    ps, ms = min(0.05, tp / 3000.0), min(0.10, tp / 1500.0)
    cell = CASE[tag][0]
    out = head(cell) + [
        "CA bka 0 %gf" % CA, "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
        % (T0 - EDGE, T0, VGH, to, VGH, to + EDGE),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
        % (VGH, T0 - EDGE, VGH, T0, to, to + EDGE, VGH),
        "VPK pk 0 PWL(0 0 %gp 0 %gp %g)" % (to + EDGE, to + 2 * EDGE, VGH),
        "LT bka mid %gn" % LH, "RT mid sw %g" % RS,
    ] + sw() + bank(tag)
    pr = ["V(bka)", "V(bkb)", "V(sw)", "I(LT)"] + ["V(o%d)" % i for i in range(N)]
    for k in range(0, len(pr), 8):
        out.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    out += [".ic V(bka)=%g V(bkb)=0" % DV,
            ".tran %gp %gp 0 %gp" % (ps, tend, ms), ".end"]
    return out, to, tend


# ------------------------------------------------------------- my own extractor
def load(path):
    hdr, rows = None, []
    for ln in open(path):
        p = ln.split()
        if hdr is None and p and p[0].lower() == "index":
            hdr = [h.upper() for h in p]
            continue
        if hdr and p and p[0][0].isdigit():
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                pass
    ti = hdr.index("TIME")
    t = [r[ti] * 1e12 for r in rows]
    return hdr, rows, t


def colof(hdr, nm):
    n = nm.upper()
    for i, h in enumerate(hdr):
        if h == n:
            return i
    for i, h in enumerate(hdr):
        if n in h:
            return i
    raise KeyError(nm)


def interp(t, y, x):
    if x <= t[0]:
        return y[0]
    for k in range(1, len(t)):
        if t[k] >= x:
            a, b = t[k - 1], t[k]
            f = 0.0 if b == a else (x - a) / (b - a)
            return y[k - 1] + f * (y[k] - y[k - 1])
    return y[-1]


def zero_after_peak(path):
    hdr, rows, t = load(path)
    c = colof(hdr, "I(LT)")
    i = [r[c] for r in rows]
    ip = max(range(len(i)), key=lambda k: i[k])
    for k in range(ip + 1, len(i)):
        if i[k] <= 0.0 < i[k - 1]:
            f = i[k - 1] / (i[k - 1] - i[k])
            return t[k - 1] + f * (t[k] - t[k - 1]), i[ip] * 1e6
    return None, i[ip] * 1e6


def analyse(path, to, tend):
    hdr, rows, t = load(path)
    vb = [r[colof(hdr, "V(bkb)")] for r in rows]
    oc = [colof(hdr, "V(o%d)" % i) for i in range(N)]
    tE = tend - 5.0
    vbe = interp(t, vb, tE)
    vbpk = max(vb)
    # C1 VALUE at the END of the window: correct side of half the end rail
    vend = {i: interp(t, [r[oc[i]] for r in rows], tE) for i in range(N)}
    val = {}
    for i in range(N):
        want_hi = i in LO
        v = vend[i]
        val[i] = dict(want_hi=want_hi, v=v,
                      ok=bool(v > 0.5 * vbe if want_hi else v < 0.5 * vbe))
    # t_valid_f : ALL 8 simultaneously within f of the INSTANTANEOUS rail and
    # staying so to the end of the window.
    def tvalid(f):
        gf = None
        for k in range(len(t)):
            if t[k] < T0 or vb[k] < 0.05:
                continue
            ok = True
            for i in range(N):
                v = rows[k][oc[i]]
                s = (1.0 - v / vb[k]) if i in HI else (v / vb[k])
                if s < f:
                    ok = False
                    break
            if ok and gf is None:
                gf = t[k]
            elif not ok:
                gf = None
        return None if gf is None else gf - T0
    send = {}
    for i in range(N):
        v = vend[i]
        send[i] = 100.0 * ((1.0 - v / vbe) if i in HI else (v / vbe))
    return dict(VBEND=vbe, VBPK=vbpk,
                t_valid80_ps=tvalid(0.80), t_valid90_ps=tvalid(0.90),
                t_valid95_ps=tvalid(0.95),
                C1_VALUE=all(x["ok"] for x in val.values()),
                value=val, s_end=send, v_end=vend)


def run(fn, lines, timeout=2400):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    if not os.path.exists(p + ".prn"):
        return None, "FAIL %s" % r.stdout[-500:]
    return p, "ok %.0fs" % (time.monotonic() - t)


if __name__ == "__main__":
    tag = sys.argv[1]
    t0 = time.monotonic()
    pp, m = run("p_%s.cir" % tag, probe(tag))
    print("probe", m, flush=True)
    assert pp, m
    tz, ipk = zero_after_peak(pp + ".prn")
    print("true zero %.5f ps -> t_hop %.5f ps, Ipk %.3f uA" % (tz, tz - T0, ipk),
          flush=True)
    hl, to, tend = hop(tag, tz - T0)
    hp, m = run("h_%s.cir" % tag, hl)
    print("hop", m, flush=True)
    assert hp, m
    r = analyse(hp + ".prn", to, tend)
    r.update(tag=tag, cell=CASE[tag][0], vec_rise=CASE[tag][1],
             vec_fall=CASE[tag][2], t_hop_ps=tz - T0, probe_Ipk_uA=ipk,
             dv=DV, L_nH=LH, TG_um=TOT, CL_fF=CL, tail_ps=TAIL, VGH=VGH,
             wall_s=round(time.monotonic() - t0, 1))
    r["t_level_ps"] = (max(r["t_hop_ps"], r["t_valid90_ps"])
                       if r["t_valid90_ps"] is not None else None)
    json.dump(r, open(os.path.join(HERE, "MYC_%s.json" % tag), "w"), indent=1)
    print("VBEND %.6f  t_hop %.4f  t_valid90 %s  t_level %s  C1 %s"
          % (r["VBEND"], r["t_hop_ps"], r["t_valid90_ps"], r["t_level_ps"],
             r["C1_VALUE"]), flush=True)
    print("s_end", {k: round(v, 2) for k, v in r["s_end"].items()}, flush=True)
