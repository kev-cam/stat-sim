#!/usr/bin/env python3
"""A6: re-probe the k=1 hop zeros PER STRUCTURAL CLASS and re-run the k=1 chain.

AMENDMENT A2 transferred the zeros measured on a ONE-SEGMENT deck to every segment
of the full chain, and said in terms that acceptance A4 would CHECK that transfer
per hop.  It DID check it and it FAILED: on the k=1 6-bank chain, |I(L)| at the
switch's own opening instant was -0.0045 uA on hop 1 but 11.17 / 18.04 / 17.97 /
17.97 / 16.25 uA on hops 2-6, against a 1.0 uA gate.

The reason is structural, and a one-segment deck cannot contain it.  At k=1 the six
hops are NOT identical: they differ in what loads their destination bank.

  class A  hop 1      : destination's gates driven by IDEAL DC sources, outputs
                        loaded by a restoring stage
  class B  hops 2..5  : destination's gates driven by a RESTORING STAGE's output,
                        outputs loaded by the next restoring stage
  class C  hop 6      : destination's gates driven by a restoring stage, outputs
                        load NOTHING (it is the end of the chain)

A THREE-segment deck contains one hop of each class, so probing it gives all three
zeros for the price of three short runs instead of six full-length ones.  The zeros
are then mapped A, B, B, B, B, C and A4 is re-checked on the re-run row.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rest, extract

T, TRES, K = 300.0, 179.0, 1
NB_PROBE = 3


def main():
    tz = []
    for h in (1, 2, 3):
        lines, S = rest.deck(K, T, TRES, nbank=NB_PROBE,
                             tz=tz + [rest.TZ_ANCHOR * rest.CHAIN_F] * (NB_PROBE - len(tz)),
                             probe=h)
        fn = "q%d_k1_T300.cir" % h
        p, msg = rest.run(fn, lines)
        print("  classprobe%d %s" % (h, msg), flush=True)
        if p is None:
            return 1
        hdr, rows = rest.read_prn(p + ".prn")
        z, pk = rest.zero_after_peak(hdr, rows, "I(L%d)" % h, S["close"][h])
        tz.append(z - S["close"][h])
        print("    class %s hop%d t_zcs = %.4f ps (Ipk %.2f uA)"
              % ("ABC"[h - 1], h, tz[-1], pk * 1e6), flush=True)
    zA, zB, zC = tz
    full = [zA, zB, zB, zB, zB, zC]
    print("  mapped zeros A,B,B,B,B,C = %s" % [round(x, 4) for x in full], flush=True)
    lines, S = rest.deck(K, T, TRES, nbank=rest.NBANK, tz=full)
    p, msg = rest.run("c_k1_T300_zcs.cir", lines)
    print("  row %s" % msg, flush=True)
    if p is None:
        return 1
    r = extract.row_extract(K, T, TRES, full, p)
    r["tres_in_full_chain_ps"] = extract.tres_measure(p, S, rest.NBANK)
    r["_note"] = ("AMENDMENT A6: hop zeros re-probed per structural class on a "
                  "three-segment deck and mapped A,B,B,B,B,C, because the "
                  "one-segment transfer failed acceptance A4 per hop.")
    rows = json.load(open(os.path.join(rest.HERE, "rows.json"))) \
        if os.path.exists(os.path.join(rest.HERE, "rows.json")) else {}
    rows["k1_T300_zcs"] = r
    json.dump(rows, open(os.path.join(rest.HERE, "rows.json"), "w"), indent=1)
    print("  A4 ZCS per hop: %s" % {k: round(v, 5) for k, v in r["IZ_uA"].items()})
    print("  A4 PASS %s | A1 %s | A2 %s | A5 %s | PASS %s"
          % (r["A4_IZ_PASS"], r["A1_all_gates_90_all_banks"],
             r["A2_pattern_guard_all"], r["A5_restore_outputs_full_swing"], r["PASS"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
