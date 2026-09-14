"""Relaxed multi-timeframe trend-pullback strategy.
1h: small trend (EMA20 vs EMA50 and two HH/HL or LL/LH).
15m: Fibonacci 38.2%-61.8% pullback, then a close back beyond 38.2%/61.8% (reclaim).
5m: entry on pullback continuation/break of prior candle, with structural ATR stop.
"""
import numpy as np
import pandas as pd

def hourly_context(h):
    c,hig,lo=h.c,h.h,h.l
    e20=c.ewm(span=20,adjust=False,min_periods=20).mean()
    e50=c.ewm(span=50,adjust=False,min_periods=50).mean()
    hi2=hig.shift(1).rolling(48).max(); lo2=lo.shift(1).rolling(48).min()
    span=(hi2-lo2).replace(0,np.nan)
    fib38=hi2-span*.382; fib62=hi2-span*.618
    hh=(hig>hig.shift(1))&(hig.shift(1)>hig.shift(2))
    hl=(lo>lo.shift(1))&(lo.shift(1)>lo.shift(2))
    lh=(hig<hig.shift(1))&(hig.shift(1)<hig.shift(2))
    ll=(lo<lo.shift(1))&(lo.shift(1)<lo.shift(2))
    up=(e20>e50)&(hh|hl).rolling(6).sum().ge(2)
    dn=(e20<e50)&(lh|ll).rolling(6).sum().ge(2)
    return pd.DataFrame({"up":up,"dn":dn,"fib38":fib38,"fib62":fib62,"atr":(hig-lo).rolling(14).mean()},index=h.index)

def signals(one_h,fifteen_m,five_m):
    z=hourly_context(one_h).reindex(fifteen_m.index,method="ffill")
    c,o,h,l=fifteen_m.c,fifteen_m.o,fifteen_m.h,fifteen_m.l
    loz=z[["fib38","fib62"]].min(axis=1); hiz=z[["fib38","fib62"]].max(axis=1)
    atr=(h-l).rolling(14).mean()
    near_long=(l<=hiz+0.35*atr)&(c>=loz-0.25*atr)&(c<=hiz+0.5*atr)
    near_short=(h>=loz-0.35*atr)&(c<=hiz+0.25*atr)&(c>=loz-0.5*atr)
    bull=(c>o)|(c>c.shift(1)); bear=(c<o)|(c<c.shift(1))
    # Require a genuine 15m reclaim after entering the Fib pullback zone.
    # Long: price touched 38.2%-61.8% and closes back above 38.2%.
    # Short: price touched the zone and closes back below 61.8%.
    reclaim_long=near_long & bull & (c>=z.fib38)
    reclaim_short=near_short & bear & (c<=z.fib62)
    react_long=reclaim_long.rolling(3).max().fillna(False).astype(bool)
    react_short=reclaim_short.rolling(3).max().fillna(False).astype(bool)
    active_l=react_long.reindex(five_m.index,method="ffill").fillna(False).rolling(12).max().fillna(False).astype(bool)
    active_s=react_short.reindex(five_m.index,method="ffill").fillna(False).rolling(12).max().fillna(False).astype(bool)
    d=z[["up","dn"]].reindex(five_m.index,method="ffill").fillna(False)
    c5,o5,h5,l5=five_m.c,five_m.o,five_m.h,five_m.l
    pull_l=(c5>o5)&(c5>h5.shift(1)) | ((c5>c5.shift(1))&(l5>l5.shift(1)))
    pull_s=(c5<o5)&(c5<l5.shift(1)) | ((c5<c5.shift(1))&(h5<h5.shift(1)))
    out=pd.DataFrame(index=five_m.index)
    out["long_signal"]=d.up&active_l&pull_l
    out["short_signal"]=d.dn&active_s&pull_s
    out["atr5"]=(h5-l5).rolling(14).mean()
    out["stop_long"]=l5.rolling(3).min()-out.atr5*.25
    out["stop_short"]=h5.rolling(3).max()+out.atr5*.25
    return out

def causal_check(one_h,fifteen_m,five_m):
    full=signals(one_h,fifteen_m,five_m)
    for n in (len(five_m)//3,len(five_m)//2):
        part=signals(one_h[one_h.index<=five_m.index[n]],fifteen_m[fifteen_m.index<=five_m.index[n]],five_m.iloc[:n])
        pd.testing.assert_frame_equal(full.iloc[:n],part)
    return True
