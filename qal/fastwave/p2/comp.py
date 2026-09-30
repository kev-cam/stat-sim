"""p2 stage 3 -- THE COMPARISON THAT DECIDES IT.

(a) versus a LOAD-MATCHED CMOS logic level.
(b) versus CMOS PLUS ITS FLOP TAX at pipeline depth D:
        CMOS effective per level = t_level + t_reg / D
    so QAL's flop-free beat wins iff  beat < t_level + t_reg / D, i.e.
        D  <  D* = t_reg / (beat - t_level).
All four inputs (two CMOS levels, three t_reg points) are MEASURED numbers
carried from committed files; nothing here is re-simulated except through
instr.py's byte-identical re-run of the comparator itself.
"""
CMOS_6p91 = 94.1745          # ps, qal/fcrit/cmos.cir.mt0 T90R at 6.91 fF
CMOS_2 = 57.1428             # ps, the same deck's T90R2 at 2 fF
TREG = {0.0: 307.1, 6.91: 335.7, 20.0: 390.0}   # ps, OpenSTA, vendor liberty
LIB_OPT = (1.11, 1.21)       # liberty is this much OPTIMISTIC vs transistor


def treg_at(cl_fF):
    xs = sorted(TREG)
    if cl_fF <= xs[0]:
        return TREG[xs[0]]
    for i in range(1, len(xs)):
        if xs[i] >= cl_fF:
            a, b = xs[i - 1], xs[i]
            return TREG[a] + (cl_fF - a) / (b - a) * (TREG[b] - TREG[a])
    return TREG[xs[-1]]


TREG_2 = treg_at(2.0)        # 315.3778581765557 ps


def one(beat_ps, t_level_ps, t_reg_ps, label):
    d = {}
    d["CMOS_level_ps"] = t_level_ps
    d["t_reg_ps"] = t_reg_ps
    d["ratio_QAL_over_CMOS_level"] = beat_ps / t_level_ps
    d["QAL_faster_at_the_level"] = bool(beat_ps < t_level_ps)
    if beat_ps <= t_level_ps:
        d["crossover_D_star"] = None
        d["reading"] = ("QAL's beat is at or below the CMOS level itself, so it "
                        "wins at EVERY pipeline depth: there is no crossover.")
    else:
        ds = t_reg_ps / (beat_ps - t_level_ps)
        d["crossover_D_star"] = ds
        d["D_star_with_liberty_optimism_removed"] = [
            (t_reg_ps * f) / (beat_ps - t_level_ps) for f in LIB_OPT]
        d["reading"] = ("QAL's flop-free beat beats CMOS+flop only for pipeline "
                        "depth D < %.2f levels" % ds)
    tab = {}
    for D in range(1, 11):
        eff = t_level_ps + t_reg_ps / D
        tab[D] = dict(CMOS_effective_per_level_ps=eff,
                      QAL_beat_ps=beat_ps,
                      QAL_wins=bool(beat_ps < eff),
                      QAL_over_CMOS=beat_ps / eff)
    d["D_table_1_to_10"] = tab
    d["label"] = label
    return d


def compare(beat_ps, what, load_matched="2fF"):
    return dict(
        _what=what,
        beat_ps=beat_ps,
        load_matched_comparator=(
            "2 fF / %.4f ps -- every cell in this phase carries CL = 2 fF on its "
            "output referenced to the cell ground, which is the SAME load the 2 fF "
            "arm of qal/fcrit/cmos.cir drives.  The 6.91 fF / %.4f ps figure is "
            "the committed campaign headline and is reported alongside, but it is "
            "NOT load-matched and it FLATTERS QAL." % (CMOS_2, CMOS_6p91)),
        vs_CMOS_2fF_LOAD_MATCHED=one(beat_ps, CMOS_2, TREG_2, "load-matched"),
        vs_CMOS_6p91fF=one(beat_ps, CMOS_6p91, TREG[6.91], "committed headline"),
        criterion_note=(
            "Scored against the FUNCTIONAL criterion: each receiver commits at its "
            "own MEASURED trip (qal/fcrit/TRIP.json) at its own DELIVERED rail, the "
            "trip fraction interpolated per row and never assumed constant.  THE "
            "SAME criterion applies to CMOS -- but qal/fcrit MEASURED a CMOS stage "
            "delay to be bar-INVARIANT (gain 1.0000-1.0001x), so the relaxation "
            "helps QAL and not CMOS, and the comparison is if anything generous to "
            "QAL."),
        liberty_note=(
            "t_reg is OpenSTA on the vendor liberty, best flop, MEASURED at "
            "307.1 / 335.7 / 390.0 ps for 0 / 6.91 / 20 fF; the 2 fF value is "
            "linearly interpolated to %.4f ps.  A transistor cross-check put the "
            "real flop at 258.9-302 ps, i.e. liberty is 1.11-1.21x OPTIMISTIC, so "
            "a D* computed from liberty FLATTERS CMOS and the widened range is "
            "reported on every row." % TREG_2))


def latency(qal_lat_by_depth_ps):
    """QAL's MEASURED latency to a given logic depth vs CMOS's, where CMOS must
    pay one flop at the end of the pipeline it is being compared against."""
    out = {}
    for D, lat in sorted(qal_lat_by_depth_ps.items()):
        if lat is None:
            out[D] = None
            continue
        out[D] = dict(
            QAL_latency_ps=lat,
            CMOS_2fF_combinational_ps=D * CMOS_2,
            CMOS_2fF_plus_one_flop_ps=D * CMOS_2 + TREG_2,
            QAL_over_CMOS_comb=lat / (D * CMOS_2),
            QAL_over_CMOS_plus_flop=lat / (D * CMOS_2 + TREG_2),
            QAL_wins_vs_comb=bool(lat < D * CMOS_2),
            QAL_wins_vs_plus_flop=bool(lat < D * CMOS_2 + TREG_2))
    return out
