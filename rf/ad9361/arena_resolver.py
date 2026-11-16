#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
arena_resolver.py -- write the resolver network of a spectral RF design for nvc --std=2040.

In --std=2040 a component's RF pin is a std_logic port whose payload travels on the port's implicit
'driver and 'other signals; nothing joins those until a resolver does, through external names.  This
writes that resolver for a design given as
  wires:  nets that are wires; each a list of "instance.port" ends (two ends: each sees the other;
          more: each sees the sum of the others, rf_spectrum_pkg.wire_resolve);
  arena:  antenna instances (rf_spec_antenna); each antenna's air'other becomes the sum of every other
          antenna's air'driver through free space between their positions (rf_spectrum_pkg.arena_resolve),
          recomputed when any antenna radiates something new or moves;
and a wrapper entity resolved_<design> that holds the design (as `dut`) beside its resolver.

Used as a module (emit()) by an2597_nvc.py; the payload type is work.rf_spectrum_pkg.rf_spectrum.
"""


def emit(design, wires, arena, generics=None):
    """VHDL text: entity resolver_<design> and the wrapper resolved_<design>.  generics: {name: VHDL
    literal} for the design's generic map in the wrapper."""
    top = "resolved_%s" % design
    o = []
    w = o.append
    w("-- Resolver network for %s (nvc --std=2040), written by arena_resolver.py." % design)
    for i, net in enumerate(wires):
        w("-- wire %d: %s" % (i, " <-> ".join(net)))
    w("-- arena: %s" % ", ".join(arena))
    w("library ieee;")
    w("use ieee.std_logic_1164.all;")
    w("use work.rf_spectrum_pkg.all;")
    w("")
    w("entity resolver_%s is" % design)
    w("end entity;")
    w("")
    w("architecture generated of resolver_%s is" % design)
    for i, net in enumerate(wires):
        for j, end in enumerate(net):
            w("    alias w%d_drv_%d is << signal .%s.dut.%s.driver : rf_spectrum >>;" % (i, j, top, end))
            w("    alias w%d_oth_%d is << signal .%s.dut.%s.other : rf_spectrum >>;" % (i, j, top, end))
    for j, ant in enumerate(arena):
        w("    alias air_drv_%d is << signal .%s.dut.%s.air.driver : rf_spectrum >>;" % (j, top, ant))
        w("    alias air_oth_%d is << signal .%s.dut.%s.air.other : rf_spectrum >>;" % (j, top, ant))
        w("    alias air_pos_%d is << signal .%s.dut.%s.pos : rf_position >>;" % (j, top, ant))
    w("begin")
    for i, net in enumerate(wires):
        n = len(net)
        w("    wire_%d: process (%s)" % (i, ", ".join("w%d_drv_%d" % (i, j) for j in range(n))))
        if n == 2:
            w("    begin")
            w("        w%d_oth_0 := w%d_drv_1;" % (i, i))
            w("        w%d_oth_1 := w%d_drv_0;" % (i, i))
        else:
            w("        variable d, r : rf_spectrum_vector(0 to %d);" % (n - 1))
            w("    begin")
            for j in range(n):
                w("        d(%d) := w%d_drv_%d;" % (j, i, j))
            w("        r := wire_resolve(d, sim_time);")
            for j in range(n):
                w("        w%d_oth_%d := r(%d);" % (i, j, j))
        w("    end process;")
        w("")
    if arena:
        n = len(arena)
        w("    arena: process (%s)" % ", ".join(["air_drv_%d" % j for j in range(n)] + ["air_pos_%d" % j for j in range(n)]))
        w("        variable d, r : rf_spectrum_vector(0 to %d);" % (n - 1))
        w("        variable p : rf_position_vector(0 to %d);" % (n - 1))
        w("    begin")
        for j in range(n):
            w("        d(%d) := air_drv_%d;" % (j, j))
            w("        p(%d) := air_pos_%d;" % (j, j))
        w("        r := arena_resolve(d, p, sim_time);")
        for j in range(n):
            w("        air_oth_%d := r(%d);" % (j, j))
        w("    end process;")
    w("end architecture;")
    w("")
    w("entity %s is" % top)
    w("end entity;")
    w("")
    w("architecture wrapper of %s is" % top)
    w("begin")
    if generics:
        w("    dut: entity work.%s" % design)
        w("        generic map (%s);" % ", ".join("%s => %s" % kv for kv in generics.items()))
    else:
        w("    dut: entity work.%s;" % design)
    w("    resolver: entity work.resolver_%s;" % design)
    w("end architecture;")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    print(emit("example", [["radio.tx1", "ant_a.feed"], ["radio2.rx1", "ant_b.feed"]], ["ant_a", "ant_b"]))
