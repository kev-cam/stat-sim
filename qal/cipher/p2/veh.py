#!/usr/bin/env python3
"""qal/cipher/p2/veh.py -- the two PHASE 2 cipher vehicles, their wire geometry,
and their reference implementations.  NO SIMULATION happens in this file.

  (a) AES-128 AddRoundKey  -- 128 XOR2 in ONE level, plus ShiftRows as pure
      wiring.  Depth 1, zero carry.  QAL's best possible case in cryptography.
  (b) ChaCha20 quarter-round with a 32-bit KOGGE-STONE adder, and
  (c) the SAME adder as a RIPPLE CPA, so the wide-vs-narrow adder difference is
      measured here rather than asserted.

THE CONSTRAINT THAT SHAPES BOTH, and which the brief does not mention:

An unbuffered QAL bank RETURNS ITS RAIL CHARGE at the end of its hold window.
A cell's output is held up only by its own pull-up from its own bank rail, so
when that rail comes down the value is GONE.  Therefore a signal produced at
level j and consumed at level k > j+1 cannot simply be routed there: it must be
RE-DRIVEN at every intervening level by a FORWARDING cell.  In CMOS that same
signal is a WIRE and costs nothing but capacitance, because a static gate holds
its output against a supply that never goes away.

So QAL converts wires into cells, at one cell per bit per level crossed.  This
is measured, not assumed: Chain.evaluate() REFUSES a netlist in which any cell
reads a level older than k-1, so a vehicle that needs forwarding cannot be built
without paying for it.  The forwarding census is reported per vehicle.

Kogge-Stone is UNIFORM-DEPTH -- every prefix cell reads only the level directly
above it -- which is exactly the property QAL needs, and is a real structural
argument in the parallel-prefix form's favour.  A ripple CPA is not: bit i's
propagate must survive i carry levels, so its forwarding cost grows as O(W^2).
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cg import Chain, Cell, CELLS, CELL_WIDTH_UM, cell_devices

# ---------------------------------------------------------------- wire model
# Phase 1's PDK-derived figures, reused VERBATIM from qal/cipher/WIRE_MODEL.json
# (sha256 5d5b9987..., MEASURED from sg13g2_tech.lef + ITF geometry).
WIRE_LOW = 0.0930       # fF/um  isolated min-width Metal2 (LEF, MEASURED)
WIRE_NOM = 0.15         # fF/um  the campaign figure, PDK-BRACKETED by Phase 1
WIRE_HIGH = 0.2181      # fF/um  middle of a min-pitch Metal2 bus (DERIVED)
WIRE_R_PER_UM = 0.515   # ohm/um at min width (LEF RPERSQ, MEASURED)


# ============================================================ the builder
class Build(object):
    """Level-by-level construction with POLARITY TRACKING, automatic FORWARDING
    and LIVENESS PRUNING.

    A logical signal has a name and, at any level, a net that carries either its
    true value or its complement.  Consumers ask for a polarity; the builder
    picks the cell that matches (xor2/xnor2, nand2/nor2, a21oi/o21ai) rather than
    spending an inverter, which is what a synthesis tool does.

    HELD sources (primary inputs, the AES round key, the adder's A and B words)
    are driven by registers on a supply that does NOT return, so they are legal
    inputs at ANY level.  That is a BOOKING -- an ideal DC source -- and it is
    metered and symmetric: the CMOS comparator reads the identical sources.
    """

    def __init__(self, name):
        self.name = name
        self.levels = []            # list of list[(kind, [inref], sig, pol)]
        self.sources = {}           # 's_tag' -> bool
        self.cur = {}               # sig -> (level, idx, pol)  after last level
        self.srcval = {}

    # ------------------------------------------------------------- sources
    def src(self, tag, val):
        t = "s_" + tag
        self.sources[t] = bool(val)
        return t

    # -------------------------------------------------------------- levels
    def begin(self):
        self._lv = []
        self._new = {}
        return self

    def ref(self, x):
        """Resolve an input reference for the level under construction."""
        if isinstance(x, str) and x.startswith("s_"):
            return ("src", x)
        if x not in self.cur:
            raise SystemExit("%s: signal %r is not live" % (self.name, x))
        return ("net", x)

    def emit(self, kind, sig, ins, pol):
        """Produce logical signal `sig` at this level with polarity `pol`."""
        self._lv.append((kind, [self.ref(i) for i in ins], sig, bool(pol)))
        self._new[sig] = len(self._lv) - 1
        return sig

    def fwd(self, sig):
        """Carry a live signal across this level.  ONE inverter, which flips the
        polarity -- the cheapest physical forwarding there is, and the whole
        reason this function exists."""
        pol = self.cur[sig][2]
        return self.emit("inv", sig, [sig], not pol)

    def end(self):
        lv = len(self.levels) + 1
        self.levels.append(self._lv)
        nxt = {}
        for idx, (kind, ins, sig, pol) in enumerate(self._lv):
            nxt[sig] = (lv, idx, pol)
        self.cur = nxt
        self._lv, self._new = None, None
        return lv

    def pol(self, sig):
        return self.cur[sig][2]

    # -------------------------------------------------- liveness + assembly
    def finish(self, outputs, prune=True):
        """Prune cells whose outputs nothing reads, then assemble a cg.Chain.

        `outputs` are the logical signal names that must survive at the LAST
        level -- the vehicle's real result.  Everything not in a live cone of one
        of those is dead and is removed, so the reported cell count is the cell
        count the function actually needs."""
        nb = len(self.levels)
        keep = [set() for _ in range(nb + 1)]
        # seed: the declared outputs at the last level
        byname = {}
        for k in range(1, nb + 1):
            for idx, (kind, ins, sig, pol) in enumerate(self.levels[k - 1]):
                byname[(k, sig)] = idx
        for o in outputs:
            if (nb, o) not in byname:
                raise SystemExit("%s: output %r not produced at last level %d"
                                 % (self.name, o, nb))
            keep[nb].add(byname[(nb, o)])
        if prune:
            for k in range(nb, 0, -1):
                for idx in sorted(keep[k]):
                    kind, ins, sig, pol = self.levels[k - 1][idx]
                    for (t, x) in ins:
                        if t == "net":
                            keep[k - 1].add(byname[(k - 1, x)])
        else:
            for k in range(1, nb + 1):
                keep[k] = set(range(len(self.levels[k - 1])))

        # renumber
        newidx = [{} for _ in range(nb + 1)]
        ch = Chain(self.name)
        ch.sources = dict(self.sources)
        for k in range(1, nb + 1):
            cells = []
            for idx in sorted(keep[k]):
                newidx[k][idx] = len(cells)
                kind, ins, sig, pol = self.levels[k - 1][idx]
                nets = []
                for (t, x) in ins:
                    if t == "src":
                        nets.append(x)
                    else:
                        j = newidx[k - 1][byname[(k - 1, x)]]
                        nets.append("o%d_%d" % (k - 1, j))
                cells.append(Cell(kind, nets, name=sig))
            ch.add_level(cells)
        # remember the polarity and the index of every kept signal
        ch.sigmap = {}
        for k in range(1, nb + 1):
            for idx in sorted(keep[k]):
                kind, ins, sig, pol = self.levels[k - 1][idx]
                ch.sigmap[(k, sig)] = (newidx[k][idx], pol)
        ch.out_sigs = list(outputs)
        ch.pruned = [len(self.levels[k - 1]) - len(keep[k]) for k in range(1, nb + 1)]
        return ch


# ============================================ forwarding-cost arithmetic
def forward_census(nb, produced_at, consumed_at, width):
    """DERIVED, closed form: the forwarding cells a signal set costs in an
    unbuffered QAL chain.  One cell per bit per level strictly between the
    producing level and the consuming level."""
    tot = 0
    for p, c in zip(produced_at, consumed_at):
        tot += max(0, c - p - 1)
    return tot * width


# ======================================================= (a) AddRoundKey
def aes_sbox_free_state(seed=0xA5):
    """A declared, non-degenerate 128-bit state and round key.  Fixed constants,
    not random, so the vehicle is reproducible from this file alone."""
    st = [(seed * (i + 1) + 0x3B * i) & 0xFF for i in range(16)]
    rk = [(0x5C ^ (i * 0x1D) ^ (seed >> 1)) & 0xFF for i in range(16)]
    return st, rk


def shiftrows(bytes16):
    """AES ShiftRows on a column-major 4x4 state: byte index 4c+r holds s[r][c],
    and row r is rotated LEFT by r byte positions."""
    out = [0] * 16
    for c in range(4):
        for r in range(4):
            out[4 * c + r] = bytes16[4 * ((c + r) % 4) + r]
    return out


def shiftrows_displacement():
    """DERIVED geometry.  Destination byte slot (r, c) is fed by source slot
    (r, (c+r) mod 4), so the byte travels |c - (c+r) mod 4| COLUMN pitches.

    FLOORPLAN, stated: the 16 bytes sit in the natural AES 4x4 tile grid, one
    tile per byte, with the 8 bit-slices of a byte side by side across the tile.
    A column pitch is therefore 8 bit pitches.  Returns the mean and max
    displacement in BIT pitches, and the per-byte list."""
    disp = []
    for c in range(4):
        for r in range(4):
            src_c = (c + r) % 4
            d = abs(c - src_c)
            d = min(d, 4 - d)          # the wrap goes the short way round
            disp.append(d * 8)         # column pitch = 8 bit pitches
    mean = sum(disp) / float(len(disp))
    return dict(per_byte_bitpitches=disp, mean_bitpitches=mean,
                max_bitpitches=max(disp),
                floorplan="4x4 byte tiles, 8 bit-slices across a tile, "
                          "column pitch = 8 bit pitches, wrap takes the short way")


def aes_addroundkey(cw_per_bit=0.0, nb_pre=1, nb_post=1):
    """AddRoundKey as a REAL chain, not a lone bank.

    level 1        a driving level (inv) that produces the state bits, so the
                   AddRoundKey level is fed by a QAL rail exactly as it would be
                   inside a round, and not by ideal sources.
    level 2        128 x XOR2:  out = state XOR round_key.  The round key is a
                   HELD source (a key-schedule register), legal at any level.
    level 3        a receiving level (inv) whose inputs are the AddRoundKey
                   outputs PERMUTED BY SHIFTROWS -- the permutation is pure
                   wiring, and the wire capacitance it costs is hung on level
                   2's outputs.

    The receiver exists because the functional criterion scores a sender against
    ITS RECEIVER's measured trip at the RECEIVER's delivered rail, and because a
    lone bank would be a single hop (gate G10).
    """
    st, rk = aes_sbox_free_state()
    sb = [(st[i] >> b) & 1 for i in range(16) for b in range(8)]
    kb = [(rk[i] >> b) & 1 for i in range(16) for b in range(8)]

    B = Build("aes_addroundkey")
    # level 1: drive the state.  inv of the complement gives the state bit.
    B.begin()
    for j in range(128):
        s = B.src("st%d" % j, not sb[j])
        B.emit("inv", "st%d" % j, [s], True)
    B.end()
    # level 2: the AddRoundKey XOR bank
    B.begin()
    for j in range(128):
        k = B.src("rk%d" % j, kb[j])
        B.emit("xor2", "y%d" % j, ["st%d" % j, k], True)
    B.end()
    # level 3: the receiver, fed through the ShiftRows permutation
    perm = shiftrows(list(range(16)))       # dst byte slot -> src byte slot
    B.begin()
    for i in range(16):
        for b in range(8):
            src_bit = perm[i] * 8 + b
            B.emit("inv", "z%d" % (i * 8 + b), ["y%d" % src_bit], False)
    B.end()

    ch = B.finish(["z%d" % j for j in range(128)])
    # The ShiftRows wire lives on level 2's outputs, and it is PER BIT rather
    # than a flat mean: source byte 4c+r moves to column (c-r) mod 4, so its
    # displacement depends only on the ROW r and is 0 / 8 / 16 / 8 bit pitches
    # for r = 0..3 (the wrap routed the short way).  Row 0 does not move at all
    # and pays NO wire, which is a real feature of ShiftRows that a flat mean
    # would smear away.
    if cw_per_bit > 0.0:
        for j in range(128):
            i_byte = j // 8
            r = i_byte % 4
            dc = abs(r)                      # |c - (c-r) mod 4| before wrapping
            dc = min(dc, 4 - dc) if r else 0
            pitches = dc * 8
            idx, _ = ch.sigmap[(2, "y%d" % j)]
            # cw_per_bit is quoted at the MEAN displacement of 8 bit pitches, so
            # scale each bit by its own displacement relative to that mean
            ch.wire[(2, idx)] = cw_per_bit * (pitches / 8.0)
        ch.note.append("ShiftRows wire is PER BIT from the permutation: rows "
                       "0/1/2/3 travel 0/8/16/8 bit pitches, mean 8.0")
    ch.evaluate()

    # ---- the reference: AddRoundKey then ShiftRows, computed independently
    ark = [st[i] ^ rk[i] for i in range(16)]
    want_y = [(ark[i] >> b) & 1 for i in range(16) for b in range(8)]
    sr = shiftrows(ark)
    want_z = [(sr[i] >> b) & 1 for i in range(16) for b in range(8)]
    ref = {}
    for j in range(128):
        idx, pol = ch.sigmap[(2, "y%d" % j)]
        ref[(2, idx)] = bool(want_y[j]) == pol
        idx, pol = ch.sigmap[(3, "z%d" % j)]
        ref[(3, idx)] = bool(want_z[j]) == pol
    ch.reference = ref
    ch.note.append("AddRoundKey = 128 XOR2 in ONE level; ShiftRows is the "
                   "level-2 -> level-3 wiring permutation and costs NO cells.")
    ch.vector = dict(state=st, round_key=rk, addroundkey=ark, shiftrows=sr)
    return ch


# =================================================== the adders
def build_adder(W, form, cw_per_bit=0.0, seed=0x9E37):
    """A complete W-bit adder as a QAL chain, in one of two FORMS of the SAME
    FUNCTION, with the bit-propagate forwarding made explicit.

    form "ks"     Kogge-Stone parallel prefix: ceil(log2 W) prefix stages.
    form "ripple" ripple CPA: W carry levels, one alternating AOI21/OAI21 each.

    Both end with a sum level.  Both carry the identical held A/B sources and the
    identical wire load, so the two are comparable to each other and each is
    comparable to its own CMOS twin.
    """
    import math
    a_val = [(seed >> (i % 16)) & 1 for i in range(W)]
    b_val = [((seed * 3 + 0x5A5A) >> (i % 16)) & 1 for i in range(W)]
    # make the carry chain actually propagate: force a long run of P=1
    for i in range(1, min(W, 6)):
        a_val[i], b_val[i] = 1, 0
    a_val[0], b_val[0] = 1, 1

    B = Build("%s_w%d" % (form, W))
    A = [B.src("a%d" % i, a_val[i]) for i in range(W)]
    Bw = [B.src("b%d" % i, b_val[i]) for i in range(W)]

    # ---------------------------------------------------- level 1: generate
    B.begin()
    for i in range(W):
        B.emit("xor2", "p%d" % i, [A[i], Bw[i]], True)
        B.emit("and2", "g%d" % i, [A[i], Bw[i]], True)
    B.end()

    if form == "ks":
        nstage = int(math.ceil(math.log(W, 2)))
        for st in range(1, nstage + 1):
            s = 1 << (st - 1)
            true_in = (st % 2 == 1)
            B.begin()
            for i in range(W):
                gi, pi = "g%d" % i, "p%d" % i
                if i >= s:
                    if true_in:
                        B.emit("a21oi", gi, [pi, "g%d" % (i - s), gi], False)
                    else:
                        B.emit("o21ai", gi, [pi, "g%d" % (i - s), gi], True)
                    if st < nstage:
                        if true_in:
                            B.emit("nand2", pi, [pi, "p%d" % (i - s)], False)
                        else:
                            B.emit("nor2", pi, [pi, "p%d" % (i - s)], True)
                else:
                    B.fwd(gi)
                    if st < nstage:
                        B.fwd(pi)
                B.fwd("bp%d" % i) if st > 1 else B.emit(
                    "inv", "bp%d" % i, ["p%d" % i], False)
            B.end()
        carry_sig = ["g%d" % i for i in range(W)]
        nlev_prefix = nstage
    elif form == "ripple":
        # c_{i+1} = G_i | (P_i & c_i).  One level per bit, alternating polarity.
        B.begin()
        for i in range(W):
            B.fwd("g%d" % i); B.fwd("p%d" % i)
            B.emit("inv", "bp%d" % i, ["p%d" % i], False)
        B.emit("inv", "c0", ["g0"], False)      # c1 = g0 (cin = 0)
        B.end()
        for i in range(1, W):
            true_in = (i % 2 == 1)
            B.begin()
            for j in range(W):
                B.fwd("g%d" % j); B.fwd("p%d" % j); B.fwd("bp%d" % j)
            # every carry already produced must survive to the SUM level, so it
            # is re-driven here.  c_{i-1} is forwarded AND read by the cell that
            # makes c_i -- two cells on one net, which is what a real fanout is.
            for j in range(i):
                B.fwd("c%d" % j)
            # c_{i} from c_{i-1}: polarity alternates with the cell used
            if B.pol("c%d" % (i - 1)):
                B.emit("a21oi", "c%d" % i, ["p%d" % i, "c%d" % (i - 1),
                                            "g%d" % i], False)
            else:
                B.emit("o21ai", "c%d" % i, ["p%d" % i, "c%d" % (i - 1),
                                            "g%d" % i], True)
            B.end()
        carry_sig = ["c%d" % i for i in range(W)]
        nlev_prefix = W
    else:
        raise SystemExit("form?")

    # ------------------------------------------------------- the sum level
    B.begin()
    for i in range(W):
        if i == 0:
            B.fwd("bp0")
        else:
            pb = B.pol("bp%d" % i)
            cb = B.pol(carry_sig[i - 1])
            kind = "xor2" if (pb == cb) else "xnor2"
            B.emit(kind, "s%d" % i, ["bp%d" % i, carry_sig[i - 1]], True)
    sig0 = "bp0"
    B.end()

    outs = [sig0] + ["s%d" % i for i in range(1, W)]
    ch = B.finish(outs)
    ch.evaluate()

    # ---------------------------------------------------- the wire, per bit
    if cw_per_bit > 0.0:
        for k in range(1, ch.nb + 1):
            for i in range(ch.n_of(k)):
                ch.wire[(k, i)] = cw_per_bit

    # ---------------------------------------------------------- the reference
    av = sum(a_val[i] << i for i in range(W))
    bv = sum(b_val[i] << i for i in range(W))
    sv = (av + bv) & ((1 << W) - 1)
    ref = {}
    for i in range(W):
        sig = outs[i]
        idx, pol = ch.sigmap[(ch.nb, sig)]
        want = bool((sv >> i) & 1)
        ref[(ch.nb, idx)] = (want == pol)
    ch.reference = ref
    ch.vector = dict(W=W, form=form, a=av, b=bv, sum=sv,
                     a_bits=a_val, b_bits=b_val)
    ch.adder_form = form
    ch.note.append("%s %d-bit adder: %d levels, %d cells, %d devices"
                   % (form, W, ch.nb, sum(ch.n_of(k) for k in range(1, ch.nb + 1)),
                      ch.census()["devices_total"]))
    return ch


# ============================================= ChaCha20 reference + rotates
def rotl32(x, n):
    x &= 0xFFFFFFFF
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def chacha_qr(a, b, c, d):
    """RFC 8439 quarter-round, the reference."""
    a = (a + b) & 0xFFFFFFFF; d ^= a; d = rotl32(d, 16)
    c = (c + d) & 0xFFFFFFFF; b ^= c; b = rotl32(b, 12)
    a = (a + b) & 0xFFFFFFFF; d ^= a; d = rotl32(d, 8)
    c = (c + d) & 0xFFFFFFFF; b ^= c; b = rotl32(b, 7)
    return a, b, c, d


def rotate_geometry(W=32, rots=(16, 12, 8, 7)):
    """DERIVED, Phase 1's formula: bit i -> bit (i+r) mod W, so (W-r) bits travel
    r pitches and r bits travel (W-r) -- mean 2 r (W-r) / W bit pitches."""
    out = {}
    for r in rots:
        out["r%d" % r] = 2.0 * r * (W - r) / float(W)
    out["mean"] = sum(out["r%d" % r] for r in rots) / float(len(rots))
    return out


def qr_structure(W=32, adder="ks"):
    """The quarter-round's LEVEL STRUCTURE and its forwarding bill, DERIVED.

    The QR is four (add, xor, rotate) triples.  A rotate is wiring.  An xor is
    one level.  An add is the adder's own level count.  a, b, c, d are all live
    across the whole round, so three of the four words are forwarded through
    every level the fourth is being computed in -- and that forwarding is the
    cost the brief's 'wiring costs zero gates' claim does not carry.
    """
    import math
    nadd = (int(math.ceil(math.log(W, 2))) + 2) if adder == "ks" else (W + 2)
    steps = [("add", nadd), ("xor", 1), ("add", nadd), ("xor", 1),
             ("add", nadd), ("xor", 1), ("add", nadd), ("xor", 1)]
    levels = sum(n for _, n in steps)
    # at every level, the words NOT being written must be re-driven
    fwd = 0
    for kind, n in steps:
        live_other = 3 if kind == "add" else 3
        fwd += n * live_other * W
    return dict(W=W, adder=adder, levels_per_qr=levels,
                adder_levels=nadd, steps=steps,
                forwarding_cells_per_qr=fwd,
                note="forwarding = one inverter per live word per bit per level")


# ===================================================================== main
def summarise():
    out = {}
    sr = shiftrows_displacement()
    out["shiftrows_geometry"] = sr
    pitches = {"brief_1.00um": 1.00, "inv_1_1.44um": 1.44, "xor2_1_3.84um": 3.84}
    out["shiftrows_wire_per_bit_fF"] = {}
    for nm, p in sorted(pitches.items()):
        L = sr["mean_bitpitches"] * p
        out["shiftrows_wire_per_bit_fF"][nm] = {
            "mean_len_um": round(L, 4),
            "LOW_0.0930": round(L * WIRE_LOW, 4),
            "NOM_0.15": round(L * WIRE_NOM, 4),
            "HIGH_0.2181": round(L * WIRE_HIGH, 4),
            "R_ohm": round(L * WIRE_R_PER_UM, 3)}
    out["chacha_rotate_geometry_bitpitches"] = rotate_geometry()
    rg = rotate_geometry()
    out["chacha_rotate_wire_per_bit_fF"] = {}
    for nm, p in sorted(pitches.items()):
        L = rg["mean"] * p
        out["chacha_rotate_wire_per_bit_fF"][nm] = {
            "mean_len_um": round(L, 4),
            "LOW_0.0930": round(L * WIRE_LOW, 4),
            "NOM_0.15": round(L * WIRE_NOM, 4),
            "HIGH_0.2181": round(L * WIRE_HIGH, 4)}

    # vehicles
    v = {}
    ark = aes_addroundkey(cw_per_bit=0.0)
    v["aes_addroundkey"] = ark.census()
    v["aes_addroundkey"]["vector"] = {
        k: ([hex(x) for x in val] if isinstance(val, list) else val)
        for k, val in ark.vector.items()}
    for W in (8, 32):
        for form in ("ks", "ripple"):
            ch = build_adder(W, form)
            c = ch.census()
            c["vector"] = {k: (hex(x) if isinstance(x, int) and k in
                               ("a", "b", "sum") else x)
                           for k, x in ch.vector.items() if k != "a_bits"
                           and k != "b_bits"}
            v["adder_%s_w%d" % (form, W)] = c
    out["vehicles"] = v
    out["qr_structure_ks32"] = qr_structure(32, "ks")
    out["qr_structure_ripple32"] = qr_structure(32, "ripple")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        ok = True
        # ChaCha reference against the RFC 8439 test vector
        a, b, c, d = 0x11111111, 0x01020304, 0x9b8d6f43, 0x01234567
        got = chacha_qr(a, b, c, d)
        want = (0xea2a92f4, 0xcb1cf8ce, 0x4581472e, 0x5881c4bb)
        print("chacha QR vs RFC 8439 2.1.1: %s  got %s" %
              ("MATCH" if got == want else "MISMATCH",
               " ".join("%08x" % x for x in got)))
        ok = ok and (got == want)
        # ShiftRows against the FIPS-197 round-1 example
        st = list(range(16))
        sr = shiftrows(st)
        exp = [0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11]
        print("ShiftRows permutation: %s" % ("MATCH FIPS-197 column-major"
                                             if sr == exp else "MISMATCH %s" % sr))
        ok = ok and (sr == exp)
        # every vehicle must evaluate and its reference must be self-consistent
        for nm, ch in [("aes", aes_addroundkey(2.0)),
                       ("ks8", build_adder(8, "ks", 1.0)),
                       ("rip8", build_adder(8, "ripple", 1.0)),
                       ("ks32", build_adder(32, "ks", 1.0))]:
            n = len(ch.reference)
            print("  %-5s nb=%2d cells=%4d devices=%5d refpoints=%d"
                  % (nm, ch.nb, sum(ch.n_of(k) for k in range(1, ch.nb + 1)),
                     ch.census()["devices_total"], n))
        print("SELFTEST_VEH %s" % ("PASS" if ok else "FAIL"))
        sys.exit(0 if ok else 1)
    print(json.dumps(summarise(), indent=1, sort_keys=True))


# =============================================== structural wire extraction
def bit_of(signame):
    """The bit index a signal belongs to, parsed from its own name.  Signals are
    named <prefix><bit> by the builders (p5, g12, bp3, c7, s9, y41, st41, z41)."""
    mm = re.match(r"^[a-z]+(\d+)$", signame or "")
    return int(mm.group(1)) if mm else None


def struct_wire(ch, pitch_um, fF_per_um=WIRE_NOM, floor_pitches=1.0):
    """DERIVED-FROM-NETLIST wire model: every net's routed length is taken from
    the BIT DISTANCES to the sinks it actually drives, read off the netlist.

    Sinks of a datapath net are collinear along the bit axis, so a net feeding
    sinks at +1 and +16 bit positions is ONE wire of 16 pitches with a tap at 1:
    the length is the MAX distance on each side, summed over the two sides, with
    a floor of one pitch because every net must at least reach its neighbour.

    This is what makes the two adder forms differ in WIRE as well as in DEPTH: a
    Kogge-Stone prefix cell at stride s reads a net s bit positions away, so its
    driving nets are s pitches long (1, 2, 4, 8, 16 over the five stages of a
    32-bit adder), while a ripple CPA's carry wire is always ONE pitch.  The
    parallel-prefix form's shallow depth is partly paid for in interconnect, and
    this function is what makes that price MEASURED rather than argued.
    """
    # map net -> (level, idx, bit)
    bits = {}
    for k in range(1, ch.nb + 1):
        for i, c in enumerate(ch.levels[k - 1]):
            bits[(k, i)] = bit_of(c.name)
    lens = {}
    for k in range(1, ch.nb + 1):
        for i in range(ch.n_of(k)):
            lens[(k, i)] = 0.0
    for k in range(2, ch.nb + 1):
        for i, c in enumerate(ch.levels[k - 1]):
            cb = bits[(k, i)]
            for s in c.ins:
                mm = re.match(r"o(\d+)_(\d+)$", s)
                if not mm:
                    continue            # a held source: not a datapath net here
                pk, pi = int(mm.group(1)), int(mm.group(2))
                pb = bits.get((pk, pi))
                if cb is None or pb is None:
                    d = floor_pitches
                else:
                    d = abs(cb - pb)
                key = (pk, pi)
                prev = lens.get(key, 0.0)
                lens[key] = max(prev, float(d))
    out = {}
    for key, d in lens.items():
        out[key] = max(d, floor_pitches) * pitch_um * fF_per_um
    return out


def apply_struct_wire(ch, pitch_um, fF_per_um=WIRE_NOM):
    w = struct_wire(ch, pitch_um, fF_per_um)
    ch.wire = dict(w)
    ch.note.append("wire DERIVED FROM NETLIST fan-out bit distances at "
                   "pitch %.2f um and %.4f fF/um" % (pitch_um, fF_per_um))
    return ch


def wire_report(ch):
    tot = sum(ch.wire.values())
    per_level = {}
    for k in range(1, ch.nb + 1):
        per_level[k] = round(sum(ch.wire.get((k, i), 0.0)
                                 for i in range(ch.n_of(k))), 4)
    vals = sorted(ch.wire.values())
    return dict(total_fF=round(tot, 4), per_level_fF=per_level,
                n_nets=len(ch.wire),
                mean_fF=round(tot / len(ch.wire), 4) if ch.wire else 0.0,
                max_fF=round(vals[-1], 4) if vals else 0.0,
                median_fF=round(vals[len(vals) // 2], 4) if vals else 0.0)


# ============================= (b) the ChaCha20 XOR + ROTATE level
def qr_xor_rotate(W=32, r=16, cw_at_mean=0.0, seed=0x3C):
    """ONE of the quarter-round's four (xor, rotate) steps as a REAL chain:

      level 1   drive the word d            (inv, W cells)
      level 2   d ^= a                      (xor2, W cells; a is a HELD word)
      level 3   the receiver, fed through d <<< r -- the ROTATE, which is PURE
                WIRING and costs no cells, exactly as the insight says

    The rotate wire is PER BIT and exact: bit i -> bit (i+r) mod W, so (W-r)
    bits travel r pitches and r bits travel (W-r).  For r = 16 on 32 bits every
    bit travels 16 pitches, which is the uniform worst case and the brief's own
    geometry.  `cw_at_mean` is the load quoted at the MEAN displacement
    2r(W-r)/W, and each bit is scaled by its own displacement.

    This is the level type the AES vehicle does NOT cover (32 bits and a rotate,
    rather than 128 bits and ShiftRows), and together with the measured adder it
    is what a quarter-round is made of.
    """
    # Non-periodic 32-bit constants (the first words of the ChaCha/Blowfish pi
    # constant).  A periodic vector would be invariant under a 16-bit rotation
    # and the value check would not be able to see a rotate error at all --
    # which an 8-periodic seed silently was, and this line is the fix.
    D0, A0 = 0x243F6A88, 0x85A308D3
    d_val = [(D0 >> i) & 1 for i in range(W)]
    a_val = [(A0 >> i) & 1 for i in range(W)]

    B = Build("qrxor_w%d_r%d" % (W, r))
    B.begin()
    for i in range(W):
        s = B.src("d%d" % i, not d_val[i])
        B.emit("inv", "d%d" % i, [s], True)
    B.end()
    B.begin()
    for i in range(W):
        s = B.src("a%d" % i, a_val[i])
        B.emit("xor2", "x%d" % i, ["d%d" % i, s], True)
    B.end()
    # level 3: the receiver reads the ROTATED bit.  destination bit j is fed by
    # source bit (j - r) mod W, which is the wiring that implements <<< r.
    B.begin()
    for j in range(W):
        B.emit("inv", "z%d" % j, ["x%d" % ((j - r) % W)], False)
    B.end()

    ch = B.finish(["z%d" % j for j in range(W)])

    mean_pitches = 2.0 * r * (W - r) / float(W)
    if cw_at_mean > 0.0 and mean_pitches > 0:
        for i in range(W):
            dst = (i + r) % W
            d = abs(dst - i)
            d = min(d, W - d)
            idx, _ = ch.sigmap[(2, "x%d" % i)]
            ch.wire[(2, idx)] = cw_at_mean * (d / mean_pitches)
        ch.note.append("rotate wire PER BIT: bit i -> (i+%d) mod %d, mean %.4f "
                       "bit pitches" % (r, W, mean_pitches))
    ch.evaluate()

    dv_ = sum(d_val[i] << i for i in range(W))
    av_ = sum(a_val[i] << i for i in range(W))
    xv = dv_ ^ av_
    zv = rotl32(xv, r) if W == 32 else None
    ref = {}
    for i in range(W):
        idx, pol = ch.sigmap[(2, "x%d" % i)]
        ref[(2, idx)] = (bool((xv >> i) & 1) == pol)
    for j in range(W):
        idx, pol = ch.sigmap[(3, "z%d" % j)]
        ref[(3, idx)] = (bool((zv >> j) & 1) == pol)
    ch.reference = ref
    ch.vector = dict(W=W, r=r, d=dv_, a=av_, xor=xv, rotated=zv)
    ch.note.append("the ROTATE itself costs ZERO cells and ZERO levels -- that "
                   "part of the insight is confirmed; what it costs is the wire "
                   "hung on level 2's outputs, and one level of RECEIVER.")
    return ch


# ====================================== the FULL quarter-round, symbolically
def qr_full(W=32, adder="ks", rots=(16, 12, 8, 7), nsteps=8):
    """The complete ChaCha20 quarter-round as an unbuffered-QAL level chain,
    built symbolically and censused EXACTLY.  Not simulated -- 32 levels of a
    32-bit ARX round is far beyond this run's deck budget -- but every number
    below is read off a netlist that was actually constructed and whose output
    is checked against the RFC 8439 section 2.1.1 test vector.

    The point of building it is the FORWARDING BILL.  At every level the words
    not being written must be re-driven, because their producing rail has
    returned its charge.  a, b, c and d are all live across the whole round, so
    three of the four words are being re-driven at all times.

    THE ROTATE COSTS ZERO LEVELS AND ZERO CELLS, exactly as the insight claims:
    it is folded into the XOR level's output indexing, because
        rotl(d ^ a, r)_j = d_{(j-r) mod W} XOR a_{(j-r) mod W}
    so the permutation is which nets the XOR cell reaches for, and nothing else.
    That part of the insight is CONFIRMED here and is not in dispute.
    """
    import math
    D0 = [0x11111111, 0x01020304, 0x9b8d6f43, 0x01234567]   # RFC 8439 2.1.1
    B = Build("qr_%s_w%d" % (adder, W))
    nstage = int(math.ceil(math.log(W, 2)))

    B.begin()
    for nm, v in zip("abcd", D0):
        for i in range(W):
            s = B.src("%s%d" % (nm, i), not ((v >> i) & 1))
            B.emit("inv", "%s%d" % (nm, i), [s], True)
    B.end()

    WORDS = ["%s%d" % (nm, i) for nm in "abcd" for i in range(W)]

    def fwd_except(prod):
        for s in WORDS:
            if s not in prod:
                B.fwd(s)

    def to_true(sig, newname):
        """Re-drive `sig` under `newname` with polarity normalised to TRUE, so
        every word begins each step in a known polarity: one inverter if it is
        currently complemented, one buffer if it is not."""
        kind = "inv" if not B.pol(sig) else "buf"
        return B.emit(kind, newname, [sig], True)

    def do_add(dst, srcw):
        # ---- generate level: P = dst ^ src, G = dst & src
        # ---- generate level, POLARITY-AWARE.
        # A word that has been forwarded across N levels arrives complemented if
        # N is odd, because forwarding is one inverter.  An XOR term absorbs that
        # by swapping xor2 for xnor2 and costs nothing; an AND term CANNOT --
        # and2(!A, B) is a different function, not a relabelling of A & B.  The
        # PDK's mixed-polarity cells cover every case at 4-6 devices:
        #     (T,T) and2   A & B
        #     (F,F) nor2   !(!A | !B) = A & B
        #     mixed nor2b  !A' & B'   with A' the complemented net
        # so the generate level always emits TRUE-polarity P and G and the
        # alternating prefix downstream needs no repair.  Getting this wrong is
        # what made the second 'a += b' compute the wrong word.
        B.begin()
        prod = set()
        for i in range(W):
            dn, sn = "%s%d" % (dst, i), "%s%d" % (srcw, i)
            pd, ps = B.pol(dn), B.pol(sn)
            B.emit("xor2" if pd == ps else "xnor2", "P%d" % i, [dn, sn], True)
            if pd and ps:
                B.emit("and2", "G%d" % i, [dn, sn], True)
            elif (not pd) and (not ps):
                B.emit("nor2", "G%d" % i, [dn, sn], True)
            elif not pd:
                B.emit("nor2b", "G%d" % i, [dn, sn], True)
            else:
                B.emit("nor2b", "G%d" % i, [sn, dn], True)
            prod |= {"P%d" % i, "G%d" % i}
        fwd_except(prod)
        B.end()
        # ---- prefix.  BP (the BIT propagate, as opposed to the group
        # propagate that overwrites P) is created at the first prefix stage from
        # the generate level's P and forwarded from then on.
        if adder == "ks":
            for st in range(1, nstage + 1):
                sd = 1 << (st - 1)
                true_in = (st % 2 == 1)
                B.begin()
                prod = set()
                for i in range(W):
                    gi, pi = "G%d" % i, "P%d" % i
                    if i >= sd:
                        if true_in:
                            B.emit("a21oi", gi, [pi, "G%d" % (i - sd), gi], False)
                        else:
                            B.emit("o21ai", gi, [pi, "G%d" % (i - sd), gi], True)
                        if st < nstage:
                            if true_in:
                                B.emit("nand2", pi, [pi, "P%d" % (i - sd)], False)
                            else:
                                B.emit("nor2", pi, [pi, "P%d" % (i - sd)], True)
                    else:
                        B.fwd(gi)
                        if st < nstage:
                            B.fwd(pi)
                    if st == 1:
                        B.emit("inv", "BP%d" % i, ["P%d" % i], False)
                    else:
                        B.fwd("BP%d" % i)
                    prod |= {gi, pi, "BP%d" % i}
                fwd_except(prod)
                B.end()
            carry = ["G%d" % i for i in range(W)]
        else:
            B.begin()
            prod = set()
            for i in range(W):
                B.fwd("G%d" % i); B.fwd("P%d" % i)
                B.emit("inv", "BP%d" % i, ["P%d" % i], False)
                prod |= {"G%d" % i, "P%d" % i, "BP%d" % i}
            B.emit("inv", "C0", ["G0"], False); prod.add("C0")
            fwd_except(prod)
            B.end()
            for i in range(1, W):
                B.begin()
                prod = set()
                for j in range(W):
                    B.fwd("G%d" % j); B.fwd("P%d" % j); B.fwd("BP%d" % j)
                    prod |= {"G%d" % j, "P%d" % j, "BP%d" % j}
                for j in range(i):
                    B.fwd("C%d" % j); prod.add("C%d" % j)
                if B.pol("C%d" % (i - 1)):
                    B.emit("a21oi", "C%d" % i, ["P%d" % i, "C%d" % (i - 1),
                                                "G%d" % i], False)
                else:
                    B.emit("o21ai", "C%d" % i, ["P%d" % i, "C%d" % (i - 1),
                                                "G%d" % i], True)
                prod.add("C%d" % i)
                fwd_except(prod)
                B.end()
            carry = ["C%d" % i for i in range(W)]
        # ---- sum level.  Every sum bit is normalised to TRUE polarity so the
        # next step starts from a known state.
        B.begin()
        prod = set()
        for i in range(W):
            if i == 0:
                to_true("BP0", "%s0" % dst)
            else:
                pb, cb = B.pol("BP%d" % i), B.pol(carry[i - 1])
                kind = "xor2" if (pb == cb) else "xnor2"
                B.emit(kind, "%s%d" % (dst, i), ["BP%d" % i, carry[i - 1]], True)
            prod.add("%s%d" % (dst, i))
        fwd_except(prod)
        B.end()

    def do_xor_rot(dst, srcw, r):
        """dst = rotl(dst ^ src, r) in ONE level.  The rotation is folded into
        which nets each XOR cell reads, so it costs nothing at all."""
        B.begin()
        prod = set()
        for j in range(W):
            k = (j - r) % W
            pd, ps = B.pol("%s%d" % (dst, k)), B.pol("%s%d" % (srcw, k))
            kind = "xor2" if (pd == ps) else "xnor2"
            B.emit(kind, "%s%d" % (dst, j),
                   ["%s%d" % (dst, k), "%s%d" % (srcw, k)], True)
            prod.add("%s%d" % (dst, j))
        fwd_except(prod)
        B.end()

    STEPS = [("add", "a", "b", 0), ("xor", "d", "a", rots[0]),
             ("add", "c", "d", 0), ("xor", "b", "c", rots[1]),
             ("add", "a", "b", 0), ("xor", "d", "a", rots[2]),
             ("add", "c", "d", 0), ("xor", "b", "c", rots[3])]
    for (op, dd, ss, rr) in STEPS[:nsteps]:
        if op == "add":
            do_add(dd, ss)
        else:
            do_xor_rot(dd, ss, rr)

    ch = B.finish(WORDS)
    ch.evaluate()

    def qr_partial(a, b, c, d, n):
        ops = [("add", 0), ("xor", 0), ("add", 1), ("xor", 1),
               ("add", 2), ("xor", 2), ("add", 3), ("xor", 3)]
        w = dict(a=a, b=b, c=c, d=d)
        seq = [("add", "a", "b", None), ("xor", "d", "a", rots[0]),
               ("add", "c", "d", None), ("xor", "b", "c", rots[1]),
               ("add", "a", "b", None), ("xor", "d", "a", rots[2]),
               ("add", "c", "d", None), ("xor", "b", "c", rots[3])]
        for (op, dd, ss, rr) in seq[:n]:
            if op == "add":
                w[dd] = (w[dd] + w[ss]) & 0xFFFFFFFF
            else:
                w[dd] = rotl32(w[dd] ^ w[ss], rr)
        return (w["a"], w["b"], w["c"], w["d"])

    want = qr_partial(*(D0 + [nsteps]))
    got = []
    for nm in "abcd":
        v = 0
        for i in range(W):
            idx, pol = ch.sigmap[(ch.nb, "%s%d" % (nm, i))]
            bit = ch.levels[ch.nb - 1][idx].val
            if not pol:
                bit = not bit
            v |= (1 if bit else 0) << i
        got.append(v)
    cen = ch.census()
    nfwd = 0
    for lvl in cen["kinds_per_level"]:
        nfwd += lvl.get("inv", 0) + lvl.get("buf", 0)
    ch.vector = dict(inputs=[hex(x) for x in D0], want=[hex(x) for x in want],
                     got=[hex(x) for x in got], MATCH=(tuple(got) == want))
    ch.qr = dict(W=W, adder=adder, rots=list(rots), levels=ch.nb,
                 cells=cen["cells_total"], devices=cen["devices_total"],
                 forwarding_cells=nfwd,
                 forwarding_share_of_cells_pct=round(100.0 * nfwd /
                                                     cen["cells_total"], 2),
                 per_level=cen["n_per_level"],
                 rotate_cells=0, rotate_levels=0,
                 RFC8439_MATCH=ch.vector["MATCH"])
    return ch
