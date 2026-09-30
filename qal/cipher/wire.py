#!/usr/bin/env python3
"""PHASE 1 (b) -- the INTERCONNECT MODEL, extracted from the IHP-Open-PDK.

No simulation.  Pure arithmetic on committed PDK files, so this runs BEFORE the
pre-registration (its figure is what the pre-registration has to state).

SOURCES, in order of directness:

  S1  sg13g2_tech.lef (libs.ref/sg13g2_stdcell/lef) -- the routing-layer RC that
      OpenROAD/librelane themselves use for this PDK:
          CAPACITANCE CPERSQDIST  [pF/um^2]   area cap to the plane below
          EDGECAPACITANCE         [pF/um]     fringe, PER EDGE
          RESISTANCE  RPERSQ      [ohm/sq]
      Isolated-wire model:  C/L = CPERSQDIST*W + 2*EDGECAPACITANCE.
      *** This is MEASURED-FROM-PDK: the numbers are read, not modelled. ***

  S2  parasitics/itf/sg13g2_typ.itf -- conductor THICKNESS, dielectric ER,
      WMIN/SMIN.  Used to CROSS-CHECK S1 with the Sakurai-Tamaru closed form and
      to DERIVE the same-layer coupling term that the LEF model does not carry.

  S3  libs.tech/librelane/openrcx/ihp-sg13g2.nom.magic.rules -- OpenRCX pattern
      tables, `Metal n OVER m` rows are `<spacing> <coupling> <fringe> <res>`.
      Its FAR-spacing fringe corroborates S1 to 12 %.  Its MIN-spacing coupling
      does NOT corroborate anything -- it is ~4.5x the Sakurai value and ~6x a
      parallel-plate bound, so it is reported and FLAGGED, not used.

  S4  sg13g2_stdcell.lef -- cell widths and the CoreSite pitch, for the datapath
      bit pitch.
"""
import json, math, os, re, sys

PDK   = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2"
TLEF  = PDK + "/libs.ref/sg13g2_stdcell/lef/sg13g2_tech.lef"
CLEF  = PDK + "/libs.ref/sg13g2_stdcell/lef/sg13g2_stdcell.lef"
ITF   = PDK + "/libs.tech/parasitics/itf/sg13g2_typ.itf"
RCX   = PDK + "/libs.tech/librelane/openrcx/ihp-sg13g2.nom.magic.rules"
HERE  = os.path.dirname(os.path.abspath(__file__))

EPS0 = 8.8541878128e-18          # F/um


# ------------------------------------------------------------------ S1: LEF
def lef_layers():
    """Parse ROUTING layers out of the tech LEF."""
    out, cur = {}, None
    for ln in open(TLEF):
        s = ln.strip()
        m = re.match(r"^LAYER\s+(\S+)", s)
        if m:
            cur = {"name": m.group(1)}
            continue
        if s.startswith("END") and cur:
            if cur.get("TYPE") == "ROUTING":
                out[cur["name"]] = cur
            cur = None
            continue
        if cur is None:
            continue
        m = re.match(r"^TYPE\s+(\S+)\s*;", s)
        if m:
            cur["TYPE"] = m.group(1)
        m = re.match(r"^DIRECTION\s+(\S+)\s*;", s)
        if m:
            cur["DIR"] = m.group(1)
        m = re.match(r"^WIDTH\s+([\d.eE+-]+)\s*;", s)
        if m and "W" not in cur:
            cur["W"] = float(m.group(1))
        m = re.match(r"^PITCH\s+([\d.eE+-]+)", s)
        if m and "PITCH" not in cur:
            cur["PITCH"] = float(m.group(1))
        m = re.match(r"^THICKNESS\s+([\d.eE+-]+)\s*;", s)
        if m:
            cur["T"] = float(m.group(1))
        m = re.match(r"^HEIGHT\s+([\d.eE+-]+)\s*;", s)
        if m:
            cur["H"] = float(m.group(1))
        m = re.match(r"^RESISTANCE\s+RPERSQ\s+([\d.eE+-]+)\s*;", s)
        if m:
            cur["RPSQ"] = float(m.group(1))
        m = re.match(r"^CAPACITANCE\s+CPERSQDIST\s+([\d.eE+-]+)\s*;", s)
        if m:
            cur["CAREA_pF_um2"] = float(m.group(1))
        m = re.match(r"^EDGECAPACITANCE\s+([\d.eE+-]+)\s*;", s)
        if m:
            cur["CEDGE_pF_um"] = float(m.group(1))
        # the min same-layer spacing: first row of the SPACINGTABLE
        m = re.match(r"^WIDTH\s+0\.00\s+([\d.eE+-]+)", s)
        if m:
            cur.setdefault("SMIN", float(m.group(1)))
        m = re.match(r"^SPACING\s+([\d.eE+-]+)\s*;", s)
        if m:
            cur.setdefault("SMIN", float(m.group(1)))
    return out


# ------------------------------------------------------------------ S2: ITF
def itf_stack():
    cond, diel = {}, []
    for ln in open(ITF):
        s = ln.strip()
        m = re.match(r"^CONDUCTOR\s+(\S+)\s*\{(.*)\}", s)
        if m:
            d = dict(re.findall(r"(\w+)\s*=\s*([\d.eE+-]+)", m.group(2)))
            cond[m.group(1)] = {k: float(v) for k, v in d.items()}
            continue
        m = re.match(r"^DIELECTRIC\s+(\S+)\s*\{(.*)\}", s)
        if m:
            d = dict(re.findall(r"(\w+)\s*=\s*([\d.eE+-]+)", m.group(2)))
            diel.append((m.group(1), {k: float(v) for k, v in d.items()}))
    return cond, diel


def sakurai(W, T, H, S, er):
    """Sakurai & Tamaru (1983), IEEE TED 30(2) -- the standard closed form for a
    wire of width W, thickness T at height H over a ground plane, with identical
    neighbours at spacing S on the same layer.  Returns (C_ground_isolated,
    C_coupling_per_neighbour) in fF/um.  Used ONLY as a cross-check of S1 and as
    the DERIVED coupling term."""
    k = er * EPS0 * 1e15                       # fF/um
    cg = k * (1.15 * (W / H) + 2.80 * (T / H) ** 0.222)
    cc = k * (0.03 * (W / H) + 0.83 * (T / H) - 0.07 * (T / H) ** 0.222) \
         * (S / H) ** -1.34
    return cg, cc


# ------------------------------------------------------------------ S3: RCX
def rcx_over0(layer_idx):
    """First and last DIST rows of `Metal <n> OVER 0`: (s_min, cc, fringe),
    (s_far, cc, fringe).  Units pF/um; fringe is PER EDGE."""
    want = "Metal %d OVER 0" % layer_idx
    rows, on = [], False
    for ln in open(RCX):
        s = ln.strip()
        if s == want:
            on = True
            continue
        if on:
            if s.startswith("DIST count"):
                continue
            if s.startswith("END DIST"):
                break
            p = s.split()
            if len(p) == 4:
                rows.append([float(x) for x in p])
    return (rows[0], rows[-1]) if rows else (None, None)


# --------------------------------------------------------------------- main
def main():
    lef = lef_layers()
    cond, diel = itf_stack()
    R = {"provenance": {
        "S1_tech_lef": TLEF, "S2_itf": ITF, "S3_openrcx_nom": RCX,
        "S4_stdcell_lef": CLEF,
        "LEF_units": "CAPACITANCE CPERSQDIST = pF/um^2; EDGECAPACITANCE = pF/um "
                     "PER EDGE; RESISTANCE RPERSQ = ohm/square",
        "isolated_model": "C/L = CPERSQDIST*W + 2*EDGECAPACITANCE"}}

    lay = {}
    for i, nm in enumerate(["Metal1", "Metal2", "Metal3", "Metal4", "Metal5"], 1):
        d = lef[nm]
        W, S = d["W"], d["SMIN"]
        Tl, H = d["T"], d["H"]
        Ti = cond[nm]["THICKNESS"]
        # dielectric er immediately around the conductor (all inter-metal ox = 4.1)
        er = 4.1
        c_iso_lef = (d["CAREA_pF_um2"] * W + 2.0 * d["CEDGE_pF_um"]) * 1000.0  # fF/um
        cg_sak, cc_sak = sakurai(W, Tl, H, S, er)
        rmin, rfar = rcx_over0(i)
        e = dict(
            layer=nm, direction=d.get("DIR"),
            W_min_um=W, S_min_um=S, pitch_um=d.get("PITCH"),
            T_lef_um=Tl, T_itf_um=Ti, H_bottom_um=H, er_assumed=er,
            R_ohm_per_sq=d["RPSQ"], R_ohm_per_um_minW=d["RPSQ"] / W,
            C_area_fF_per_um2=d["CAREA_pF_um2"] * 1000.0,
            C_edge_fF_per_um_per_edge=d["CEDGE_pF_um"] * 1000.0,
            # --- the three figures ---
            C_isolated_LEF_fF_per_um=c_iso_lef,                       # MEASURED
            C_isolated_sakurai_fF_per_um=cg_sak,                      # cross-check
            C_couple_per_side_sakurai_fF_per_um=cc_sak,               # DERIVED
        )
        if rfar:
            e["rcx_far_spacing_um"] = rfar[0]
            e["rcx_far_fringe_fF_per_um_per_edge"] = rfar[2] * 1000.0
            e["rcx_far_total_fF_per_um"] = 2.0 * rfar[2] * 1000.0 + \
                d["CAREA_pF_um2"] * 1000.0 * W
            e["rcx_min_spacing_um"] = rmin[0]
            e["rcx_min_coupling_fF_per_um_per_side"] = rmin[1] * 1000.0
            e["rcx_min_fringe_fF_per_um_per_edge"] = rmin[2] * 1000.0
        # wire in the middle of a MIN-PITCH bus (the rotate case): the ground
        # fringe is shielded by the neighbours -- take the shielding factor from
        # the RCX table's own fringe ratio, which is the one thing in that table
        # that IS corroborated -- and add two Sakurai coupling terms.
        if rfar:
            shield = rmin[2] / rfar[2]
            e["rcx_fringe_shield_factor_at_Smin"] = shield
            c_gnd_shielded = d["CAREA_pF_um2"] * 1000.0 * W + \
                2.0 * rmin[2] * 1000.0
            e["C_bus_minpitch_fF_per_um"] = c_gnd_shielded + 2.0 * cc_sak
            e["C_bus_minpitch_parts_fF_per_um"] = dict(
                ground_shielded=c_gnd_shielded, coupling_two_sides=2.0 * cc_sak)
            # what the RCX table would say if taken at face value
            e["C_bus_minpitch_RCX_facevalue_fF_per_um"] = \
                c_gnd_shielded + 2.0 * rmin[1] * 1000.0
            e["RCX_coupling_over_sakurai_ratio"] = rmin[1] * 1000.0 / cc_sak
        # a hard parallel-plate LOWER bound on the coupling, for the flag
        e["C_couple_parallel_plate_bound_fF_per_um"] = er * EPS0 * 1e15 * Tl / S
        lay[nm] = e
    R["layers"] = lay

    # ------------------------------------------------- S4: datapath bit pitch
    sizes = {}
    mac = None
    for ln in open(CLEF):
        s = ln.strip()
        m = re.match(r"^MACRO\s+(\S+)", s)
        if m:
            mac = m.group(1)
        m = re.match(r"^SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", s)
        if m and mac:
            sizes[mac] = (float(m.group(1)), float(m.group(2)))
    site = None
    on = False
    for ln in open(CLEF):
        s = ln.strip()
        if s.startswith("SITE "):
            on = True
        if on:
            m = re.match(r"^SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", s)
            if m:
                site = (float(m.group(1)), float(m.group(2)))
                break
    R["stdcell"] = dict(
        site_um=site,
        inv_1_um=sizes.get("sg13g2_inv_1"), xor2_1_um=sizes.get("sg13g2_xor2_1"),
        and2_1_um=sizes.get("sg13g2_and2_1"), nor2_1_um=sizes.get("sg13g2_nor2_1"),
        buf_1_um=sizes.get("sg13g2_buf_1"), dfrbp_1_um=sizes.get("sg13g2_dfrbp_1"))

    # ------------------------------------------------- the ROTATE geometry
    # bit i -> bit (i+r) mod Wb.  (Wb-r) bits travel r pitches, r bits travel
    # (Wb-r) pitches (the wrap).  Mean = 2 r (Wb-r) / Wb pitches.
    def rot_mean_pitches(Wb, r):
        return 2.0 * r * (Wb - r) / float(Wb)

    chacha = [16, 12, 8, 7]
    rot = dict(
        formula="mean |delta index| = 2 r (W-r) / W  bit pitches",
        chacha20_rotations=chacha,
        chacha20_mean_pitches={str(r): rot_mean_pitches(32, r) for r in chacha},
        chacha20_mean_over_four_rotates=sum(rot_mean_pitches(32, r)
                                            for r in chacha) / 4.0,
        worst_case_32bit_r16_pitches=rot_mean_pitches(32, 16))
    R["rotate_geometry"] = rot

    # ------------------------------------------------- the figure to carry
    pitches = dict(
        brief_32um_datapath=1.00,          # the brief's own stated geometry
        pdk_site_2x=2 * site[0],           # 0.96 um: a 2-site-wide bit slice
        pdk_inv_1=sizes["sg13g2_inv_1"][0],   # 1.44 um
        pdk_xor2_1=sizes["sg13g2_xor2_1"][0])  # 3.84 um
    caps = dict(
        LEF_isolated_M2=lay["Metal2"]["C_isolated_LEF_fF_per_um"],
        campaign_assumed=0.15,
        DERIVED_bus_minpitch_M2=lay["Metal2"]["C_bus_minpitch_fF_per_um"])
    r16 = rot_mean_pitches(32, 16)
    grid = {}
    for pn, p in pitches.items():
        for cn, c in caps.items():
            Lmean = r16 * p
            grid["%s|%s" % (pn, cn)] = dict(
                bit_pitch_um=p, c_fF_per_um=c, mean_len_um=Lmean,
                C_per_bit_fF=Lmean * c,
                C_32bit_total_fF=32.0 * Lmean * c,
                R_wire_ohm=Lmean * lay["Metal2"]["R_ohm_per_um_minW"])
    R["rotate_load_grid_r16_32bit"] = grid
    R["brief_cross_check"] = dict(
        brief_claim_fF="~75 fF for a 32-bit rotate across a ~32 um datapath at "
                       "0.15 fF/um",
        this_extraction_fF=grid["brief_32um_datapath|campaign_assumed"]
                               ["C_32bit_total_fF"],
        note="reproduces the brief's own arithmetic: 16 um mean x 32 bits x 0.15")
    json.dump(R, open(os.path.join(HERE, "WIRE_MODEL.json"), "w"),
              indent=1, default=str)

    # ---------------------------------------------------------------- report
    print("PER-MICRON INTERCONNECT CAPACITANCE, IHP sg13g2 (fF/um)")
    print("%-8s %-5s %6s %6s %6s %6s | %8s %8s %8s %8s | %8s"
          % ("layer", "dir", "Wmin", "Smin", "T", "H", "LEF_iso", "Sak_iso",
             "Sak_cc", "BUS_min", "R/um"))
    for nm in ["Metal1", "Metal2", "Metal3", "Metal4", "Metal5"]:
        e = lay[nm]
        print("%-8s %-5s %6.2f %6.2f %6.3f %6.3f | %8.4f %8.4f %8.4f %8.4f | %8.3f"
              % (nm, (e["direction"] or "")[:4], e["W_min_um"], e["S_min_um"],
                 e["T_lef_um"], e["H_bottom_um"],
                 e["C_isolated_LEF_fF_per_um"], e["C_isolated_sakurai_fF_per_um"],
                 e["C_couple_per_side_sakurai_fF_per_um"],
                 e["C_bus_minpitch_fF_per_um"], e["R_ohm_per_um_minW"]))
    print()
    e = lay["Metal2"]
    print("Metal2 corroboration:")
    print("  LEF isolated               %.4f fF/um   [MEASURED-FROM-PDK]" %
          e["C_isolated_LEF_fF_per_um"])
    print("  OpenRCX far-spacing total  %.4f fF/um   (%.0f%% of LEF)" %
          (e["rcx_far_total_fF_per_um"],
           100 * e["rcx_far_total_fF_per_um"] / e["C_isolated_LEF_fF_per_um"]))
    print("  Sakurai isolated           %.4f fF/um   (%.0f%% of LEF)" %
          (e["C_isolated_sakurai_fF_per_um"],
           100 * e["C_isolated_sakurai_fF_per_um"] / e["C_isolated_LEF_fF_per_um"]))
    print("  Sakurai coupling/side      %.4f fF/um   [DERIVED]" %
          e["C_couple_per_side_sakurai_fF_per_um"])
    print("  parallel-plate bound       %.4f fF/um   (T/S only, no fringe)" %
          e["C_couple_parallel_plate_bound_fF_per_um"])
    print("  OpenRCX coupling @Smin     %.4f fF/um   *** %.1fx Sakurai, "
          "%.1fx the plate bound -> FLAGGED, NOT USED ***" %
          (e["rcx_min_coupling_fF_per_um_per_side"],
           e["RCX_coupling_over_sakurai_ratio"],
           e["rcx_min_coupling_fF_per_um_per_side"] /
           e["C_couple_parallel_plate_bound_fF_per_um"]))
    print("  min-pitch BUS wire         %.4f fF/um   [DERIVED: shielded ground "
          "%.4f + 2 x coupling %.4f]" %
          (e["C_bus_minpitch_fF_per_um"],
           e["C_bus_minpitch_parts_fF_per_um"]["ground_shielded"],
           e["C_bus_minpitch_parts_fF_per_um"]["coupling_two_sides"]))
    print()
    print("stdcell: site %s  inv_1 %s  xor2_1 %s" %
          (site, sizes["sg13g2_inv_1"], sizes["sg13g2_xor2_1"]))
    print("rotate mean length: 2r(W-r)/W bit pitches; ChaCha20 r=%s -> %s "
          "pitches (mean %.2f)" %
          (chacha, [round(rot_mean_pitches(32, r), 2) for r in chacha],
           rot["chacha20_mean_over_four_rotates"]))
    print()
    print("32-BIT ROTATE (r=16, mean 16 bit pitches) LOAD GRID")
    print("%-34s %8s %9s %9s %10s %9s"
          % ("pitch|cap", "p(um)", "c(fF/um)", "len(um)", "C/bit(fF)", "R(ohm)"))
    for k in sorted(grid):
        g = grid[k]
        print("%-34s %8.2f %9.4f %9.2f %10.3f %9.2f"
              % (k, g["bit_pitch_um"], g["c_fF_per_um"], g["mean_len_um"],
                 g["C_per_bit_fF"], g["R_wire_ohm"]))
    print()
    print("brief's own figure reproduced: 32-bit rotate, 1 um pitch, 0.15 fF/um "
          "-> %.1f fF total  (brief said ~75 fF)" %
          grid["brief_32um_datapath|campaign_assumed"]["C_32bit_total_fF"])


if __name__ == "__main__":
    main()
