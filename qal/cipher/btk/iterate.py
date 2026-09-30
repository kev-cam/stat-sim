#!/usr/bin/env python3
"""G2 fixed-point iteration on the RETURN zeros.

The committed SEQUENTIAL probe protocol measures bank k's return zero with banks
1..k-1 returning at their own measured zeros and banks k+1..N IDLE.  In the row
every bank returns, and with a wire load the return hop is long enough
(150-185 ps against a 150 ps beat) that bank k's return is still in progress when
bank k+1's starts.  So the probe environment differs from the row environment in
exactly the way banktank AMENDMENT A7 identified for the RISE, and the measured
residual |I(L)| at the commanded return-open comes out at up to 8.6 uA instead of
<= 1 uA.

Physical size, stated so it is neither over- nor under-sold: 8.6 uA against a
return peak of ~230 uA strands 1/2 L I^2 = 0.00056 fJ in the inductor -- 2.5e-6
of a 220 fJ row.  It cannot move any headline here.  It is nevertheless a
pre-registered INSTRUMENT gate, so it is cleared rather than argued away: this
script reads the ROW'S OWN waveform, finds the true zero of every I(L_k) inside
that bank's own return window, writes a corrected zeros file, and the row is
re-run.  The row's own waveform IS the row environment, so this is a fixed point,
not a different protocol.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bt import NBANK, read_prn
from btw import schedule, cfgtag


def true_return_zero(hdr, rows, k, t_from, t_to):
    """First sign change of I(L_k) after its NEGATIVE peak inside [t_from, t_to]
    (the return window).  Linear interpolation, the committed refined rule."""
    ic = hdr.index("I(L%d)" % k)
    pk, tpk = 0.0, None
    for r in rows:
        t = r[1] * 1e12
        if t < t_from or t > t_to:
            continue
        if r[ic] < pk:
            pk, tpk = r[ic], t
    if tpk is None:
        return None, None
    prev = None
    for r in rows:
        t = r[1] * 1e12
        if t <= tpk or t > t_to:
            if t <= tpk:
                prev = (t, r[ic])
            continue
        if prev is not None and (r[ic] == 0.0 or (prev[1] > 0) != (r[ic] > 0)):
            t0, v0 = prev
            t1, v1 = t, r[ic]
            return (t0 if v1 == v0 else t0 + (0.0 - v0) * (t1 - t0) / (v1 - v0)), pk
        prev = (t, r[ic])
    return None, pk


def main():
    m, T, H, dv, mode = 10.0, 150.0, 4, 1.65, "free"
    cw, wm, cm, zf = float(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    z = json.load(open(os.path.join(HERE, zf)))
    S = schedule(T, H, dv, z["tzr"], z["tzq"])
    import btw
    tag = btw.rowtag(m, T, H, dv, mode, cw, wm, cm)
    path = os.path.join(HERE, "c_%s.cir" % tag)
    hdr, rows = read_prn(path + ".prn")
    tzq = list(z["tzq"])
    out = []
    for k in range(1, NBANK + 1):
        # SEARCH ONLY INSIDE THE CONDUCTION WINDOW.  My first attempt searched
        # [r_k, r_k + 1.6 tzq_k], which runs PAST the commanded open; after the
        # open the transfer gate is off and the park has shorted L into the tank,
        # so I(L) is a park-loop current, and for banks 2 and 4 the search
        # returned a park-loop zero +83 ps late.  The transfer zero can only be
        # inside [r_k, ro_k]; a residual of +6.4 uA at ro_k means the crossing is
        # just BEFORE ro_k, which is what has to be found.
        lo = S["r"][k]
        hi = S["ro"][k] + 0.5
        t, pk = true_return_zero(hdr, rows, k, lo, hi)
        if t is None:
            print("  bank%d NO ZERO in [%.1f, %.1f]" % (k, lo, hi))
            out.append(None)
            continue
        new = t - lo
        out.append(new)
        print("  bank%d  commanded open %+9.4f ps  ->  row's own zero %+9.4f ps  "
              "(shift %+7.4f ps, return peak %.2f uA)"
              % (k, z["tzq"][k - 1], new, new - z["tzq"][k - 1], pk * 1e6))
        tzq[k - 1] = new
    z2 = dict(z)
    z2["tzq"] = tzq
    z2["iteration"] = int(z.get("iteration", 0)) + 1
    z2["protocol"] = "row_fixed_point_return_zeros (qal/cipher AMENDMENT A2)"
    nm = "z_%s_m10_dv1650_T150_H4_sp3.6_it%d.json" % (cfgtag(cw, wm, cm),
                                                      z2["iteration"])
    open(os.path.join(HERE, nm), "w").write(json.dumps(z2, indent=1))
    print("wrote %s" % nm)


if __name__ == "__main__":
    main()
