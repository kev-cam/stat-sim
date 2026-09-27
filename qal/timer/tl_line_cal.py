#!/usr/bin/env python3
"""Instrument check G1: the delay line ALONE, against the committed inverter anchor.

24-stage FO1 chain of sg13g2_inv_1 (the PDK stdcell, PSP103 via the shim), per-stage delay
and per-stage supply energy. At 1.2V this must reproduce the async_power_anchor line
(44-inv line 1.968 ns -> 44.7 ps/stage; E_inv ~6.3 fJ/inv/traversal). At 1.5V it is the
timer's design point (the timer must swing the switch gates to VGH=1.5).

Usage: tl_line_cal.py [vdd] [temp]   (defaults 1.5 27; writes tl_cal_<vdd>_<temp>.cir)
"""
import os, re, subprocess, sys, json, time

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
CELLS = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_timer"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

NSTG = 24

def deck(vdd, temp):
    L = ['* line cal: %d-stage FO1 inv_1 chain, VDD=%g, T=%g' % (NSTG, vdd, temp),
         '.hdl "%s"' % VA, '.include "%s"' % model_for(temp)] + corner_lines(temp) + [
         '.include "%s"' % CELLS,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    L += ['VV vdd 0 %g' % vdd,
          'VIN din 0 PWL(0 0 200p 0 210p %g 2400p %g 2410p 0)' % (vdd, vdd)]
    prev = 'din'
    for i in range(NSTG):
        L.append('Xi%d c%d %s vdd 0 sg13g2_inv_1' % (i, i, prev))
        prev = 'c%d' % i
    L += ['CO c%d 0 2f' % (NSTG - 1),
          '.tran 1p 4400p',
          # c3 -> c19: 16 stages, same-polarity edges, mixes 8 rising + 8 falling
          '.measure tran T16R TRIG V(c3) VAL=%g RISE=1 TARG V(c19) VAL=%g RISE=1' % (vdd/2, vdd/2),
          '.measure tran T16F TRIG V(c3) VAL=%g FALL=1 TARG V(c19) VAL=%g FALL=1' % (vdd/2, vdd/2),
          # supply charge over one full traversal (rising launch): all 24 stages toggle once
          '.measure tran QUP INTEGRAL I(VV) FROM=150p TO=2300p',
          '.measure tran QDN INTEGRAL I(VV) FROM=2300p TO=4400p',
          '.print tran V(din) V(c3) V(c11) V(c19) V(c%d) I(VV)' % (NSTG - 1),
          '.end']
    return '\n'.join(L) + '\n'

def parse_mt0(p):
    d = {}
    for ln in open(p):
        m = re.match(r'\s*(\w+)\s*=\s*(\S+)', ln)
        if m:
            try: d[m.group(1).upper()] = float(m.group(2))
            except ValueError: pass
    return d

def main():
    vdd  = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
    temp = float(sys.argv[2]) if len(sys.argv) > 2 else 27.0
    tag = 'tl_cal_%s_%s' % (('%g' % vdd).replace('.', 'p'), ('%g' % temp).replace('-', 'm'))
    fn = os.path.join(HERE, tag + '.cir')
    open(fn, 'w').write(deck(vdd, temp))
    t0 = time.monotonic()
    r = subprocess.run([XYCE, os.path.basename(fn)], capture_output=True, text=True,
                       timeout=1200, cwd=HERE, env=ENV)
    wall = time.monotonic() - t0
    if not os.path.exists(fn + '.mt0'):
        print('XYCE FAILED (%.0fs):' % wall)
        print('\n'.join(l for l in r.stdout.splitlines() if 'rror' in l or 'bort' in l)[:800])
        sys.exit(1)
    m = parse_mt0(fn + '.mt0')
    tr, tf = m['T16R'] * 1e12, m['T16F'] * 1e12
    ps = (tr + tf) / 2.0 / 16.0
    e_up = abs(m['QUP']) * vdd * 1e15   # fJ, one rising-launch traversal, 24 stages
    e_dn = abs(m['QDN']) * vdd * 1e15
    print('VDD=%g T=%g: 16-stage %s=%.2f ps (rise-launch) %.2f ps (fall-launch)'
          % (vdd, temp, 'delay', tr, tf))
    print('  per-stage delay %.3f ps | E/traversal %.3f fJ/stage (up) %.3f (down) | wall %.0fs'
          % (ps, e_up / NSTG, e_dn / NSTG, wall))
    out = {}
    fj = os.path.join(HERE, 'tl_cal.json')
    if os.path.exists(fj):
        try: out = json.load(open(fj))
        except Exception: out = {}
    out[tag] = dict(vdd=vdd, temp=temp, n_stages=NSTG, t16_rise_ps=round(tr, 3),
                    t16_fall_ps=round(tf, 3), per_stage_ps=round(ps, 4),
                    e_per_stage_up_fJ=round(e_up / NSTG, 4),
                    e_per_stage_dn_fJ=round(e_dn / NSTG, 4), wall_s=round(wall, 1))
    json.dump(out, open(fj, 'w'), indent=1)
    print('  wrote %s' % fj)

if __name__ == '__main__':
    main()
