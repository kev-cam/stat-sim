#!/usr/bin/env python3
"""Per-row extraction for the QAL SHA-256 BLOCK.

Conventions VERBATIM from qal/banktank/extract.py (which inherits skip4 /chain3/
lsweep/swsweep/gateb):
  * per-gate settling at the gate's OWN bank boundary, NEVER aggregated:
      expected-LOW  output: pct = 100*(1 - V(o)/rail_k)
      expected-HIGH output: pct = 100*(V(o)/rail_k)
  * data-pattern guard: expected-LOW <= 0.10*rail_k, expected-HIGH >= 0.50*rail_k
  * separation by depth against the 6.44 mV 1-sigma floor
  * energy from 1 F integrators only, every read t0-referenced at the Z checkpoint
THE ONE DIFFERENCE: the expected value of a gate is not 'this bank is an inverter
chain', it is the value an INDEPENDENT Python evaluation of the netlist gives for
the pre-registered input vector.  Settling alone is not correctness.
"""
import json, os, sys
import bt
import blk

HERE = blk.HERE
N = blk.N
SIGMA_FLOOR_MV = 6.44


def extract(tag):
    meta = json.load(open(os.path.join(HERE, "ROWMETA_%s.json" % tag)))
    pfx = "k_" if meta.get("buck") else "b_"
    mt = bt.parse_mt0(os.path.join(HERE, "%s%s.cir.mt0" % (pfx, tag)))
    cb = json.load(open(os.path.join(HERE, "CBANK_dv%g.json" % (meta["dv"] * 1000))))
    D, m, dv, T = N["D"], meta["m"], meta["dv"], meta["T"]
    S = meta["sched"]
    r = dict(tag=tag, m=m, T_ps=T, dv=dv, lmode=meta["lmode"], L_ref=meta["L_ref"],
             H={int(k): v for k, v in meta["H"].items()},
             cells=len(N["cells"]), depth=D,
             profile=[len(N["banks"][k]) for k in range(1, D + 1)])
    r["C_bank_fF"] = {k: cb[str(k)]["C_bank_fF"] for k in range(1, D + 1)}
    r["C_tank_fF"] = {k: m * cb[str(k)]["C_bank_fF"] for k in range(1, D + 1)}
    r["V_tank0"] = bt.vtank0(m, dv)

    rail = {k: mt["VR%dB%d" % (k, k)] for k in range(1, D + 1)}
    r["rail_at_own_boundary_V"] = rail
    r["rail_peak_V"] = {k: mt["VR%dPK" % k] for k in range(1, D + 1)}
    r["rail_at_own_open_V"] = {k: mt["VR%dO%d" % (k, k)] for k in range(1, D + 1)}
    r["tank_t0_V"] = {k: mt["VT%dZ" % k] for k in range(1, D + 1)}
    r["tank_after_rise_V"] = {k: mt["VT%dO%d" % (k, k)] for k in range(1, D + 1)}
    r["tank_after_return_V"] = {k: mt["VT%dQ%d" % (k, k)] for k in range(1, D + 1)}
    r["tank_end_V"] = {k: mt["VT%dD" % k] for k in range(1, D + 1)}
    r["rail_depth_spread_mV"] = 1000.0 * (max(rail.values()) - min(rail.values()))

    # ---------------- per-gate settling + VALUE check, all 161 gates
    st, pat, sep = {}, {}, {}
    for k in range(1, D + 1):
        rk = rail[k]
        sk, pk_, his, los = {}, {}, [], []
        for j, cn in enumerate(N["banks"][k]):
            exp_hi = bool(N["val"][N["cells"][cn]["out"]])
            v = mt["G%d_%dB" % (k, j)]
            sk[cn] = (100.0 * (v / rk) if exp_hi else 100.0 * (1.0 - v / rk)) \
                if rk > 0 else None
            guard = (v >= 0.50 * rk) if exp_hi else (v <= 0.10 * rk)
            pk_[cn] = dict(v=v, expect_hi=exp_hi, typ=N["cells"][cn]["typ"],
                           guard=bool(guard) if rk > 0 else False,
                           v_end=mt["G%d_%dD" % (k, j)])
            (his if exp_hi else los).append(v)
        st[k], pat[k] = sk, pk_
        sep[k] = dict(min_HIGH_V=(min(his) if his else None),
                      max_LOW_V=(max(los) if los else None),
                      n_hi=len(his), n_lo=len(los),
                      separation_mV=(1000.0 * (min(his) - max(los))
                                     if his and los else None))
    r["settling_pct_per_gate"] = st
    r["value_check_per_gate"] = pat
    r["separation_by_depth"] = sep
    r["n_gates_checked"] = sum(len(v) for v in pat.values())

    r["worst_gate_pct"] = min(v for k in st for v in st[k].values() if v is not None)
    r["worst_gate_where"] = min(((v, k, gn) for k in st for gn, v in st[k].items()
                                 if v is not None))[1:]
    r["per_bank_worst_pct"] = {k: min(v for v in st[k].values() if v is not None)
                               for k in st}
    r["value_fail_list"] = [[k, gn, round(pat[k][gn]["v"], 6),
                             pat[k][gn]["expect_hi"], pat[k][gn]["typ"]]
                            for k in pat for gn in pat[k] if not pat[k][gn]["guard"]]
    r["value_check_all_pass"] = not r["value_fail_list"]
    r["n_value_fail"] = len(r["value_fail_list"])
    r["value_fails_by_bank"] = {k: sum(1 for gn in pat[k] if not pat[k][gn]["guard"])
                                for k in pat}
    r["A1_settling_pass_90"] = r["worst_gate_pct"] >= 90.0
    r["A2_value_pass"] = r["value_check_all_pass"]
    seps = [sep[k]["separation_mV"] for k in sep if sep[k]["separation_mV"] is not None]
    r["separation_min_mV"] = min(seps) if seps else None
    r["A5_fade_pass"] = bool(seps and min(seps) >= SIGMA_FLOOR_MV)

    # ---------------- PRIMARY OUTPUT correctness: the block's actual answer
    po = {}
    for nm in ("maj", "ch", "sum"):
        bits, ok = 0, True
        for i in range(8):
            net = "%s[%d]" % (nm, i)
            cn = N["drv"][net]
            k = N["lvl"][cn]
            j = N["banks"][k].index(cn)
            v = mt["G%d_%dD" % (k, j)]          # at the END of the run
            rk = r["rail_peak_V"][k]
            b = 1 if v >= 0.5 * rk else 0
            bits |= b << i
            ok = ok and (b == N["val"][net])
        po[nm] = dict(measured=hex(bits), expected=hex(
            sum(N["val"]["%s[%d]" % (nm, i)] << i for i in range(8))), correct=ok)
    r["primary_outputs"] = po
    r["A2b_block_answer_correct"] = all(po[x]["correct"] for x in po)
    r["PASS"] = bool(r["A1_settling_pass_90"] and r["A2_value_pass"])

    # ---------------- instrument gates
    r["IZ_uA"] = {k: 1e6 * mt["IZ%d" % k] for k in range(1, D + 1)}
    r["IZQ_uA"] = {k: 1e6 * mt["IZQ%d" % k] for k in range(1, D + 1)}
    r["IPK_uA"] = {k: 1e6 * mt["IPK%d" % k] for k in range(1, D + 1)}
    r["A6_zcs_pass"] = (all(abs(v) <= 1.0 for v in r["IZ_uA"].values()) and
                        all(abs(v) <= 1.0 for v in r["IZQ_uA"].values()))
    r["A6_worst_uA"] = max(max(abs(v) for v in r["IZ_uA"].values()),
                           max(abs(v) for v in r["IZQ_uA"].values()))
    r["A6_worst_rise_uA"] = max(abs(v) for v in r["IZ_uA"].values())
    r["A6_worst_return_uA"] = max(abs(v) for v in r["IZQ_uA"].values())
    # what the residual is PHYSICALLY worth: the energy still in the inductor at the
    # instant the switch opens, 1/2 L I^2, summed over every commanded open.  The
    # <=1 uA gate is an instrument standard; this is the consequence.
    lnh = {k: blk.L_of(k, cb, meta["lmode"], meta["L_ref"]) for k in range(1, D + 1)}
    r["A6_trapped_energy_fJ"] = sum(
        0.5 * lnh[k] * 1e-9 * ((r["IZ_uA"][k] * 1e-6) ** 2 +
                               (r["IZQ_uA"][k] * 1e-6) ** 2) * 1e15
        for k in range(1, D + 1))

    # ---------------- ENERGY (1 F integrators, t0-referenced, fJ)
    def g(tag_, ck):
        return (mt["%s_%s" % (tag_.upper(), ck)] - mt["%s_Z" % tag_.upper()]) * 1e15

    en, tot_tank_loss = {}, 0.0
    for k in range(1, D + 1):
        o, q, rc = "O%d" % k, "Q%d" % k, "R%d" % k
        ea_o, eb_o, esw_o, er_o = (g("ea%d" % k, o), g("eb%d" % k, o),
                                   g("esw%d" % k, o), g("er%d" % k, o))
        ct_fF = r["C_tank_fF"][k]
        v0, v1, v2 = mt["VT%dZ" % k], mt["VT%dQ%d" % (k, k)], mt["VT%dD" % k]
        loss_cycle = 0.5 * ct_fF * (v0 * v0 - v1 * v1)
        loss_end = 0.5 * ct_fF * (v0 * v0 - v2 * v2)
        tot_tank_loss += loss_end
        en[k] = dict(
            E_out_of_tank_rise_fJ=ea_o, E_into_rail_rise_fJ=eb_o,
            E_seriesR_rise_fJ=er_o, E_switchblock_rise_fJ=esw_o - eb_o,
            path_identity_rise_fJ=ea_o - esw_o - er_o,
            E_back_into_tank_return_fJ=-(g("ea%d" % k, q) - g("ea%d" % k, rc)),
            E_out_of_rail_return_fJ=-(g("eb%d" % k, q) - g("eb%d" % k, rc)),
            tank_dV_over_cycle_mV=1000.0 * (v0 - v1),
            tank_energy_lost_fJ=loss_cycle,
            tank_dV_to_end_mV=1000.0 * (v0 - v2),
            tank_energy_lost_to_end_fJ=loss_end,
            E_out_of_tank_whole_run_fJ=g("ea%d" % k, "D"),
            tank_closure_residual_fJ=g("ea%d" % k, "D") - loss_end,
            recycle_fraction_pct=(100.0 * (-(g("ea%d" % k, q) - g("ea%d" % k, rc)))
                                  / eb_o if eb_o else None))
    r["energy_per_bank"] = en
    r["A6_path_identity_pass"] = all(
        abs(en[k]["path_identity_rise_fJ"]) <= 0.01 * abs(en[k]["E_out_of_tank_rise_fJ"])
        for k in en if en[k]["E_out_of_tank_rise_fJ"])

    r["E_tank_loss_total_fJ"] = tot_tank_loss
    r["E_gate_drive_total_fJ"] = g("egt", "D")
    r["E_vhi_total_fJ"] = g("ehi", "D")
    r["E_primary_inputs_fJ"] = g("ei", "D")
    r["Q_primary_inputs_fC"] = g("qi", "D")

    # THE HEADLINE ENERGY LEDGER.
    #
    # AMENDMENT P2-R7.  An earlier version of this function summed abs() of the
    # gate-drive and VHI integrals into the total.  Both are NEGATIVE under the
    # committed sign convention (-V*I(Vsrc) is POSITIVE when the source delivers),
    # i.e. those ideal sources are net ABSORBING, and taking abs() booked a credit
    # as a cost.  Every such term is now reported RAW, BY SIGN, and is NOT folded
    # into a total -- exactly as the committed banktank analyse.py reports them.
    #
    # THE ONE CONVENTION-FREE NUMBER is the tank energy, because C_tank is a LINEAR
    # capacitor: 1/2 C (V0^2 - V1^2) needs no integrator convention at all.  That is
    # what the operation costs the timing hardware's energy store, and it is the
    # headline.
    V0 = r["V_tank0"]
    per_op_tank = sum(0.5 * r["C_tank_fF"][k] *
                      (V0 * V0 - mt["VT%dQ%d" % (k, k)] ** 2) for k in range(1, D + 1))
    r["E_per_op_TANK_MEASURED_fJ"] = per_op_tank
    r["ENERGY_LEDGER_fJ"] = {
        "tank_energy_taken_per_operation_MEASURED": per_op_tank,
        "tank_energy_lost_to_end_of_run": tot_tank_loss,
        "switch_gate_drive_all_banks_RAW_signed": r["E_gate_drive_total_fJ"],
        "vhi_rail_RAW_signed": r["E_vhi_total_fJ"],
        "primary_input_sources_RAW_signed_BOOKING": r["E_primary_inputs_fJ"],
    }
    r["_ledger_note"] = (
        "the three RAW_signed rows are NEGATIVE, i.e. those ideal sources ABSORB "
        "net energy over the run: ideal PWL gate drivers recover their gate charge, "
        "which a real driver does not. They are BOOKINGS and they make every total "
        "below a LOWER BOUND.")
    r["E_per_op_fJ_timing_hw_included"] = per_op_tank
    r["E_per_op_fJ_logic_and_tanks_only"] = per_op_tank

    # ---------------- the FIXED buck top-up, when present
    if meta.get("buck"):
        q = g("qbk", "D")                    # fC out of the buck supply
        e = g("ebk", "D")                    # fJ out of the buck supply
        egb = abs(g("egb", "D"))             # buck gate-drive energy
        stored = 0.0
        for k in range(1, D + 1):
            v_q, v_d = mt["VT%dQ%d" % (k, k)], mt["VT%dD" % k]
            stored += 0.5 * r["C_tank_fF"][k] * (v_d * v_d - v_q * v_q)
        r["BUCK"] = dict(
            Q_supply_fC=q, E_supply_fJ=e, E_gate_drive_fJ=egb,
            E_stored_into_tanks_fJ=stored,
            eta_energy=(stored / e if e else None),
            eta_including_gate_drive=(stored / (e + egb) if (e + egb) else None),
            tank_V_after_return={k: mt["VT%dQ%d" % (k, k)] for k in range(1, D + 1)},
            tank_V_end={k: mt["VT%dD" % k] for k in range(1, D + 1)},
            ITZ_uA={k: 1e6 * mt.get("ITZ%d" % k, 0.0) for k in range(1, D + 1)},
            A6b_buck_zcs_worst_uA=max(abs(1e6 * mt.get("ITZ%d" % k, 0.0))
                                      for k in range(1, D + 1)))
        r["ENERGY_LEDGER_fJ"]["buck_supply_delivered"] = e
        r["ENERGY_LEDGER_fJ"]["buck_gate_drive_RAW_signed"] = g("egb", "D")
        # THE WALL-PLUG NUMBER: the supply energy needed to put back what the
        # operation actually took out of the tanks, at the MEASURED buck efficiency.
        # The measured pulse only replaced part of it, so scaling by eta is the
        # honest steady-state figure and it is labelled DERIVED.
        r["BUCK"]["per_op_tank_energy_fJ"] = per_op_tank
        r["BUCK"]["fraction_replaced_pct"] = (100.0 * stored / per_op_tank
                                              if per_op_tank else None)
        r["E_per_op_fJ_WALL_DERIVED"] = (per_op_tank / r["BUCK"]["eta_energy"]
                                         if r["BUCK"]["eta_energy"] else None)

    # ---------------- area of the timing hardware
    r["tank_area_um2_total"] = sum(r["C_tank_fF"].values()) / 1.5
    r["n_inductors"] = D
    r["L_nH_per_bank"] = {k: blk.L_of(k, cb, meta["lmode"], meta["L_ref"])
                          for k in range(1, D + 1)}

    # ---------------- timing
    r["beat_ps"] = T
    r["II_beats"] = max(r["H"].values())
    r["II_ps"] = max(r["H"].values()) * T
    r["latency_ps"] = S["bound"][str(D)] - S["c"]["1"]
    r["latency_from_t0_ps"] = S["bound"][str(D)] - blk.T1
    return r


if __name__ == "__main__":
    tag = sys.argv[1]
    r = extract(tag)
    json.dump(r, open(os.path.join(HERE, "ROW_%s.json" % tag), "w"), indent=1,
              default=str)
    print("%s  PASS=%s  A1=%s A2=%s A6=%s  worst=%.2f%%  nfail=%d/%d  "
          "sep_min=%s  E=%.1f fJ  beat=%g ps II=%g ps  answer=%s"
          % (tag, r["PASS"], r["A1_settling_pass_90"], r["A2_value_pass"],
             r["A6_zcs_pass"], r["worst_gate_pct"], r["n_value_fail"],
             r["n_gates_checked"],
             ("%.3f" % r["separation_min_mV"]) if r["separation_min_mV"] else "n/a",
             r["E_per_op_fJ_timing_hw_included"], r["beat_ps"], r["II_ps"],
             r["A2b_block_answer_correct"]))
    print("   outputs", {k: (v["measured"], v["expected"]) for k, v in
                         r["primary_outputs"].items()})
    print("   value fails by bank", {k: v for k, v in r["value_fails_by_bank"].items() if v})
