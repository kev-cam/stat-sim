#!/usr/bin/env python3
"""Offline ulp-bounded check of the div variant's FP outputs.
usage: ulpcheck.py check.bin post.bin.fpref [maxulp]
Compares the 1024B FP region at 0x40000 in check.bin (DPI dump of actual memory)
against the IEEE-RNE x86 reference. The fpnew divsqrt unit is faithful-but-not-
RNE-exact, so a small drift is expected over chained ops."""
import struct, sys, collections

check, ref = sys.argv[1], sys.argv[2]
maxulp = int(sys.argv[3]) if len(sys.argv) > 3 else 64

mem = {}
data = open(check, 'rb').read()
o = 0
while o < len(data):
    addr, size = struct.unpack_from('<QQ', data, o); o += 16
    mem[addr] = data[o:o+size]; o += size
pg = mem[0x40000]
refb = open(ref, 'rb').read()

def bits(b): return struct.unpack('<I', b)[0]

dx, dy = [], []
for g in range(16):
    for c in range(8):
        ox = g*64 + c*4
        oy = g*64 + 32 + c*4
        dx.append(bits(pg[ox:ox+4]) - bits(refb[ox:ox+4]))
        dy.append(bits(pg[oy:oy+4]) - bits(refb[oy:oy+4]))

print('x (fdiv chains) ulp delta: min %d max %d  hist %s' %
      (min(dx), max(dx), dict(collections.Counter(dx))))
print('y (fsqrt)       ulp delta: min %d max %d  hist %s' %
      (min(dy), max(dy), dict(collections.Counter(dy))))
worst = max(max(abs(d) for d in dx), max(abs(d) for d in dy))
print('WORST |ulp| = %d (bound %d): %s' % (worst, maxulp, 'OK' if worst <= maxulp else 'EXCEEDED'))
sys.exit(0 if worst <= maxulp else 1)
