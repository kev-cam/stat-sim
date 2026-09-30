import math
from fractions import Fraction
def cdf(p,k,n): return sum(math.comb(n,i)*p**i*(1-p)**(n-i) for i in range(k+1))
def cp(k,n,alpha=0.05):
    def bis(f,a,b):
        fa=f(a)
        for _ in range(400):
            m=.5*(a+b); fm=f(m)
            if (fm>0)==(fa>0): a,fa=m,fm
            else: b=m
        return .5*(a+b)
    lo=0.0 if k==0 else bis(lambda p: cdf(p,k-1,n)-(1-alpha/2),0.,1.)
    hi=1.0 if k==n else bis(lambda p: cdf(p,k,n)-alpha/2,0.,1.)
    return lo,hi
print("--- closed-form checks ---")
for n in (300,50,30):
    lo,hi=cp(n,n); cf=0.025**(1.0/n)
    print(f"k=n={n}: CP lo={lo*100:.4f}%  closed form 0.025^(1/n)={cf*100:.4f}%  diff={abs(lo-cf):.2e}  hi={hi}")
print(f"\nrule of three 3/N: N=300 -> {3/300*100:.3f}%   N=200 -> {3/200*100:.3f}%   N=50 -> {3/50*100:.3f}%  N=30 -> {3/30*100:.3f}%")
print("\n--- exact one-sided 95% upper bound on failure rate at 0 failures (1-0.05^(1/N)) ---")
for n in (300,200,50,30):
    print(f"  N={n}: {(1-0.05**(1.0/n))*100:.4f}%   (rule-of-three approx {3/n*100:.3f}%)")
print("\n--- every yield claimed in the record, re-derived ---")
claims=[("DUT_A bound",0,300,"[98.78,100]"),("RX_STD",191,300,"36.33 [30.88,42.06]"),
        ("RX_SKEW",0,300,"[98.78,100]"),("DUT_B link",0,30,"[88.43,100]"),
        ("p2 1x",0,50,"[92.89,100]"),("p2 4x",5,50,"90.0 [78.19,96.67]"),
        ("p2 8x base",32,50,"36.0 [22.92,50.81]"),("p2 8x wx2",13,50,"74.0 [59.66,85.37]"),
        ("p2 8x wx4",16,50,"68.0 [53.30,80.48]"),("p2 8x lx2",8,50,"84.0 [70.89,92.83]")]
for nm,f,n,rep in claims:
    lo,hi=cp(n-f,n)
    print(f"{nm:14s} {n-f:3d}/{n:3d} pass -> yield {100*(n-f)/n:6.2f}%  CI [{lo*100:6.2f},{hi*100:6.2f}]%   record: {rep}")
def fisher(a,b,c,d):
    # two-tailed Fisher exact on [[a,b],[c,d]]
    n=a+b+c+d; r1=a+b; c1=a+c
    def pr(x): return math.comb(r1,x)*math.comb(n-r1,c1-x)/math.comb(n,c1)
    p0=pr(a); lo=max(0,c1-(n-r1)); hi=min(r1,c1)
    return sum(pr(x) for x in range(lo,hi+1) if pr(x)<=p0+1e-15)
print("\n--- Fisher exact (fail,pass) re-derived ---")
P=[("base vs wx2",32,18,13,37),("base vs wx4",32,18,16,34),("base vs lx2",32,18,8,42),
   ("wx2 vs wx4",13,37,16,34),("wx2 vs lx2",13,37,8,42),("wx4 vs lx2",16,34,8,42),
   ("wx2@8x vs base@4x",13,37,5,45)]
for nm,a,b,c,d in P:
    print(f"  {nm:20s} p={fisher(a,b,c,d):.6f}")
