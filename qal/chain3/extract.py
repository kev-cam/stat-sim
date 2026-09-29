#!/usr/bin/env python3
"""Extractor / runner for the 3-bank unbuffered QAL chain.

Every reported field is MEASURED off the .mt0 / .prn of a run unless its name
carries _DERIVED.  Nothing here re-derives the single-hop comparator; that is
frozen in PRE_REGISTERED.json from the committed qal/lsweep table.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chain import (HERE, MGATE, NBANK, DV, EDGE, T1, TAIL, CA_FF, RS_REF,
                   chain_lines, timing, run, parse_mt0, read_prn,
                   zero_after_peak, widths, is_hi, delta_ps, t_est)

VBEND_REF   = 0.6758936      # committed single-hop delivered rail
BUDGET_MV   = 120.0          # pre-registered total rail-depression allowance
CLIFF_FLOOR = 0.600          # committed C3 sub-allowance
SETTLE_MIN  = 90.0
C2_FRAC     = 0.1478         # committed rail-drain completeness fraction


# --------------------------------------------------------------- the probes
def probe_hop(tag, l_nh, total_um, mode, tz1=None, srccut=True, dov=None):
    """probe A (tz1 None) -> t_zcs(1); probe B (tz1 given) -> t_zcs(2)."""
    which = 1 if tz1 is None else 2
    lines, T = chain_lines(l_nh, total_um, mode, tz1=tz1, probe=which,
                           srccut=srccut, dov=dov)
    fn = "p%d_%s.cir" % (which, tag)
    path, msg = run(fn, lines)
    print("    " + msg)
    if path is None:
        return None, msg
    hdr, rows = read_prn(path + ".prn")
    t0 = T1 if which == 1 else T["T2"]
    z, st = zero_after_peak(hdr, rows, "I(L%d)" % which, t0, rows[-1][1] * 1e12)
    if z is None:
        return None, "probe%d: %s" % (which, st)
    z["t_zcs"] = z["tz"] - t0
    z["status"] = st
    print("    probe%d %s: close %.2f -> true zero at %.4f ps after close "
          "(%s, Ipk %.1f uA, analytic pi*sqrt(LC) would be %.2f)"
          % (which, tag, t0, z["t_zcs"], st, z["ipk_uA"], t_est(l_nh)))
    return z, st


# ------------------------------------------------------------- the extractor
def extract(mt0, prn, l_nh, total_um, mode, tz1, tz2, T, no_tg=False, srccut=True):
    m = parse_mt0(mt0)
    f = 1e15
    row = dict(L_nH=l_nh, total_um=total_um, mode=mode,
               **{("w_" + k): v for k, v in widths(total_um).items()},
               t_zcs1_ps=tz1, t_zcs2_ps=tz2, delta_ps=T["delta"],
               t_stage1_ps=tz1 + T["delta"], t_stage2_ps=tz2 + T["delta"],
               t_analytic_pred_ps=t_est(l_nh),
               ck_ps={"ck1": T["ck1"], "ck2": T["ck2"], "ck3": T["ck3"]})

    # ---- rails: the delivered rail at EACH bank, at its own boundary
    vr = {}
    for k in range(1, NBANK + 1):
        for nm in ("H", "K1", "K2", "K3", "B1", "C1", "B2", "C2", "D"):
            vr["%d%s" % (k, nm)] = m.get("VR%d%s" % (k, nm))
    row["VBEND1"] = vr["1K1"]
    row["VBEND2"] = vr["2K2"]
    row["VBEND3"] = vr["3K3"]
    row["rail_head_after_headTG_open"] = vr["1H"]
    row["VRPK"] = {k: m.get("VR%dPK" % k) for k in range(1, NBANK + 1)}
    row["rails_all_checkpoints"] = vr
    row["VBEND3_end_of_tail"] = vr["3D"]

    # ---- droop
    row["hop1_ratio"] = row["VBEND2"] / row["VBEND1"]
    row["hop2_ratio"] = row["VBEND3"] / row["VBEND2"]
    row["droop_hop1_pct"] = 100.0 * (row["hop1_ratio"] - 1.0)
    row["droop_hop2_pct"] = 100.0 * (row["hop2_ratio"] - 1.0)
    row["droop_hop1_mV"] = 1000.0 * (row["VBEND2"] - row["VBEND1"])
    row["droop_hop2_mV"] = 1000.0 * (row["VBEND3"] - row["VBEND2"])
    row["accum_droop_1to3_pct"] = 100.0 * (row["VBEND3"] / row["VBEND1"] - 1.0)
    row["accum_droop_1to3_mV"] = 1000.0 * (row["VBEND3"] - row["VBEND1"])
    row["steady_state_per_hop_pct_DERIVED"] = row["droop_hop2_pct"]

    # ---- margin budget (pre-registered both ways)
    row["margin_cumulative_from_committed_ref_mV"] = 1000.0 * (VBEND_REF - min(
        row["VBEND2"], row["VBEND3"]))
    row["margin_compounding_only_mV"] = 1000.0 * (row["VBEND2"] - row["VBEND3"])
    row["A2i_budget_PASS"] = (row["margin_cumulative_from_committed_ref_mV"]
                              <= BUDGET_MV)
    row["A2ii_budget_PASS"] = row["margin_compounding_only_mV"] <= BUDGET_MV
    row["cliff_floor_PASS"] = min(row["VBEND2"], row["VBEND3"]) >= CLIFF_FLOOR
    row["budget_used_pct_of_120mV"] = \
        100.0 * row["margin_cumulative_from_committed_ref_mV"] / BUDGET_MV

    # ---- per-gate settling at EACH bank's own stage boundary (never aggregated)
    st, pat, grp = {}, {}, {}
    for k in range(1, NBANK + 1):
        rail = row["VBEND%d" % k]
        st[k], pat[k] = {}, {}
        up, dn = [], []
        for i in range(MGATE):
            v = m["O%d_%dS" % (k, i)]
            if is_hi(k, i):                          # pull-DOWN cell
                s = 100.0 * (1.0 - v / rail)
                ok = v <= 0.10 * rail
                dn.append(s)
            else:                                    # pull-UP cell
                s = 100.0 * (v / rail)
                ok = v >= 0.50 * rail
                up.append(s)
            st[k]["o%d_%d" % (k, i)] = s
            pat[k]["o%d_%d" % (k, i)] = ok
        grp[k] = dict(pullup_min=min(up), pullup_max=max(up),
                      pulldown_min=min(dn), pulldown_max=max(dn),
                      limiting="pull-down" if min(dn) < min(up) else "pull-up",
                      gap_pct=abs(min(dn) - min(up)))
    row["settling_pct_per_gate"] = st
    row["outputs_at_own_checkpoint_V"] = {
        k: {"o%d_%d" % (k, i): m["O%d_%dS" % (k, i)] for i in range(MGATE)}
        for k in range(1, NBANK + 1)}
    row["outputs_at_end_of_tail_V"] = {
        k: {"o%d_%d" % (k, i): m["O%d_%dE" % (k, i)] for i in range(MGATE)}
        for k in range(1, NBANK + 1)}
    # bank 3 is the only bank whose rail is still up at the end of the tail, so it
    # is the only one whose EVENTUAL settling is meaningful: it separates
    # "ran out of stage time" from "cannot drive at this rail".
    r3 = vr["3D"]
    row["bank3_settling_end_of_tail_pct"] = {
        "o3_%d" % i: 100.0 * ((1.0 - m["O3_%dE" % i] / r3) if is_hi(3, i)
                              else (m["O3_%dE" % i] / r3)) for i in range(MGATE)}
    row["settling_min_per_bank"] = {k: min(st[k].values()) for k in st}
    row["group_settling"] = grp
    row["data_pattern_present"] = {k: all(pat[k].values()) for k in pat}
    row["data_pattern_detail"] = pat
    row["A1_settle_PASS"] = all(min(st[k].values()) >= SETTLE_MIN for k in st)
    row["limiting_device_per_bank"] = {k: grp[k]["limiting"] for k in grp}
    lim = [k for k in grp if min(st[k].values()) == min(
        min(st[j].values()) for j in st)][0]
    row["worst_bank"] = lim
    row["limiting_device_overall"] = grp[lim]["limiting"]

    # ---- the gate drive each group actually gets (the limiting-device evidence)
    drv = {}
    for k in range(1, NBANK + 1):
        if k == 1:
            hi_in = DV
        else:
            hi_in = max(m["O%d_%dS" % (k - 1, i)] for i in range(MGATE)
                        if not is_hi(k - 1, i))
        drv[k] = dict(pulldown_gate_V=hi_in, pullup_source_V=row["VBEND%d" % k])
    row["gate_drive_available_V"] = drv

    # ---- rail-drain completeness per hop (committed C2)
    row["residual_source_rail_V"] = {1: vr["1B1"], 2: vr["2B2"]}
    row["residual_frac"] = {1: vr["1B1"] / row["VBEND1"],
                            2: (vr["2B2"] / row["VBEND2"]) if mode != "hold" else None}
    if mode == "hold":
        row["residual_source_rail_V"][2] = None
    row["A4_raildrain_PASS"] = all(v <= C2_FRAC for v in row["residual_frac"].values()
                                   if v is not None)

    # ---- per-hop energy + the instrument identity at each hop's OWN zero
    def ck(tg, p):
        a = m.get("%s_%s" % (tg.upper(), p))
        z = m.get("%s_Z" % tg.upper())
        return None if a is None or z is None else (a - z) * f
    en, ident = {}, {}
    for k in (1, 2):
        b, c = "B%d" % k, "C%d" % k
        en[k] = dict(ea_at_zero=ck("ea%d" % k, b), ea_at_open7=ck("ea%d" % k, c),
                     eb_at_open7=ck("eb%d" % k, c), er_at_zero=ck("er%d" % k, b),
                     er_at_open7=ck("er%d" % k, c), esw_at_zero=ck("esw%d" % k, b),
                     esw_at_open7=ck("esw%d" % k, c),
                     q_through_L_fC=ck("qlt%d" % k, c))
        # AMENDMENT A1 of the committed campaign: the path identity is
        # e_into_inductor - e_out_of_inductor - I^2R = dE_L, and it vanishes ONLY
        # where the inductor current is zero.  With a source-side cut the
        # inductor's near node is a{k}, not rail{k}, so ean is the correct term.
        # the pre-source-cut (rxonly) decks have no a{k} node, so ean does not
        # exist there; the inductor's near node IS rail{k} in that topology.
        en[k]["ean_at_zero"] = ck("ean%d" % k, b)
        if en[k]["ean_at_zero"] is None:
            en[k]["ean_at_zero"] = en[k]["ea_at_zero"]
        en[k]["src_switch_block_fJ"] = (en[k]["ea_at_zero"] - en[k]["ean_at_zero"]
                                        if srccut else 0.0)
        en[k]["dst_switch_block_fJ"] = en[k]["esw_at_open7"] - en[k]["eb_at_open7"]
        ident[k] = (en[k]["ean_at_zero"] - en[k]["esw_at_zero"]
                    - en[k]["er_at_zero"])
    row["hop_energy_fJ"] = en
    row["identity_at_own_zero_fJ"] = ident
    row["A3_instrument_PASS"] = all(abs(v) <= 0.02 for v in ident.values())

    # ---- supply / top-up cost.  The head window [0, 180 ps], bank 2's top-up
    # window (t_open1, ck2) and bank 3's (t_open2, ck3) are DISJOINT, so the
    # single qdv integrator splits exactly by checkpoint difference.
    qdv = {p: ck("qdv", p) for p in ("K1", "B1", "K2", "B2", "K3", "D")}
    row["qdv_at_checkpoints_fC"] = qdv
    row["head_charge_fC"] = qdv["K1"]
    row["head_energy_fJ"] = DV * qdv["K1"] if qdv["K1"] is not None else None
    if not no_tg:
        q = {2: qdv["K2"] - qdv["B1"],
             3: qdv["K3"] - (qdv["B2"] if mode != "hold" else qdv["K2"])}
        eg = {k: ck("egtu%d" % k, "D") for k in (2, 3)}
        row["topup_charge_fC"] = {2: q[2], 3: q[3]}
        row["topup_energy_fJ"] = {2: DV * q[2], 3: DV * q[3]}
        row["topup_gatedrive_fJ"] = {2: eg[2], 3: eg[3]}
        row["topup_total_fJ"] = DV * (q[2] + q[3]) + eg[2] + eg[3]
        row["topup_per_hop_fJ"] = DV * q[2] + eg[2]
    else:
        row["supply_charge_after_head_fC"] = qdv["D"] - qdv["K1"]
    row["IPK_uA"] = {1: m.get("IPK1", 0) * 1e6, 2: m.get("IPK2", 0) * 1e6}
    row["IZ_uA"] = {1: m.get("IZ1", 0) * 1e6, 2: m.get("IZ2", 0) * 1e6}

    # ---- THE CHAIN-ONLY MECHANISM, measured off the waveform:
    # bank k's pull-DOWN gate drive is bank k-1's pull-UP output, and that output
    # is referenced to bank k-1's RAIL -- which is being drained forward by the very
    # hop that powers bank k.  A logic LOW is referenced to ground and survives;
    # a logic HIGH does not.  Measure how far the HIGH has collapsed by the time
    # the evaluating hop reaches its own current zero.
    try:
        row.update(drive_collapse(prn, T))
    except Exception as e:                                        # noqa
        row["drive_collapse_error"] = repr(e)

    # ---- waveform timing: when does each bank actually become valid?
    try:
        row.update(valid_times(prn, T, row))
    except Exception as e:                                        # noqa
        row["valid_time_error"] = repr(e)

    # ---- instrument cross-check: the mt0 FIND values against the raw waveform,
    # which owes nothing to .measure and nothing to the LAG_PS correction.
    try:
        hdr, rows = read_prn(prn)
        def wav(sig, t):
            c = hdr.index(sig); prev = None
            for r in rows:
                tt = r[1] * 1e12
                if prev is not None and prev[1] * 1e12 <= t <= tt:
                    a = prev[1] * 1e12
                    g = (t - a) / (tt - a) if tt != a else 0.0
                    return prev[c] + g * (r[c] - prev[c])
                prev = r
            return float("nan")
        xc = {}
        for k in range(1, NBANK + 1):
            xc["VBEND%d_waveform" % k] = wav("V(RAIL%d)" % k, T["ck%d" % k])
            xc["VBEND%d_mt0_minus_waveform_mV" % k] = \
                1000.0 * (row["VBEND%d" % k] - xc["VBEND%d_waveform" % k])
        for k in (1, 2):
            en_sig = ("V(XEAN%d)" % k) if ("V(XEAN%d)" % k) in hdr else ("V(XEA%d)" % k)
            ea = wav(en_sig, T["t_open%d" % k])
            es = wav("V(XESW%d)" % k, T["t_open%d" % k])
            er = wav("V(XER%d)" % k, T["t_open%d" % k])
            row.setdefault("_xc_dbg", {})["hop%d" % k] = [ea, es, er]
            z = [wav(en_sig, 0.5),
                 wav("V(XESW%d)" % k, 0.5), wav("V(XER%d)" % k, 0.5)]
            xc["identity_hop%d_waveform_fJ" % k] = \
                ((ea - z[0]) - (es - z[1]) - (er - z[2])) * f
        row["instrument_xcheck"] = xc
        row["A3_xcheck_PASS"] = all(
            abs(xc["identity_hop%d_waveform_fJ" % k]) <= 0.02 for k in (1, 2))
    except Exception as e:                                        # noqa
        row["xcheck_error"] = repr(e)

    # ---- verdict (pre-registered: A1 and A2i and A3)
    row["FUNCTIONAL"] = ("YES" if (row["A1_settle_PASS"] and row["A2i_budget_PASS"]
                                   and row["A3_instrument_PASS"]
                                   and all(row["data_pattern_present"].values()))
                         else "NO")
    row["fail_reasons"] = [n for n, ok in
                           (("A1_settle", row["A1_settle_PASS"]),
                            ("A2i_budget", row["A2i_budget_PASS"]),
                            ("A3_instrument", row["A3_instrument_PASS"]),
                            ("data_pattern", all(row["data_pattern_present"].values())),
                            ("A2ii_compounding", row["A2ii_budget_PASS"]),
                            ("cliff_floor", row["cliff_floor_PASS"]),
                            ("A4_raildrain", row["A4_raildrain_PASS"])) if not ok]
    return row


VT = json.load(open(os.path.join(HERE, "vt.json")))


def idn(vgs):
    """MEASURED nMOS drive current (chain3/vt.cir, |Vds| = 0.1 V), log-interpolated."""
    tb = sorted((float(k), v) for k, v in VT["Id_nmos_uA"].items())
    if vgs <= tb[0][0]:
        return tb[0][1] * 10 ** ((vgs - tb[0][0]) / 0.08)
    for (a, ia), (b, ib) in zip(tb, tb[1:]):
        if a <= vgs <= b:
            f = (vgs - a) / (b - a)
            return ia * (ib / ia) ** f
    return tb[-1][1]


def drive_collapse(prn, T):
    hdr, rows = read_prn(prn)
    def at(sig, t):
        c = hdr.index(sig); prev = None
        for r in rows:
            tt = r[1] * 1e12
            if prev is not None and prev[1] * 1e12 <= t <= tt:
                a = prev[1] * 1e12
                g = (t - a) / (tt - a) if tt != a else 0.0
                return prev[c] + g * (r[c] - prev[c])
            prev = r
        return float("nan")
    out = {}
    for k in (2, 3):                      # bank k is evaluated by hop k-1
        h = k - 1
        # its pull-DOWN cells' gates are bank k-1's PULL-UP outputs
        src = [i for i in range(MGATE) if not is_hi(k - 1, i)]
        if ("V(O%d_%d)" % (k - 1, src[0])) not in hdr:
            continue
        i0 = src[0]
        sig = "V(O%d_%d)" % (k - 1, i0)
        vc = at(sig, T["T%d" % h] if h > 1 else T["T1"])
        vo = at(sig, T["t_open%d" % h])
        vk = at(sig, T["ck%d" % k])
        out["bank%d_pulldown_gate_at_hop_close_V" % k] = vc
        out["bank%d_pulldown_gate_at_hop_open_V" % k] = vo
        out["bank%d_pulldown_gate_at_checkpoint_V" % k] = vk
        out["bank%d_pulldown_gate_collapse_pct" % k] = 100.0 * (vo / vc - 1.0) if vc else None
        out["bank%d_pulldown_Id_at_close_uA" % k] = idn(vc)
        out["bank%d_pulldown_Id_at_open_uA" % k] = idn(vo)
        out["bank%d_pulldown_Id_collapse_x" % k] = (idn(vc) / idn(vo)) if idn(vo) else None
        out["bank%d_pullup_gate_at_hop_open_V" % k] = at(
            "V(O%d_%d)" % (k - 1, [i for i in range(MGATE) if is_hi(k - 1, i)][0]),
            T["t_open%d" % h])
    return out


def valid_times(prn, T, row):
    """t_valid90 per bank off the WAVEFORM: the time after that bank's incoming
    hop closes at which ALL 8 of its cells are simultaneously within 90% of its
    INSTANTANEOUS rail and stay there up to the bank's own checkpoint."""
    hdr, rows = read_prn(prn)
    out = {}
    close = {1: 0.0, 2: T["T1"], 3: T["T2"]}
    ckt = {1: T["ck1"], 2: T["ck2"], 3: T["ck3"]}
    for k in range(1, NBANK + 1):
        ir = hdr.index("V(RAIL%d)" % k)
        io = [hdr.index("V(O%d_%d)" % (k, i)) for i in range(MGATE)]
        first = None
        for r in rows:
            t = r[1] * 1e12
            if t < close[k] or t > ckt[k]:
                continue
            vb = r[ir]
            good = vb > 1e-6
            if good:
                for i in range(MGATE):
                    s = (1.0 - r[io[i]] / vb) if is_hi(k, i) else (r[io[i]] / vb)
                    if s < 0.90:
                        good = False
                        break
            if good:
                if first is None:
                    first = t
            else:
                first = None
        out["t_valid90_bank%d_ps" % k] = (first - close[k]) if first is not None else None
        out["bank%d_valid_before_boundary" % k] = first is not None
    for k in (2, 3):
        tv = out["t_valid90_bank%d_ps" % k]
        st = row["t_zcs%d_ps" % (k - 1)] + T["delta"]
        out["bank%d_slack_ps" % k] = (st - tv) if tv is not None else None
    return out


# ------------------------------------------------------------------- driver
def point(tag, l_nh, total_um, mode, tz1=None, srccut=True, dov=None):
    t_start = time.monotonic()
    print("  == %s  L=%g nH  W=%g um  mode=%s  DELTA=%g ps =="
          % (tag, l_nh, total_um, mode, delta_ps(l_nh)))
    if tz1 is None:
        z1, st = probe_hop(tag, l_nh, total_um, mode, srccut=srccut, dov=dov)
        if z1 is None:
            return dict(tag=tag, L_nH=l_nh, total_um=total_um, mode=mode, error=st)
        tz1 = z1["t_zcs"]
    if mode == "hold":                     # hop 2 never closes: nothing to probe
        z2, st, tz2 = {"t_zcs": 0.001}, "hold (hop 2 disabled)", 0.001
    else:
        z2, st = probe_hop(tag, l_nh, total_um, mode, tz1=tz1, srccut=srccut, dov=dov)
    if z2 is None:
        return dict(tag=tag, L_nH=l_nh, total_um=total_um, mode=mode,
                    error=st, t_zcs1_ps=tz1)
    tz2 = z2["t_zcs"]
    lines, T = chain_lines(l_nh, total_um, mode, tz1=tz1, tz2=tz2,
                           srccut=srccut, dov=dov)
    fn = "c_%s.cir" % tag
    path, msg = run(fn, lines)
    print("    " + msg)
    if path is None:
        return dict(tag=tag, L_nH=l_nh, total_um=total_um, mode=mode, error=msg,
                    t_zcs1_ps=tz1, t_zcs2_ps=tz2)
    try:
        row = extract(path + ".mt0", path + ".prn", l_nh, total_um, mode,
                      tz1, tz2, T, mode not in ("topup", "ctrl"), srccut)
    except Exception as e:                                        # noqa
        import traceback; traceback.print_exc()
        return dict(tag=tag, L_nH=l_nh, total_um=total_um, mode=mode,
                    error="extract: %r" % e, t_zcs1_ps=tz1, t_zcs2_ps=tz2)
    row["tag"] = tag
    row["banks23_have_supply_tg"] = mode in ("topup", "ctrl", "hold")
    row["srccut"] = srccut
    row["probe1_ipk_uA"] = None if tz1 is None else None
    row["probe2_status"] = st
    row["wall_s"] = round(time.monotonic() - t_start, 1)
    return row


def load():
    fn = os.path.join(HERE, "rows.json")
    return json.load(open(fn)) if os.path.exists(fn) else {}


def save(row):
    fn = os.path.join(HERE, "rows.json")
    d = load(); d[row["tag"]] = row
    json.dump(d, open(fn, "w"), indent=1)


def brief(r):
    if "error" in r:
        return "%-18s L=%-7g W=%-4g %-5s ERROR %s" % (
            r.get("tag"), r["L_nH"], r["total_um"], r["mode"], r["error"][:140])
    sm = r["settling_min_per_bank"]
    return ("%-18s L=%-7g W=%-4g %-5s | tz %7.2f/%7.2f stage %7.2f/%7.2f | "
            "VB %.4f/%.4f/%.4f droop %+6.2f%%/%+6.2f%% | settle %6.2f/%6.2f/%6.2f%% "
            "lim=%-9s | budget %6.1f mV (%5.1f%%) | %s%s"
            % (r["tag"], r["L_nH"], r["total_um"], r["mode"],
               r["t_zcs1_ps"], r["t_zcs2_ps"], r["t_stage1_ps"], r["t_stage2_ps"],
               r["VBEND1"], r["VBEND2"], r["VBEND3"],
               r["droop_hop1_pct"], r["droop_hop2_pct"],
               sm["1"] if "1" in sm else sm[1], sm["2"] if "2" in sm else sm[2],
               sm["3"] if "3" in sm else sm[3],
               r["limiting_device_overall"],
               r["margin_cumulative_from_committed_ref_mV"],
               r["budget_used_pct_of_120mV"], r["FUNCTIONAL"],
               (" [" + ",".join(r["fail_reasons"]) + "]") if r["fail_reasons"] else ""))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "point":
        tag, l_nh, tot, mode = sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
        extra = sys.argv[6:]
        sc = "rxonly" not in extra
        dov = None
        for e in extra:
            if e.startswith("d="):
                dov = float(e[2:])
        r = point(tag, l_nh, tot, mode, srccut=sc, dov=dov)
        save(r); print(brief(r))
    elif cmd == "reex":
        tag = sys.argv[2]
        d = load(); old = d[tag]
        T = timing(old["L_nH"], old["t_zcs1_ps"], old["t_zcs2_ps"],
                   old.get("delta_ps"))
        r = extract(os.path.join(HERE, "c_%s.cir.mt0" % tag),
                    os.path.join(HERE, "c_%s.cir.prn" % tag),
                    old["L_nH"], old["total_um"], old["mode"],
                    old["t_zcs1_ps"], old["t_zcs2_ps"], T,
                    old["mode"] not in ("topup", "ctrl"), old.get("srccut", True))
        r["tag"] = tag; r["srccut"] = old.get("srccut", True)
        r["banks23_have_supply_tg"] = old["mode"] in ("topup", "ctrl")
        save(r); print(brief(r))
    elif cmd == "show":
        for k, r in sorted(load().items(), key=lambda x: (-x[1]["L_nH"], x[1]["mode"])):
            print(brief(r))
