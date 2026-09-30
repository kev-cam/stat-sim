#!/usr/bin/env python3
"""btk/btw.py -- the committed banktank deck generator (btk/bt.py, sha256
5b3582be..., qal/banktank @ 0aae11e) EXTENDED by ONE thing: an explicit
interconnect capacitance.

Everything else -- cells, widths, CL, CBANK, RS, L, VGH, EDGE, LAG, TAIL, T1,
the tg15p triple, the A6 tank-referenced park, the break-before-make phases, the
sequential true-ZCS probe protocol, the 1F-integrator metering, the .OPTIONS,
the .ic, the .measure grid -- is the committed code, reached by importing bt.

REGRESSION GUARANTEE, checked by selftest(): with cw = 0 and ct_mode = "fixed"
this generator emits a netlist BYTE-IDENTICAL to bt.deck().

THE WIRE, three placements:
  "signal"  Cw on EVERY cell output node o{k}_{i} (all 8, whether it swings or
            not -- the rotate wire physically exists on every bit).  The rail
            only has to charge the n_hi(k) nodes whose cell is pulling UP; the
            rest sit at ~0 through their nMOS.  This is where a rotate wire
            actually lives: BEHIND the driving cell's own pMOS, OUTSIDE the LC
            loop.
  "rail"    the SAME rail-visible capacitance, n_hi(k)*Cw, lumped onto rail{k}
            -- i.e. ON the resonant node.  Same total capacitance, only its
            position changes.  This is the discriminating variant.
  "pi"      "signal", but each wire is a 3-segment pi RC ladder (Cw/6, R/3,
            Cw/3, R/3, Cw/3, R/3, Cw/6) with the PDK's own R for that length,
            to bound the lumped-C idealisation.

TANK SIZING, two modes:
  "fixed"    C_t(k) = m * CBANK for every bank -- the committed value.  The wire
             load then lowers the effective m and the delivered rail droops.
  "matched"  C_t(k) = m * (CBANK + n_hi(k)*Cw) -- tanks tuned per bank, which the
             brief endorses, holding the effective m at 10 against the LOADED
             bank so the delivered rail is preserved and the price shows up as
             tank area and hop time instead.
"""
import json, math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt
from bt import (NBANK, MGATE, WP, WN, CLOAD, CBANK, RS_REF, L_REF, VGH, EDGE,
                LAG_PS, TAIL, T1, TZ_ANCH, PAT, widths, in_hi, out_hi, in_net,
                vtank0, schedule, head_lines, bank_cells, phase_pwl, integ,
                parse_mt0, read_prn, zero_after_peak, run as bt_run)

CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)


def n_hi(k):
    """How many of bank k's 8 cells are pulling UP, i.e. how many output nodes
    the rail actually has to charge.  DERIVED from the committed PAT."""
    return sum(1 for i in range(MGATE) if out_hi(k, i))


def ct_of(k, m, cw, ct_mode):
    if ct_mode == "matched":
        return m * (CBANK + n_hi(k) * cw)
    return m * CBANK


# ------------------------------------------------------------- the wire piece
def wire_lines(k, cw, wire_mode, rw):
    """The ONLY addition to the committed netlist."""
    if cw <= 0.0 or wire_mode == "none":
        return []
    L = []
    if wire_mode == "rail":
        L.append("CWR%d rail%d gn%d %.6ff" % (k, k, k, n_hi(k) * cw))
        return L
    for i in range(MGATE):
        o = "o%d_%d" % (k, i)
        if wire_mode == "signal":
            L.append("CW%d_%d %s gn%d %.6ff" % (k, i, o, k, cw))
        elif wire_mode == "pi":
            a, b, c = ("w%d_%da" % (k, i), "w%d_%db" % (k, i), "w%d_%dc" % (k, i))
            L += ["CW%d_%d0 %s gn%d %.6ff" % (k, i, o, k, cw / 6.0),
                  "RW%d_%d1 %s %s %.6f" % (k, i, o, a, rw / 3.0),
                  "CW%d_%d1 %s gn%d %.6ff" % (k, i, a, k, cw / 3.0),
                  "RW%d_%d2 %s %s %.6f" % (k, i, a, b, rw / 3.0),
                  "CW%d_%d2 %s gn%d %.6ff" % (k, i, b, k, cw / 3.0),
                  "RW%d_%d3 %s %s %.6f" % (k, i, b, c, rw / 3.0),
                  "CW%d_%d3 %s gn%d %.6ff" % (k, i, c, k, cw / 6.0)]
        else:
            raise SystemExit("bad wire_mode %s" % wire_mode)
    return L


def tank_branch(k, ct_fF, total_um, l_nh, rs):
    """bt.tank_branch VERBATIM except that the tank capacitance is passed in
    (the committed call is tank_branch(k, m, ...) with m*CBANK inlined)."""
    w = widths(total_um)
    return ["CT%d tnk%d 0 %gf" % (k, k, ct_fF),
            "L%d tnk%d mid%d %gn" % (k, k, k, l_nh),
            "R%d mid%d sw%d %g" % (k, k, k, rs),
            "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (k, k, k, k, w["wp"]),
            "XPK%d sw%d pk%d tnk%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, k, w["park"])]


def integrators(nb, rs, topup):
    return bt.integrators(nb, rs, topup)


# --------------------------------------------------------------------- deck
def deck(m, T, H, dv, mode="free", l_nh=L_REF, total_um=30.0, rs=RS_REF,
         tzr=None, tzq=None, probe=None, nb=NBANK,
         cw=0.0, wire_mode="none", ct_mode="fixed", rw=0.0, probe_span=2.6):
    S = schedule(T, H, dv, tzr, tzq, nb)
    vt0 = dv if mode == "vfull" else vtank0(m, dv)
    big = S["tend"] * 4.0
    L = head_lines() + ["VHI vhi 0 %g" % VGH]
    for k in range(1, nb + 1):
        L += bank_cells(k, dv)
    for k in range(1, nb + 1):
        L += wire_lines(k, cw, wire_mode, rw)
    for k in range(1, nb + 1):
        L += tank_branch(k, ct_of(k, m, cw, ct_mode), total_um, l_nh, rs)

    for k in range(1, nb + 1):
        if probe is None:
            wins = [(S["c"][k], S["o"][k]), (S["r"][k], S["ro"][k])]
        elif probe[0] == "rise":
            if k < probe[1]:
                wins = [(S["c"][k], S["o"][k])]
            elif k == probe[1]:
                wins = [(S["c"][k], None)]
            else:
                wins = []
        else:
            wins = [(S["c"][k], S["o"][k])]
            if k < probe[1]:
                wins.append((S["r"][k], S["ro"][k]))
            elif k == probe[1]:
                wins.append((S["r"][k], None))
        if not wins:
            L += ["VGT%d gt%d 0 0" % (k, k), "VGTP%d gtp%d 0 %g" % (k, k, VGH),
                  "VPK%d pk%d 0 %g" % (k, k, VGH)]
        else:
            L += phase_pwl(k, wins, big)

    topup = (mode == "topup")
    if topup:
        L += bt.topup_devices(nb, total_um, S, vt0)

    tags = []
    if probe is None:
        ig, tags = integrators(nb, rs, topup)
        L += ig
        tend = S["tend"]
        if topup:
            tend = max(tend, max(S["ro"].values()) + EDGE + 60.0 + TAIL)
    elif probe[0] == "rise":
        tend = S["c"][probe[1]] + probe_span * TZ_ANCH * math.sqrt(l_nh / L_REF)
    else:
        # AMENDMENT A1 (qal/cipher): probe_span defaults to the committed 2.6,
        # which gives a 170.3 ps window.  With a wire load the RETURN hop is
        # slower than that and banks 2-4 found NO ZERO inside the window
        # (measured: signal/fixed and signal/matched both aborted at ret2).  The
        # span is widened for EVERY configuration in this run, including the
        # cw = 0 control, so one protocol produces every number -- and the
        # already-probed configurations are RE-PROBED and their zeros compared,
        # because a wider window can only change a zero if a LATER, LARGER
        # current excursion exists, which would itself be a ringing pathology
        # worth reporting.
        tend = S["r"][probe[1]] + probe_span * TZ_ANCH * math.sqrt(l_nh / L_REF)

    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                               % (k, vt0, k, k, vt0) for k in range(1, nb + 1)))
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"]))

    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)]
        for k in range(1, nb + 1):
            cks += [("O%d" % k, S["o"][k]), ("B%d" % k, S["bound"][k]),
                    ("R%d" % k, S["r"][k] - EDGE), ("Q%d" % k, S["ro"][k])]
        cks += [("D", tend - 5.0)]
        for tg in tags:
            kk = re.sub(r"\D", "", tg)
            want = cks if not kk else [x for x in cks
                                       if x[0] in ("Z", "D", "O" + kk, "B" + kk,
                                                   "R" + kk, "Q" + kk)]
            if not kk:
                want = cks
            for nm, tt in want:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        for k in range(1, nb + 1):
            for nm, tt in cks:
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
                L.append(".measure tran VT%d%s FIND V(tnk%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], tend))
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["o"][k])))
            L.append(".measure tran IZQ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["ro"][k])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], tend))
            for i in range(MGATE):
                L.append(".measure tran O%d_%dB FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(S["bound"][k])))
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tend - 5.0)))
                if k > 1:
                    L.append(".measure tran N%d_%dB FIND V(o%d_%d) AT=%.6fp"
                             % (k, i, k - 1, i, g(S["bound"][k])))
            # --- ADDED for the wire study: the output node at the rise-open and
            #     return-open instants, so the wire's own stored energy
            #     1/2 Cw V^2 needs no integrator and no convention.
            if cw > 0.0 and wire_mode != "rail":
                for i in range(MGATE):
                    L.append(".measure tran W%d_%dO FIND V(o%d_%d) AT=%.6fp"
                             % (k, i, k, i, g(S["o"][k])))
                    L.append(".measure tran W%d_%dQ FIND V(o%d_%d) AT=%.6fp"
                             % (k, i, k, i, g(S["ro"][k])))
                    L.append(".measure tran W%d_%dP MAX V(o%d_%d) FROM=%gp TO=%gp"
                             % (k, i, k, i, S["c"][k], tend))
            if cw > 0.0 and wire_mode == "rail":
                L.append(".measure tran WR%dO FIND V(rail%d) AT=%.6fp"
                         % (k, k, g(S["o"][k])))
                L.append(".measure tran WR%dQ FIND V(rail%d) AT=%.6fp"
                         % (k, k, g(S["ro"][k])))
        pr = (["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)] +
              ["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(sw%d)" % k for k in range(1, nb + 1)] +
              ["V(o%d_%d)" % (k, i) for k in range(1, nb + 1) for i in range(MGATE)])
    else:
        pr = (["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=2400):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run(["/usr/local/src/xyce-build/src/Xyce", fn],
                           capture_output=True, text=True, timeout=timeout,
                           cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout
    wall = time.monotonic() - t0
    ok = os.path.exists(path + ".prn")
    if r.returncode != 0 or not ok:
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-300:])
    return path, "ran %s in %.1fs" % (fn, wall)


def cfgtag(cw, wire_mode, ct_mode):
    if cw <= 0.0 or wire_mode == "none":
        return "cw0"
    return "%s_%s_cw%.0f" % (wire_mode, ct_mode, cw * 1000)


def probe_cfg(m, dv, T, H, cw, wire_mode, ct_mode, rw, l_nh=L_REF, nb=NBANK,
              probe_span=2.6):
    """The committed SEQUENTIAL true-ZCS protocol (bt.do_probe), schedule-matched
    (banktank A7), re-run for THIS wire configuration."""
    tag = "%s_m%g_dv%g_T%g_H%d%s" % (cfgtag(cw, wire_mode, ct_mode), m,
                                     dv * 1000, T, H,
                                     "" if probe_span == 2.6 else
                                     "_sp%g" % probe_span)
    tzr, tzq = [], []
    for ph in ("rise", "ret"):
        lst = tzr if ph == "rise" else tzq
        for k in range(1, nb + 1):
            padr = tzr + [TZ_ANCH] * (nb - len(tzr))
            padq = tzq + [TZ_ANCH] * (nb - len(tzq))
            lines, S = deck(m, T, H, dv, l_nh=l_nh, tzr=padr, tzq=padq,
                            probe=(ph, k), cw=cw, wire_mode=wire_mode,
                            ct_mode=ct_mode, rw=rw, probe_span=probe_span)
            fn = "p_%s_%s%d.cir" % (tag, ph, k)
            path = os.path.join(HERE, fn)
            cached = (os.path.exists(path) and os.path.exists(path + ".prn")
                      and open(path).read() == "\n".join(lines) + "\n")
            p, msg = (path, "reused %s" % fn) if cached else run(fn, lines)
            print("  probe %s%d %s" % (ph, k, msg), flush=True)
            if p is None:
                return None
            hdr, rows = read_prn(p + ".prn")
            t0 = S["c"][k] if ph == "rise" else S["r"][k]
            z, pk = zero_after_peak(hdr, rows, "I(L%d)" % k, t0)
            if z is None:
                print("  probe %s%d NO ZERO" % (ph, k))
                return None
            lst.append(z - t0)
            print("    %s%d t_zcs = %.4f ps (Ipk %.2f uA)"
                  % (ph, k, lst[-1], pk * 1e6), flush=True)
    return dict(m=m, dv=dv, L_nH=l_nh, tzr=tzr, tzq=tzq, T_probe=T, H_probe=H,
                cw=cw, wire_mode=wire_mode, ct_mode=ct_mode, rw=rw,
                probe_span=probe_span,
                protocol="sequential8_schedule_matched")


def rowtag(m, T, H, dv, mode, cw, wire_mode, ct_mode):
    return "m%g_T%g_H%d_dv%g_%s_%s" % (m, T, H, dv * 1000, mode,
                                       cfgtag(cw, wire_mode, ct_mode))


# ------------------------------------------------------------------ selftest
def selftest():
    """cw = 0 + ct_mode fixed  ==>  byte-identical to the committed generator."""
    ok = True
    for (m, T, H, dv, mode, zf) in [
            (10, 150.0, 4, 1.65, "free", "zeros_m10_dv1650.json"),
            (10, 200.0, 4, 1.2, "free", "zeros_m10_dv1200_T200_H4.json")]:
        z = json.load(open(os.path.join(HERE, zf)))
        a, _ = bt.deck(m, T, H, dv, mode=mode, tzr=z["tzr"], tzq=z["tzq"])
        b, _ = deck(m, T, H, dv, mode=mode, tzr=z["tzr"], tzq=z["tzq"],
                    cw=0.0, wire_mode="none", ct_mode="fixed")
        same = ("\n".join(a) == "\n".join(b))
        print("selftest row  %s  %s" % (zf, "IDENTICAL" if same else "DIFFERS"))
        ok = ok and same
        for ph in ("rise", "ret"):
            for k in (1, 4):
                a, _ = bt.deck(m, T, H, dv, tzr=z["tzr"], tzq=z["tzq"],
                               probe=(ph, k))
                b, _ = deck(m, T, H, dv, tzr=z["tzr"], tzq=z["tzq"],
                            probe=(ph, k), cw=0.0, wire_mode="none",
                            ct_mode="fixed")
                s = ("\n".join(a) == "\n".join(b))
                ok = ok and s
                if not s:
                    print("  selftest probe %s%d DIFFERS" % (ph, k))
    print("SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "selftest":
        sys.exit(0 if selftest() else 1)
    if a[0] == "probe":
        # probe m dv T H cw wire_mode ct_mode rw
        m, dv, T, H = float(a[1]), float(a[2]), float(a[3]), int(a[4])
        cw, wm, cm, rw = float(a[5]), a[6], a[7], float(a[8])
        sp = float(a[9]) if len(a) > 9 else 2.6
        z = probe_cfg(m, dv, T, H, cw, wm, cm, rw, probe_span=sp)
        if z is None:
            sys.exit(1)
        nm = "z_%s_m%g_dv%g_T%g_H%d%s.json" % (cfgtag(cw, wm, cm), m, dv * 1000,
                                               T, H,
                                               "" if sp == 2.6 else "_sp%g" % sp)
        open(os.path.join(HERE, nm), "w").write(json.dumps(z, indent=1))
        print("wrote %s" % nm)
    elif a[0] == "row":
        # row m T H dv mode cw wire_mode ct_mode rw zeros.json
        m, T, H, dv, mode = float(a[1]), float(a[2]), int(a[3]), float(a[4]), a[5]
        cw, wm, cm, rw = float(a[6]), a[7], a[8], float(a[9])
        z = json.load(open(os.path.join(HERE, a[10])))
        lines, S = deck(m, T, H, dv, mode=mode, tzr=z["tzr"], tzq=z["tzq"],
                        cw=cw, wire_mode=wm, ct_mode=cm, rw=rw)
        fn = "c_%s.cir" % rowtag(m, T, H, dv, mode, cw, wm, cm)
        p, msg = run(fn, lines)
        print("  row %s" % msg, flush=True)
        sys.exit(0 if p else 1)
