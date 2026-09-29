#!/usr/bin/env python3
"""Per-row extraction for the restored-chain study.

Every number is MEASURED off a .mt0 or a .prn.  Conventions inherited VERBATIM
from qal/skip4/extract.py (which inherits chain3/lsweep/swsweep/gateb):

  * per-gate settling at the bank's OWN stage boundary, NEVER aggregated:
      pull-DOWN cell (input HIGH):  pct = 100*(1 - V(o)/rail_j)
      pull-UP   cell (input LOW ):  pct = 100*(V(o)/rail_j)
    with rail_j = V(rail j) at that same boundary instant.
  * data-pattern guard: pull-DOWN output <= 0.10*rail, pull-UP >= 0.50*rail.
  * absolute cliff 0.60 V on every hop-charged rail.
  * 1F integrators are t0-referenced against their own Z checkpoint (pedestal).
"""
import json, math, os, sys
from rest import (MGATE, EDGE, is_hi, in_net, schedule, src_node, topo,
                  parse_mt0, read_prn, at, trace, NBANK, CA_FF)

CLIFF = 0.60
VTN   = 0.5239      # MEASURED nMOS threshold (inherited)
VTP   = 0.4403      # MEASURED |pMOS threshold| (inherited)


def settle_pct(j, i, v, rail):
    return 100.0 * ((1.0 - v / rail) if is_hi(j, i) else (v / rail))


def guard_ok(j, i, v, rail):
    return (v <= 0.10 * rail) if is_hi(j, i) else (v >= 0.50 * rail)


def row_extract(k, T, tres, tz, path, nbank=NBANK, dv=1.2):
    m = parse_mt0(path + ".mt0")
    S = schedule(k, T, tres, nbank)
    nb = nbank
    op = {j: S["close"][j] + tz[(j - 1) % len(tz)] for j in range(1, nb + 1)}
    r = dict(k=k, T_ps=T, tres_ps=tres, tz_ps=tz, nbank=nb, nseg=S["S"],
             pos_in_segment={j: S["pos"][j] + 1 for j in range(1, nb + 1)},
             segment_of={j: S["seg"][j] + 1 for j in range(1, nb + 1)},
             restore_into_bank=sorted(S["restore_into"].keys()),
             close_ps=S["close"], open_ps=op, bound_ps=S["bound"],
             drain_ps=S["drain"], tend_ps=S["tend"])

    rail = {j: m["VR%dK%d" % (j, j)] for j in range(1, nb + 1)}
    r["rail_at_own_boundary_V"] = rail
    r["rail_at_own_hop_open_V"] = {j: m["VR%dB%d" % (j, j)] for j in range(1, nb + 1)}
    r["rail_peak_V"] = {j: m["VR%dPK" % j] for j in range(1, nb + 1)}
    r["rail_end_of_tail_V"] = {j: m["VR%dD" % j] for j in range(1, nb + 1)}
    r["reservoir_at_Z_V"] = {s + 1: m["VS%dZ" % (s + 1)] for s in range(S["S"])}
    r["reservoir_at_own_hop_open_V"] = {
        s + 1: m["VS%dB%d" % (s + 1, S["first"][s])] for s in range(S["S"])}

    # ---------------- per-hop droop: delivered rail vs its source at close
    droop = {}
    for j in range(1, nb + 1):
        sn = src_node(k, j)
        if sn.startswith("res"):
            sidx = int(sn[3:])
            vs = m["VS%dZ" % sidx]
        else:
            # the source bank's rail at ITS OWN stage boundary, which for a bank
            # that is about to be drained IS close[j] - EDGE -- the last instant
            # before the draining switch moves.
            si = int(sn[4:])
            vs = m["VR%dK%d" % (si, si)]
        vd = m["VR%dB%d" % (j, j)]
        droop[j] = dict(src=sn, dst="rail%d" % j, src_ref_V=vs, dst_at_open_V=vd,
                        droop_pct=100.0 * (vd / vs - 1.0) if vs else None)
    r["per_hop_droop"] = droop

    # ---------------- per-gate settling at each bank's own boundary
    st, grp, pat, drv = {}, {}, {}, {}
    for j in range(1, nb + 1):
        st[j], pat[j], drv[j] = {}, {}, {}
        up, dn = [], []
        for i in range(MGATE):
            v = m["O%d_%dS" % (j, i)]
            sp = settle_pct(j, i, v, rail[j])
            st[j]["o%d_%d" % (j, i)] = sp
            pat[j]["o%d_%d" % (j, i)] = guard_ok(j, i, v, rail[j])
            (dn if is_hi(j, i) else up).append(sp)
            gb, gc, gx = (m["G%d_%dB" % (j, i)], m["G%d_%dC" % (j, i)],
                          m["G%d_%dX" % (j, i)])
            drv[j]["o%d_%d" % (j, i)] = dict(
                src_net=in_net(k, j, i), kind="pull-down" if is_hi(j, i) else "pull-up",
                gate_at_close_V=gc, gate_at_boundary_V=gb,
                gate_worst_in_window_V=gx,
                # the device budget: a pull-DOWN cell needs its nMOS on
                # (Vgs - Vtn) and its pMOS off; a pull-UP cell needs its pMOS on
                # (rail - Vg - |Vtp|).
                overdrive_at_boundary_V=(gb - VTN) if is_hi(j, i)
                else (rail[j] - gb - VTP),
                collapse_mV=1000.0 * (gb - gc))
        grp[j] = dict(pullup_min=min(up), pullup_max=max(up),
                      pulldown_min=min(dn), pulldown_max=max(dn),
                      worst=min(min(up), min(dn)),
                      limiting="pull-down" if min(dn) < min(up) else "pull-up",
                      gap_pct=abs(min(dn) - min(up)),
                      guard_all_pass=all(pat[j].values()),
                      pos_in_segment=S["pos"][j] + 1,
                      input_from=("ideal DC source" if j == 1 else
                                  ("RESTORING stage" if S["pos"][j] == 0
                                   else "bank %d direct (no buffer)" % (j - 1))))
    r["settling_pct_per_gate"] = st
    r["settling_groups"] = grp
    r["pattern_guard"] = pat
    r["input_drive_per_gate"] = drv
    r["outputs_at_own_boundary_V"] = {
        j: {"o%d_%d" % (j, i): m["O%d_%dS" % (j, i)] for i in range(MGATE)}
        for j in range(1, nb + 1)}
    r["outputs_end_of_tail_V"] = {
        j: {"o%d_%d" % (j, i): m["O%d_%dE" % (j, i)] for i in range(MGATE)}
        for j in range(1, nb + 1)}
    # eventual settling, reported but NEVER used for acceptance
    ev = {}
    for j in range(1, nb + 1):
        rr = m["VR%dD" % j]
        vals = [settle_pct(j, i, m["O%d_%dE" % (j, i)], rr) for i in range(MGATE)]
        ev[j] = dict(worst=min(vals), rail_V=rr)
    r["eventual_settling_at_end_of_tail"] = ev

    # ---------------- DID THE RESTORING STAGE RESTORE?  (AMENDMENT A5)
    # For a segment-head bank the gate net IS the restoring stage's output, and
    # G{j}_{i}B is that net MEASURED at the bank's own boundary -- so all 8 restored
    # bits are checked, not just the two that are printed.  A restoring stage that
    # resolves a QAL HIGH as a LOW makes its bank's settling meaningless, so this is
    # checked and reported before any settling number from that bank is believed.
    rst = {}
    for j in sorted(S["restore_into"]):
        ok, det = True, {}
        for i in range(MGATE):
            gb = m["G%d_%dB" % (j, i)]
            want_hi = is_hi(j, i)            # bank j's cell i expects a HIGH input
            good = (gb >= 0.9 * dv) if want_hi else (gb <= 0.1 * dv)
            ok = ok and good
            det["bit%d" % i] = dict(restored_level_V=gb, expected_high=want_hi,
                                    full_swing=good)
        rst[j] = dict(into_bank=j, from_bank=j - 1, ALL_BITS_FULL_SWING=ok,
                      bits=det)
    r["restore_stage_output_check"] = rst
    r["A5_restore_outputs_full_swing"] = all(v["ALL_BITS_FULL_SWING"]
                                             for v in rst.values()) if rst else None
    r["banks_fed_by_a_restoring_stage"] = sorted(S["restore_into"])

    # ---------------- settling by POSITION within a segment (the mechanism axis)
    bypos = {}
    for j in range(1, nb + 1):
        p = S["pos"][j] + 1
        bypos.setdefault(p, []).append(dict(bank=j, worst=grp[j]["worst"],
                                           up=grp[j]["pullup_min"],
                                           dn=grp[j]["pulldown_min"],
                                           rail=rail[j]))
    r["by_position_in_segment"] = bypos

    # ---------------- acceptance
    r["worst_gate_pct_all_banks"] = min(grp[j]["worst"] for j in range(1, nb + 1))
    r["worst_gate_bank"] = min(range(1, nb + 1), key=lambda j: grp[j]["worst"])
    r["A1_all_gates_90_all_banks"] = all(grp[j]["worst"] >= 90.0
                                         for j in range(1, nb + 1))
    r["A1_per_bank_pass"] = {j: grp[j]["worst"] >= 90.0 for j in range(1, nb + 1)}
    r["A2_pattern_guard_all"] = all(grp[j]["guard_all_pass"] for j in range(1, nb + 1))
    r["A3_cliff_pass"] = all(rail[j] >= CLIFF for j in range(1, nb + 1))
    r["A3_rails_below_cliff"] = [j for j in range(1, nb + 1) if rail[j] < CLIFF]
    # AMENDMENT A5: a row whose restoring stages did not produce full-swing levels
    # is VOID for acceptance -- the banks they feed were evaluating the wrong logic
    # values, so their settling numbers do not mean what the convention says.
    r["PASS"] = bool(r["A1_all_gates_90_all_banks"] and r["A2_pattern_guard_all"]
                     and (r["A5_restore_outputs_full_swing"] is not False))
    r["VOID_for_acceptance"] = (r["A5_restore_outputs_full_swing"] is False)

    # ---------------- A4 instrument
    r["IZ_uA"] = {j: m["IZ%d" % j] * 1e6 for j in range(1, nb + 1)}
    r["IPK_uA"] = {j: m["IPK%d" % j] * 1e6 for j in range(1, nb + 1)}

    def d(tg, nm):
        return m["%s_%s" % (tg.upper(), nm)] - m["%s_Z" % tg.upper()]
    r["identity_at_own_zero_fJ"] = {
        j: (d("ean%d" % j, "B%d" % j) - d("esw%d" % j, "B%d" % j)
            - d("er%d" % j, "B%d" % j)) * 1e15 for j in range(1, nb + 1)}
    r["A4_IZ_pass_per_hop"] = {j: abs(r["IZ_uA"][j]) <= 1.0
                               for j in range(1, nb + 1)}
    r["A4_IZ_PASS"] = all(r["A4_IZ_pass_per_hop"].values())
    r["A4_identity_PASS"] = all(abs(v) <= 0.02
                                for v in r["identity_at_own_zero_fJ"].values())

    # ---------------- energy (reported; gates nothing)
    en = {}
    for j in range(1, nb + 1):
        b = "B%d" % j
        z = lambda tg: (m["%s_%s" % (tg.upper(), b)] - m["%s_Z" % tg.upper()]) * 1e15
        en[j] = dict(E_out_of_source_fJ=z("ea%d" % j),
                     E_into_dest_fJ=-z("eb%d" % j),
                     E_series_R_fJ=z("er%d" % j),
                     E_switch_block_fJ=z("ea%d" % j) - z("ean%d" % j),
                     Q_through_L_fC=z("qlt%d" % j))
    r["energy_per_hop_fJ"] = en
    dend = lambda tg: (m["%s_D" % tg.upper()] - m["%s_Z" % tg.upper()]) * 1e15
    # AMENDMENT A3: the reservoirs carry no head gate, so there is no qpre/eghd
    # integrator in the chain deck; the per-segment PRE-CHARGE is MEASURED in its
    # own deck (qpre.cir) and carried into the economics from there.
    r["supply_ledger_fJ"] = dict(
        Q_restore_supply_fC=dend("qres"), E_restore_supply_fJ=dv * dend("qres"),
        Q_vhi_fC=dend("qhi"), E_vhi_fJ=1.5 * dend("qhi"),
        E_transfer_gate_drive_fJ=dend("egt"),
        Q_ideal_inputs_bank1_fC=dend("qi1"))
    r["bank_gate_charge_fC"] = {j: dend("qg%d" % j) for j in range(1, nb + 1)}
    # Restoring stages burn STATIC current the whole time they hold a QAL level on
    # their input: the level is ~0.71 V on a 1.2 V rail, so BOTH devices conduct
    # (committed bound/ H1 A1 measured 8.78 uA static at V_in = 0.6759 V).  The
    # whole-run figure therefore scales with the 500 ps tail and would flatter or
    # punish the blend depending on run length, so the per-beat charge is taken
    # between consecutive stage-boundary checkpoints as well.
    def win(tg, a, b):
        return (m["%s_%s" % (tg.upper(), b)] - m["%s_%s" % (tg.upper(), a)]) * 1e15
    r["restore_supply_per_window_fC"] = {
        "K%d->K%d" % (j, j + 1): win("qres", "K%d" % j, "K%d" % (j + 1))
        for j in range(1, nb)}
    r["restore_supply_tail_fC"] = win("qres", "K%d" % nb, "D")
    # restore-stage supply energy per RESTORING STAGE per bit (the blend term)
    nres = len(S["restore_into"]) + (1 if nb not in S["restore_into"] else 0)
    r["n_restore_stages_in_deck"] = nres
    r["E_restore_per_stage_per_bit_fJ"] = (dv * dend("qres") / nres / MGATE
                                           if nres else None)
    return r


def tres_measure(path, S, nbank, dv=1.2):
    """MEASURE the restoring stage's latency AND its CORRECTNESS off its own
    waveform in the .prn.

    AMENDMENT A5.  Two corrections to the pre-registered M3 definition, both forced
    by measurement, neither of them loosening anything:

    (i) CORRECTNESS IS CHECKED FIRST, and it is not optional.  A restoring stage
        that resolves a QAL HIGH as a LOW has no meaningful latency, and the
        pre-registered definition ("time to reach 90% of its FINAL value") would
        have reported a perfectly healthy-looking number for exactly that failure.
        The expected logic value of bit i out of bank b is (not is_hi(b, i)); a
        restoring stage is CORRECT only if its output settles on the matching rail.

   (ii) THE SEARCH STARTS AT THE DRIVING BANK'S OWN HOP CLOSE, NOT AT ITS BOUNDARY,
        and the latency is reported SIGNED.  A restoring stage is COMBINATIONAL: it
        tracks its input continuously and flips when that input crosses its trip
        point, which happens PARTWAY through the bank's settling, not after it.  Its
        output can therefore be valid BEFORE the bank's own stage boundary -- a
        NEGATIVE latency, meaning it adds no pipeline latency at all.  Searching
        only forward from the boundary (the pre-registered window) finds no crossing
        in that case and reports None, which would have been read as a failure.  The
        signed number is the honest one, and what the next segment must actually
        wait for beyond its data being valid is max(0, latency)."""
    hdr, rows = read_prn(path + ".prn")
    out = {}
    pairs = [(jb - 1, rr) for jb, rr in sorted(S["restore_into"].items())]
    if nbank not in S["restore_into"]:
        pairs.append((nbank, S["S"]))        # the trailing restoring stage
    for srcbank, rr in pairs:
        t0 = S["bound"][srcbank]
        tsearch = S["close"][srcbank]
        for i in range(MGATE):
            expect_hi = not is_hi(srcbank, i)          # the datum being restored
            for lab, net, inv in (("inv1", "V(RM%d_%d)" % (rr, i), True),
                                  ("pair", "V(RB%d_%d)" % (rr, i), False)):
                if net not in hdr:
                    continue
                tr = trace(hdr, rows, net, tsearch, S["tend"])
                if not tr:
                    continue
                vf = tr[-1][1]
                want_hi = (not expect_hi) if inv else expect_hi
                got_hi = vf > dv / 2.0
                correct = (got_hi == want_hi)
                thr = 0.9 * dv if want_hi else 0.1 * dv
                tcross, prev = None, None
                for t, v in tr:
                    if prev is not None:
                        a, b = prev, (t, v)
                        if (a[1] < thr <= b[1]) or (a[1] > thr >= b[1]):
                            tcross = a[0] + (thr - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                            break
                    prev = (t, v)
                out["r%d_bit%d_%s" % (rr, i, lab)] = dict(
                    src_bank=srcbank, data_valid_at_ps=t0, searched_from_ps=tsearch,
                    final_V=vf, expected_logic_high=want_hi, got_logic_high=got_hi,
                    CORRECT=correct, thr_V=thr, cross_ps=tcross,
                    latency_ps=(tcross - t0) if tcross is not None else None,
                    latency_beyond_data_valid_ps=(max(0.0, tcross - t0)
                                                  if tcross is not None else None),
                    at_data_valid_V=at(hdr, rows, net, t0))
    ds = [v for v in out.values() if isinstance(v, dict) and "CORRECT" in v]
    out["ALL_CORRECT"] = all(v["CORRECT"] for v in ds) if ds else None
    out["WRONG_BITS"] = [kk for kk, v in out.items()
                         if isinstance(v, dict) and v.get("CORRECT") is False]
    return out


def level_time(path, S, j, k, dv=1.2):
    """MEASURE the LEVEL TIME of bank j directly off the waveform, in exactly the
    committed lsweep definitions, so it is comparable digit-for-digit with the
    committed single-hop t_valid90 = 123.443 ps / t_settle90 = 115.571 ps:

      t_valid90  -- first SUSTAINED instant at which every pull-DOWN output is
                    <= 10% of the INSTANTANEOUS rail and every pull-UP output is
                    >= 90% of it, measured from that bank's own hop close;
      t_settle90 -- same but against the bank's FINAL rail (VBEND), i.e. every
                    output within 10%*VBEND of its final value;
      t_level_cons = max(t_hop, t_settle90, t_valid90) -- the conservative level
                    time, which is the quantity a beat period has to cover.

    This is what makes the beat period a MEASUREMENT rather than a sweep artefact:
    the sweep confirms it, this reads it off directly.  Requires the deck to print
    all MGATE outputs of bank j (the one-segment decks do)."""
    hdr, rows = read_prn(path + ".prn")
    need = ["V(O%d_%d)" % (j, i) for i in range(MGATE)]
    if any(n not in hdr for n in need) or ("V(RAIL%d)" % j) not in hdr:
        return dict(error="deck does not print all %d outputs of bank %d" % (MGATE, j))
    ic = [hdr.index(n) for n in need]
    ir = hdr.index("V(RAIL%d)" % j)
    t_close = S["close"][j]
    t_open = None
    vbend = None
    for r in rows:
        vbend = r[ir]
    out = {}
    for th, nm in ((0.80, 80), (0.90, 90), (0.95, 95)):
        tol = (1.0 - th) * vbend
        fv = fs = None
        for r in rows:
            t = r[1] * 1e12
            if t < t_close:
                continue
            rail = r[ir]
            gv = all((r[ic[i]] <= (1.0 - th) * rail) if is_hi(j, i)
                     else (r[ic[i]] >= th * rail) for i in range(MGATE))
            gs = all(abs(r[ic[i]] - (0.0 if is_hi(j, i) else vbend)) <= tol
                     for i in range(MGATE))
            fv = (t if fv is None else fv) if gv else None
            fs = (t if fs is None else fs) if gs else None
        out["t_valid%d_ps" % nm] = (fv - t_close) if fv is not None else None
        out["t_settle%d_ps" % nm] = (fs - t_close) if fs is not None else None
    out["bank"] = j
    out["rail_final_V"] = vbend
    out["close_ps"] = t_close
    out["committed_single_hop_t_valid90_ps"] = 123.44311400000001
    out["committed_single_hop_t_settle90_ps"] = 115.570918
    return out
