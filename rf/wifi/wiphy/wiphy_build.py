#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
wiphy_build.py -- compile Nuand's bladeRF-wiphy (an IEEE 802.11 modem in VHDL, GPL-2.0, not part of
this repository) into nvc libraries, with the stand-ins of this directory for the vendor primitives
it instantiates.

    python3 wiphy_build.py --src <bladeRF-wiphy checkout> --nvc-build <nvc build> --work <dir> [--tb]

What it does, in order:
  1. empty libraries for the library clauses that name vendor IP the design no longer uses
     (fft64, viterbi_decoder) or that only hold a component's model (wlan_pll), and `nuand`;
  2. the stand-ins: altera_mf (scfifo, dcfifo), lpm (lpm_divide), and wlan_pll into the modem's
     library;
  3. the modem's own files in the order of its fpga/common/wlan_files.tcl, into library `wlan`;
     with --tb its test benches as well.

The sources are compiled as they are but for the entries of FIXUPS, each a change made to a copy in
the work directory, never to the checkout, and each printed when it is applied.
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def reorder_fft(text):
    """fft.vhd: architecture `mult` instantiates fft(arch), which follows it in the file.  nvc binds an
    instance when it analyses it, so `arch` has to come first."""
    m1 = re.search(r"^architecture mult of fft is.*?^end architecture mult;[ \t]*\n", text, re.S | re.M)
    m2 = re.search(r"^architecture arch of fft is.*?^end architecture;[ \t]*\n?", text, re.S | re.M)
    if not (m1 and m2 and m1.end() <= m2.start()):
        return None
    return text[:m1.start()] + m2.group(0) + "\n" + m1.group(0) + text[m1.end():m2.start()] + text[m2.end():]


def drop_line(pattern):
    def fix(text):
        new, n = re.subn(pattern, "", text, count=1, flags=re.M)
        return new if n == 1 else None
    return fix


def keep_ack_mac(text):
    """wlan_rx_framer.vhd: the framer's state record has a field ack_mac (the address an acknowledgement
    goes to) that its reset function NULL_STATE leaves unassigned.  The state is set to NULL_STATE when a
    frame is done, a few clocks before the address is taken for the acknowledgement: in a simulator the
    field is then undefined and the acknowledgement goes out with a dead address and FCS.  Hardware
    keeps a register that a reset does not mention, and the acknowledgements of the real thing reach
    their senders, so the copy says so: the field holds through NULL_STATE (not through the asynchronous
    reset)."""
    sync_old = ("            if( framer_quiet_reset = '1' ) then\n"
                "                current <= NULL_STATE ;\n")
    comb_old = "future <= NULL_STATE ;\n"
    if text.count(sync_old) != 1 or text.count(comb_old) != 2:
        return None
    text = text.replace(sync_old, sync_old + "                current.ack_mac <= current.ack_mac ;\n")
    return text.replace(comb_old, comb_old + "                future.ack_mac <= current.ack_mac ;\n")


def replace_n(old, new, n):
    def fix(text):
        return text.replace(old, new) if text.count(old) == n else None
    return fix


def replace_once(old, new):
    return replace_n(old, new, 1)


BITS14 = ("bit counts declared up to 12000, which a frame over about 1470 octets passes: given the 14 bits "
          "that synthesis gives them (to 16383)")


# file name -> (what is done to the copy, why)
FIXUPS = {
    "fft.vhd": (reorder_fft, "architecture arch moved before architecture mult, which instantiates it"),
    "wlan_tx_p.vhd": (drop_line(r"^[ \t]*rv\.num_data_symbols := 0 ;[ \t]*\n"),
                      "NULL_PARAMS assigns 0 to num_data_symbols (range 1 to 1366) and then 1: the first assignment dropped"),
    # The receiver keeps a frame's bit count, 8 x (length + 2), and a running count that passes it by up
    # to a symbol's worth, in fields declared 0 (or 1) to 12000.  Synthesis makes them 14 bits and the
    # hardware takes frames of some 2000 octets; a simulator stops at the declared bound, on any frame
    # over 1471 octets at 54 Mb/s (1498 at 6 Mb/s).  The declarations are given the 14 bits.
    "wlan_rx_p.vhd": (replace_n("natural range 1 to 12000 ;", "natural range 1 to 16383 ;", 1), BITS14),
    "wlan_rx_controller.vhd": (replace_n("natural range 0 to 12000 ;", "natural range 0 to 16383 ;", 2), BITS14),
    "wlan_depuncturer.vhd": (replace_n("natural range 0 to 12000 ;", "natural range 0 to 16383 ;", 2), BITS14),
    "wlan_rx_framer.vhd": (keep_ack_mac,
                           "the acknowledgement's address (ack_mac) is not given a value by the framer's reset "
                           "function and is undefined in simulation by the time it is used: made to hold, as a "
                           "register that a reset does not mention does in hardware"),
    "wlan_bsd.vhd": (replace_once("signed(bsds.bsds(0)'range)", "signed(7 downto 0)"),
                     "function compress sizes a variable by the range of the port bsds, which nvc does not let a pure "
                     "function name: the range written out (an element of bsd_array_t, 7 downto 0)"),
}

EMPTY_LIBS = ("fft64", "viterbi_decoder", "wlan_pll", "nuand", "pll")


def file_lists(src):
    """The lists of fpga/common/wlan_files.tcl: name -> paths."""
    tcl = os.path.join(src, "fpga", "common", "wlan_files.tcl")
    text = open(tcl).read()
    out = {}
    for name in ("wlan_common", "wlan_synthesis_tx", "wlan_synthesis_rx", "wlan_synthesis_top", "wlan_sim"):
        m = re.search(r"set %s \[\s*list(.*?)\]\s*;" % name, text, re.S)
        if not m:
            raise SystemExit("%s: no list %s" % (tcl, name))
        out[name] = [os.path.normpath(os.path.join(src, "fpga", "common", f.strip()))
                     for f in re.findall(r"file join \$here ([^\]]+)\]", m.group(1))]
    return out


class Build:
    def __init__(self, src, nvc_build, work, verbose=True):
        self.src, self.work, self.verbose = src, os.path.abspath(work), verbose
        self.nvc = [os.path.join(nvc_build, "bin", "nvc"), "--std=2008", "-H", "1g",
                    "-L", os.path.join(nvc_build, "lib"), "-L", self.work]
        os.makedirs(self.work, exist_ok=True)
        self.applied = []

    def say(self, *a):
        if self.verbose:
            print(*a)
            sys.stdout.flush()

    def run(self, lib, *args, cwd=None):
        cmd = self.nvc + ["--work=%s:%s" % (lib, os.path.join(self.work, lib))] + list(args)
        r = subprocess.run(cmd, cwd=cwd or self.work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        return r.returncode, r.stdout

    def analyse(self, lib, path, relaxed=False):
        code, out = self.run(lib, "-a", *(["--relaxed"] if relaxed else []), path)
        if code != 0:
            raise SystemExit("analysis of %s failed:\n%s" % (path, out[:3000]))
        return out

    def source(self, path):
        """The file to analyse for `path`: itself, or its fixed-up copy."""
        fix = FIXUPS.get(os.path.basename(path))
        if not fix:
            return path
        new = fix[0](open(path).read())
        if new is None:
            self.say("   note: %s is not as expected, no change made (%s)" % (os.path.basename(path), fix[1]))
            return path
        copy = os.path.join(self.work, "fixed_" + os.path.basename(path))
        open(copy, "w").write(new)
        self.applied.append((os.path.basename(path), fix[1]))
        self.say("   changed in a copy: %s: %s" % (os.path.basename(path), fix[1]))
        return copy

    def libraries(self, nuand=()):
        """The libraries the modem names.  `nuand`: files for the library of that name (the complete
        modem, wlan_top, takes its host interface's types from the bladeRF's fifo_readwrite_p.vhd)."""
        empty = os.path.join(self.work, "empty_lib.vhd")
        open(empty, "w").write("package empty_lib is end package;\n")
        for lib in EMPTY_LIBS:
            self.analyse(lib, empty)
        for f in nuand:
            self.analyse("nuand", f)
        self.analyse("altera_mf", os.path.join(HERE, "altera_mf_sim.vhd"))
        self.analyse("lpm", os.path.join(HERE, "lpm_sim.vhd"))

    def modem(self, parts=("wlan_common", "wlan_synthesis_tx", "wlan_synthesis_rx", "wlan_synthesis_top"), extra=()):
        lists = file_lists(self.src)
        self.analyse("wlan", os.path.join(HERE, "wlan_pll_sim.vhd"))
        done = set()
        n = 0
        for part in parts:
            for f in lists[part]:
                if f in done:
                    continue             # the tcl lists name a few files twice
                done.add(f)
                self.analyse("wlan", self.source(f), relaxed=True)
                n += 1
        for f in extra:
            self.analyse("wlan", self.source(f), relaxed=True)
            n += 1
        self.say("   %d files of the modem analysed into library wlan" % n)

    def elaborate(self, top, *generics):
        code, out = self.run("wlan", "-e", *generics, top)
        if code != 0:
            raise SystemExit("elaboration of %s failed:\n%s" % (top, out[:3000]))

    def simulate(self, top, cwd, *args):
        return self.run("wlan", "-r", *args, top, cwd=cwd)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=os.environ.get("WIPHY_SRC"), help="a bladeRF-wiphy checkout (default: $WIPHY_SRC)")
    ap.add_argument("--nvc-build", default=os.environ.get("NB"), help="an nvc build directory (default: $NB)")
    ap.add_argument("--work", required=True, help="directory for the libraries")
    ap.add_argument("--tb", action="store_true", help="also the modem's own test benches")
    a = ap.parse_args()
    if not a.src or not a.nvc_build:
        raise SystemExit("needs --src (or WIPHY_SRC) and --nvc-build (or NB)")
    b = Build(a.src, a.nvc_build, a.work)
    b.libraries()
    b.modem(parts=("wlan_common", "wlan_synthesis_tx", "wlan_synthesis_rx", "wlan_synthesis_top") + (("wlan_sim",) if a.tb else ()))
    print("built in %s" % b.work)


if __name__ == "__main__":
    main()
