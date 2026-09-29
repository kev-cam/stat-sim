#!/usr/bin/env python3
"""THE ECONOMICS: amortised per-stage overhead of restoration vs pipelined CMOS,
and the blended energy per gate as a function of k.

Every formula here was pre-registered in PRE_REGISTERED.json.ECONOMICS_pre_stated
BEFORE any deck existed; nothing in this file chooses a definition after seeing a
number.

  QAL amortised stage       = T_min + t_res / k
  CMOS pipelined stage      = t_reg + t_level_CMOS + unc
  headline ratio            = CMOS stage / QAL stage      (a BAND, never one number)
  blended energy per gate   = (E_pre + E_restore)/k + E_hop_loss + E_gate_burn
"""
import json, os, sys

# ---- committed comparator numbers (MEASURED by others, cited, not re-derived) --
T_REG = {"0 fF": 307.1, "6.91 fF": 335.7, "20 fF": 390.0}   # OpenSTA, sg13g2_dfrbpq_1
T_REG_NOTE = ("OpenSTA on the vendor liberty with sg13g2_dfrbpq_1, the library's "
              "best flop. The transistor-level cross-check gave CLK->Q 258.9-302.25 "
              "ps, i.e. liberty is 1.11-1.21x OPTIMISTIC, so every t_reg here is a "
              "LOWER bound and every ratio below is CONSERVATIVE in CMOS's favour.")
UNC = {"flow-250": 250.0, "tree-100": 100.0, "ideal-0": 0.0}
T_LEVEL_CMOS_COMMITTED = 151.0      # ps, committed worst CMOS level
E_INV_COMMITTED = 10.0831           # fJ per hi+lo cycle, 1.2 V / 2 fF
QAL_BEAT_COMMITTED_NO_RESTORE = 123.443   # ps, committed single-hop t_level(90%)


def stage_table(T_min, t_res, k, t_level_cmos=None):
    tlc = T_LEVEL_CMOS_COMMITTED if t_level_cmos is None else t_level_cmos
    qal = T_min + t_res / float(k)
    rows = []
    for ln, tr in T_REG.items():
        for un, uv in UNC.items():
            cm = tr + tlc + uv
            rows.append(dict(t_reg_load=ln, t_reg_ps=tr, unc=un, unc_ps=uv,
                             cmos_stage_ps=cm, qal_stage_ps=qal,
                             ratio_cmos_over_qal=cm / qal))
    rs = [r["ratio_cmos_over_qal"] for r in rows]
    return dict(k=k, T_min_ps=T_min, t_res_ps=t_res, t_res_amortised_ps=t_res / float(k),
                qal_amortised_stage_ps=qal, t_level_cmos_ps=tlc,
                rows=rows, ratio_min=min(rs), ratio_max=max(rs),
                t_reg_note=T_REG_NOTE)


def energy_blend(k, E_pre_per_bit, E_restore_per_bit, E_hop_loss_per_bit,
                 E_gate_burn_per_bit):
    """per GATE (= per bank per bit) as a function of k."""
    per_gate = ((E_pre_per_bit + E_restore_per_bit) / float(k)
                + E_hop_loss_per_bit + E_gate_burn_per_bit)
    return dict(k=k,
                E_precharge_per_bit_fJ=E_pre_per_bit,
                E_restore_per_bit_fJ=E_restore_per_bit,
                amortised_pre_plus_restore_per_gate_fJ=
                (E_pre_per_bit + E_restore_per_bit) / float(k),
                E_hop_loss_per_gate_fJ=E_hop_loss_per_bit,
                E_gate_burn_per_gate_fJ=E_gate_burn_per_bit,
                blended_fJ_per_gate=per_gate,
                vs_cmos_inverter_fJ=E_INV_COMMITTED,
                ratio_cmos_over_qal=E_INV_COMMITTED / per_gate if per_gate else None)


def stage_table_own_level(T_min, t_res, k, t_inv_measured):
    """The same table but with the CMOS logic level replaced by MY OWN MEASURED
    inverter stage delay under IDENTICAL loading to the QAL bank (FO1 + 2 fF, same
    1.12u/0.74u cell, same 1.2 V).  This is the fairer match -- one CMOS inverter
    level against one QAL inverter bank -- and the committed 151.0 ps is the worst
    level of a whole mapped ALU slice, a different thing.  BOTH are reported."""
    return stage_table(T_min, t_res, k, t_level_cmos=t_inv_measured)


def full(T_min, t_res, k, t_inv_measured, E_pre_bit, E_res_bit, E_hop_bit,
         E_burn_bit, E_inv_measured):
    o = dict(
        _formulas="pre-registered in PRE_REGISTERED.json.ECONOMICS_pre_stated",
        time_committed_cmos_level=stage_table(T_min, t_res, k),
        time_own_measured_cmos_level=stage_table_own_level(T_min, t_res, k,
                                                          t_inv_measured),
        energy=dict())
    for kk in (1, 2, 3, 6):
        e = energy_blend(kk, E_pre_bit, E_res_bit, E_hop_bit, E_burn_bit)
        e["vs_my_own_measured_inverter_fJ"] = E_inv_measured
        e["ratio_my_cmos_over_qal"] = (E_inv_measured / e["blended_fJ_per_gate"]
                                       if e["blended_fJ_per_gate"] else None)
        o["energy"]["k=%d" % kk] = e
    return o


if __name__ == "__main__":
    print(json.dumps(stage_table(float(sys.argv[1]), float(sys.argv[2]),
                                 int(sys.argv[3])), indent=1))


def depth_sweep(qal_stage_ps, t_level_cmos, depths=(1, 2, 4, 10)):
    """THE HONEST DEPTH DEPENDENCE, and it is the term that decides the verdict.

    A pipelined CMOS stage contains D logic levels and ONE register, so per logic
    level it costs t_level + (t_reg + unc)/D: the register tax AMORTISES over the
    pipeline depth.  A restored QAL chain pays its restoring stage every k banks
    and its own level time every bank, so per logic level it costs the amortised
    stage time, independent of any D.

      ratio(D) = (D*t_level_cmos + t_reg + unc) / (D * qal_stage_ps)

    D = 1 is the register-tax-MAXIMAL comparator (a flop after every single logic
    level), which is the case the committed 1.5-4.7x streaming figure was quoted
    against.  It is also the case a real design almost never builds."""
    out = []
    for ln, tr in T_REG.items():
        for un, uv in UNC.items():
            for D in depths:
                cm = D * t_level_cmos + tr + uv
                out.append(dict(t_reg_load=ln, unc=un, cmos_levels_per_register=D,
                                cmos_stage_ps=cm,
                                cmos_per_level_ps=cm / D,
                                qal_per_level_ps=qal_stage_ps,
                                ratio_cmos_over_qal=cm / (D * qal_stage_ps)))
    return out
