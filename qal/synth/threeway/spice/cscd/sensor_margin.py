#!/usr/bin/env python3
"""Turn the MEASURED supply-current waveform into the sense-FET (T2) detector
numbers: what comparator threshold the measured lull floor and quiescent floor
imply, and what detection latency that threshold buys.

Front end assumed (T2 in the survey): block current mirrored 1:K through a
sense FET into C_sense with a resistive load R. The bandwidth wall is
R*C_sense <= t_r (the current-pulse rise time), so V_sig = I_blk*R/K with
R <= t_r/C_sense.

Comparator offset floor, SG13G2 A_Vt = 3.5 mV.um (stat-sim/qal/qal_a3_mc.cir:5,
as corrected by stat-sim/qal/va/README.md:268):
  sigma_Vos = A_Vt*sqrt(2)/sqrt(W*L)   -- two input devices
"""
import sys, json, math

A_VT = 3.5e-3          # V.um


def sigma_vos(w_um, l_um):
    return A_VT * math.sqrt(2.0) / math.sqrt(w_um * l_um)


def report(sig_json):
    d = json.load(open(sig_json))
    print("=== sense-FET (T2) detector numbers from the MEASURED waveform ===")
    print("comparator input-pair offset (A_Vt = 3.5 mV.um, two devices):")
    for w, l in ((0.5, 0.13), (5.0, 1.0), (10.0, 2.0)):
        s = sigma_vos(w, l)
        print("   W=%-5g L=%-5g um : sigma_Vos = %6.2f mV   3-sigma = %6.2f mV"
              % (w, l, s * 1e3, 3 * s * 1e3))
    print("   kT/C at C_sense=20 fF  : 455 uV rms -> 3-sigma 1.37 mV (auto-zeroed floor)")
    print()

    for w in d["windows"]:
        if not w["net_toggles"]:
            continue
        tr = max(w["fwhm_ps"], 1.0) * 1e-12
        print("W%d %-22s  togs=%d  Ipk=%.4f mA  Iq=%.4f nA  FWHM=%.1f ps"
              % (w["window"], w["name"], w["net_toggles"], w["I_peak_A"] * 1e3,
                 w["I_quiescent_A"] * 1e9, w["fwhm_ps"]))
        lull = w["deepest_lulls"][0]["i_A"] if w["deepest_lulls"] else None
        for K, Cs in ((100, 20e-15), (100, 10e-15), (1000, 20e-15)):
            R = tr / Cs
            vpk = w["I_peak_A"] * R / K
            vq = w["I_quiescent_A"] * R / K
            s = "   K=%-5d C=%-5.0ffF R=%8.0f ohm : V(peak)=%8.2f mV  V(quiescent)=%9.4f mV" \
                % (K, Cs * 1e15, R, vpk * 1e3, vq * 1e3)
            if lull:
                s += "  V(deepest lull)=%8.3f mV" % (lull * R / K * 1e3)
            print(s)
        print()


if __name__ == "__main__":
    report(sys.argv[1])
