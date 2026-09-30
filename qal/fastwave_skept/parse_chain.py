import re,sys,os
def parse(path):
    txt=open(path).read().splitlines()
    dev=[]; res=[]; vsrc={}
    for l in txt:
        t=l.split()
        if not t: continue
        u=t[0].upper()
        if u.startswith('X') and len(t)>=6 and t[5].lower().startswith('sg13_lv'):
            dev.append((t[0],t[1],t[2],t[3],t[4],t[5],l))
        elif u.startswith('R') and len(t)==4:
            res.append((t[0],t[1],t[2],t[3]))
        elif u.startswith('V') and len(t)>=4 and re.match(r'^[-0-9.]+$',t[3]):
            vsrc[t[1]]=float(t[3])
    return dev,res,vsrc

def cells(dev,res,nb=7,nbit=4):
    # wire: R<name> <src> <dst> <ohm>  => dst node fed from src
    wsrc={}
    for nm,a,b,r in res:
        wsrc[b]=a
    out={}
    for k in range(1,nb+1):
        for i in range(nbit):
            an='a%d_%d'%(k,i); bn='b%d_%d'%(k,i)
            yi='yi%d_%d'%(k,i); y='y%d_%d'%(k,i)
            # TG devices whose SOURCE (4th field position = t[3]) is yi
            tg=[d for d in dev if d[3]==yi]
            # inverters feeding ab / bb
            inv=[d for d in dev if d[1] in ('ab%d_%d'%(k,i),'bb%d_%d'%(k,i))]
            orv=[d for d in dev if d[1]==y]
            # determine form: find nMOS pass device (gate is bb -> conducts when b=0)
            form=None
            for nm,d,g,s,b,mod,l in tg:
                if 'nmos' in mod:
                    if g=='bb%d_%d'%(k,i):
                        # conducts when b=0, passes node d
                        if d=='ab%d_%d'%(k,i): form='yi=aXORb'   # b=0 -> yi=~a ... careful
                        else: form='yi=XNOR'
            # explicit truth-table build instead
            tab={}
            for av in (0,1):
                for bv in (0,1):
                    # TG that conducts: nMOS gate node value
                    val=None
                    for nm,d,g,s,bb_,mod,l in tg:
                        if 'nmos' not in mod: continue
                        gv = bv if g=='b%d_%d'%(k,i) else (1-bv)
                        if gv==1:
                            dv = av if d=='a%d_%d'%(k,i) else (1-av)
                            val=dv
                    tab[(av,bv)]=val
            out[(k,i)]=dict(a_from=wsrc.get(an), b_from=wsrc.get(bn),
                            tab=tab, has_inv=len(orv)>0, ntg=len(tg))
    return out
if __name__=='__main__':
    dev,res,vsrc=parse(sys.argv[1])
    C=cells(dev,res)
    head={'h0':vsrc.get('h0'),'h1':vsrc.get('h1'),'h2':vsrc.get('h2'),'h3':vsrc.get('h3')}
    print('head sources:',head, ' VHI=',vsrc.get('vhi'))
    # propagate
    val={}
    for n,v in head.items(): val[n]=1 if v>0.6 else 0
    for k in range(1,8):
        w=[]
        for i in range(4):
            c=C[(k,i)]
            af,bf=c['a_from'],c['b_from']
            av,bv=val.get(af),val.get(bf)
            yi=c['tab'][(av,bv)]
            y=1-yi if c['has_inv'] else yi
            val['y%d_%d'%(k,i)]=y
            w.append(y)
            if k<=2: print('  bank%d bit%d  a<-%s(%s)  b<-%s(%s)  tab=%s inv=%s  yi=%d y=%d'%(k,i,af,av,bf,bv,c['tab'],c['has_inv'],yi,y))
        print('DERIVED y%d = %s   (bit0..bit3)'%(k,''.join(map(str,w))))
