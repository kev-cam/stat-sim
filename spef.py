#!/usr/bin/env python3
"""
stat-sim spef -- SPEF parasitic back-annotation for the nvc/PWL runtime.

CDC failure depends on *arrival times*: whether a data edge lands inside a
flop's setup/hold aperture is decided by the interconnect delay on the net
feeding it. SPEF (Standard Parasitic Exchange Format) carries the extracted RC
per net; this reads it and produces a per-net delay that the netlist binder adds
to the `after` clauses / TSETUP comparison of the generated logic3da cells
(nvcgen.py). With SPEF annotated, the CDC trap fires on the *real* layout timing,
not zero-delay ideal nets.

This module parses the RC and computes a lumped (Elmore-style) net delay now;
binding those delays onto specific cell instances in the elaborated nvc design
is the next increment (it needs the design's net<->port map).
"""
import re, sys

_UNIT = {"S": 1.0, "MS": 1e-3, "US": 1e-6, "NS": 1e-9, "PS": 1e-12, "FS": 1e-15,
         "F": 1.0, "MF": 1e-3, "UF": 1e-6, "NF": 1e-9, "PF": 1e-12, "FF": 1e-15,
         "OHM": 1.0, "KOHM": 1e3, "MOHM": 1e6}


def _scale(line):
    # e.g. "*T_UNIT 1 PS" -> 1e-12 ;  "*C_UNIT 1 FF" -> 1e-15
    t = line.split()
    return float(t[1]) * _UNIT.get(t[2].upper(), 1.0)


def parse(text: str) -> dict:
    """Parse SPEF -> {net_name: {"c": total_cap_F, "r": total_res_Ohm,
    "delay": lumped_RC_delay_s}}. Honors *T_UNIT/*C_UNIT/*R_UNIT and *NAME_MAP.
    Lumped delay = R_total * C_total (order-of-magnitude; Elmore on the RC tree
    is the refinement)."""
    tu = cu = ru = 1.0
    namemap = {}
    nets = {}
    cur = None
    section = None          # "cap" | "res" within the current *D_NET
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("//"):
            continue
        if ln.startswith("*T_UNIT"): tu = _scale(ln); continue
        if ln.startswith("*C_UNIT"): cu = _scale(ln); continue
        if ln.startswith("*R_UNIT"): ru = _scale(ln); continue
        if ln.startswith("*D_NET"):
            t = ln.split()
            cur = namemap.get(t[1], t[1])
            nets[cur] = {"c": float(t[2]) * cu if len(t) > 2 else 0.0,
                         "r": 0.0, "_csum": 0.0}
            section = None
            continue
        if ln.startswith("*END"):
            cur = None; section = None; continue
        if ln.startswith("*CAP"): section = "cap"; continue
        if ln.startswith("*RES"): section = "res"; continue
        if ln.startswith("*CONN") or ln.startswith("*PORTS"):
            section = None; continue
        if re.match(r"\*\d+\s", ln) and cur is None:            # name map: *123 netname
            t = ln.split(); namemap[t[0]] = t[1]; continue
        if cur is None:
            continue
        t = ln.split()                            # a CAP/RES data row
        if section == "cap":
            # ground cap "id node val" (3) or coupling "id n1 n2 val" (4)
            nets[cur]["_csum"] += float(t[-1]) * cu
        elif section == "res":
            # "id n1 n2 val"
            if len(t) >= 4:
                nets[cur]["r"] += float(t[-1]) * ru
    out = {}
    for n, d in nets.items():
        c = d["_csum"] if d["_csum"] > 0 else d["c"]
        r = d["r"]
        out[n] = {"c": c, "r": r, "delay": r * c}
    return out


LN2 = 0.6931471805599453        # lock-step with disc.py / statsim_disc.vhd


def net_loads(text: str) -> dict:
    """PRIMARY product: {net_name: (c_wire_F, r_wire_ohm)}. The binder turns each
    net into one PL_WIRE(c_wire, r_wire) tap on the multi-UDN node (plus one
    PL_LOAD(Cin) per fan-out receiver, Cin from bfit's characterized cin, NOT
    from SPEF). The on-the-fly delay is then computed at resolution time, not
    baked here. Missing-net policy is the caller's; parse() only yields nets it saw."""
    return {n: (d["c"], d["r"]) for n, d in parse(text).items()}


def net_load(text: str, net: str) -> tuple:
    """One net's (c_wire, r_wire); (0.0, 0.0) + warning if absent (graceful:
    zero wire parasitic, fan-out load still counted by the resolver)."""
    loads = net_loads(text)
    if net not in loads:
        print(f"spef: warning: net {net!r} not in SPEF; using (0,0)", file=sys.stderr)
        return (0.0, 0.0)
    return loads[net]


def node_load(c_wire: float, fanout_cins) -> float:
    """Total node capacitance the resolver would compute: c_wire + sum(Cin)."""
    return c_wire + sum(fanout_cins)


def rc_delay(r_drive: float, r_wire: float, c_node: float,
             tpd0: float = 0.0, k: float = LN2) -> float:
    """On-the-fly lumped single-pole delay, mirroring disc.delay_of:
    tpd0 + k*(r_drive + r_wire)*c_node. This REPLACES the baked r*c constant."""
    return tpd0 + k * (r_drive + r_wire) * c_node


def taps_for_net(text: str, net: str, fanout_cins, mode: str = "lump") -> list:
    """Binder helper: the prob_load taps to instantiate on `net`.
    mode="lump" (default): one lumped load at the driver node --
        [("wire", c_wire, r_wire)] + [("load", Cin, 0.0) per receiver].
    mode="rc": pull the wire R-C into the driver->receiver PATH --
        [("rc", c_wire, r_wire, "a", "b")] + [("load", Cin, 0.0, "b") per receiver]
        (a = near/driver node, b = far/receiver node; statsim_pl_rc straddles them)."""
    c_wire, r_wire = net_load(text, net)
    if mode == "rc":
        return ([("rc", c_wire, r_wire, "a", "b")]
                + [("load", cin, 0.0, "b") for cin in fanout_cins])
    return [("wire", c_wire, r_wire)] + [("load", cin, 0.0) for cin in fanout_cins]


def rc_delay_flight(r: float, c: float, cin: float,
                    alpha: float = 0.5, k: float = LN2) -> float:
    """Wire flight delay (driver end -> receiver end) for the rc tap:
    k*r*(alpha*c + cin). Mirrors disc.wire_flight_delay / the statsim_pl_rc element."""
    return k * r * (alpha * c + cin)


def net_conn(text: str) -> dict:
    """Parse the *CONN sections -> {net: {"driver": "inst:pin"|None,
    "receivers": [...], "ports": [(port,dir)...]}}. This is the reusable interface:
    cell-subtraction (which nets to keep) and the RC-in-path binder (which end
    drives) both read it -- and ANY RCX tool's SPEF carries *CONN. Driver = the
    *I ...O pin (or an input *P port); receivers = *I ...I pins. Coords ignored."""
    namemap, out, cur, in_conn = {}, {}, None, False
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("//"):
            continue
        if ln.startswith("*D_NET"):
            cur = namemap.get(ln.split()[1], ln.split()[1])
            out[cur] = {"driver": None, "receivers": [], "ports": []}
            in_conn = False
            continue
        if ln.startswith("*END"):
            cur = None; in_conn = False; continue
        if ln.startswith("*CONN"):
            in_conn = True; continue
        if ln.startswith("*CAP") or ln.startswith("*RES"):
            in_conn = False; continue
        if cur is None and re.match(r"\*\d+\s", ln):              # name map
            t = ln.split(); namemap[t[0]] = t[1]; continue
        if cur is None or not in_conn:
            continue
        t = ln.split()
        if ln.startswith("*I") and len(t) >= 3:                   # *I inst:pin DIR [*C x y]
            if t[2] == "O":
                out[cur]["driver"] = t[1]
            else:
                out[cur]["receivers"].append(t[1])
        elif ln.startswith("*P") and len(t) >= 3:                 # *P port DIR (boundary)
            out[cur]["ports"].append((t[1], t[2]))
            if t[2] == "I" and out[cur]["driver"] is None:        # input port drives the net
                out[cur]["driver"] = t[1]
    return out


def rc_path_for_net(text: str, net: str, receivers) -> dict:
    """Structural RC-in-path plan for `net` (lumped one-pl_rc, shared far node):
    the statsim_pl_rc(C,R) params + per-receiver Cin and flight delay.
    `receivers` = [(pin, cin), ...]."""
    c_wire, r_wire = net_load(text, net)
    return {
        "net": net,
        "pl_rc": {"C": c_wire, "R": r_wire},
        "receivers": [{"pin": p, "cin": cin,
                       "flight": rc_delay_flight(r_wire, c_wire, cin)}
                      for (p, cin) in receivers],
    }


def net_delays(text: str) -> dict:
    """DEPRECATED back-compat diagnostic: {net: lumped r*c}. Equals the zero-fan-out
    delay term; real timing now comes from rc_delay() over the resolved node load."""
    return {n: d["delay"] for n, d in parse(text).items()}


_SAMPLE = """\
*SPEF "IEEE 1481-1998"
*T_UNIT 1 PS
*C_UNIT 1 FF
*R_UNIT 1 OHM
*NAME_MAP
*1 sync_d
*2 clk
*D_NET *1 12.0
*CAP
1 *1 4.0
2 *1 8.0
*RES
1 *1 N1 200.0
2 *1 N2 150.0
*END
"""


def _self_test() -> int:
    # decomposed load, NOT a baked delay
    cw, rw = net_load(_SAMPLE, "sync_d")     # C=4+8=12fF, R=200+150=350ohm
    if abs(cw - 12e-15) > 1e-18 or abs(rw - 350.0) > 1e-9:
        print(f"SELF-TEST FAIL: net_load wrong c={cw:g} r={rw:g}"); return 1
    # on-the-fly delay grows with fan-out (the whole point): 3 vs 4 receivers @2fF
    c18 = node_load(cw, [2e-15] * 3)         # 12fF wire + 6fF -> 18fF
    c20 = node_load(cw, [2e-15] * 4)         # 12fF wire + 8fF -> 20fF
    d18 = rc_delay(100.0, rw, c18)           # ln2*(100+350)*18e-15
    d20 = rc_delay(100.0, rw, c20)
    if not (d20 > d18 > 0):
        print(f"SELF-TEST FAIL: delay not monotone {d18:g}->{d20:g}"); return 1
    if abs(d18 - LN2 * 450.0 * 18e-15) > 1e-18:
        print(f"SELF-TEST FAIL: delay numeric {d18:g}"); return 1
    # binder taps: 1 wire + 3 loads
    taps = taps_for_net(_SAMPLE, "sync_d", [2e-15] * 3)
    kind, tc, tr = taps[0]
    if (kind != "wire" or abs(tc - 12e-15) > 1e-18 or abs(tr - 350.0) > 1e-9
            or len(taps) != 4 or [t[0] for t in taps[1:]] != ["load"] * 3):
        print(f"SELF-TEST FAIL: taps {taps}"); return 1
    # legacy r*c diagnostic still computes (zero-fan-out term)
    if abs(net_delays(_SAMPLE)["sync_d"] - 4.2e-12) > 1e-15:
        print("SELF-TEST FAIL: legacy r*c diagnostic"); return 1
    # --- RC-in-path / *CONN reusable interface ---
    conn_spef = """\
*C_UNIT 1 FF
*R_UNIT 1 OHM
*NAME_MAP
*1 sync_d
*D_NET *1 12.0
*CONN
*I drv_cell:Y O *C 1.0 2.0
*I rcv_a:A I *C 3.0 4.0
*I rcv_b:A I *C 5.0 6.0
*CAP
1 *1 12.0
*RES
1 *1 *0 350.0
*END
"""
    cn = net_conn(conn_spef)["sync_d"]
    if cn["driver"] != "drv_cell:Y" or cn["receivers"] != ["rcv_a:A", "rcv_b:A"]:
        print(f"SELF-TEST FAIL: net_conn {cn}"); return 1
    # back-compat: net_loads still parses the SAME *CONN-bearing text
    cw, rw = net_loads(conn_spef)["sync_d"]
    if abs(cw - 12e-15) > 1e-18 or abs(rw - 350.0) > 1e-9:
        print(f"SELF-TEST FAIL: net_loads broke on *CONN text ({cw:g},{rw:g})"); return 1
    # rc tap mode + flight delay
    rc = taps_for_net(_SAMPLE, "sync_d", [2e-15] * 3, mode="rc")
    k0, c0, r0, na, nb = rc[0]
    if (k0 != "rc" or abs(c0 - 12e-15) > 1e-18 or abs(r0 - 350.0) > 1e-9
            or na != "a" or nb != "b" or rc[1][0] != "load" or rc[1][3] != "b"):
        print(f"SELF-TEST FAIL: rc taps {rc}"); return 1
    if abs(rc_delay_flight(350.0, 12e-15, 6e-15, 0.5) - LN2 * 350.0 * 12e-15) > 1e-18:
        print("SELF-TEST FAIL: rc_delay_flight"); return 1
    print(f"self-test OK: sync_d C=12fF R=350ohm -> delay {d18*1e12:.2f}ps(3 fo) "
          f"-> {d20*1e12:.2f}ps(4 fo); *CONN driver={cn['driver']} "
          f"recv={len(cn['receivers'])}; rc flight={rc_delay_flight(350.0,12e-15,6e-15)*1e12:.2f}ps")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(_self_test())
    txt = open(sys.argv[1]).read() if len(sys.argv) > 1 else _SAMPLE
    for n, (c, r) in net_loads(txt).items():
        print(f"{n}\tc_wire={c:.3e} F  r_wire={r:.3e} ohm")
