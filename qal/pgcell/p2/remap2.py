#!/usr/bin/env python3
"""PHASE 2 (d) -- the RESTORED pass-gate remap, done properly.

remap.py applies the Phase 1 restoration rule NAIVELY: whenever a restoring
inverter would land on a MUX DATA input it pays for a second inverter to undo
the inversion.  That costs 2 cells and 2 LEVELS per carry stage and blows the
depth out to 23.  It is reported as the naive baseline.

This file applies two levers that cost nothing and are checked by the same SAT
proof:

  POLARITY ALGEBRA.  Track, per net, whether it carries the complement of its
  logical value.  Then a restoring inverter is never "undone" -- the complement
  is simply carried forward and absorbed downstream:
      * XOR/XNOR absorbs any input polarity           (tap swap, 0 devices)
      * a MUX SELECT absorbs its polarity             (swap A0/A1, 0 devices)
      * a MUX's two DATA inputs need only AGREE with each other; the mux output
        then carries that polarity onward
  So the carry chain runs in ALTERNATING polarity: k, ~k, k, ~k ... and each
  stage costs ONE restoring inverter on the critical path instead of two.

  RESTORE CACHING.  The half-sum p[i] drives three sinks (maj[i], the carry mux
  and the sum xor).  Its restoring inverter is emitted ONCE and shared, not once
  per sink.  Likewise ~a[i], which the alternating carry needs at every other
  stage, is a primary-input inverter at level 1 -- cached, and off the critical
  path.

Every variant here is put through the same E1/E2/E3/E5 flow as everything else;
none of these levers is asserted correct.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
N = 8


class Sig:
    """pol=True means the net carries the COMPLEMENT of the logical value."""
    __slots__ = ("name", "lvl", "run", "pol", "src")

    def __init__(self, name, lvl=0, run=0, pol=False, src="PI"):
        self.name, self.lvl, self.run, self.pol, self.src = name, lvl, run, pol, src

    def __repr__(self):
        return "%s%s(L%d,r%d)" % ("~" if self.pol else "", self.name, self.lvl, self.run)


class B2:
    def __init__(self, max_run=None, restore_outputs=False):
        self.cells, self.wires, self.k = [], [], 0
        self.max_run, self.restore_outputs = max_run, restore_outputs
        self.stats = {}
        self.n_inv_restore = 0      # inverters emitted to satisfy the rule
        self.n_inv_polmatch = 0     # inverters emitted only to match mux data polarity
        self.n_inv_output = 0       # inverters emitted at module outputs
        self._invcache = {}
        self.max_run_seen = 0

    def w(self, t):
        self.k += 1
        nm = "_%s%d_" % (t, self.k)
        self.wires.append(nm)
        return nm

    def emit(self, typ, conns, y):
        self.cells.append({"typ": typ, "conns": list(conns), "y": y})
        self.stats[typ] = self.stats.get(typ, 0) + 1

    def inv(self, s, why):
        """One restoring inverter.  CACHED: a net restored once is restored for
        every sink."""
        if s.name in self._invcache:
            return self._invcache[s.name]
        y = self.w("n")
        self.emit("sg13g2_inv_1", (("A", s.name), ("Y", y)), y)
        out = Sig(y, s.lvl + 1, 0, not s.pol, "inv")
        self._invcache[s.name] = out
        setattr(self, "n_inv_" + why, getattr(self, "n_inv_" + why) + 1)
        return out

    def need(self, s):
        return self.max_run is not None and s.run >= self.max_run and s.src != "const"

    def track(self, s):
        self.max_run_seen = max(self.max_run_seen, s.run)
        return s

    # ---------------------------------------------------------------- cells
    def xor2(self, x, y):
        if self.need(x):
            x = self.inv(x, "restore")
        if self.need(y):
            y = self.inv(y, "restore")
        o = self.w("x")
        flip = x.pol ^ y.pol                 # emit the twin that lands on pol 0
        typ, pin = ("pg_xnor2", "Y") if flip else ("pg_xor2", "X")
        self.emit(typ, (("A", x.name), ("B", y.name), (pin, o)), o)
        return self.track(Sig(o, max(x.lvl, y.lvl) + 1, max(x.run, y.run) + 1,
                              False, "xor"))

    def mux2(self, a0, a1, s):
        """logical X = s ? a1 : a0."""
        if self.need(s):
            s = self.inv(s, "restore")
        if s.pol:
            a0, a1 = a1, a0                  # inverted select is free
        if self.need(a0):
            a0 = self.inv(a0, "restore")
        if self.need(a1):
            a1 = self.inv(a1, "restore")
        if a0.pol != a1.pol:
            # the two data inputs must agree; flip whichever is cheaper on the
            # critical path (a primary-input inverter sits at level 1 and is
            # cached, so it costs no depth)
            if a0.src == "const":
                a0 = Sig("1'b1" if a0.name == "1'b0" else "1'b0", 0, 0, a1.pol, "const")
            elif a1.src == "const":
                a1 = Sig("1'b1" if a1.name == "1'b0" else "1'b0", 0, 0, a0.pol, "const")
            elif a0.lvl <= a1.lvl:
                a0 = self.inv(a0, "polmatch")
            else:
                a1 = self.inv(a1, "polmatch")
            if a0.pol != a1.pol:             # the flip may itself have been cached
                a1 = self.inv(a1, "polmatch") if a0.pol != a1.pol else a1
        assert a0.pol == a1.pol, (a0, a1)
        o = self.w("m")
        self.emit("pg_mux2", (("A0", a0.name), ("A1", a1.name), ("S", s.name),
                              ("X", o)), o)
        return self.track(Sig(o, max(a0.lvl, a1.lvl, s.lvl) + 1,
                              max(a0.run, a1.run, s.run) + 1, a0.pol, "mux"))

    # ------------------------------------------------------- module outputs
    def out(self, s):
        """A module output must be pol 0.  If the net is inverted, ONE inverter
        fixes the polarity AND restores it -- the restoration is free."""
        if s.pol:
            return self.inv(s, "output").name
        if self.restore_outputs and self.need(s):
            return self.inv(self.inv(s, "output"), "output").name
        return s.name

    def render(self):
        return ["  %s %s (%s);" % (c["typ"], "U" + c["y"].strip("_"),
                                   ", ".join(".%s(%s)" % kv for kv in c["conns"]))
                for c in self.cells]


def build(max_run=None, name="pgp", restore_outputs=False):
    B = B2(max_run, restore_outputs)
    a = [Sig("a[%d]" % i) for i in range(N)]
    b = [Sig("b[%d]" % i) for i in range(N)]
    c = [Sig("c[%d]" % i) for i in range(N)]
    e = [Sig("e[%d]" % i) for i in range(N)]
    f = [Sig("f[%d]" % i) for i in range(N)]
    g = [Sig("g[%d]" % i) for i in range(N)]

    p = [B.xor2(a[i], b[i]) for i in range(N)]              # half-sum, SHARED
    maj = [B.mux2(a[i], c[i], p[i]) for i in range(N)]      # p ? c : a
    ch = [B.mux2(g[i], f[i], e[i]) for i in range(N)]       # e ? f : g
    k = [Sig("1'b0", 0, 0, False, "const")]
    for i in range(N - 1):
        k.append(B.mux2(a[i], k[i], p[i]))                  # p ? k : a
    s = [p[0]] + [B.xor2(p[i], k[i]) for i in range(1, N)]

    body = ["module sha_slice(a, b, c, e, f, g, maj, ch, sum);"]
    body += ["  input [7:0] %s;" % n for n in ("a", "b", "c", "e", "f", "g")]
    body += ["  output [7:0] %s;" % n for n in ("maj", "ch", "sum")]
    outs = [(i, "maj", B.out(maj[i])) for i in range(N)]
    outs += [(i, "ch", B.out(ch[i])) for i in range(N)]
    outs += [(i, "sum", B.out(s[i])) for i in range(N)]
    body += ["  wire %s;" % x for x in B.wires] + B.render()
    for i, nm, nt in outs:
        body.append("  assign %s[%d] = %s;" % (nm, i, nt))
    body.append("endmodule")

    stats = {k2: v for k2, v in sorted(B.stats.items()) if v}
    hdr = ["// AUTO-GENERATED by qal/pgcell/p2/remap2.py -- variant '%s'" % name,
           "// POLARITY-ALGEBRA + RESTORE-CACHING restored pass-gate remap.",
           "// max consecutive PASS-GATE levels: %s ; outputs restored: %s"
           % ("unrestricted" if max_run is None else max_run, restore_outputs),
           "// cells: " + ", ".join("%s x%d" % kv for kv in stats.items()),
           "// inverters: %d restore, %d mux-data polarity match, %d output"
           % (B.n_inv_restore, B.n_inv_polmatch, B.n_inv_output), ""]
    path = os.path.join(OUT, "sha_slice.%s.v" % name)
    open(path, "w").write("\n".join(hdr + body) + "\n")
    return {"variant": name, "max_run": max_run, "restore_outputs": restore_outputs,
            "cell_types": stats,
            "inverters": {"restore": B.n_inv_restore,
                          "mux_data_polarity_match": B.n_inv_polmatch,
                          "module_output": B.n_inv_output},
            "max_pg_run_seen": B.max_run_seen, "path": path}


if __name__ == "__main__":
    R = json.load(open(os.path.join(OUT, "RESTORE_RULE.json")))
    V = [build(None, "pgp"),
         build(R["N_SEP"], "pgp2"), build(R["N_SEP"], "pgp2c", restore_outputs=True),
         build(1, "pgp1"), build(1, "pgp1c", restore_outputs=True)]
    json.dump(V, open(os.path.join(OUT, "REMAP2_META.json"), "w"), indent=1)
    for m in V:
        print("%-7s run<=%-4s outrest=%-5s %-52s inv %s" %
              (m["variant"], m["max_run"], m["restore_outputs"],
               m["cell_types"], m["inverters"]))
