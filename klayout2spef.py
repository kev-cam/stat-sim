#!/usr/bin/env python3
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


@dataclass
class NetRC:
    name: str
    c: float        # total net capacitance, farads
    r: float        # lumped series resistance, ohms


# ----------------------------------------------------------------------------
# Half 1: KLayout extraction  (mirrors kestrel layout/extract.py + parasitics.py)
# ----------------------------------------------------------------------------
def extract_net_rc(gds_path: str, top_cell: str = None, skip=("VPWR", "VGND",
                   "VDD", "VSS", "vpwr", "vgnd", "vdd", "vss")) -> list:
    """Extract per-net (C, R) from a GDS using KLayout's LayoutToNetlist.

    For each net: C = sum_layers (Carea*area + Cfringe*perimeter); R =
    sum_layers (Rsh * n_squares) + sum_vias (Rvia * count). `skip` drops the
    power/ground rails (huge nets, not signal CDC paths) by net name.
    """
    try:
        import klayout.db as kdb
    except ImportError as e:
        raise SystemExit(
            "klayout2spef: the `klayout` module is required for extraction.\n"
            "  pip install klayout   (cp39-cp312 wheels; this box's WSL py3.14 / "
            "Cygwin py3.9 have none -- run on a Linux py3.10-3.12).\n"
            f"  (import error: {e})")

    layout = kdb.Layout()
    layout.read(gds_path)
    dbu = layout.dbu
    tc = layout.cell(top_cell) if top_cell else layout.top_cells()[0]

    l2n = kdb.LayoutToNetlist(kdb.RecursiveShapeIterator(layout, tc, []))

    # register layers (empty layer if absent, so booleans don't crash)
    layers = {}
    for name, (ln, dt) in LAYER_MAP.items():
        li = layout.find_layer(ln, dt)
        layers[name] = l2n.make_layer(li, name) if li is not None else l2n.make_layer(name)

    # device recognition (NFET/PFET) -- same derivation as kestrel
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

    # connectivity stack
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

    l2n.extract_netlist()
    netlist = l2n.netlist()
    netlist.combine_devices()
    netlist.purge()

    def region_area_perim(reg):
        a = p = 0.0
        for poly in reg.each():
            a += poly.area(); p += poly.perimeter()
        return a * dbu * dbu, p * dbu          # um^2, um

    out = []
    skip = set(skip)
    circuits = list(netlist.each_circuit())
    multi = len(circuits) > 1
    for circuit in circuits:
        for net in circuit.each_net():
            nm = net.expanded_name()
            if nm in skip:
                continue
            c_fF = r_ohm = 0.0
            for lname in ROUTING_LAYERS:
                reg = l2n.shapes_of_net(net, layers[lname])    # this net's shapes on this layer
                area, perim = region_area_perim(reg)
                if area <= 0:
                    continue
                c_fF += CAREA[lname] * area + CFRINGE[lname] * perim
                avg_w = 2 * area / perim if perim > 0 else 0.0
                if avg_w > 0:
                    r_ohm += RSH[lname] * (perim / (2 * avg_w))   # ~ n_squares
            for vname in VIA_LAYERS:
                nvia = l2n.shapes_of_net(net, layers[vname]).count()
                r_ohm += RVIA[vname] * nvia                       # series vias (worst case)
            qual = f"{circuit.name}/{nm}" if multi else nm
            out.append(NetRC(qual, c_fF * 1e-15, r_ohm))
    return out


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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="klayout2spef",
        description="Extract per-net RC from a GDS via KLayout and write SPEF.")
    ap.add_argument("gds", nargs="?", help="input GDSII")
    ap.add_argument("-o", "--output", help="output SPEF (default <gds>.spef)")
    ap.add_argument("--top", help="top cell (auto-detect if omitted)")
    ap.add_argument("--self-test", action="store_true",
                    help="round-trip the SPEF writer through spef.py (no klayout)")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.gds:
        ap.error("a GDS file is required (or use --self-test)")
    out = a.output or (os.path.splitext(a.gds)[0] + ".spef")
    nets = extract_net_rc(a.gds, top_cell=a.top)
    n = write_spef(nets, out, design=os.path.splitext(os.path.basename(a.gds))[0])
    print(f"klayout2spef: wrote {n} nets -> {out}")
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
