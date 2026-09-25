#!/usr/bin/env python3
"""Nominal per-cell ENERGY + DELAY characterization for the DIRECT-THRESHOLD TH cells
(th23, th33, th34w2, th14) -- the cells the Fant/natural-threshold mapping needs and
that char_energy_nominal.py never covered.

Same method as char_energy_nominal.py (which did th22/th12/th13):
  E_cell(C_load) = E0 + k*C_load, fitted on CL = 1/3/10 fF, one op = a full
  DATA -> NULL return-to-zero cycle, Vdd=1.2V, SG13G2 PSP103 tt.
  Energy via '.measure tran QOP INTEG I(VDD)' + PARAM multiply (the form that has
  always cross-validated). NEVER '.measure INTEGRAL V(Bsrc)'.

STIMULUS / ARCS -- worked out from what actually co-fires in the netlist:

  th23  (2-of-3, ldx/asic/cells/th_gates.sp)
      In the Fant full adder, ncl_gates.vhd:197  coutt := th23(at,bt,cint).
      at/bt/cint are the TRUE rails of a/b/cin, so the number of asserted inputs is
      popcount(a,b,cin) in {0,1,2,3} and the gate fires iff >=2 -- i.e. it IS the
      carry majority. Arcs:
        2of3  A,B fire, C low   -> OUTPUT FIRES. Minimal firing arc (popcount 2).
        3of3  A,B,C fire        -> OUTPUT FIRES (popcount 3), more input energy.
        1of3  A fires only      -> NO output transition (popcount 1), partial activity.
      Uniform random data: p(0,1,2,3) = 1/8, 3/8, 3/8, 1/8.

  th33  (3-of-3, th_gates.sp)
      map_ncl_struct.py:53-62 MUX_MIN -- th33 is a DIMS 3-rail minterm over (s,a,b).
      Exactly one of the 8 minterms has all three rails asserted per op.
        3of3  A,B,C fire -> FIRES. The selected minterm.
        2of3  A,B fire   -> NO fire. A non-selected minterm differing in one rail;
                            this is the COMMON case (7 of 8 minterms do not fire).

  th34w2 (weighted 3-of-4, A has weight 2; fires when 2A+B+C+D >= 3)
      ncl_gates.vhd:199  st := th34w2(coutf, at, bt, cint)  -- A = coutf (weight 2).
      With p = popcount(at,bt,cint): coutf asserts iff p<=1, so
        p=0: A only          -> 2 <3  NO fire   (sum bit 0)
        p=1: A + one of BCD  -> 3 >=3 FIRES via an A.X 2-series branch
        p=2: two of BCD      -> 2 <3  NO fire   (sum bit 0)
        p=3: B,C,D (A low)   -> 3 >=3 FIRES via the B.C.D 3-series branch
      The two FIRING arcs use structurally different pull-down branches (2-series vs
      3-series nMOS), so both are characterized separately.

  th14  (1-of-4, mylex/nulex/lib/th_cells_sg13g2.sp)
      map_ncl_struct.py:64 COLLECT = {2:th12, 3:th13, 4:th14} -- a rail collector over
      MUTUALLY EXCLUSIVE minterms, so exactly ONE input fires per op, same convention
      as the already-measured th12/th13. Driving all four would overstate it.

DELAY: TRIG on the (simultaneously arriving) firing input at 50%, TARG V(y) at 50%,
same convention as the th22 356 ps figure. Simultaneous arrival is the max-drive case,
so these delays are OPTIMISTIC for the >=2-input threshold gates.
"""
import os, re, subprocess, sys, json

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
INC   = ["/usr/local/src/ldx/asic/cells/th22.sp",
         "/usr/local/src/ldx/asic/cells/th_gates.sp",
         "/usr/local/src/mylex/nulex/lib/th_cells_sg13g2.sp"]
VDD   = 1.2
OUT   = "cell_energy_th_direct.json"

# arc name -> (cell, all ports in subckt order, ports that FIRE, fires_output?)
ARCS = {
    "th22_both":    ("th22",   ["A","B"],         ["A","B"],     True),   # sanity re-run
    # non-firing th22 arc: a DIMS minterm whose (a,b) combination does NOT hold still
    # receives one asserted rail. Tests the "mutually exclusive -> non-firing cells are
    # free" assumption behind the alpha=0.250 / 7.23 pJ DIMS correction.
    "th22_aonly":   ("th22",   ["A","B"],         ["A"],         False),
    # RIPPLE-CHAIN CRITICAL ARC (delay-only; see EARLY). a,b stable early, carry-in C
    # arrives last and is what meets the threshold -> fires through the single A.C
    # 2-series branch. This is the real 8-bit carry-propagate arc; the simultaneous-
    # arrival th23_2of3 number is optimistic for it.
    "th23_cin_late": ("th23",  ["A","B","C"],     ["C"],         True),
    "th23_2of3":    ("th23",   ["A","B","C"],     ["A","B"],     True),
    "th23_3of3":    ("th23",   ["A","B","C"],     ["A","B","C"], True),
    "th23_1of3":    ("th23",   ["A","B","C"],     ["A"],         False),
    "th33_3of3":    ("th33",   ["A","B","C"],     ["A","B","C"], True),
    "th33_2of3":    ("th33",   ["A","B","C"],     ["A","B"],     False),
    "th34w2_w2p1":  ("th34w2", ["A","B","C","D"], ["A","B"],     True),
    "th34w2_bcd":   ("th34w2", ["A","B","C","D"], ["B","C","D"], True),
    "th34w2_aonly": ("th34w2", ["A","B","C","D"], ["A"],         False),
    "th34w2_bc":    ("th34w2", ["A","B","C","D"], ["B","C"],     False),
    "th14_1of4":    ("th14",   ["A","B","C","D"], ["A"],         True),
}


def deck(cell, ins, fire, cl_ff, early=()):
    """early = inputs that are ALREADY DATA before the late input arrives (ripple-chain
    case: a,b of a full adder are stable long before the carry-in ripples in). They rise
    at 0.5n and fall at 6.4n, straddling the late input's 2n/6n window, so the measured
    arc is genuinely 'threshold met by the LAST input'."""
    L = ['* nominal energy: %s  fire=%s early=%s  CL=%gfF'
         % (cell, "+".join(fire), "+".join(early) or "-", cl_ff),
         '.hdl "%s"' % VA, '.include "%s"' % MODEL]
    L += ['.include "%s"' % i for i in INC]
    L += ["VDD vdd 0 %g" % VDD, "VSS vss 0 0"]
    # DATA at 2n (0.1n edge), NULL at 6n; measure the full cycle 1.9n..10n
    for p in ins:
        if p in early:
            L.append("V%s %s 0 PWL(0 0 0.4n 0 0.5n %g 6.4n %g 6.5n 0 12n 0)"
                     % (p, p.lower(), VDD, VDD))
        elif p in fire:
            L.append("V%s %s 0 PWL(0 0 1.9n 0 2n %g 5.9n %g 6n 0 12n 0)"
                     % (p, p.lower(), VDD, VDD))
        else:
            L.append("V%s %s 0 0" % (p, p.lower()))
    nodes = " ".join(p.lower() for p in ins)
    L += ["X1 %s y vdd vss %s" % (nodes, cell),
          "CL y 0 %gf" % cl_ff,
          ".tran 2p 12n",
          ".print tran V(y)",
          ".measure tran QOP INTEG I(VDD) from=1.9n to=10n",
          ".measure tran EOP PARAM {%g*QOP}" % (-VDD),
          ".measure tran YMAX MAX V(y) from=1.9n to=10n",
          ".measure tran YEND FIND V(y) AT=9.9n",
          ".measure tran TD TRIG V(%s) VAL=%g RISE=1 TARG V(y) VAL=%g RISE=1"
              % (fire[0].lower(), VDD/2, VDD/2),
          ".end"]
    return "\n".join(L) + "\n"


# arcs whose listed inputs are ALREADY DATA before the late (fire) input arrives
EARLY = {"th23_cin_late": ["A"]}


def run(arc, cl, tag=""):
    cell, ins, fire, _ = ARCS[arc]
    fn = "cd_%s%s_%g.cir" % (arc, tag, cl)
    open(fn, "w").write(deck(cell, ins, fire, cl, EARLY.get(arc, ())))
    if int(subprocess.run("pgrep Xyce | wc -l", shell=True, capture_output=True,
                          text=True).stdout.strip()) > 0:
        print("  REFUSING: another Xyce is running"); return None
    env = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=1800, env=env)
    except subprocess.TimeoutExpired:
        print("  %-14s CL=%-5g TIMEOUT" % (arc, cl)); return None
    o = r.stdout
    g = {}
    for k in ("EOP", "YMAX", "YEND", "TD"):
        m = re.search(r"^%s\s*=\s*(\S+)" % k, o, re.M)
        if m:
            try: g[k] = float(m.group(1))
            except ValueError: pass
    if "EOP" not in g:
        print("  %-14s CL=%-5g NO EOP. tail:\n%s" % (arc, cl, o[-1500:]))
        return None
    return g


def fit(xs, ys):
    n = len(xs)
    if n < 2: return (ys[0] if ys else 0.0), 0.0
    mx = sum(xs)/n; my = sum(ys)/n
    den = sum((x-mx)**2 for x in xs)
    k = sum((x-mx)*(y-my) for x, y in zip(xs, ys))/den if den else 0.0
    return my - k*mx, k


def load():
    try: return json.load(open(OUT))
    except Exception: return {"vdd": VDD, "arcs": {}}


def save(db):
    db["_doc"] = ("direct-threshold TH cell energy, SG13G2 PSP103 tt, DATA->NULL "
                  "cycle, Vdd=1.2V. E(CL)=E0+k*CL[fF]. Arcs chosen from the Fant "
                  "adder (ncl_gates.vhd:197-200), MUX_MIN and COLLECT "
                  "(map_ncl_struct.py:53-64). Companion to cell_energy_nominal.json.")
    json.dump(db, open(OUT, "w"), indent=1)


def main():
    jobs = sys.argv[1:]
    db = load()
    for spec in jobs:
        arc, _, cls = spec.partition(":")
        loads = [float(x) for x in cls.split(",")] if cls else [1.0, 3.0, 10.0]
        if arc not in ARCS:
            print("unknown arc %s" % arc); continue
        rec = db["arcs"].setdefault(arc, {"cell": ARCS[arc][0],
                                          "fire": ARCS[arc][2],
                                          "fires_output": ARCS[arc][3],
                                          "points": {}})
        for cl in loads:
            g = run(arc, cl)
            if g is None: continue
            e = g["EOP"]*1e15
            rec["points"][str(cl)] = {"E_fJ": round(e, 4),
                                      "ymax": round(g.get("YMAX", 0), 4),
                                      "yend": round(g.get("YEND", 0), 5),
                                      "td_ps": round(g.get("TD", float("nan"))*1e12, 2)}
            print("  %-14s CL=%5gfF  E=%9.4f fJ/op  Ymax=%.4f  Yend=%.5f  td=%8.2f ps"
                  % (arc, cl, e, g.get("YMAX", 0), g.get("YEND", 0),
                     g.get("TD", float("nan"))*1e12))
            save(db)
        pts = sorted((float(k), v["E_fJ"]) for k, v in rec["points"].items())
        base = [p for p in pts if p[0] in (1.0, 3.0, 10.0)]
        if len(base) >= 2:
            E0, k = fit([p[0] for p in base], [p[1] for p in base])
            rec["E0_fJ"] = round(E0, 4); rec["k_fJ_per_fF"] = round(k, 4)
            rec["resid_fJ"] = [round(y - (E0 + k*x), 4) for x, y in base]
            print("  %-14s -> E(CL) = %.4f + %.4f*CL  resid=%s"
                  % (arc, E0, k, rec["resid_fJ"]))
        save(db)
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
