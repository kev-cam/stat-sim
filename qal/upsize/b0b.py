#!/usr/bin/env python3
"""B0a + B0b -- the instrument check that licenses everything else.

B0a  the generator at scale=1 emits decks BYTE-IDENTICAL to Phase 1's.
B0b  that deck, RE-RUN in this study's own (copied + merged) PyMS cache,
     reproduces Phase 1's row to <=0.01% on every pre-registered quantity.

B0b is what actually licenses the cache merge (A2/A6).  No argument about
content-addressed filenames licenses it; this measurement does.
"""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
W1 = "/usr/local/src/stat-sim/qal/widebank"
TOL = 1e-4                       # 0.01 %

# (label, path-into-row) -- the pre-registered B0b quantities plus every other
# scalar the two rows share, so the check is not cherry-picked.
KEYS = [
    ("E_per_gate_headline_fJ", ["E_per_gate_headline_fJ"]),
    ("t_hop_rise_ps", ["t_hop_rise_ps"]),
    ("t_hop_return_ps", ["t_hop_return_ps"]),
    ("A2_margin_min_mV", ["A2_functional", "margin_min_mV"]),
    ("A2_rail_receiver_V", ["A2_functional", "rail_receiver_V"]),
    ("A2_vtrip_receiver_V", ["A2_functional", "vtrip_receiver_V"]),
    ("worst_gate_pct", ["worst_gate_pct"]),
    ("I_pk_bank2_uA", ["IPK_uA", "2"]),
    ("I_pk_bank1_uA", ["IPK_uA", "1"]),
    ("I_pk_bank3_uA", ["IPK_uA", "3"]),
    ("rail_bank1_V", ["rail_at_own_boundary_V", "1"]),
    ("rail_bank2_V", ["rail_at_own_boundary_V", "2"]),
    ("rail_bank3_V", ["rail_at_own_boundary_V", "3"]),
    ("E_tank_loss_fJ", ["LEDGER", "E_tank_loss_fJ"]),
    ("E_switch_conduction_fJ", ["LEDGER", "E_switch_conduction_fJ"]),
    ("E_seriesR_rise_fJ", ["LEDGER", "E_seriesR_rise_fJ"]),
    ("Q_gate_MEASURED_fC", ["LEDGER", "Q_gate_MEASURED_fC"]),
    ("Q_gate_MEASURED_per_um", ["LEDGER", "Q_gate_MEASURED_per_um"]),
    ("E_gate_drive_idealPWL_per_bank_fJ",
     ["LEDGER", "E_gate_drive_idealPWL_per_bank_fJ"]),
    ("E_wellrail_total_fJ", ["E_wellrail_total_fJ"]),
    ("separation_min_mV", ["separation_min_mV"]),
    ("t_settle90_bank2_ps", ["LEVEL_TIME_measured_bank2_ps"]),
    ("t_settle_func_bank2_ps", ["LEVEL_TIME_measured_functional_bank2_ps"]),
    ("stage_time_measured_ps", ["stage_time_measured_ps"]),
    ("A9_C_bank_measured_secant_fF", ["A9_C_bank_measured_secant_fF"]),
    ("recycle_pct_bank2", ["energy_per_bank", "2", "recycle_fraction_pct"]),
    ("E_out_of_tank_rise_bank2_fJ",
     ["energy_per_bank", "2", "E_out_of_tank_rise_fJ"]),
    ("tank_closure_residual_bank2_fJ",
     ["energy_per_bank", "2", "tank_closure_residual_fJ"]),
    ("IZ_bank2_uA", ["IZ_uA", "2"]),
    ("IZQ_bank2_uA", ["IZQ_uA", "2"]),
]


def dig(d, path):
    for k in path:
        if d is None:
            return None
        if isinstance(d, dict):
            d = d.get(k, d.get(str(k), d.get(int(k)) if str(k).isdigit()
                               else None))
        else:
            return None
    return d


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def b0a():
    out = []
    for n, T, zf, ph1 in (
            (64, 440, "zeros_n64_dv1650_T440_H4_nb3.json",
             "c_n64_T440_H4_dv1650_free_nb3.cir"),
            (8, 200, "zeros_n8_dv1650_T200_H4_nb3.json",
             "c_n8_T200_H4_dv1650_free_nb3.cir")):
        env = dict(os.environ, UP_NO_RETQG="1")
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "up.py"), "deckonly",
             str(n), str(T), "4", "1.65", "free", os.path.join(W1, zf), "1"],
            capture_output=True, text=True, env=env, cwd=HERE)
        mine = hashlib.sha256(r.stdout.encode()).hexdigest()
        theirs = sha(os.path.join(W1, ph1))
        out.append(dict(N=n, T=T, phase1_deck=ph1, sha256_mine=mine,
                        sha256_phase1=theirs, BYTE_IDENTICAL=mine == theirs,
                        note="generated with UP_NO_RETQG=1 so the A1 "
                             "return-hop .measure amendment is off; with it ON "
                             "the deck gains exactly 36 lines, all of them "
                             ".measure tran, which are passive"))
    return out


def b0b():
    tag = "n64_T440_H4_dv1650_free_nb3"
    mine_p = os.path.join(HERE, "row_%s.json" % tag)
    th_p = os.path.join(W1, "row_%s.json" % tag)
    if not os.path.exists(mine_p):
        return dict(status="row not yet produced", path=mine_p)
    m = json.load(open(mine_p))
    t = json.load(open(th_p))
    rows, worst, nfail = [], 0.0, 0
    for lbl, path in KEYS:
        a, b = dig(m, path), dig(t, path)
        try:
            a = float(a); b = float(b)
        except (TypeError, ValueError):
            rows.append(dict(key=lbl, mine=a, phase1=b, rel=None,
                             ok=None, note="non-numeric"))
            continue
        rel = abs(a - b) / abs(b) if b else (0.0 if a == b else float("inf"))
        ok = rel <= TOL
        worst = max(worst, rel)
        nfail += 0 if ok else 1
        rows.append(dict(key=lbl, mine=a, phase1=b, rel=rel, ok=bool(ok)))
    return dict(status="compared", tolerance_rel=TOL, n_quantities=len(rows),
                n_fail=nfail, worst_rel=worst, PASS=bool(nfail == 0),
                deck_sha256_mine=sha(os.path.join(HERE, "c_%s.cir" % tag))
                if os.path.exists(os.path.join(HERE, "c_%s.cir" % tag))
                else None,
                deck_sha256_phase1=sha(os.path.join(W1, "c_%s.cir" % tag)),
                deck_note="mine carries the A1 return-hop .measure lines, so "
                          "the deck sha256 differs from Phase 1's BY DESIGN; "
                          "B0a proves the generator reproduces Phase 1's bytes "
                          "exactly when that amendment is switched off",
                quantities=rows)


def main():
    res = dict(
        _doc="qal/upsize PHASE 2 instrument check. B0a = generator fidelity "
             "(byte-identical decks at scale=1). B0b = re-run fidelity in this "
             "study's own merged PyMS cache. B0b is what licenses the cache "
             "merge; no argument about filenames does.",
        B0a_transcription=b0a(), B0b_rerun=b0b())
    open(os.path.join(HERE, "INSTRUMENT_CHECK_PHASE2.json"), "w").write(
        json.dumps(res, indent=1, default=str))
    for d in res["B0a_transcription"]:
        print("B0a N=%-4d %s  %s" % (d["N"],
                                     "BYTE-IDENTICAL" if d["BYTE_IDENTICAL"]
                                     else "DIFFERS", d["sha256_mine"][:16]))
    b = res["B0b_rerun"]
    if b.get("status") != "compared":
        print("B0b: %s" % b.get("status"))
        return
    print("B0b: %s  %d/%d quantities within %.4g%%, worst rel %.3e"
          % ("PASS" if b["PASS"] else "FAIL",
             b["n_quantities"] - b["n_fail"], b["n_quantities"],
             100 * b["tolerance_rel"], b["worst_rel"]))
    for q in b["quantities"]:
        if q["ok"] is False or q["ok"] is None:
            print("   %-36s mine %s  phase1 %s  rel %s"
                  % (q["key"], q["mine"], q["phase1"], q["rel"]))


if __name__ == "__main__":
    main()
