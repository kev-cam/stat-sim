#!/usr/bin/env python3
"""Build liberty SUBSETS of the real IHP sg13g2 library for ABC mapping.

Every cell block is copied VERBATIM out of the PDK liberty -- areas, pin caps
and timing tables are the PDK's own, not invented.  Two things are constructed:




The three pg_* entries are the PDK's own xor2_1 / xnor2_1 / mux2_1 blocks with
the cell renamed and the AREA scaled by the MEASURED device-width ratio of the
Phase 1 transmission-gate cell to the static cell it replaces.  TIMING IS LEFT
AT THE STATIC CELL'S PDK TABLES, UNCHANGED, and that is declared:

  * Phase 1 MEASURED that the pass-gate transparent path has NO POST-RAMP
    SETTLING AT ALL (t50/t90 undefined -- the output is established from the
    predecessor before the local rail arrives), so the static cell's tables are
    a CONSERVATIVE stand-in, never a flattering one.
  * They are a BOOKING either way: this liberty exists to let ABC choose a
    mapping, not to produce a timing number.  No delay figure from it is quoted.

The pin-level `function` attributes are copied verbatim too, so a pg_ cell is
Boolean-identical to the static cell it stands for -- which the SAT proof then
re-checks independently.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
PDK = "/home/claude/tools/OpenROAD/test/ihp-sg13g2/sg13g2_stdcell_typ_1p20V_25C.lib"

# MEASURED device widths (qal/pgcell/pg.py tgM + the PDK spice), from census.py
AREA_SCALE = {          # pass-gate cell / static cell, by total device width
    "pg_xor2":  ("sg13g2_xor2_1",  7.44, None),
    "pg_xnor2": ("sg13g2_xnor2_1", 7.44, None),
    "pg_mux2":  ("sg13g2_mux2_1",  5.58, None),
}


def blocks(txt):
    """Split the library into (header, {cellname: text}, footer)."""
    out, i = {}, 0
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"^  cell \((\w+)\) \{", txt, re.M)]
    hdr = txt[:starts[0][0]] if starts else txt
    for j, (pos, name) in enumerate(starts):
        depth, k = 0, pos
        while True:
            ch = txt[k]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out[name] = txt[pos:k + 1]
    return hdr, out


def cell_area(block):
    m = re.search(r"area\s*:\s*([0-9.eE+-]+)\s*;", block)
    return float(m.group(1)) if m else None


def make(path, keep, pg=()):
    txt = open(PDK).read()
    hdr, cells = blocks(txt)
    body = [cells[c] for c in keep]
    notes = {}
    for newname in pg:
        src, w_pg, _ = AREA_SCALE[newname]
        blk = cells[src]
        a_static = cell_area(blk)
        # MEASURED static-cell total device width, from the PDK spice
        sys.path.insert(0, HERE)
        import census
        census.build_dev_table()
        w_static = census.DEV[src]["W_um"]
        scale = w_pg / w_static
        newblk = blk.replace("cell (%s)" % src, "cell (%s)" % newname, 1)
        newblk = re.sub(r"(area\s*:\s*)[0-9.eE+-]+(\s*;)",
                        lambda m: "%s%.6f%s" % (m.group(1), a_static * scale, m.group(2)),
                        newblk, count=1)
        body.append(newblk)
        notes[newname] = {"from": src, "W_static_um": w_static, "W_pg_um": w_pg,
                          "area_scale": round(scale, 5),
                          "area_static": a_static,
                          "area_pg": round(a_static * scale, 6),
                          "timing": "PDK static-cell tables UNCHANGED (declared "
                                    "conservative stand-in; a BOOKING, no delay "
                                    "number from this liberty is quoted)"}
    open(path, "w").write(hdr + "\n".join(body) + "\n}\n")
    return notes


if __name__ == "__main__":
    import json
    BASE = ["sg13g2_inv_1", "sg13g2_buf_1", "sg13g2_tiehi", "sg13g2_tielo", "sg13g2_nand2_1"]
    n1 = make(os.path.join(OUT, "nand.lib"), BASE)
    n2 = make(os.path.join(OUT, "pg.lib"), BASE,
              ("pg_xor2", "pg_xnor2", "pg_mux2"))
    n3 = make(os.path.join(OUT, "pgnor.lib"),
              BASE + ["sg13g2_nor2_1"],
              ("pg_xor2", "pg_xnor2", "pg_mux2"))
    json.dump({"pg.lib": n2}, open(os.path.join(OUT, "LIB_NOTES.json"), "w"), indent=1)
    print(json.dumps(n2, indent=1))
