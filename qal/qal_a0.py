#!/usr/bin/env python3
"""QAL A0 — schedule model (QAL_PLAN.md sec.2 A0). Prove the RTL->wave transform is
functionally correct BEFORE any transistor exists, and that the 3D-Logic certainty plane
(un-compute window = MEANINGLESS, distinct from X) catches an un-balanced schedule.

Vehicle: SHA-256 sigma0(x) = ROTR7(x) ^ ROTR18(x) ^ SHR3(x)  (32-bit, XOR depth 2, no carries).

The wave: phase φ = dataflow level. A stage evaluates at its phase's flat top and un-computes
after (data ephemeral, no restoration). A net is readable ONLY during its own phase's flat top;
read it earlier and it is NOTYET, later and it is UNCOMPUTED — both MEANINGLESS, a third
certainty state, never a stale bit and never X. So a consumer must be scheduled exactly one
phase after its producer; a late input needs a balancing BUFFER to arrive in-phase (the AQFP-
style equal-arrival constraint, QAL_PLAN B3). This model demonstrates the buffer is *required*:
without it the level-2 XOR reads t3 during its un-computed window and the certainty plane flags it.
"""
MASK = 0xFFFFFFFF
def rotr(x, n): return ((x >> n) | (x << (32 - n))) & MASK
def sigma0_ref(x): return rotr(x, 7) ^ rotr(x, 18) ^ ((x >> 3))  # SHR3 has no wrap

# ---- 3D-Logic certainty (value plane omitted here; A0 is ideal, focus on the certainty plane) ----
NOTYET, VALID, UNCOMPUTED = "NOTYET", "VALID", "UNCOMPUTED"   # UNCOMPUTED/NOTYET are MEANINGLESS (not X)

class Net:
    __slots__ = ("name", "level", "val")
    def __init__(self, name, level): self.name, self.level, self.val = name, level, None
    def certainty(self, phase):
        if phase < self.level: return NOTYET
        if phase == self.level: return VALID
        return UNCOMPUTED     # rail has recovered — meaningless, NOT X

def wave_sigma0(x, balanced=True):
    """Evaluate sigma0 as a phased wave. Returns (result, violations). A violation = a gate that
    read an input whose certainty was not VALID at the gate's phase (schedule/balancing error)."""
    # level 0: input + wiring (rotates/shifts are bit permutations of x -> free, level 0)
    t1 = Net("t1=ROTR7", 0);  t1.val = rotr(x, 7)
    t2 = Net("t2=ROTR18", 0); t2.val = rotr(x, 18)
    t3 = Net("t3=SHR3", 0);   t3.val = (x >> 3)
    nets = [t1, t2, t3]
    # level 1: a = t1 ^ t2 ; and (if balanced) a pass-through buffer carries t3 to arrive in-phase
    a = Net("a=t1^t2", 1)
    gates = [("a", a, "XOR", [t1, t2])]
    t3_at_L2 = t3
    if balanced:
        bt3 = Net("buf(t3)", 1); gates.append(("buf", bt3, "BUF", [t3])); t3_at_L2 = bt3; nets.append(bt3)
    nets += [a]
    # level 2: s0 = a ^ (t3 or buf(t3))
    s0 = Net("s0=a^t3", 2); gates.append(("s0", s0, "XOR", [a, t3_at_L2])); nets.append(s0)
    # run the wave: at gate output level L, inputs must be VALID at phase L-1 -> the crossing transfer.
    violations = []
    for gname, out, op, ins in gates:
        read_phase = out.level - 1                       # inputs captured at the producer/consumer crossing
        for i in ins:
            c = i.certainty(read_phase)
            if c != VALID:
                violations.append(f"gate {out.name}@φ{out.level} read {i.name} at φ{read_phase}: {c} (MEANINGLESS)")
        v = [i.val for i in ins]
        out.val = (v[0] ^ v[1]) if op == "XOR" else v[0]  # BUF passes through
    return s0.val, violations, nets, gates

def main():
    import random
    rng = random.Random(0x5A17)
    print("=" * 82)
    print("QAL A0 — sigma0 as a phased wave: functional proof + certainty-plane check")
    print("=" * 82)
    # (1) schedule
    _, _, nets, gates = wave_sigma0(0, balanced=True)
    print("  balanced schedule (level = phase):")
    for n in nets: print("    φ%d  %-10s" % (n.level, n.name))
    nbuf = sum(1 for g in gates if g[2] == "BUF")
    print("  -> XOR depth 2; %d balancing buffer/bit inserted so t3 arrives in-phase at φ2 (×32 bits)" % nbuf)

    # (2) functional correctness vs the SHA-256 reference
    NV = 20000; ok = True
    for _ in range(NV):
        x = rng.getrandbits(32)
        r, viol, _, _ = wave_sigma0(x, balanced=True)
        if r != sigma0_ref(x) or viol: ok = False; break
    print("\n  (1) FUNCTIONAL: wave sigma0 == SHA-256 reference over %d random vectors: %s"
          % (NV, "PASS" if ok else "FAIL"))

    # (3) certainty plane catches the un-balanced schedule
    x = 0xDEADBEEF
    rb, vb, _, _ = wave_sigma0(x, balanced=True)
    ru, vu, _, _ = wave_sigma0(x, balanced=False)
    print("\n  (2) CERTAINTY PLANE (un-compute = MEANINGLESS, not X):")
    print("    balanced   : result=0x%08X  violations=%d" % (rb, len(vb)))
    print("    UNbalanced : result=0x%08X  violations=%d" % (ru, len(vu)))
    for v in vu: print("       ! " + v)
    print("    -> without the buffer, φ2's XOR reads t3 one phase too late — its rail has recovered,")
    print("       so the certainty plane returns UNCOMPUTED (meaningless), a DETECTABLE schedule error.")
    print("       In 4-state this would silently read a stale/X bit; the 3rd certainty plane makes")
    print("       the un-compute window a checkable state, which is why A0 needs 3D-Logic.")

    print("\n  A0 DELIVERABLE: RTL->wave transform proven functionally correct (golden model), the")
    print("  equal-arrival balancing requirement made concrete (buffer count), and the certainty-plane")
    print("  semantics validated. Next: A1 (single-gate Xyce, ramp rail, residual charge), then the")
    print("  A3 mismatch-MC GO/NO-GO (the fixed cell-MC flow) — nothing above A3 is worth building first.")

if __name__ == "__main__":
    main()
