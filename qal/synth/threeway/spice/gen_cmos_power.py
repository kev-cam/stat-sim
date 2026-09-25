#!/usr/bin/env python3
"""CMOS transistor-level power: sha_slice.cmos.v (SG13G2 stdcells) -> SPICE deck
instantiating IHP sg13g2_stdcell.spice subckts, driven by real vectors, energy by
supply-current integral in Xyce/PSP103. NO VCD, NO liberty (per user directive:
VCD is not reliable for power; use Verilog-A device sims)."""
import re, sys, random

NET  = "/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice.cmos.v"
SPF  = "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice"
MODEL= "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"   # PSP103 device .model (bound via stdcell.spice's own .include? no -> stdcell.spice includes its own)
VDD  = 1.2
NVEC = 8
TVEC = 2.0e-9        # per-vector settle window (ns) -- CMOS single-rail
random.seed(1)

# --- subckt pin orders from the IHP spice lib ---
pinorder = {}
for line in open(SPF):
    m = re.match(r'\.subckt\s+(sg13g2_\S+)\s+(.*)', line, re.I)
    if m: pinorder[m.group(1).lower()] = m.group(2).split()

# --- parse structural verilog: cell inst ( .PIN(net), ... ); ---
txt = open(NET).read()
# gather module port directions
ports_in, ports_out = [], []
mm = re.search(r'module\s+sha_slice\s*\((.*?)\);(.*)endmodule', txt, re.S)
body = mm.group(2)
for d,decl in re.findall(r'\b(input|output)\b\s*(\[[^\]]*\]\s*)?([^;]+);', body):
    for nm in decl.split(','):
        nm=nm.strip()
        if nm: (ports_in if d=='input' else ports_out).append(nm)

# expand buses: input [7:0] a; -> a[0..7]
def expand(decls, body, dir):
    out=[]
    for m in re.finditer(r'\b%s\b\s*(\[(\d+):(\d+)\])?\s*([A-Za-z_][\w,\s]*);'%dir, body):
        rng, hi, lo, names = m.group(1), m.group(2), m.group(3), m.group(4)
        for nm in names.split(','):
            nm=nm.strip()
            if not nm: continue
            if rng:
                for i in range(int(lo), int(hi)+1): out.append("%s[%d]"%(nm,i))
            else: out.append(nm)
    return out
inb = expand(None, body, 'input')
outb= expand(None, body, 'output')

def sanitize(n):
    return n.replace('[','_').replace(']','').replace('\\','').replace('.','_')

# parse instances
insts=[]
for m in re.finditer(r'(sg13g2_\w+)\s+(\S+)\s*\(\s*(.*?)\)\s*;', txt, re.S):
    ctype, inst, conns = m.group(1), m.group(2), m.group(3)
    cmap={}
    for pm in re.finditer(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', conns):
        cmap[pm.group(1)] = pm.group(2).strip()
    insts.append((ctype.lower(), inst, cmap))

# collect all nets
allnets=set()
for ct,inst,cmap in insts:
    for p,n in cmap.items(): allnets.add(n)
# emit deck
out=[]
out.append("* CMOS sha_slice transistor-level power (SG13G2 stdcells + PSP103), direct energy")
out.append('.include "%s"'%SPF)
out.append("VDD vdd 0 %g"%VDD)
out.append("VSS vss 0 0")
# input drivers (PWL) -- generate vectors
vecs=[{b:random.randint(0,1) for b in inb} for _ in range(NVEC)]
# ensure first vector all-0 baseline for a clean start
vecs[0]={b:0 for b in inb}
for b in inb:
    sb=sanitize(b)
    pts=["0 0"]
    for k,v in enumerate(vecs):
        t=(k*TVEC)
        # step at start of each window with 50ps edge
        pts.append("%.4gn %g"%((t*1e9), v[b]*VDD))
        pts.append("%.4gn %g"%((t*1e9+0.05), v[b]*VDD))
    out.append("V%s %s 0 PWL(%s)"%(sb, sb, " ".join(pts)))
# instances: map net names, tie VDD/VSS
def netmap(n):
    n=n.strip()
    if n in ("1'b0","1'b1","1'h0","1'h1"): return "0" if "0" in n else "vdd"
    return sanitize(n)
for ct,inst,cmap in insts:
    order=pinorder[ct]
    pins=[]
    for p in order:
        if p=="VDD": pins.append("vdd")
        elif p=="VSS": pins.append("vss")
        else: pins.append(netmap(cmap.get(p,"0")))
    out.append("X%s %s %s"%(sanitize(inst), " ".join(pins), ct))
# measure energy per op over a mid window (vector 4->5), steady
t0=4*TVEC; t1=5*TVEC
out.append(".tran 5p %gn uic"%((NVEC*TVEC)*1e9))
out.append(".measure tran QOP INTEG I(VDD) from=%gn to=%gn"%(t0*1e9,t1*1e9))
out.append(".measure tran EOP PARAM {%g*QOP}"%VDD)
# also total dynamic energy across all vectors (avg per op)
out.append(".measure tran QTOT INTEG I(VDD) from=%gn to=%gn"%(TVEC*1e9,(NVEC*TVEC)*1e9))
out.append(".measure tran ETOT PARAM {%g*QTOT}"%VDD)
out.append(".end")
open("cmos_slice_pwr.cir","w").write("\n".join(out)+"\n")
print("wrote cmos_slice_pwr.cir: %d stdcell instances, %d input bits, %d vectors"%(len(insts),len(inb),NVEC))
print("NOTE energy per op = EOP (one window), avg = ETOT/(NVEC-1)")
