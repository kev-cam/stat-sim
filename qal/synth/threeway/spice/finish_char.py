import sys
sys.path.insert(0,'.')
import char_energy_nominal as C
import json
todo = [("th12",["A","B"],1,[1.0]), ("th13",["A","B","C"],1,[1.0,3.0,10.0])]
out={}
for cell,ins,nf,loads in todo:
    for cl in loads:
        g=C.run(cell,ins,nf,cl)
        if g is None: print("%s CL=%g FAILED"%(cell,cl),flush=True); continue
        print("%-6s CL=%5gfF E=%8.3f fJ/op Ymax=%.3f td=%.0fps"%(cell,cl,g["EOP"]*1e15,g.get("YMAX",0),g.get("TD",0)*1e12),flush=True)
print("DONE",flush=True)
