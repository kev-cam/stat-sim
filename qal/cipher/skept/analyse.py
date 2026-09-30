#!/usr/bin/env python3
"""qal/cipher/p2/analyse.py -- assemble every measured row into the Phase 2
result tables and score the pre-registered expectations.

Nothing here simulates.  Every input is a ROW_*.json or CMOS_*.json written by
run.py, or a structural census written by veh.py / cmosnat.py.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(pat):
    out = {}
    for f in sorted(glob.glob(os.path.join(HERE, pat))):
        try:
            out[os.path.basename(f)] = json.load(open(f))
        except Exception as e:
            out[os.path.basename(f)] = {"_load_error": str(e)}
    return out


def qal_rows():
    return {k: v for k, v in load("ROW_*.json").items()
            if v.get("status") == "OK"}


def cmos_rows():
    return load("CMOS_*.json")


def pair(qrow, crow):
    """The QAL/CMOS comparison for one vehicle at one wire load.

    ENERGY.  QAL headline is the convention-free tank loss summed over banks,
    which is the energy the tanks actually gave up in the first cycle (Phase 1
    A4: rails do not return to 0, so this is a FIRST-CYCLE energy on both
    sides).  CMOS headline is the supply integral over one settle.  Both are
    divided by the same cell count.

    SPEED.  Both sides' level time is MEASURED by the same rule: the first
    instant at which every cell of a level is >= 90 % settled to its correct
    rail AND pattern-correct.  Neither is composed from per-gate delays.
    """
    if not qrow or not crow:
        return None
    eq = qrow["E_tank_lost_total_fJ_CONVENTION_FREE"]
    ec = crow["E_supply_fJ"]
    d = dict(
        vehicle=qrow["vehicle"], tag=qrow["tag"],
        cw_per_bit_fF=qrow.get("cw_per_bit_fF"),
        cells=qrow["cells_total"], levels=qrow["nb"],
        QAL_E_total_fJ=round(eq, 4), CMOS_E_total_fJ=round(ec, 4),
        QAL_E_per_gate_fJ=round(qrow["E_per_gate_fJ"], 4),
        CMOS_E_per_gate_fJ=round(crow["E_per_gate_fJ"], 4),
        ENERGY_ratio_CMOS_over_QAL=round(ec / eq, 4) if eq else None,
        _energy_reading=("> 1 means QAL costs LESS energy than CMOS at the "
                         "same measured swing; < 1 means QAL costs MORE"),
        CMOS_vdd_V=crow["vdd_V"],
        QAL_rail_peak_V=qrow["rail_peak_V"],
        QAL_level_time_max_ps=qrow.get("LEVEL_TIME_measured_max_ps"),
        CMOS_level_time_max_ps=crow.get("LEVEL_TIME_measured_max_ps"),
        QAL_op_time_ps=qrow.get("OP_TIME_end_to_end_MEASURED_ps"),
        CMOS_op_time_ps=crow.get("OP_TIME_end_to_end_MEASURED_ps"),
        QAL_beat_ps=qrow["T_ps"],
        QAL_gates=qrow.get("GATES"), QAL_PASS=qrow.get("PASS"),
        CMOS_value_pass=crow.get("value_pass"),
        QAL_worst_gate_pct=qrow.get("worst_gate_pct"),
        QAL_fcrit=qrow["G6_functional"]["score"],
        QAL_rail_min_V=qrow.get("G7_worst_rail_V"))
    # SPEED ratio: a QAL level costs a whole beat because the rail must be
    # raised and returned; a CMOS level costs a gate delay.  The honest speed
    # comparison is the OP time, measured end to end on both sides.
    if d["QAL_op_time_ps"] and d["CMOS_op_time_ps"]:
        d["SPEED_ratio_QAL_over_CMOS"] = round(
            d["QAL_op_time_ps"] / d["CMOS_op_time_ps"], 4)
        d["_speed_reading"] = ("> 1 means QAL is SLOWER by that factor")
    # The QAL initiation interval is the beat, not the settle: a new operand
    # cannot enter until the rail has returned.  Reported separately.
    d["QAL_initiation_interval_ps"] = qrow["T_ps"] * (1 + qrow["H"])
    return d


def summarise():
    Q, C = qal_rows(), cmos_rows()
    out = dict(_what="qal/cipher/p2 PHASE 2 results",
               n_qal_rows=len(Q), n_cmos_rows=len(C))
    out["qal_rows"] = {}
    for k, v in Q.items():
        out["qal_rows"][v["tag"]] = dict(
            vehicle=v["vehicle"], levels=v["nb"], cells=v["cells_total"],
            devices=v["devices_total"], T_ps=v["T_ps"],
            cw_per_bit_fF=v.get("cw_per_bit_fF"),
            PASS=v["PASS"], GATES=v["GATES"],
            worst_gate_pct=v["worst_gate_pct"],
            fcrit=v["G6_functional"]["score"],
            rail_min_V=v["G7_worst_rail_V"],
            separation_min_mV=v["separation_min_mV"],
            E_total_fJ=v["E_tank_lost_total_fJ_CONVENTION_FREE"],
            E_per_gate_fJ=v["E_per_gate_fJ"],
            level_time_max_ps=v.get("LEVEL_TIME_measured_max_ps"),
            op_time_ps=v.get("OP_TIME_end_to_end_MEASURED_ps"),
            G2_worst_uA=v["G2_worst_uA"],
            G3_path_identity_pct=v["G3_path_identity_pct"],
            wall_s=v["wall_s"])
    out["cmos_rows"] = {v.get("tag", k): dict(
        vdd_V=v.get("vdd_V"), E_fJ=v.get("E_supply_fJ"),
        E_per_gate_fJ=v.get("E_per_gate_fJ"),
        VQ_crosscheck_fJ=v.get("E_supply_crosscheck_VQ_fJ"),
        value_pass=v.get("value_pass"),
        op_time_ps=v.get("OP_TIME_end_to_end_MEASURED_ps"),
        level_time_max_ps=v.get("LEVEL_TIME_measured_max_ps"))
        for k, v in C.items()}
    return out


def structural():
    """Everything that is a NETLIST FACT rather than a measurement: cell counts,
    level counts, forwarding taxes, and the two technologies' forms of the same
    function.  No simulation anywhere in this function."""
    sys.path.insert(0, HERE)
    import veh, cmosnat
    out = {}
    for W in (8, 32):
        out["adders_w%d" % W] = cmosnat.structural_table(W)
    qr = {}
    for adder in ("ks", "ripple"):
        ch = veh.qr_full(32, adder)
        qr["qal_" + adder] = dict(ch.qr)
        qr["qal_" + adder]["RFC8439_vector"] = ch.vector
        F = cmosnat.cmos_adder(32, adder)
        c = F.census()
        qr["cmos_" + adder] = dict(
            cells=4 * c["cells"] + 4 * 32,
            devices=4 * c["devices"] + 4 * 32 * 10,
            gate_depth_DERIVED=4 * (c["gate_depth_DERIVED"] + 1),
            note="DERIVED: 4 x the CMOS-native adder + 4 x 32 xor2; the rotate is "
                 "wiring; NO forwarding cells anywhere")
    for adder in ("ks", "ripple"):
        q, c = qr["qal_" + adder], qr["cmos_" + adder]
        qr["ratio_" + adder] = dict(
            cells_QAL_over_CMOS=round(q["cells"] / float(c["cells"]), 3),
            devices_QAL_over_CMOS=round(q["devices"] / float(c["devices"]), 3),
            QAL_levels=q["levels"] - 1,
            CMOS_gate_depth=c["gate_depth_DERIVED"])
    qr["THE_INVERSION"] = dict(
        _what="the adder form that wins is NOT the same in the two technologies",
        QAL_ripple_over_ks_cells=round(qr["qal_ripple"]["cells"] /
                                       float(qr["qal_ks"]["cells"]), 3),
        QAL_ripple_over_ks_levels=round((qr["qal_ripple"]["levels"] - 1) /
                                        float(qr["qal_ks"]["levels"] - 1), 3),
        CMOS_ripple_over_ks_cells=round(qr["cmos_ripple"]["cells"] /
                                        float(qr["cmos_ks"]["cells"]), 3),
        CMOS_ripple_over_ks_devices=round(qr["cmos_ripple"]["devices"] /
                                          float(qr["cmos_ks"]["devices"]), 3))
    out["quarter_round"] = qr
    return out


def verdict():
    """Pair every QAL row with its two CMOS comparators and state, per vehicle,
    whether QAL is ahead on energy, on speed, or on neither.

    ENERGY.  QAL = the convention-free tank loss summed over banks for ONE beat
    (raise + return).  CMOS = vdd * dQ over one full input cycle, vdd set to the
    QAL row's own measured rail peak (gate G9).  Both are one complete
    charge-and-discharge of the same datapath.  Ratio > 1 means QAL costs less.

    SPEED.  QAL = the MEASURED end-to-end time for the last level to become
    valid, plus the initiation interval it implies.  CMOS = the MEASURED
    propagation delay of the identical function.  Ratio > 1 means QAL is slower.

    ACTIVITY.  QAL's energy is activity-independent (the rail rises whatever the
    data does); CMOS's scales with activity.  The CMOS rows are measured at the
    activity a toggled operand word produces, which is the worst case for CMOS
    and therefore conservative for QAL.  Reported, not hidden.
    """
    Q = qal_rows()
    T = load("TWIN_*.json")
    N = load("NAT_*.json")
    byveh = {}
    for k, v in Q.items():
        byveh.setdefault(v["vehicle"], []).append(v)
    out = {}
    for f, t in sorted(T.items()):
        out.setdefault(t["which"], {}).setdefault("twin", []).append(t)
    for f, n in sorted(N.items()):
        out.setdefault(n["which"], {}).setdefault("nat", []).append(n)
    res = {}
    for k, v in Q.items():
        nm = v["tag"]
        d = dict(vehicle=v["vehicle"], tag=nm, levels=v["nb"],
                 cells=v["cells_total"], devices=v["devices_total"],
                 cw_per_bit_fF=v.get("cw_per_bit_fF"), beat_ps=v["T_ps"],
                 QAL_PASS=v["PASS"], QAL_GATES=v["GATES"],
                 QAL_fcrit=v["G6_functional"]["score"],
                 QAL_worst_gate_pct=v["worst_gate_pct"],
                 QAL_rail_peak_V=v["rail_peak_V"],
                 QAL_rail_min_boundary_V=v["G7_worst_rail_V"],
                 QAL_E_beat_fJ=v["E_tank_lost_total_fJ_CONVENTION_FREE"],
                 QAL_E_per_gate_fJ=v["E_per_gate_fJ"],
                 QAL_level_time_max_ps=v.get("LEVEL_TIME_measured_max_ps"),
                 QAL_op_time_ps=v.get("OP_TIME_end_to_end_MEASURED_ps"),
                 QAL_initiation_interval_ps=v["T_ps"] * (1 + v["H"]))
        res[nm] = d
    return dict(qal=res, twins={k: v for k, v in T.items()},
                natives={k: v for k, v in N.items()})


def compare(qtag, ctab):
    pass


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "struct":
        d = structural()
        json.dump(d, open(os.path.join(HERE, "STRUCTURAL.json"), "w"), indent=1)
        print(json.dumps(d, indent=1))
    elif a and a[0] == "verdict":
        d = verdict()
        json.dump(d, open(os.path.join(HERE, "VERDICT.json"), "w"), indent=1)
        print(json.dumps(d, indent=1))
    else:
        d = summarise()
        json.dump(d, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
        print(json.dumps(d, indent=1))


# --------------------------------------------------- COMPOSED adder estimates
def composed_adder_energy():
    """If the 8-bit ripple row does not complete, its energy is COMPOSED from a
    MEASURED per-cell energy and its own EXACT cell census -- and labelled.

    Energy is additive across distinct hardware, so composing it across levels
    is legitimate where a direct measurement is not available; TIME is not
    composed into a level time anywhere, and an op time that sums measured level
    times is labelled COMPOSED wherever it appears.

    The per-cell energy is taken from the measured Kogge-Stone row of the same
    width, which shares the generate level, the cell library and the beat, so
    the composition holds the per-cell cost fixed and varies only the census --
    which is exactly the quantity the adder-form question turns on.
    """
    import veh, cmosnat
    Q = qal_rows()
    out = {"_label": "COMPOSED", "_method": composed_adder_energy.__doc__.strip()}
    src = None
    for v in Q.values():
        if v["vehicle"] == "ks_w8":
            src = v
            break
    if src is None:
        out["status"] = "no measured ks8 row to compose from"
        return out
    epc = src["E_per_gate_fJ"]
    lvl = src.get("LEVEL_TIME_measured_max_ps")
    out["source_row"] = src["tag"]
    out["E_per_cell_fJ_MEASURED"] = epc
    out["level_time_ps_MEASURED"] = lvl
    for W in (8, 32):
        t = cmosnat.structural_table(W)
        row = {}
        for form in ("ks", "ripple"):
            c = t[form]
            row[form] = dict(
                cells=c["QAL_cells"], levels=c["QAL_levels"],
                E_COMPOSED_fJ=round(c["QAL_cells"] * epc, 2),
                op_time_COMPOSED_ps=(round(c["QAL_levels"] * lvl, 1)
                                     if lvl else None))
        row["ripple_over_ks_energy"] = round(
            row["ripple"]["E_COMPOSED_fJ"] / row["ks"]["E_COMPOSED_fJ"], 3)
        if row["ks"]["op_time_COMPOSED_ps"]:
            row["ripple_over_ks_time"] = round(
                row["ripple"]["op_time_COMPOSED_ps"] /
                row["ks"]["op_time_COMPOSED_ps"], 3)
        out["W%d" % W] = row
    return out


# ------------------------------------------- B13: validate the coarser step
def step_validation():
    """Compare the SAME vehicle at the committed 0.25 ps max step and at 1.0 ps.

    This is the check that decides whether the AES row -- which is only
    affordable at the coarser step -- may be believed.  Every extracted scalar
    is compared; the worst relative deviation is the headline.
    """
    Q = qal_rows()
    fine = coarse = None
    for v in Q.values():
        if v["vehicle"] != "qrxor_w32_r16" or not v.get("cw_per_bit_fF"):
            continue
        if abs(v.get("mstep_ps", 0.25) - 0.25) < 1e-9:
            fine = v
        elif abs(v.get("mstep_ps", 0.25) - 1.0) < 1e-9:
            coarse = v
    if not (fine and coarse):
        return {"status": "need both a 0.25 ps and a 1.0 ps qrxor row",
                "have_fine": bool(fine), "have_coarse": bool(coarse)}

    def flat(d, pre=""):
        out = {}
        for k, x in d.items():
            if isinstance(x, dict):
                out.update(flat(x, pre + k + "/"))
            elif isinstance(x, (int, float)) and not isinstance(x, bool):
                out[pre + k] = float(x)
        return out

    a, b = flat(fine), flat(coarse)
    skip = ("mstep_ps", "wall_s", "tend", "tzr", "tzq")
    rows = []
    for k in sorted(set(a) & set(b)):
        if any(sk in k for sk in skip):
            continue
        va, vb = a[k], b[k]
        den = max(abs(va), abs(vb))
        rel = 0.0 if den < 1e-12 else abs(va - vb) / den
        rows.append((rel, k, va, vb))
    rows.sort(reverse=True)
    hl = ["E_tank_lost_total_fJ_CONVENTION_FREE", "E_per_gate_fJ",
          "worst_gate_pct", "G7_worst_rail_V", "separation_min_mV",
          "LEVEL_TIME_measured_max_ps"]
    return dict(
        _label="INSTRUMENT CHECK for AMENDMENT B13",
        fine_row=fine["tag"], coarse_row=coarse["tag"],
        n_quantities=len(rows),
        worst_relative=round(rows[0][0], 6) if rows else None,
        worst_key=rows[0][1] if rows else None,
        worst_10=[dict(key=k, fine=va, coarse=vb, rel=round(r, 6))
                  for r, k, va, vb in rows[:10]],
        headline=[dict(key=k, fine=a.get(k), coarse=b.get(k),
                       rel=(None if k not in a or k not in b or
                            max(abs(a[k]), abs(b[k])) < 1e-12
                            else round(abs(a[k] - b[k]) /
                                       max(abs(a[k]), abs(b[k])), 6)))
                  for k in hl],
        fcrit_fine=fine["G6_functional"]["score"],
        fcrit_coarse=coarse["G6_functional"]["score"],
        PASS_fine=fine["PASS"], PASS_coarse=coarse["PASS"])


# ------------------------------------------------------- the paired verdict
def paired():
    """Pair each QAL row with its G9 comparators and state the verdict.

    ENERGY headline is quoted at the MINIMUM measured rail peak, which is the
    LEAST energy CMOS can be charged under gate G9 and therefore the hardest
    case for QAL.  SPEED headline uses the same comparator's measured
    propagation delay.  The ACTIVITY CROSSOVER is reported with every energy
    ratio, because QAL's energy is activity-independent and CMOS's is not, so a
    single ratio without its crossover is not a verdict.
    """
    import glob
    Q = qal_rows()
    nats, twins = {}, {}
    for f in glob.glob(os.path.join(HERE, "NAT_*.json")):
        d = json.load(open(f)); nats.setdefault(d["which"], []).append(d)
    for f in glob.glob(os.path.join(HERE, "TWIN_*.json")):
        d = json.load(open(f)); twins.setdefault(d["which"], []).append(d)
    key = {"aes_addroundkey": "aes", "qrxor_w32_r16": "qrxor",
           "ks_w8": "ks8", "ripple_w8": "rip8", "ks_w32": "ks32"}
    out = {}
    for v in Q.values():
        nm = key.get(v["vehicle"], v["vehicle"])
        cw = v.get("cw_per_bit_fF") or 0.0
        vmin = min(v["rail_peak_V"].values())
        cand = lambda lst: [d for d in lst
                            if abs((d.get("cw_per_bit_fF") or 0.0) - cw) < 1e-6]
        pick = lambda lst: (min(cand(lst), key=lambda d: abs(d["vdd_V"] - vmin))
                            if cand(lst) else None)
        tw, nt = pick(twins.get(nm, [])), pick(nats.get(nm, []))
        Eq = v["E_tank_lost_total_fJ_CONVENTION_FREE"]
        d = dict(vehicle=v["vehicle"], tag=v["tag"], levels=v["nb"],
                 cells=v["cells_total"], cw_per_bit_fF=cw, beat_ps=v["T_ps"],
                 mstep_ps=v.get("mstep_ps"),
                 QAL_E_beat_fJ=round(Eq, 3),
                 QAL_E_per_gate_fJ=round(v["E_per_gate_fJ"], 4),
                 QAL_level_time_ps=v.get("LEVEL_TIME_measured_max_ps"),
                 QAL_op_time_ps=v.get("OP_TIME_end_to_end_MEASURED_ps"),
                 QAL_initiation_interval_ps=v["T_ps"] * (1 + v["H"]),
                 QAL_rail_peak_min_V=round(vmin, 4),
                 QAL_rail_at_boundary_min_V=round(v["G7_worst_rail_V"], 4),
                 QAL_fcrit=v["G6_functional"]["score"],
                 QAL_worst_gate_pct=round(v["worst_gate_pct"], 3),
                 QAL_GATES=v["GATES"], QAL_PASS=v["PASS"])
        for lbl, c in (("twin", tw), ("native", nt)):
            if not c:
                continue
            Ec = c["E_full_cycle_fJ_CONVENTION_FREE"]
            a = c["activity"]["activity"]
            # WHICH QAL NUMBER THE COMPARATOR IS PAIRED WITH.
            #
            # The same-netlist TWIN carries the identical netlist, so it pairs
            # with the QAL WHOLE CHAIN.
            #
            # The CMOS-NATIVE form implements only what CMOS would actually
            # build.  For the permutation vehicles that is ONE logic level (128
            # XOR2 for AddRoundKey, 32 XOR2 for the ChaCha step) -- the drive and
            # receiver levels exist in the QAL vehicle because a bank needs a
            # real predecessor and a real receiver, and CMOS needs neither -- so
            # it pairs with the QAL BANK THAT DOES THAT WORK, identified as the
            # bank carrying the most energy (it is the one holding the wide cells
            # and the permutation wire).  For an ADDER the native form is the
            # whole function, so it pairs with the whole chain.
            #
            # Getting this wrong is not cosmetic: _widest() picked bank 1 for
            # qrxor, whose three levels all hold 32 cells, and reported 6.935x
            # where the correct pairing gives 1.795x.
            # SINGLE-LEVEL vehicles only.  An ADDER's CMOS-native form implements
            # the WHOLE function, so it pairs with the whole chain even though it
            # has fewer cells (no forwarding) -- pairing it with one bank was
            # wrong and reported ks8 at a 0.158 crossover instead of its real one.
            single_level = v["vehicle"] in ("aes_addroundkey", "qrxor_w32_r16")
            if lbl == "twin":
                base = Eq
            elif single_level and c["cells"] < v["cells_total"]:
                eb = v["energy_per_bank"]
                bk = max(eb, key=lambda k: eb[k]["E_tank_lost_fJ_CONVENTION_FREE"])
                base = eb[bk]["E_tank_lost_fJ_CONVENTION_FREE"]
                d["_native_paired_with_bank"] = bk
                d["_native_paired_bank_cells"] = eb[bk]["n_cells"]
            else:
                base = Eq
            d["CMOS_%s_vdd_V" % lbl] = c["vdd_V"]
            d["CMOS_%s_cells" % lbl] = c["cells"]
            d["CMOS_%s_E_fJ" % lbl] = round(Ec, 3)
            d["CMOS_%s_activity" % lbl] = a
            d["CMOS_%s_delay_ps" % lbl] = c["DELAY_end_to_end_MEASURED_ps"]
            d["ENERGY_ratio_CMOS_over_QAL_%s" % lbl] = round(Ec / base, 4)
            d["ENERGY_crossover_activity_%s" % lbl] = round(base / (Ec / a), 4)
            d["ENERGY_at_activity_0.5_%s" % lbl] = round((Ec * 0.5 / a) / base, 4)
            d["_QAL_side_%s" % lbl] = ("the functional bank alone"
                                       if (lbl == "native" and single_level and
                                           c["cells"] < v["cells_total"])
                                       else "whole chain")
            if c["DELAY_end_to_end_MEASURED_ps"] and d["QAL_op_time_ps"]:
                d["SPEED_latency_QAL_over_CMOS_%s" % lbl] = round(
                    d["QAL_op_time_ps"] / c["DELAY_end_to_end_MEASURED_ps"], 3)
                d["SPEED_throughput_QAL_over_CMOS_%s" % lbl] = round(
                    d["QAL_initiation_interval_ps"] /
                    c["DELAY_end_to_end_MEASURED_ps"], 3)
        out[v["tag"]] = d
    return out


def _widest(v):
    n = v["n_per_level"]
    return 1 + max(range(len(n)), key=lambda i: n[i]) if n else 1
