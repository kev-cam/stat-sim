#!/usr/bin/env python3
"""A5 -- BOTH instrument anchors, digit-checked in THIS directory under MY OWN
PYMS_VAE_CACHE, from md5-verified BYTE-IDENTICAL copies of the committed decks.

  (a) the committed robust single-hop point (qal/lsweep/h_L15_W30_dv120.cir and
      p_L15_W30_dv120.cir): t_hop 65.49500982344826 ps, VBEND 0.7138163,
      VBPK 0.8368896, 8/8 cells settled.
  (b) the skiptu CLAMP row's attributable stage-2 damage: free 0.438143 V ->
      clamp 0.551708 V = +113.565 mV, from
      qal/skiptu/r_s4_free_T200_dv1200_L5_W10_t12_f0.cir and
      qal/skiptu/r_s4_rtu_T200_dv1200_L1_W10_t20_f0.cir.

If either fails, nothing else in this run reports.
"""
import json, os
import tf

HERE = tf.HERE
REF = {"TZ_ps": 65.49500982344826, "VBEND": 0.7138163, "VBPK": 0.8368896,
       "IZ_uA": -0.0004958676}
T0_CLOSE = 50.0
CLAMP_REF = {"free_max_LOW_V": 0.438143, "clamp_max_LOW_V": 0.551708,
             "damage_mV": 113.565,
             "free_rail3_V": 0.765884, "clamp_rail3_V": 1.069085}


def anchor_a(out):
    m = tf.parse_mt0(os.path.join(HERE, "instr_anchor.cir.mt0"))
    hdr, rows = tf.read_prn(os.path.join(HERE, "instr_probe.cir.prn"))
    icol = [c for c in hdr if c.startswith("I(L")][0]
    tz_abs, pk = tf.zero_after_peak(hdr, rows, icol, 0.0)
    tz = tz_abs - T0_CLOSE
    a = dict(t_hop_ps=dict(mine=round(tz, 8), committed=REF["TZ_ps"],
                           mine_absolute_ps=round(tz_abs, 8),
                           switch_close_ps=T0_CLOSE,
                           rel=abs(tz - REF["TZ_ps"]) / REF["TZ_ps"]),
             IPK_uA_from_prn=round(pk * 1e6, 4))
    for k in ("VBEND", "VBPK"):
        if k in m:
            a[k] = dict(mine=m[k], committed=REF[k],
                        rel=abs(m[k] - REF[k]) / abs(REF[k]))
    if "IZ" in m:
        a["IZ_uA"] = dict(mine=m["IZ"] * 1e6, committed=REF["IZ_uA"],
                          rel=abs(m["IZ"] * 1e6 - REF["IZ_uA"]) / abs(REF["IZ_uA"]))
    theirs = tf.parse_mt0("/usr/local/src/stat-sim/qal/lsweep/h_L15_W30_dv120.cir.mt0")
    shared = sorted(set(m) & set(theirs))
    ident, worst, worstk = 0, 0.0, None
    for k in shared:
        x, y = m[k], theirs[k]
        if x == y:
            ident += 1; continue
        d = abs(x - y) / max(abs(x), abs(y), 1e-30)
        if d > worst:
            worst, worstk = d, k
    a["mt0_keys_compared"] = len(shared)
    a["mt0_keys_BIT_IDENTICAL"] = ident
    a["mt0_worst_rel"] = worst
    a["mt0_worst_key"] = worstk
    vr, cells, w = m.get("VBEND"), {}, 100.0
    for i in range(8):
        vo = m.get("O%dE" % i)
        if vo is None or not vr:
            continue
        f = (1.0 - vo / vr) if (i % 2 == 0) else (vo / vr)
        cells[i] = dict(kind="pulldown" if i % 2 == 0 else "pullup", v_o=vo,
                        settle_pct=100.0 * f)
        w = min(w, 100.0 * f)
    a["cells"] = cells
    a["cells_measured"] = len(cells)
    a["cells_worst_settle_pct"] = w
    a["PASS"] = (a["t_hop_ps"]["rel"] < 1e-6 and a.get("VBEND", {}).get("rel", 1) < 1e-6
                 and a.get("VBPK", {}).get("rel", 1) < 1e-6
                 and len(cells) == 8 and w >= 99.9)
    out["anchor_a_single_hop"] = a
    return a["PASS"]


def stage2_max_low(mt0):
    """The committed convention: stage 2's pull-DOWN outputs at bank 2's own
    boundary.  In the skiptu s4 harness bank k cell i is a pull-DOWN cell iff
    (i+k) is odd, so bank 2's pull-downs are the ODD i."""
    vs = [mt0["O2_%dS" % i] for i in range(8) if ("O2_%dS" % i) in mt0
          and (i + 2) % 2 == 1]
    return max(vs) if vs else None


def anchor_b(out):
    mf = tf.parse_mt0(os.path.join(HERE, "instr_free.cir.mt0"))
    mc = tf.parse_mt0(os.path.join(HERE, "instr_clamp.cir.mt0"))
    lf, lc = stage2_max_low(mf), stage2_max_low(mc)
    b = dict(free_max_LOW_V=lf, clamp_max_LOW_V=lc,
             committed_free=CLAMP_REF["free_max_LOW_V"],
             committed_clamp=CLAMP_REF["clamp_max_LOW_V"],
             damage_mV=(None if (lf is None or lc is None) else (lc - lf) * 1e3),
             committed_damage_mV=CLAMP_REF["damage_mV"],
             free_rail3_V=mf.get("VR3K3"), clamp_rail3_V=mc.get("VR3K3"),
             committed_free_rail3_V=CLAMP_REF["free_rail3_V"],
             committed_clamp_rail3_V=CLAMP_REF["clamp_rail3_V"])
    if b["damage_mV"] is not None:
        b["damage_err_mV"] = abs(b["damage_mV"] - CLAMP_REF["damage_mV"])
        b["PASS"] = b["damage_err_mV"] < 1.0
    else:
        b["PASS"] = False
    b["_NOTE_on_the_committed_convention"] = (
        "the committed 'free' control deck instantiates NO top-up device on banks "
        "3 and 4 at all, while the clamp deck instantiates one AND fires it.  So "
        "the committed +113.565 mV conflates the top-up EXISTING with the top-up "
        "FIRING.  chain3 measured that merely having the gate present shifts "
        "t_zcs by +11.5 ps and VBEND2 by -43.4 mV, so the conflation is not "
        "negligible.  Every free control in qal/tankfed carries the top-up "
        "devices PHYSICALLY PRESENT and parked off, which isolates the firing "
        "term.  This anchor is reproduced on the committed convention so the "
        "instrument is anchored; the run's own numbers use the stricter one.")
    out["anchor_b_clamp_damage"] = b
    return b["PASS"]


def main():
    out = {"_what": "A5 instrument gate for qal/tankfed",
           "_cache": tf.CACHE,
           "_decks": "instr_anchor.cir / instr_probe.cir are md5-identical to "
                     "qal/lsweep/h_L15_W30_dv120.cir / p_L15_W30_dv120.cir; "
                     "instr_free.cir / instr_clamp.cir are md5-identical to "
                     "qal/skiptu/r_s4_free_T200_dv1200_L5_W10_t12_f0.cir / "
                     "r_s4_rtu_T200_dv1200_L1_W10_t20_f0.cir"}
    ok = []
    for fn, f in (("a", anchor_a), ("b", anchor_b)):
        try:
            ok.append(f(out))
        except Exception as e:
            out["anchor_%s_error" % fn] = "%s: %s" % (type(e).__name__, e)
            ok.append(False)
    out["VERDICT"] = "PASS, digit-checked" if all(ok) else "FAIL"
    json.dump(out, open(os.path.join(HERE, "INSTRUMENT.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
