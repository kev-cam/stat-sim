#!/usr/bin/env python3
"""Which links actually carry the II verdict?

Every deck's LAST bank has no receiver inside the deck, so its 8 links are
scored GENEROUSLY (at the committed stage boundary).  ii.py showed the strict
alternative (own ZCS) fails EVERY row including T = 300 ps, which the committed
VALUE check passes 32/32 -- so the strict instant is invalid, not merely harsh,
and the generous choice is forced.  That makes the question: does any II
conclusion REST on the generous bank, or do the 24 real-receiver links decide it?
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "II.json")))["rows"]
R = json.load(open(os.path.join(HERE, "RESCORE.json")))["banktank"]
NEW = json.load(open(os.path.join(HERE, "BEAT_NEWROWS.json")))


def links_for(b):
    if b in R:
        return R[b]["links"]
    for k, v in NEW.items():
        if isinstance(v, dict) and v.get("tag") == b:
            return v["links"]
        if isinstance(v, dict) and "links" in v and v.get("deck", "").startswith(b):
            return v["links"]
    return None


out = {}
print("%-34s %2s %4s %5s | %-22s | %-22s | verdict"
      % ("row", "H", "T", "II", "REAL receivers (k<=3)", "GENEROUS last bank (k=4)"))
for b in sorted(D, key=lambda x: (D[x]["H"], D[x]["T"])):
    d = D[b]
    ls = links_for(b)
    if ls is None:
        print("%-34s  -- links not cached --" % b)
        continue
    real = [L for L in ls if not L["rx_generous"]]
    gen = [L for L in ls if L["rx_generous"]]
    rp = sum(1 for L in real if L["S3_pass"])
    gp = sum(1 for L in gen if L["S3_pass"])
    rw = min(L["S3_margin_mV"] for L in real) if real else None
    gw = min(L["S3_margin_mV"] for L in gen) if gen else None
    if rp == len(real) and gp == len(gen):
        v = "PASS (both)"
    elif rp == len(real):
        v = "REAL links all pass; blocked ONLY by the generous bank"
    elif gp == len(gen):
        v = "FAILS on REAL links"
    else:
        v = "FAILS on both"
    out[b] = dict(H=d["H"], T=d["T"], II_ps=d["II_ps"], origin=d["origin"],
                  real_pass=rp, real_n=len(real), real_worst_mV=rw,
                  gen_pass=gp, gen_n=len(gen), gen_worst_mV=gw, verdict=v)
    print("%-34s %2d %4d %5d | %2d/%2d worst %9.3f | %2d/%2d worst %9.3f | %s"
          % (b, d["H"], d["T"], d["II_ps"], rp, len(real), rw, gp, len(gen), gw, v))

# earliest T per H on REAL links only
print()
tab = {}
for b, d in out.items():
    if d["real_pass"] != d["real_n"]:
        continue
    H = d["H"]
    if H not in tab or d["T"] < tab[H]["T"]:
        tab[H] = dict(T=d["T"], II_ps=H * d["T"], row=b)
print("earliest correct T per H, REAL-receiver links only (24 links):")
for H in sorted(tab):
    print("  H=%d  T=%3d ps -> II = %4d ps  (%s)" % (H, tab[H]["T"], tab[H]["II_ps"], tab[H]["row"]))
if tab:
    bestr = min(tab.values(), key=lambda x: x["II_ps"])
    print("  BEST II on real links only = %d ps (%s)" % (bestr["II_ps"], bestr["row"]))
json.dump({"per_row": out, "earliest_real_only": tab},
          open(os.path.join(HERE, "II_ATTRIB.json"), "w"), indent=1)
print("\nwrote II_ATTRIB.json")
