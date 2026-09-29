#!/usr/bin/env python3
"""Extract the QAL->sync receiver DC result: trip point, output level at the
measured QAL high level, and the static contention current.  All MEASURED."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VQAL = 0.6758936      # MEASURED, tg15p_zcs VBEND
VQAL_WORST = 0.5763002  # MEASURED, tg60 VBEND (worst of the committed family)

RX = {   # tag: (label, out node, stage2 node or None, supply node, vdd)
    "A1": ("std 1.12p/0.74n @1.2V (campaign generic gate)", "OA1", "OB1", "VDA1", 1.2),
    "A2": ("skew 0.56p/0.74n @1.2V",                        "OA2", "OB2", "VDA2", 1.2),
    "A3": ("skew 0.28p/0.74n @1.2V",                        "OA3", "OB3", "VDA3", 1.2),
    "A4": ("skew 0.15p/1.48n @1.2V",                        "OA4", "OB4", "VDA4", 1.2),
    "B1": ("std 1.12p/0.74n @1.0V rail",                    "OB1A", None,  "VDB1", 1.0),
    "B2": ("std 1.12p/0.74n @0.9V rail",                    "OB2A", None,  "VDB2", 0.9),
    "B3": ("std 1.12p/0.74n @0.8V rail",                    "OB3A", None,  "VDB3", 0.8),
    "C1": ("longL 0.15p(L=0.5u)/1.48n @1.2V",               "OC1", "OC1B", "VDC1", 1.2),
}


def read_prn(path):
    rows, hdr = [], None
    for ln in open(path):
        p = ln.split()
        if hdr is None and p and p[0].lower() == "index":
            hdr = [h.upper() for h in p]
            continue
        if hdr and p and p[0][0].isdigit():
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                pass
    return hdr, rows


def main():
    path = os.path.join(HERE, "bd_dc.cir.prn")
    hdr, rows = read_prn(path)
    def col(nm):
        want = nm.upper()
        for i, h in enumerate(hdr):
            if h in ("V(" + want + ")", "I(" + want + ")", want):
                return i
        cand = [i for i, h in enumerate(hdr) if want in h]
        if not cand:
            raise KeyError("%s not in %s" % (nm, hdr))
        return cand[0]
    iv = col("IN")
    vin = [r[iv] for r in rows]

    def interp(cidx, v):
        for k in range(1, len(rows)):
            a, b = vin[k - 1], vin[k]
            if (a - v) * (b - v) <= 0 and a != b:
                f = (v - a) / (b - a)
                return rows[k - 1][cidx] + f * (rows[k][cidx] - rows[k - 1][cidx])
        return None

    def crossing(cidx, target):
        """V_in where column crosses target (first crossing, falling output)."""
        for k in range(1, len(rows)):
            y0, y1 = rows[k - 1][cidx], rows[k][cidx]
            if (y0 - target) * (y1 - target) <= 0 and y0 != y1:
                f = (target - y0) / (y1 - y0)
                return vin[k - 1] + f * (vin[k] - vin[k - 1])
        return None

    out = {}
    for tag, (lbl, o1, o2, isrc, vdd) in RX.items():
        c1 = col(o1)
        ci = col(isrc)
        d = dict(label=lbl, vdd=vdd)
        d["trip_Vin_at_Vout_half_VDD"] = crossing(c1, vdd / 2.0)
        d["Vout_at_QAL_high_0.6759"] = interp(c1, VQAL)
        d["Vout_at_worst_QAL_high_0.5763"] = interp(c1, VQAL_WORST)
        d["Vout_at_Vin_0"] = rows[0][c1]
        ii = interp(ci, VQAL)
        d["Istatic_at_QAL_high_uA"] = abs(ii) * 1e6 if ii is not None else None
        iiw = interp(ci, VQAL_WORST)
        d["Istatic_at_worst_QAL_high_uA"] = abs(iiw) * 1e6 if iiw is not None else None
        imax = max(abs(r[ci]) for r in rows)
        d["Ipeak_over_sweep_uA"] = imax * 1e6
        if o2:
            c2 = col(o2)
            d["Vout2_at_QAL_high"] = interp(c2, VQAL)
            d["Vout2_at_worst_QAL_high"] = interp(c2, VQAL_WORST)
        # static energy over one 293.245 ps QAL hold window
        if ii is not None:
            d["Estatic_over_293ps_hold_fJ"] = abs(ii) * vdd * 293.245e-12 * 1e15
        out[tag] = d
    js = os.path.join(HERE, "dc_rows.json")
    json.dump(out, open(js, "w"), indent=1)
    print(json.dumps(out, indent=1))
    print("\nwrote", js)


if __name__ == "__main__":
    main()
