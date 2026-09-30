#!/usr/bin/env python3
"""Aggregate runs/*/OUT.json into the deliverable tables (TABLES.json)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
T_CMOS, T_CORNER = 367.888, 467.888


def row_summary(d):
    th = d["th"]
    links = d["links"]
    hand = d["handoff"]
    ovs, margins, widths, commits, dies, raws = [], [], [], [], [], []
    for k in ("1", "2", "3", "4", "5"):
        for nn in ("2", "3", "4"):
            h = hand.get(k, {}).get(nn, {})
            if h.get("overlap_ps") is not None:
                ovs.append(h["overlap_ps"])
            m = h.get("margin_at_commit_mV") or {}
            for v in m.values():
                if v is not None:
                    margins.append(v)
    for k in list(links):
        for nn in ("2", "3", "4"):
            lk = links[k].get(nn, {})
            e = lk.get("0mV", {})
            if "width_ps" in e:
                widths.append(e["width_ps"])
            if lk.get("commit_raw_ps") is not None:
                srx = lk["srx_ps"]
                raws.append(round(lk["commit_raw_ps"] - (srx - th), 1))
            if lk.get("die_ps") is not None:
                dies.append(round(lk["die_ps"] - lk["srx_ps"], 1))
    a = d.get("acceptance", {})
    ch = d.get("charge_spec_reported_not_gated", {})
    qs = [v["Q_rise_fC"] for v in ch.values() if v.get("Q_rise_fC")]
    qf = [v["Q_fall_fC"] for v in ch.values() if v.get("Q_fall_fC") is not None]
    cb = []
    for k, rows in (d.get("crowbar") or {}).items():
        for r in rows:
            cb.append(r.get("Iph_pk_uA"))
    return dict(
        PASS=a.get("PASS", False), A=a.get("A_value"), B=a.get("B_eye"),
        C=a.get("C_handoff"),
        n_value_fail=d.get("value", {}).get("n_fail"),
        worst_margin_mV=a.get("worst_margin_at_commit_mV"),
        worst_overlap_ps=a.get("worst_overlap_ps"),
        eye_width_min_ps=round(min(widths), 1) if widths else None,
        eye_width_med_ps=round(sorted(widths)[len(widths) // 2], 1) if widths else None,
        die_minus_srx_med_ps=sorted(dies)[len(dies) // 2] if dies else None,
        commitraw_minus_slot_med_ps=sorted(raws)[len(raws) // 2] if raws else None,
        coupling_worst_mV=(d.get("coupling") or {}).get("worst_bump_LOW_mV"),
        Q_rise_fC_med=round(sorted(qs)[len(qs) // 2], 1) if qs else None,
        Q_fall_fC_med=round(sorted(qf)[len(qf) // 2], 1) if qf else None,
        Iph_trough_pk_uA=round(max(cb), 1) if cb else None,
        rising_lag=d.get("rising_lag_ps"))


def main():
    out = {}
    rd = os.path.join(HERE, "runs")
    for tag in sorted(os.listdir(rd)):
        oj = os.path.join(rd, tag, "OUT.json")
        if not os.path.exists(oj) or tag.startswith(("icb", "sawi")):
            continue
        d = json.load(open(oj))
        if d.get("error"):
            out[tag] = dict(ERROR=str(d["error"])[:120])
            continue
        out[tag] = row_summary(d)
        out[tag].update(wave=d["wave"], th=d["th"], d=d["d"], fly=d["fly"],
                        pat=d["pat"], rs=d["rs"])
    # frontier per (waveform-key, th)
    front = {}
    for tag, r in out.items():
        if "ERROR" in r or r["pat"] != "P0" or r["rs"] != 0.001:
            continue
        key = r["wave"] if r["wave"] == "sine" else "saw_f%g" % (100 * r["fly"])
        front.setdefault(key, {})
        th = r["th"]
        cur = front[key].setdefault(th, dict(max_d=0))
        if r["PASS"] and r["d"] > cur["max_d"]:
            cur["max_d"] = r["d"]
    for key in front:
        for th, cur in front[key].items():
            b = cur["max_d"]
            cur.update(ratio_headline=round(b * T_CMOS / (2 * th), 3),
                       ratio_corner=round(b * T_CORNER / (2 * th), 3),
                       ratio_chain_advance=round(b * T_CMOS / th, 3),
                       latency_per_level_ps=round(th / b, 2) if b else None)
    json.dump(dict(rows=out, frontier=front),
              open(os.path.join(HERE, "TABLES.json"), "w"), indent=1)
    # console table
    for key in sorted(front):
        print("== %s: th -> max_d (headline ratio)" % key)
        for th in sorted(front[key]):
            c = front[key][th]
            print("   th=%-4g d=%d ratio=%.2fx corner=%.2fx lat/level=%s" %
                  (th, c["max_d"], c["ratio_headline"], c["ratio_corner"],
                   c["latency_per_level_ps"]))
    print("\nper-row:")
    for tag in sorted(out):
        r = out[tag]
        if "ERROR" in r:
            print("%-26s ERROR %s" % (tag, r["ERROR"])); continue
        print("%-26s %s A=%s B=%s C=%s m=%-8s ov=%-8s eyeW=%-5s die=%-5s cr=%-5s Q=%s" %
              (tag, "PASS" if r["PASS"] else "fail", r["A"], r["B"], r["C"],
               r["worst_margin_mV"], r["worst_overlap_ps"], r["eye_width_min_ps"],
               r["die_minus_srx_med_ps"], r["commitraw_minus_slot_med_ps"],
               r["Q_rise_fC_med"]))


if __name__ == "__main__":
    main()
