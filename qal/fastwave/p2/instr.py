"""p2 stage 0 -- INSTRUMENT CHECK, before any chain row is believed.

F1  the comparator that DECIDES the run: qal/fcrit/cmos.cir copied BYTE-IDENTICAL
    (sha256 verified equal) into this directory and re-run under this phase's own
    PYMS_VAE_CACHE.  Every .mt0 measure must reproduce at rel 0.
F2  the wire model: every number in PRE_REGISTERED section E re-derived from
    qal/cipher/WIRE_MODEL.json's own fields, so a typo in the pre-registration
    cannot become a result.
F3  the logic table: recomputed from X0/ROT/FORMS and asserted against
    PRE_REGISTERED section D (w.check_logic_against_prereg).
"""
import hashlib, json, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W

HERE = W.HERE
FCRIT = "/usr/local/src/stat-sim/qal/fcrit"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def f1():
    src = os.path.join(FCRIT, "cmos.cir")
    dst = os.path.join(HERE, "F1_cmos.cir")
    shutil.copyfile(src, dst)
    assert sha(src) == sha(dst)
    t0 = time.monotonic()
    r = subprocess.run([W.XYCE, "F1_cmos.cir"], capture_output=True, text=True,
                       timeout=1200, cwd=HERE, env=W.ENV)
    wall = time.monotonic() - t0
    if r.returncode != 0:
        return dict(verdict="FAIL", err=(r.stderr or r.stdout)[-500:])
    got = W.parse_mt0(dst + ".mt0")
    ref = W.parse_mt0(os.path.join(FCRIT, "cmos.cir.mt0"))
    rel, worst = {}, 0.0
    for k in sorted(ref):
        if k not in got:
            rel[k] = "MISSING"
            worst = 1.0
            continue
        d = abs(got[k] - ref[k]) / (abs(ref[k]) if ref[k] else 1.0)
        rel[k] = d
        worst = max(worst, d)
    return dict(verdict=("PASS" if worst == 0.0 else "DRIFT"),
                max_rel=worst, wall_s=round(wall, 1),
                sha256_src=sha(src), sha256_copy=sha(dst),
                n_measures=len(ref), per_measure_rel=rel,
                CMOS_level_6p91fF_ps=got.get("T90R", 0.0) * 1e12 - 100.0,
                CMOS_level_2fF_ps=got.get("T90R2", 0.0) * 1e12 - 100.0,
                note="qal/fcrit/cmos.cir byte-identical; the 100 ps input edge is "
                     "subtracted, giving the committed 94.1745 ps at 6.91 fF and "
                     "57.1428 ps at 2 fF.")


def f2():
    wm = json.load(open("/usr/local/src/stat-sim/qal/cipher/WIRE_MODEL.json"))
    m2 = wm["layers"]["Metal2"]
    c = m2["C_bus_minpitch_fF_per_um"]
    rr = m2["R_ohm_per_um_minW"]
    pitch = wm["stdcell"]["xor2_1_um"][0]
    rotp = wm["rotate_geometry"]["chacha20_mean_over_four_rotates"]
    out = dict(source="qal/cipher/WIRE_MODEL.json",
               sha256=sha("/usr/local/src/stat-sim/qal/cipher/WIRE_MODEL.json"),
               c_fF_per_um=c, R_ohm_per_um=rr, bit_pitch_um=pitch,
               rotate_pitches=rotp,
               parts=m2["C_bus_minpitch_parts_fF_per_um"],
               tech_lef=wm["provenance"]["S1_tech_lef"],
               openrcx=wm["provenance"]["S3_openrcx_nom"])
    chk, worst = {}, 0.0
    def cmpv(nm, got, want):
        nonlocal worst
        d = abs(got - want) / (abs(want) if want else 1.0)
        chk[nm] = dict(rederived=got, in_prereg=want, rel=d)
        worst = max(worst, d)
    cmpv("W2_rot_C_fF", rotp * pitch * c, W.WIRE["W2"]["rotC"][2])
    cmpv("W2_rot_R_ohm", rotp * pitch * rr, W.WIRE["W2"]["rotR"][2])
    cmpv("W2_str_C_fF", pitch * c, W.WIRE["W2"]["strC"])
    cmpv("W2_str_R_ohm", pitch * rr, W.WIRE["W2"]["strR"])
    cmpv("W1_rot_C_fF", 16.0 * 0.15, W.WIRE["W1"]["rotC"][2])
    for r in (1, 2, 3):
        cmpv("WL_rot%d_C_fF" % r, 2.0 * r * (4 - r) / 4.0 * pitch * c,
             W.WIRE["WL"]["rotC"][r])
    out["verdict"] = "PASS" if worst < 1e-4 else "DRIFT"
    out["max_rel"] = worst
    out["checks"] = chk
    out["w2_over_w1_ratio"] = W.WIRE["W2"]["rotC"][2] / W.WIRE["W1"]["rotC"][2]
    out["w2_over_LEF_isolated_ratio"] = c / m2["C_isolated_LEF_fF_per_um"]
    return out


if __name__ == "__main__":
    out = {}
    ws, ps = W.check_logic_against_prereg()
    out["F3_logic_table"] = dict(
        verdict="PASS",
        note="recomputed from X0/ROT/FORMS and asserted equal to "
             "PRE_REGISTERED section D for all six pre-registered banks; "
             "bank 7 is the AMENDMENT P1 terminator and is not in section D.",
        outputs={("bank%d" % (k + 1)): ws[k] for k in range(len(ws))},
        paths={("bank%d" % (k + 1)): "".join(ps[k]) for k in range(len(ps))},
        restored_per_bank={("bank%d" % (k + 1)): "".join(ps[k]).count("R")
                           for k in range(len(ps))})
    out["F2_wire_model"] = f2()
    print("F2 wire model %s (max rel %.2e); PDK bus is %.2fx the brief's 0.15 "
          "fF/um figure and %.2fx the LEF isolated figure"
          % (out["F2_wire_model"]["verdict"], out["F2_wire_model"]["max_rel"],
             out["F2_wire_model"]["w2_over_w1_ratio"],
             out["F2_wire_model"]["w2_over_LEF_isolated_ratio"]))
    out["F1_comparator"] = f1()
    print("F1 comparator %s  max rel %.2e over %d measures  (%.1f s)"
          % (out["F1_comparator"]["verdict"], out["F1_comparator"].get("max_rel", -1),
             out["F1_comparator"].get("n_measures", 0),
             out["F1_comparator"].get("wall_s", 0)))
    print("   CMOS level: %.4f ps at 6.91 fF, %.4f ps at 2 fF"
          % (out["F1_comparator"].get("CMOS_level_6p91fF_ps", 0),
             out["F1_comparator"].get("CMOS_level_2fF_ps", 0)))
    json.dump(out, open(os.path.join(HERE, "INSTRUMENT_CHECK.json"), "w"), indent=1)
    print("wrote INSTRUMENT_CHECK.json")
