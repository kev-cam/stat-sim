import os,sys
sys.path.insert(0,"/usr/local/src/stat-sim/qal/lsweep")
import lsw
HERE=os.path.dirname(os.path.abspath(__file__)); lsw.HERE=HERE
C="/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_sk2b"
lsw.ENV=dict(os.environ,PYMS_DIR="/usr/local/share/xyce/PyMS",PYMS_VAE_CACHE=C)
nn,pp=set(),set()
for t in (36.0,40.0,45.0):
    w=lsw.widths(t); nn|={w["wn"],w["park"]}; pp.add(w["wp"])
L=lsw.head()+["V1 a 0 0.5","V2 b 0 0.5"]; k=0
for w in sorted(nn):
    L+=["XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u"%(k,k,w),"RN%d d%d b 1k"%(k,k)];k+=1
for w in sorted(pp):
    L+=["XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u"%(k,k,w),"RP%d e%d 0 1k"%(k,k)];k+=1
L+=[".tran 1p 10p",".print tran V(a)",".end"]
print("warm40 n=%s p=%s"%(sorted(nn),sorted(pp)))
print(lsw.run("warm40.cir",L,timeout=3000)[1])
