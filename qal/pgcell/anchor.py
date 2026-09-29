#!/usr/bin/env python3
"""(b) ANCHOR THE HARNESS -- reproduce the o21ai result in THIS harness.

Two independent anchors, both pre-registered:

  A -- THE BANK ROW the brief quotes.  qal/dvopt/h_i0_o21_dv150.cir is copied
       BYTE-IDENTICAL (md5 recorded) into this directory and re-run under THIS
       run's own PYMS_VAE_CACHE.  Checked two ways: (1) waveform-vs-waveform
       against the committed .prn, column by column -- the strongest possible
       form, because if the waveform reproduces then every derived quantity
       does; (2) independent re-extraction here of VBEND, s_end, v_end and
       t_valid80/90 with code written in this file, compared against the
       committed row in dvopt/o21.json.

  B -- THE IDEAL-SUPPLY FLOOR.  The same 2-high pMOS stack against an ideal
       stepped supply at 0.60 / 1.00 / 1.50 V, which is the measurement that
       AMENDED "never settles" to "settles, but 3.1-3.5x slower than an
       inverter".  Committed: 715.433 / 177.001 / 116.458 ps and 99.78-99.99 %
       settled.  Plus the 1.2 V CMOS inverter reference (57.143 ps).
"""
import hashlib, json, os, shutil, sys, time
import pg

DV150 = "/usr/local/src/stat-sim/qal/dvopt/h_i0_o21_dv150.cir"
HI, LO = (0, 2, 4, 6), (1, 3, 5, 7)
REF_ROW = dict(VBEND=0.6076701932224732, t_hop_ps=67.31716163004057,
               VA_open=-0.17394619083354046, t_valid80_ps=515.148911,
               IPK_uA=1435.09869, s_end_min=82.988377554491)
REF_FLOOR = {0.60: 715.433, 1.00: 177.001, 1.50: 116.458}
REF_CMOS = 57.143
T0_CLOSE = 50.0   # ps, the committed probe/hop switch-CLOSE instant


def s_of(i, v, rail):
    if rail <= 0.05:          # banktank convention: the rail has not arrived yet
        return -1e9
    return (1.0 - v / rail) * 100.0 if i in HI else (v / rail) * 100.0


def valid_t(ts, outs, rail, frac):
    """first time at which ALL 8 outputs are within frac of the INSTANTANEOUS
    rail and stay there to the end -- the committed t_validXX convention."""
    n = len(ts)
    ok = [all(s_of(i, outs[i][k], rail[k]) >= frac * 100.0 for i in range(8))
          for k in range(n)]
    last_bad = -1
    for k in range(n):
        if not ok[k]:
            last_bad = k
    if last_bad == n - 1 or last_bad < 0 and not ok[0]:
        return None
    k = last_bad + 1
    if k >= n:
        return None
    if k == 0:
        return ts[0]
    # interpolate on the binding output's own crossing
    return ts[k]


def anchor_A():
    md5 = hashlib.md5(open(DV150, "rb").read()).hexdigest()
    dst = os.path.join(pg.HERE, "A_h_i0_o21_dv150.cir")
    shutil.copyfile(DV150, dst)
    assert hashlib.md5(open(dst, "rb").read()).hexdigest() == md5
    t0 = time.monotonic()
    if os.path.exists(dst + ".prn"):
        p = dst
        print("reusing existing %s.prn" % os.path.basename(dst))
    else:
        p = pg.run("A_h_i0_o21_dv150.cir", open(dst).read().splitlines(), timeout=1800)
    if p is None:
        return dict(status="RUN FAILED")
    wall = time.monotonic() - t0
    hdr, rows = pg.read_prn(p + ".prn")
    chdr, crows = pg.read_prn(DV150 + ".prn")

    # (1) waveform vs waveform
    wf = {}
    if chdr == hdr and len(crows) == len(rows):
        for c in range(1, len(hdr)):
            d = max(abs(rows[k][c] - crows[k][c]) for k in range(len(rows)))
            sc = max(abs(crows[k][c]) for k in range(len(rows))) or 1.0
            wf[hdr[c]] = dict(max_abs=d, max_rel=d / sc)
        wf_status = ("EXACT" if all(v["max_abs"] == 0.0 for v in wf.values())
                     else "max_rel %.3e" % max(v["max_rel"] for v in wf.values()))
    else:
        wf_status = ("SHAPE MISMATCH hdr=%s len=%d vs %d"
                     % (chdr == hdr, len(rows), len(crows)))

    # (2) independent re-extraction
    ts, bkb = pg.col(hdr, rows, "V(bkb)")
    outs = [pg.col(hdr, rows, "V(o%d)" % i)[1] for i in range(8)]
    _, ilt = pg.col(hdr, rows, "I(LT)")
    # TWO COMMITTED CONVENTIONS, both pinned by measurement against this very
    # waveform (see INSTRUMENT_NOTE in RESULTS):
    #  D-checkpoint: the committed extractor samples the END values at tend - 5 ps,
    #                not at the last printed row (the rail is still drooping).
    #  T0-reference: the committed t_validXX is referenced to the switch-CLOSE
    #                instant T0 = 50 ps, not to t = 0.
    TD = ts[-1] - 5.0
    vbend = pg.at_t(ts, bkb, TD)
    v_end = {"o%d" % i: pg.at_t(ts, outs[i], TD) for i in range(8)}
    s_end = {"o%d" % i: s_of(i, v_end["o%d" % i], vbend) for i in range(8)}
    t80 = valid_t(ts, outs, bkb, 0.80)
    t90 = valid_t(ts, outs, bkb, 0.90)
    t80 = None if t80 is None else t80 - T0_CLOSE
    t90 = None if t90 is None else t90 - T0_CLOSE
    ipk = max(abs(x) for x in ilt) * 1e6
    mine = dict(VBEND=vbend, t_valid80_ps=t80, t_valid90_ps=t90,
                IPK_uA=ipk, s_end_min=min(s_end.values()))
    cmp_ = {}
    for k, ref in (("VBEND", REF_ROW["VBEND"]), ("IPK_uA", REF_ROW["IPK_uA"]),
                   ("s_end_min", REF_ROW["s_end_min"]),
                   ("t_valid80_ps", REF_ROW["t_valid80_ps"])):
        m = mine[k]
        cmp_[k] = dict(mine=m, committed=ref,
                       rel=(abs(m - ref) / abs(ref)) if m is not None else None)
    cmp_["t_valid90_ps"] = dict(mine=t90, committed=None,
                                rel=0.0 if t90 is None else None)
    return dict(md5=md5, wall_s=round(wall, 1), waveform=wf_status,
                waveform_detail={k: v for k, v in list(wf.items())[:24]},
                extract=cmp_, v_end=v_end, s_end=s_end)


def floor_deck():
    """PART B: ideal stepped supply.  o21ai in its worst RISE vector (A1=A2=0,
    B1 high -> the 2-high pMOS series pull-up must raise Y), plus the inverter at
    the same supplies, plus the mandatory DC companion."""
    L = pg.head()
    pr, meta, ms = [], [], []
    for v in (0.60, 1.00, 1.50):
        tg = "o%d" % int(v * 100)
        L += ["VS%s s_%s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tg, tg, pg.TSTEP, pg.TSTEP + pg.EDGE, v),
              "VA1%s a1_%s 0 0" % (tg, tg), "VA2%s a2_%s 0 0" % (tg, tg),
              "VB1%s b1_%s 0 %.7f" % (tg, tg, v)]
        L += pg.o21ai_hand(tg, "y_" + tg, "a1_" + tg, "a2_" + tg, "b1_" + tg,
                           "s_" + tg, "0")
        pr.append("V(y_%s)" % tg); meta.append(dict(tag=tg, kind="o21ai", vdd=v))
        tg2 = "i%d" % int(v * 100)
        L += ["VS%s s_%s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tg2, tg2, pg.TSTEP, pg.TSTEP + pg.EDGE, v),
              "VI%s i_%s 0 0" % (tg2, tg2)]
        L += pg._inv(tg2, "y_" + tg2, "i_" + tg2, "s_" + tg2, "0")
        L += ["CL%s y_%s 0 %gf" % (tg2, tg2, pg.CL)]
        pr.append("V(y_%s)" % tg2); meta.append(dict(tag=tg2, kind="inv", vdd=v))
    cl, cn = pg.companion()
    L += cl; pr.append("V(%s)" % cn)
    meta.append(dict(tag="zc", kind="cmos_ref", vdd=1.2))
    L.append(".tran 0.02p %gp 0 0.05p" % (pg.TSTEP + 1200.0))
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L, meta


def anchor_B():
    L, meta = floor_deck()
    p = pg.run("A_floor_o21.cir", L, timeout=900)
    if p is None:
        return dict(status="RUN FAILED")
    hdr, rows = pg.read_prn(p + ".prn")
    out = {}
    for d in meta:
        node = "V(y_%s)" % d["tag"] if d["kind"] != "cmos_ref" else "V(o_zc)"
        ts, y = pg.col(hdr, rows, node)
        v = d["vdd"]
        if d["kind"] == "cmos_ref":
            t = pg.cross(ts, y, 0.9 * v, rise=True, t_from=pg.TSTEP)
        else:
            t = pg.cross(ts, y, 0.9 * v, rise=True, t_from=pg.TSTEP)
        out[d["tag"]] = dict(kind=d["kind"], vdd=v,
                             t90_ps=(t - pg.TSTEP) if t is not None else None,
                             v_end=y[-1], settled_pct=100.0 * y[-1] / v)
    chk = {}
    for v, ref in REF_FLOOR.items():
        t = out["o%d" % int(v * 100)]["t90_ps"]
        chk["o21_%.2f" % v] = dict(mine=t, committed=ref,
                                   rel=abs(t - ref) / ref if t else None)
    t = out["zc"]["t90_ps"]
    chk["cmos_1.2"] = dict(mine=t, committed=REF_CMOS, rel=abs(t - REF_CMOS) / REF_CMOS)
    for v in (0.60, 1.00, 1.50):
        a = out["o%d" % int(v * 100)]["t90_ps"]; b = out["i%d" % int(v * 100)]["t90_ps"]
        chk["ratio_o21_over_inv_%.2f" % v] = dict(o21=a, inv=b, ratio=a / b if b else None)
    return dict(rows=out, check=chk)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    res = {}
    if what in ("A", "both"):
        res["A_bank_row"] = anchor_A()
    if what in ("B", "both"):
        res["B_ideal_supply_floor"] = anchor_B()
    json.dump(res, open(os.path.join(pg.HERE, "ANCHOR_%s.json" % what), "w"), indent=1)
    print(json.dumps(res, indent=1)[:4000])
