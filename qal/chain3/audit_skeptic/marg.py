import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from police import load_prn, at, ckpts
REF = 0.6758936
print("%-16s %8s %8s %8s | %8s %8s | %9s %9s %9s | %8s" % (
  "deck","VB1@B1","VB2@B1","VB3@B2","m2_mV","m3_mV","worst_mV","%of120","cliff3","dr_h2%"))
for cir in sys.argv[1:]:
    prn=cir+'.prn'
    if not os.path.exists(prn): continue
    cp=ckpts(cir); cols,rows,t=load_prn(prn)
    r1=at(cols,rows,t,'V(RAIL1)',cp['B1']*1e-12)
    vb2=at(cols,rows,t,'V(RAIL2)',cp['B1']*1e-12)
    vb3=at(cols,rows,t,'V(RAIL3)',cp['B2']*1e-12)
    m2=(REF-vb2)*1000; m3=(REF-vb3)*1000
    worst=max(m2,m3)
    dr=100*(vb3-vb2)/vb2
    print("%-16s %8.4f %8.4f %8.4f | %8.1f %8.1f | %9.1f %9.1f | %8s | %+7.2f" % (
      os.path.basename(cir).replace('.cir',''), r1, vb2, vb3, m2, m3, worst, 100*worst/120,
      "OK" if vb3>=0.600 else "FAIL", dr))
