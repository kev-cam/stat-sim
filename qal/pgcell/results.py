#!/usr/bin/env python3
"""Assemble RESULTS.json from the measured row files.  No simulation here."""
import glob, json, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
SIG = 6.44


def L(n):
    p = os.path.join(HERE, n)
    return json.load(open(p)) if os.path.exists(p) else None


def rows(d):
    return {k: v for k, v in (d or {}).items()
            if isinstance(v, dict) and not k.startswith("_")}


def summarize_cells():
    out = {}
    for deck in ("W", "R", "S", "V"):
        d = L("CELLS_%s.json" % deck)
        if not d:
            continue
        for k, r in rows(d).items():
            if r.get("kind") == "cmos_ref":
                out.setdefault("_instrument", {})["cmos_ref_t90_ps_%s" % deck] = \
                    r.get("t90_ps")
                continue
            out.setdefault(deck, {})[k] = r
    return out


def group(cells, pred):
    return [r for deck in cells for k, r in cells[deck].items()
            if deck != "_instrument" and pred(r)]


def stat(rs, key):
    v = [r[key] for r in rs if r.get(key) is not None]
    if not v:
        return None
    return dict(n=len(v), min=min(v), max=max(v), mean=sum(v) / len(v))


def main():
    R = {}
    R["anchor"] = dict(A=L("ANCHOR_A.json"), B=L("ANCHOR_B.json"))
    cells = summarize_cells()
    R["cells_raw_decks"] = sorted(k for k in cells if k != "_instrument")
    R["instrument"] = cells.get("_instrument", {})

    # ---- C1 function
    wrong = [(d, k) for d in cells if d != "_instrument"
             for k, r in cells[d].items() if r.get("correct_ckpt") is False]
    wrong_long = [(d, k) for d in cells if d != "_instrument"
                  for k, r in cells[d].items() if r.get("correct_long") is False]
    n_all = sum(len(cells[d]) for d in cells if d != "_instrument")
    R["C1_FUNCTION"] = dict(n_cases=n_all, wrong_at_checkpoint=wrong,
                            wrong_at_long_tail=wrong_long,
                            PASS=(len(wrong) == 0))

    # ---- C2 level (single cell), by cell kind and path
    lv = {}
    for kind in ("tg_xnor2", "tg_mux2", "pdk_xnor2", "pdk_mux2",
                 "tg_xnor2_driven", "tg_mux2_driven"):
        for pol in (1, 0):
            rs = group(cells, lambda r, K=kind, P=pol:
                       r.get("kind") == K and r.get("want") == P)
            if rs:
                lv["%s_%s" % (kind, "HIGH" if pol else "LOW")] = dict(
                    loss_ckpt_mV=stat(rs, "loss_ckpt_mV"),
                    loss_long_mV=stat(rs, "loss_long_mV"),
                    t90_ps=stat(rs, "t90_ps") if pol else None)
    R["C2_LEVEL_single_cell"] = lv
    R["LEVEL_chain"] = L("LEVEL.json")
    R["RAILDRAW"] = L("RAILDRAW.json")
    for n in ("CTL", "ALT", "ALLTG"):
        R.setdefault("CHAIN", {})[n] = L("CHAIN_%s.json" % n)
    json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    print("wrote RESULTS.json; cases %d wrong %d" % (n_all, len(wrong)))


if __name__ == "__main__":
    main()
