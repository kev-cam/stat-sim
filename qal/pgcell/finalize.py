#!/usr/bin/env python3
"""Assemble RESULTS.json from the measured rows.  No simulation here."""
import json, os, statistics as st
HERE=os.path.dirname(os.path.abspath(__file__))
SIG=6.44
def L(n):
    p=os.path.join(HERE,n); return json.load(open(p)) if os.path.exists(p) else None
def rows(d): return {k:v for k,v in (d or {}).items() if isinstance(v,dict) and not k.startswith("_")}
def agg(rs,key):
    v=[r[key] for r in rs if r.get(key) is not None]
    return None if not v else dict(n=len(v),min=min(v),max=max(v),mean=st.mean(v))

R={"_doc":"PHASE 1 RESULTS -- pass-gate XNOR2/MUX2 on a QAL rail. Pre-registration "
          "PRE_REGISTERED.json sha256 6b6d6663df54b544bcb09122c05124ff0919fcd4b7b9caf87c064b94aaeb75fd, "
          "written 2026-09-29 11:46:11 -0700 when qal/pgcell/ held one 0-byte file. "
          "MEASURED unless a row says DERIVED or ASSUMED. Every device number is a LOWER BOUND: "
          "sg13lv_compat.sp drops instance ad/as/pd/ps so the PSP103 model-card junction defaults apply "
          "and no layout parasitics are present."}

R["anchor"]={"A_bank_row":L("ANCHOR_A.json"),"B_ideal_supply_floor":L("ANCHOR_B.json"),
 "C_chain_control":"the CTL chain (4 inverter banks, tank-fed) reproduces the committed banktank "
   "headline: rails 0.7544/0.6767/0.7312/0.7201 V, separations 706.56/612.38/619.51/671.43 mV, "
   "IZ -0.0076/-0.0012/-0.0031/-0.0030 uA -- all digit-identical to qal/banktank/README.md."}

cells={}
for deck in ("W","B","V","S1"):
    d=L("CELLS_%s.json"%deck)
    if not d: continue
    for k,r in rows(d).items():
        if r.get("kind")=="cmos_ref":
            R.setdefault("instrument",{})["cmos_ref_t90_ps_%s"%deck]=r.get("t90_ps"); continue
        cells.setdefault(deck,{})[k]=r
R["instrument"]["cmos_ref_committed_ps"]=57.143
R["cells"]=cells
allc=[r for d in cells.values() for r in d.values()]
R["C1_FUNCTION"]={"n_cases":len(allc),
 "wrong_at_checkpoint":[r["tag"] for r in allc if r.get("correct_ckpt") is False],
 "wrong_at_long_tail":[r["tag"] for r in allc if r.get("correct_long") is False]}
R["C1_FUNCTION"]["PASS"]=not R["C1_FUNCTION"]["wrong_at_checkpoint"]

lv={}
for kind in ("tg_xnor2","tg_mux2","tg_xnor2_driven","tg_mux2_driven","pdk_xnor2","pdk_mux2","pdk_inv"):
    for well in ("rail","vhi","static"):
        for path in ("transparent","restored","static"):
            for pol in (1,0):
                rs=[r for r in allc if r.get("kind")==kind and r.get("well")==well
                    and r.get("path")==path and r.get("want")==pol and r.get("width") in ("tgM","pdk")]
                if rs:
                    lv["%s|%s|%s|%s"%(kind,well,path,"HIGH" if pol else "LOW")]=dict(
                        loss_ckpt_mV=agg(rs,"loss_ckpt_mV"),loss_long_mV=agg(rs,"loss_long_mV"),
                        t90_ps=agg(rs,"t90_ps"))
R["C2_LEVEL_single_cell_tgM_at_0p7138V"]=lv
R["C2_LEVEL_chained"]=L("LEVEL.json")
R["C4_RAILDRAW_railwell"]=L("RAILDRAW.json")
R["C4_RAILDRAW_fixedwell"]=L("RAILDRAW_VHI.json")
R["C5_CHAIN"]={n:L("CHAIN_%s.json"%n) for n in
               ("CTL_vhi","ALT_vhi","ALT_rail","ALLTG_vhi")}
json.dump(R,open(os.path.join(HERE,"RESULTS.json"),"w"),indent=1)
print("RESULTS.json written: %d cell cases, %d wrong@ckpt"%(
    len(allc),len(R["C1_FUNCTION"]["wrong_at_checkpoint"])))
print("wrong@ckpt:",R["C1_FUNCTION"]["wrong_at_checkpoint"])
print("wrong@long:",R["C1_FUNCTION"]["wrong_at_long_tail"])
