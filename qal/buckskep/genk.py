#!/usr/bin/env python3
"""Generate the ONE-VARIABLE experiment the prior agent never ran.

For each (L, TON) the ONLY difference between the two decks is whether the
freewheel nMOS is DRIVEN (mode=buck) or its gate is tied low for the whole run
(mode=nofw, the prior agent's C9 form). Dead times, OUT-switch timing, fire
time, inductance and on-time are IDENTICAL between the pair.

The prior agent compared a freewheel form tested only at L=1 nH and t_on=12 ps
against a no-freewheel form swept to L=35 nH and t_on=45 ps, then attributed the
whole improvement to deleting the freewheel. This pairs them properly.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mkchain import sched, build

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "IC_C1.cir")

# bank 3 fires after hop1 opens at 303.137; bank 4 after hop2 opens at 500.096
FIRE3, FIRE4 = 305.137, 502.096
# pass-1 late cut so the inductor current zero can be READ, then iterated
TZ3_P1, TZ4_P1 = 396.0, 596.0

def gen(pass_no, zeros=None, grid=None):
    grid = grid or [(1e-9, 40.0), (10e-9, 40.0), (40e-9, 40.0)]
    made = {}
    for (L, TON) in grid:
        for mode in ("buck", "nofw"):
            tag = "K%d_%s_L%g_T%g" % (pass_no, mode, L * 1e9, TON)
            if zeros and tag.replace("K%d" % pass_no, "K1") in zeros:
                tz3, tz4 = zeros[tag.replace("K%d" % pass_no, "K1")]
            else:
                tz3, tz4 = TZ3_P1, TZ4_P1
            s3 = sched(FIRE3, TON, tz3)
            s4 = sched(FIRE4, TON, tz4)
            dst = os.path.join(HERE, tag + ".cir")
            build(SRC, dst, L, s3, s4, mode=mode)
            made[tag] = dict(L=L, TON=TON, mode=mode, tz3=tz3, tz4=tz4,
                             s3=s3, s4=s4, deck=dst)
    return made

if __name__ == "__main__":
    pass_no = int(sys.argv[1])
    zeros = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    m = gen(pass_no, zeros)
    json.dump(m, open(os.path.join(HERE, "KMETA_p%d.json" % pass_no), "w"),
              indent=1, default=str)
    for k in sorted(m): print(k)
