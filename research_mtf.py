import time,traceback
import pandas as pd
from app import get,emit
from mtf_strategy import signals,causal_check

def candles(symbol,bars=35040):
    rows=[]; end=int(time.time()*1000)
    while len(rows)<bars:
        b=get("/v5/market/kline",{"category":"linear","symbol":symbol,"interval":"5","limit":min(1000,bars-len(rows)),"end":end})["list"]
        rows+=b; end=min(int(x[0]) for x in b)-1; time.sleep(.05)
    d=pd.DataFrame(rows,columns=["start","o","h","l","c","v","turn"]).astype(float)
    d.index=pd.to_datetime(d.start+300000,unit="ms",utc=True)
    return d.sort_index()[list("ohlcv")]

def backtest(x,s,mode):
    trades=[]; side=None; entry=stop=target=risk=0.0; best=0.0
    for i in range(20,len(x)-1):
        hi,lo=float(x.h.iloc[i]),float(x.l.iloc[i])
        if side:
            if side=="L":
                best=max(best,hi-entry)
                if mode=="trail" and best>=risk: stop=max(stop,entry)
                if mode=="trail" and best>=risk: stop=max(stop,hi-float(s.atr5.iloc[i])*1.0)
                hit=lo<=stop; win=(mode!="trail" and hi>=target)
                r=(stop-entry)/risk if hit else (2.0 if win else None)
            else:
                best=max(best,entry-lo)
                if mode=="trail" and best>=risk: stop=min(stop,entry)
                if mode=="trail" and best>=risk: stop=min(stop,lo+float(s.atr5.iloc[i])*1.0)
                hit=hi>=stop; win=(mode!="trail" and lo<=target)
                r=(entry-stop)/risk if hit else (2.0 if win else None)
            if hit or win or i>=exit_i:
                if r is None:
                    r=((float(x.c.iloc[i])-entry)/risk if side=="L" else (entry-float(x.c.iloc[i]))/risk)
                trades.append(r-0.0009); side=None
        if side is None and i+1<len(x):
            if bool(s.long_signal.iloc[i]):
                entry=float(x.o.iloc[i+1]); stop=float(s.stop_long.iloc[i]); risk=entry-stop
                if risk>0: side="L"; target=entry+(1.5 if mode=="1.5R" else 2.0)*risk; exit_i=i+48; best=0
            elif bool(s.short_signal.iloc[i]):
                entry=float(x.o.iloc[i+1]); stop=float(s.stop_short.iloc[i]); risk=stop-entry
                if risk>0: side="S"; target=entry-(1.5 if mode=="1.5R" else 2.0)*risk; exit_i=i+48; best=0
    if not trades: return {"trades":0,"win_rate":0,"total_r":0,"profit_factor":0}
    wins=[r for r in trades if r>0]; losses=[-r for r in trades if r<0]
    return {"trades":len(trades),"win_rate":round(len(wins)/len(trades),3),"total_r":round(sum(trades),3),"profit_factor":round(sum(wins)/sum(losses),3) if losses else 99.0}

def run():
    try:
        for symbol in ["ETHUSDT","BTCUSDT","SOLUSDT"]:
            x=candles(symbol); m=x.resample("15min",closed="right",label="right").agg({"o":"first","h":"max","l":"min","c":"last","v":"sum"}).dropna(); h=x.resample("60min",closed="right",label="right").agg({"o":"first","h":"max","l":"last","c":"last","v":"sum"}).dropna()
            # Correct the hourly high/low aggregation explicitly.
            h=x.resample("60min",closed="right",label="right").agg({"o":"first","h":"max","l":"min","c":"last","v":"sum"}).dropna()
            s=signals(h,m,x); causal_check(h,m,x)
            for mode in ["1.5R","2R","trail"]:
                bt=backtest(x,s,mode)
                emit({"event":"mtf_result","symbol":symbol,"mode":mode,"bars_5m":len(x),"signals":int((s.long_signal|s.short_signal).sum()),"causal_check":True,**bt})
        emit({"event":"mtf_complete"})
    except Exception: emit({"event":"mtf_failed","error":traceback.format_exc()})
if __name__=="__main__": run()
