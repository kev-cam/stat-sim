#!/usr/bin/env python3
"""S1 -- both instrument anchors, re-run under MY OWN cache from md5-verified
byte-identical copies of the committed decks.  Nothing else reports until these
digit-check."""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import sk

EXP = dict(t_hop=65.49500982344826, VBEND=0.7138163, VBPK=0.8368896,
           damage_mV=113.565, free_low=0.438143, clamp_low=0.551708)


def go(fn):
    t0 = time.monotonic()
    r = subprocess.run([sk.XYCE, fn], capture_output=True, text=True,
                       cwd=sk.HERE, env=sk.ENV, timeout=1800)
    return fn, time.monotonic() - t0, r.returncode


if __name__ == "__main__":
    decks = ["a_p.cir", "a_h.cir", "a_free.cir", "a_clamp.cir"]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for fn, w, rc in ex.map(go, decks):
            print("%-12s %6.1fs rc=%d" % (fn, w, rc), flush=True)
    out = {}
    # (a) the robust single hop
    hdr, rows = sk.read_prn(os.path.join(sk.HERE, "a_p.cir.prn"))
    z, pk = sk.zero_after_peak(hdr, rows, "I(LT)", 50.0)
    out["t_hop_ps"] = z - 50.0
    m = sk.parse_mt0(os.path.join(sk.HERE, "a_h.cir.mt0"))
    out["VBEND"] = m.get("VBEND")
    out["VBPK"] = m.get("VBPK")
    out["IZ_uA"] = m.get("IZ", 0.0) * 1e6
    cells = sorted(k for k in m if k.startswith("O") and k.endswith("S"))
    out["n_cell_measures"] = len(cells)
    out["rel_t_hop"] = abs(out["t_hop_ps"] - EXP["t_hop"]) / EXP["t_hop"]
    out["rel_VBEND"] = abs(out["VBEND"] - EXP["VBEND"]) / EXP["VBEND"]
    out["rel_VBPK"] = abs(out["VBPK"] - EXP["VBPK"]) / EXP["VBPK"]
    # (b) the skiptu clamp attributable stage-2 damage
    def low2(fn):
        mm = sk.parse_mt0(os.path.join(sk.HERE, fn))
        pd = [mm["O2_%dS" % i] for i in range(8)
              if ("O2_%dS" % i) in mm and (i + 2) % 2 == 1]
        return max(pd), len(pd), mm
    lf, nf, mf = low2("a_free.cir.mt0")
    lc, nc, mc = low2("a_clamp.cir.mt0")
    out["skiptu_free_max_LOW_V"] = lf
    out["skiptu_clamp_max_LOW_V"] = lc
    out["skiptu_n_pulldown"] = nf
    out["skiptu_damage_mV"] = (lc - lf) * 1e3
    out["skiptu_damage_err_mV"] = abs(out["skiptu_damage_mV"] - EXP["damage_mV"])
    out["skiptu_rail3_free_V"] = mf.get("VR3K3")
    out["skiptu_rail3_clamp_V"] = mc.get("VR3K3")
    out["PASS"] = (out["rel_t_hop"] < 1e-6 and out["rel_VBEND"] < 1e-6
                   and out["rel_VBPK"] < 1e-6 and out["skiptu_damage_err_mV"] < 1.0)
    json.dump(out, open(os.path.join(sk.HERE, "ANCHOR_SKEPT.json"), "w"), indent=1)
    for k, v in out.items():
        print("  %-24s %s" % (k, v))
