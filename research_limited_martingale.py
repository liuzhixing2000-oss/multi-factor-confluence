"""Research-only BTC/ETH martingale backtest. No production dependencies."""
import json, urllib.request, time, math
from datetime import datetime, timezone
import numpy as np, pandas as pd

SYMS=["BTCUSDT","ETHUSDT"]; INTERVAL="60"; START=int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp()*1000)
FEE=.00055; SLIP=.00015; COST=FEE+SLIP
START_CAP=2000.; BASE_FRAC=.01; STEP_DROP=.0125; MULT=1.5; MAX_LAYERS=4; TP=.006; HARD_STOP=.05

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def klines(sym):
    out=[]; end=int(time.time()*1000)
    while end>START:
        u=f"https://api.bybit.com/v5/market/kline?category=linear&symbol={sym}&interval={INTERVAL}&end={end}&limit=1000"
        j=fetch(u); rows=j["result"]["list"]
        if not rows: break
        out += rows
        oldest=min(int(x[0]) for x in rows); end=oldest-1
        if oldest<=START: break
        time.sleep(.05)
    d=pd.DataFrame(out,columns=["ts","o","h","l","c","v","turn"])
    d=d.drop_duplicates("ts"); d["ts"]=d.ts.astype("int64"); d=d[d.ts>=START].sort_values("ts")
    for c in ["o","h","l","c","v"]:d[c]=d[c].astype(float)
    return d.reset_index(drop=True)
def features(d):
    c=d.c
    d["ema20"]=c.ewm(span=20,adjust=False).mean(); d["ema50"]=c.ewm(span=50,adjust=False).mean(); d["ema200"]=c.ewm(span=200,adjust=False).mean()
    r=c.pct_change(); d["vol20"]=r.rolling(20).std(); d["mom24"]=c/c.shift(24)-1
    # fixed, non-optimized proxy regime: quiet/non-trending long mean-reversion environment
    d["regime"]=(abs(d.ema20/d.ema50-1)<.012)&(abs(d.mom24)<.025)&(d.vol20<d.vol20.rolling(240).median())
    d["signal"]=d.regime & (c<d.ema20*.995) & (c>d.ema200*.94)
    return d
def one_cycle(d,i,filtered):
    entry=d.c.iloc[i]; equity=START_CAP; notionals=[START_CAP*BASE_FRAC]; prices=[entry]; fees=notionals[0]*COST
    next_add=entry*(1-STEP_DROP); layers=1
    for j in range(i+1,min(i+73,len(d))):
        lo,hi,cl=d.l.iloc[j],d.h.iloc[j],d.c.iloc[j]
        if layers<MAX_LAYERS and lo<=next_add:
            n=notionals[-1]*MULT; notionals.append(n); prices.append(next_add); fees+=n*COST; layers+=1; next_add*=1-STEP_DROP
        avg=sum(n*p for n,p in zip(notionals,prices))/sum(notionals)
        if hi>=avg*(1+TP):
            ex=avg*(1+TP); pnl=sum(n*(ex/p-1) for n,p in zip(notionals,prices))-fees-sum(notionals)*COST
            return j,pnl,layers
        if lo<=entry*(1-HARD_STOP):
            ex=entry*(1-HARD_STOP); pnl=sum(n*(ex/p-1) for n,p in zip(notionals,prices))-fees-sum(notionals)*COST
            return j,pnl,layers
        if filtered and not bool(d.regime.iloc[j]):
            ex=cl; pnl=sum(n*(ex/p-1) for n,p in zip(notionals,prices))-fees-sum(notionals)*COST
            return j,pnl,layers
    ex=d.c.iloc[min(i+72,len(d)-1)]; pnl=sum(n*(ex/p-1) for n,p in zip(notionals,prices))-fees-sum(notionals)*COST
    return min(i+72,len(d)-1),pnl,layers
def run_variant(d,variant):
    pnls=[]; layers=[]; i=240
    while i<len(d)-73:
        eligible=True if variant=="A" else bool(d.signal.iloc[i])
        if not eligible: i+=1; continue
        if variant=="B":
            p=d.c.iloc[i]; ex=d.c.iloc[min(i+24,len(d)-1)]; pnl=START_CAP*BASE_FRAC*(ex/p-1)-2*START_CAP*BASE_FRAC*COST; j=min(i+24,len(d)-1); l=1
        else:j,pnl,l=one_cycle(d,i,variant=="C")
        pnls.append(pnl); layers.append(l); i=j+1
    a=np.array(pnls); eq=START_CAP+np.cumsum(a); peak=np.maximum.accumulate(np.r_[START_CAP,eq]); curve=np.r_[START_CAP,eq]; dd=(curve-peak)/peak
    gains=a[a>0].sum(); losses=-a[a<0].sum()
    return {"cycles":len(a),"net":float(a.sum()),"return_pct":float(a.sum()/START_CAP*100),"expectancy":float(a.mean()) if len(a) else None,"pf":float(gains/losses) if losses else None,"win_rate":float((a>0).mean()) if len(a) else None,"max_dd_pct":float(dd.min()*100),"worst_cycle":float(a.min()) if len(a) else None,"q05":float(np.quantile(a,.05)) if len(a) else None,"q01":float(np.quantile(a,.01)) if len(a) else None,"avg_layers":float(np.mean(layers)) if layers else None}
for s in SYMS:
    d=features(klines(s)); split=int(len(d)*.7)
    print(json.dumps({"event":"sample","symbol":s,"rows":len(d),"start":datetime.fromtimestamp(d.ts.iloc[0]/1000,timezone.utc).isoformat(),"end":datetime.fromtimestamp(d.ts.iloc[-1]/1000,timezone.utc).isoformat(),"oos_start":datetime.fromtimestamp(d.ts.iloc[split]/1000,timezone.utc).isoformat(),"assumptions":{"fee_side":FEE,"slippage_side":SLIP,"base_fraction":BASE_FRAC,"add_drop":STEP_DROP,"multiplier":MULT,"max_layers":MAX_LAYERS,"tp":TP,"hard_stop":HARD_STOP}}),flush=True)
    for part,dd in [("IS",d.iloc[:split].reset_index(drop=True)),("OOS",d.iloc[split:].reset_index(drop=True))]:
        for v in ["A","B","C"]: print(json.dumps({"event":"result","symbol":s,"part":part,"variant":v,**run_variant(dd,v)}),flush=True)
print('{"event":"complete"}',flush=True)
