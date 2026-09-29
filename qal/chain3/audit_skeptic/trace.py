import sys, bisect
sys.path.insert(0,'/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/skept_chain')
from police import load_prn
prn, t0, t1, step = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
sigs = sys.argv[5].split(',')
cols, rows, t = load_prn(prn)
print("%9s " % "t_ps" + "".join("%12s" % s for s in sigs))
tq = t0
while tq <= t1+1e-9:
    i = bisect.bisect_left(t, tq*1e-12)
    i = min(max(i,0), len(rows)-1)
    print("%9.2f " % (t[i]*1e12) + "".join("%12.5f" % rows[i][cols[s.upper()]] for s in sigs))
    tq += step
