#!/usr/bin/env python3
"""(d) THE BOOKING AUDIT.

Every independent voltage source in a deck is an IDEAL source: infinite drive,
zero output impedance, and -- the point for this campaign -- its charge is
supplied from outside the circuit and is charged to no rail.  This enumerates
them per deck and classifies them, for BOTH runs' decks, and specifically asks:

  is the TG's own drive counted?

A transmission gate has FOUR MOS gates.  In a tg_mux2 the cell's own control
inverter drives two of them (that charge IS on the bank rail).  The other two sit
on the SELECT line.  In a real circuit the select line is driven by rail-powered
logic; in these decks it is an ideal source, so that half of the gate-drive
charge is charged to nothing.
"""
import collections, json, os, re, sys

DECKS = {
    "run/D_raildraw.cir": "/usr/local/src/stat-sim/qal/pgcell/D_raildraw.cir",
    "run/D2_raildraw_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell/D2_raildraw_vhi.cir",
    "run/E_level.cir": "/usr/local/src/stat-sim/qal/pgcell/E_level.cir",
    "run/C_W.cir": "/usr/local/src/stat-sim/qal/pgcell/C_W.cir",
    "run/F_ALT_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell/ALT_vhi/F_ALT_vhi.cir",
    "run/F_CTL_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell/CTL_vhi/F_CTL_vhi.cir",
    "run/F_ALLTG_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell/ALLTG_vhi/F_ALLTG_vhi.cir",
    "mine/R_rail.cir": "/usr/local/src/stat-sim/qal/pgcell_skept/R_rail.cir",
    "mine/L_level.cir": "/usr/local/src/stat-sim/qal/pgcell_skept/L_level.cir",
    "mine/F_CTL_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell_skept/CTL_vhi/F_CTL_vhi.cir",
    "mine/F_ALT_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell_skept/ALT_vhi/F_ALT_vhi.cir",
    "mine/F_ALTB_vhi.cir": "/usr/local/src/stat-sim/qal/pgcell_skept/ALTB_vhi/F_ALTB_vhi.cir",
    "mine/F_ALT_rail.cir": "/usr/local/src/stat-sim/qal/pgcell_skept/ALT_rail/F_ALT_rail.cir",
}

CLASS = [
    (r"^VS(?!EL)", "rail / supply ramp (the METERED bank supply)"),
    (r"^VHI", "the global +1.5 V fixed-well / switch-drive supply"),
    (r"^VQ", "second rail source (mux under the gate-drive meter)"),
    (r"^(VSEL|VD?SEL)", "TG SELECT line -- drives 2 of the TG's 4 gates"),
    (r"^VGTP", "bank transfer-switch pMOS gate drive (tg15p, committed)"),
    (r"^VGT", "bank transfer-switch nMOS gate drive (tg15p, committed)"),
    (r"^VPK", "bank transfer-switch PARK gate drive (tg15p, committed)"),
    (r"^VG", "TG cell gate control (ideal -- the TG's own drive NOT charged to a rail)"),
    (r"^VP", "TG cell pMOS gate control (ideal)"),
    (r"^VD", "cell data input"),
    (r"^VA[01]", "mux data input"),
    (r"^VI", "bank-1 chain-head input / inverter input"),
    (r"^VH", "cascade head"),
    (r"^VO", "cascade off-path head"),
    (r"^VMG", "bank ground reference"),
    (r"^VT", "tank pre-charge"),
    (r"^VR", "tank / rail pre-charge"),
    (r"^V", "other ideal source"),
]


def classify(nm):
    for pat, lab in CLASS:
        if re.match(pat, nm, re.I):
            return lab
    return "other"


def audit(path):
    src = collections.Counter()
    names = collections.defaultdict(list)
    for ln in open(path):
        s = ln.strip()
        if not s or s[0] in ".*+":
            continue
        t = s.split()
        if t[0][0].upper() == "V":
            c = classify(t[0])
            src[c] += 1
            if len(names[c]) < 3:
                names[c].append(s[:90])
    return dict(total_ideal_sources=sum(src.values()),
                by_class={k: dict(n=v, examples=names[k]) for k, v in src.items()})


if __name__ == "__main__":
    R = {}
    for name, p in DECKS.items():
        if not os.path.exists(p):
            R[name] = dict(error="not present")
            continue
        R[name] = audit(p)
        print("%-26s %4d ideal sources" % (name, R[name]["total_ideal_sources"]))
        for k, v in sorted(R[name]["by_class"].items(), key=lambda x: -x[1]["n"]):
            print("      %3d  %s" % (v["n"], k))
    json.dump(R, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "BOOKING.json"), "w"), indent=1)
    print("wrote BOOKING.json")
