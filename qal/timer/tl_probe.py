#!/usr/bin/env python3
"""(c) replica-tracking, hop half: the tg15p TRUE ZERO vs temperature.

Byte-faithful re-emission of sw_hop_meter.py stage_probe for tg15p (switch held closed,
first zero of I(LT)), plus an .OPTIONS DEVICE TEMP line for corners. At 27C this must
reproduce the committed 266.76 ps (probe re-run instrument check).

Usage: tl_probe.py [temp]
"""
import os, re, subprocess, sys, json, math, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"

def model_for(temp):
    """corner = model-card DTA (PSP103 temperature offset); the global .OPTIONS DEVICE
    TEMP was MEASURED inert against the PyMS-compiled PSP103 (identical zeros at
    0/27/85C; all cached .so carry TR=27), while instance/model DTA moves the device
    (Id 321.7 -> 305.0 uA at +58K, dta_test.cir)."""
    return MODEL   # model-card dta was MEASURED dropped; corner goes through corner_lines()

def corner_lines(temp):
    """MEASURED mechanism: instance-level DTA via the dta shim's GDTA default
    (dta_test3.cir: Id 321.7 -> 305.0 uA at GDTA=58). Original shim at 27C so the
    27C rows stay byte-identical to the committed instrument."""
    if abs(temp - 27.0) < 1e-9:
        return ['.include "%s"' % SHIM]
    return ['.param GDTA=%g' % (temp - 27.0),
            '.include "%s"' % os.path.join(HERE, "sg13lv_dta.sp")]
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_timer"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

DV, L_NH, RS, VGH = 1.0, 277.8, 10.0, 1.5
WP, WN, MGATE, CLOAD, CA_FF = 1.12, 0.74, 8, 2.0, 35.979
T0 = 50.0
HI = [i for i in range(MGATE) if i % 2 == 0]

def main():
    temp = float(sys.argv[1]) if len(sys.argv) > 1 else 27.0
    ca = CA_FF
    cser = (ca * ca / (2 * ca)) * 1e-15
    tend = 50.0 + 6.0 * math.pi * math.sqrt((L_NH * 1e-9) * cser) * 1e12
    L = ['.hdl "%s"' % VA, '.include "%s"' % model_for(temp)] + corner_lines(temp) + [
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    L += ['.param LT=%gn RS=%g CA=%gf' % (L_NH, RS, ca),
          'CA bka 0 {CA}', 'VHI vhi 0 %g' % VGH,
          'VGT  gt  0 PWL(0 0 48p 0 50p %g %gp %g)' % (VGH, tend * 2, VGH),
          'VGTP gtp 0 PWL(0 %g 48p %g 50p 0 %gp 0)' % (VGH, VGH, tend * 2),
          'XSWN sw gt bkb 0 sg13_lv_nmos w=5u l=0.13u',
          'XSWP sw gtp bkb vhi sg13_lv_pmos w=10u l=0.13u',
          'XPK sw pk 0 0 sg13_lv_nmos w=1u l=0.13u',
          'VPK pk 0 0',
          'LT bka mid {LT}', 'RT mid sw {RS}',
          'VMGH gnh 0 0', 'VMGL gnl 0 0']
    for i in range(MGATE):
        gnd = 'gnh' if i in HI else 'gnl'
        L.append('VI%d in%d 0 %g' % (i, i, DV if i in HI else 0.0))
        L.append('XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u' % (i, i, i, WP))
        L.append('XN%d o%d in%d %s %s sg13_lv_nmos w=%gu l=0.13u' % (i, i, i, gnd, gnd, WN))
        L.append('CL%d o%d %s %gf' % (i, i, gnd, CLOAD))
    L += ['.ic V(bka)=%g V(bkb)=0' % DV,
          '.print tran I(LT) V(bkb) V(bka)',
          '.tran 0.1p %gp' % tend, '.end']
    tag = 'tl_probe_t%s' % ('%g' % temp).replace('-', 'm')
    fn = os.path.join(HERE, tag + '.cir')
    open(fn, 'w').write('\n'.join(L) + '\n')
    t0 = time.monotonic()
    subprocess.run([XYCE, os.path.basename(fn)], capture_output=True, text=True,
                   timeout=1800, cwd=HERE, env=ENV)
    wall = time.monotonic() - t0
    prev = prevt = None
    hdr = None
    tz = None
    for ln in open(fn + '.prn'):
        f = ln.split()
        if hdr is None:
            if f and f[0].lower() == 'index':
                hdr = [h.upper() for h in f]
                ii = [i for i, h in enumerate(hdr) if 'LT' in h][0]
            continue
        if not f or not f[0][0].isdigit(): continue
        try: t, cur = float(f[1]), float(f[ii])
        except (ValueError, IndexError): continue
        if prev is not None and prev > 0 and cur <= 0 and t > 60e-12:
            g = prev / (prev - cur) if (prev - cur) else 0.0
            tz = (prevt + g * (t - prevt)) * 1e12 - T0
            break
        prev, prevt = cur, t
    print('temp=%g: tg15p probe zero t_half = %s ps (committed 27C: 266.76) wall %.0fs'
          % (temp, ('%.3f' % tz) if tz else 'NOT FOUND', wall))
    fj = os.path.join(HERE, 'tl_probe.json')
    db = {}
    if os.path.exists(fj):
        try: db = json.load(open(fj))
        except Exception: db = {}
    db['t%g' % temp] = dict(temp=temp, t_zero_ps=round(tz, 3) if tz else None,
                            wall_s=round(wall, 1))
    json.dump(db, open(fj, 'w'), indent=1)

if __name__ == '__main__':
    main()
