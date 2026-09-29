#!/usr/bin/env python3
"""Analyse one fixture run: find the inductor current zero after HS turn-off,
read the ledger AT that zero (the ideal stopping point), and report Qdel/Qsup."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anal import Trace, P

FC = 1e-15

def zero_after(tr, name, t_from, t_to):
    """First downward zero crossing of `name` strictly after t_from (seconds)."""
    t = tr.t; y = tr.col(name)
    prev = None
    for i in range(len(t)):
        if t[i] < t_from or t[i] > t_to: continue
        if prev is not None and prev[1] > 0 and y[i] <= 0:
            # linear interpolation
            f = prev[1] / (prev[1] - y[i]) if (prev[1] - y[i]) != 0 else 0.0
            return prev[0] + f * (t[i] - prev[0])
        prev = (t[i], y[i])
    return None

def analyse(prn, meta):
    tr = Trace(prn)
    t0 = 0.5 * P
    t_hs_off = meta["t_hs_off"] * P
    tend = meta["tend"] * P
    tz = zero_after(tr, "I(LTU3)", t_hs_off, tend)
    t_read = tz if tz else tend
    # peak inductor current
    ipk = max(tr.col("I(LTU3)"))
    def q(e):
        return tr.integ(e, t0, t_read)
    qsup = -q("I(VTSUP)")
    qbank = q("I(VMBANK)")
    qbias = q("I(VMBIAS)")
    qout = q("I(VMTU3)")
    qfws = q("I(VMFWS3)")
    qhsd = q("I(VMHS3)")
    qfwd = q("I(VMFW3)")
    qcna = q("I(VMCNA3)")
    qind = q("I(LTU3)")
    qgtu = q("I(VGTU3)")
    qgfw = q("I(VGFW3)")
    # identities
    res_kcl = qhsd + qfwd - qind - qcna
    # rail
    v0 = tr.at("V(rail3)", t0)
    v_read = tr.at("V(rail3)", t_read)
    v_end = tr.at("V(rail3)", tend)
    na_min = min(tr.col("V(na3)"))
    # freewheel charge delivered during the HS-off phase (the buck's gain term)
    qfw_phase = -tr.integ("I(VMFWS3)", t_hs_off, t_read) if tz else 0.0
    # energies
    esup = -1.2 * q("I(VTSUP)")
    egd = tr.integ("I(VGTU3)", t0, t_read) * 0.0  # placeholder; see below
    return dict(
        prn=os.path.basename(prn), L=meta["L"], TON=meta["TON"], CB=meta["CB"],
        mode=meta["mode"],
        t_hs_off_ps=meta["t_hs_off"], t_zero_ps=(tz / P if tz else None),
        Ipk_uA=ipk * 1e6,
        Qsup_fC=qsup / FC, Qbank_fC=qbank / FC, Qout_fC=qout / FC,
        Qbias_fC=qbias / FC,
        Qdel_over_Qsup=(qbank / qsup) if qsup else None,
        Qout_over_Qsup=(qout / qsup) if qsup else None,
        Q_from_ground_during_freewheel_fC=qfw_phase / FC,
        Qhsd_fC=qhsd / FC, Qfwd_fC=qfwd / FC, Qfws_fC=qfws / FC,
        Qcna_fC=qcna / FC, Qind_fC=qind / FC,
        Qgtu_fC=qgtu / FC, Qgfw_fC=qgfw / FC,
        kcl_residual_fC=res_kcl / FC,
        kcl_residual_pct_Qsup=(100 * res_kcl / qsup) if qsup else None,
        V0=v0, V_at_zero=v_read, V_end=v_end,
        dV_mV=(v_read - v0) * 1e3,
        na3_min_V=na_min,
        E_supply_fJ=esup / 1e-15,
    )

if __name__ == "__main__":
    metaf = sys.argv[1]
    meta = json.load(open(metaf))
    out = {}
    for tag, m in sorted(meta.items()):
        prn = os.path.join(os.path.dirname(os.path.abspath(metaf)), tag + ".cir.prn")
        if not os.path.exists(prn):
            out[tag] = {"missing": prn}; continue
        try:
            out[tag] = analyse(prn, m)
        except Exception as e:
            out[tag] = {"error": str(e)}
    print(json.dumps(out, indent=1))
