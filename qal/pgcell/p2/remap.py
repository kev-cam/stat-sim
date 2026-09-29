#!/usr/bin/env python3
"""PHASE 2 (a)(d) -- remap sha_slice onto the Phase 1 pass-gate cells.

THE STRUCTURAL CLAIM.  Proven by SAT in verify.py; asserted nowhere.

    maj(a,b,c) = (a&b) ^ (a&c) ^ (b&c) = (a ^ b) ? c : a
    c_out      = maj(a, b, c_in)       = (a ^ b) ? c_in : a

The 3-input majority AND the adder carry are the SAME 2:1 MUX, selected by the
half-sum a^b.  A transmission gate is natively a 2:1 MUX.  So the committed
netlist's 14 AOI/OAI cells (6 a21oi + 5 o21ai + 3 a21o) -- which ARE its carry
chain and its majority -- are not decomposed into a NAND2 tree at all.  They are
ABSORBED, one pass-gate mux each.  And the half-sum is SHARED three ways: one
pg_xor2 drives maj[i], the carry mux and the sum xor.

THE RESTORATION RULE (variant pgrN) comes from rule.py, i.e. from Phase 1's
measured per-bank chain data, and caps how many consecutive PASS-GATE levels a
signal may traverse before a rail-restoring cell.

THE INVERSION-ABSORPTION LEVER.  A restoring inverter flips its signal, but
  * an inverted MUX SELECT is free       -- swap the A0/A1 taps, 0 devices
  * an inverted XOR INPUT is free        -- XOR <-> XNOR is a tap swap, 0 devices
  * an XOR-driven module OUTPUT is free  -- emit XNOR, let the restoring inverter
                                            supply the final inversion
so single-inverter restoration is absorbed almost everywhere.  Only a MUX DATA
input and a MUX-driven module output need an inverter PAIR.  The lever is applied
automatically and its effect is counted, not estimated.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
N = 8


class Net:
    __slots__ = ("name", "lvl", "run", "src")

    def __init__(self, name, lvl=0, run=0, src="PI"):
        self.name, self.lvl, self.run, self.src = name, lvl, run, src


class Build:
    """`run` = number of PASS-GATE levels a net has traversed since the last
    rail-restoring cell.  A primary input is run = 0: in the measured banktank
    arrangement the chain head is a driven, rail-referenced source.

    max_run = None means no rule.  Otherwise an input whose run has already
    reached max_run is restored BEFORE it is consumed, so no net ever exceeds
    max_run pass-gate levels."""

    def __init__(self, max_run=None, restore_outputs=False):
        self.lines, self.wires, self.k = [], [], 0
        self.max_run, self.restore_outputs = max_run, restore_outputs
        self.stats = {}
        self.absorbed = {"mux_select": 0, "xor_xnor": 0, "output_from_xor": 0}
        self.pairs = {"mux_data": 0, "output_from_mux_or_shared_xor": 0}

    def w(self, base):
        self.k += 1
        nm = "_%s%d_" % (base, self.k)
        self.wires.append(nm)
        return nm

    def inst(self, typ, conns, y):
        """Cells are kept as RECORDS, not formatted strings, so that the output
        restoration below can rewrite one safely and so fanout can be counted."""
        self.lines.append({"typ": typ, "conns": list(conns), "y": y})
        self.stats[typ] = self.stats.get(typ, 0) + 1

    def fanout(self, net_name):
        """How many cell INPUTS this net drives.  Module outputs are counted by
        the caller."""
        n = 0
        for c in self.lines:
            for pin, v in c["conns"]:
                if v == net_name and pin not in ("X", "Y"):
                    n += 1
        return n

    def flip_xor(self, y):
        """Re-emit the cell driving net y as its XOR<->XNOR twin -- the SAME 8
        devices with the two TG source taps exchanged, zero extra devices.  Only
        legal when that cell drives nothing else; the caller checks."""
        for c in self.lines:
            if c["y"] != y:
                continue
            old = c["typ"]
            new = "pg_xnor2" if old == "pg_xor2" else "pg_xor2"
            c["typ"] = new
            c["conns"] = [((("Y" if new == "pg_xnor2" else "X") if pin in ("X", "Y")
                            else pin), v) for pin, v in c["conns"]]
            self.stats[old] -= 1
            self.stats[new] = self.stats.get(new, 0) + 1
            return True
        return False

    def render(self):
        return ["  %s %s (%s);" % (c["typ"], "U" + c["y"].strip("_"),
                                   ", ".join(".%s(%s)" % kv for kv in c["conns"]))
                for c in self.lines]

    def _inv(self, src):
        y = self.w("r")
        self.inst("sg13g2_inv_1", (("A", src.name), ("Y", y)), y)
        return Net(y, src.lvl + 1, 0, "inv")

    def need(self, net):
        return self.max_run is not None and net.run >= self.max_run

    def restore(self, net, sink):
        """-> (net, inverted).  sink in {'sel','xorin','data'}; 'sel' and 'xorin'
        absorb the inversion for free, 'data' pays for a second inverter."""
        if not self.need(net):
            return net, False
        inv = self._inv(net)
        if sink in ("sel", "xorin"):
            self.absorbed["mux_select" if sink == "sel" else "xor_xnor"] += 1
            return inv, True
        self.pairs["mux_data"] += 1
        return self._inv(inv), False

    # ------------------------------------------------------------- PG cells
    def xor2(self, a, b, force_invert=False):
        """pg_xor2 / pg_xnor2 -- the SAME 8 devices, source-tap swap only."""
        a, fa = self.restore(a, "xorin")
        b, fb = self.restore(b, "xorin")
        flip = fa ^ fb ^ force_invert
        y = self.w("x")
        typ, op = ("pg_xnor2", "Y") if flip else ("pg_xor2", "X")
        self.inst(typ, (("A", a.name), ("B", b.name), (op, y)), y)
        return Net(y, max(a.lvl, b.lvl) + 1, max(a.run, b.run) + 1, "xor")

    def mux2(self, a0, a1, s):
        """pg_mux2: X = S ? A1 : A0.  Inverted select is free -- swap the taps."""
        s, fs = self.restore(s, "sel")
        if fs:
            a0, a1 = a1, a0
        a0, _ = self.restore(a0, "data")
        a1, _ = self.restore(a1, "data")
        y = self.w("m")
        self.inst("pg_mux2",
                  (("A0", a0.name), ("A1", a1.name), ("S", s.name), ("X", y)), y)
        return Net(y, max(a0.lvl, a1.lvl, s.lvl) + 1,
                   max(a0.run, a1.run, s.run) + 1, "mux")


def build(max_run=None, name="pg", restore_outputs=False):
    B = Build(max_run, restore_outputs)
    a = [Net("a[%d]" % i) for i in range(N)]
    b = [Net("b[%d]" % i) for i in range(N)]
    c = [Net("c[%d]" % i) for i in range(N)]
    e = [Net("e[%d]" % i) for i in range(N)]
    f = [Net("f[%d]" % i) for i in range(N)]
    g = [Net("g[%d]" % i) for i in range(N)]
    zero = Net("1'b0", 0, 0, "const")

    p = [B.xor2(a[i], b[i]) for i in range(N)]        # half-sum, SHARED 3 ways
    maj = [B.mux2(a[i], c[i], p[i]) for i in range(N)]      # p ? c : a
    ch = [B.mux2(g[i], f[i], e[i]) for i in range(N)]       # e ? f : g

    k = [zero]                                        # k[i] = carry INTO bit i
    for i in range(N - 1):
        k.append(B.mux2(a[i], k[i], p[i]))            # p ? k : a  (k[0]=0 -> a&b)
    s = [p[0]] + [B.xor2(p[i], k[i]) for i in range(1, N)]

    # -------- chain-legal output restoration (so the block can be cascaded) ---
    # The free XOR<->XNOR lever is legal ONLY when the driving XOR feeds nothing
    # but this one output.  p[0] drives sum[0] AND two mux selects, so flipping
    # it would silently corrupt maj[0] and the carry -- that case takes the pair.
    def fix_out(net):
        if not (restore_outputs and B.need(net)):
            return net.name
        if net.src == "xor" and B.fanout(net.name) == 0 and B.flip_xor(net.name):
            B.absorbed["output_from_xor"] += 1
            return B._inv(net).name
        B.pairs["output_from_mux_or_shared_xor"] += 1
        return B._inv(B._inv(net)).name

    majn = [fix_out(maj[i]) for i in range(N)]
    chn = [fix_out(ch[i]) for i in range(N)]
    sn = [fix_out(s[i]) for i in range(N)]

    body = ["module sha_slice(a, b, c, e, f, g, maj, ch, sum);"]
    body += ["  input [7:0] %s;" % n for n in ("a", "b", "c", "e", "f", "g")]
    body += ["  output [7:0] %s;" % n for n in ("maj", "ch", "sum")]
    body += ["  wire %s;" % x for x in B.wires] + B.render()
    for i in range(N):
        body.append("  assign maj[%d] = %s;" % (i, majn[i]))
        body.append("  assign ch[%d]  = %s;" % (i, chn[i]))
        body.append("  assign sum[%d] = %s;" % (i, sn[i]))
    body.append("endmodule")

    stats = {k2: v for k2, v in sorted(B.stats.items()) if v}
    hdr = ["// AUTO-GENERATED by qal/pgcell/p2/remap.py -- variant '%s'" % name,
           "// max consecutive PASS-GATE levels: %s ; outputs restored: %s"
           % ("unrestricted" if max_run is None else max_run, restore_outputs),
           "// cells: " + ", ".join("%s x%d" % kv for kv in stats.items()),
           "// inversions ABSORBED free: %s" % B.absorbed,
           "// inverter PAIRS forced:    %s" % B.pairs, ""]
    path = os.path.join(OUT, "sha_slice.%s.v" % name)
    open(path, "w").write("\n".join(hdr + body) + "\n")
    return {"variant": name, "max_run": max_run, "restore_outputs": restore_outputs,
            "cell_types": stats, "absorbed_free": B.absorbed,
            "inverter_pairs_forced": B.pairs,
            "max_run_on_outputs": max(x.run for x in maj + ch + s),
            "path": path}


if __name__ == "__main__":
    R = json.load(open(os.path.join(OUT, "RESTORE_RULE.json")))
    V = [build(None, "pg"),
         build(R["N_SEP"], "pgr2"),
         build(R["N_SEP"], "pgr2c", restore_outputs=True),
         build(1, "pgr1"),
         build(1, "pgr1c", restore_outputs=True)]
    json.dump(V, open(os.path.join(OUT, "REMAP_META.json"), "w"), indent=1)
    for m in V:
        print("%-7s run<=%-4s outrest=%-5s %s" % (
            m["variant"], m["max_run"], m["restore_outputs"], m["cell_types"]))
        print("        absorbed %s  pairs %s" % (m["absorbed_free"],
                                                 m["inverter_pairs_forced"]))
