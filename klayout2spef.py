#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
"""
klayout2spef -- per-net RC parasitics from a GDS (via KLayout) -> SPEF for stat-sim.

This closes the loop on the SPEF stage: a real layout's interconnect parasitics
become the on-the-fly load taps that set CDC timing (spef.py -> nvc/prob_load).

Two halves:
  extract_net_rc(gds) -- KLayout LayoutToNetlist: per-net connectivity AND per-net
      geometry -> [NetRC(name, C, R)]. The device/connectivity recipe mirrors the
      proven kestrel flow (/usr/local/src/kestrel/layout/{extract,parasitics}.py);
      needs `klayout` (pip install klayout; cp39-cp312 wheels on Linux/Win/Mac).
  write_spef(nets, path) -- emit IEEE-1481 SPEF (NAME_MAP / D_NET / CAP / RES) in
      the exact dialect spef.py parses. PURE python -- `--self-test` round-trips it
      through stat-sim's own spef.parse()/net_loads(), so the format is verified
      here even without klayout.

sky130 interconnect parameters are from kestrel/layout/parasitics.py. The model is
lumped (one ground C + one series R per net) -- which is exactly what spef.py
reduces a net to (c_wire, r_wire); distributed RC trees / coupling caps are a
refinement (see NOTES at the bottom).

Usage:
    python3 klayout2spef.py design.gds -o design.spef [--top CELL]
    python3 klayout2spef.py --self-test
"""
import os
import sys
import argparse
from dataclasses import dataclass

# --- sky130 interconnect parameters (from kestrel/layout/parasitics.py) ------
RSH = {'li': 12.8, 'met1': 0.125, 'met2': 0.125, 'met3': 0.047}        # ohm/square
RVIA = {'licon': 70.0, 'mcon': 9.3, 'via1': 4.5, 'via2': 4.5}          # ohm/via
CAREA = {'li': 0.040, 'met1': 0.038, 'met2': 0.028, 'met3': 0.020}     # fF/um^2
CFRINGE = {'li': 0.040, 'met1': 0.040, 'met2': 0.036, 'met3': 0.030}   # fF/um

ROUTING_LAYERS = ('li', 'met1', 'met2', 'met3')
VIA_LAYERS = ('licon', 'mcon', 'via1', 'via2')

# GDS layer/datatype map (sky130; matches kestrel extract.py)
LAYER_MAP = {
    'diff': (65, 20), 'tap': (65, 44), 'nwell': (64, 20), 'poly': (66, 20),
    'nsdm': (93, 44), 'psdm': (94, 20),
    'licon': (66, 44), 'li': (67, 20), 'mcon': (67, 44),
    'met1': (68, 20), 'via1': (68, 44), 'met2': (69, 20), 'via2': (69, 44),
    'met3': (70, 20),
}

# --- IHP SG13G2 interconnect parameters --------------------------------------
# Sourced from the PDK itself: RSH = RESISTANCE RPERSQ, RVIA = via RESISTANCE, and
# C = CPERSQDIST / EDGECAPACITANCE (LEF pF -> fF, x1000) all from
#   ihp-sg13g2/libs.ref/sg13g2_stdcell/lef/sg13g2_tech.lef ;
# GDS layer numbers + the via stack from sg13g2.map / sg13_tech_info.py. 5 thin
# metals (Metal1..5) + 2 thick top metals, 6 via layers. (Same DCCURRENTDENSITY
# LEF that feeds hotspot's --lef EM limits.)
IHP_RSH = {'Metal1': 0.135, 'Metal2': 0.103, 'Metal3': 0.103, 'Metal4': 0.103,
           'Metal5': 0.103, 'TopMetal1': 0.021, 'TopMetal2': 0.0145}          # ohm/square
IHP_RVIA = {'Via1': 20.0, 'Via2': 20.0, 'Via3': 20.0, 'Via4': 20.0,
            'TopVia1': 4.0, 'TopVia2': 2.2}                                   # ohm/via
IHP_CAREA = {'Metal1': 0.0349, 'Metal2': 0.0181, 'Metal3': 0.0120, 'Metal4': 0.00894,
             'Metal5': 0.00713, 'TopMetal1': 0.00564, 'TopMetal2': 0.00323}   # fF/um^2
IHP_CFRINGE = {'Metal1': 0.0316, 'Metal2': 0.0447, 'Metal3': 0.0448, 'Metal4': 0.0450,
               'Metal5': 0.0437, 'TopMetal1': 0.0508, 'TopMetal2': 0.0418}    # fF/um
IHP_ROUTING = ('Metal1', 'Metal2', 'Metal3', 'Metal4', 'Metal5', 'TopMetal1', 'TopMetal2')
IHP_VIA = ('Via1', 'Via2', 'Via3', 'Via4', 'TopVia1', 'TopVia2')
IHP_LAYER_MAP = {
    'Metal1': (8, 0), 'Via1': (19, 0), 'Metal2': (10, 0), 'Via2': (29, 0),
    'Metal3': (30, 0), 'Via3': (49, 0), 'Metal4': (50, 0), 'Via4': (66, 0),
    'Metal5': (67, 0), 'TopVia1': (125, 0), 'TopMetal1': (126, 0),
    'TopVia2': (133, 0), 'TopMetal2': (134, 0),
}
# (bottom_metal, cut, top_metal) for connectivity
IHP_VIA_STACK = [('Metal1', 'Via1', 'Metal2'), ('Metal2', 'Via2', 'Metal3'),
                 ('Metal3', 'Via3', 'Metal4'), ('Metal4', 'Via4', 'Metal5'),
                 ('Metal5', 'TopVia1', 'TopMetal1'), ('TopMetal1', 'TopVia2', 'TopMetal2')]


@dataclass
class NetRC:
    name: str
    c: float        # total net capacitance, farads
    r: float        # lumped series resistance, ohms


# ----------------------------------------------------------------------------
# Half 1: KLayout extraction  (mirrors kestrel layout/extract.py + parasitics.py)
# ----------------------------------------------------------------------------
DEFAULT_SKIP = ("VPWR", "VGND", "VDD", "VSS", "vpwr", "vgnd", "vdd", "vss")
_OUT_PINS = {"out", "o", "q", "qn", "nq", "y", "z", "zn", "co", "cout", "x"}
_PWR_PINS = {"vdd", "vss", "vpwr", "vgnd", "vnb", "vpb", "gnd", "vcc"}


def _connect_sky130(kdb, l2n, layers):
    """sky130 device recognition (NFET/PFET) + full connectivity (poly/li/metN,
    contacts, and the diffusion S/D + gate regions). Mirrors kestrel extract.py."""
    gate = layers['poly'] & layers['diff']
    sd = layers['diff'] - layers['poly']
    nsd = (sd & layers['nsdm']) - layers['nwell']
    psd = (sd & layers['psdm']) & layers['nwell']
    ngate = gate - layers['nwell']
    pgate = gate & layers['nwell']
    l2n.extract_devices(kdb.DeviceExtractorMOS3Transistor("sky130_fd_pr__nfet_01v8"),
                        {"SD": nsd, "G": ngate, "P": ngate})
    l2n.extract_devices(kdb.DeviceExtractorMOS3Transistor("sky130_fd_pr__pfet_01v8"),
                        {"SD": psd, "G": pgate, "P": pgate})
    for ln in ('poly', 'li', 'met1', 'met2', 'met3', 'licon', 'mcon'):
        l2n.connect(layers[ln])
    for reg in (nsd, psd, ngate, pgate):
        l2n.connect(reg)
    l2n.connect(ngate, layers['poly']); l2n.connect(pgate, layers['poly'])
    l2n.connect(nsd, layers['licon']); l2n.connect(psd, layers['licon'])
    l2n.connect(layers['poly'], layers['licon'])
    l2n.connect(layers['licon'], layers['li']); l2n.connect(layers['li'], layers['mcon'])
    l2n.connect(layers['mcon'], layers['met1']); l2n.connect(layers['met1'], layers['via1'])
    l2n.connect(layers['via1'], layers['met2']); l2n.connect(layers['met2'], layers['via2'])
    l2n.connect(layers['via2'], layers['met3'])


def _connect_ihp(kdb, l2n, layers):
    """IHP SG13G2 ROUTING connectivity (metal + via stack only). No device
    recognition: EM screens the metal interconnect, and because the diffusion
    (Activ) is not connected, a transistor's source/drain stay separate metal nets
    -- so the top-level routing nets (pad, rails, signals) come out correctly
    without modelling the FETs. Cont is intentionally excluded (device contact)."""
    for ln in IHP_ROUTING + IHP_VIA:
        l2n.connect(layers[ln])
    for bot, cut, top in IHP_VIA_STACK:
        l2n.connect(layers[bot], layers[cut])
        l2n.connect(layers[cut], layers[top])


# PDK registry: each tech bundles its GDS layer map, R/C constants, routing/via
# layer sets, and its connectivity/device-recognition setup. `--pdk` selects one.
TECHS = {
    "sky130": {"LAYER_MAP": LAYER_MAP, "RSH": RSH, "RVIA": RVIA, "CAREA": CAREA,
               "CFRINGE": CFRINGE, "ROUTING": ROUTING_LAYERS, "VIA": VIA_LAYERS,
               "connect": _connect_sky130},
    "ihp-sg13g2": {"LAYER_MAP": IHP_LAYER_MAP, "RSH": IHP_RSH, "RVIA": IHP_RVIA,
                   "CAREA": IHP_CAREA, "CFRINGE": IHP_CFRINGE, "ROUTING": IHP_ROUTING,
                   "VIA": IHP_VIA, "connect": _connect_ihp,
                   # connectivity-only (no devices/pins): purge would delete the nets
                   "combine_devices": False, "purge": False},
}


def _build_l2n(gds_path, top_cell=None, tech=None, flatten=False):
    """KLayout LayoutToNetlist setup for the selected `tech` (layers + its
    connectivity/device recognition + extract) -> (l2n, netlist, layers, dbu).
    flatten=True collapses the top cell's hierarchy first, so a single cell (e.g.
    one IO pad) extracts to one flat set of nets."""
    tech = tech or TECHS["sky130"]
    try:
        import klayout.db as kdb
    except ImportError as e:
        raise SystemExit(
            "klayout2spef: the `klayout` module is required for extraction.\n"
            "  pip install klayout   (cp39-cp313 wheels; this box's WSL py3.14 / "
            "Cygwin py3.9 have none -- run on a Linux py3.10-3.13, e.g. a venv).\n"
            f"  (import error: {e})")
    layout = kdb.Layout()
    layout.read(gds_path)
    dbu = layout.dbu
    tc = layout.cell(top_cell) if top_cell else layout.top_cells()[0]
    l2n = kdb.LayoutToNetlist(kdb.RecursiveShapeIterator(layout, tc, []))
    layers = {}
    for name, (ln, dt) in tech["LAYER_MAP"].items():
        li = layout.find_layer(ln, dt)
        layers[name] = l2n.make_layer(li, name) if li is not None else l2n.make_layer(name)
    tech["connect"](kdb, l2n, layers)
    l2n.extract_netlist()
    netlist = l2n.netlist()
    if flatten:
        netlist.flatten()                    # merge the cell hierarchy -> one flat net set
    if tech.get("combine_devices", True):
        netlist.combine_devices()
    if tech.get("purge", True):
        netlist.purge()                      # purge drops pinless nets -> OFF for a
    return l2n, netlist, layers, dbu         # connectivity-only tech (IHP EM routing)


def net_geometry_rc(l2n, net, layers, dbu, tech=None):
    """(C_farad, R_ohm) of one net from its own per-layer geometry (the wire only --
    a parent-owned routing net's shapes exclude the cell interior)."""
    tech = tech or TECHS["sky130"]
    rsh, rvia, carea, cfringe = tech["RSH"], tech["RVIA"], tech["CAREA"], tech["CFRINGE"]
    c_fF = r_ohm = 0.0
    for lname in tech["ROUTING"]:
        reg = l2n.shapes_of_net(net, layers[lname])
        a = p = 0.0
        for poly in reg.each():
            a += poly.area(); p += poly.perimeter()
        area, perim = a * dbu * dbu, p * dbu
        if area <= 0:
            continue
        c_fF += carea[lname] * area + cfringe[lname] * perim
        avg_w = 2 * area / perim if perim > 0 else 0.0
        if avg_w > 0:
            r_ohm += rsh[lname] * (perim / (2 * avg_w))      # ~ n_squares
    for vname in tech["VIA"]:
        r_ohm += rvia[vname] * l2n.shapes_of_net(net, layers[vname]).count()
    return c_fF * 1e-15, r_ohm


def extract_net_rc(gds_path, top_cell=None, skip=DEFAULT_SKIP, tech=None) -> list:
    """FULL extraction (every net, cell-internal + routing). Returns [NetRC]."""
    tech = tech or TECHS["sky130"]
    l2n, netlist, layers, dbu = _build_l2n(gds_path, top_cell, tech)
    out, skip = [], set(skip)
    circuits = list(netlist.each_circuit())
    multi = len(circuits) > 1
    for circuit in circuits:
        for net in circuit.each_net():
            nm = net.expanded_name()
            if nm in skip:
                continue
            c, r = net_geometry_rc(l2n, net, layers, dbu, tech)
            out.append(NetRC(f"{circuit.name}/{nm}" if multi else nm, c, r))
    return out


# ----------------------------------------------------------------------------
# Routing-only extraction (Ask A): subtract the cells, keep inter-cell wiring
# ----------------------------------------------------------------------------
def _classify_pins(net):
    """(driver, receivers, ports) from a net's pin connectivity. Best-effort by
    pin name (output set -> driver, power -> skip, else receiver); the binder
    (which knows the cell models / port directions) can correct this."""
    drv, recvs, ports = None, [], []
    for spr in net.each_subcircuit_pin():
        sc = spr.subcircuit()
        pin = spr.pin().name() or ""
        if pin.lower() in _PWR_PINS:
            continue
        inst = sc.name or (sc.circuit_ref().name if sc.circuit_ref() else "?")
        ref = f"{inst}:{pin}"
        if pin.lower() in _OUT_PINS:
            drv = ref
        else:
            recvs.append(ref)
    for pr in net.each_pin():
        ports.append(pr.pin().name() or "")
    return drv, recvs, ports


def extract_routing_rc(gds_path, model_cells=(), top_cell=None, skip=DEFAULT_SKIP, tech=None):
    """ROUTING-ONLY extraction. Cell-internal nets are dropped (a "cell" = a
    circuit that contains devices, or whose name is in `model_cells`); inter-cell
    routing nets are kept with their wire R-C + a driver/receiver pin map. The
    kept nets are wire-only by construction (parent-owned). Returns [route dict]."""
    tech = tech or TECHS["sky130"]
    l2n, netlist, layers, dbu = _build_l2n(gds_path, top_cell, tech)
    mc, skip = set(model_cells or ()), set(skip)

    def opaque(circ):                               # a behavioral-model cell (or a device cell)
        return circ.name.split('$')[0] in mc or any(True for _ in circ.each_device())

    routes = []
    for circuit in netlist.each_circuit():
        if opaque(circuit):                         # drop the whole cell's internal nets
            continue
        for net in circuit.each_net():
            nm = net.expanded_name()
            if nm in skip:
                continue
            drv, recvs, ports = _classify_pins(net)
            if drv is None and not recvs and not ports:
                continue                            # dangling
            c, r = net_geometry_rc(l2n, net, layers, dbu, tech)
            routes.append({"net": f"{circuit.name}/{nm}",   # qualify -> unique across circuits
                           "circuit": circuit.name, "c": c, "r": r,
                           "driver": drv, "receivers": recvs, "ports": ports})
    return routes


def write_routing_spef(routes, path, design="routing") -> int:
    """Routing-only SPEF (same dialect spef.py reads) + a *CONN block per net, and
    a <path>.json sidecar with the driver/receiver pin map for the nvc RC binder.
    spef.parse() ignores *CONN/*I/*P, so net_loads() still returns (Ctot,Rtot)."""
    lines = [
        '*SPEF "IEEE 1481-1998"', f'*DESIGN "{design}"',
        '*DATE "stat-sim klayout2spef --routing-only"', '*VENDOR "stat-sim"',
        '*PROGRAM "klayout2spef"', '*VERSION "1.0"', '*DESIGN_FLOW "EXTRACTION"',
        '*DIVIDER /', '*DELIMITER :', '*BUS_DELIMITER [ ]',
        '*T_UNIT 1 PS', '*C_UNIT 1 FF', '*R_UNIT 1 OHM', '*L_UNIT 1 HENRY',
        '', '*NAME_MAP',
    ]
    ids = {rt["net"]: i for i, rt in enumerate(routes, start=1)}
    for rt in routes:
        lines.append(f'*{ids[rt["net"]]} {rt["net"]}')
    for rt in routes:
        i = ids[rt["net"]]
        c_fF = rt["c"] * 1e15
        lines += ['', f'*D_NET *{i} {c_fF:.6g}', '*CONN']
        if rt["driver"]:
            lines.append(f'*I {rt["driver"]} O')
        for rcv in rt["receivers"]:
            lines.append(f'*I {rcv} I')
        for p in rt["ports"]:
            lines.append(f'*P {p} I')
        if c_fF > 0:
            lines += ['*CAP', f'1 *{i} {c_fF:.6g}']
        if rt["r"] > 0:
            lines += ['*RES', f'1 *{i} *0 {rt["r"]:.6g}']
        lines.append('*END')
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    import json
    with open(path + '.json', 'w') as fh:
        json.dump(routes, fh, indent=1)
    return len(routes)


# ----------------------------------------------------------------------------
# EM detail (Ask C): per-layer / per-via geometry -> distributed SPEF + a
# geometry sidecar hot-spot (hotspot.py) reads for electromigration screening.
# Additive: net_geometry_rc / the writers above are untouched.
# ----------------------------------------------------------------------------
def net_geometry_detail(l2n, net, layers, dbu, tech=None):
    """Break one net into per-layer metal segments + per-via-layer segments, with
    the WIDTH each carries -- the quantity an EM current-density screen needs
    (Imax = Jlin[layer]*width). Returns ([seg dict], c_farad). Same RSH/RVIA model
    as net_geometry_rc, so the segments' R sum to that net's lumped R; in series
    they carry the net's through-current, each checked against its own width limit.
    A metal seg = {layer,width,length,area,r,x1,y1,x2,y2}; a via seg =
    {layer,cuts,r,x1,y1,x2,y2}. Coordinates are the net's per-layer bounding box
    (um) -- enough to place the segment on hot-spot's heat-map."""
    tech = tech or TECHS["sky130"]
    rsh, rvia, carea, cfringe = tech["RSH"], tech["RVIA"], tech["CAREA"], tech["CFRINGE"]
    segs, c_fF = [], 0.0
    for lname in tech["ROUTING"]:
        reg = l2n.shapes_of_net(net, layers[lname])
        a = p = 0.0
        for poly in reg.each():
            a += poly.area(); p += poly.perimeter()
        area, perim = a * dbu * dbu, p * dbu
        if area <= 0:
            continue
        c_fF += carea[lname] * area + cfringe[lname] * perim
        avg_w = 2 * area / perim if perim > 0 else 0.0
        if avg_w <= 0:
            continue
        bb = reg.bbox()
        segs.append({"layer": lname, "width": round(avg_w, 4),
                     "length": round(area / avg_w, 4), "area": round(area, 4),
                     "r": round(rsh[lname] * (perim / (2 * avg_w)), 4),
                     "x1": round(bb.left * dbu, 3), "y1": round(bb.bottom * dbu, 3),
                     "x2": round(bb.right * dbu, 3), "y2": round(bb.top * dbu, 3)})
    for vname in tech["VIA"]:
        reg = l2n.shapes_of_net(net, layers[vname])
        n = reg.count()
        if n <= 0:
            continue
        bb = reg.bbox()
        segs.append({"layer": vname, "cuts": n, "r": round(rvia[vname] * n, 4),
                     "x1": round((bb.left + bb.right) / 2 * dbu, 3),
                     "y1": round((bb.bottom + bb.top) / 2 * dbu, 3),
                     "x2": round((bb.left + bb.right) / 2 * dbu, 3),
                     "y2": round((bb.bottom + bb.top) / 2 * dbu, 3)})
    return segs, c_fF * 1e-15


def extract_detail_rc(gds_path, top_cell=None, skip=DEFAULT_SKIP, tech=None, flatten=False) -> list:
    """Per-net EM detail for every net. Returns [{"net","c","segs":[...]}]."""
    tech = tech or TECHS["sky130"]
    l2n, netlist, layers, dbu = _build_l2n(gds_path, top_cell, tech, flatten)
    out, skip = [], set(skip)
    circuits = list(netlist.each_circuit())
    multi = len(circuits) > 1
    for circuit in circuits:
        for net in circuit.each_net():
            nm = net.expanded_name()
            if nm in skip:
                continue
            segs, c = net_geometry_detail(l2n, net, layers, dbu, tech)
            if not segs:
                continue
            out.append({"net": f"{circuit.name}/{nm}" if multi else nm,
                        "c": c, "segs": segs})
    return out


def write_detail_spef(nets, path, design="detail") -> int:
    """Distributed SPEF (one *RES row per layer/via, chained through net-internal
    nodes) + a `<path>.json` geometry sidecar keyed (net,id) that hot-spot reads.
    spef.py's net_loads() still sums the rows to the same (c_wire, r_wire)."""
    lines = [
        '*SPEF "IEEE 1481-1998"', f'*DESIGN "{design}"',
        '*DATE "stat-sim klayout2spef --detail (EM)"', '*VENDOR "stat-sim"',
        '*PROGRAM "klayout2spef"', '*VERSION "1.0"', '*DESIGN_FLOW "EXTRACTION"',
        '*DIVIDER /', '*DELIMITER :', '*BUS_DELIMITER [ ]',
        '*T_UNIT 1 PS', '*C_UNIT 1 FF', '*R_UNIT 1 OHM', '*L_UNIT 1 HENRY',
        '', '*NAME_MAP',
    ]
    ids = {d["net"]: i for i, d in enumerate(nets, start=1)}
    for d in nets:
        lines.append(f'*{ids[d["net"]]} {d["net"]}')
    geom = {"units": {"r": "ohm", "len": "um", "coord": "um"},
            "design": design, "segments": []}
    for d in nets:
        i = ids[d["net"]]
        c_fF = d["c"] * 1e15
        lines += ['', f'*D_NET *{i} {c_fF:.6g}']
        if c_fF > 0:
            lines += ['*CAP', f'1 *{i} {c_fF:.6g}']
        lines.append('*RES')
        for k, seg in enumerate(d["segs"], start=1):
            n1 = f'*{i}' if k == 1 else f'*{i}:{k-1}'
            n2 = f'*{i}:{k}'
            lines.append(f'{k} {n1} {n2} {seg["r"]:.6g}')
            g = {"net": d["net"], "id": str(k), "layer": seg["layer"]}
            for key in ("width", "length", "cuts", "x1", "y1", "x2", "y2"):
                if key in seg:
                    g[key] = seg[key]
            geom["segments"].append(g)
        lines.append('*END')
    import json
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    with open(path + '.json', 'w') as fh:
        json.dump(geom, fh, indent=1)
    return len(nets)


# ----------------------------------------------------------------------------
# EM layout heat-map: recolor the REAL layout by moving each segment's polygons to
# a per-risk-tier GDS layer (open in klayout with the .lyp). NOT an SVG redraw --
# klayout renders the actual pad shapes; segments just change layer by I/Imax tier.
# ----------------------------------------------------------------------------
EM_TIERS = [   # (worst < thr, name, gds_layer, RGB). grey (within limit) -> hot colour
    (0.5,  "EM_ok",    200, (0x56, 0x5b, 0x61)),   # grey: within limit, recedes
    (1.0,  "EM_watch", 201, (0xb0, 0xa0, 0x30)),   # approaching the limit
    (3.0,  "EM_over",  202, (0xe0, 0x5a, 0x1a)),   # over (orange)
    (10.0, "EM_high",  203, (0xd0, 0x20, 0x3a)),   # red
    (1e18, "EM_crit",  204, (0xd1, 0x3b, 0xbf)),   # magenta: many x over
]


def _em_tier(worst):
    for thr, nm, ly, rgb in EM_TIERS:
        if worst < thr:
            return nm, ly, rgb
    return EM_TIERS[-1][1], EM_TIERS[-1][2], EM_TIERS[-1][3]


def _write_em_lyp(path):
    """KLayout layer-properties colouring the EM risk tiers."""
    rows = []
    for thr, nm, ly, (r, g, b) in EM_TIERS:
        c = "#%02x%02x%02x" % (r, g, b)
        rows.append(f'  <properties><frame-color>{c}</frame-color><fill-color>{c}</fill-color>'
                    f'<dither-pattern>I5</dither-pattern><valid>true</valid><visible>true</visible>'
                    f'<transparent>false</transparent><width>1</width><marked>false</marked>'
                    f'<xfill>false</xfill><animation>0</animation><name>{nm} ({ly}/0)</name>'
                    f'<source>{ly}/0@1</source></properties>')
    open(path, "w").write('<?xml version="1.0" encoding="utf-8"?>\n<layer-properties>\n'
                          + "\n".join(rows) + "\n</layer-properties>\n")


def emit_em_layout(gds_path, csv_path, out_gds, top_cell=None, tech=None, rename=None,
                   out_lyp=None, out_poly=None, flatten=True) -> dict:
    """Recolor the layout by EM risk: copy every net's per-layer metal shapes to a
    risk-TIER GDS layer chosen from that segment's `worst` I/Imax in `csv_path`
    (columns net,layer,worst). Writes out_gds (+ out_lyp klayout colours, + out_poly
    per-tier polygon hulls for a quick viewer). `rename` maps extracted net names to
    the CSV's names. Returns a per-tier segment count."""
    import klayout.db as kdb
    import csv as _csv
    tech = tech or TECHS["sky130"]
    ren = rename or {}
    worst = {(r["net"], r["layer"]): float(r["worst"])
             for r in _csv.DictReader(open(csv_path))}
    l2n, netlist, layers, dbu = _build_l2n(gds_path, top_cell, tech, flatten)
    out = kdb.Layout(); out.dbu = dbu
    top = out.create_cell(top_cell or "EM_MAP")
    tlyr = {ly: out.layer(ly, 0) for _, _, ly, _ in EM_TIERS}
    counts, polys = {}, {}
    for circuit in netlist.each_circuit():
        for net in circuit.each_net():
            raw = net.expanded_name()
            nm = ren.get(raw, raw.replace("$", "n"))
            for lname in tech["ROUTING"]:
                reg = l2n.shapes_of_net(net, layers[lname])
                if reg.is_empty():
                    continue
                w = worst.get((nm, lname))
                if w is None:
                    continue
                tname, ly, rgb = _em_tier(w)
                top.shapes(tlyr[ly]).insert(reg)
                counts[tname] = counts.get(tname, 0) + 1
                if out_poly is not None:
                    hulls = [[[round(pt.x * dbu, 3), round(pt.y * dbu, 3)]
                              for pt in p.each_point_hull()]
                             for p in reg.merged().each()]
                    hulls = [h for h in hulls if len(h) >= 3]
                    if hulls:
                        d = polys.setdefault(tname, {"rgb": "#%02x%02x%02x" % rgb, "polys": []})
                        d["polys"] += hulls
    out.write(out_gds)
    if out_lyp:
        _write_em_lyp(out_lyp)
    if out_poly is not None:
        import json
        json.dump(polys, open(out_poly, "w"))
    return counts


# ----------------------------------------------------------------------------
# Half 2: SPEF writer  (the exact dialect spef.py parses; pure, self-tested)
# ----------------------------------------------------------------------------
def write_spef(nets, path, design="extracted") -> int:
    """Write [NetRC] as IEEE-1481 SPEF (PS/FF/OHM units). Returns the net count.
    One lumped ground cap + one series resistor per net -- the form spef.py
    collapses to (c_wire, r_wire)."""
    lines = [
        '*SPEF "IEEE 1481-1998"',
        f'*DESIGN "{design}"',
        '*DATE "generated by stat-sim klayout2spef"',
        '*VENDOR "stat-sim"',
        '*PROGRAM "klayout2spef"',
        '*VERSION "1.0"',
        '*DESIGN_FLOW "EXTRACTION"',
        '*DIVIDER /', '*DELIMITER :', '*BUS_DELIMITER [ ]',
        '*T_UNIT 1 PS', '*C_UNIT 1 FF', '*R_UNIT 1 OHM', '*L_UNIT 1 HENRY',
        '', '*NAME_MAP',
    ]
    ids = {}
    for i, n in enumerate(nets, start=1):
        ids[n.name] = i
        lines.append(f'*{i} {n.name}')
    for n in nets:
        i = ids[n.name]
        c_fF = n.c * 1e15
        lines += ['', f'*D_NET *{i} {c_fF:.6g}']
        if c_fF > 0:
            lines += ['*CAP', f'1 *{i} {c_fF:.6g}']        # lumped ground cap
        if n.r > 0:
            lines += ['*RES', f'1 *{i} *0 {n.r:.6g}']      # net -> gnd lumped R
        lines.append('*END')
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    return len(nets)


# ----------------------------------------------------------------------------
def _self_test() -> int:
    import tempfile
    import spef                                             # stat-sim's own parser
    nets = [NetRC("sync_d", 12e-15, 350.0),
            NetRC("clk", 4e-15, 100.0),
            NetRC("q", 0.0, 0.0)]                           # a parasitic-free net
    d = tempfile.mkdtemp(prefix="k2s_")
    p = os.path.join(d, "t.spef")
    write_spef(nets, p, design="selftest")
    loads = spef.net_loads(open(p).read())                 # round-trip through spef.py
    for n in nets:
        c, r = loads[n.name]
        if abs(c - n.c) > 1e-18 or abs(r - n.r) > 1e-9:
            print(f"SELF-TEST FAIL: {n.name} wrote ({n.c:g},{n.r:g}) read ({c:g},{r:g})")
            return 1
    # the extracted load drives the on-the-fly delay spef.py/the cells compute
    cw, rw = loads["sync_d"]
    td = spef.rc_delay(100.0, rw, cw)                       # ln2*(100+350)*12e-15
    if abs(td - 0.6931471805599453 * 450.0 * 12e-15) > 1e-18:
        print(f"SELF-TEST FAIL: rc_delay {td:g}"); return 1
    full = spef.parse(open(p).read())
    if "sync_d" not in full or abs(full["sync_d"]["delay"] - 350.0 * 12e-15) > 1e-15:
        print("SELF-TEST FAIL: spef.parse legacy delay mismatch"); return 1
    print("self-test OK: klayout2spef SPEF round-trips through spef.py "
          f"(sync_d -> 12fF/350ohm -> t_pd {td*1e12:.2f}ps; clk -> 4fF/100ohm; q -> 0/0)")
    return 0


def _self_test_routing() -> int:
    import tempfile, json
    import spef
    routes = [
        {"net": "n1", "circuit": "top", "c": 12e-15, "r": 350.0,
         "driver": "U1:Y", "receivers": ["U2:A", "U3:A"], "ports": []},
        {"net": "n2", "circuit": "top", "c": 4e-15, "r": 100.0,
         "driver": "U2:Y", "receivers": ["U4:A"], "ports": ["OUT"]},
    ]
    d = tempfile.mkdtemp(prefix="k2sr_")
    p = os.path.join(d, "r.spef")
    write_routing_spef(routes, p, design="selftest")
    loads = spef.net_loads(open(p).read())          # *CONN ignored -> RC still parses
    conn = spef.net_conn(open(p).read())            # *CONN -> driver/receivers
    cw, rw = loads["n1"]
    if abs(cw - 12e-15) > 1e-18 or abs(rw - 350.0) > 1e-9:
        print(f"SELF-TEST FAIL (routing): net_loads {cw:g},{rw:g}"); return 1
    if conn["n1"]["driver"] != "U1:Y" or conn["n1"]["receivers"] != ["U2:A", "U3:A"]:
        print(f"SELF-TEST FAIL (routing): net_conn {conn['n1']}"); return 1
    if len(json.load(open(p + ".json"))) != 2:
        print("SELF-TEST FAIL (routing): json sidecar"); return 1
    print("self-test OK (routing): SPEF + *CONN + .json round-trips through spef.py "
          "(n1 -> 12fF/350ohm, driver U1:Y, 2 receivers)")
    return 0


def _self_test_detail() -> int:
    """Round-trip the distributed EM SPEF + geometry sidecar through BOTH spef.py
    (RC still sums) and hotspot.build_segments (geometry aligns, Imax set). No klayout."""
    import tempfile, json
    import spef
    nets = [{"net": "pad_drv", "c": 30e-15, "segs": [
        {"layer": "met1", "width": 0.5, "length": 5.0, "r": 1.25,
         "x1": 10, "y1": 20, "x2": 15, "y2": 20},
        {"layer": "mcon", "cuts": 4, "r": 2.325, "x1": 15, "y1": 20, "x2": 15, "y2": 20},
        {"layer": "met3", "width": 4.0, "length": 20.0, "r": 0.235,
         "x1": 15, "y1": 20, "x2": 90, "y2": 20}]}]
    d = tempfile.mkdtemp(prefix="k2sd_")
    p = os.path.join(d, "det.spef")
    write_detail_spef(nets, p, design="selftest")
    # spef.py: the 3 chained *RES rows sum to the net's lumped R
    cw, rw = spef.net_loads(open(p).read())["pad_drv"]
    if abs(rw - (1.25 + 2.325 + 0.235)) > 1e-6 or abs(cw - 30e-15) > 1e-18:
        print(f"SELF-TEST FAIL (detail): net_loads {cw:g},{rw:g}"); return 1
    # geometry sidecar aligns with *RES ids -> hot-spot builds & limits the segments
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hotspot
    segs, _ = hotspot.build_segments(open(p).read(), p + ".json")
    by = {(s.net, s.sid): s for s in segs}
    neck = by[("pad_drv", "1")]
    if neck.layer != "met1" or abs(neck.width - 0.5) > 1e-9:
        print(f"SELF-TEST FAIL (detail): neck geometry {neck}"); return 1
    if abs(neck.imax["avg"] - 0.395e-3) > 1e-12:                # 0.79mA/um * 0.5um
        print(f"SELF-TEST FAIL (detail): neck Imax {neck.imax}"); return 1
    via = by[("pad_drv", "2")]
    if not via.is_via or via.cuts != 4:
        print(f"SELF-TEST FAIL (detail): via {via}"); return 1
    if len(json.load(open(p + ".json"))["segments"]) != 3:
        print("SELF-TEST FAIL (detail): sidecar segment count"); return 1
    # every tech is internally consistent: each routing/via layer has R & C
    # constants and a GDS layer-map entry (catches an IHP-port typo without klayout)
    for name, t in TECHS.items():
        for lyr in t["ROUTING"]:
            if not (lyr in t["RSH"] and lyr in t["CAREA"] and lyr in t["CFRINGE"]
                    and lyr in t["LAYER_MAP"]):
                print(f"SELF-TEST FAIL (tech {name}): routing layer {lyr} missing a constant")
                return 1
        for v in t["VIA"]:
            if not (v in t["RVIA"] and v in t["LAYER_MAP"]):
                print(f"SELF-TEST FAIL (tech {name}): via {v} missing a constant"); return 1
        if not callable(t["connect"]):
            print(f"SELF-TEST FAIL (tech {name}): no connect fn"); return 1
    print("self-test OK (detail): distributed EM SPEF sums to 1.81ohm in spef.py AND "
          "aligns with the geometry sidecar; techs {%s} consistent (sky130 4+4 layers, "
          "ihp-sg13g2 %d metals + %d vias)"
          % (", ".join(TECHS), len(TECHS["ihp-sg13g2"]["ROUTING"]),
             len(TECHS["ihp-sg13g2"]["VIA"])))
    return 0


def _load_model_cells(path):
    if not path:
        return ()
    with open(path) as fh:
        return tuple(ln.strip() for ln in fh if ln.strip() and not ln.startswith("#"))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="klayout2spef",
        description="Extract per-net RC from a GDS via KLayout and write SPEF.")
    ap.add_argument("gds", nargs="?", help="input GDSII")
    ap.add_argument("-o", "--output", help="output SPEF (default <gds>.spef)")
    ap.add_argument("--top", help="top cell (auto-detect if omitted)")
    ap.add_argument("--pdk", default="sky130", choices=list(TECHS),
                    help="PDK tech (layer map + R/C + connectivity). sky130 does "
                         "device recognition; ihp-sg13g2 is routing/EM connectivity.")
    ap.add_argument("--flatten", action="store_true",
                    help="flatten the top cell's hierarchy before extraction (one flat "
                         "net set for a single cell, e.g. an IO pad)")
    ap.add_argument("--routing-only", action="store_true",
                    help="emit routing-only SPEF (cell-internal nets dropped) + *CONN + .json")
    ap.add_argument("--detail", action="store_true",
                    help="emit DISTRIBUTED EM SPEF (per-layer/via *RES segments) + a "
                         "geometry sidecar .json for hot-spot electromigration screening")
    ap.add_argument("--em-layout", action="store_true",
                    help="recolor the LAYOUT by EM risk -> a GDS with each segment's "
                         "polygons on a risk-tier layer + a .lyp (open in klayout)")
    ap.add_argument("--csv", help="EM results CSV (net,layer,worst) from hotspot heatmap")
    ap.add_argument("--rename", help="JSON map {extracted-net: csv-net} for --em-layout")
    ap.add_argument("--model-cells",
                    help="file of cell names to treat as opaque (one per line); "
                         "default = any circuit containing devices")
    ap.add_argument("--self-test", action="store_true",
                    help="round-trip the SPEF writers through spef.py (no klayout)")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test() or _self_test_routing() or _self_test_detail()
    if not a.gds:
        ap.error("a GDS file is required (or use --self-test)")
    design = os.path.splitext(os.path.basename(a.gds))[0]
    tech = TECHS[a.pdk]
    if a.em_layout:
        import json
        if not a.csv:
            ap.error("--em-layout needs --csv (the EM results from hotspot heatmap)")
        ren = json.load(open(a.rename)) if a.rename else {}
        out = a.output or (os.path.splitext(a.gds)[0] + ".em.gds")
        lyp = os.path.splitext(out)[0] + ".lyp"
        poly = os.path.splitext(out)[0] + ".poly.json"
        counts = emit_em_layout(a.gds, a.csv, out, top_cell=a.top, tech=tech, rename=ren,
                                out_lyp=lyp, out_poly=poly, flatten=a.flatten)
        print(f"klayout2spef[{a.pdk}]: EM heat-map layout -> {out} (+ {os.path.basename(lyp)}); "
              f"tiers {counts}")
        print(f"  open:  klayout {out} -l {lyp}")
        return 0
    if a.detail:
        out = a.output or (os.path.splitext(a.gds)[0] + ".em.spef")
        nets = extract_detail_rc(a.gds, top_cell=a.top, tech=tech, flatten=a.flatten)
        n = write_detail_spef(nets, out, design=design)
        print(f"klayout2spef[{a.pdk}]: wrote {n} nets (distributed EM SPEF) -> {out} (+ {out}.json)")
        print(f"  now:  hotspot.py check {out} --harness <stim>   |   hotspot.py heatmap {out} -o em.svg")
        return 0
    if a.routing_only:
        out = a.output or (os.path.splitext(a.gds)[0] + ".routing.spef")
        routes = extract_routing_rc(a.gds, model_cells=_load_model_cells(a.model_cells),
                                    top_cell=a.top, tech=tech)
        n = write_routing_spef(routes, out, design=design)
        print(f"klayout2spef[{a.pdk}]: wrote {n} routing nets -> {out} (+ {out}.json)")
        return 0
    out = a.output or (os.path.splitext(a.gds)[0] + ".spef")
    n = write_spef(extract_net_rc(a.gds, top_cell=a.top, tech=tech), out, design=design)
    print(f"klayout2spef[{a.pdk}]: wrote {n} nets -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# NOTES / refinements (lumped model is intentional, matching spef.py):
#   * coupling caps (*CAP id n1 n2 val) need net-adjacency analysis -- ground+fringe
#     only here; spef.py sums all caps into the node load either way.
#   * distributed RC tree (multiple *RES segments / net) instead of one lumped R --
#     spef.py's lumped (c_wire,r_wire) doesn't use it yet; add when the binder does.
#   * KLayout has no built-in field-solver RCX; this analytic geometry model matches
#     kestrel's and is adequate for the inter-engine ~1% tolerance philosophy.
