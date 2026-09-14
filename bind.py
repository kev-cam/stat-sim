#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
"""
stat-sim bind -- a gate netlist bound to prob_load cell models, as an nvc design.

A structural Verilog netlist (Yosys or OpenROAD `write_verilog`) becomes:
  * one VHDL entity per combinational cell TYPE, generated from the Liberty:
    the cell's function as a truth table evaluated on the inputs' probability
    simplexes (exact under independence: p1 = sum over input vectors of
    f(v) * prod p(v_i); px = what is left), the output driven with the
    Liberty-fitted drive resistance of the edge and its intrinsic delay, the
    load-dependent part computed at event time from the resolved node
    (LN2 * (R + rwire) * cload) -- the same on-the-fly delay as the flops;
  * the flops as stat-sim's metastable DFF (sky130_dfxtp) with the Liberty's
    setup / clock-to-Q / drive; an enable flop as a mux in front of it;
  * a top entity with one resolved_pl signal per net, a statsim_pl_load tap
    per receiver pin (the Liberty's pin capacitance) and, with a SPEF, the
    wiring as the node model (spef.py: one statsim_pl_rc per resistor, every
    receiver on its own node) or as one lumped wire tap;
  * a testbench with a clock PERIOD generic, random vectors on the primary
    inputs one picosecond after each rising edge, and a probe that writes
    per cycle each flop's D-node px at the capture edge and every output --
    the raw material of the clock sweep (sweep.py): as the period shrinks,
    the flops whose D is still moving at the edge show px > 0 first, and
    those are the ends of the critical paths.

    bind.py design_pnr.v --top gcd --lib sky130_fd_sc_hd__tt_025C_1v80.lib [--spef design.spef] -o build/gcd
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/usr/local/src/mylex")
import spef as spefmod                                         # noqa: E402

LN2 = 0.6931471805599453
POWER_PINS = {"VPWR", "VGND", "VPB", "VNB", "VDD", "VSS"}
KAPPA = 0.4          # the switching input's transition's share in a cell's delay (--kappa)


# --- the netlist -----------------------------------------------------------------
def read_netlist(path, top):
    txt = open(path).read()
    txt = re.sub(r"/\*.*?\*/", " ", txt, flags=re.S); txt = re.sub(r"//[^\n]*", " ", txt)
    m = re.search(r"\bmodule\s+" + re.escape(top) + r"\s*\((.*?)\)\s*;(.*?)\bendmodule", txt, re.S)
    if not m:
        raise SystemExit("module %s not found in %s" % (top, path))
    body = m.group(2)
    def ident(tok):
        return tok[1:] if tok.startswith("\\") else tok
    ports = {}                       # name -> (dir, width)
    for d, decl in re.findall(r"\b(input|output|inout)\s+([^;]+);", body):
        rng = re.match(r"\s*\[(\d+):(\d+)\]\s*(.*)", decl, re.S)
        width = 0                                   # 0: a scalar; a declared range, even [0:0], is a vector (its bits are name[k])
        if rng:
            width = abs(int(rng.group(1)) - int(rng.group(2))) + 1; decl = rng.group(3)
        for name in re.findall(r"\\\S+|[A-Za-z_][\w$.]*", decl):
            if ident(name) in POWER_PINS:
                continue                            # a P&R netlist lists the supplies as ports
            ports[ident(name)] = (d, width)
    insts = []
    for cell, inst, conns in re.findall(r"\b(sky130_fd_sc_hd__\w+)\s+(\\\S+|[\w$.]+)\s*\((.*?)\)\s*;", body, re.S):
        pins = {}
        for pin, expr in re.findall(r"\.(\w+)\s*\(\s*([^()]*?)\s*\)", conns):
            expr = expr.strip()
            if pin in POWER_PINS or expr == "":
                continue
            pins[pin] = ident(expr)
        t = cell.replace("sky130_fd_sc_hd__", "")
        if not pins or any(k in t for k in ("fill", "tap", "decap")):
            continue                                   # physical cells: no signal pins
        insts.append((t, ident(inst), pins))
    assigns = re.findall(r"\bassign\s+(\\\S+|[\w$.\[\]]+)\s*=\s*(\\\S+|[\w'$.\[\]]+)\s*;", body)
    return ports, insts, [(ident(a), ident(b)) for a, b in assigns]


# --- the cells from the Liberty -----------------------------------------------------
def liberty_cells(lib_path, types):
    from layopt import drive
    cells = drive.read_liberty(lib_path, ["sky130_fd_sc_hd__" + t for t in types])
    txt = open(lib_path).read()

    def block_at(i):
        """the text of the brace-delimited group starting at the first '{' after i"""
        j = txt.index("{", i); depth = 0
        for k in range(j, len(txt)):
            if txt[k] == "{":
                depth += 1
            elif txt[k] == "}":
                depth -= 1
                if depth == 0:
                    return txt[j + 1:k]
        return txt[j + 1:]

    def groups(block, kind):
        """[(name, body)] of the `kind (name) { ... }` groups directly inside block"""
        out = []; depth = 0; k = 0
        while k < len(block):
            ch = block[k]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif depth == 0:
                m = re.match(kind + r'\s*\(([^)]*)\)\s*\{', block[k:])
                if m:
                    inner = 0; start = k + m.end() - 1
                    for q in range(start, len(block)):
                        if block[q] == "{":
                            inner += 1
                        elif block[q] == "}":
                            inner -= 1
                            if inner == 0:
                                out.append((m.group(1), block[start + 1:q])); k = q; break
            k += 1
        return out
    out = {}
    for t in types:
        c = cells.get("sky130_fd_sc_hd__" + t)
        i = txt.find('cell ("sky130_fd_sc_hd__%s")' % t)
        if c is None or i < 0:
            raise SystemExit("cell %s not in the Liberty" % t)
        block = block_at(i)
        ffs = groups(block, "ff")
        ff = None
        if ffs:
            names = ffs[0][0].replace('"', "").split(",")
            ff = (names[0].strip(), names[1].strip() if len(names) > 1 else "", ffs[0][1])
        funcs = {}
        for pname, pbody in groups(block, "pin"):
            fm = re.search(r'function\s*:\s*"([^"]*)"', pbody)
            if fm:
                funcs[pname.replace('"', "")] = fm.group(1)
        inputs = sorted(p for p, pin in c.pins.items() if pin.direction == "input" and p not in POWER_PINS)
        outputs = [p for p, pin in c.pins.items() if pin.direction == "output"]
        cin = {p: c.pins[p].capacitance_fF * 1e-15 for p in inputs}
        drv = {}
        for o in outputs:
            rr, rf, tr, tf = [], [], [], []
            for arc in c.pins[o].arcs:
                for edge, R, T0 in (("rise", rr, tr), ("fall", rf, tf)):
                    try:
                        f = drive.edge_fit(arc, edge)
                    except Exception:
                        continue
                    if f.r_ohm > 0:
                        R.append(f.r_ohm); T0.append(max(f.t0_ps, 0.0))
            med = lambda xs, d: sorted(xs)[len(xs) // 2] if xs else d
            drv[o] = {"r_rise": med(rr, 4000.0), "r_fall": med(rf, 3000.0), "t0_rise": med(tr, 30.0) * 1e-12, "t0_fall": med(tf, 30.0) * 1e-12}
        seq = None
        if ff:
            body = ff[2]
            ns = re.search(r'next_state\s*:\s*"([^"]*)"', body); ck = re.search(r'clocked_on\s*:\s*"([^"]*)"', body)
            seq = {"iq": ff[0], "next_state": ns.group(1) if ns else "D", "clocked_on": ck.group(1) if ck else "CLK"}
        out[t] = {"inputs": inputs, "outputs": outputs, "cin": cin, "drive": drv, "funcs": funcs, "seq": seq}
    return out


def truth_table(func, inputs):
    expr = func.replace("!", " not ").replace("&", " and ").replace("|", " or ").replace("^", " != ").replace("+", " or ").replace("*", " and ")
    tt = []
    for v in range(1 << len(inputs)):
        env = {p: bool((v >> k) & 1) for k, p in enumerate(inputs)}
        tt.append(1 if eval(expr, {}, env) else 0)
    return tt


# --- VHDL ---------------------------------------------------------------------------
HDR = """-- generated by stat-sim bind.py -- do not edit
library ieee;
use ieee.math_real.all;
library statsim;
use statsim.statsim_disc_pkg.all;
"""


def vid(name):
    """a VHDL identifier for a netlist name"""
    s = re.sub(r"[^A-Za-z0-9]", "_", name).strip("_")
    if not s or not s[0].isalpha():
        s = "n_" + s
    return re.sub(r"__+", "_", s)


def comb_entity(t, spec, out_pin, func):
    ins = [p for p in spec["inputs"]]
    used = [p for p in ins if re.search(r"\b%s\b" % re.escape(p), func)] or ins
    tt = truth_table(func, used)
    n = len(used)
    d = spec["drive"][out_pin]
    ports = "; ".join("%s : in resolved_pl" % p for p in used) + "; %s : inout resolved_pl := PL_FLOAT" % out_pin
    return """
entity sc_%(t)s%(suffix)s is
  generic ( R_RISE : real := %(rr).1f; R_FALL : real := %(rf).1f; T0_RISE : real := %(tr).4e; T0_FALL : real := %(tf).4e;
            KAPPA : real := %(kappa).2f );     -- the switching input's transition's share in the delay (layopt drive.py: 0.41 rise / 0.38 fall)
  port ( %(ports)s );
end entity;

architecture pl of sc_%(t)s%(suffix)s is
  type tt_t is array (0 to %(last)d) of integer;
  constant TT : tt_t := (%(tt)s);
  function clamp0 (x : real) return real is       -- a not-yet-resolved record reads as garbage at time 0
  begin
    if x /= x or x < 0.0 then return 0.0; end if;
    return x;
  end function;
begin
  process (%(sens)s)
    variable ins : prob_load_vector(0 to %(nm1)d);
    variable p0, p1, px, pr, r, t0, tsl, g : real;
    variable td : time;
  begin
    ins := (%(insv)s);
    -- the switching input's transition, from its node's driver conductance and load
    -- (LN9 * (R_driver + rwire) * cload, the same estimate the driver uses for its edge)
    tsl := 0.0;
%(slew_of_switching)s
    if tsl > 2.0e-9 then tsl := 2.0e-9; end if;
    p0 := 0.0; p1 := 0.0;
    for v in 0 to %(last)d loop
      pr := 1.0;
      for i in 0 to %(nm1)d loop
        if ((v / (2 ** i)) mod 2) = 1 then pr := pr * ins(i).p1; else pr := pr * ins(i).p0; end if;
      end loop;
      if TT(v) = 1 then p1 := p1 + pr; else p0 := p0 + pr; end if;
    end loop;
    px := 1.0 - p0 - p1;
    if px < 0.0 then px := 0.0; end if;
    if p1 >= %(o)s.p1 then r := R_RISE; t0 := T0_RISE; else r := R_FALL; t0 := T0_FALL; end if;
    td := integer(maximum(t0 + KAPPA * tsl + LN2 * (r + clamp0(%(o)s.rwire)) * clamp0(%(o)s.cload), TPD_FLOOR) * 1.0e15) * 1 fs;
    %(o)s <= transport (p0, p1, px, 1.0 / r, 0.0, 0.0) after td;
  end process;
end architecture;
""" % {"t": t, "suffix": "" if len(spec["outputs"]) == 1 else "_" + out_pin, "rr": d["r_rise"], "rf": d["r_fall"], "tr": d["t0_rise"], "tf": d["t0_fall"],
       "ports": ports, "last": (1 << n) - 1, "tt": ", ".join(str(b) for b in tt), "sens": ", ".join(used), "nm1": n - 1,
       "insv": ", ".join(used) if n > 1 else "0 => " + used[0], "o": out_pin, "kappa": KAPPA,
       "slew_of_switching": "\n".join("    if %s'event then g := %s.gdrv; if g = g and g >= G_EPS then tsl := maximum(tsl, LN9 * (1.0 / g + clamp0(%s.rwire)) * clamp0(%s.cload)); end if; end if;" % (p, p, p, p) for p in used)}


def const_entity(t, out_pin, one):
    return """
entity sc_%(t)s_%(o)s is
  port ( %(o)s : inout resolved_pl := PL_FLOAT );
end entity;
architecture pl of sc_%(t)s_%(o)s is
begin
  %(o)s <= %(v)s;
end architecture;
""" % {"t": t, "o": out_pin, "v": "PL_1" if one else "PL_0"}


MUX_ENTITY = """
entity sc_enmux is
  port ( D : in resolved_pl; DE : in resolved_pl; Q : in resolved_pl; M : inout resolved_pl := PL_FLOAT );
end entity;
architecture pl of sc_enmux is
begin
  process (D, DE, Q)
    variable p0, p1, px, q0, q1 : real;
  begin
    -- a hold flop whose Q is still invalid (power-up, before any enable) holds 0:
    -- otherwise the X feeds back through the mux and the flop never leaves it
    q0 := Q.p0; q1 := Q.p1;
    if Q.px > 0.5 or (q0 + q1) < 0.5 then q0 := 1.0; q1 := 0.0; end if;
    p1 := D.p1 * DE.p1 + q1 * DE.p0;
    p0 := D.p0 * DE.p1 + q0 * DE.p0;
    px := 1.0 - p0 - p1;
    if px < 0.0 then px := 0.0; end if;
    M <= transport (p0, p1, px, G_STRONG, 0.0, 0.0) after 1 ps;
  end process;
end architecture;
"""


def emit(ports, insts, assigns, cells, top, outdir, spef_text=None, spef_mode="tree", dff_spec=None, r_min=30.0):
    os.makedirs(outdir, exist_ok=True)
    dff = dff_spec or {"tsetup": 90e-12, "tcq": 110e-12, "r_drive": 1500.0}
    # --- cell entities ---
    cell_vhd = [HDR + MUX_ENTITY]              # every entity carries its own context clause
    for t, spec in sorted(cells.items()):
        if spec["seq"]:
            continue
        for o in spec["outputs"]:
            f = spec["funcs"].get(o, "")
            if f.strip() in ("0", "1"):
                cell_vhd.append(HDR + const_entity(t, o, f.strip() == "1"))
            else:
                cell_vhd.append(HDR + comb_entity(t, spec, o, f))
    open(os.path.join(outdir, "cells.vhd"), "w").write("\n".join(cell_vhd))
    # --- nets ---
    nets = {}
    def net(n):
        if n in ("1'b0", "1'h0", "1'b1", "1'h1"):
            return "PL_1" if n.endswith("1") else "PL_0"
        if n not in nets:
            nets[n] = "s_" + vid(n)
        return nets[n]
    pin_ports = []
    for p, (d, w) in ports.items():
        for b in (range(w) if w >= 1 else [None]):
            n = p if b is None else "%s[%d]" % (p, b)
            pin_ports.append((n, d, net(n)))
    for a, b in assigns:
        net(a); net(b)
    # the SPEF trees: a receiver pin's node signal (mode "tree"), the wiring as pl_rc elements
    node_of = {}                       # (inst, pin) -> node signal
    tree_decls, tree_insts = [], []
    if spef_text and spef_mode == "tree":
        conn_all = spefmod.net_conn(spef_text)
        trees_all = spefmod.net_rc_trees(spef_text)         # one pass over the SPEF
        for n in list({pins[p] for _, _, pins in insts for p in pins} | {n for n, _, _ in pin_ports}):
            if n not in conn_all or n in ("1'b0", "1'b1", "1'h0", "1'h1"):
                continue
            tree = trees_all.get(n)
            if tree is None:
                continue
            if not tree["res"]:
                continue
            recv = [(r, 0.0) for r in conn_all[n]["receivers"]]
            plan = spefmod.rc_tree_plan(tree, recv, r_min=r_min)
            sig = {plan["root"]: net(n)}
            for k, nd in enumerate(plan["nodes"][1:], 1):
                sig[nd] = "w_%s_%d" % (vid(n), k)
                tree_decls.append("  signal %s : resolved_pl := PL_FLOAT;" % sig[nd])
            if plan["root_cap"] > 0:
                tree_insts.append("  wr_%s : entity statsim.statsim_pl_wire generic map (C => %.4e, R => 0.0) port map (n => %s);" % (vid(n), plan["root_cap"], sig[plan["root"]]))
            for i, (a, b, r, c) in enumerate(plan["elements"]):
                tree_insts.append("  wt_%s_%d : entity statsim.statsim_pl_rc generic map (C => %.4e, R => %.4e, ALPHA => 1.0) port map (a => %s, b => %s);" % (vid(n), i, c, r, sig[a], sig[b]))
            for rv in plan["receivers"]:
                ip = rv["pin"].rsplit(":", 1)
                if len(ip) == 2:
                    node_of[(ip[0], ip[1])] = sig[rv["node"]]
    def pin_net(inst, p, n):
        """the signal a cell's input pin connects to: its SPEF-tree node when there is one"""
        return node_of.get((inst, p), net(n))
    lines = [HDR, "library work;", "", "entity %s_dut is" % top, "  port ("]
    # every port inout: the load taps and the wire taps hang on the port's net (a tap's port is inout)
    lines.append(";\n".join("    %s : inout resolved_pl := PL_FLOAT" % s for n, d, s in pin_ports))
    lines += ["  );", "end entity;", "", "architecture pl of %s_dut is" % top]
    port_sigs = {s for _, _, s in pin_ports}
    body = []
    loads = []
    flops = []               # (inst, D net signal, Q net signal)
    for cell, inst, pins in insts:
        spec = cells[cell]
        iv = "u_" + vid(inst)
        if spec["seq"]:
            dnet = pins.get("D"); qnet = pins.get("Q"); ck = pins.get("CLK")
            if "DE" in pins:
                msig = "m_" + vid(inst)
                body.append("  signal %s : resolved_pl := PL_FLOAT;" % msig)
                body.append("  %s_mux : entity work.sc_enmux port map (D => %s, DE => %s, Q => %s, M => %s);" % (iv, pin_net(inst, "D", dnet), pin_net(inst, "DE", pins["DE"]), net(qnet), msig))
                loads.append((pin_net(inst, "DE", pins["DE"]), spec["cin"].get("DE", 2e-15)))
                dsig = msig
            else:
                dsig = net(dnet)
            if "DE" not in pins:
                dsig = pin_net(inst, "D", dnet)
            body.append("  %s : entity statsim.sky130_dfxtp generic map (TSETUP => %d ps, TCQ0 => %d ps, R_DRIVE => %.1f, SEED => %d) port map (d => %s, clk => %s, q => %s);" % (
                iv, int(dff["tsetup"] * 1e12), int(dff["tcq"] * 1e12), spec["drive"].get("Q", {}).get("r_rise", dff["r_drive"]), 1 + len(flops), dsig, pin_net(inst, "CLK", ck), net(qnet)))
            loads.append((pin_net(inst, "D", dnet), spec["cin"].get("D", 2e-15))); loads.append((pin_net(inst, "CLK", ck), spec["cin"].get("CLK", 2e-15)))
            flops.append((inst, dsig, net(qnet)))
            continue
        for o in spec["outputs"]:
            if o not in pins:
                continue
            f = spec["funcs"].get(o, "")
            if f.strip() in ("0", "1"):
                body.append("  %s_%s : entity work.sc_%s_%s port map (%s => %s);" % (iv, o, cell, o, o, net(pins[o])))
                continue
            used = [p for p in spec["inputs"] if re.search(r"\b%s\b" % re.escape(p), f)] or spec["inputs"]
            pm = ", ".join("%s => %s" % (p, pin_net(inst, p, pins[p]) if p in pins else "PL_0") for p in used) + ", %s => %s" % (o, net(pins[o]))
            body.append("  %s%s : entity work.sc_%s%s port map (%s);" % (iv, "" if len(spec["outputs"]) == 1 else "_" + o, cell, "" if len(spec["outputs"]) == 1 else "_" + o, pm))
        for p in spec["inputs"]:
            if p in pins and pins[p] not in ("1'b0", "1'b1", "1'h0", "1'h1"):
                loads.append((pin_net(inst, p, pins[p]), spec["cin"][p]))
    for a, b in assigns:
        body.append("  %s <= %s;" % (net(a), net(b)))
    decls = ["  signal %s : resolved_pl := PL_FLOAT;" % s for n, s in sorted(nets.items()) if s not in port_sigs]
    # a metastable-capture counter per flop: its Q holds PL_X for the Exp(tau) plateau after a
    # setup violation; a process on Q counts the entries (the testbench reads the counters)
    for k, (i, d, q) in enumerate(flops):
        decls.append("  signal hz_%d : integer := 0;" % k)
        body.append("  hzp_%d : process (%s) begin if %s.px > 0.5 then hz_%d <= hz_%d + 1; end if; end process;" % (k, q, q, k, k))
    taps = ["  l%d : entity statsim.statsim_pl_load generic map (CIN => %.4e) port map (n => %s);" % (k, c, s) for k, (s, c) in enumerate(loads)]
    wires = []
    if spef_text:
        conn = spefmod.net_conn(spef_text)
        lumped = spefmod.net_loads(spef_text)          # parsed once: per-net lookups re-parse the whole file
        for n, s in nets.items():
            if n not in conn:
                continue
            if spef_mode == "tree":
                continue                             # done above: the tree's nodes, elements and receiver binding
            else:
                c, r = lumped.get(n, (0.0, 0.0))
                wires.append("  w%d : entity statsim.statsim_pl_wire generic map (C => %.4e, R => %.4e) port map (n => %s);" % (len(wires), c, r, s))
    wires = tree_insts + wires
    lines += decls + tree_decls + [l for l in body if l.startswith("  signal")] + ["begin"] + [l for l in body if not l.startswith("  signal")] + taps + wires + ["end architecture;", ""]
    open(os.path.join(outdir, "top.vhd"), "w").write("\n".join(lines))
    # --- testbench ---
    ins = [(n, s) for n, d, s in pin_ports if d == "input"]
    outs = [(n, s) for n, d, s in pin_ports if d != "input"]
    clk = next((s for n, s in ins if n.lower() in ("clk", "clock", "core_clock")), None)
    rst = [s for n, s in ins if n.lower() in ("reset", "rst", "rst_n", "resetn")]
    tb = [HDR, "library work;", "use std.textio.all;", "", "entity %s_tb is" % top,
          "  generic ( PERIOD : time := 4 ns; SEED : integer := 1; CYCLES : integer := 300; RESET_CYCLES : integer := 4; TRACE : string := \"trace.txt\" );", "end entity;", "",
          "architecture sim of %s_tb is" % top, "  signal clk_v : bit := '0';", "  signal cycle : integer := 0;"]
    tb += ["  signal %s : resolved_pl := PL_0;" % s for n, s in ins] + ["  signal %s : resolved_pl := PL_FLOAT;" % s for n, s in outs]
    tb += ["begin", "  clk_v <= not clk_v after PERIOD / 2;"]
    if clk:
        tb.append("  %s <= PL_1 when clk_v = '1' else PL_0;" % clk)
    tb.append("  dut : entity work.%s_dut port map (%s);" % (top, ", ".join("%s => %s" % (s, s) for _, _, s in pin_ports)))
    tb += ["  stim : process (clk_v)", "    variable s1, s2 : integer := SEED;", "    variable u : real;", "  begin", "    if clk_v'event and clk_v = '1' then", "      cycle <= cycle + 1;"]
    for n, s in ins:
        if s == clk:
            continue
        if s in rst:
            tb.append("      if cycle < RESET_CYCLES then %s <= %s after 1 ps; else %s <= %s after 1 ps; end if;" % (s, "PL_0" if n.lower().endswith("_n") or n.lower() == "resetn" else "PL_1", s, "PL_1" if n.lower().endswith("_n") or n.lower() == "resetn" else "PL_0"))
        else:
            tb.append("      uniform(s1, s2, u); if u < 0.5 then %s <= PL_0 after 1 ps; else %s <= PL_1 after 1 ps; end if;" % (s, s))
    tb += ["    end if;", "  end process;", "",
           "  probe : process (clk_v)", "    file f : text open write_mode is TRACE;", "    variable l : line;"]
    # the flops' D nodes inside the dut, by external name -- declared here, after the dut
    # instance in elaboration order (an alias of an external name in the architecture's
    # declarative part would be elaborated before the instance exists)
    for k, (i, d, q) in enumerate(flops):
        tb.append("    alias hz_%d is << signal .%s_tb.dut.hz_%d : integer >>;" % (k, top, k))
    tb += ["  begin",
           "    if clk_v'event and clk_v = '1' then", "      write(l, cycle); write(l, string'(\" \"));"]
    tb.append("      -- flops: metastable captures so far, one count per flop (%s)" % " ".join(i for i, _, _ in flops))
    for k, (i, d, q) in enumerate(flops):
        tb.append("      write(l, hz_%d); write(l, string'(\",\"));" % k)
    tb.append("      write(l, string'(\" \"));")
    tb.append("      -- outputs (%s)" % " ".join(n for n, _ in outs))
    for n, s in outs:
        tb.append("      if %s.px > 0.5 then write(l, string'(\"X\")); elsif %s.p1 > 0.5 then write(l, string'(\"1\")); else write(l, string'(\"0\")); end if;" % (s, s))
    tb += ["      writeline(f, l);", "      if cycle >= CYCLES then std.env.finish; end if;", "    end if;", "  end process;", "end architecture;", ""]
    open(os.path.join(outdir, "tb.vhd"), "w").write("\n".join(tb))
    open(os.path.join(outdir, "flops.txt"), "w").write("\n".join("%s %s %s" % f for f in flops) + "\n")
    open(os.path.join(outdir, "outputs.txt"), "w").write("\n".join(n for n, _ in outs) + "\n")
    return len(nets), len(insts), len(flops), len(loads), len(wires)


def main():
    a = sys.argv[1:]
    src = a[0]
    top = a[a.index("--top") + 1]
    lib = a[a.index("--lib") + 1]
    out = a[a.index("-o") + 1] if "-o" in a else "build/" + top
    spef_text = open(a[a.index("--spef") + 1]).read() if "--spef" in a else None
    mode = a[a.index("--spef-mode") + 1] if "--spef-mode" in a else "tree"
    r_min = float(a[a.index("--r-min") + 1]) if "--r-min" in a else 30.0     # tree mode: resistors below this (ohm) are merged away (gcd: 820 -> 140 elements, the ALU 21k -> ~1k)
    global KAPPA
    KAPPA = float(a[a.index("--kappa") + 1]) if "--kappa" in a else KAPPA
    ports, insts, assigns = read_netlist(src, top)
    cells = liberty_cells(lib, sorted({c for c, _, _ in insts}))
    n_nets, n_inst, n_ff, n_loads, n_wires = emit(ports, insts, assigns, cells, top, out, spef_text, mode, r_min=r_min)
    print("bind: %s -> %s: %d instances (%d flops, %d cell types), %d nets, %d load taps, %d wire taps" % (src, out, n_inst, n_ff, len(cells), n_nets, n_loads, n_wires))


if __name__ == "__main__":
    main()
