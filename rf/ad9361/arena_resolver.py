#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
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
          recomputed when any antenna radiates something new (an antenna or a target that moves changes
          what the next event sees; moving is not an event).  Antennas on the same platform (the
          antenna's generic, not 0) do not hear each other directly;
  scatterers: point targets (rf_spec_scatterer); every antenna hears every antenna's signal off them;
and a wrapper entity resolved_<design> that holds the design (as `dut`) beside its resolver.

The resolver also holds the bridge to the spectral accelerator (accel/spectral_accel_pkg.vhd): a process
that does nothing unless the run is compiled for it (spectral_accel_on.vhd), and then hands the accelerator the same wiring (a wire
between a chip's tx1 or rx1 pin and an antenna's feed; the arena's antennas) and moves the design's
data and processing out and back when SPECTRAL_ACCEL_SCHEDULE says.  A design the accelerator declines
(a wire that is not chip pin to antenna feed, ...) stays in nvc.

Used as a module (emit()) by an2597_nvc.py; the payload type is work.rf_spectrum_pkg.rf_spectrum.
"""


def emit(design, wires, arena, generics=None, scatterers=()):
    """VHDL text: entity resolver_<design> and the wrapper resolved_<design>.  generics: {name: VHDL
    literal} for the design's generic map in the wrapper.  Instance names may be generate paths
    ("g(3).ant_tx")."""
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
    w("use work.spectral_accel_pkg.all;")
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
        w("    alias air_plat_%d is << signal .%s.dut.%s.plat : integer >>;" % (j, top, ant))
    for j, sc in enumerate(scatterers):
        w("    alias sc_pos_%d is << signal .%s.dut.%s.pos : rf_position >>;" % (j, top, sc))
        w("    alias sc_rcs_%d is << signal .%s.dut.%s.rcs : real >>;" % (j, top, sc))
    # the accelerator's handles of the instances the wiring names
    ids = {}
    for inst in sorted(set([e.rsplit(".", 1)[0] for net in wires for e in net] + list(arena))):
        ids[inst] = "accel_id_%d" % len(ids)
        w("    alias %s is << signal .%s.dut.%s.accel_id : real >>;" % (ids[inst], top, inst))
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
        # sensitive to what is radiated, not to the positions: an antenna that moves changes what the next
        # event sees, it is not an event itself
        w("    arena: process (%s)" % ", ".join("air_drv_%d" % j for j in range(n)))
        ns = len(scatterers)
        w("        variable d, r : rf_spectrum_vector(0 to %d);" % (n - 1))
        w("        variable p : rf_position_vector(0 to %d);" % (n - 1))
        w("        variable pl : integer_vector(0 to %d);" % (n - 1))
        w("        variable sp : rf_position_vector(0 to %d);" % (ns - 1))
        w("        variable sr : real_vector(0 to %d);" % (ns - 1))
        w("    begin")
        for j in range(n):
            w("        d(%d) := air_drv_%d;" % (j, j))
            w("        p(%d) := air_pos_%d;" % (j, j))
            w("        pl(%d) := air_plat_%d;" % (j, j))
        for j in range(ns):
            w("        sp(%d) := sc_pos_%d;" % (j, j))
            w("        sr(%d) := sc_rcs_%d;" % (j, j))
        w("        r := arena_resolve(d, p, pl, sp, sr, sim_time);")
        for j in range(n):
            w("        air_oth_%d := r(%d);" % (j, j))
        w("    end process;")
    w("")
    w("    -- the bridge to the spectral accelerator")
    w("    accel: process")
    w("        variable t : real;")
    w("    begin")
    w("        if not sa_available then")
    w("            wait;")
    w("        end if;")
    w("        wait for 0 fs;                       -- every chip and antenna has its handle")
    w("        wait for 0 fs;")
    pins = {"tx1": "0.0", "rx1": "1.0"}
    for net in wires:
        ends = [e.rsplit(".", 1) for e in net]
        chip = [e for e in ends if e[1] in pins]
        feed = [e for e in ends if e[1] == "feed"]
        if len(net) == 2 and len(chip) == 1 and len(feed) == 1:
            w("        sa_wire(%s, %s, %s);" % (ids[chip[0][0]], pins[chip[0][1]], ids[feed[0][0]]))
        else:
            w("        -- %s: not a chip pin to an antenna feed; the accelerator will decline the design" % " <-> ".join(net))
            for inst, port in ends:
                if port == "feed":
                    w("        sa_wire(%s, 0.0, %s);" % (ids[inst], ids[inst]))
    for ant in arena:
        w("        sa_arena_antenna(%s);" % ids[ant])
    w("        if sa_commit /= 0.0 then")
    w("            for i in 0 to integer(sa_schedule_count) - 1 loop")
    w("                t := sa_schedule_time(real(i));")
    w("                if t > sim_time then")
    w("                    wait for (t - sim_time) * 1 sec;")
    w("                end if;")
    w("                wait for 1 fs;               -- after everything at that time has settled")
    w("                if sa_schedule_mode(real(i)) /= 0.0 then")
    w("                    if sa_mode /= SA_ON_ACCEL then")
    w("                        sa_set_mode(1.0);")
    w("                        sa_mode <= SA_ON_ACCEL;          -- the chips push their state and pins out")
    w("                    end if;")
    w("                elsif sa_mode = SA_ON_ACCEL then")
    w("                    sa_set_mode(0.0);")
    w("                    sa_mode <= SA_RESTORING;             -- the chips pull them back")
    w("                    wait for 1 fs;")
    w("                    sa_mode <= SA_IN_NVC;")
    w("                end if;")
    w("            end loop;")
    w("        end if;")
    w("        wait;")
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
