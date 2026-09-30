import re,glob,json,math
import numpy as np
BT='/usr/local/src/stat-sim/qal/mcsize/'
PAT={1:[0,0,0,1,0,1,1,0],2:[1,1,1,0,1,0,0,1],3:[0,0,0,1,0,1,1,0],4:[1,1,1,0,1,0,0,1]}
def read_ms(p):
    v={}
    for ln in open(p):
        m=re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*([-\d.eE+]+)\s*$',ln)
        if m: v[m.group(1).upper()]=float(m.group(2))
    return v
S=[]
for d in ['bt_mc_2001.cir','bt_mc_2002.cir','bt_mc_2003.cir']:
    for p in sorted(glob.glob(BT+d+'.mt*'),key=lambda x:int(x.split('mt')[-1])): S.append(read_ms(p))
print(f"N={len(S)}")
print(f"{'link':6s} {'rail_mean':>10s} {'rail_sd':>8s} | {'gate':8s} {'want':>5s} {'level_mean':>11s} {'level_sd':>9s} {'thr=rail/2':>11s}")
for (k,r) in [(1,2),(2,3),(3,4)]:
    tg=f'M_L{k}{r}BOUND_'
    rail=np.array([s[tg+f'RAIL{r}'] for s in S])
    for i in range(8):
        v=np.array([s[tg+f'O{r}_{i}'] for s in S])
        print(f"{k}->{r:<3d} {rail.mean():10.5f} {rail.std(ddof=1):8.5f} | o{r}_{i:<5d} {PAT[r][i]:5d} "
              f"{v.mean():11.5f} {v.std(ddof=1):9.5f} {rail.mean()/2:11.5f}")
