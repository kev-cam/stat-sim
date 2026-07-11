#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
"""
hot-spot -- electromigration (EM) current-density screening from SPEF.

Same shape as bfit's `-bfit` flow (recognize a structure in the netlist, replace
it with a smart behavioral model, run any engine): here the "structure" is an
*interconnect wire segment* and the behavioral model is an EM-aware wire that
knows its own geometry (layer, width) and therefore its own current-density
limit. Two products, both driven from the extracted-parasitic SPEF:

  instrument  -- rewrite the SPEF's RC wires as `statsim_em_wire` models (an
                 ammeter-wrapped resistor, or the portable Verilog-A monitor with
                 `--va`) that carry per-segment Imax. Preserves the SPEF node
                 names, so the result back-annotates your design deck OR runs
                 stand-alone with a `--harness`. This is the "replace the wires
                 with smart behavioral models" mode.
  check       -- instrument, simulate (ngspice / Xyce via bfit's drivers, or read
                 a rawfile), reduce each segment's current to (avg, rms, peak),
                 compare to its layer/width Imax, and PRINT EM ALERTS. Exit
                 nonzero if any segment is over limit.
  heatmap     -- the same risk numbers painted onto the layout: a self-contained
                 SVG coloured by J/Jmax, plus a ranked CSV of the worst segments.

Current density is checked the way a foundry states EM: a maximum current per
micron of wire width (metals) or per via cut (vias), for average current (mass
transport / EM proper), rms current (Joule self-heat) and peak current. So for a
segment of width W on layer L, Imax = Jlin[L,kind] * W -- no film thickness
needed, exactly how a sign-off EM checker and the sky130 current-density rules
express it. The per-layer numbers below are *representative* sky130 figures
(order-of-magnitude, per the project's inter-engine ~1% tolerance philosophy);
refine them from the PDK's current-density rules or override with --em-rules.

Geometry (layer, width, length, coordinates) rides in a JSON sidecar next to the
SPEF -- klayout2spef.py emits it (`net_geometry_detail`), and the hand-authored
test/iopad_em.spef carries one so the whole flow runs with no klayout. Without a
sidecar hot-spot still runs, geometry-blind, on a --default-width (loud warning).

Pure-python; `--self-test` exercises the physics, the SPEF pass, instrumentation
and the SVG with no simulator and no klayout.
"""
import os
import re
import sys
import json
import math
import argparse
from dataclasses import dataclass, field

# bfit lives next door; hot-spot reuses its engine-neutral SimDriver contract
# (ngspice/OpenVAF + Xyce) exactly like the rest of stat-sim does.
_BFIT = os.environ.get("BFIT_DIR", "/usr/local/src/sv2ghdl/bfit")
if _BFIT not in sys.path:
    sys.path.insert(0, _BFIT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# EM rules -- per-layer max current-density limits.
#   metal[L][kind]  = amps per micron of drawn WIDTH   (kind in avg|rms|peak)
#   via[V][kind]    = amps per via CUT
# avg  -> DC / mass-transport EM (Black);  rms -> Joule self-heat;  peak -> short pulse.
# A missing kind (value absent) means "not specified by this PDK" -> hot-spot does
# not screen that kind (rather than inventing a number).
#
# THE sky130 TABLE BELOW IS AN ESTIMATE, NOT A FOUNDRY RULE. SkyWater publishes no
# official EM limits for sky130 -- the periphery rules mark electromigration as
# rule x.4 "NC" (not checked by DRC); the only public numbers are community
# cross-section estimates. So these are hot-spot's estimates (Al J~1-2 mA/um^2 x
# layer thickness), fine for a screening demo but NOT sign-off. For REAL foundry
# numbers use a PDK that ships them: `--lef <pdk>_tech.lef` reads DCCURRENTDENSITY
# straight from the LEF (e.g. IHP SG13G2 -> rules/ihp_sg13g2.em.json, real), or
# `--em-rules rules.json`.
# ---------------------------------------------------------------------------
EM_RULES = {
    "metal": {
        "li":   {"avg": 0.31e-3, "rms": 0.72e-3, "peak": 0.79e-3},
        "met1": {"avg": 0.79e-3, "rms": 1.40e-3, "peak": 1.90e-3},
        "met2": {"avg": 0.79e-3, "rms": 1.40e-3, "peak": 1.90e-3},
        "met3": {"avg": 1.02e-3, "rms": 1.90e-3, "peak": 2.60e-3},
    },
    "via": {
        "licon": {"avg": 0.12e-3, "rms": 0.30e-3, "peak": 0.40e-3},
        "mcon":  {"avg": 0.28e-3, "rms": 0.50e-3, "peak": 0.70e-3},
        "via1":  {"avg": 0.28e-3, "rms": 0.50e-3, "peak": 0.70e-3},
        "via2":  {"avg": 0.38e-3, "rms": 0.65e-3, "peak": 0.90e-3},
    },
    "black_n": 2.0,     # Black's-equation current exponent for the relative-MTTF derate
    "_provenance": ("ESTIMATE -- sky130 has no official EM rules (periphery rule x.4 "
                    "is NC / not checked); community cross-section estimate. Use "
                    "--lef or --em-rules for real foundry numbers."),
}


def em_rules_from_lef(path, black_n=2.0):
    """Read REAL per-layer EM limits straight from a LEF tech file's
    `DCCURRENTDENSITY AVERAGE` -- the authoritative-PDK path. Routing layers give
    mA per micron of WIDTH, cut layers give mA per via; hot-spot stores them as
    amps. Only the DC/average (mass-transport) limit lives in LEF -- rms/peak
    (LEF ACCURRENTDENSITY tables) aren't provided by e.g. IHP, so those kinds stay
    unset and are not screened. Point this at the PDK's own tech LEF, e.g.
    IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lef/sg13g2_tech.lef."""
    metal, via, cur, typ = {}, {}, None, None
    for raw in open(path):
        t = raw.split()
        if not t:
            continue
        if t[0] == "LAYER" and len(t) >= 2:
            cur, typ = t[1], None
        elif t[0] == "END":
            cur = typ = None
        elif cur is not None and t[0] == "TYPE" and len(t) >= 2:
            typ = t[1]
        elif cur is not None and t[0] == "DCCURRENTDENSITY" and len(t) >= 3 and t[1] == "AVERAGE":
            try:
                a = float(t[2]) * 1e-3           # mA -> A (per um width / per cut)
            except ValueError:
                continue
            if typ == "ROUTING":
                metal[cur] = {"avg": a}
            elif typ == "CUT":
                via[cur] = {"avg": a}
    if not metal and not via:
        raise SystemExit(f"em_rules_from_lef: no DCCURRENTDENSITY AVERAGE found in {path}")
    return {"metal": metal, "via": via, "black_n": black_n,
            "_provenance": f"REAL -- LEF DCCURRENTDENSITY AVERAGE (DC/mass-transport, "
                           f"mA/um width & mA/via) from {os.path.basename(path)}"}

VIA_LAYERS = ("licon", "mcon", "via1", "via2")
METAL_LAYERS = ("li", "met1", "met2", "met3")
KINDS = ("avg", "rms", "peak")
# minimum-drawn-width fallback (um) when no geometry sidecar is present
DEFAULT_WIDTH = 0.14
DEFAULT_LAYER = "met1"


def load_em_rules(path):
    """Load an EM rules JSON. A file that defines `metal`/`via` REPLACES the
    built-in table (that's the point -- your PDK's numbers, not the sky130
    estimate); set `"extends":"builtin"` to instead layer over the defaults. A
    file with neither key is treated as a partial per-layer override of the
    built-in. Carries a `_provenance` string into the report."""
    if not path:
        return EM_RULES
    doc = json.load(open(path))
    if "metal" not in doc and "via" not in doc:                 # partial override
        out = {"metal": {k: dict(v) for k, v in EM_RULES["metal"].items()},
               "via": {k: dict(v) for k, v in EM_RULES["via"].items()},
               "black_n": doc.get("black_n", EM_RULES["black_n"]),
               "_provenance": f"built-in sky130 estimate + overrides from {os.path.basename(path)}"}
        for grp in ("metal", "via"):
            for lyr, kinds in (doc.get(grp) or {}).items():
                out[grp].setdefault(lyr, {}).update(kinds)
        return out
    out = {"metal": {k: dict(v) for k, v in doc.get("metal", {}).items()},
           "via": {k: dict(v) for k, v in doc.get("via", {}).items()},
           "black_n": doc.get("black_n", EM_RULES["black_n"]),
           "_provenance": doc.get("_provenance", f"user rules {os.path.basename(path)}")}
    if doc.get("extends") == "builtin":
        for grp in ("metal", "via"):
            merged = {k: dict(v) for k, v in EM_RULES[grp].items()}
            merged.update(out[grp])
            out[grp] = merged
    return out


def imax(layer, kind, width_um=0.0, cuts=0, rules=EM_RULES):
    """The current limit (amps) for one segment: Jlin*W for a metal, Jcut*N for a
    via. Returns None for an unknown layer OR a kind this PDK doesn't specify
    (e.g. IHP gives only avg) -- an unscreened kind, not a zero limit."""
    if layer in rules.get("metal", {}):
        j = rules["metal"][layer].get(kind)
        return None if j is None else j * max(width_um, 0.0)
    if layer in rules.get("via", {}):
        j = rules["via"][layer].get(kind)
        return None if j is None else j * max(cuts, 0)
    return None


# ---------------------------------------------------------------------------
# Segment-level SPEF pass. spef.py collapses a net to (c_wire, r_wire) -- the
# right product for the nvc load taps -- but EM fails *per segment* (the narrow
# neck goes first), so hot-spot keeps every *RES row with its nodes and id.
# ---------------------------------------------------------------------------
_UNIT = {"OHM": 1.0, "KOHM": 1e3, "MOHM": 1e6,
         "F": 1.0, "MF": 1e-3, "UF": 1e-6, "NF": 1e-9, "PF": 1e-12, "FF": 1e-15}


@dataclass
class Segment:
    net: str
    sid: str            # *RES id within the net
    n1: str             # SPEF node names (net-internal)
    n2: str
    r: float            # ohms
    layer: str = ""     # metal or via layer; "" = geometry-blind
    width: float = 0.0  # um  (metals)
    length: float = 0.0 # um
    cuts: int = 0       # via cut count
    x1: float = 0.0; y1: float = 0.0; x2: float = 0.0; y2: float = 0.0
    imax: dict = field(default_factory=dict)   # {kind: amps}
    is_via: bool = False                       # set by set_limits (rules-aware)

    def set_limits(self, rules):
        # via-ness comes from the active ruleset (any PDK's via names) or a cut
        # count -- NOT a hardcoded sky130 list, so IHP Via1/Via2 classify too.
        self.is_via = (self.layer in rules.get("via", {})) or (self.cuts > 0)
        self.imax = {k: imax(self.layer, k, self.width, self.cuts, rules) for k in KINDS}


def parse_spef_segments(text):
    """{net: {"segs":[Segment(r only)], "caps":[(node,val)]}} keeping every *RES
    row. Honors *R_UNIT/*C_UNIT and *NAME_MAP; ignores *CONN. Node ids like *3:7
    are expanded via the name map to <netname>:7."""
    ru = cu = 1.0
    namemap, nets, cur, section = {}, {}, None, None

    def expand(tok):
        # "*3:7" -> "<name-of-3>:7" ; "*3" -> name ; "*0" -> "0" (ground)
        m = re.match(r"\*(\d+)(?::(.+))?$", tok)
        if not m:
            return tok
        base = "0" if m.group(1) == "0" else namemap.get("*" + m.group(1), "*" + m.group(1))
        return f"{base}:{m.group(2)}" if m.group(2) else base

    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("//"):
            continue
        u = ln.upper()
        if u.startswith("*R_UNIT"): ru = float(ln.split()[1]) * _UNIT.get(ln.split()[2].upper(), 1.0); continue
        if u.startswith("*C_UNIT"): cu = float(ln.split()[1]) * _UNIT.get(ln.split()[2].upper(), 1.0); continue
        if u.startswith("*D_NET"):
            cur = expand(ln.split()[1]); nets[cur] = {"segs": [], "caps": []}; section = None; continue
        if u.startswith("*END"):
            cur = None; section = None; continue
        if u.startswith("*CAP"): section = "cap"; continue
        if u.startswith("*RES"): section = "res"; continue
        if u.startswith(("*CONN", "*PORTS")): section = None; continue
        if cur is None and re.match(r"\*\d+\s", ln):            # name map row
            t = ln.split(); namemap[t[0]] = t[1]; continue
        if cur is None or section is None:
            continue
        t = ln.split()
        if section == "cap":
            nets[cur]["caps"].append((expand(t[1]), float(t[-1]) * cu))
        elif section == "res" and len(t) >= 4:
            nets[cur]["segs"].append(Segment(net=cur, sid=t[0],
                                             n1=expand(t[1]), n2=expand(t[2]),
                                             r=float(t[-1]) * ru))
    return nets


def load_geom(path):
    """Geometry sidecar -> {(net, sid): dict}. Schema (all optional except net/id):
       {"segments":[{"net":..,"id":..,"layer":..,"width":..,"length":..,
                     "cuts":..,"x1":..,"y1":..,"x2":..,"y2":..}, ...]}"""
    if not path or not os.path.exists(path):
        return {}
    doc = json.load(open(path))
    out = {}
    for s in doc.get("segments", []):
        out[(s["net"], str(s["id"]))] = s
    return out


def build_segments(spef_text, geom_path=None, rules=EM_RULES,
                   default_width=DEFAULT_WIDTH, default_layer=DEFAULT_LAYER):
    """Join SPEF *RES rows with the geometry sidecar -> [Segment] with limits set.
    No geometry for a segment -> geometry-blind fallback (default_layer/width) with
    a warning, so a bare SPEF still runs (honestly flagged)."""
    geom = load_geom(geom_path)
    nets = parse_spef_segments(spef_text)
    out, blind = [], 0
    for net, d in nets.items():
        for seg in d["segs"]:
            g = geom.get((net, seg.sid))
            if g:
                seg.layer = g.get("layer", "")
                seg.width = float(g.get("width", 0.0))
                seg.length = float(g.get("length", 0.0))
                seg.cuts = int(g.get("cuts", 0))
                for k in ("x1", "y1", "x2", "y2"):
                    setattr(seg, k, float(g.get(k, 0.0)))
            if not seg.layer:
                seg.layer, seg.width, blind = default_layer, default_width, blind + 1
            seg.set_limits(rules)
            out.append(seg)
    if blind:
        sys.stderr.write(
            f"hot-spot: WARNING: {blind} segment(s) had no geometry sidecar entry; "
            f"assumed layer={default_layer} width={default_width}um (geometry-blind, "
            f"results indicative only -- run klayout2spef.py --geom for real widths).\n")
    return out, nets


# ---------------------------------------------------------------------------
# instrument: SPEF wires -> statsim_em_wire behavioral models (+ ammeter tap)
# ---------------------------------------------------------------------------
def spice_node(name):
    """SPEF node name -> a clean SPICE node token ('/'/'‌:' -> '_'; ground kept 0)."""
    if name in ("0", "gnd", "GND"):
        return "0"
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def _tag(seg):
    return f"{spice_node(seg.net)}_{seg.sid}"


def instrument(segments, nets, harness="", va=False, title="hot-spot EM deck"):
    """Emit a SPICE deck where every wire segment is an EM-aware model.

    Non-VA (default, portable): each segment ->  R<tag> n1 mid {r}  +  VI<tag> mid n2 0
    The 0 V source VI<tag> is an ammeter: its branch current I(VI<tag>) is the
    segment current the check/heatmap reduce to (avg,rms,peak). Node names are the
    SPEF's own, so this include back-annotates a design that drives those nets.

    VA (`--va`): each segment -> a statsim_em_wire Verilog-A instance that watches
    its own current density and $strobe's an alert inline (needs OpenVAF/PyMS).

    `harness` (sources, loads, .tran, supplies) is appended verbatim -> a complete
    stand-alone deck. Returns (deck_text, ammeter_map) with ammeter_map[VI<tag>]=seg.
    """
    L = [f"* {title}", "* generated by stat-sim hot-spot -- do not edit by hand"]
    ammeters = {}
    if va:
        L.append('.hdl "statsim_em_wire.vams"')
    for seg in segments:
        n1, n2, tag = spice_node(seg.n1), spice_node(seg.n2), _tag(seg)
        lim = seg.imax
        if va:
            # N<tag> n1 n2 statsim_em_wire  (self-monitoring; params carry the geometry+limits)
            L.append(
                f"N{tag} {n1} {n2} statsim_em_wire "
                f"r={seg.r:.6g} imax_avg={lim.get('avg') or 0:.6g} "
                f"imax_rms={lim.get('rms') or 0:.6g} imax_peak={lim.get('peak') or 0:.6g} "
                f"seg=\"{seg.net}:{seg.sid} {seg.layer} w={seg.width}\"")
        else:
            mid = f"{n1}__i_{seg.sid}"
            L.append(f"R{tag} {n1} {mid} {seg.r:.6g}")
            L.append(f"VI{tag} {mid} {n2} 0")     # 0 V ammeter -> I(VI{tag})
            ammeters[f"VI{tag}"] = seg
    # ground caps (make the transient realistic; EM reads the R-branch currents)
    ci = 0
    for net, d in nets.items():
        for node, val in d["caps"]:
            ci += 1
            a, b = (node, "0") if not isinstance(node, tuple) else node
            L.append(f"CH{ci} {spice_node(a)} 0 {val:.6g}")
    if harness:
        L += ["", "* ---- harness ----", harness.rstrip()]
    return "\n".join(L) + "\n", ammeters


# ---------------------------------------------------------------------------
# current reduction + risk
# ---------------------------------------------------------------------------
def reduce_current(series):
    """(avg, rms, peak) of a current waveform, amps. avg = |mean| (net DC / mass
    transport), rms = sqrt(mean(i^2)) (self-heat), peak = max|i| (short pulse)."""
    if not series:
        return (0.0, 0.0, 0.0)
    n = len(series)
    mean = sum(series) / n
    rms = math.sqrt(sum(x * x for x in series) / n)
    peak = max(abs(x) for x in series)
    return (abs(mean), rms, peak)


def risk(seg, avg, rms, peak, rules=EM_RULES):
    """Per-segment EM risk. ratio[kind] = I[kind]/Imax[kind] (>1 == over limit).
    worst = max ratio; rel_mttf = (Imax_avg/I_avg)^n derate vs nominal (Black)."""
    cur = {"avg": avg, "rms": rms, "peak": peak}
    ratios = {}
    for k in KINDS:
        lim = seg.imax.get(k)
        ratios[k] = (cur[k] / lim) if lim and lim > 0 else 0.0
    worst = max(ratios.values()) if ratios else 0.0
    la = seg.imax.get("avg")
    rel_mttf = ((la / avg) ** rules["black_n"]) if (la and avg > 0) else float("inf")
    return {"cur": cur, "ratio": ratios, "worst": worst, "rel_mttf": rel_mttf}


# ---------------------------------------------------------------------------
# simulate (via bfit's engine-neutral drivers) and pull ammeter currents
# ---------------------------------------------------------------------------
def simulate_currents(deck, ammeters, sim="ngspice"):
    """Run `deck` on `sim` (bfit driver) and return {VI<tag>: (avg,rms,peak)}.
    Branch current of an ammeter V-source appears as i(vi<tag>) in the rawfile."""
    import bfit
    drv = bfit.DRIVERS[sim]()
    # ask the driver to save every ammeter branch current
    sigs = None
    if sim == "xyce":
        # Xyce needs explicit I(...) prints; append them before the driver runs
        prints = " ".join(f"I({v})" for v in ammeters)
        deck = deck.rstrip() + "\n.print tran " + prints + "\n"
    data = drv.run(deck, signals=sigs)
    lk = {k.lower(): v for k, v in data.items()}
    return {v: reduce_current(_pick_current(lk, v)) for v in ammeters}


def _pick_current(lk, vname):
    """Find an ammeter's branch-current column across engine naming dialects:
    ngspice 'vname#branch', Xyce/print 'i(vname)', or a bare 'vname'."""
    v = vname.lower()
    for key in (f"{v}#branch", f"i({v})", v):
        if key in lk:
            return lk[key]
    return []


# ---------------------------------------------------------------------------
# check: print EM alerts
# ---------------------------------------------------------------------------
def check_report(segments, ammeters, currents, rules=EM_RULES, out=sys.stdout):
    """Print the EM alert report; return (n_violations, rows) sorted worst-first."""
    seg_by_vi = {v: s for v, s in ammeters.items()}
    rows = []
    for v, (avg, rms, peak) in currents.items():
        seg = seg_by_vi[v]
        rows.append((seg, risk(seg, avg, rms, peak, rules)))
    rows.sort(key=lambda sr: sr[1]["worst"], reverse=True)
    nviol = sum(1 for _, r in rows if r["worst"] > 1.0)
    out.write("\n=== hot-spot EM current-density report ===\n")
    out.write(f"rules: {rules.get('_provenance', 'built-in')}\n")
    out.write(f"{'segment':<22}{'layer':<7}{'w(um)':>7}{'I_avg':>11}"
              f"{'Imax_avg':>11}{'worst':>8}  verdict\n")
    for seg, r in rows:
        tag = f"{seg.net}:{seg.sid}"
        geo = f"{seg.cuts}cut" if seg.is_via else f"{seg.width:g}"
        lim = seg.imax.get("avg") or 0.0
        verdict = _verdict(r["worst"])
        out.write(f"{tag:<22}{seg.layer:<7}{geo:>7}{r['cur']['avg']:>11.3e}"
                  f"{lim:>11.3e}{r['worst']:>8.2f}  {verdict}\n")
    out.write(f"\n{nviol} segment(s) over EM limit "
              f"(worst-first; worst = max of avg/rms/peak I over Imax).\n")
    for seg, r in rows:
        if r["worst"] > 1.0:
            k = max(KINDS, key=lambda kk: r["ratio"][kk])
            out.write(f"  ALERT  {seg.net}:{seg.sid} ({seg.layer} "
                      f"{'via' if seg.is_via else str(seg.width)+'um'}): "
                      f"{k} current {r['cur'][k]:.3e} A is {r['ratio'][k]:.1f}x "
                      f"Imax ({seg.imax[k]:.3e} A) -> ~{100.0*r['rel_mttf']:.1f}% of "
                      f"nominal EM lifetime\n")
    return nviol, rows


def _verdict(worst):
    if worst > 1.0:  return "OVER-LIMIT (EM)"
    if worst > 0.8:  return "marginal"
    if worst > 0.5:  return "watch"
    return "ok"


# ---------------------------------------------------------------------------
# heatmap: SVG layout risk map + ranked CSV
# ---------------------------------------------------------------------------
# Risk colormap: render the layout as GREY where EM is within limit (it recedes,
# reads as an ordinary layout plot) and COLOUR it up only where risk is over --
# so the hot-spots pop. Below 1x: neutral grey, lightening with load. At/above 1x:
# saturated heat orange->red->magenta->hot pink, LOG-scaled (1x,10x,100x) because
# overshoot spans orders of magnitude (a neck at 40x vs a rail at 1.3x).
def _rgb_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in (r, g, b))


def risk_color(worst):
    if worst < 1.0:                                    # under limit -> greyscale layout
        g = 0.42 + 0.32 * max(0.0, worst)              # 0.42 (idle) .. 0.74 (near limit)
        return _rgb_hex(g, g, g)
    L = min(math.log10(worst), 2.0)                    # 0 (1x) .. 1 (10x) .. 2 (100x)
    stops = [(0.0, (0.94, 0.55, 0.17)),                # orange  ~1x
             (0.5, (0.88, 0.20, 0.15)),                # red     ~3x
             (1.0, (0.78, 0.12, 0.42)),                # magenta ~10x
             (1.6, (0.82, 0.23, 0.75)),                # pink    ~40x
             (2.0, (1.00, 0.66, 0.94))]                # hot     ~100x
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if L <= b:
            t = 0.0 if b == a else (L - a) / (b - a)
            return _rgb_hex(*(ca[i] + t * (cb[i] - ca[i]) for i in range(3)))
    return _rgb_hex(*stops[-1][1])


def heatmap_svg(rows, width_px=900, pad=48, title="hot-spot EM heat-map"):
    """rows = [(Segment, risk_dict)]. Draw each segment as a width-scaled line at
    its layout coordinates, coloured by worst risk; self-contained SVG string."""
    segs = [(s, r) for s, r in rows if (s.x1 or s.y1 or s.x2 or s.y2)]
    if not segs:
        return _svg_empty(title)
    xs = [c for s, _ in segs for c in (s.x1, s.x2)]
    ys = [c for s, _ in segs for c in (s.y1, s.y2)]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    spanx, spany = (maxx - minx) or 1.0, (maxy - miny) or 1.0
    sc = (width_px - 2 * pad) / spanx
    height_px = int(spany * sc + 2 * pad + 60)

    def X(x): return pad + (x - minx) * sc
    def Y(y): return height_px - 60 - pad - (y - miny) * sc      # flip: +y up

    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" '
        f'height="{height_px}" viewBox="0 0 {width_px} {height_px}" '
        f'font-family="ui-monospace,Menlo,Consolas,monospace">',
        f'<rect width="{width_px}" height="{height_px}" fill="#0d1117"/>',
        f'<text x="{pad}" y="28" fill="#e6edf3" font-size="18">{title}</text>',
    ]
    for seg, r in sorted(segs, key=lambda sr: sr[1]["worst"]):   # hot on top
        w_line = max(2.0, (seg.width or 0.3) * sc) if not seg.is_via else 6.0
        col = risk_color(r["worst"])
        if seg.is_via:
            body.append(f'<circle cx="{X(seg.x1):.1f}" cy="{Y(seg.y1):.1f}" r="5" '
                        f'fill="{col}" stroke="#0d1117"/>')
        else:
            body.append(
                f'<line x1="{X(seg.x1):.1f}" y1="{Y(seg.y1):.1f}" '
                f'x2="{X(seg.x2):.1f}" y2="{Y(seg.y2):.1f}" stroke="{col}" '
                f'stroke-width="{w_line:.1f}" stroke-linecap="round">'
                f'<title>{seg.net}:{seg.sid} {seg.layer} w={seg.width}um  '
                f'worst={r["worst"]:.2f}x</title></line>')
    # legend
    ly = height_px - 34
    body.append(f'<text x="{pad}" y="{ly-6}" fill="#9aa4ad" font-size="12">'
                f'EM risk  I / Imax   (grey = within limit; colour = over, log-scaled)</text>')
    for i, (lab, val) in enumerate([("under 1x", 0.4), ("limit 1x", 1.0),
                                    ("3x", 3.0), ("10x", 10.0), ("40x", 40.0)]):
        x = pad + i * 150
        body.append(f'<rect x="{x}" y="{ly}" width="16" height="16" fill="{risk_color(val)}"/>')
        body.append(f'<text x="{x+22}" y="{ly+13}" fill="#c9d1d9" font-size="12">{lab}</text>')
    body.append("</svg>")
    return "\n".join(body)


def _svg_empty(title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="120">'
            f'<rect width="600" height="120" fill="#0d1117"/>'
            f'<text x="20" y="60" fill="#e6edf3" font-size="15">{title}: no segment '
            f'coordinates in geometry sidecar</text></svg>')


def heatmap_csv(rows):
    out = ["net,seg,layer,width_um,length_um,is_via,cuts,I_avg,I_rms,I_peak,"
           "Imax_avg,ratio_avg,ratio_rms,ratio_peak,worst,rel_mttf_pct,x1,y1,x2,y2"]
    for seg, r in sorted(rows, key=lambda sr: sr[1]["worst"], reverse=True):
        c, ra = r["cur"], r["ratio"]
        out.append(",".join(str(x) for x in [
            seg.net, seg.sid, seg.layer, seg.width, seg.length, int(seg.is_via), seg.cuts,
            f"{c['avg']:.4e}", f"{c['rms']:.4e}", f"{c['peak']:.4e}",
            f"{(seg.imax.get('avg') or 0):.4e}",
            f"{ra['avg']:.3f}", f"{ra['rms']:.3f}", f"{ra['peak']:.3f}",
            f"{r['worst']:.3f}",
            (f"{100*r['rel_mttf']:.1f}" if math.isfinite(r['rel_mttf']) else "inf"),
            seg.x1, seg.y1, seg.x2, seg.y2]))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _run(spef_text, geom, rules, sim, raw, harness, default_width):
    """Shared path for check/heatmap: build segments, get currents, make rows."""
    segments, nets = build_segments(spef_text, geom, rules, default_width)
    deck, ammeters = instrument(segments, nets, harness=harness)
    if raw:
        currents = _currents_from_raw(raw, ammeters)
    else:
        currents = simulate_currents(deck, ammeters, sim=sim)
    rows = [(ammeters[v], risk(ammeters[v], *currents[v], rules)) for v in ammeters]
    return segments, nets, ammeters, currents, rows


def _currents_from_raw(path, ammeters):
    """Read a precomputed rawfile (ngspice binary or Xyce .prn) -> currents."""
    import bfit
    if path.endswith(".prn"):
        data = bfit._parse_prn(path)
    else:
        from drivers_ngspice import _parse_ngspice_raw
        data = _parse_ngspice_raw(path)
    lk = {k.lower(): v for k, v in data.items()}
    return {v: reduce_current(_pick_current(lk, v)) for v in ammeters}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hot-spot",
        description="Electromigration current-density screening from SPEF.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, need_out=False):
        p.add_argument("spef", nargs="?", help="input SPEF")
        p.add_argument("--geom", help="geometry sidecar JSON (default <spef>.json)")
        p.add_argument("--em-rules", help="EM current-density limits (JSON); a file with "
                       "metal/via REPLACES the built-in sky130 estimate")
        p.add_argument("--lef", help="read REAL EM limits from a PDK tech LEF's "
                       "DCCURRENTDENSITY (e.g. IHP sg13g2_tech.lef); wins over --em-rules")
        p.add_argument("--default-width", type=float, default=DEFAULT_WIDTH,
                       help="assumed width (um) for geometry-blind segments")

    pi = sub.add_parser("instrument", help="rewrite SPEF wires as EM behavioral models")
    common(pi)
    pi.add_argument("--harness", help="SPICE harness (sources/loads/.tran) to append")
    pi.add_argument("--va", action="store_true", help="use the Verilog-A statsim_em_wire "
                    "(inline $strobe alerts; needs OpenVAF/PyMS)")
    pi.add_argument("-o", "--out", help="output deck (default stdout)")

    pc = sub.add_parser("check", help="simulate + print EM alerts (exit nonzero if over)")
    common(pc)
    pc.add_argument("--sim", default="ngspice", help="engine (ngspice|xyce)")
    pc.add_argument("--harness", help="SPICE harness to drive the nets")
    pc.add_argument("--raw", help="read currents from a rawfile/.prn instead of simulating")

    ph = sub.add_parser("heatmap", help="EM risk heat-map SVG + ranked CSV")
    common(ph)
    ph.add_argument("--sim", default="ngspice", help="engine (ngspice|xyce)")
    ph.add_argument("--harness", help="SPICE harness to drive the nets")
    ph.add_argument("--raw", help="read currents from a rawfile/.prn instead of simulating")
    ph.add_argument("-o", "--out", help="output SVG (default <spef>.em.svg)")
    ph.add_argument("--csv", help="also write a ranked CSV")

    ap.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    if getattr(a, "lef", None):
        rules = em_rules_from_lef(a.lef)
    else:
        rules = load_em_rules(getattr(a, "em_rules", None))
    if not a.spef:
        ap.error("a SPEF file is required")
    geom = a.geom or (a.spef + ".json" if os.path.exists(a.spef + ".json") else None)
    spef_text = open(a.spef).read()
    harness = open(a.harness).read() if getattr(a, "harness", None) else ""

    if a.cmd == "instrument":
        segments, nets = build_segments(spef_text, geom, rules, a.default_width)
        deck, _ = instrument(segments, nets, harness=harness, va=a.va)
        (open(a.out, "w") if a.out else sys.stdout).write(deck)
        if a.out:
            sys.stderr.write(f"hot-spot: wrote {len(segments)} EM wire model(s) -> {a.out}\n")
        return 0

    if a.cmd == "check":
        segments, nets, ammeters, currents, _ = _run(
            spef_text, geom, rules, a.sim, a.raw, harness, a.default_width)
        nviol, _ = check_report(segments, ammeters, currents, rules)
        return 1 if nviol else 0

    if a.cmd == "heatmap":
        _, _, _, _, rows = _run(
            spef_text, geom, rules, a.sim, a.raw, harness, a.default_width)
        outp = a.out or (os.path.splitext(a.spef)[0] + ".em.svg")
        open(outp, "w").write(heatmap_svg(rows))
        sys.stderr.write(f"hot-spot: wrote heat-map -> {outp}\n")
        if a.csv:
            open(a.csv, "w").write(heatmap_csv(rows))
            sys.stderr.write(f"hot-spot: wrote ranked CSV -> {a.csv}\n")
        return 0


# ---------------------------------------------------------------------------
# self-test -- physics + SPEF pass + instrument + SVG, no simulator, no klayout
# ---------------------------------------------------------------------------
_SAMPLE_SPEF = """\
*SPEF "IEEE 1481-1998"
*T_UNIT 1 PS
*C_UNIT 1 FF
*R_UNIT 1 OHM
*NAME_MAP
*1 pad_drv
*2 vdd_rail
*D_NET *1 20.0
*CAP
1 *1:2 8.0
*RES
1 *1 *1:1 128.0
2 *1:1 *1:2 3.5
3 *1:2 *1:3 12.0
*END
*D_NET *2 40.0
*RES
1 *2 *2:1 0.9
*END
"""

_SAMPLE_GEOM = {"segments": [
    {"net": "pad_drv", "id": "1", "layer": "met1", "width": 0.5, "length": 5.0,
     "x1": 0, "y1": 0, "x2": 5, "y2": 0},
    {"net": "pad_drv", "id": "2", "layer": "mcon", "cuts": 4, "x1": 5, "y1": 0, "x2": 5, "y2": 0},
    {"net": "pad_drv", "id": "3", "layer": "met3", "width": 4.0, "length": 20.0,
     "x1": 5, "y1": 0, "x2": 25, "y2": 0},
    {"net": "vdd_rail", "id": "1", "layer": "met3", "width": 8.0, "length": 30.0,
     "x1": 0, "y1": 5, "x2": 0, "y2": 35},
]}


def _self_test():
    import tempfile
    # 1. imax math: metals scale with width, vias with cuts
    assert abs(imax("met1", "avg", width_um=1.0) - 0.79e-3) < 1e-12
    assert abs(imax("met1", "avg", width_um=0.5) - 0.395e-3) < 1e-12
    assert abs(imax("mcon", "avg", cuts=4) - 4 * 0.28e-3) < 1e-12
    assert imax("bogus", "avg", width_um=1.0) is None
    # 2. segment-level SPEF pass keeps every *RES row with expanded node names
    nets = parse_spef_segments(_SAMPLE_SPEF)
    assert set(nets) == {"pad_drv", "vdd_rail"}, nets.keys()
    segs = nets["pad_drv"]["segs"]
    assert [s.sid for s in segs] == ["1", "2", "3"]
    assert segs[0].n1 == "pad_drv" and segs[0].n2 == "pad_drv:1" and abs(segs[0].r - 128.0) < 1e-9
    assert nets["pad_drv"]["caps"][0][0] == "pad_drv:2"
    # 3. build_segments joins geometry + sets limits
    d = tempfile.mkdtemp(prefix="hs_")
    gp = os.path.join(d, "s.spef.json")
    json.dump(_SAMPLE_GEOM, open(gp, "w"))
    segments, nets = build_segments(_SAMPLE_SPEF, gp)
    by = {(s.net, s.sid): s for s in segments}
    neck = by[("pad_drv", "1")]
    assert neck.layer == "met1" and abs(neck.width - 0.5) < 1e-9
    assert abs(neck.imax["avg"] - 0.395e-3) < 1e-12
    via = by[("pad_drv", "2")]
    assert via.is_via and via.cuts == 4 and abs(via.imax["avg"] - 1.12e-3) < 1e-12
    # 4. risk: 20 mA through the 0.5um met1 neck is ~50x its 0.395 mA avg limit
    r = risk(neck, 20e-3, 22e-3, 36e-3)
    assert r["ratio"]["avg"] > 40 and r["worst"] > 40, r
    assert r["rel_mttf"] < 1e-3, r["rel_mttf"]           # deep into EM -> tiny lifetime
    # a benign wide rail carrying 0.1 mA is well under limit
    rail = by[("vdd_rail", "1")]
    assert risk(rail, 1e-4, 1e-4, 1e-4)["worst"] < 0.1
    # 5. instrument emits a parseable deck: R + 0V ammeter per segment, node names kept
    deck, ammeters = instrument(segments, nets, harness="Vx a 0 1\n.tran 1n 10n")
    assert deck.count("\nR") + deck.startswith("R") >= 4       # >=4 wire resistors
    assert len(ammeters) == 4 and all(v.startswith("VI") for v in ammeters)
    assert "pad_drv pad_drv__i_1" in deck                      # SPEF node name preserved
    assert "* ---- harness ----" in deck and ".tran" in deck
    # VA emission references the portable model
    vdeck, _ = instrument(segments, nets, va=True)
    assert '.hdl "statsim_em_wire.vams"' in vdeck and "statsim_em_wire" in vdeck
    # 6. current reduction: avg=|mean|, rms, peak of a 50%-duty square wave
    sq = [0.0, 0.0, 4e-3, 4e-3] * 25
    avg, rms, peak = reduce_current(sq)
    assert abs(avg - 2e-3) < 1e-9 and abs(peak - 4e-3) < 1e-12
    assert abs(rms - 4e-3 / math.sqrt(2)) < 1e-6
    # 7. report + heatmap render (synthetic currents: neck hot, rail cool)
    currents = {}
    for v, s in ammeters.items():
        currents[v] = (18e-3, 25e-3, 36e-3) if s.net == "pad_drv" else (1e-4, 1e-4, 1e-4)
    import io
    buf = io.StringIO()
    nviol, rows = check_report(segments, ammeters, currents, out=buf)
    assert nviol >= 2, buf.getvalue()
    assert "ALERT" in buf.getvalue() and "OVER-LIMIT" in buf.getvalue()
    svg = heatmap_svg(rows)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>") and "<line" in svg
    csv = heatmap_csv(rows)
    assert csv.splitlines()[0].startswith("net,seg,layer") and len(csv.splitlines()) == 5
    # 8. REAL rules parsed from a LEF (IHP-style DCCURRENTDENSITY) + unspecified-kind
    lef = os.path.join(d, "t.lef")
    open(lef, "w").write(
        "LAYER Metal1\n  TYPE ROUTING ;\n  THICKNESS 0.40 ;\n"
        "  DCCURRENTDENSITY AVERAGE 1 ; #mA/um\nEND Metal1\n"
        "LAYER Via1\n  TYPE CUT ;\n  DCCURRENTDENSITY AVERAGE 0.4 ;\nEND Via1\n")
    ihp = em_rules_from_lef(lef)
    assert abs(ihp["metal"]["Metal1"]["avg"] - 1e-3) < 1e-12
    assert abs(ihp["via"]["Via1"]["avg"] - 0.4e-3) < 1e-12 and "REAL" in ihp["_provenance"]
    assert imax("Metal1", "avg", width_um=2.0, rules=ihp) == 2e-3       # 1mA/um * 2um
    assert imax("Metal1", "peak", width_um=2.0, rules=ihp) is None      # LEF has no peak
    nseg = Segment(net="n", sid="1", n1="a", n2="b", r=1.0, layer="Metal1", width=0.5)
    nseg.set_limits(ihp)
    assert abs(nseg.imax["avg"] - 0.5e-3) < 1e-12 and nseg.imax["peak"] is None
    ir = risk(nseg, 20e-3, 25e-3, 40e-3, ihp)      # 20mA avg / 0.5mA = 40x; rms/peak unscreened
    assert abs(ir["ratio"]["avg"] - 40.0) < 1e-6 and ir["ratio"]["peak"] == 0.0 and abs(ir["worst"] - 40.0) < 1e-6
    print("self-test OK: imax(met1 0.5um)=0.395mA; neck 20mA -> %.0fx over, "
          "rel-MTTF %.2e; %d/%d segs over limit; SVG+CSV render"
          % (risk(neck, 20e-3, 22e-3, 36e-3)["worst"],
             risk(neck, 20e-3, 22e-3, 36e-3)["rel_mttf"], nviol, len(rows)))
    return 0


if __name__ == "__main__":
    if "--self-test" in (sys.argv[1:] or []):
        sys.exit(_self_test())
    sys.exit(main())
