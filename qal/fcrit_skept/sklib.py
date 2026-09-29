"""SKEPT independent library.  Written from scratch; shares no code with fcrit/."""
import numpy as np, os, re, json

def read_prn(path):
    """-> (names_upper, t_ps or None, array[nrow, ncol]).  Fast hand parser:
    keeps only rows whose field count matches the header (Xyce appends a
    4-field 'End of Xyce' trailer and can emit short lines)."""
    with open(path) as f:
        hdr = f.readline().split()
        n = len(hdr)
        buf = []
        for ln in f:
            p2 = ln.split()
            if len(p2) != n:
                continue
            try:
                buf.append(np.fromiter((float(x) for x in p2), float, n))
            except ValueError:
                continue
    names = [h.upper() for h in hdr]
    dat = np.vstack(buf) if buf else np.zeros((0, n))
    t = dat[:, names.index("TIME")] * 1e12 if "TIME" in names else None
    return names, t, dat


class W(object):
    def __init__(self, path):
        self.names, self.t, self.d = read_prn(path)
        self.cache = {}
    def has(self, n):
        return n.upper() in self.names
    def s(self, n):
        n = n.upper()
        if n not in self.cache:
            self.cache[n] = self.d[:, self.names.index(n)]
        return self.cache[n]
    def at(self, n, tt):
        return float(np.interp(tt, self.t, self.s(n)))
    def win(self, n, ta, tb):
        m = (self.t >= ta) & (self.t <= tb)
        return self.t[m], self.s(n)[m]

# ---- trip curve, from MY OWN DC sweep
class Trip(object):
    def __init__(self, path, tag="S"):
        d = json.load(open(path))[tag]
        self.v = np.array(d["vdd"], float)
        self.tr = np.array(d["trip_V"], float)
        ok = ~np.isnan(self.tr)
        self.v, self.tr = self.v[ok], self.tr[ok]
        self.frac = self.tr / self.v
    def __call__(self, vdd):
        vdd = np.asarray(vdd, float)
        # below/above the swept range: hold the end FRACTION (same convention
        # the primary used, so the comparison is apples to apples)
        out = np.interp(vdd, self.v, self.tr)
        lo = vdd < self.v[0];  hi = vdd > self.v[-1]
        out = np.where(lo, self.frac[0] * vdd, out)
        out = np.where(hi, self.frac[-1] * vdd, out)
        return out if out.shape else float(out)

# ---- deck introspection, independent of fcrit
def deck_banks(cir):
    """-> {bank: [gate indices]} from the XP{k}_{i} instance lines."""
    b = {}
    for ln in open(cir):
        m = re.match(r"^XP(\d+)_(\d+)\s", ln, re.I)
        if m:
            b.setdefault(int(m.group(1)), set()).add(int(m.group(2)))
    return {k: sorted(v) for k, v in b.items()}

def deck_checkpoints(cir):
    """{bank: t_ps} from '.measure tran O{k}_{i}B FIND V(o{k}_{i}) AT=..p'."""
    ck = {}
    for ln in open(cir):
        m = re.match(r"^\.measure\s+tran\s+O(\d+)_(\d+)[SB]\s+FIND\s+V\(o\d+_\d+\)"
                     r"\s+AT=([0-9.eE+-]+)p", ln.strip(), re.I)
        if m:
            ck[int(m.group(1))] = float(m.group(3))
    return ck

def deck_bank1_inputs(cir):
    """{i: 1/0} from 'VI1_{i} in1_{i} 0 <val>'."""
    o = {}
    for ln in open(cir):
        m = re.match(r"^VI1_(\d+)\s+in1_\d+\s+0\s+([0-9.eE+-]+)\s*$", ln.strip(), re.I)
        if m:
            o[int(m.group(1))] = 1 if float(m.group(2)) > 0.5 else 0
    return o

def intended(cir, nbank):
    """out_hi(k,i): bank1 input from the deck, inverter parity thereafter.
    Derived from the DECK, not from any committed table."""
    b1 = deck_bank1_inputs(cir)
    def f(k, i):
        if i not in b1:
            return None
        v = b1[i]
        # bank 1 output = NOT input ; each further bank inverts again
        return ((v + k) % 2) == 1
    return f

def topup_windows(cir):
    """[(bank, t_on, t_off)] for every XTUN{k}/VTUN{k} top-up that FIRES."""
    devs = {}
    for ln in open(cir):
        m = re.match(r"^XTUN(\d+)\s", ln, re.I)
        if m:
            devs[int(m.group(1))] = True
    out = []
    for ln in open(cir):
        m = re.match(r"^VTUN(\d+)\s+tun\d+\s+0\s+PWL\((.*)\)\s*$", ln.strip(), re.I)
        if not m:
            continue
        k = int(m.group(1))
        if k not in devs:
            continue
        nums = [float(x.rstrip("p")) for x in m.group(2).split()]
        pts = [(nums[j], nums[j + 1]) for j in range(0, len(nums) - 1, 2)]
        # nMOS top-up conducts while tun is HIGH
        on = None
        for j in range(1, len(pts)):
            if pts[j][1] > 0.75 and pts[j - 1][1] <= 0.75:
                on = pts[j][0]
            elif pts[j][1] <= 0.75 and pts[j - 1][1] > 0.75 and on is not None:
                out.append((k, on, pts[j][0])); on = None
        if on is not None:
            out.append((k, on, None))
    return out
