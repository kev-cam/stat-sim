#!/usr/bin/env python3
"""Reference measurements + the instrument check, all MEASURED off .mt0/.prn.

  ia_hop   -- qal/skip4/instr_anchor.cir, byte-identical, re-run under MY cache.
              Digit-checks the committed single hop (L=15 nH, W=30 um, dV=1.2,
              t_hop 65.495 ps, VBEND 0.71382, 8/8 at 100%).
  ia_chain -- qal/chain3/c_a277_free.cir, byte-identical, re-run under MY cache.
              Anchors the harness to a KNOWN NEGATIVE: the failing no-restore
              adjacent 3-bank chain row (bank 3 pull-up 35.75 / pull-down 62.97).
  cinv     -- full-rail CMOS inverter chain: the restoring stage's own cell, so
              its per-stage delay IS the restoring stage's half-latency and the
              CMOS level time, and its per-inverter supply energy is the full-swing
              energy the blend needs.
  qpre     -- the per-segment PRE-CHARGE, metered on its own ideal source.
"""
import json, math, os, sys
from rest import parse_mt0, read_prn

HERE = os.path.dirname(os.path.abspath(__file__))


def cross(tr, thr, rising):
    prev = None
    for t, v in tr:
        if prev is not None:
            if (rising and prev[1] < thr <= v) or ((not rising) and prev[1] > thr >= v):
                return prev[0] + (thr - prev[1]) * (t - prev[0]) / (v - prev[1])
        prev = (t, v)
    return None


def ia_hop():
    """Digit check against the committed anchor."""
    m = parse_mt0(os.path.join(HERE, "ia_hop.cir.mt0"))
    ref = parse_mt0("/usr/local/src/stat-sim/qal/skip4/instr_anchor.cir.mt0")
    keys = ["VBPK", "VBEND", "VAEND", "IPK", "IZ", "VBOPEN", "VSWPK", "VSWMN"]
    out, alleq = {}, True
    for k in keys:
        a, b = m.get(k), ref.get(k)
        eq = (a == b)
        alleq = alleq and eq
        out[k] = dict(mine=a, committed=b, identical=eq,
                      rel=(abs(a - b) / abs(b) if b else None))
    # committed 8/8 at 100%: settling at the END of the tail, against the
    # instantaneous rail, the committed convention for this anchor deck.
    rail = m["VBEND"]
    st = {}
    for i in range(8):
        v = m["O%dE" % i]
        st["o%d" % i] = 100.0 * ((1.0 - v / rail) if i % 2 == 0 else (v / rail))
    # ALSO re-derive the committed LEVEL TIMES from the waveform with my own code
    # path, so the analysis code is checked against the committed numbers too:
    #   t_valid90  -- output within 10% of the INSTANTANEOUS rail, sustained
    #   t_settle90 -- output within 10% of VBEND of its FINAL value, sustained
    # both measured from the switch close at T0 = 50 ps (lsweep's definitions).
    hdr, rows = read_prn(os.path.join(HERE, "ia_hop.cir.prn"))
    ib, i0, i1 = hdr.index("V(BKB)"), hdr.index("V(O0)"), hdr.index("V(O1)")
    T0 = 50.0
    lv = {}
    for th, nm in ((0.80, 80), (0.90, 90), (0.95, 95)):
        fv = fs = None
        tol = (1.0 - th) * rail
        for r in rows:
            t = r[1] * 1e12
            if t < T0:
                continue
            gv = (r[i0] <= (1.0 - th) * r[ib]) and (r[i1] >= th * r[ib])
            gs = abs(r[i0]) <= tol and abs(r[i1] - rail) <= tol
            fv = (t if fv is None else fv) if gv else None
            fs = (t if fs is None else fs) if gs else None
        lv["t_valid%d_ps" % nm] = (fv - T0) if fv is not None else None
        lv["t_settle%d_ps" % nm] = (fs - T0) if fs is not None else None
    lv["t_level_cons_ps"] = max(65.49500982344826, lv["t_settle90_ps"],
                                lv["t_valid90_ps"])
    lv["committed_t_valid90_ps"] = 123.44311400000001
    lv["committed_t_settle90_ps"] = 115.570918
    lv["committed_t_level_cons_ps"] = 123.44311400000001
    return dict(digit_check=out, all_digits_identical=alleq,
                settling_end_pct=st, worst_end_pct=min(st.values()),
                t_hop_ps=65.49500982344826,
                t_hop_from_deck_ps=115.495 - 50.0,
                level_times_rederived=lv)


def ia_chain():
    """Digit check against a KNOWN FAILING no-restore chain row (chain3 a277_free)."""
    m = parse_mt0(os.path.join(HERE, "ia_chain.cir.mt0"))
    ref = parse_mt0("/usr/local/src/stat-sim/qal/chain3/c_a277_free.cir.mt0")
    # rails at each bank's own checkpoint, and per-gate settling, chain3 convention
    out, alleq = {}, True
    keys = ["VR1K1", "VR2K2", "VR3K3", "IZ1", "IZ2", "IPK1", "IPK2"] + \
           ["O%d_%dS" % (k, i) for k in (1, 2, 3) for i in range(8)]
    for k in keys:
        a, b = m.get(k), ref.get(k)
        eq = (a == b)
        alleq = alleq and eq
        out[k] = dict(mine=a, committed=b, identical=eq)
    st = {}
    for k in (1, 2, 3):
        rail = m["VR%dK%d" % (k, k)]
        up, dn = [], []
        for i in range(8):
            v = m["O%d_%dS" % (k, i)]
            hi = (i + k) % 2 == 1
            p = 100.0 * ((1.0 - v / rail) if hi else (v / rail))
            (dn if hi else up).append(p)
        st[k] = dict(rail_V=rail, pullup_min=min(up), pulldown_min=min(dn),
                     worst=min(min(up), min(dn)))
    return dict(digit_check_n=len(keys), all_digits_identical=alleq,
                mismatches={k: v for k, v in out.items() if not v["identical"]},
                per_bank_settling=st)


def cinv(dv=1.2, N=8):
    """MEASURED full-rail CMOS inverter: per-stage delay and per-cycle energy."""
    p = os.path.join(HERE, "cinv.cir")
    m = parse_mt0(p + ".mt0")
    hdr, rows = read_prn(p + ".prn")
    tr = {i: [(r[1] * 1e12, r[hdr.index("V(N%d)" % i)]) for r in rows]
          for i in range(N + 1)}
    res = dict(stage_delay_50pct_ps={}, stage_delay_90pct_ps={})
    # input rises at 100-120 ps: even nodes rise, odd nodes fall.  The window runs
    # to 399 ps -- the input's falling edge is at 400 ps, and the deepest stages of
    # the chain cross their thresholds only ~350-400 ps after it.
    for i in range(N + 1):
        rising = (i % 2 == 0)
        t50 = cross([(t, v) for t, v in tr[i] if 90 <= t <= 399], 0.5 * dv, rising)
        # 90% of the FINAL level: 0.9*dv for a rising node, 0.1*dv for a falling one
        thr = 0.9 * dv if rising else 0.1 * dv
        t90 = cross([(t, v) for t, v in tr[i] if 90 <= t <= 399], thr, rising)
        res.setdefault("_t50", {})[i] = t50
        res.setdefault("_t90", {})[i] = t90
    for i in range(1, N + 1):
        a, b = res["_t50"][i - 1], res["_t50"][i]
        if a is not None and b is not None:
            res["stage_delay_50pct_ps"][i] = b - a
        a, b = res["_t90"][i - 1], res["_t90"][i]
        if a is not None and b is not None:
            res["stage_delay_90pct_ps"][i] = b - a
    # stage 1 is driven by the ideal PWL ramp, so its slew is not the chain's.
    # Stages 2 onward carry the chain's own steady slew; those are the ones quoted.
    ok = [i for i in range(2, N + 1) if i in res["stage_delay_50pct_ps"]]
    mid = [res["stage_delay_50pct_ps"][i] for i in ok]
    res["stages_used"] = ok
    res["t_inv_50pct_mean_ps"] = sum(mid) / len(mid) if mid else None
    res["t_inv_50pct_spread_ps"] = (max(mid) - min(mid)) if mid else None
    # a rising stage output is a pMOS pull-up, a falling one an nMOS pull-down;
    # W_p/W_n = 1.51 is not the ratio that balances them, so they differ and BOTH
    # are reported -- a buffer pays one of each.
    res["t_inv_rise_ps"] = [res["stage_delay_50pct_ps"][i] for i in ok if i % 2 == 0]
    res["t_inv_fall_ps"] = [res["stage_delay_50pct_ps"][i] for i in ok if i % 2 == 1]
    ok9 = [i for i in range(2, N + 1) if i in res["stage_delay_90pct_ps"]]
    mid9 = [res["stage_delay_90pct_ps"][i] for i in ok9]
    res["t_inv_90pct_mean_ps"] = sum(mid9) / len(mid9) if mid9 else None
    res["t_buffer_50pct_ps"] = (2.0 * res["t_inv_50pct_mean_ps"]
                                if res["t_inv_50pct_mean_ps"] else None)
    # energy per inverter over a full hi+lo cycle (t0-referenced, 1F pedestal)
    en = {}
    for i in range(1, N + 1):
        q = (m["Q%dD" % i] - m["Q%dZ" % i]) * 1e15
        e = (m["E%dD" % i] - m["E%dZ" % i]) * 1e15
        en[i] = dict(Q_fC=q, E_fJ=e, C_eff_fF=q / dv if dv else None)
    res["per_inverter_hi_lo_cycle"] = en
    midE = [en[i]["E_fJ"] for i in ok]
    res["E_inv_hi_lo_mid_fJ"] = sum(midE) / len(midE)
    res["committed_reference_E_inv_fJ"] = 10.0831
    return res


def qpre(dv=1.2, c_ff=35.979):
    m = parse_mt0(os.path.join(HERE, "qpre.cir.mt0"))
    out = {}
    for nm in ("A", "B", "D"):
        q = (m["QPRE%s" % nm] - m["QPREZ"]) * 1e15
        e = (m["EPRE%s" % nm] - m["EPREZ"]) * 1e15
        out[nm] = dict(Q_fC=q, E_supply_fJ=e, V_res=m["VRES%s" % nm])
    q = out["D"]["Q_fC"]
    out["summary"] = dict(
        Q_precharge_fC=q, E_supply_fJ=out["D"]["E_supply_fJ"],
        E_stored_half_CV2_fJ=0.5 * c_ff * dv * dv,
        E_dissipated_fJ=out["D"]["E_supply_fJ"] - 0.5 * c_ff * dv * dv,
        C_implied_fF=q / dv, C_nominal_fF=c_ff,
        per_bit_E_supply_fJ=out["D"]["E_supply_fJ"] / 8.0,
        per_bit_E_dissipated_fJ=(out["D"]["E_supply_fJ"] - 0.5 * c_ff * dv * dv) / 8.0)
    return out


def rtrip(dv=1.2):
    """DC transfer curves of BOTH candidate restoring stages.  The trip point is the
    number that decides whether a restoring stage can read a QAL level at all, and
    the static supply current at that level is the contention cost of reading a
    half-swing input on a full rail.  Cross-checked against committed qal/bound/ H1
    (A1 std 1.12p/0.74n trip 0.6451630 V, I_static 8.780 uA at V_in 0.6759;
     A4 skew 0.15p/1.48n trip 0.4594805 V, I_static 0.0339 uA at V_in 0.6759)."""
    hdr, rows = read_prn(os.path.join(HERE, "rtrip.cir.prn"))
    ii = hdr.index("V(IN)")
    out = {}
    for tag, lab, ref_trip, ref_ist in (
            ("S", "std 1.12p/0.74n (pre-registered, REFUTED)", 0.6451630261834231,
             8.780026706089604),
            ("A", "skew 0.15p/1.48n (AMENDMENT A4)", 0.4594805, 0.033872832820352056)):
        i1, i2 = hdr.index("V(%sO1)" % tag), hdr.index("V(%sO2)" % tag)
        isup = hdr.index("I(V0%s)" % tag)
        tr1 = [(r[ii], r[i1]) for r in rows]
        # trip point: V_in where V_out1 crosses dV/2 (the committed definition)
        trip = cross(tr1, 0.5 * dv, False)
        def val(col, vin):
            best, bd = None, None
            for r in rows:
                d0 = abs(r[ii] - vin)
                if bd is None or d0 < bd:
                    bd, best = d0, r
            return best[col]
        out[tag] = dict(
            label=lab, trip_Vin_at_Vout_half_dV=trip,
            committed_trip_V=ref_trip,
            trip_rel_to_committed=(abs(trip - ref_trip) / ref_trip
                                   if trip else None),
            Vout1_at_0p6759=val(i1, 0.6759), Vout2_at_0p6759=val(i2, 0.6759),
            Istatic_at_0p6759_uA=abs(val(isup, 0.6759)) * 1e6,
            committed_Istatic_uA=ref_ist,
            Vout1_at_0p6007=val(i1, 0.6007), Vout2_at_0p6007=val(i2, 0.6007),
            Istatic_at_0p6007_uA=abs(val(isup, 0.6007)) * 1e6,
            Vout1_at_0p5763_family_worst=val(i1, 0.5763),
            Vout2_at_0p5763_family_worst=val(i2, 0.5763))
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    o = {}
    for nm, fn in (("ia_hop", ia_hop), ("ia_chain", ia_chain),
                   ("cinv", cinv), ("qpre", qpre), ("rtrip", rtrip)):
        if which in ("all", nm):
            try:
                o[nm] = fn()
            except Exception as e:                                   # noqa
                o[nm] = dict(error=repr(e))
    print(json.dumps(o, indent=1, default=str))
