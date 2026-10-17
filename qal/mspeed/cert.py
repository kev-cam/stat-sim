#!/usr/bin/env python3
"""Task 1 certification: design point trap_tt92_d3 (s=1) Xyce vs VACASK,
offline like-for-like, against the PRE_REGISTERED bands.  Writes CERT.json."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mspeed as M

RUNS = M.RUNS
X = os.path.join(RUNS, "s1_tt92_d3_xyce")
V = os.path.join(RUNS, "s1_tt92_d3_vacask")
V6 = os.path.join(RUNS, "s1_tt92_d3_rt1e-06_vacask")
V4 = os.path.join(RUNS, "s1_tt92_d3_rt0.0001_vacask")
COMMITTED = "/usr/local/src/stat-sim/qal/mesh3/runs/trap_tt92_d3/OUT.json"

REPO = os.path.join(M.HERE, "runs")
ox = json.load(open(os.path.join(REPO, "s1_tt92_d3", "OUT_xyce.json")))
ov = json.load(open(os.path.join(REPO, "s1_tt92_d3", "OUT_vacask.json")))
V6 = os.path.join(REPO, "s1_tt92_d3_rt1e-06")
V4 = os.path.join(REPO, "s1_tt92_d3_rt0.0001")
oc = json.load(open(COMMITTED))
R = dict(bands_from="PRE_REGISTERED.json certification_task1.acceptance_bands_PRE_STATED")

def g(o, *ks):
    for k in ks:
        o = o[str(k)] if isinstance(o, dict) and str(k) in o else o[k]
    return o

# ---- anchor: this study's Xyce run vs the committed mesh3 row (same deck, same binary)
anc = {}
for k in range(1, 7):
    for n in (2, 3, 4):
        a, b = g(ox, "links", k, n), g(oc, "links", k, n)
        anc["commit_raw_%d_%d" % (k, n)] = (a["commit_raw_ps"], b["commit_raw_ps"])
        anc["width_%d_%d" % (k, n)] = (a["0mV"]["width_ps"], b["0mV"]["width_ps"])
anc_worst = max(abs(x - y) for x, y in anc.values())
R["anchor_xyce_vs_committed"] = dict(
    worst_abs_delta_ps=anc_worst,
    acceptance_equal=(ox["acceptance"]["worst_margin_at_commit_mV"] == oc["acceptance"]["worst_margin_at_commit_mV"]
                      and ox["acceptance"]["worst_overlap_ps"] == oc["acceptance"]["worst_overlap_ps"]),
    xyce_here=ox["acceptance"], committed=oc["acceptance"])

# ---- extractor identity: mesh3.extract on the SAME Xyce prn vs mspeed.extract
S = dict(wave="trap", tt=92.0, T=276.0, d=3, pat="P0", rs=0.001, tend=1932.0, crestoff=138.0, nb=6)
m3o = M.m3.extract(X, S, keep_prn=True)
os.rename(os.path.join(X, "OUT.json"), os.path.join(X, "OUT_mesh3extract.json"))
idn = {}
for k in range(1, 7):
    for n in (2, 3, 4):
        a, b = m3o["links"][k][n], g(ox, "links", k, n)
        idn["commit_raw_%d_%d" % (k, n)] = (a["commit_raw_ps"], b["commit_raw_ps"])
        idn["die_%d_%d" % (k, n)] = (a.get("die_ps"), b.get("die_ps"))
        idn["width_%d_%d" % (k, n)] = (a["0mV"]["width_ps"], b["0mV"]["width_ps"])
for k in range(1, 6):
    for n in (2, 3, 4):
        a, b = m3o["handoff"][k][n], g(ox, "handoff", k, n)
        idn["ovl_%d_%d" % (k, n)] = (a["overlap_ps"], b["overlap_ps"])
        idn["mH_%d_%d" % (k, n)] = (a["margin_at_commit_mV"]["HIGH"], b["margin_at_commit_mV"]["HIGH"])
        idn["mL_%d_%d" % (k, n)] = (a["margin_at_commit_mV"]["LOW"], b["margin_at_commit_mV"]["LOW"])
R["extractor_identity_mesh3_vs_mspeed_same_prn"] = dict(
    n=len(idn), n_differ=sum(1 for x, y in idn.values() if x != y),
    acceptance_equal=(m3o["acceptance"] == ox["acceptance"]), value_equal=(m3o["value"]["n_fail"] == ox["value"]["n_fail"]))

# ---- cross-engine rows
rows, viol = {}, []
def row(name, xv, vv, band_abs=None, band_rel=None, unit=""):
    dlt = None if (xv is None or vv is None) else vv - xv
    ok = None
    if dlt is not None:
        lim = 0.0
        if band_abs is not None:
            lim = max(lim, band_abs)
        if band_rel is not None:
            lim = max(lim, band_rel * abs(xv))
        ok = abs(dlt) <= lim
        if not ok:
            viol.append(name)
    rows[name] = dict(xyce=xv, vacask=vv, delta=(None if dlt is None else round(dlt, 4)),
                      rel=(None if (dlt is None or not xv) else round(dlt / xv, 5)), PASS=ok, unit=unit)

for k in range(1, 7):
    for n in (2, 3, 4):
        a, b = g(ox, "links", k, n), g(ov, "links", k, n)
        row("commit_raw_L%d_w%d" % (k, n), a["commit_raw_ps"], b["commit_raw_ps"], band_abs=1.0, unit="ps")
        row("die_L%d_w%d" % (k, n), a.get("die_ps"), b.get("die_ps"), band_abs=1.0, unit="ps")
        row("width0_L%d_w%d" % (k, n), a["0mV"]["width_ps"], b["0mV"]["width_ps"], band_abs=1.0, unit="ps")
for k in range(1, 6):
    for n in (2, 3, 4):
        a, b = g(ox, "handoff", k, n), g(ov, "handoff", k, n)
        row("overlap_L%d_w%d" % (k, n), a["overlap_ps"], b["overlap_ps"], band_abs=1.0, unit="ps")
        for pol in ("HIGH", "LOW"):
            row("margin_%s_L%d_w%d" % (pol, k, n), a["margin_at_commit_mV"][pol], b["margin_at_commit_mV"][pol],
                band_abs=5.0, band_rel=0.01, unit="mV")
row("asymptotic_eye_w3", g(ox, "erosion", 3)["asymptotic_width_ps"], g(ov, "erosion", 3)["asymptotic_width_ps"], band_abs=1.0, unit="ps")
row("restored_HIGH_min", ox["value"]["restored_HIGH_min_V"], ov["value"]["restored_HIGH_min_V"], band_abs=0.005, unit="V")
R["value_identical"] = (ox["value"]["checked"] == ov["value"]["checked"] == 144 and ox["value"]["n_fail"] == ov["value"]["n_fail"] == 0)
R["erosion_sign"] = (g(ox, "erosion", 3)["sign"], g(ov, "erosion", 3)["sign"])
for k in range(1, 7):
    a, b = g(ox, "charge_spec_reported_not_gated", k), g(ov, "charge_spec_reported_not_gated", k)
    for q in ("Q_rise_fC", "Q_hold_fC", "Q_fall_fC", "E_rise_fJ", "E_hold_fJ", "E_fall_fJ", "E_cycle_net_fJ"):
        row("%s_bank%d" % (q, k), a[q], b[q], band_rel=0.02, band_abs=0.5, unit=q[-2:])

# ---- waveform offsets on the 0.10 ps grid (rails: band 5 mV max; cells: reported)
tx, cx = M.load_native_prn(os.path.join(X, "c_s1_tt92_d3.cir.prn"))
tv, cv = M.load_native_raw(os.path.join(V, "tr.raw"))
nx, GX = M.to_grid(tx, {k: v for k, v in cx.items() if k.startswith("V(PH")}, 1932.0)
nv, GV = M.to_grid(tv, {k: v for k, v in cv.items() if k.startswith("V(PH")}, 1932.0)
wf = {}
for k in range(1, 7):
    a, b = GX["V(PH%d)" % k], GV["V(PH%d)" % k]
    n = min(len(a), len(b))
    dd = [abs(a[i] - b[i]) for i in range(n)]
    wf["rail%d" % k] = dict(max_mV=round(1000 * max(dd), 4), rms_mV=round(1000 * math.sqrt(sum(x * x for x in dd) / n), 4))
rail_ok = all(w["max_mV"] <= 5.0 and w["rms_mV"] <= 0.5 for w in wf.values())
if not rail_ok:
    viol.append("rail_waveforms")
R["rail_waveforms"] = dict(rows=wf, PASS=rail_ok, band="max 5 mV, rms 0.5 mV")
onames = [k for k in cx if k.startswith("V(O")]
nx, GX = M.to_grid(tx, {k: cx[k] for k in onames}, 1932.0)
nv, GV = M.to_grid(tv, {k: cv[k] for k in onames}, 1932.0)
cmax, crms = 0.0, []
for k in onames:
    a, b = GX[k], GV[k]
    n = min(len(a), len(b))
    dd = [abs(a[i] - b[i]) for i in range(n)]
    cmax = max(cmax, max(dd))
    crms.append(math.sqrt(sum(x * x for x in dd) / n))
R["cell_waveforms_reported"] = dict(n_signals=len(onames), max_abs_mV=round(1000 * cmax, 3),
                                    rms_mV_median=round(1000 * sorted(crms)[len(crms) // 2], 4),
                                    rms_mV_max=round(1000 * max(crms), 4))

# ---- same-instant margin re-sampling: VACASK outputs at XYCE's commit instants
TR = M.TRIPF
same = {}
GXr = M.to_grid(tx, {k: cx[k] for k in cx if k.startswith("V(PH")}, 1932.0)[1]
GVr = M.to_grid(tv, {k: cv[k] for k in cv if k.startswith("V(PH")}, 1932.0)[1]
worst_same = 0.0
for k in range(1, 6):
    for n in (2, 3, 4):
        tc = g(ox, "handoff", k, n)["t_commit_rx_ps"]
        a = int(tc / M.GRID)
        bb = M.bits(M.PATS["P0"], k, 3, n, 3)
        rx = M.rxbank(k)
        for eng, G, Gr in (("xyce", GX, GXr), ("vacask", GV, GVr)):
            t_, _ = TR(Gr["V(PH%d)" % rx][a])
            ms = {"HIGH": 1e9, "LOW": 1e9}
            for i in range(8):
                v = G["V(O%d_3_%d)" % (k, i)][a]
                mm = 1000.0 * (1.0 if bb[i] else -1.0) * (v - t_)
                ms["HIGH" if bb[i] else "LOW"] = min(ms["HIGH" if bb[i] else "LOW"], mm)
            same.setdefault("L%d_w%d" % (k, n), {})[eng] = {p: round(v, 2) for p, v in ms.items()}
        e = same["L%d_w%d" % (k, n)]
        for p in ("HIGH", "LOW"):
            worst_same = max(worst_same, abs(e["vacask"][p] - e["xyce"][p]) / abs(e["xyce"][p]))
R["margin_same_instant_resample"] = dict(worst_rel=round(worst_same, 5), rows=same,
                                         note="VACASK and Xyce outputs both sampled at XYCE's commit instant; separates "
                                              "commit-instant shift from waveform difference")

# ---- Xyce in-engine integrator (mt0, +1 ps FIND convention) vs offline trapz (nominal and +1 ps windows)
mt0 = M.m3.parse_mt0(os.path.join(X, "c_s1_tt92_d3.cir.mt0"))
integ = {}
worst_int = 0.0
for k in range(1, 7):
    iq = [-x for x in cx["I(VPH%d)" % k]]
    pw = [-a * b for a, b in zip(cx["V(PH%d)" % k], cx["I(VPH%d)" % k])]
    for n in (2, 3, 4):
        ts = M.slot(k, n, 276.0, 92.0)
        qr_mt0 = (mt0["QPH%dR%d" % (k, n)] - mt0["QPH%dT%d" % (k, n)]) * 1e15
        er_mt0 = (mt0["EPH%dR%d" % (k, n)] - mt0["EPH%dT%d" % (k, n)]) * 1e15
        qr_off1 = M.trapz_native(tx, iq, ts + 1.0, ts + 93.0) * 1e3
        qr_off0 = M.trapz_native(tx, iq, ts, ts + 92.0) * 1e3
        er_off1 = M.trapz_native(tx, pw, ts + 1.0, ts + 93.0) * 1e3
        integ["bank%d_w%d" % (k, n)] = dict(Q_rise_mt0_fC=round(qr_mt0, 4), Q_rise_offline_shifted1ps_fC=round(qr_off1, 4),
                                            Q_rise_offline_nominal_fC=round(qr_off0, 4),
                                            E_rise_mt0_fJ=round(er_mt0, 4), E_rise_offline_shifted1ps_fJ=round(er_off1, 4))
        worst_int = max(worst_int, abs(qr_off0 / qr_mt0 - 1))
R["xyce_integrator_vs_offline"] = dict(
    worst_rel_like_for_like=round(worst_int, 6), PASS=worst_int <= 0.01, rows=integ,
    finding="mt0 reads (deck convention AT = nominal + 1.0 ps LAG_PS) equal the offline trapezoid over the NOMINAL "
            "window to ~1e-5: the +1 ps convention exactly cancels the measured ~0.9 ps FIND-AT early sample "
            "(SKEPTIC Amendment 3). The +1 ps-shifted offline window is NOT the like-for-like (1-2.5% off).")

# ---- reltol ladder on VACASK
lad = {}
for tagp, pth in (("1e-6", V6), ("1e-4", V4)):
    f = os.path.join(pth, "OUT_vacask.json")
    if not os.path.exists(f):
        continue
    o6 = json.load(open(f))
    dc, dm = 0.0, 0.0
    for k in range(1, 7):
        for n in (2, 3, 4):
            dc = max(dc, abs(g(o6, "links", k, n)["commit_raw_ps"] - g(ov, "links", k, n)["commit_raw_ps"]))
    for k in range(1, 6):
        for n in (2, 3, 4):
            for p in ("HIGH", "LOW"):
                a, b = g(ov, "handoff", k, n)["margin_at_commit_mV"][p], g(o6, "handoff", k, n)["margin_at_commit_mV"][p]
                dm = max(dm, abs(b - a) / abs(a))
    lad[tagp] = dict(max_commit_shift_ps=round(dc, 3), max_margin_rel=round(dm, 5),
                     worst_margin=o6["acceptance"]["worst_margin_at_commit_mV"], wall_s=o6.get("wall_s"))
R["vacask_reltol_ladder_vs_1e-5"] = dict(rows=lad, band="1e-6 vs 1e-5: commit < 0.3 ps, margin < 0.2%",
                                        PASS=(lad.get("1e-6", {}).get("max_commit_shift_ps", 9) < 0.3 and
                                              lad.get("1e-6", {}).get("max_margin_rel", 9) < 0.002))

R["wall_s"] = dict(xyce=ox.get("wall_s"), vacask=ov.get("wall_s"),
                   ratio_xyce_over_vacask=(round(ox["wall_s"] / ov["wall_s"], 2) if ox.get("wall_s") and ov.get("wall_s") else None),
                   loadavg_xyce_end=ox.get("loadavg_at_end"), loadavg_vacask_end=ov.get("loadavg_at_end"),
                   native_points=(ox.get("n_native_points"), ov.get("n_native_points")))
R["rows"] = rows
R["violations"] = viol
R["n_rows"] = len(rows)
R["summary"] = dict(
    commit_raw_worst_ps=max(abs(v["delta"]) for k, v in rows.items() if k.startswith("commit_raw")),
    die_worst_ps=max(abs(v["delta"]) for k, v in rows.items() if k.startswith("die")),
    width_worst_ps=max(abs(v["delta"]) for k, v in rows.items() if k.startswith("width0")),
    overlap_worst_ps=max(abs(v["delta"]) for k, v in rows.items() if k.startswith("overlap")),
    margin_worst_rel=max(abs(v["rel"]) for k, v in rows.items() if k.startswith("margin")),
    margin_worst_mV=max(abs(v["delta"]) for k, v in rows.items() if k.startswith("margin")),
    charge_energy_worst_rel=max(abs(v["rel"]) for k, v in rows.items() if k[:1] in "QE" and v["rel"] is not None),
    acceptance=dict(xyce=ox["acceptance"], vacask=ov["acceptance"]))
json.dump(R, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "CERT.json"), "w"), indent=1)
print(json.dumps({k: R[k] for k in ("anchor_xyce_vs_committed", "extractor_identity_mesh3_vs_mspeed_same_prn", "summary",
                                    "rail_waveforms", "cell_waveforms_reported", "xyce_integrator_vs_offline",
                                    "vacask_reltol_ladder_vs_1e-5", "wall_s", "violations", "value_identical", "erosion_sign")}, indent=1,
                 default=str)[:6000])
print("same-instant worst rel:", R["margin_same_instant_resample"]["worst_rel"])
