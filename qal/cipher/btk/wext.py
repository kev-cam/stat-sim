#!/usr/bin/env python3
"""Per-row extraction for the WIRE study.  Conventions inherited VERBATIM from
qal/banktank/extract.py (per-gate settling at the bank's own stage boundary,
never aggregated; the data-pattern guard; the gate-drive-vs-Vt check; the
convention-free linear-tank energy) with the per-bank tank capacitance and the
wire terms added.

THE WIRE ENERGY SPLIT, and why it is computed by DIFFERENCE.

The only honest, convention-free statement of what a capacitor costs in this
topology is what the TANK permanently gave up, because the tank is a LINEAR
capacitor and 1/2 C (V0^2 - V1^2) needs no integrator and no sign convention:

    E_tank_lost(k)  =  1/2 C_t(k) (V_tnk(t0)^2 - V_tnk(return-open)^2)

So the incremental cost of the wire is

    dE_wire  =  sum_k [ E_tank_lost(k) | Cw ]  -  sum_k [ E_tank_lost(k) | Cw=0 ]

with every other element of the deck identical.  Every fixed overhead -- the
cell's own load, the gate drives, the switch loss, the baseline tank loss --
cancels exactly.  Against that:

    E_wire_stored  =  sum over the nodes that actually swing of 1/2 Cw V_peak^2
    E_wire_stranded=  sum over the same nodes of 1/2 Cw V_end^2

and the two bounds on recovery are

    recovered_best  = 1 - dE_wire / (2 * E_wire_stored)        stranded = RETAINED
    recovered_worst = 1 - (dE_wire + E_wire_stranded) / (2 * E_wire_stored)

The factor 2 is because a CMOS cycle of the same node costs Cw*V^2 = 2 * the
stored 1/2 Cw V^2 (half burnt on the way up, half on the way down), which is the
thing being compared against.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bt import MGATE, NBANK, EDGE, TAIL, CBANK, in_hi, out_hi, parse_mt0, read_prn
from btw import n_hi, ct_of, schedule, vtank0

SIGMA_FLOOR_MV = 6.44
VTN, VTP = 0.5239, 0.4403
FLOOR_V = VTN + VTP


def settle_pct(k, i, v, rail):
    return 100.0 * ((1.0 - v / rail) if in_hi(k, i) else (v / rail))


def guard_ok(k, i, v, rail):
    return (v <= 0.10 * rail) if in_hi(k, i) else (v >= 0.50 * rail)


def col(hdr, n):
    return hdr.index(n.upper())


def data_valid_instant(hdr, rows, k, t_from, t_to, thresh=90.0):
    ir = col(hdr, "V(RAIL%d)" % k)
    io = [col(hdr, "V(O%d_%d)" % (k, i)) for i in range(MGATE)]
    for r in rows:
        t = r[1] * 1e12
        if t < t_from or t > t_to:
            continue
        rail = r[ir]
        if rail <= 0.05:
            continue
        ok = True
        for i in range(MGATE):
            v = r[io[i]]
            if settle_pct(k, i, v, rail) < thresh or not guard_ok(k, i, v, rail):
                ok = False
                break
        if ok:
            return t
    return None


def extract(path, m, T, H, dv, mode, z, cw, wire_mode, ct_mode):
    mt = parse_mt0(path + ".mt0")
    hdr, rows = read_prn(path + ".prn")
    S = schedule(T, H, dv, z["tzr"], z["tzq"])
    nb = S["nbank"]
    vt0 = dv if mode == "vfull" else vtank0(m, dv)
    ct = {k: ct_of(k, m, cw, ct_mode) for k in range(1, nb + 1)}
    r = dict(deck=os.path.basename(path), m=m, T_ps=T, H=H, dv=dv, mode=mode,
             cw_fF=cw, wire_mode=wire_mode, ct_mode=ct_mode,
             C_tank_fF=ct, V_tank0=vt0, n_hi={k: n_hi(k) for k in ct},
             C_bank_loaded_fF={k: CBANK + (n_hi(k) * cw if cw > 0 else 0.0)
                               for k in ct},
             tzr=z["tzr"], tzq=z["tzq"], bound=S["bound"], tend=S["tend"])
    r["m_effective"] = {k: ct[k] / r["C_bank_loaded_fF"][k] for k in ct}
    r["tank_area_um2_per_chain_MIM"] = sum(ct.values()) / 1.5

    rail = {k: mt["VR%dB%d" % (k, k)] for k in range(1, nb + 1)}
    r["rail_at_own_boundary_V"] = rail
    r["rail_peak_V"] = {k: mt["VR%dPK" % k] for k in range(1, nb + 1)}
    r["rail_at_own_open_V"] = {k: mt["VR%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_t0_V"] = {k: mt["VT%dZ" % k] for k in range(1, nb + 1)}
    r["tank_after_rise_V"] = {k: mt["VT%dO%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_after_return_V"] = {k: mt["VT%dQ%d" % (k, k)] for k in range(1, nb + 1)}
    r["tank_end_V"] = {k: mt["VT%dD" % k] for k in range(1, nb + 1)}
    r["G7_level_restoring_pass"] = all(v > FLOOR_V for v in rail.values())
    r["rail_min_V"] = min(rail.values())

    # ---- per-gate settling + value check at each bank's own boundary
    st, pat, drv, sep = {}, {}, {}, {}
    for k in range(1, nb + 1):
        rk = rail[k]
        sk, pk_, dk, his, los = {}, {}, {}, [], []
        for i in range(MGATE):
            v = mt["O%d_%dB" % (k, i)]
            sk["o%d" % i] = settle_pct(k, i, v, rk) if rk > 0 else None
            pk_["o%d" % i] = dict(v=v, expect_hi=bool(out_hi(k, i)),
                                  guard=bool(guard_ok(k, i, v, rk)) if rk > 0 else False)
            (los if in_hi(k, i) else his).append(v)
            if k > 1:
                vin = mt["N%d_%dB" % (k, i)]
                dk["o%d" % i] = (dict(vin=vin, dev="nmos", overdrive_V=vin - VTN)
                                 if in_hi(k, i) else
                                 dict(vin=vin, dev="pmos", overdrive_V=rk - vin - VTP))
        st[k], pat[k], drv[k] = sk, pk_, dk
        sep[k] = dict(min_HIGH_V=min(his), max_LOW_V=max(los),
                      separation_mV=1000.0 * (min(his) - max(los)))
    r["settling_pct_per_gate"] = st
    r["value_check_per_gate"] = pat
    r["gate_drive_per_gate"] = drv
    r["separation_by_depth"] = sep
    r["worst_gate_pct"] = min(v for k in st for v in st[k].values() if v is not None)
    r["worst_gate_where"] = min(((v, k, g) for k in st for g, v in st[k].items()
                                 if v is not None))[1:]
    r["per_bank_worst_pct"] = {k: min(v for v in st[k].values() if v is not None)
                               for k in st}
    r["value_check_all_pass"] = all(pat[k][g]["guard"] for k in pat for g in pat[k])
    r["value_fail_list"] = [(k, g) for k in pat for g in pat[k]
                            if not pat[k][g]["guard"]]
    r["A1_settling_pass_90"] = r["worst_gate_pct"] >= 90.0
    r["A2_value_pass"] = r["value_check_all_pass"]
    r["PASS_committed_bars"] = bool(r["A1_settling_pass_90"] and r["A2_value_pass"])
    r["separation_min_mV"] = min(sep[k]["separation_mV"] for k in sep)
    r["G8_separation_pass"] = (r["separation_min_mV"] >= SIGMA_FLOOR_MV and
                               all(sep[k]["separation_mV"] > 0 for k in sep))

    # ---- MEASURED data-valid instants and the directly measured stage time
    dvt = {k: data_valid_instant(hdr, rows, k, S["c"][k], S["tend"] - TAIL / 2)
           for k in range(1, nb + 1)}
    r["data_valid_instant_ps"] = dvt
    r["steady_state_stage_time_ps"] = {
        "%d_minus_%d" % (k, k - 1): ((dvt[k] - dvt[k - 1])
                                     if (dvt[k] and dvt[k - 1]) else None)
        for k in range(2, nb + 1)}
    r["stage_time_deepest_ps"] = (dvt[nb] - dvt[nb - 1]) \
        if (dvt[nb] and dvt[nb - 1]) else None
    r["all_banks_reach_valid"] = all(dvt[k] is not None for k in dvt)
    r["t_hop_measured_rise_ps"] = {k: z["tzr"][k - 1] for k in range(1, nb + 1)}
    r["t_hop_measured_return_ps"] = {k: z["tzq"][k - 1] for k in range(1, nb + 1)}

    # ---- instrument gates
    r["IZ_uA"] = {k: 1e6 * mt["IZ%d" % k] for k in range(1, nb + 1)}
    r["IZQ_uA"] = {k: 1e6 * mt["IZQ%d" % k] for k in range(1, nb + 1)}
    r["IPK_uA"] = {k: 1e6 * mt["IPK%d" % k] for k in range(1, nb + 1)}
    r["G2_zcs_pass"] = all(abs(v) <= 1.0 for v in r["IZ_uA"].values()) and \
                       all(abs(v) <= 1.0 for v in r["IZQ_uA"].values())

    # ---- energy
    def g(tag, ck):
        return (mt["%s_%s" % (tag.upper(), ck)] - mt["%s_Z" % tag.upper()]) * 1e15

    en = {}
    for k in range(1, nb + 1):
        o, q, rc = "O%d" % k, "Q%d" % k, "R%d" % k
        ea_o, eb_o = g("ea%d" % k, o), g("eb%d" % k, o)
        esw_o, er_o = g("esw%d" % k, o), g("er%d" % k, o)
        v0, v1, v2 = mt["VT%dZ" % k], mt["VT%dQ%d" % (k, k)], mt["VT%dD" % k]
        en[k] = dict(
            E_out_of_tank_rise_fJ=ea_o, E_into_rail_rise_fJ=eb_o,
            E_seriesR_rise_fJ=er_o, E_switchblock_rise_fJ=esw_o - eb_o,
            path_identity_rise_fJ=ea_o - esw_o - er_o,
            E_back_into_tank_return_fJ=-(g("ea%d" % k, q) - g("ea%d" % k, rc)),
            E_seriesR_return_fJ=g("er%d" % k, q) - g("er%d" % k, rc),
            tank_dV_over_cycle_mV=1000.0 * (v0 - v1),
            tank_energy_lost_fJ=0.5 * ct[k] * (v0 * v0 - v1 * v1),
            tank_energy_lost_to_end_fJ=0.5 * ct[k] * (v0 * v0 - v2 * v2),
            E_out_of_tank_whole_run_fJ=g("ea%d" % k, "D"))
        en[k]["tank_closure_residual_fJ"] = en[k]["E_out_of_tank_whole_run_fJ"] - \
            en[k]["tank_energy_lost_to_end_fJ"]
        en[k]["recycle_fraction_pct"] = (
            100.0 * en[k]["E_back_into_tank_return_fJ"] / en[k]["E_into_rail_rise_fJ"]
            if en[k]["E_into_rail_rise_fJ"] else None)
    r["energy_per_bank"] = en
    r["E_tank_lost_chain_fJ"] = sum(en[k]["tank_energy_lost_fJ"] for k in en)
    r["E_tank_lost_chain_to_end_fJ"] = sum(en[k]["tank_energy_lost_to_end_fJ"]
                                           for k in en)
    r["E_gate_drive_total_fJ"] = g("egt", "D")
    r["E_vhi_total_fJ"] = g("ehi", "D")
    r["G3_path_identity_pass"] = all(
        abs(en[k]["path_identity_rise_fJ"]) <= 0.01 * abs(en[k]["E_out_of_tank_rise_fJ"])
        for k in en if en[k]["E_out_of_tank_rise_fJ"])

    # ---- the WIRE's own stored / stranded energy (linear cap, no integrator)
    if cw > 0.0:
        wl = {}
        tot_pk = tot_end = 0.0
        for k in range(1, nb + 1):
            if wire_mode == "rail":
                vpk, vend = mt["VR%dPK" % k], mt["VR%dD" % k]
                nn = n_hi(k)
                e_pk = 0.5 * nn * cw * vpk ** 2
                e_end = 0.5 * nn * cw * vend ** 2
                wl[k] = dict(n_swinging=nn, V_peak=vpk, V_end=vend,
                             E_stored_peak_fJ=e_pk, E_stranded_end_fJ=e_end)
            else:
                e_pk = e_end = 0.0
                det = {}
                for i in range(MGATE):
                    if not out_hi(k, i):
                        continue          # pull-down node: never charged
                    vpk = mt["W%d_%dP" % (k, i)]
                    vend = mt["O%d_%dE" % (k, i)]
                    e_pk += 0.5 * cw * vpk ** 2
                    e_end += 0.5 * cw * vend ** 2
                    det["o%d" % i] = dict(V_peak=vpk, V_end=vend)
                wl[k] = dict(n_swinging=n_hi(k), per_node=det,
                             E_stored_peak_fJ=e_pk, E_stranded_end_fJ=e_end)
            tot_pk += wl[k]["E_stored_peak_fJ"]
            tot_end += wl[k]["E_stranded_end_fJ"]
        r["wire_per_bank"] = wl
        r["E_wire_stored_peak_chain_fJ"] = tot_pk
        r["E_wire_stranded_end_chain_fJ"] = tot_end
        r["E_CMOS_reference_same_wire_fJ"] = 2.0 * tot_pk   # Cw*V^2 per cycle
    return r


if __name__ == "__main__":
    import btw
    a = sys.argv[1:]
    m, T, H, dv, mode = float(a[0]), float(a[1]), int(a[2]), float(a[3]), a[4]
    cw, wm, cm = float(a[5]), a[6], a[7]
    z = json.load(open(os.path.join(HERE, a[8])))
    tag = btw.rowtag(m, T, H, dv, mode, cw, wm, cm)
    path = os.path.join(HERE, "c_%s.cir" % tag)
    r = extract(path, m, T, H, dv, mode, z, cw, wm, cm)
    open(os.path.join(HERE, "row_%s.json" % tag), "w").write(
        json.dumps(r, indent=1, default=str))
    print("%s  worst=%.3f%% val=%s sep=%.3fmV railmin=%.4f G2=%s G3=%s "
          "Etank=%.3f fJ" %
          (tag, r["worst_gate_pct"], r["A2_value_pass"], r["separation_min_mV"],
           r["rail_min_V"], r["G2_zcs_pass"], r["G3_path_identity_pass"],
           r["E_tank_lost_chain_fJ"]))
