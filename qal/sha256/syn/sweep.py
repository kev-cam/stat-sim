import os,re,subprocess,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import remap
VAR={
 "default":     "abc -liberty {lib}",
 "D1":          "abc -liberty {lib} -D 1",
 "D1_lut":      "abc -liberty {lib} -D 1 -dff",
 "sc_resyn2":   "abc -liberty {lib} -script +strash;dch,-f;map,-B,0.2;topo;stime,-c;buffer,-c;upsize,-c;dnsize,-c",
 "sc_del":      "abc -liberty {lib} -script +strash;dch,-f;amap;topo;stime,-c",
 "nf_D":        "abc -liberty {lib} -script +strash;ifraig;scorr;dc2;dretime;strash;&get,-n;&dch,-f;&nf,{D};&put;buffer;upsize,{D};dnsize,{D}",
 "share":       "abc -liberty {lib} -fast",
}
name=sys.argv[1]
keep=remap.SETS[name]
lib=remap.LIB
if keep is not None:
    lib=os.path.join(remap.SYN,"lib_%s.lib"%name); remap.subset_liberty(set(keep),lib)
best=None
for v,ab in VAR.items():
    outv=os.path.join(remap.SYN,"sw_%s_%s.v"%(name,v))
    sc="\n".join(["read_verilog %s"%remap.RTL,"hierarchy -check -top sha_slice",
        "proc","opt","fsm","opt","memory","opt","techmap","opt",
        ab.format(lib=lib,D="{D}"),"opt_clean","write_verilog -noattr %s"%outv])
    sp=os.path.join(remap.SYN,"sw_%s_%s.ys"%(name,v)); open(sp,"w").write(sc+"\n")
    r=subprocess.run(["yosys","-q","-s",sp],capture_output=True,text=True,timeout=900)
    if r.returncode or not os.path.exists(outv):
        print("%-10s FAIL %s"%(v,(r.stderr or r.stdout).strip().splitlines()[-1:] )); continue
    out=remap.levelize(outv)
    m=re.search(r"comb (\d+).*DEPTH (\d+)",out); pr=re.search(r"profile: (\S+)",out).group(1)
    c,d=int(m.group(1)),int(m.group(2))
    print("%-10s cells %4d DEPTH %3d  %s"%(v,c,d,pr))
    if best is None or (d,c)<best[0]: best=((d,c),v,outv)
print("BEST",best)
