#!/usr/bin/env python3
"""qal/cipher/p2/run.py -- probe, run, extract and score one cipher vehicle.

Conventions are the committed ones, imported rather than restated:
  settle_pct / guard_ok / data_valid_instant  -- qal/cipher/btk/extract.py
  Trip (the measured receiver threshold)      -- qal/fcrit/rescore.py
  schedule / vtank0 / zeros protocol          -- qal/banktank/bt.py
"""
import json, math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CIPH = os.path.dirname(HERE)
QAL = os.path.dirname(CIPH)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CIPH, "btk"))
sys.path.insert(0, os.path.join(QAL, "fcrit"))

import cg, veh
from cg import (Chain, Cell, CELLS, cell_devices, c_bank_derived, deck,
                cmos_deck, run as xrun, probe_chain, integ)
import bt
from bt import (CBANK, CLOAD, RS_REF, L_REF, VGH, EDGE, LAG_PS, TAIL, T1,
                TZ_ANCH, schedule, vtank0, parse_mt0, read_prn, zero_after_peak)
from rescore import Trip

SIGMA_FLOOR_MV = 6.44
VTN, VTP = 0.5239, 0.4403
RESTORE_FLOOR = VTN + VTP          # 0.9642 V
NB_3SIGMA_V = 3 * 6.441 / 1000.0   # 19.323 mV, fcrit's own free-mode budget
TRIP = Trip(os.path.join(QAL, "fcrit", "TRIP.json"), "S")


# ------------------------------------------------------------------ vehicles
# The prefix/forwarding cells of both adders are a21oi / o21ai / nand2 / nor2 /
# inv, whose LEF widths run 1.92-2.40 um; 2.40 um is the widest and is used as
# the bit pitch for the adders' own local routing.
ADDER_PITCH_UM = 2.40


def make(name, cw=0.0):
    """cw >= 0  : a flat per-bit load (used for the permutation vehicles, whose
                  wire IS a single well-defined displacement).
       cw == -1 : the STRUCTURAL wire model -- every net's length read off the
                  netlist's own fan-out bit distances (veh.struct_wire).  This is
                  the right model for an adder, because a Kogge-Stone prefix cell
                  at stride s reads a net s bit positions away while a ripple
                  carry is always one pitch, and a flat load would erase exactly
                  the difference being measured."""
    struct = (cw == -1.0)
    c = 0.0 if struct else cw
    if name == "aes":
        ch = veh.aes_addroundkey(cw_per_bit=c)
    elif name == "ks8":
        ch = veh.build_adder(8, "ks", cw_per_bit=c)
    elif name == "rip8":
        ch = veh.build_adder(8, "ripple", cw_per_bit=c)
    elif name == "qrxor":
        ch = veh.qr_xor_rotate(32, 16, cw_at_mean=c)
    elif name == "ks32":
        ch = veh.build_adder(32, "ks", cw_per_bit=c)
    elif name == "rip32":
        ch = veh.build_adder(32, "ripple", cw_per_bit=c)
    else:
        raise SystemExit("unknown vehicle %s" % name)
    if struct:
        veh.apply_struct_wire(ch, ADDER_PITCH_UM, veh.WIRE_NOM)
    return ch


def static_value_gate(name):
    """G11, static half: the NETLIST's own semantics must reproduce the
    INDEPENDENT reference (AES arithmetic / integer addition).  Pure Python."""
    ch = make(name, 0.0)
    bad = []
    for (k, i), want_high in sorted(ch.reference.items()):
        got = ch.levels[k - 1][i].val
        if bool(got) != bool(want_high):
            bad.append((k, i, got, want_high))
    return dict(vehicle=name, points=len(ch.reference), mismatches=len(bad),
                first=bad[:6], PASS=(not bad),
                cells=sum(ch.n_of(k) for k in range(1, ch.nb + 1)),
                levels=ch.nb, devices=ch.census()["devices_total"])


# --------------------------------------------------------------- extraction
def col(hdr, nm):
    return hdr.index(nm.upper())


_TIDX = {}


def _tindex(rows):
    """Cache the time axis once per .prn so at() is a bisect, not a scan.

    The committed extractor scans every row for every lookup, which is fine for
    8 cells and 4 banks.  This run's AES vehicle has 384 cells and ~32000 time
    points, so a linear at() per cell is 12 million row visits.  Same answer,
    same nearest-sample rule -- just indexed."""
    key = id(rows)
    if key not in _TIDX:
        _TIDX[key] = [r[1] * 1e12 for r in rows]
    return _TIDX[key]


def at(hdr, rows, nm, tt):
    """The value of `nm` at the sample NEAREST tt -- the committed convention."""
    import bisect
    ic = col(hdr, nm)
    ts = _tindex(rows)
    j = bisect.bisect_left(ts, tt)
    cands = [k for k in (j - 1, j, j + 1) if 0 <= k < len(ts)]
    if not cands:
        return None
    best = min(cands, key=lambda k: abs(ts[k] - tt))
    return rows[best][ic]


def settle_pct(hi, v, rail):
    """The committed convention: percentage of the way to the CORRECT rail."""
    return 100.0 * ((v / rail) if hi else (1.0 - v / rail))


def guard_ok(hi, v, rail):
    return (v >= 0.50 * rail) if hi else (v <= 0.10 * rail)


def data_valid_instant(ch, hdr, rows, k, t_from, t_to, thresh=90.0):
    ir = col(hdr, "V(RAIL%d)" % k)
    io = [col(hdr, "V(%s)" % ch.out_net(k, i)) for i in range(ch.n_of(k))]
    hi = [bool(ch.levels[k - 1][i].val) for i in range(ch.n_of(k))]
    import bisect
    ts = _tindex(rows)
    start = max(0, bisect.bisect_left(ts, t_from) - 1)
    for idx in range(start, len(rows)):
        t = ts[idx]
        if t < t_from:
            continue
        if t > t_to:
            break
        r = rows[idx]
        rail = r[ir]
        if rail <= 0.05:
            continue
        ok = True
        for i in range(len(io)):
            v = r[io[i]]
            if settle_pct(hi[i], v, rail) < thresh or not guard_ok(hi[i], v, rail):
                ok = False; break
        if ok:
            return t
    return None


def extract(ch, m, T, H, dv, z, path, tag, cw, wall):
    mt = parse_mt0(path + ".mt0")
    hdr, rows = read_prn(path + ".prn")
    nb = ch.nb
    S = schedule(T, H, dv, z["tzr"], z["tzq"], nb)
    vt0 = vtank0(m, dv)
    ct = {k: m * c_bank_derived(ch, k) for k in range(1, nb + 1)}

    r = dict(_LABELS="MEASURED unless the key says DERIVED/COMPOSED/ASSUMED",
             vehicle=ch.name, tag=tag, nb=nb, m=m, T_ps=T, H=H, dv=dv,
             cw_per_bit_fF=cw, wall_s=round(wall, 1),
             n_per_level=[ch.n_of(k) for k in range(1, nb + 1)],
             devices_total=ch.census()["devices_total"],
             C_bank_fF_DERIVED={k: round(c_bank_derived(ch, k), 4)
                                for k in range(1, nb + 1)},
             C_tank_fF_DERIVED={k: round(ct[k], 4) for k in range(1, nb + 1)},
             V_tank0_DERIVED=vt0, tzr=z["tzr"], tzq=z["tzq"],
             c=S["c"], o=S["o"], rcl=S["r"], ro=S["ro"], bound=S["bound"],
             tend=S["tend"])

    # ---- rails / tanks (MEASURED)
    r["rail_at_own_boundary_V"] = {k: mt["VR%dB%d" % (k, k)] for k in range(1, nb + 1)}
    r["rail_peak_V"] = {k: mt["VR%dPK" % k] for k in range(1, nb + 1)}
    r["rail_at_own_open_V"] = {k: mt["VR%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_t0_V"] = {k: mt["VT%dZ" % k] for k in range(1, nb + 1)}
    r["tank_after_rise_V"] = {k: mt["VT%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_after_return_V"] = {k: mt["VT%dQ%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_end_V"] = {k: mt["VT%dD" % k] for k in range(1, nb + 1)}
    r["G7_level_restoring_floor_V"] = RESTORE_FLOOR
    r["G7_pass"] = all(r["rail_at_own_boundary_V"][k] > RESTORE_FLOOR
                       for k in range(1, nb + 1))
    r["G7_worst_rail_V"] = min(r["rail_at_own_boundary_V"].values())

    # ---- per-gate settling + VALUE check at each bank's own boundary
    st, sep, vfail = {}, {}, []
    for k in range(1, nb + 1):
        rk = r["rail_at_own_boundary_V"][k]
        sk, his, los = {}, [], []
        for i in range(ch.n_of(k)):
            v = mt["O%d_%dB" % (k, i)]
            hi = bool(ch.levels[k - 1][i].val)
            sk["o%d" % i] = settle_pct(hi, v, rk) if rk > 0 else None
            (his if hi else los).append(v)
            if rk > 0 and not guard_ok(hi, v, rk):
                vfail.append([k, i, ch.levels[k - 1][i].name, round(v, 6),
                              round(rk, 6), "want HIGH" if hi else "want LOW"])
        st[k] = sk
        if his and los:
            sep[k] = dict(min_HIGH_V=min(his), max_LOW_V=max(los),
                          separation_mV=1000.0 * (min(his) - max(los)))
        else:
            sep[k] = dict(min_HIGH_V=(min(his) if his else None),
                          max_LOW_V=(max(los) if los else None),
                          separation_mV=None,
                          note="level is all-HIGH or all-LOW; separation undefined")
    r["settling_worst_per_bank_pct"] = {k: (min(v for v in st[k].values()
                                                if v is not None)
                                            if st[k] else None)
                                        for k in st}
    wg = [(r["settling_worst_per_bank_pct"][k], k) for k in st
          if r["settling_worst_per_bank_pct"][k] is not None]
    r["worst_gate_pct"] = min(wg)[0] if wg else None
    r["worst_gate_bank"] = min(wg)[1] if wg else None
    r["separation_by_depth"] = sep
    sm = [sep[k]["separation_mV"] for k in sep if sep[k]["separation_mV"] is not None]
    r["separation_min_mV"] = min(sm) if sm else None
    r["G8_pass"] = bool(sm) and min(sm) >= SIGMA_FLOOR_MV
    r["A1_settling_pass_90"] = (r["worst_gate_pct"] or 0) >= 90.0
    r["G11_value_fail_count"] = len(vfail)
    r["G11_value_fail_list"] = vfail[:20]
    r["G11_value_pass"] = (len(vfail) == 0)

    # ---- the INDEPENDENT reference at the output level
    orf = []
    for (k, i), want_high in sorted(ch.reference.items()):
        rk = r["rail_at_own_boundary_V"][k]
        v = mt["O%d_%dB" % (k, i)]
        if rk > 0 and not guard_ok(bool(want_high), v, rk):
            orf.append([k, i, round(v, 6), round(rk, 6), bool(want_high)])
    r["G11_reference_points"] = len(ch.reference)
    r["G11_reference_fail_count"] = len(orf)
    r["G11_reference_fail_list"] = orf[:20]
    r["G11_reference_pass"] = (len(orf) == 0)

    # ---- fcrit S3 functional criterion
    tc = {}
    for k in range(1, nb + 1):
        tc[k] = S["o"][k]          # the bank commits when its charge delivery ends
    fc = dict(_criterion="qal/fcrit S3: sender vs the RECEIVER's MEASURED trip at "
                         "the RECEIVER's delivered rail at the instant the RECEIVER "
                         "commits (its rise ZCS)",
              noise_budget_mV=1000.0 * NB_3SIGMA_V, per_bank={})
    nfail_tot, ntot = 0, 0
    for k in range(1, nb + 1):
        rx = k + 1 if k + 1 <= nb else k
        generous = (rx == k)
        trx = S["bound"][k] if generous else tc[rx]
        Rrx = at(hdr, rows, "V(RAIL%d)" % rx, trx)
        vtrip, extrap = TRIP(Rrx) if Rrx and Rrx > 0 else (None, True)
        nf, worst = 0, None
        for i in range(ch.n_of(k)):
            v = at(hdr, rows, "V(%s)" % ch.out_net(k, i), trx)
            hi = bool(ch.levels[k - 1][i].val)
            if vtrip is None:
                nf += 1; continue
            marg = (v - vtrip) if hi else (vtrip - v)
            if worst is None or marg < worst[0]:
                worst = (marg, i, ch.levels[k - 1][i].name)
            if marg < NB_3SIGMA_V:
                nf += 1
        fc["per_bank"][k] = dict(receiver_bank=rx, generous=generous,
                                 t_commit_ps=trx,
                                 rail_receiver_V=Rrx,
                                 trip_V=vtrip, trip_extrapolated=extrap,
                                 n=ch.n_of(k), n_fail=nf,
                                 worst_margin_mV=(1000.0 * worst[0]
                                                  if worst else None),
                                 worst_cell=(worst[2] if worst else None))
        nfail_tot += nf; ntot += ch.n_of(k)
    fc["n_total"], fc["n_fail_total"] = ntot, nfail_tot
    fc["score"] = "%d/%d" % (ntot - nfail_tot, ntot)
    r["G6_functional"] = fc
    r["G6_pass"] = (nfail_tot == 0)

    # ---- hop times (MEASURED zeros) and the LEVEL TIME, end to end
    r["t_hop_rise_ps"] = {k: z["tzr"][k - 1] for k in range(1, nb + 1)}
    r["t_hop_return_ps"] = {k: z["tzq"][k - 1] for k in range(1, nb + 1)}
    dv90, dvfn = {}, {}
    for k in range(1, nb + 1):
        lo = S["c"][k]
        hi = min(S["r"][k], S["tend"])
        dv90[k] = data_valid_instant(ch, hdr, rows, k, lo, hi, 90.0)
        dvfn[k] = data_valid_instant(ch, hdr, rows, k, lo, hi, 50.0)
    r["first_valid90_instant_ps"] = dv90
    r["t_settle_from_own_rail_start_ps"] = {
        k: (dv90[k] - S["c"][k]) if dv90[k] else None for k in dv90}
    # LEVEL TIME, MEASURED END TO END: the interval between consecutive levels
    # becoming valid.  Never composed from per-gate delays.
    r["LEVEL_TIME_measured_ps"] = {
        k: ((dv90[k] - dv90[k - 1]) if (dv90.get(k) and dv90.get(k - 1)) else None)
        for k in range(2, nb + 1)}
    lt = [v for v in r["LEVEL_TIME_measured_ps"].values() if v is not None]
    r["LEVEL_TIME_measured_max_ps"] = max(lt) if lt else None
    r["LEVEL_TIME_measured_mean_ps"] = (sum(lt) / len(lt)) if lt else None
    r["LEVEL_TIME_scheduled_beat_ps"] = T
    r["OP_TIME_end_to_end_MEASURED_ps"] = (
        (dv90[nb] - dv90[1]) if (dv90.get(nb) and dv90.get(1)) else None)

    # ---- ZCS gate
    r["IZ_uA"] = {k: mt["IZ%d" % k] * 1e6 for k in range(1, nb + 1)}
    r["IZQ_uA"] = {k: mt["IZQ%d" % k] * 1e6 for k in range(1, nb + 1)}
    r["IPK_uA"] = {k: mt["IPK%d" % k] * 1e6 for k in range(1, nb + 1)}
    r["G2_pass"] = all(abs(r["IZ_uA"][k]) <= 1.0 and abs(r["IZQ_uA"][k]) <= 1.0
                       for k in range(1, nb + 1))
    r["G2_worst_uA"] = max(max(abs(r["IZ_uA"][k]), abs(r["IZQ_uA"][k]))
                           for k in range(1, nb + 1))

    # ---- energy.  HEADLINE is convention-free: 1/2 C_t (V0^2 - V_end^2).
    def g(tag_, ck):
        a = mt.get("%s_%s" % (tag_.upper(), ck))
        z0 = mt.get("%s_Z" % tag_.upper())
        return None if (a is None or z0 is None) else (a - z0)

    en, tot = {}, 0.0
    for k in range(1, nb + 1):
        c = ct[k] * 1e-15
        v0, ve = r["tank_t0_V"][k], r["tank_end_V"][k]
        vr = r["tank_after_rise_V"][k]
        vq = r["tank_after_return_V"][k]
        e_lost = 0.5 * c * (v0 ** 2 - ve ** 2) * 1e15
        e_out = 0.5 * c * (v0 ** 2 - vr ** 2) * 1e15
        e_back = 0.5 * c * (vq ** 2 - vr ** 2) * 1e15
        ea = g("ea%d" % k, "O%d" % k)
        eb = g("eb%d" % k, "O%d" % k)
        er = g("er%d" % k, "O%d" % k)
        esw = g("esw%d" % k, "O%d" % k)
        eo = None if ea is None else -ea * 1e15
        ei = None if eb is None else -eb * 1e15
        erj = None if er is None else er * 1e15
        esb = (None if (eo is None or ei is None or erj is None)
               else eo - ei - erj)
        en[k] = dict(
            E_tank_lost_fJ_CONVENTION_FREE=e_lost,
            E_out_of_tank_rise_fJ=e_out,
            E_back_into_tank_return_fJ=e_back,
            recycle_fraction_pct=(100.0 * e_back / e_out) if e_out else None,
            E_out_of_tank_rise_integrator_fJ=eo,
            E_into_rail_rise_integrator_fJ=ei,
            E_seriesR_rise_fJ=erj,
            E_switchblock_rise_fJ=esb,
            path_identity_fJ=(None if esb is None else eo - esb - erj - ei),
            n_cells=ch.n_of(k))
        tot += e_lost
    r["energy_per_bank"] = en
    r["E_tank_lost_total_fJ_CONVENTION_FREE"] = tot
    ncell = sum(ch.n_of(k) for k in range(1, nb + 1))
    r["cells_total"] = ncell
    r["E_per_gate_fJ"] = tot / ncell if ncell else None
    # path identity gate
    pid = []
    for k in range(1, nb + 1):
        eo = en[k]["E_out_of_tank_rise_integrator_fJ"]
        esb = en[k]["E_switchblock_rise_fJ"]
        erj = en[k]["E_seriesR_rise_fJ"]
        ei = en[k]["E_into_rail_rise_integrator_fJ"]
        if None in (eo, esb, erj, ei) or not eo:
            pid.append(None); continue
        pid.append(100.0 * abs(eo - esb - erj - ei) / abs(eo))
    r["G3_path_identity_pct"] = pid
    r["G3_pass"] = all(p is not None and p <= 1.0 for p in pid)

    r["E_gate_drive_idealPWL_total_fJ"] = (g("egt", "D") or 0) * 1e15
    r["E_wellrail_total_fJ"] = (g("ehi", "D") or 0) * 1e15
    r["E_held_sources_fJ"] = (g("ei1", "D") or 0) * 1e15 if mt.get("EI1_D") else None

    r["PASS"] = bool(r["G2_pass"] and r["G3_pass"] and r["G6_pass"] and
                     r["G7_pass"] and r["G11_value_pass"] and
                     r["G11_reference_pass"])
    r["GATES"] = {g_: r.get(g_ + "_pass") for g_ in
                  ("G2", "G3", "G6", "G7", "G8", "G11_value", "G11_reference")}
    return r


# ------------------------------------------------------ the CMOS comparator
def cmos_row(ch, vdd, T, H, dv, tag, wire=True, tstep=200.0, tail=TAIL):
    lines, meta = cmos_deck(ch, vdd, T, H, dv, tstep=tstep, tail=tail, wire=wire)
    fn = "m_%s.cir" % tag
    p, msg, wall = xrun(fn, lines)
    print("  cmos %s" % msg, flush=True)
    if p is None:
        return None
    mt = parse_mt0(p + ".mt0")
    hdr, rows = read_prn(p + ".prn")
    z0 = mt.get("EVDD_Z", 0.0)
    e = (mt["EVDD_D"] - z0) * 1e15
    q0 = mt.get("QVDD_Z", 0.0)
    q = (mt["QVDD_D"] - q0)
    nb = ch.nb
    ncell = sum(ch.n_of(k) for k in range(1, nb + 1))
    # value check at the end
    bad = 0
    for k in range(1, nb + 1):
        for i in range(ch.n_of(k)):
            v = mt["O%d_%dE" % (k, i)]
            hi = bool(ch.levels[k - 1][i].val)
            if not guard_ok(hi, v, vdd):
                bad += 1
    # LEVEL TIME, measured the same way: when does each level become valid
    ir = None
    dv90 = {}
    for k in range(1, nb + 1):
        io = [col(hdr, "V(%s)" % ch.out_net(k, i)) for i in range(ch.n_of(k))]
        hi = [bool(ch.levels[k - 1][i].val) for i in range(ch.n_of(k))]
        got = None
        for rr in rows:
            t = rr[1] * 1e12
            if t < tstep:
                continue
            ok = True
            for j in range(len(io)):
                v = rr[io[j]]
                if settle_pct(hi[j], v, vdd) < 90.0 or not guard_ok(hi[j], v, vdd):
                    ok = False; break
            if ok:
                got = t; break
        dv90[k] = got
    lt = {k: ((dv90[k] - dv90[k - 1]) if (dv90.get(k) and dv90.get(k - 1)) else None)
          for k in range(2, nb + 1)}
    ltv = [v for v in lt.values() if v is not None]
    return dict(_LABELS="MEASURED", tag=tag, vdd_V=vdd,
                note="G9: vdd is the QAL row's OWN MEASURED delivered rail peak",
                wire=wire, wall_s=None,
                E_supply_fJ=e, Q_supply_C=q,
                E_supply_crosscheck_VQ_fJ=vdd * q * 1e15,
                E_per_gate_fJ=e / ncell if ncell else None,
                cells_total=ncell, value_fail_count=bad,
                value_pass=(bad == 0),
                first_valid90_instant_ps=dv90,
                t_settle_level1_ps=(dv90[1] - tstep) if dv90.get(1) else None,
                LEVEL_TIME_measured_ps=lt,
                LEVEL_TIME_measured_max_ps=max(ltv) if ltv else None,
                OP_TIME_end_to_end_MEASURED_ps=((dv90[nb] - tstep)
                                                if dv90.get(nb) else None))


# --------------------------------------------------------------------- main
def do_row(name, T, cw, m=10.0, H=4, dv=1.65, tagx="", mstep=None):
    ch = make(name, cw)
    tag = "%s_T%g_%s%s%s" % (name, T,
                             "cwstruct" if cw == -1.0 else "cw%.0f" % (cw * 1000),
                             ("_ms%g" % mstep) if mstep else "", tagx)
    print("== %s  nb=%d cells=%d devices=%d  T=%g cw=%g" %
          (tag, ch.nb, sum(ch.n_of(k) for k in range(1, ch.nb + 1)),
           ch.census()["devices_total"], T, cw), flush=True)
    zf = os.path.join(HERE, "z_%s.json" % tag)
    if os.path.exists(zf):
        z = json.load(open(zf))
        print("  reused zeros %s" % os.path.basename(zf), flush=True)
    else:
        z = probe_chain(ch, m, T, H, dv, tag, probe_span=3.6, mstep=mstep)
        if z is None:
            return dict(tag=tag, status="PROBE_FAIL")
        open(zf, "w").write(json.dumps(z, indent=1))
    lines, S = deck(ch, m, T, H, dv, tzr=z["tzr"], tzq=z["tzq"],
                    ct_mode="matched", mstep=mstep)
    fn = "c_%s.cir" % tag
    p, msg, wall = xrun(fn, lines)
    print("  row %s" % msg, flush=True)
    if p is None:
        return dict(tag=tag, status="ROW_FAIL", msg=msg)
    r = extract(ch, m, T, H, dv, z, p, tag, cw, wall)
    r["mstep_ps"] = mstep if mstep else 0.25
    r["status"] = "OK"
    open(os.path.join(HERE, "ROW_%s.json" % tag), "w").write(json.dumps(r, indent=1))
    print("  -> PASS=%s worst_gate=%.2f%% fcrit=%s rail_min=%.4f "
          "E_tot=%.1f fJ  E/gate=%.3f fJ  lvl_time=%s" %
          (r["PASS"], r["worst_gate_pct"] or -1, r["G6_functional"]["score"],
           r["G7_worst_rail_V"], r["E_tank_lost_total_fJ_CONVENTION_FREE"],
           r["E_per_gate_fJ"], r["LEVEL_TIME_measured_max_ps"]), flush=True)
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "static":
        out = {}
        for nm in ("aes", "qrxor", "ks8", "rip8", "ks32", "rip32"):
            out[nm] = static_value_gate(nm)
            d = out[nm]
            print("  %-6s levels=%2d cells=%5d devices=%6d  refpoints=%3d  "
                  "mismatches=%d  %s" % (nm, d["levels"], d["cells"],
                                         d["devices"], d["points"],
                                         d["mismatches"],
                                         "PASS" if d["PASS"] else "FAIL"))
        open(os.path.join(HERE, "STATIC_VALUE_GATE.json"), "w").write(
            json.dumps(out, indent=1))
        sys.exit(0 if all(v["PASS"] for v in out.values()) else 1)
    if a and a[0] == "row":
        name, T, cw = a[1], float(a[2]), float(a[3])
        ms = float(a[4]) if len(a) > 4 else None
        r = do_row(name, T, cw, mstep=ms)
        sys.exit(0 if r.get("status") == "OK" else 1)
    if a and a[0] == "cmos":
        name, vdd, cw = a[1], float(a[2]), float(a[3])
        ch = make(name, cw)
        tag = "%s_cw%.0f_vdd%.0f" % (name, cw * 1000, vdd * 10000)
        r = cmos_row(ch, vdd, 150.0, 4, 1.65, tag)
        if r:
            open(os.path.join(HERE, "CMOS_%s.json" % tag), "w").write(
                json.dumps(r, indent=1))
            print("  -> E=%.3f fJ  E/gate=%.4f fJ  VQ-crosscheck=%.3f fJ  "
                  "value_pass=%s  op_time=%s ps" %
                  (r["E_supply_fJ"], r["E_per_gate_fJ"],
                   r["E_supply_crosscheck_VQ_fJ"], r["value_pass"],
                   r["OP_TIME_end_to_end_MEASURED_ps"]))
        sys.exit(0 if r else 1)
    print(__doc__)


# ------------------------------------------------- the CMOS-NATIVE comparator
def cmos_native_row(which, vdd, cw=0.0, dv=1.65, wire=True):
    """The same FUNCTION built the way CMOS would build it: no forwarding cells.
    AMENDMENT B10: constant supply, inputs cycled, so E = vdd * dQ EXACTLY."""
    import cmosnat
    if which == "aes":
        F = cmosnat.cmos_addroundkey(cw_per_bit=cw)
    elif which == "qrxor":
        F = cmosnat.cmos_qr_xor(32, 16, cw_at_mean=cw)
    elif which in ("ks8", "rip8", "ks32", "rip32"):
        W = 8 if which.endswith("8") else 32
        form = "ks" if which.startswith("ks") else "ripple"
        F = cmosnat.cmos_adder(W, form, cw_per_bit=cw)
    else:
        raise SystemExit("no cmos-native form for %s" % which)
    if not F.reference.get("MATCH"):
        raise SystemExit("%s: CMOS-native reference MISMATCH -- refusing to run"
                         % which)
    lines, meta = cmosnat.flat_deck(F, vdd, wire=wire, dv=dv)
    tag = "nat_%s_cw%.0f_vdd%.0f" % (which, cw * 1000, vdd * 10000)
    fn = "n_%s.cir" % tag
    p, msg, wall = xrun(fn, lines)
    print("  cmos-native %s" % msg, flush=True)
    if p is None:
        return None
    mt = parse_mt0(p + ".mt0")
    hdr, rows = read_prn(p + ".prn")
    c = F.census()
    # HEADLINE, convention-free: the supply is CONSTANT, so the energy it
    # delivered over the full input cycle is exactly vdd * dQ.
    q_full = mt["QVDD_D"] - mt["QVDD_Z"]
    q_half = mt["QVDD_A"] - mt["QVDD_Z"]
    e_full = vdd * q_full * 1e15
    bad = 0
    for o in F.outputs:
        v = mt["M_%s" % o.upper()]
        if not guard_ok(bool(F.val[o]), v, vdd):
            bad += 1
    # PROPAGATION DELAY, measured on the FIRST input edge against the
    # COMPLEMENT-state output values.  Measuring after the RETURN edge is
    # meaningless: the outputs are already near their final state before it
    # arrives, and the first version of this harness duly reported 3.29 ps for a
    # 32-cell XOR level, which is not a propagation delay but an artefact.
    comp = F.eval_toggled(getattr(F, "toggle", set()))
    act = F.activity(getattr(F, "toggle", set()))
    io = [col(hdr, "V(%s)" % o) for o in F.outputs]
    hic = [bool(comp[o]) for o in F.outputs]
    got = None
    for rr in rows:
        t = rr[1] * 1e12
        if t < meta["t1"] + EDGE:
            continue
        if t > meta["t2"]:
            break
        ok = True
        for j2 in range(len(io)):
            v = rr[io[j2]]
            if settle_pct(hic[j2], v, vdd) < 90.0 or not guard_ok(hic[j2], v, vdd):
                ok = False; break
        if ok:
            got = t; break
    return dict(_LABELS="MEASURED", tag=tag, which=which, vdd_V=vdd,
                form="CMOS-NATIVE (no forwarding cells)",
                stimulus="B10: constant supply, inputs cycled final->complement->final",
                cells=c["cells"], devices=c["devices"],
                gate_depth_DERIVED=c["gate_depth_DERIVED"],
                wire_total_fF=c["wire_total_fF"], cw_per_bit_fF=cw,
                Q_full_cycle_C=q_full, Q_half_cycle_C=q_half,
                E_full_cycle_fJ_CONVENTION_FREE=e_full,
                E_per_gate_fJ=e_full / c["cells"],
                C_switched_fF_DERIVED=q_full / vdd * 1e15,
                activity=act,
                value_fail_count=bad, value_pass=(bad == 0),
                t_valid_ps=got,
                DELAY_end_to_end_MEASURED_ps=((got - (meta["t1"] + EDGE))
                                              if got else None),
                _delay_note=("propagation delay on the FIRST input edge, "
                             "measured to the COMPLEMENT-state values by the "
                             "same >=90%-settled + pattern-correct rule the QAL "
                             "side uses"),
                wall_s=round(wall, 1))


if len(sys.argv) > 1 and sys.argv[1] == "nat":
    which, vdd, cw = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    rr = cmos_native_row(which, vdd, cw)
    if rr:
        open(os.path.join(HERE, "NAT_%s.json" % rr["tag"]), "w").write(
            json.dumps(rr, indent=1))
        print("  -> cells=%d dev=%d depth=%d  E_cycle=%.3f fJ  E/gate=%.4f fJ  "
              "C_sw=%.1f fF  value=%s  delay=%s ps"
              % (rr["cells"], rr["devices"], rr["gate_depth_DERIVED"],
                 rr["E_full_cycle_fJ_CONVENTION_FREE"], rr["E_per_gate_fJ"],
                 rr["C_switched_fF_DERIVED"], rr["value_pass"],
                 rr["DELAY_end_to_end_MEASURED_ps"]))
    sys.exit(0 if rr else 1)


# -------------------------------- the SAME-NETLIST CMOS twin (gate G9 strict)
def cmos_twin_row(name, vdd, cw=0.0, dv=1.65, wire=True):
    """The IDENTICAL netlist -- forwarding cells and all -- on an ideal supply
    set to the QAL row's own MEASURED delivered rail peak.

    Only the technology differs, so this isolates the technology at a fixed
    netlist.  It is produced by cmosnat.flat_from_chain() and then by the SAME
    flat_deck() as the CMOS-native form, so the two CMOS variants are generated
    identically and differ only in which netlist they carry.  The gap between
    them IS the forwarding tax, measured.
    """
    import cmosnat
    ch = make(name, cw)
    F = cmosnat.flat_from_chain(ch)
    if not F.chain_agreement["PASS"]:
        raise SystemExit("%s: flat netlist disagrees with the chain on %d cells"
                         % (name, F.chain_agreement["mismatches"]))
    # toggle the same operand the CMOS-native form toggles
    pref = {"aes": "s_rk", "qrxor": "s_a", "ks8": "s_b", "rip8": "s_b",
            "ks32": "s_b", "rip32": "s_b"}[name]
    F.toggle = set(n for n in F.sources if n.startswith(pref))
    if not F.toggle:
        raise SystemExit("%s: empty toggle set" % name)
    act = F.activity(F.toggle)
    lines, meta = cmosnat.flat_deck(F, vdd, wire=wire, dv=dv)
    tag = "twin_%s_cw%s_vdd%.0f" % (name, ("struct" if cw == -1.0
                                           else "%.0f" % (cw * 1000)), vdd * 10000)
    p, msg, wall = xrun("t_%s.cir" % tag, lines)
    print("  cmos twin %s" % msg, flush=True)
    if p is None:
        return None
    mt = parse_mt0(p + ".mt0")
    hdr, rows = read_prn(p + ".prn")
    c = F.census()
    q_full = mt["QVDD_D"] - mt["QVDD_Z"]
    e_full = vdd * q_full * 1e15
    bad = 0
    for o in F.outputs:
        if not guard_ok(bool(F.val[o]), mt["M_%s" % o.upper()], vdd):
            bad += 1
    comp = F.eval_toggled(F.toggle)
    io = [col(hdr, "V(%s)" % o) for o in F.outputs]
    hic = [bool(comp[o]) for o in F.outputs]
    got = None
    for rr in rows:
        t = rr[1] * 1e12
        if t < meta["t1"] + EDGE or t > meta["t2"]:
            continue
        ok = True
        for j2 in range(len(io)):
            v = rr[io[j2]]
            if settle_pct(hic[j2], v, vdd) < 90.0 or not guard_ok(hic[j2], v, vdd):
                ok = False; break
        if ok:
            got = t; break
    return dict(_LABELS="MEASURED", tag=tag, which=name, vdd_V=vdd,
                form="SAME-NETLIST CMOS TWIN (gate G9 strict; forwarding cells kept)",
                stimulus="B10: constant supply, one operand cycled",
                cells=c["cells"], devices=c["devices"],
                gate_depth_DERIVED=c["gate_depth_DERIVED"],
                wire_total_fF=c["wire_total_fF"], cw_per_bit_fF=cw,
                chain_agreement=F.chain_agreement, activity=act,
                Q_full_cycle_C=q_full,
                E_full_cycle_fJ_CONVENTION_FREE=e_full,
                E_per_gate_fJ=e_full / c["cells"],
                C_switched_fF_DERIVED=q_full / vdd * 1e15,
                value_fail_count=bad, value_pass=(bad == 0),
                DELAY_end_to_end_MEASURED_ps=((got - (meta["t1"] + EDGE))
                                              if got else None),
                wall_s=round(wall, 1))


if len(sys.argv) > 1 and sys.argv[1] == "twin":
    nm, vdd, cw = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    rr = cmos_twin_row(nm, vdd, cw)
    if rr:
        open(os.path.join(HERE, "TWIN_%s.json" % rr["tag"]), "w").write(
            json.dumps(rr, indent=1))
        print("  -> cells=%d dev=%d  E_cycle=%.3f fJ  E/gate=%.4f fJ  C_sw=%.1f fF"
              "  act=%.3f  value=%s  delay=%s ps"
              % (rr["cells"], rr["devices"], rr["E_full_cycle_fJ_CONVENTION_FREE"],
                 rr["E_per_gate_fJ"], rr["C_switched_fF_DERIVED"],
                 rr["activity"]["activity"], rr["value_pass"],
                 rr["DELAY_end_to_end_MEASURED_ps"]))
    sys.exit(0 if rr else 1)
