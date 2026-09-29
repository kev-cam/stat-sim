#!/usr/bin/env python3
"""Assemble the skeptic record: RESULTS_SKEPT.json."""
import glob, hashlib, json, os, statistics as st, time

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = "/usr/local/src/stat-sim/qal/pgcell"
P2 = os.path.join(RUN, "p2")
V = 0.7138163
FLOOR = 6.44


def J(p):
    try:
        return json.load(open(p))
    except Exception as e:
        return {"_error": str(e)}


def mean(xs):
    return st.mean(xs) if xs else None


R = {"when": time.strftime("%F %T %z"),
     "cache": "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
              "/scratchpad/vae_cache_pgcell_SKEPT",
     "dir": HERE}

# ---------------------------------------------------------------- (a) rail
rail = J(os.path.join(HERE, "RAIL.json"))
runr = J(os.path.join(RUN, "RAILDRAW.json"))
runv = J(os.path.join(RUN, "RAILDRAW_VHI.json"))
conn = J(os.path.join(HERE, "CONNAUDIT.json"))
A = {"connectivity_audit": {
        k: {s: dict(node=d["node"], n_real_circuit_elements=d["n_real_circuit_elements"],
                    VERDICT=d["VERDICT"])
            for s, d in v.items() if d["n_real_circuit_elements"] == 0}
        for k, v in conn.items() if isinstance(v, dict)}}
if "_error" not in rail:
    rows = {k: d for k, d in rail.items() if isinstance(d, dict)}
    A["instrument_inv1p2_t90_ps"] = rail.get("_instr_inv1p2_t90_ps")
    A["controls"] = {k: dict(cell=d["cell"], q_rail_fC=d["q_rail_fC"],
                             analytic_q_fC=d.get("analytic_q_fC"),
                             rel_err=(abs(d["q_rail_fC"] - d["analytic_q_fC"])
                                      / d["analytic_q_fC"]
                                      if d.get("analytic_q_fC") else None))
                     for k, d in rows.items() if d.get("pop") == "CONTROL"}
    A["gate_drive"] = {k: dict(cell=d["cell"], q_rail_fC=d["q_rail_fC"],
                               e_rail_fJ=d["e_rail_fJ"])
                       for k, d in rows.items() if d.get("pop") == "GATEDRIVE"}
    g = A["gate_drive"]
    if "gdn" in g and "gdm" in g:
        A["select_line_rail_charge_fC"] = g["gdm"]["q_rail_fC"] - g["gdn"]["q_rail_fC"]
        A["select_line_rail_energy_fJ"] = g["gdm"]["e_rail_fJ"] - g["gdn"]["e_rail_fJ"]
    pops = {}
    for pop in ("PROPER", "WHOLE_MUX", "WHOLE_XNOR", "STATIC"):
        for well in ("vhi", "rail", "-"):
            sel = [d for d in rows.values()
                   if d.get("pop") == pop and d.get("well", "-") == well]
            if not sel:
                continue
            key = "%s_%s" % (pop, well)
            pops[key] = dict(
                n=len(sel),
                cells=sorted({d["cell"] for d in sel}),
                q_rail_fC_mean=mean([d["q_rail_fC"] for d in sel]),
                q_rail_fC_min=min(d["q_rail_fC"] for d in sel),
                q_rail_fC_max=max(d["q_rail_fC"] for d in sel),
                e_rail_fJ_mean=mean([d["e_rail_fJ"] for d in sel]),
                all_correct_ckpt=all(d.get("correct_ckpt", True) for d in sel),
                per_vector={d["tag"]: dict(q=d["q_rail_fC"], e=d["e_rail_fJ"],
                                           v_ckpt=d["v_ckpt"], v_long=d["v_long"],
                                           ok=d.get("correct_ckpt"))
                            for d in sel})
    A["populations"] = pops
    # single-cell level loss on the transparent path, from the same deck
    lv = {}
    for k, d in rows.items():
        if d.get("pop") not in ("WHOLE_MUX", "WHOLE_XNOR"):
            continue
        w = d["want"]
        lv[k] = dict(well=d.get("well"), want=w,
                     loss_ckpt_mV=1e3 * ((V - d["v_ckpt"]) if w else d["v_ckpt"]),
                     loss_long_mV=1e3 * ((V - d["v_long"]) if w else d["v_long"]),
                     path=d.get("path", "transparent"), ok=d.get("correct_ckpt"))
    A["single_cell_level"] = lv
# what the run reported, for side-by-side
A["run_reported"] = dict(
    PROPER_vhi_q_fC=[runv.get("qp0", {}).get("q_rail_fC"),
                     runv.get("qp1", {}).get("q_rail_fC")],
    PROPER_rail_q_fC_mean=mean([runr[k]["q_rail_fC"] for k in ("pp0", "pp1")
                                if k in runr]),
    WHOLE_MUX_vhi_q_fC_mean=mean([runv[k]["q_rail_fC"] for k in runv
                                  if k.startswith("qm")]),
    WHOLE_MUX_rail_q_fC_mean=mean([runr[k]["q_rail_fC"] for k in runr
                                   if k.startswith("wm")]),
    STATIC_mux_q_fC_mean=mean([runr[k]["q_rail_fC"] for k in runr
                               if k.startswith("sm")]),
    STATIC_inv_q_fC_mean=mean([runr[k]["q_rail_fC"] for k in ("si0", "si1")
                               if k in runr]))
R["a_rail_draw"] = A

# ---------------------------------------------------------------- (b) chain
B = {}
for nm in ("CTL_vhi", "ALT_vhi", "ALTB_vhi", "ALTI_vhi", "ALT_rail",
           "ALT_vhi_m6", "ALT_vhi_m14"):
    p = os.path.join(HERE, "CH_%s.json" % nm)
    if not os.path.exists(p):
        B[nm] = {"_status": "not produced in this run"}
        continue
    d = J(p)
    B[nm] = dict(comp=d.get("comp"), well=d.get("well"),
                 separation_by_depth_mV=d.get("separation_by_depth_mV"),
                 x_floor_by_depth=d.get("x_floor_by_depth"),
                 rail_at_own_boundary_V=d.get("rail_at_own_boundary_V"),
                 min_HIGH_V={k: v["min_HIGH_V"] for k, v in d.get("banks", {}).items()},
                 max_LOW_V={k: v["max_LOW_V"] for k, v in d.get("banks", {}).items()},
                 worst_settle_pct={k: v["worst_settle_pct"]
                                   for k, v in d.get("banks", {}).items()},
                 all_correct_by_bank={k: v["all_correct"]
                                      for k, v in d.get("banks", {}).items()},
                 VALUE_CHECK=d.get("VALUE_CHECK"),
                 ALL_GATES_90PCT=d.get("ALL_GATES_90PCT"),
                 first_bad_bank=d.get("first_bad_bank"),
                 monotone_fade=d.get("monotone_fade"),
                 nodes_above_own_rail=d.get("nodes_above_own_rail"),
                 wall_s=d.get("wall_s"))
# the committed anchor the harness must reproduce
B["_anchor_committed_banktank_mV"] = [706.5578189999999, 612.378631,
                                      619.5096000000001, 671.433094]
if "separation_by_depth_mV" in B.get("CTL_vhi", {}):
    got = B["CTL_vhi"]["separation_by_depth_mV"]
    B["_anchor_reproduced"] = all(
        abs(a - b) < 1e-4 for a, b in zip(got, B["_anchor_committed_banktank_mV"]))
# what the run reported
B["_run_reported"] = {nm: J(os.path.join(RUN, "CHAIN_%s.json" % nm)
                            ).get("separation_by_depth_mV")
                      for nm in ("CTL_vhi", "ALT_vhi", "ALT_rail", "ALLTG_vhi")}
B["_threshold_rescore"] = J(os.path.join(HERE, "THRESH.json"))
R["b_chain"] = B

# ---------------------------------------------------- (b) supporting level
lvl = J(os.path.join(HERE, "LEVEL_SKEPT.json"))
if "_error" not in lvl:
    R["b_level_cascade"] = {
        k: dict(chain=d["chain"], well=d["well"], head_hi=d["head_hi"],
                off=d["off"], head=d["head"],
                loss_ckpt_by_depth_mV=d["loss_ckpt_by_depth_mV"],
                loss_long_by_depth_mV=d["loss_long_by_depth_mV"],
                loss_grows_with_depth=d["loss_grows_with_depth"],
                all_correct=d["all_correct"])
        for k, d in lvl.items() if isinstance(d, dict)}
    R["b_level_cascade"]["_instrument_t90_ps"] = lvl.get("_instr_inv1p2_t90_ps")

# ------------------------------------------------------- (c) equivalence
veq = J(os.path.join(HERE, "VEQ.json"))
neg = J(os.path.join(HERE, "NEGCTL.json"))
C = {"models_from": "PDK liberty sg13g2_stdcell_typ_1p20V_25C.lib `function :`",
     "pg_crosscheck": veq.get("pg_crosscheck"),
     "netlists": {k: dict(E1_sat=d.get("E1_sat", {}).get("pass_"),
                          E2_induct=d.get("E2_induct", {}).get("pass_"),
                          vectors=d.get("E3_vectors", {}).get("vectors"),
                          mismatches=d.get("E3_vectors", {}).get("mismatches"),
                          PASS=d.get("PASS"))
                  for k, d in veq.get("netlists", {}).items()},
     "negative_control": {k: dict(mutation=v.get("mutation"),
                                  DETECTED=v.get("DETECTED"),
                                  E3_mismatches=v.get("E3_vectors", {}).get("mismatches"))
                          for k, v in neg.items() if isinstance(v, dict)},
     "ALL_NETLISTS_PASS": all(d.get("PASS") for d in veq.get("netlists", {}).values()),
     "ALL_MUTANTS_DETECTED": neg.get("ALL_DETECTED")}
C["E4_real_PDK_verilog"] = J(os.path.join(HERE, "VEQ_PDKV.json"))
C["identities_brute_forced"] = J(os.path.join(HERE, "IDENTITIES_SKEPT.json"))
R["c_equivalence"] = C
R["c_census"] = J(os.path.join(HERE, "CENSUS_SKEPT.json"))
R["c_stack_depth"] = J(os.path.join(HERE, "STACKDEPTH_SKEPT.json"))

# --------------------------------------------------------- (d) bookings
R["d_bookings"] = J(os.path.join(HERE, "BOOKING.json"))
R["d_cost_consistency"] = J(os.path.join(HERE, "COST_SKEPT.json"))
R["b_offpath_diagnosis"] = J(os.path.join(HERE, "OFFPATH.json"))

# --------------------------------------------------------------- manifest
man = {}
for p in sorted(glob.glob(os.path.join(HERE, "*.py"))
                + glob.glob(os.path.join(HERE, "*.json"))
                + glob.glob(os.path.join(HERE, "*.cir"))):
    b = os.path.basename(p)
    if b == "RESULTS_SKEPT.json":
        continue
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    man[b] = dict(sha256_16=h, bytes=os.path.getsize(p),
                  mtime=time.strftime("%F %T", time.localtime(os.path.getmtime(p))))
R["manifest"] = man

json.dump(R, open(os.path.join(HERE, "RESULTS_SKEPT.json"), "w"), indent=1)
print("wrote RESULTS_SKEPT.json (%d bytes)"
      % os.path.getsize(os.path.join(HERE, "RESULTS_SKEPT.json")))
