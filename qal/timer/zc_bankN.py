#!/usr/bin/env python3
"""Q3 (spread half): does the ZERO-CROSS instant's data spread shrink with N?

qal_bankN_zcs.json measured 61.6 ps / 16.9% full-scale zero movement vs data at N=8
(dV=0.8). Whether that spread SHRINKS with N (CLT on switching charge, like the rail
modulation's 1/sqrt(N) in qal_bankN_sqrtN.py) is UNMEASURED and decides the shared-timer
mistiming budget. This measures it at N=8/32/128.

Construction (the sqrtN scaling rule, verbatim): a bank of N=8*M gates is M PARALLEL
COPIES of the N=8 zcs unit -- C_A*M, L/M, Rs/M, switch width*M -- so the circuit is
scale-invariant in the activity fraction a=k/N and only the GRANULARITY of a changes
with N. Switch held ON throughout (this is the probe/freeze measurement, not a hop);
the observable is the first zero of I(LT).

TON=10 ps turn-on edge UNIFORMLY at every N (the sqrtN lesson: 2 ps corners abort at
N=128); the offset against the committed 2 ps N=8 zcs rows is measured and reported.

PREDICTION (pre-registered): t_zcs is a function of a alone => sigma over random words
falls ~1/sqrt(N) while the FULL-SCALE (k=0 vs k=N) spread stays ~constant.

Usage: zc_bankN.py N [mode] [count] [lane]   mode in {kgrid, perm, rand, all}
"""
import os, re, sys, json, math, time, random, subprocess

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
OUT   = os.path.join(HERE, "zc_bankN.json")

# the committed N=8 zcs unit (qal_bankN_zcs.py), dV=0.8 case
DV, CA8, L8, RS8, WSW8, N8 = 0.8, 35.0025, 400.0, 10.0, 20.0, 8
WP, WN, CLOAD, VGH = 1.12, 0.74, 2.0, 1.5
TON = 10.0

def cache_env(lane):
    base = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad"
    c = os.environ.get("PYMS_VAE_CACHE") or (base + "/vae_cache_timer")
    if lane:
        cl = base + "/vae_cache_zcn_l%s" % lane
        os.makedirs(cl, exist_ok=True)
        os.system("cp -n %s/* %s/ 2>/dev/null" % (c, cl))
        c = cl
    return dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=c)

def deck(N, pattern):
    M = N / float(N8)
    ca, l_nh, rs, wsw = CA8 * M, L8 / M, RS8 / M, WSW8 * M
    tend = 1200.0
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         '.param LT=%gn RS=%g CA=%gf' % (l_nh, rs, ca),
         'CA bka 0 {CA}', 'VHI vhi 0 %g' % VGH,
         'VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)' % (50 - TON, 50, VGH, tend, VGH),
         'VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0)' % (VGH, 50 - TON, VGH, 50, tend),
         'XSWN bka gt  sw 0   sg13_lv_nmos w=%gu l=0.13u' % wsw,
         'XSWP bka gtp sw vhi sg13_lv_pmos w=%gu l=0.13u' % (2 * wsw),
         'LT sw mid {LT}', 'RT mid bkb {RS}']
    for i, b in enumerate(pattern):
        L += ['VI%d in%d 0 %g' % (i, i, 0.0 if b else DV),
              'XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u' % (i, i, i, WP),
              'XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u' % (i, i, i, WN),
              'CL%d o%d 0 %gf' % (i, i, CLOAD)]
    L += ['.ic V(bka)=%g V(bkb)=0' % DV, '.print tran I(LT) V(bkb)',
          '.tran 0.1p %gp' % tend, '.end']
    return '\n'.join(L) + '\n'

def zero_from_prn(p):
    prev = prevt = prevv = None
    hdr = None
    for ln in open(p):
        f = ln.split()
        if hdr is None:
            if f and f[0].lower() == 'index':
                hdr = [h.upper() for h in f]
                ii = [i for i, h in enumerate(hdr) if 'LT' in h][0]
                jj = [i for i, h in enumerate(hdr) if 'BKB' in h][0]
            continue
        if not f or not f[0][0].isdigit(): continue
        try:
            t, cur, v = float(f[1]), float(f[ii]), float(f[jj])
        except (ValueError, IndexError):
            continue
        if prev is not None and prev > 0 and cur <= 0 and t > 100e-12:
            g = prev / (prev - cur) if (prev - cur) else 0.0
            return (prevt + g * (t - prevt)) * 1e12, prevv + g * (v - prevv)
        prev, prevt, prevv = cur, t, v
    return None, None

def run_one(tag, N, pattern, env):
    fn = os.path.join(HERE, 'zn_%s.cir' % tag)
    open(fn, 'w').write(deck(N, pattern))
    t0 = time.time()
    try:
        r = subprocess.run([XYCE, os.path.basename(fn)], capture_output=True, text=True,
                           timeout=900, cwd=HERE, env=env)
    except subprocess.TimeoutExpired:
        return None, None, time.time() - t0, 'TIMEOUT'
    wall = time.time() - t0
    if not os.path.exists(fn + '.prn'):
        err = '; '.join(l.strip() for l in r.stdout.splitlines()
                        if 'rror' in l or 'bort' in l)[:200]
        return None, None, wall, err or 'no prn'
    tz, vb = zero_from_prn(fn + '.prn')
    os.unlink(fn + '.prn')          # 12k rows each; keep the decks, drop the traces
    return tz, vb, wall, None

def load():
    if os.path.exists(OUT):
        try: return json.load(open(OUT))
        except Exception: pass
    return {"runs": []}

def save(db):
    db["_doc"] = ("Zero-cross instant vs DATA vs bank size N (dV=0.8, parallel-copy scaling "
                  "of the committed N=8 zcs unit, switch held ON, TON=10ps uniform). "
                  "pattern bit 1 = input LOW = output charges; k = popcount. "
                  "Tests whether the 61.6ps/16.9%% N=8 spread shrinks 1/sqrt(N).")
    json.dump(db, open(OUT, 'w'), indent=1)

def main():
    N = int(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'all'
    cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    lane = sys.argv[4] if len(sys.argv) > 4 else ''
    env = cache_env(lane)
    pats = []
    if mode in ('kgrid', 'all'):
        for x in (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0):
            k = int(round(x * N))
            pats.append(('k%d' % k, [1] * k + [0] * (N - k)))
    if mode in ('perm', 'all'):
        rng = random.Random(777)
        base = [1] * (N // 2) + [0] * (N - N // 2)
        for r in range(3):
            p = base[:]; rng.shuffle(p)
            pats.append(('perm%d' % r, p))
    if mode in ('rand', 'all'):
        rng = random.Random(12345 + N)
        for r in range(cnt):
            pats.append(('r%d' % r, [rng.randint(0, 1) for _ in range(N)]))
    db = load()
    done_tags = {r['tag'] for r in db['runs']}
    print('N=%d mode=%s: %d patterns' % (N, mode, len(pats)))
    for name, p in pats:
        tag = 'n%d_%s' % (N, name)
        if tag in done_tags:
            print('  %-12s cached' % name); continue
        tz, vb, wall, err = run_one(tag, N, p, env)
        k = sum(p)
        if tz is None:
            print('  %-12s k=%-4d FAILED %.0fs: %s' % (name, k, wall, err)); continue
        print('  %-12s k=%-4d a=%.4f  t_zcs=%8.3f ps  V_B@0=%.5f  (%.0fs)'
              % (name, k, k / float(N), tz, vb, wall))
        db['runs'].append(dict(tag=tag, N=N, k=k, a=round(k / float(N), 6),
                               pattern_name=name, t_zcs_ps=round(tz, 3),
                               V_B_at_zero=round(vb, 5), wall_s=round(wall, 1),
                               pattern_bits=''.join(str(b) for b in p)))
        save(db)
    save(db)

if __name__ == '__main__':
    main()
