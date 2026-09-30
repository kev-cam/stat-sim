#!/usr/bin/env python3
"""Warm a DISJOINT subset of the PyMS geometry set.

The shim discards `m=` (AMENDMENT A3), so every distinct device width is a
distinct PyMS geometry with its own .so compile (~4 min each).  The committed
race trap is two processes building the SAME geometry at once, so the width set
is partitioned into disjoint groups and one process takes each group.  Within a
group the widths are built sequentially by a single Xyce run.

The width values are computed by importing wb and formatting with the SAME
"%gu" that the decks use, so the geometry hashes are identical.

usage: warmset.py <group_index> <n_groups>
"""
import math, os, sys
import wb


def all_widths():
    ws = set([wb.WN, wb.WP])
    for n in (8, 16, 32, 64, 128, 256):
        ws |= set(wb.widths(wb.wtot(n)).values())
    for n, mul in ((32, 0.5), (32, 2.0), (256, 0.5), (256, 2.0)):
        ws |= set(wb.widths(wb.wtot(n, mul)).values())
    return sorted(ws)


# already built by the instrument-check warm (btk/warm.cir): bt.py's own set
ALREADY = set(["%g" % x for x in (0.74, 1.12, 2.0, 10.0, 20.0)])


def main():
    gi, ng = int(sys.argv[1]), int(sys.argv[2])
    todo = [x for x in all_widths() if ("%g" % x) not in ALREADY]
    mine = todo[gi::ng]
    if not mine:
        print("group %d/%d: nothing to do" % (gi, ng)); return
    print("group %d/%d widths: %s" % (gi, ng, ["%g" % x for x in mine]),
          flush=True)
    L = wb.head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    k = 0
    for x in mine:
        L.append("XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, x))
        L.append("RN%d d%d b 1k" % (k, k)); k += 1
        L.append("XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, x))
        L.append("RP%d e%d 0 1k" % (k, k)); k += 1
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    p, msg = wb.run("warmset_%d.cir" % gi, L, timeout=5400)
    print(msg, flush=True)
    sys.exit(0 if p else 1)


if __name__ == "__main__":
    main()
