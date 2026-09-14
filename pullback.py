"""Frozen pullback hypotheses. No parameter search."""
import numpy as np
from engine import scores,backtest as base_backtest

def pullback_scores(d):
    s,f=scores(d)
    up=(f['4h|trend.ema.24']>0)&(f['4h|trend.slope.24']>0)&(f['1h|trend.ema.24']>0)&(f['1h|trend.slope.24']>0)
    down=(f['4h|trend.ema.24']<0)&(f['4h|trend.slope.24']<0)&(f['1h|trend.ema.24']<0)&(f['1h|trend.slope.24']<0)
    # EMA24 on closed 15m candles. First countertrend close starts a pullback.
    x=f['15m|trend.ema.24']
    long_touch=up & (x<=0) & (x.shift(1)>0)
    short_touch=down & (x>=0) & (x.shift(1)<0)
    long_recent=long_touch.shift(1).rolling(8,min_periods=1).max().eq(1)
    short_recent=short_touch.shift(1).rolling(8,min_periods=1).max().eq(1)
    long_resume=up & long_recent & (x>0)&(x.shift(1)<=0)
    short_resume=down & short_recent & (x<0)&(x.shift(1)>=0)
    eligible=s.ready & s.atr_pct.between(.001,.04)
    body=(d.c-d.o).abs(); rng=(d.h-d.l).replace(0,np.nan)
    lower=d[['o','c']].min(axis=1)-d.l; upper=d.h-d[['o','c']].max(axis=1)
    bull_pin=(lower>=2*body)&(lower>=upper)&((d.c-d.l)/rng>=.60)&(d.c>d.o)
    bear_pin=(upper>=2*body)&(upper>=lower)&((d.h-d.c)/rng>=.60)&(d.c<d.o)
    long_pin=up & long_recent & bull_pin
    short_pin=down & short_recent & bear_pin
    # 4H-only direction: no 1H trend filter, but still require a post-pullback rejection candle.
    htf_up=(f['4h|trend.ema.24']>0)
    htf_down=(f['4h|trend.ema.24']<0)
    htf_long_recent=((htf_up & (x<=0) & (x.shift(1)>0)).shift(1).rolling(8,min_periods=1).max().eq(1))
    htf_short_recent=((htf_down & (x>=0) & (x.shift(1)<0)).shift(1).rolling(8,min_periods=1).max().eq(1))
    htf_long_pin=htf_up & htf_long_recent & bull_pin
    htf_short_pin=htf_down & htf_short_recent & bear_pin
    for name,long,short in [('pullback_touch',long_touch,short_touch),('pullback_resume',long_resume,short_resume),('pullback_pinbar',long_pin,short_pin),('htf_pinbar',htf_long_pin,htf_short_pin)]:
        s[name+'_signal']=np.where(eligible&long,1,np.where(eligible&short,-1,0))
    return s

def backtest(d,policy='grouped',**kwargs):
    return base_backtest(d,policy,signal_frame=pullback_scores(d),**kwargs)
