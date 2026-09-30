import sys, json
sys.path.insert(0, "/usr/local/src/VACASK/python")
from rawfile import rawread
exp = open("expected_bits.txt").readlines()[1].strip()
p = rawread("xbtr.raw").get()
t = p[p.names[0]]
n = len(t)
rail = p["rail"][n-1]
tnk = p["tnk"][n-1]
ok = bad = 0
badlist = []
for i in range(128):
    v = p["o%d" % i][n-1]
    want = exp[i] == "1"
    good = (v >= 0.5 * rail) if want else (v <= 0.10 * rail)
    if good: ok += 1
    else: bad += 1; badlist.append((i, round(float(v),4), exp[i]))
print(json.dumps(dict(t_end=float(t[n-1]), rail_end=float(rail), tnk_end=float(tnk),
                      npoints=n, ok=ok, bad=bad, bad_detail=badlist[:8])))
