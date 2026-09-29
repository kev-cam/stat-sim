#!/usr/bin/env python3
"""Extract the sync<->QDI adapter result from bd_qdi.cir.mt0.
Two bits are in the deck (D=1 and D=0) so per-bit numbers divide by 2.
All integrators t0-referenced at the Z checkpoint."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
T_EN_R, T_EN_F, T_END = 100.0, 600.0, 1000.0


def parse_mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d


def main():
    m = parse_mt0(os.path.join(HERE, "bd_qdi.cir.mt0"))
    f = 1e15

    def ck(tag, lbl):
        return (m["%s_%s" % (tag, lbl)] - m["%s_Z" % tag]) * f

    o = {}
    for tag, lbl in (("EENC", "encoder rail (2 bits)"),
                     ("EDEC", "decoder/completion rail (2 bits)"),
                     ("ETRE", "one completion-tree AND2 node"),
                     ("EEN2", "what the sync side pays to drive EN into the adapters")):
        o[tag] = dict(label=lbl,
                      E_DATA_phase_fJ=ck(tag, "B") - ck(tag, "A"),
                      E_NULL_phase_fJ=ck(tag, "C") - ck(tag, "B"),
                      E_full_cycle_fJ=ck(tag, "C") - ck(tag, "A"))
    o["per_bit"] = {
        "encoder_sync_to_QDI_fJ_per_bit": o["EENC"]["E_full_cycle_fJ"] / 2.0,
        "decoder_completion_QDI_to_sync_fJ_per_bit":
            o["EDEC"]["E_full_cycle_fJ"] / 2.0,
        "tree_node_fJ_per_node": o["ETRE"]["E_full_cycle_fJ"],
        "tree_fJ_per_bit_amortised_W_minus_1_nodes":
            o["ETRE"]["E_full_cycle_fJ"],       # (W-1)/W -> ~1 node per bit
        "round_trip_sync_QDI_sync_fJ_per_bit":
            (o["EENC"]["E_full_cycle_fJ"] + o["EDEC"]["E_full_cycle_fJ"]) / 2.0
            + o["ETRE"]["E_full_cycle_fJ"],
    }
    lv = {}
    for k in ("T0END", "F0END", "T1END", "F1END", "CTEND", "T0NUL", "CTNUL"):
        lv[k] = m.get(k)
    o["levels_functional_check"] = lv
    o["functional_verdict"] = (
        "PASS" if (lv["T0END"] > 1.0 and lv["F0END"] < 0.1 and
                   lv["T1END"] < 0.1 and lv["F1END"] > 1.0 and
                   lv["CTEND"] > 1.0 and lv["T0NUL"] < 0.1 and lv["CTNUL"] < 0.1)
        else "FAIL -- encoding or NULL return is wrong")
    tm = {}
    for k in ("TEN", "TT0", "TF1", "TC0", "TC1", "TCT"):
        tm[k] = m[k] * 1e12 if k in m and m[k] > 0 else None
    o["timing_ps"] = tm
    if tm["TEN"] and tm["TT0"]:
        o["timing_ps"]["encoder_delay_EN_to_T_ps"] = tm["TT0"] - tm["TEN"]
    if tm["TT0"] and tm["TCT"]:
        o["timing_ps"]["decoder_delay_T_to_tree_ps"] = tm["TCT"] - tm["TT0"]
    if tm["TEN"] and tm["TCT"]:
        o["timing_ps"]["round_trip_EN_to_completion_ps"] = tm["TCT"] - tm["TEN"]
    js = os.path.join(HERE, "qdi_rows.json")
    json.dump(o, open(js, "w"), indent=1)
    print(json.dumps(o, indent=1))
    print("\nwrote", js)


if __name__ == "__main__":
    main()
