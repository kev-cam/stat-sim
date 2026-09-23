#!/usr/bin/env python3
"""Emit statsim_model.h from ncl_th_delay.json: the shared read-only DRIVER (in-context
stage means, th23 sigma_frac per kvt, rho0) plus the transistor-MC ground truth, baked
into the binary so the shipped GPU farm needs no JSON parser on the run host."""
import json, sys
sys.path.insert(0, "/usr/local/src/stat-sim")
from statsim_delay import DelayModels, predict_ctx      # analytic golden
d = json.load(open("/usr/local/src/stat-sim/models/ncl_th_delay.json"))
ic = d["in_context_carry_ps"]; rho0 = d["inter_stage_correlation"]["rho0"]
kvt = d["kvt"]
sf = [sd/mu for sd, mu in zip(d["cells"]["th23"]["sd_ps"], d["cells"]["th23"]["mu_ps"])]
gt4, gt8 = d["ground_truth_nclfa4"], d["ground_truth_nclfa8"]
# analytic golden (predict_ctx) per N,kvt — the tight <1% faithfulness check on-device
_m = DelayModels()
an4 = [predict_ctx(_m, 4, k) for k in kvt]
an8 = [predict_ctx(_m, 8, k) for k in kvt]
def arr(name, xs, t="double"):
    fmt = "%d" if t == "int" else "%.6f"
    return "static const %s %s[] = {%s};" % (t, name, ", ".join(fmt % x for x in xs))
H = f"""// AUTO-GENERATED from ncl_th_delay.json by gen_model_header.py -- do not edit.
#pragma once
#define NKVT {len(kvt)}
{arr("KVT", kvt, "int")}
static const double T_FIRST = {ic['t_first']};
static const double T_CTX   = {ic['t_ctx']};
static const double T_LAST  = {ic['t_last']};
static const double RHO0    = {rho0};
{arr("SIGMA_FRAC", sf)}                 // th23 sigma_frac[kvt]
{arr("GT4_MU", gt4['mu_ps'])}
{arr("GT4_SD", gt4['sd_ps'])}
{arr("GT8_MU", gt8['mu_ps'])}
{arr("GT8_SD", gt8['sd_ps'])}
{arr("AN4_MU", [x[0] for x in an4])}
{arr("AN4_SD", [x[1] for x in an4])}
{arr("AN8_MU", [x[0] for x in an8])}
{arr("AN8_SD", [x[1] for x in an8])}
"""
open("statsim_model.h", "w").write(H)
print("wrote statsim_model.h")
